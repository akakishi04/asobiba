"""Registered workflow contracts, model selection and validated graph construction.

No backend access, LLM inference or generation jobs.
"""
from __future__ import annotations

import copy
import json
import re
from pathlib import Path

from .parameters import OrchestratorError, PARAMS, check_param
from .model_profiles import ANIMA_ID, anima_model_name, anima_models
from .model_registry import parse_image_key, model_filename, installed_registrations
from .h3 import H3_MODELS, h3_ref2va_model_key, h3_hybrid_model_key


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
    manual = parse_image_key(name)
    if manual is not None:
        return {"sdxl": "illustrious", "sdxl_turbo": "turbo"}.get(manual[0])
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
    if ids == {ANIMA_ID} and anima_model_name(name):
        return inputs, {"checkpoint_model": name}
    manual = parse_image_key(name)
    if ids == {QWEN_T2I_ID} and manual and manual[0] == "qwen":
        return inputs, {"checkpoint_model": name}
    if not ids or not ids <= SDXL_WORKFLOW_IDS or kind is None:
        raise OrchestratorError("このワークフローに対応しないSDXLチェックポイントです")
    if kind == "turbo" and ids != {"wai_t2i_basic"}:
        raise OrchestratorError("SDXL Turboは画像生成（T2I）を選択してください")
    return inputs, {"checkpoint_model": name}


def prepare_checkpoint_workflow(template: dict, options: dict) -> dict:
    if not options:
        return template
    graph = copy.deepcopy(template)
    manual = parse_image_key(options["checkpoint_model"])
    if manual and manual[0] == "qwen":
        loader = graph.get("226", {})
        if (loader.get("class_type") != "UNETLoader"
                or loader.get("inputs", {}).get("unet_name") != "qwen_image_2512_fp8_e4m3fn.safetensors"):
            raise OrchestratorError("標準Qwen-Image用ローダーが見つかりません")
        loader["inputs"]["unet_name"] = manual[1]
        return graph
    loader = graph.get("2", {})
    if loader.get("class_type") == "UNETLoader" and anima_model_name(options["checkpoint_model"]):
        if "unet_name" not in loader.get("inputs", {}) or not anima_model_name(loader["inputs"]["unet_name"]):
            raise OrchestratorError("Anima用ローダーが見つかりません")
        loader["inputs"]["unet_name"] = model_filename(options["checkpoint_model"])
        return graph
    if loader.get("class_type") != "CheckpointLoaderSimple" or "ckpt_name" not in loader.get("inputs", {}):
        raise OrchestratorError("標準SDXLチェックポイントノードが見つかりません")
    name = options["checkpoint_model"]
    loader["inputs"]["ckpt_name"] = model_filename(name)
    if sdxl_checkpoint_kind(name) == "turbo":
        sampler = graph.get("11", {})
        if sampler.get("class_type") != "KSampler":
            raise OrchestratorError("SDXL Turbo用サンプラーが見つかりません")
        sampler["inputs"].update(sampler_name="euler_ancestral", scheduler="normal", steps=4, cfg=1)
    return graph


def installed_model_choices(inventory: dict, registrations=()) -> dict:
    """Only show registered architectures and installed filenames."""
    local = installed_registrations(inventory, registrations)
    claimed = {item.identity for item in local}
    inventory = inventory or {}
    native = tuple(name for name in inventory.get("UNETLoader", ()) if ("UNETLoader", name) not in claimed)
    gguf = inventory.get("UnetLoaderGGUF", ())
    return {
        "h3": (tuple(key for key, name in H3_MODELS.items()
                     if name in (gguf if name.endswith(".gguf") else native))
               + tuple(dict.fromkeys(key for name in native
                                     if (key := h3_ref2va_model_key(name)) is not None))
               + tuple(dict.fromkeys(key for name in native for reference_only in (False, True)
                                     if (key := h3_hybrid_model_key(name, reference_only=reference_only)) is not None))
               + tuple(key for item in local if item.spec.h3_modes for key in item.keys)),
        "anima": anima_models({"UNETLoader": native}) + tuple(item.keys[0] for item in local if item.spec.image_family == "anima"),
        "qwen": tuple(item.keys[0] for item in local if item.spec.image_family == "qwen"),
        "sdxl": (tuple(name for name in inventory.get("CheckpointLoaderSimple", ())
                       if ("CheckpointLoaderSimple", name) not in claimed and sdxl_checkpoint_kind(name) is not None)
                 + tuple(item.keys[0] for item in local if item.spec.image_family == "sdxl")),
    }


def supplied_inputs(image=None, mask=None, pose=None) -> frozenset[str]:
    return frozenset(name for name, value in (("image", image), ("mask", mask), ("pose", pose)) if value is not None)


def compatible_workflows(workflows: dict, image=None, mask=None, pose=None) -> dict:
    supplied = supplied_inputs(image, mask, pose)
    return {
        key: entry for key, entry in workflows.items()
        if IMAGE_INPUTS.intersection(entry["bindings"]) == supplied
    }



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
