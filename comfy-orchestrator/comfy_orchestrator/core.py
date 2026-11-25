"""Local Ollama -> unload -> ComfyUI orchestrator (standard-library only)."""

from __future__ import annotations

import base64
import copy
import json
import mimetypes
import re
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Callable


from .parameters import OrchestratorError, PARAMS, check_param
from .h3 import (
    H3_MODELS,
    H3_TURBOS,
    H3_REF2VA_TURBOS,
    H3_MODEL_LABELS,
    H3_TURBO_LABELS,
    H3_ENCODERS,
    H3_ENCODER_LABELS,
    H3_CLIPPROJ_MATRIX,
    H3_OPTION_KEYS,
    H3_REF2VA_PREFIX,
    H3_REF2VA_LABEL,
    H3_HYBRID_FILES,
    H3_HYBRID_PREFIXES,
    H3_HYBRID_DEFAULT_STEPS,
    H3_PERFORMANCE_LABELS,
    H3_SOL_VAE,
    H3_REF2VA_DEFAULT_PROMPT,
    h3_hybrid_model_key,
    h3_hybrid_filename,
    validate_h3_hybrid_steps,
    h3_ref2va_model_key,
    h3_ref2va_filename,
    h3_model_label,
    h3_model_from_label,
    ensure_h3_reference_prompt,
    split_h3_options,
    prepare_h3_workflow,
)


ALLOWED_KINDS = {"t2i", "i2i", "t2v", "i2v", "inpaint", "pose"}
WAN_I2V_ID = "wan22_i2v_5b"
H3_I2V_ID = "minimax_h3_i2v"
HUNYUAN_I2V_ID = "hunyuan15_i2v_480p"
QWEN_T2I_ID = "qwen_image_2512_t2i"
QWEN_LIGHTNING_ID = "qwen_image_2512_lightning_t2i"
QWEN_IDS = frozenset({QWEN_T2I_ID, QWEN_LIGHTNING_ID})
SDXL_WORKFLOW_IDS = frozenset({"wai_t2i_basic", "wai_i2i_basic", "wai_inpaint_basic",
                               "wai_pose_skeleton", "wai_pose_detect"})
DEFAULT_SDXL_CHECKPOINT = "waiIllustriousSDXL_v170.safetensors"
HOST_VIDEO_IDS = frozenset({WAN_I2V_ID, H3_I2V_ID, HUNYUAN_I2V_ID})
VIDEO_KINDS = frozenset({"i2v", "t2v"})
IMAGE_INPUTS = frozenset({"image", "mask", "pose"})

# Image-only I2V still needs valid text conditioning. This neutral fallback
# makes motion possible without inventing characters, actions or a camera move.
I2V_DEFAULT_PROMPT = "Natural, coherent motion while preserving the reference image's subject appearance and visual style."
def supports_empty_i2v_request(config: dict, workflow_id: str | None,
                               image=None, mask=None, pose=None, composition=None) -> bool:
    entry = config.get("workflows", {}).get(workflow_id, {})
    return (
        entry.get("kind") == "i2v"
        and IMAGE_INPUTS.intersection(entry.get("bindings", {})) == {"image"}
        and image is not None and mask is None and pose is None and composition is None
    )


def needs_prompt_llm(config: dict, request: str, character_traits=None,
                     composition_image=None, *, workflow_id: str | None = None) -> bool:
    """I2V uses the reference directly, with text-only LLM assistance if requested."""
    if config.get("workflows", {}).get(workflow_id, {}).get("kind") == "i2v":
        return bool(request.strip())
    return bool(request.strip() or character_traits or composition_image
                or config.get("llm", {}).get("send_reference_to_llm", False))


def sdxl_checkpoint_kind(name: str) -> str | None:
    """Recognize the supported checkpoint families without loading unknown weights."""
    if not isinstance(name, str) or not name or len(name) > 1024:
        return None
    parts = name.replace("\\", "/").split("/")
    if any(not part or part in (".", "..") or ":" in part for part in parts):
        return None
    filename = parts[-1].lower()
    if not filename.endswith((".safetensors", ".ckpt")):
        return None
    stem = re.sub(r"[^a-z0-9]", "", filename.rsplit(".", 1)[0])
    if "illustrious" in stem:
        return "illustrious"
    if "sdxlturbo" in stem or "stablediffusionxlturbo" in stem:
        return "turbo"
    return None


def split_checkpoint_option(parameters: dict, workflow_ids) -> tuple[dict, dict]:
    """Model filenames are host-owned, not an LLM parameter."""
    inputs = dict(parameters)
    if "checkpoint_model" not in inputs:
        return inputs, {}
    name = inputs.pop("checkpoint_model")
    kind = sdxl_checkpoint_kind(name)
    ids = set(workflow_ids)
    if not ids or not ids <= SDXL_WORKFLOW_IDS or kind is None:
        raise OrchestratorError("このワークフローに対応しないSDXLチェックポイントです")
    if kind == "turbo" and ids != {"wai_t2i_basic"}:
        raise OrchestratorError("SDXL Turboは画像生成（T2I）を選択してください")
    return inputs, {"checkpoint_model": name}


def prepare_checkpoint_workflow(template: dict, options: dict) -> dict:
    if not options:
        return template
    graph = copy.deepcopy(template)
    loader = graph.get("2", {})
    if loader.get("class_type") != "CheckpointLoaderSimple" or "ckpt_name" not in loader.get("inputs", {}):
        raise OrchestratorError("標準SDXLチェックポイントノードが見つかりません")
    name = options["checkpoint_model"]
    loader["inputs"]["ckpt_name"] = name
    if sdxl_checkpoint_kind(name) == "turbo":
        sampler = graph.get("11", {})
        if sampler.get("class_type") != "KSampler":
            raise OrchestratorError("SDXL Turbo用サンプラーが見つかりません")
        sampler["inputs"].update(sampler_name="euler_ancestral", scheduler="normal", steps=4, cfg=1)
    return graph


