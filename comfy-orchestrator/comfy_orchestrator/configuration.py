"""Validate local configuration and registered API-format workflow files."""
from __future__ import annotations

import json
import urllib.parse
from pathlib import Path

from . import h3_prompt, camera_spec
from .parameters import OrchestratorError, PARAMS, check_param
from .workflow_registry import ALLOWED_KINDS, IMAGE_INPUTS, load_workflow


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
        inference_timeout = config["llm"].get("inference_timeout_seconds", 1200)
        if (
            isinstance(inference_timeout, bool)
            or not isinstance(inference_timeout, (int, float))
            or not 30 <= inference_timeout <= 3600
        ):
            raise OrchestratorError("llm.inference_timeout_seconds は30～3600秒の数値です")
        image_reasoning = config["llm"].get("image_reasoning", "off")
        if image_reasoning not in ("off", "on", "auto"):
            raise OrchestratorError("llm.image_reasoning は off、on、auto のいずれかです")
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
        if config["llm"].get("h3_prompt_format", h3_prompt.LEGACY) not in (h3_prompt.LEGACY, h3_prompt.FORMAT):
            raise OrchestratorError("llm.h3_prompt_format は h3_official_v1 または legacy です")
        if not isinstance(config["llm"].get("h3_reference_vision", True), bool):
            raise OrchestratorError("llm.h3_reference_vision は真偽値です")
        if not isinstance(config["llm"].get("send_reference_to_llm", False), bool):
            raise OrchestratorError("llm.send_reference_to_llm は真偽値です")
    if isinstance(config.get("ui"), dict):
        camera_spec.normalize(config["ui"].get(camera_spec.KEY))
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
