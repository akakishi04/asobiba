"""ComfyUI transport, model inventory, targeted job submission and polling.

Dependency checks inspect registered graphs without importing the generation
orchestrator. This client never invokes a language model.
"""
from __future__ import annotations

import hashlib
import mimetypes
import re
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any

from . import http_api
from .http_api import APIHTTPError
from .parameters import OrchestratorError
from .jobs import JobCancellationRequested, JobExecutionFailed, JobSubmissionRejected
from .model_runtime import record_model_event


def combo_choices(node_info: dict, field: str) -> tuple[str, ...]:
    """Read legacy dropdowns and V3 COMBO schemas without coercing scalars."""
    spec = node_info["input"]["required"][field]
    if not isinstance(spec, (list, tuple)) or not spec:
        raise TypeError("invalid combo schema")
    if isinstance(spec[0], (list, tuple)):
        choices = spec[0]
    elif spec[0] == "COMBO" and len(spec) >= 2 and isinstance(spec[1], dict):
        choices = spec[1].get("options")
    else:
        raise TypeError("input is not a dropdown")
    if not isinstance(choices, (list, tuple)) or any(not isinstance(value, str) for value in choices):
        raise TypeError("invalid dropdown options")
    return tuple(choices)


class ComfyUI:
    def __init__(self, settings: dict):
        self.base = settings["base_url"]
        self.timeout = http_api._positive_number(settings.get("timeout_seconds"), "comfyui.timeout_seconds", 60)
        self.poll = http_api._positive_number(settings.get("poll_seconds"), "comfyui.poll_seconds", 2)
        self.wait_timeout = http_api._positive_number(settings.get("generation_timeout_seconds"), "comfyui.generation_timeout_seconds", 1800)

    def queue_is_idle(self) -> bool:
        queue = http_api.http_json(self.base, "/queue", timeout=self.timeout)
        for field in ("queue_running", "queue_pending"):
            if not isinstance(queue.get(field), list):
                raise OrchestratorError("ComfyUIのキュー応答が不正です")
        return not queue["queue_running"] and not queue["queue_pending"]

    def free_if_idle(self) -> None:
        if not self.queue_is_idle():
            raise OrchestratorError("ComfyUIに他の実行・待機ジョブがあります。VRAM解放せず中断しました")
        http_api.http_json(self.base, "/free", {"unload_models": True, "free_memory": True}, self.timeout, allow_empty=True)
        record_model_event("comfy_release_requests")

    def upload_image(self, image: Path) -> str:
        if not image.is_file():
            raise OrchestratorError(f"画像が見つかりません: {image}")
        if image.stat().st_size > 40 * 1024 * 1024:
            raise OrchestratorError("画像は40MB以下にしてください")
        boundary = uuid.uuid4().hex
        data = image.read_bytes()
        if len(data) > 40 * 1024 * 1024:
            raise OrchestratorError("画像は40MB以下にしてください")
        # Content-addressed input names let ComfyUI deduplicate identical bytes.
        # Always POST: a prior upload might have been removed from the backend.
        suffix = image.suffix.lower()
        if not re.fullmatch(r"\.[a-z0-9]{1,8}", suffix):
            suffix = ""
        filename = "asobiba_" + hashlib.sha256(data).hexdigest() + suffix
        ctype = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        prefix = (
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"image\"; filename=\"{filename}\"\r\n"
            f"Content-Type: {ctype}\r\n\r\n"
        ).encode("utf-8")
        payload = prefix + data + f"\r\n--{boundary}--\r\n".encode("ascii")
        req = urllib.request.Request(
            self.base.rstrip("/") + "/upload/image", data=payload,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}, method="POST",
        )
        result = http_api._open_json(req, self.timeout)
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
            info = http_api.http_json(self.base, "/object_info/ControlNetLoader", timeout=self.timeout)
            model_choices = combo_choices(info["ControlNetLoader"], "control_net_name")
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
                info = http_api.http_json(self.base, "/object_info/DWPreprocessor", timeout=self.timeout)
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
            info = http_api.http_json(self.base, "/object_info/" + class_type, timeout=min(self.timeout, 12))
            if class_type == "UnetLoaderGGUF" and class_type not in info:
                inventory[class_type] = ()
                continue
            try:
                inventory[class_type] = combo_choices(info[class_type], field)
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
                    "MiniMaxH3AddGuide", "ImageBatch",
                    "HunyuanVideo15ImageToVideo", "CLIPVisionEncode", "ModelSamplingSD3",
                    "VAEDecodeAudio", "CreateVideo", "SaveVideo",
                    "ModelSamplingAuraFlow", "EmptySD3LatentImage", "BlockSparseAttention"}
        for class_type in sorted(required | set(loaders)):
            if not any(n.get("class_type") == class_type for n in workflow.values()):
                continue
            try:
                info = http_api.http_json(self.base, "/object_info/" + class_type, timeout=self.timeout)
                node_info = info[class_type]
                if not isinstance(node_info, dict):
                    raise KeyError(class_type)
                if class_type not in loaders:
                    continue
                fields = loaders[class_type]
                if isinstance(fields, str):
                    fields = (fields,)
                choices_by_field = {
                    field: combo_choices(node_info, field) for field in fields
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
                            f"生成モデルがありません: {wanted}。READMEのモデル導入手順を確認してください"
                        )

    def extend_video_timeout(self, settings: dict) -> None:
        self.wait_timeout = max(
            self.wait_timeout,
            http_api._positive_number(settings.get("video_generation_timeout_seconds"),
                             "comfyui.video_generation_timeout_seconds", 7200),
        )

    def submit(self, workflow: dict, *, prompt_id: str | None = None) -> str:
        payload = {"prompt": workflow}
        if prompt_id is not None:
            payload["prompt_id"] = prompt_id
        try:
            result = http_api.http_json(self.base, "/prompt", payload, self.timeout)
        except APIHTTPError as exc:
            # HTTP validation rejection at submission differs from transport
            # failures or errors while waiting for an accepted prompt.
            if exc.status in (400, 422):
                raise JobSubmissionRejected(str(exc)) from exc
            raise
        prompt_id = result.get("prompt_id")
        if not isinstance(prompt_id, str) or not prompt_id:
            raise OrchestratorError(f"ComfyUIがワークフローを受理しませんでした: {result}")
        return prompt_id

    def job_history(self, prompt_id: str) -> dict | None:
        route = "/history/" + urllib.parse.quote(prompt_id, safe="")
        results = http_api.http_json(self.base, route, timeout=self.timeout)
        item = results.get(prompt_id)
        if item is not None and not isinstance(item, dict):
            raise OrchestratorError(f"履歴の形式が不正です: {prompt_id}")
        return item

    def job_queue_state(self, prompt_id: str) -> str:
        queue = http_api.http_json(self.base, "/queue", timeout=self.timeout)
        for field, state in (("queue_running", "running"), ("queue_pending", "pending")):
            if any(isinstance(item, (tuple, list)) and len(item) >= 2 and item[1] == prompt_id
                   for item in queue.get(field, ())):
                return state
        return "unknown"

    def request_job_cancel(self, prompt_id: str) -> None:
        """Only use the prompt-ID-targeted API verified on ComfyUI v0.46.3+."""
        stats = http_api.http_json(self.base, "/system_stats", timeout=self.timeout)
        version = stats.get("system", {}).get("comfyui_version", "")
        match = re.match(r"^(\d+)\.(\d+)\.(\d+)(?:$|[.+-])", version) if isinstance(version, str) else None
        if match is None or tuple(map(int, match.groups())) < (0, 46, 3):
            raise OrchestratorError(
                f"個別停止対応を確認できないため停止要求を送信しません。ComfyUIで確認してください: {prompt_id}"
            )
        if not isinstance(prompt_id, str) or not prompt_id:
            raise OrchestratorError("停止するジョブIDがありません")
        # First remove this ID if pending; if it became active, the server
        # checks that the same ID is running before issuing its interrupt.
        http_api.http_json(self.base, "/queue", {"delete": [prompt_id]}, self.timeout, allow_empty=True)
        http_api.http_json(self.base, "/interrupt", {"prompt_id": prompt_id}, self.timeout, allow_empty=True)

    def wait(self, prompt_id: str, cancel_event: Any = None, *, cancel_remote: bool = False) -> dict:
        deadline = time.monotonic() + self.wait_timeout
        while time.monotonic() < deadline:
            if cancel_event is not None and cancel_event.is_set():
                if cancel_remote:
                    self.request_job_cancel(prompt_id)
                    raise JobCancellationRequested(
                        f"対象ジョブの停止要求を送信しました（終了未確認）: {prompt_id}"
                    )
                raise OrchestratorError(
                    f"結果待機を終了しました。ComfyUI上の生成ジョブは継続します: prompt_id={prompt_id}"
                )
            item = self.job_history(prompt_id)
            if item is not None:
                status = item.get("status", {})
                if isinstance(status, dict) and (status.get("status_str") == "error" or status.get("completed") is False):
                    raise JobExecutionFailed(f"ComfyUIの生成が失敗しました: {prompt_id}: {status}")
                return item
            time.sleep(self.poll)
        raise OrchestratorError(f"生成結果の待機がタイムアウトしました。ComfyUIで確認してください: prompt_id={prompt_id}")