def installed_model_choices(inventory: dict) -> dict:
    """Only show registered architectures and installed filenames."""
    native = inventory.get("UNETLoader", ())
    gguf = inventory.get("UnetLoaderGGUF", ())
    return {
        "h3": (tuple(key for key, name in H3_MODELS.items()
                     if name in (gguf if name.endswith(".gguf") else native))
               + tuple(dict.fromkeys(key for name in native
                                     if (key := h3_ref2va_model_key(name)) is not None))
               + tuple(dict.fromkeys(key for name in native for reference_only in (False, True)
                                     if (key := h3_hybrid_model_key(name, reference_only=reference_only)) is not None))),
        "sdxl": tuple(name for name in inventory.get("CheckpointLoaderSimple", ())
                      if sdxl_checkpoint_kind(name) is not None),
    }


def supplied_inputs(image=None, mask=None, pose=None) -> frozenset[str]:
    return frozenset(name for name, value in (("image", image), ("mask", mask), ("pose", pose)) if value is not None)


def compatible_workflows(workflows: dict, image=None, mask=None, pose=None) -> dict:
    supplied = supplied_inputs(image, mask, pose)
    return {
        key: entry for key, entry in workflows.items()
        if IMAGE_INPUTS.intersection(entry["bindings"]) == supplied
    }



def http_json(base: str, route: str, payload: Any = None, timeout: float = 60, allow_empty: bool = False) -> dict:
    url = base.rstrip("/") + "/" + route.lstrip("/")
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"} if data is not None else {},
        method="POST" if data is not None else "GET",
    )
    return _open_json(request, timeout, allow_empty)


def _open_json(request: urllib.request.Request, timeout: float, allow_empty: bool = False) -> dict:
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
            result = json.loads(body) if body else ({} if allow_empty else None)
    except urllib.error.HTTPError as exc:
        reason = exc.read(1200).decode("utf-8", errors="replace")
        raise OrchestratorError(f"HTTP {exc.code}: {request.full_url}: {reason}") from exc
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise OrchestratorError(f"API接続またはJSONの読み込みに失敗: {request.full_url}: {exc}") from exc
    if not isinstance(result, dict):
        raise OrchestratorError(f"APIがJSONオブジェクトを返しませんでした: {request.full_url}")
    return result


def _positive_number(value: Any, label: str, default: float) -> float:
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise OrchestratorError(f"{label} は正の数値にしてください")
    return float(value)


def load_config(path: Path) -> dict:
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise OrchestratorError(f"設定ファイルを読み込めません: {path}: {exc}") from exc
    if not isinstance(config, dict):
        raise OrchestratorError("設定ファイルのトップレベルはJSONオブジェクトです")
    for name in ("comfyui", "workflows"):
        if not isinstance(config.get(name), dict):
            raise OrchestratorError(f"設定ファイルに {name} オブジェクトが必要です")
    llm_key = "llm" if "llm" in config else "ollama"
    if not isinstance(config.get(llm_key), dict):
        raise OrchestratorError("llm または従来の ollama 設定が必要です")
    provider = config[llm_key].get("provider", "lmstudio" if llm_key == "llm" else "ollama")
    if provider not in ("lmstudio", "ollama"):
        raise OrchestratorError("llm.provider は lmstudio または ollama を指定してください")
    for name in (llm_key, "comfyui"):
        base = config[name].get("base_url")
        if not isinstance(base, str) or urllib.parse.urlsplit(base).scheme not in ("http", "https") or not urllib.parse.urlsplit(base).netloc:
            raise OrchestratorError(f"{name}.base_url は http(s) URL にしてください")
    model = config[llm_key].get("model")
    if not isinstance(model, str) or not model.strip():
        raise OrchestratorError(f"{llm_key}.model にローカルで使用可能なモデル名を設定してください")
    if llm_key == "llm" and provider == "lmstudio":
        length = config["llm"].get("context_length")
        if length is not None and (isinstance(length, bool) or not isinstance(length, int) or length < 512 or length > 131072):
            raise OrchestratorError("llm.context_length は512～131072の整数です")
        inference_timeout = config["llm"].get("inference_timeout_seconds", 600)
        if (
            isinstance(inference_timeout, bool)
            or not isinstance(inference_timeout, (int, float))
            or not 30 <= inference_timeout <= 3600
        ):
            raise OrchestratorError("llm.inference_timeout_seconds は30～3600秒の数値です")
        output_tokens = config["llm"].get("max_tokens", 4096)
        if isinstance(output_tokens, bool) or not isinstance(output_tokens, int) or not 1 <= output_tokens <= 32768:
            raise OrchestratorError("llm.max_tokens は1～32768の整数です")
        if length is not None and output_tokens > length:
            raise OrchestratorError("llm.max_tokens は llm.context_length 以下にしてください")
        unload = config["llm"].get("unload_after_inference", True)
        if not isinstance(unload, bool):
            raise OrchestratorError("llm.unload_after_inference は真偽値です")
        from .prompt_profiles import (
            DEFAULT_T2I_PROFILE, T2I_PROFILES,
            DEFAULT_I2I_PROFILE, I2I_PROFILES,
            DEFAULT_H3_PROFILE, H3_PROFILES,
        )
        profile = config["llm"].get("t2i_prompt_profile", DEFAULT_T2I_PROFILE)
        if not isinstance(profile, str) or profile not in T2I_PROFILES:
            raise OrchestratorError(
                "llm.t2i_prompt_profile は illustrious_v2 または legacy です"
            )
        edit_profile = config["llm"].get("i2i_prompt_profile", DEFAULT_I2I_PROFILE)
        if not isinstance(edit_profile, str) or edit_profile not in I2I_PROFILES:
            raise OrchestratorError(
                "llm.i2i_prompt_profile は preserve_edit_v1 または legacy です"
            )
        h3_profile = config["llm"].get("h3_prompt_profile", DEFAULT_H3_PROFILE)
        if not isinstance(h3_profile, str) or h3_profile not in H3_PROFILES:
            raise OrchestratorError("llm.h3_prompt_profile は " + ", ".join(H3_PROFILES) + " から選択してください")
        if not isinstance(config["llm"].get("send_reference_to_llm", False), bool):
            raise OrchestratorError("llm.send_reference_to_llm は真偽値です")
    for key, item in config["workflows"].items():
        if not isinstance(key, str) or not key or not isinstance(item, dict):
            raise OrchestratorError("workflows の各項目に識別子とオブジェクトが必要です")
        if item.get("kind") not in ALLOWED_KINDS:
            raise OrchestratorError(f"{key}.kind は {', '.join(sorted(ALLOWED_KINDS))} から選択してください")
        if not isinstance(item.get("file"), str) or not item["file"]:
            raise OrchestratorError(f"{key}.file が未指定です")
        bindings = item.get("bindings")
        defaults = item.get("defaults", {})
        if not isinstance(bindings, dict) or "positive_prompt" not in bindings:
            raise OrchestratorError(f"{key}.bindings に positive_prompt の対応先が必要です")
        if not isinstance(defaults, dict):
            raise OrchestratorError(f"{key}.defaults はオブジェクトです")
        for field, binding in bindings.items():
            if field not in PARAMS and field not in IMAGE_INPUTS:
                raise OrchestratorError(f"未対応の入力名: {key}.{field}")
            if not isinstance(binding, dict) or not isinstance(binding.get("node"), str) or not isinstance(binding.get("input"), str) or not binding["node"] or not binding["input"]:
                raise OrchestratorError(f"{key}.bindings.{field} は node と input が必要です")
        for field, value in defaults.items():
            if field not in bindings or field in IMAGE_INPUTS:
                raise OrchestratorError(f"{key}.defaults.{field} に対応する入力がありません")
            check_param(field, value)
        workflow_file = (path.resolve().parent / item["file"]).resolve()
        if not workflow_file.is_relative_to(path.resolve().parent):
            raise OrchestratorError(f"{key}.file は設定ファイルのフォルダ内を指定してください")
        if not workflow_file.is_file():
            raise OrchestratorError(f"ワークフローJSONが見つかりません: {workflow_file}")
        load_workflow(workflow_file, bindings)
    return config


