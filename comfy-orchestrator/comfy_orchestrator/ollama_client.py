"""Legacy Ollama adapter kept for existing CLI configurations."""
from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

from . import http_api
from .parameters import OrchestratorError
from .workflow_registry import plan_schema


class Ollama:
    def __init__(self, settings: dict):
        self.base = settings["base_url"]
        self.model = settings["model"]
        self.timeout = http_api._positive_number(settings.get("timeout_seconds"), "ollama.timeout_seconds", 240)

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
            result = http_api.http_json(self.base, "/api/generate", request, self.timeout)
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
            unloaded = http_api.http_json(self.base, "/api/generate", {"model": self.model, "keep_alive": 0}, self.timeout)
            if unloaded.get("done") is not True or unloaded.get("done_reason", "unload") != "unload":
                raise OrchestratorError(f"Ollamaのアンロード完了を確認できません: {unloaded}")
