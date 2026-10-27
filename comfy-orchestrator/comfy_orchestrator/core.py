"""Local Ollama -> unload -> ComfyUI orchestrator (standard-library only)."""

from __future__ import annotations

import base64
import copy
import json
import mimetypes
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Callable


class OrchestratorError(RuntimeError):
    """An actionable configuration, protocol or execution error."""


PARAMS = {
    "positive_prompt": ("string", None, None),
    "negative_prompt": ("string", None, None),
    "width": ("integer", 64, 4096),
    "height": ("integer", 64, 4096),
    "steps": ("integer", 1, 150),
    "cfg": ("number", 0, 30),
    "seed": ("integer", 0, 9223372036854775807),
    "frames": ("integer", 1, 1000),
    "fps": ("integer", 1, 120),
    "denoise": ("number", 0, 1),
    "control_strength": ("number", 0, 2),
}
ALLOWED_KINDS = {"t2i", "i2i", "t2v", "i2v", "inpaint", "pose"}
IMAGE_INPUTS = frozenset({"image", "mask", "pose"})


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


def check_param(name: str, value: Any) -> None:
    if name not in PARAMS:
        raise OrchestratorError(f"未対応の生成パラメータ: {name}")
    typ, lower, upper = PARAMS[name]
    if typ == "string":
        if not isinstance(value, str) or len(value) > 5000:
            raise OrchestratorError(f"{name} は5000文字以内の文字列です")
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)) or (typ == "integer" and not isinstance(value, int)):
        raise OrchestratorError(f"{name} は{typ}型にしてください")
    if not lower <= value <= upper:
        raise OrchestratorError(f"{name} の範囲は {lower}～{upper} です")
    if name in ("width", "height") and value % 8:
        raise OrchestratorError(f"{name} は8の倍数にしてください")


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
        if name == "seed":
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
) -> dict:
    """Interpret natural language, unload the chosen LLM, then run a fixed workflow.

    A cancel event only stops this client's wait and does NOT interrupt ComfyUI jobs.
    """
    workflows = config["workflows"]
    if not workflows:
        raise OrchestratorError(
            "workflowsが空です。先にAPI形式JSONを配置してconfig.jsonへ登録してください"
        )
    if not request.strip():
        raise OrchestratorError("自然文の指示を入力してください")
    for field, path_value in (("参照画像", image), ("マスク", mask_image), ("ポーズ画像", pose_image)):
        if path_value is not None and not Path(path_value).is_file():
            raise OrchestratorError(f"{field}が見つかりません: {path_value}")
    if image is not None:
        image = Path(image).resolve()
    if mask_image is not None:
        mask_image = Path(mask_image).resolve()
    if pose_image is not None:
        pose_image = Path(pose_image).resolve()

    # Filter by exact required image sources before asking the LLM.
    # This prevents the LLM from choosing T2I when the user supplied an I2I
    # reference, or choosing I2I with no image to upload.
    if selected_workflow is not None:
        if selected_workflow not in workflows:
            raise OrchestratorError(f"登録されていないワークフローです: {selected_workflow}")
        workflows = {selected_workflow: workflows[selected_workflow]}
    workflows = compatible_workflows(workflows, image, mask_image, pose_image)
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

    def note(message: str) -> None:
        if progress:
            progress(message)

    def check_cancelled() -> None:
        if cancel_event is not None and cancel_event.is_set():
            raise OrchestratorError("生成開始前に処理を中止しました")

    check_cancelled()
    comfy = ComfyUI(config["comfyui"])
    if not dry_run and config["comfyui"].get("free_before_llm", True):
        note("ComfyUI: キューを確認して前回の生成モデルの解放を要求")
        comfy.free_if_idle()
    check_cancelled()

    llm_key = "llm" if "llm" in config else "ollama"
    settings = config[llm_key]
    provider = settings.get("provider", "lmstudio" if llm_key == "llm" else "ollama")
    if provider == "lmstudio":
        from .lmstudio import LMStudio
        plan = LMStudio(settings).interpret(request, workflows, image, progress=note)
    else:
        note("Ollama: 自然文を解釈しモデルをアンロード")
        plan = Ollama(settings).interpret(request, workflows, image)
    check_cancelled()
    # Treat an LLM-proposed seed as untrusted and ignore it, even if the model
    # disregards the schema. An explicit GUI/CLI override always takes priority.
    if isinstance(plan, dict) and isinstance(plan.get("parameters"), dict):
        if "seed" in plan["parameters"]:
            note("LLMが返したSeedは使用せず、GUI指定または乱数で設定します")
        plan = {**plan, "parameters": {k: v for k, v in plan["parameters"].items() if k != "seed"}}
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
    template = load_workflow(
        (config_path.resolve().parent / selection["file"]).resolve(), selection["bindings"]
    )
    note(f"ワークフロー確定: {workflow_id}")
    if dry_run:
        return {"status": "dry_run", "workflow_id": workflow_id, "parameters": params}

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
        "status": "completed", "workflow_id": workflow_id, "parameters": params,
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

    copied = dict(parameters)
    if new_seed and "seed" in bindings:
        copied["seed"] = secrets.randbits(32)
    workflow_id, params = validate_plan(
        {"workflow_id": workflow_id, "parameters": copied},
        {workflow_id: selected}, has_image,
    )
    template = load_workflow(
        (config_path.resolve().parent / selected["file"]).resolve(),
        bindings,
    )
    if cancel_event is not None and cancel_event.is_set():
        raise OrchestratorError("再生成開始前に中止しました")

    comfy = ComfyUI(config["comfyui"])
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
        "parameters": params,
        "prompt_id": prompt_id,
        "outputs": history.get("outputs", {}),
        "comfy_status": history.get("status", {}),
    }