def validate_wan_video_parameters(parameters: dict) -> None:
    """Wan 2.2 5B uses a spatial stride of 32 and temporal stride of 4."""
    for name in ("width", "height", "frames", "fps"):
        if name not in parameters:
            raise OrchestratorError(f"動画生成には {name} が必要です")
        check_param(name, parameters[name])
    if any(parameters[name] % 32 for name in ("width", "height")):
        raise OrchestratorError("Wan 2.2の動画の幅・高さは32の倍数にしてください")
    if parameters["frames"] < 5 or (parameters["frames"] - 1) % 4:
        raise OrchestratorError("Wan 2.2のフレーム数は5以上の4n+1にしてください")


def validate_h3_video_parameters(parameters: dict) -> None:
    """H3 FL2VA uses 24 fps and a 17k+5 temporal grid."""
    for name in ("width", "height", "frames", "fps"):
        if name not in parameters:
            raise OrchestratorError(f"H3動画生成には {name} が必要です")
        check_param(name, parameters[name])
    width, height = parameters["width"], parameters["height"]
    if width % 32 or height % 32 or min(width, height) < 384:
        raise OrchestratorError("H3の幅・高さは32の倍数、短辺384以上にしてください")
    if min(width, height) > 768 or max(width, height) > 1344:
        raise OrchestratorError("H3の初期ワークフローは短辺768・長辺1344以下に制限しています")
    if parameters["fps"] != 24:
        raise OrchestratorError("H3のFPSは24固定です")
    frames = parameters["frames"]
    if not 107 <= frames <= 362 or (frames - 5) % 17:
        raise OrchestratorError("H3のフレーム数は107～362の17n+5にしてください")


def validate_hunyuan_video_parameters(parameters: dict) -> None:
    """Conservative single-GPU envelope for the 480p step-distilled checkpoint."""
    for name in ("width", "height", "frames", "fps", "steps"):
        if name not in parameters:
            raise OrchestratorError(f"Hunyuan動画生成には {name} が必要です")
        check_param(name, parameters[name])
    width, height = parameters["width"], parameters["height"]
    if (width % 16 or height % 16 or min(width, height) < 320
            or max(width, height) > 848 or width * height > 640 * 640):
        raise OrchestratorError("Hunyuan 480pは16の倍数・短辺320以上・長辺848以下・約0.4MP以下です")
    if parameters["fps"] != 24:
        raise OrchestratorError("HunyuanのFPSは24固定です")
    if not 5 <= parameters["frames"] <= 121 or (parameters["frames"] - 1) % 4:
        raise OrchestratorError("Hunyuanのフレーム数は5～121の4n+1にしてください")
    if parameters["steps"] not in (8, 12):
        raise OrchestratorError("Hunyuan 480p Step Distilledは8または12 Stepsを指定してください")


def validate_video_parameters(workflow_id: str, parameters: dict) -> None:
    if workflow_id == WAN_I2V_ID:
        validate_wan_video_parameters(parameters)
    elif workflow_id == H3_I2V_ID:
        validate_h3_video_parameters(parameters)
    elif workflow_id == HUNYUAN_I2V_ID:
        validate_hunyuan_video_parameters(parameters)


def load_workflow(path: Path, bindings: dict) -> dict:
    try:
        workflow = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        raise OrchestratorError(f"ワークフローを読み込めません: {path}: {exc}") from exc
    if not isinstance(workflow, dict) or not workflow:
        raise OrchestratorError(f"API形式のワークフローJSONではありません: {path}")
    for node, data in workflow.items():
        if not isinstance(data, dict) or not isinstance(data.get("class_type"), str) or not isinstance(data.get("inputs"), dict):
            raise OrchestratorError(f"API形式のnodeではありません: {path} node={node}（UI形式JSONでは実行できません）")
    for field, binding in bindings.items():
        node, input_name = binding["node"], binding["input"]
        if node not in workflow or input_name not in workflow[node]["inputs"]:
            raise OrchestratorError(f"入力バインディングの指定先が存在しません: {field} -> {node}.{input_name}")
    return workflow


def plan_schema(workflows: dict) -> dict:
    fields = {}
    for name, (typ, lo, hi) in PARAMS.items():
        # Seed belongs to the user/host, not to the language model.
        # LLMs may emit negative, oversized or imprecise seed values.
        if name == "seed" or (bool(workflows) and workflows.keys() <= HOST_VIDEO_IDS and name not in ("positive_prompt", "negative_prompt")):
            continue
        if any(name in entry["bindings"] for entry in workflows.values()):
            spec = {"type": typ}
            if lo is not None:
                spec.update(minimum=lo, maximum=hi)
            fields[name] = spec
    return {
        "type": "object",
        "properties": {
            "workflow_id": {"type": "string", "enum": list(workflows)},
            "parameters": {"type": "object", "properties": fields, "additionalProperties": False},
        },
        "required": ["workflow_id", "parameters"],
        "additionalProperties": False,
    }


