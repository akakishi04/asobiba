"""LM Studio native model lifecycle and OpenAI-compatible structured inference.

The selected LM Studio model is unloaded before ComfyUI starts generation.
Other loaded models are never unloaded implicitly.
"""

from __future__ import annotations

import base64
import json
import mimetypes
import os
import urllib.request
from pathlib import Path
from typing import Any, Callable

from .core import OrchestratorError, _open_json, plan_schema


def _request(settings: dict, route: str, payload: dict | None = None) -> dict:
    base = settings["base_url"].rstrip("/")
    timeout = float(settings.get("timeout_seconds", 240))
    headers = {"Content-Type": "application/json"}
    token = os.environ.get(settings.get("token_env", "LMSTUDIO_API_TOKEN"), "")
    if token:
        headers["Authorization"] = "Bearer " + token
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        base + "/" + route.lstrip("/"),
        data=data,
        headers=headers,
        method="POST" if data is not None else "GET",
    )
    return _open_json(request, timeout=timeout)


def list_models(settings: dict) -> list[dict]:
    """List local LM Studio LLMs; does not load them."""
    result = _request(settings, "/api/v1/models")
    models = result.get("models")
    if not isinstance(models, list):
        raise OrchestratorError("LM Studioのモデル一覧応答が不正です。サーバーが起動しているか確認してください")
    return [
        item for item in models
        if isinstance(item, dict) and item.get("type") == "llm"
        and isinstance(item.get("key"), str)
    ]


class LMStudio:
    def __init__(self, settings: dict):
        self.settings = settings
        self.model = settings["model"]
        self.unload_after = settings.get("unload_after_inference", True)

    def _ensure_loaded(self) -> str:
        catalog = list_models(self.settings)
        matching = next((item for item in catalog if item["key"] == self.model), None)
        if matching is None:
            raise OrchestratorError(
                f"LM Studioにモデル {self.model!r} がありません。GUIの「モデルを更新」から選択してください"
            )
        running = matching.get("loaded_instances") or []
        if running:
            instance_id = running[0].get("id") if isinstance(running[0], dict) else None
            if not instance_id:
                raise OrchestratorError("LM StudioのモデルインスタンスIDを取得できません")
            return instance_id

        settings = {"model": self.model}
        if self.settings.get("context_length") is not None:
            settings["context_length"] = self.settings["context_length"]
        result = _request(self.settings, "/api/v1/models/load", settings)
        if result.get("status") != "loaded" or not isinstance(result.get("instance_id"), str):
            raise OrchestratorError(f"LM Studioのロード完了を確認できません: {result}")
        return result["instance_id"]

    def interpret(
        self, text: str, workflows: dict, image: Path | None,
        progress: Callable[[str], None] | None = None,
    ) -> dict:
        if not isinstance(self.model, str) or not self.model.strip() or self.model == "SELECT_IN_GUI":
            raise OrchestratorError("LM Studioのモデルを選択してください")
        instance_id: str | None = None
        catalog = [
            {"id": key, "kind": entry["kind"], "description": entry.get("description", ""),
             "parameters": [name for name in entry["bindings"] if name != "image"],
             "requires_image": "image" in entry["bindings"]}
            for key, entry in workflows.items()
        ]
        system = (
            "You are a fixed ComfyUI workflow selector. Output JSON matching the provided schema. "
            "Select workflow_id only from the catalog. Never invent nodes, paths, or model names. "
            "Write a detailed positive_prompt suitable for the image-generation model; "
            "use short comma-separated English visual tags for anime-style SDXL workflows. "
            "Keep instructions faithful to the user's request. "
            "Only supply parameters supported by the selected workflow."
        )
        user_text = (
            f"Available workflows: {json.dumps(catalog, ensure_ascii=False)}\n"
            f"Reference image: {'yes' if image else 'no'}\n"
            f"User request: {text}"
        )
        message: dict[str, Any] = {"role": "user", "content": user_text}
        if image is not None:
            if not image.is_file():
                raise OrchestratorError(f"参照画像が見つかりません: {image}")
            if image.stat().st_size > 20 * 1024 * 1024:
                raise OrchestratorError("LM Studioに渡す参照画像は20MB以下にしてください")
            mime = mimetypes.guess_type(image.name)[0]
            if mime not in ("image/png", "image/jpeg", "image/webp"):
                raise OrchestratorError("LM Studioの参照画像はPNG、JPEG、WebPに対応します")
            data = base64.b64encode(image.read_bytes()).decode("ascii")
            message["content"] = [
                {"type": "text", "text": user_text},
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{data}"}},
            ]

        try:
            if progress:
                progress("LM Studio: モデルを確認・ロード")
            instance_id = self._ensure_loaded()
            if progress:
                progress("LM Studio: 自然文を解釈")
            request = {
                "model": instance_id,
                "messages": [{"role": "system", "content": system}, message],
                "stream": False,
                "temperature": 0.2,
                "max_tokens": 2048,
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {"name": "comfy_plan", "schema": plan_schema(workflows)},
                },
            }
            result = _request(self.settings, "/v1/chat/completions", request)
            choices = result.get("choices")
            if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
                raise OrchestratorError(f"LM Studioの回答形式が不正です: {str(result)[:300]}")
            message_result = choices[0].get("message")
            raw = message_result.get("content") if isinstance(message_result, dict) else None
            if not isinstance(raw, str):
                raise OrchestratorError("LM StudioがJSONの文章を返しませんでした")
            try:
                answer = json.loads(raw)
            except ValueError as exc:
                raise OrchestratorError(f"LM StudioのJSON解釈に失敗: {raw[:300]}") from exc
            if not isinstance(answer, dict):
                raise OrchestratorError("LM Studioの解釈結果がJSONオブジェクトではありません")
            return answer
        finally:
            if instance_id and self.unload_after:
                if progress:
                    progress("LM Studio: 選択モデルをアンロード")
                response = _request(self.settings, "/api/v1/models/unload", {"instance_id": instance_id})
                if response.get("instance_id") != instance_id:
                    raise OrchestratorError(
                        "LM Studioのアンロード完了を確認できません。VRAM競合を避けるため生成を中止します"
                    )