def validate_plan(plan: dict, workflows: dict, has_image: bool) -> tuple[str, dict]:
    if not isinstance(plan, dict) or set(plan) != {"workflow_id", "parameters"}:
        raise OrchestratorError("LLMの回答は workflow_id と parameters のJSONが必要です")
    selected = plan["workflow_id"]
    if not isinstance(selected, str) or selected not in workflows:
        raise OrchestratorError(f"LLMが未登録ワークフローを指定: {selected!r}")
    entry = workflows[selected]
    binds = entry["bindings"]
    if has_image and "image" not in binds:
        raise OrchestratorError(f"{selected} に image バインディングがありません（参照画像を転送できません）")
    if not has_image and "image" in binds:
        raise OrchestratorError(f"{selected} には --image の指定が必要です")
    params = plan["parameters"]
    if not isinstance(params, dict):
        raise OrchestratorError("parameters はJSONオブジェクトです")
    merged = dict(entry.get("defaults", {}))
    for name, value in params.items():
        if name not in binds or name in IMAGE_INPUTS:
            raise OrchestratorError(f"{selected} では {name} を変更できません")
        check_param(name, value)
        merged[name] = value
    if "positive_prompt" not in merged or not merged["positive_prompt"].strip():
        raise OrchestratorError("positive_prompt がありません")
    return selected, merged


def render_workflow(
    workflow: dict, bindings: dict, params: dict, image_name: str | None,
    mask_name: str | None = None, pose_name: str | None = None,
) -> dict:
    rendered = copy.deepcopy(workflow)
    for name, value in params.items():
        bind = bindings[name]
        rendered[bind["node"]]["inputs"][bind["input"]] = value
    for field, value in (("image", image_name), ("mask", mask_name), ("pose", pose_name)):
        if value is not None:
            if field not in bindings:
                raise OrchestratorError(f"ワークフローに {field} 入力がありません")
            bind = bindings[field]
            rendered[bind["node"]]["inputs"][bind["input"]] = value
    return rendered


class Ollama:
    def __init__(self, settings: dict):
        self.base = settings["base_url"]
        self.model = settings["model"]
        self.timeout = _positive_number(settings.get("timeout_seconds"), "ollama.timeout_seconds", 240)

    def interpret(self, text: str, workflows: dict, image: Path | None) -> dict:
        catalog = [
            {"id": key, "kind": data["kind"], "description": data.get("description", ""),
             "parameters": [name for name in data["bindings"] if name not in ("image", "seed")],
             "requires_image": "image" in data["bindings"]}
            for key, data in workflows.items()
        ]
        instruction = (
            "あなたはComfyUIの固定ワークフロー選択器です。JSONだけを返してください。"
            "ユーザーの意図に最も合うidをcatalogから選び、対応するparametersだけを指定してください。"
            "positive_promptは生成モデルに適した具体的なプロンプトにしてください。"
            "ノードやファイル名は絶対に生成しないでください。"
            f"参照画像あり: {image is not None}。catalog={json.dumps(catalog, ensure_ascii=False)}\n"
            f"依頼: {text}"
        )
        request: dict[str, Any] = {
            "model": self.model, "prompt": instruction,
            "format": plan_schema(workflows), "stream": False, "keep_alive": 0,
        }
        if image is not None:
            request["images"] = [base64.b64encode(image.read_bytes()).decode("ascii")]
        try:
            result = http_json(self.base, "/api/generate", request, self.timeout)
            raw = result.get("response")
            if not isinstance(raw, str):
                raise OrchestratorError("Ollamaのresponseが文字列ではありません")
            try:
                return json.loads(raw)
            except ValueError as exc:
                raise OrchestratorError(f"LLMが有効なJSONを返しませんでした: {raw[:400]}") from exc
        finally:
            # Explicit unload acts as a hard barrier before ComfyUI loads a model.
            # If unloading fails, no ComfyUI /prompt will be submitted.
            unloaded = http_json(self.base, "/api/generate", {"model": self.model, "keep_alive": 0}, self.timeout)
            if unloaded.get("done") is not True or unloaded.get("done_reason", "unload") != "unload":
                raise OrchestratorError(f"Ollamaのアンロード完了を確認できません: {unloaded}")


class ComfyUI:
    def __init__(self, settings: dict):
        self.base = settings["base_url"]
        self.timeout = _positive_number(settings.get("timeout_seconds"), "comfyui.timeout_seconds", 60)
        self.poll = _positive_number(settings.get("poll_seconds"), "comfyui.poll_seconds", 2)
        self.wait_timeout = _positive_number(settings.get("generation_timeout_seconds"), "comfyui.generation_timeout_seconds", 1800)

    def free_if_idle(self) -> None:
        queue = http_json(self.base, "/queue", timeout=self.timeout)
        if queue.get("queue_running") or queue.get("queue_pending"):
            raise OrchestratorError("ComfyUIに他の実行・待機ジョブがあります。VRAM解放せず中断しました")
        http_json(self.base, "/free", {"unload_models": True, "free_memory": True}, self.timeout, allow_empty=True)

    def upload_image(self, image: Path) -> str:
        if not image.is_file():
            raise OrchestratorError(f"画像が見つかりません: {image}")
        if image.stat().st_size > 40 * 1024 * 1024:
            raise OrchestratorError("画像は40MB以下にしてください")
        boundary = uuid.uuid4().hex
        filename = image.name.replace('"', "_").replace("\r", "_").replace("\n", "_")
        ctype = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        prefix = (
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"image\"; filename=\"{filename}\"\r\n"
            f"Content-Type: {ctype}\r\n\r\n"
        ).encode("utf-8")
        payload = prefix + image.read_bytes() + f"\r\n--{boundary}--\r\n".encode("ascii")
        req = urllib.request.Request(
            self.base.rstrip("/") + "/upload/image", data=payload,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}, method="POST",
        )
        result = _open_json(req, self.timeout)
        name = result.get("name")
        if not isinstance(name, str) or not name:
            raise OrchestratorError(f"ComfyUIの画像アップロード応答が不正です: {result}")
        subfolder = result.get("subfolder", "")
        return f"{subfolder}/{name}" if subfolder else name

    def ensure_pose_dependencies(self, workflow: dict) -> None:
        """Check pose-only extra nodes and installed weights before GPU inference."""
        if not any(node.get("class_type") == "ControlNetLoader" for node in workflow.values()):
            return
        try:
            info = http_json(self.base, "/object_info/ControlNetLoader", timeout=self.timeout)
            model_choices = (
                info["ControlNetLoader"]["input"]["required"]["control_net_name"][0]
            )
        except (KeyError, IndexError, TypeError, OrchestratorError) as exc:
            raise OrchestratorError(
                "ComfyUIのControlNetLoaderを確認できません。ComfyUIを更新・再起動してください"
            ) from exc
        model_names = [
            node["inputs"]["control_net_name"]
            for node in workflow.values() if node.get("class_type") == "ControlNetLoader"
        ]
        for wanted in model_names:
            if wanted not in model_choices:
                raise OrchestratorError(
                    f"OpenPose用ControlNetモデルがありません: {wanted}。"
                    "ComfyUI/models/controlnet に配置して再起動してください"
                )
        if any(node.get("class_type") == "DWPreprocessor" for node in workflow.values()):
            try:
                info = http_json(self.base, "/object_info/DWPreprocessor", timeout=self.timeout)
                if "DWPreprocessor" not in info:
                    raise KeyError("DWPreprocessor")
            except (KeyError, OrchestratorError) as exc:
                raise OrchestratorError(
                    "ポーズ抽出には comfyui_controlnet_aux (DWPose) の追加が必要です。"
                    "ComfyUI Managerでインストールして再起動してください"
                ) from exc

    def list_generation_models(self) -> dict:
        """Read dropdown choices without loading a model or submitting a prompt."""
        inventory = {}
        for class_type, field in (
            ("CheckpointLoaderSimple", "ckpt_name"), ("UNETLoader", "unet_name"),
            ("UnetLoaderGGUF", "unet_name"),
        ):
            info = http_json(self.base, "/object_info/" + class_type, timeout=min(self.timeout, 12))
            if class_type == "UnetLoaderGGUF" and class_type not in info:
                inventory[class_type] = ()
                continue
            try:
                choices = info[class_type]["input"]["required"][field][0]
                if not isinstance(choices, (list, tuple)):
                    raise TypeError("model dropdown is not a list")
                inventory[class_type] = tuple(value for value in choices if isinstance(value, str))
            except (KeyError, IndexError, TypeError) as exc:
                raise OrchestratorError(f"モデル一覧を取得できません: {class_type}") from exc
        return inventory

    def ensure_video_dependencies(self, workflow: dict) -> None:
        """Check generation nodes and model choices before starting inference."""
        loaders = {
            "UNETLoader": "unet_name", "CLIPLoader": "clip_name",
            "VAELoader": "vae_name", "LoraLoaderModelOnly": "lora_name",
            "ClipProjApply": "projection",
            "UnetLoaderGGUF": "unet_name",
            "CheckpointLoaderSimple": "ckpt_name",
            "DualCLIPLoader": ("clip_name1", "clip_name2"),
            "CLIPVisionLoader": "clip_name",
            "ModelAttentionBackend": "attention",
        }
        required = {"Wan22ImageToVideoLatent", "MiniMaxH3ImageToVideo", "MiniMaxH3ReferenceToVideo", "MiniMaxH3SigmaShift",
                    "HunyuanVideo15ImageToVideo", "CLIPVisionEncode", "ModelSamplingSD3",
                    "VAEDecodeAudio", "CreateVideo", "SaveVideo",
                    "ModelSamplingAuraFlow", "EmptySD3LatentImage", "BlockSparseAttention"}
        for class_type in sorted(required | set(loaders)):
            if not any(n.get("class_type") == class_type for n in workflow.values()):
                continue
            try:
                info = http_json(self.base, "/object_info/" + class_type, timeout=self.timeout)
                node_info = info[class_type]
                if not isinstance(node_info, dict):
                    raise KeyError(class_type)
                if class_type not in loaders:
                    continue
                fields = loaders[class_type]
                if isinstance(fields, str):
                    fields = (fields,)
                choices_by_field = {
                    field: node_info["input"]["required"][field][0] for field in fields
                }
            except (KeyError, IndexError, TypeError, OrchestratorError) as exc:
                if class_type == "ClipProjApply":
                    raise OrchestratorError(
                        "ClipProj Applyを確認できません。ComfyUI-ClipProj 0.1.13以降をManagerで導入・更新し、ComfyUIを再起動してください"
                    ) from exc
                if class_type == "UnetLoaderGGUF":
                    raise OrchestratorError(
                        "H3 U16G対応のGGUFローダーがありません。molbal版ComfyUI-GGUFを確認してください"
                    ) from exc
                raise OrchestratorError(
                    f"生成用ノード {class_type} を確認できません。ComfyUIを更新・再起動してください"
                ) from exc
            for node in workflow.values():
                if node.get("class_type") != class_type:
                    continue
                for field, choices in choices_by_field.items():
                    wanted = node["inputs"][field]
                    if wanted not in choices:
                        if class_type == "ModelAttentionBackend":
                            raise OrchestratorError(f"Attention backendが利用できません: {wanted}。ComfyUI/Comfy Kitchenを確認してください")
                        if class_type == "ClipProjApply":
                            raise OrchestratorError(
                                f"ClipProj変換行列がありません: {wanted}。ComfyUI/models/clip_projectionsに配置してください"
                            )
                        raise OrchestratorError(
                            f"動画生成モデルがありません: {wanted}。READMEのI2V導入手順を確認してください"
                        )

    def extend_video_timeout(self, settings: dict) -> None:
        self.wait_timeout = max(
            self.wait_timeout,
            _positive_number(settings.get("video_generation_timeout_seconds"),
                             "comfyui.video_generation_timeout_seconds", 7200),
        )

    def submit(self, workflow: dict) -> str:
        result = http_json(self.base, "/prompt", {"prompt": workflow}, self.timeout)
        prompt_id = result.get("prompt_id")
        if not isinstance(prompt_id, str) or not prompt_id:
            raise OrchestratorError(f"ComfyUIがワークフローを受理しませんでした: {result}")
        return prompt_id

    def wait(self, prompt_id: str, cancel_event: Any = None) -> dict:
        deadline = time.monotonic() + self.wait_timeout
        route = "/history/" + urllib.parse.quote(prompt_id, safe="")
        while time.monotonic() < deadline:
            if cancel_event is not None and cancel_event.is_set():
                raise OrchestratorError(
                    f"結果待機を終了しました。ComfyUI上の生成ジョブは継続します: prompt_id={prompt_id}"
                )
            results = http_json(self.base, route, timeout=self.timeout)
            if prompt_id in results:
                item = results[prompt_id]
                if not isinstance(item, dict):
                    raise OrchestratorError(f"履歴の形式が不正です: {prompt_id}")
                status = item.get("status", {})
                if isinstance(status, dict) and (status.get("status_str") == "error" or status.get("completed") is False):
                    raise OrchestratorError(f"ComfyUIの生成が失敗しました: {prompt_id}: {status}")
                return item
            time.sleep(self.poll)
        raise OrchestratorError(f"生成結果の待機がタイムアウトしました。ComfyUIで確認してください: prompt_id={prompt_id}")


def execute(
    config: dict, config_path: Path, request: str, image: Path | None = None,
    dry_run: bool = False, selected_workflow: str | None = None,
    overrides: dict | None = None, progress: Callable[[str], None] | None = None,
    cancel_event: Any = None, mask_image: Path | None = None, pose_image: Path | None = None,
    composition_image: Path | None = None,
    character_traits: str | None = None,
) -> dict:
    """Interpret natural language, unload the chosen LLM, then run a fixed workflow.

    A cancel event only stops this client's wait and does NOT interrupt ComfyUI jobs.
    """
    workflows = config["workflows"]
    if not workflows:
        raise OrchestratorError(
            "workflowsが空です。先にAPI形式JSONを配置してconfig.jsonへ登録してください"
        )
    # Still-image analysis settings do not apply to I2V. Preserve their
    # persistent configuration, but exclude them from this generation job.
    explicit_i2v = workflows.get(selected_workflow, {}).get("kind") == "i2v"
    if explicit_i2v:
        composition_image = None
        character_traits = None
    empty_request = not request.strip()
    if empty_request and not supports_empty_i2v_request(
        config, selected_workflow, image, mask_image, pose_image, composition_image,
    ):
        raise OrchestratorError("自然文の指示を入力してください（I2Vの参照画像のみ指定時は省略できます）")
    use_prompt_llm = needs_prompt_llm(
        config, request, character_traits, composition_image, workflow_id=selected_workflow,
    )
    if character_traits is not None:
        from .character_refs import normalize_approved
        character_traits = normalize_approved(character_traits)
    for field, path_value in (
        ("参照画像", image), ("マスク", mask_image), ("ポーズ画像", pose_image),
        ("構図参考画像", composition_image),
    ):
        if path_value is not None and not Path(path_value).is_file():
            raise OrchestratorError(f"{field}が見つかりません: {path_value}")
    if image is not None:
        image = Path(image).resolve()
    if mask_image is not None:
        mask_image = Path(mask_image).resolve()
    if pose_image is not None:
        pose_image = Path(pose_image).resolve()
    if composition_image is not None:
        composition_image = Path(composition_image).resolve()
        if not config.get("llm", {}).get("send_reference_to_llm", False):
            raise OrchestratorError(
                "構図参考画像をLLMで解析するには「画像をLLMで構図解析」をONにしてください"
            )

    # Filter by exact required image sources before asking the LLM.
    # This prevents the LLM from choosing T2I when the user supplied an I2I
    # reference, or choosing I2I with no image to upload.
    if selected_workflow is not None:
        if selected_workflow not in workflows:
            raise OrchestratorError(f"登録されていないワークフローです: {selected_workflow}")
        workflows = {selected_workflow: workflows[selected_workflow]}
    workflows = compatible_workflows(workflows, image, mask_image, pose_image)
    if selected_workflow is None:
        # Ordinary image generation must never switch into a costly video job.
        still = {key: entry for key, entry in workflows.items()
                 if entry.get("kind") not in VIDEO_KINDS and key not in QWEN_IDS}
        if still:
            workflows = still
    if not workflows:
        if selected_workflow is not None:
            raise OrchestratorError(
                f"{selected_workflow} と参照画像・マスク・ポーズ画像の指定が一致しません"
            )
        raise OrchestratorError(
            "指定された入力に対応するワークフローが未登録です。"
            "T2Iは入力画像なし、I2Iは参照画像、部分修正は画像とマスク、"
            "ポーズ生成はポーズ画像を指定してください"
        )

    i2v_only = all(entry.get("kind") == "i2v" for entry in workflows.values())

    def note(message: str) -> None:
        if progress:
            progress(message)

    def check_cancelled() -> None:
        if cancel_event is not None and cancel_event.is_set():
            raise OrchestratorError("生成開始前に処理を中止しました")

    overrides, h3_options = split_h3_options(
        overrides or {}, enabled=set(workflows) == {H3_I2V_ID},
    )
    reference_only = h3_ref2va_filename(h3_options.get("h3_model")) is not None
    if h3_hybrid_filename(h3_options.get("h3_model")) is not None:
        overrides.setdefault("steps", H3_HYBRID_DEFAULT_STEPS)
        validate_h3_hybrid_steps(overrides["steps"], h3_options.get("h3_performance", "standard"))
    if h3_options:
        fixed_steps = H3_TURBOS[h3_options["h3_turbo"]][1]
        if fixed_steps is not None:
            overrides["steps"] = fixed_steps
    overrides, checkpoint_options = split_checkpoint_option(overrides, workflows)
    if sdxl_checkpoint_kind(checkpoint_options.get("checkpoint_model", "")) == "turbo":
        overrides.update(steps=4, cfg=1)
    if set(workflows) == {QWEN_LIGHTNING_ID}:
        overrides.update(steps=4, cfg=1)
    check_cancelled()
    comfy = ComfyUI(config["comfyui"])
    if not dry_run:
        # Fail early on uninstalled pose models without spending VRAM on an LLM.
        for candidate_id, entry in workflows.items():
            if candidate_id in QWEN_IDS or checkpoint_options:
                graph = load_workflow(
                    (config_path.resolve().parent / entry["file"]).resolve(), entry["bindings"],
                )
                graph = prepare_checkpoint_workflow(graph, checkpoint_options)
                comfy.ensure_video_dependencies(graph)
            if entry.get("kind") == "pose":
                pose_template = load_workflow(
                    (config_path.resolve().parent / entry["file"]).resolve(), entry["bindings"],
                )
                comfy.ensure_pose_dependencies(pose_template)
            elif entry.get("kind") in VIDEO_KINDS:
                video_template = load_workflow(
                    (config_path.resolve().parent / entry["file"]).resolve(), entry["bindings"],
                )
                if h3_options:
                    video_template = prepare_h3_workflow(video_template, h3_options, overrides)
                comfy.ensure_video_dependencies(video_template)
                comfy.extend_video_timeout(config["comfyui"])
    if not dry_run and use_prompt_llm and config["comfyui"].get("free_before_llm", True):
        note("ComfyUI: キューを確認して前回の生成モデルの解放を要求")
        comfy.free_if_idle()
    elif not dry_run and not use_prompt_llm:
        note("ComfyUI: LLMを使用しないためモデルキャッシュを維持")
    check_cancelled()

    llm_key = "llm" if "llm" in config else "ollama"
    settings = config[llm_key]
    if i2v_only:
        settings = {**settings, "send_reference_to_llm": False}
    if reference_only:
        settings = {**settings, "_h3_reference_only": True}
        # Keep the existing binding schema and ID; only replace the job's
        # descriptive catalog so the LLM sees the actual conditioning mode.
        workflows = {key: {**entry, "description":
                           "MiniMax H3 Ref2VA: reference image <Picture 1> is a visual guide, "
                           "not an initial frame. Generate the requested new scene and motion with "
                           "independent framing and synchronized audio."}
                     for key, entry in workflows.items()}
    provider = settings.get("provider", "lmstudio" if llm_key == "llm" else "ollama")
    if not use_prompt_llm:
        # The image is the primary conditioning; avoid a needless LLM load.
        note("I2V: 参照画像のみ（LLMを使用しません）")
        plan = {
            "workflow_id": selected_workflow,
            "parameters": {"positive_prompt": H3_REF2VA_DEFAULT_PROMPT if reference_only else I2V_DEFAULT_PROMPT},
        }
    elif provider == "lmstudio":
        from .lmstudio import LMStudio
        from .prompt_profiles import is_i2i_context
        # An edit-strength hint is provided to the prompt designer only.
        # Keep it out of config.json, the LLM output schema and ComfyUI nodes.
        if is_i2i_context(workflows):
            settings = dict(settings)
            if len(workflows) == 1:
                edit_workflow = next(iter(workflows.values()))
                effective_denoise = (overrides or {}).get(
                    "denoise", edit_workflow.get("defaults", {}).get("denoise")
                )
                if effective_denoise is not None:
                    check_param("denoise", effective_denoise)
                    settings["_edit_denoise"] = float(effective_denoise)
        if set(workflows) == {H3_I2V_ID}:
            settings = dict(settings)
            h3 = workflows[H3_I2V_ID]
            frames = (overrides or {}).get("frames", h3.get("defaults", {}).get("frames", 124))
            check_param("frames", frames)
            settings["_h3_duration_seconds"] = frames / 24
        # A pose reference is also a valid vision input. The VLM receives the
        # same image used by pose ControlNet, while ComfyUI still receives it
        # through the separate "pose" binding. In I2I, prefer the source image.
        vision_reference = (
            None if i2v_only else
            composition_image if composition_image is not None else
            image if image is not None else pose_image
        )
        # Keep the existing call signature unchanged without a confirmed
        # character sheet; offline mocks and older integrations still work.
        extra = {"character_traits": character_traits} if character_traits and not i2v_only else {}
        if composition_image is not None and not i2v_only:
            plan = LMStudio(settings).interpret(
                request, workflows, vision_reference, progress=note,
                reference_role="composition", **extra,
            )
        else:
            plan = LMStudio(settings).interpret(
                request, workflows, vision_reference, progress=note, **extra,
            )
    else:
        if composition_image is not None and not i2v_only:
            raise OrchestratorError("LLM専用の構図参考画像は現在LM Studio接続で利用してください")
        note("Ollama: 自然文を解釈しモデルをアンロード")
        plan = Ollama(settings).interpret(request, workflows, None if i2v_only else image)
    check_cancelled()
    # Treat an LLM-proposed seed as untrusted and ignore it, even if the model
    # disregards the schema. An explicit GUI/CLI override always takes priority.
    if isinstance(plan, dict) and isinstance(plan.get("parameters"), dict):
        if "seed" in plan["parameters"]:
            note("LLMが返したSeedは使用せず、GUI指定または乱数で設定します")
        plan = {**plan, "parameters": {k: v for k, v in plan["parameters"].items() if k != "seed"}}
    if bool(workflows) and workflows.keys() <= HOST_VIDEO_IDS and isinstance(plan, dict) and isinstance(plan.get("parameters"), dict):
        # Video dimensions, length, FPS and sampler settings belong to the host.
        plan = {**plan, "parameters": {
            k: v for k, v in plan["parameters"].items()
            if k in ("positive_prompt", "negative_prompt")
            and any(k in e["bindings"] for e in workflows.values())
        }}
    workflow_id, params = validate_plan(plan, workflows, image is not None)
    selection = workflows[workflow_id]
    if overrides:
        for name, value in overrides.items():
            if name not in selection["bindings"] or name in IMAGE_INPUTS:
                raise OrchestratorError(f"指定したワークフローでは {name} を変更できません")
            check_param(name, value)
            params[name] = value
    if "seed" in selection["bindings"] and (not overrides or "seed" not in overrides):
        # Seed empty in the GUI => an independent reproducible 32-bit seed.
        # Never silently inherit the fixed seed from the template JSON.
        params["seed"] = secrets.randbits(32)
    validate_video_parameters(workflow_id, params)
    if reference_only:
        params["positive_prompt"] = ensure_h3_reference_prompt(params["positive_prompt"])
    template = load_workflow(
        (config_path.resolve().parent / selection["file"]).resolve(), selection["bindings"]
    )
    if h3_options:
        template = prepare_h3_workflow(template, h3_options, params)
        note("H3: " + h3_model_label(h3_options["h3_model"])
             + " / Turbo " + H3_TURBO_LABELS[h3_options["h3_turbo"]]
             + f" / {params['steps']} Steps"
             + (f" / Text encoder={h3_options['h3_encoder_device']}" if "h3_encoder_device" in h3_options else "")
             + (f" / TE model={H3_ENCODER_LABELS[h3_options['h3_encoder_model']]}" if "h3_encoder_model" in h3_options else ""))
    if workflow_id in QWEN_IDS and any(params[name] % 16 for name in ("width", "height")):
        raise OrchestratorError("Qwen-Imageの幅・高さは16の倍数にしてください")
    template = prepare_checkpoint_workflow(template, checkpoint_options)
    if checkpoint_options:
        note("SDXL: " + checkpoint_options["checkpoint_model"])
    saved_params = {**params, **h3_options, **checkpoint_options}
    note(f"ワークフロー確定: {workflow_id}")
    if dry_run:
        return {"status": "dry_run", "workflow_id": workflow_id, "parameters": saved_params}

    check_cancelled()
    uploaded = comfy.upload_image(image) if image is not None else None
    uploaded_mask = comfy.upload_image(mask_image) if mask_image is not None else None
    uploaded_pose = comfy.upload_image(pose_image) if pose_image is not None else None
    rendered = render_workflow(
        template, selection["bindings"], params, uploaded, uploaded_mask, uploaded_pose,
    )
    check_cancelled()
    note("ComfyUI: キューに投入")
    prompt_id = comfy.submit(rendered)
    note(f"ComfyUI: 生成完了を待機中（{prompt_id}）")
    history = comfy.wait(prompt_id, cancel_event=cancel_event)
    note("ComfyUI: 生成完了")
    return {
        "status": "completed", "workflow_id": workflow_id, "parameters": saved_params,
        "prompt_id": prompt_id, "outputs": history.get("outputs", {}),
        "comfy_status": history.get("status", {}),
    }


def execute_saved(
    config: dict, config_path: Path, workflow_id: str, parameters: dict,
    reference_image: Path | None = None, new_seed: bool = False,
    progress: Callable[[str], None] | None = None, cancel_event: Any = None,
    mask_image: Path | None = None, pose_image: Path | None = None,
) -> dict:
    """Replay exact validated workflow inputs, without invoking or loading an LLM.

    With new_seed=True only seed changes; for exact replay the original seed
    and prompts are reused byte-for-byte. Does not stop other ComfyUI jobs.
    """
    if workflow_id not in config["workflows"]:
        raise OrchestratorError(f"保存されたワークフローが未登録です: {workflow_id}")
    if not isinstance(parameters, dict):
        raise OrchestratorError("保存された生成パラメータが不正です")
    selected = config["workflows"][workflow_id]
    bindings = selected["bindings"]
    required = IMAGE_INPUTS.intersection(bindings)
    if required != supplied_inputs(reference_image, mask_image, pose_image):
        raise OrchestratorError("再生成に必要な参照画像・マスク・ポーズ画像が揃っていません")
    for field, value in (("参照画像", reference_image), ("マスク", mask_image), ("ポーズ画像", pose_image)):
        if value is not None and not Path(value).is_file():
            raise OrchestratorError(f"{field}がありません: {value}")
    has_image = reference_image is not None
    if "seed" in bindings and not new_seed and "seed" not in parameters:
        raise OrchestratorError("元のSeedが履歴にありません。同条件の再生成はできません")

    copied, h3_options = split_h3_options(parameters, enabled=workflow_id == H3_I2V_ID)
    copied, checkpoint_options = split_checkpoint_option(copied, {workflow_id})
    fixed_turbo = sdxl_checkpoint_kind(checkpoint_options.get("checkpoint_model", "")) == "turbo"
    if fixed_turbo or workflow_id == QWEN_LIGHTNING_ID:
        if copied.get("steps") != 4 or copied.get("cfg") != 1:
            raise OrchestratorError("高速蒸留モデルの履歴には4 Steps、CFG 1が必要です")
    if new_seed and "seed" in bindings:
        copied["seed"] = secrets.randbits(32)
    workflow_id, params = validate_plan(
        {"workflow_id": workflow_id, "parameters": copied},
        {workflow_id: selected}, has_image,
    )
    validate_video_parameters(workflow_id, params)
    template = load_workflow(
        (config_path.resolve().parent / selected["file"]).resolve(),
        bindings,
    )
    if h3_options:
        template = prepare_h3_workflow(template, h3_options, params)
    if workflow_id in QWEN_IDS and any(params[name] % 16 for name in ("width", "height")):
        raise OrchestratorError("Qwen-Imageの幅・高さは16の倍数にしてください")
    template = prepare_checkpoint_workflow(template, checkpoint_options)
    if cancel_event is not None and cancel_event.is_set():
        raise OrchestratorError("再生成開始前に中止しました")

    comfy = ComfyUI(config["comfyui"])
    if workflow_id in QWEN_IDS or checkpoint_options:
        comfy.ensure_video_dependencies(template)
    if selected.get("kind") == "pose":
        comfy.ensure_pose_dependencies(template)
    elif selected.get("kind") in VIDEO_KINDS:
        comfy.ensure_video_dependencies(template)
        comfy.extend_video_timeout(config["comfyui"])
    if progress:
        progress("保存済みのプロンプトと生成設定を復元（LLMは使用しません）")
    uploaded = comfy.upload_image(reference_image) if has_image else None
    uploaded_mask = comfy.upload_image(mask_image) if mask_image is not None else None
    uploaded_pose = comfy.upload_image(pose_image) if pose_image is not None else None
    if cancel_event is not None and cancel_event.is_set():
        raise OrchestratorError("再生成開始前に中止しました")
    rendered = render_workflow(template, bindings, params, uploaded, uploaded_mask, uploaded_pose)
    if progress:
        progress("ComfyUI: 保存設定で再生成を開始")
    prompt_id = comfy.submit(rendered)
    history = comfy.wait(prompt_id, cancel_event=cancel_event)
    if progress:
        progress("ComfyUI: 再生成完了")
    return {
        "status": "completed",
        "workflow_id": workflow_id,
        "parameters": {**params, **h3_options, **checkpoint_options},
        "prompt_id": prompt_id,
        "outputs": history.get("outputs", {}),
        "comfy_status": history.get("status", {}),
    }
