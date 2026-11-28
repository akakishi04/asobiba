"""Shared structured local-LLM request construction, parsing and validated inference.

Model-specific prompt policies and semantic validators live in their callers.
The H3 diagnostics and bounded translation path retain their previous contract.
"""
from __future__ import annotations

import json
import re

from .parameters import OrchestratorError


IMAGE_REASONING_LABELS = {"off": "OFF", "on": "ON", "auto": "自動"}
IMAGE_REASONING_BY_LABEL = {label: key for key, label in IMAGE_REASONING_LABELS.items()}


def image_reasoning_option(client):
    """Return only an actual capability advertised by the loaded model."""
    preference = client.settings.get("image_reasoning", "off")
    options = getattr(client, "_reasoning_options", ())
    if preference == "off":
        return "off" if "off" in options else None
    if preference == "on":
        default = getattr(client, "_reasoning_default", None)
        if "on" in options:
            return "on"
        if default in ("low", "medium", "high") and default in options:
            return default
        return next((effort for effort in ("medium", "low", "high") if effort in options), None)
    return None


def image_reasoning_description(client):
    option = image_reasoning_option(client)
    preference = client.settings.get("image_reasoning", "off")
    if option == "off":
        return "思考OFF（LM Studio native API）"
    if option is not None:
        return f"思考ON ({option} / LM Studio native API)"
    if preference == "auto":
        return "思考自動（モデル既定）"
    return f"思考{preference.upper()}指定非対応（モデル既定・従来の構造化出力）"


def structured_payload(instance_id, messages, name, schema, *, max_tokens=4096, temperature=0.2):
    """Construct the same OpenAI-compatible JSON contract for all planners."""
    return {
        "model": instance_id,
        "messages": messages,
        "stream": False,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_schema", "json_schema": {"name": name, "schema": schema}},
    }


def read_json_reply(result: dict, label: str) -> dict:
    """Validate an LM Studio structured response without trusting its content."""
    choices = result.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise OrchestratorError(f"LM Studioの{label}応答形式が不正です")
    message = choices[0].get("message")
    raw = message.get("content") if isinstance(message, dict) else None
    if not isinstance(raw, str):
        raise OrchestratorError(f"LM Studioの{label}がJSON文字列を返しませんでした")
    try:
        parsed = json.loads(raw)
    except ValueError as exc:
        raise OrchestratorError(f"LM Studioの{label}のJSONを解析できません: {raw[:150]}") from exc
    if not isinstance(parsed, dict):
        raise OrchestratorError(f"LM Studioの{label}はJSONオブジェクトが必要です")
    return parsed


def check_cancel(cancel_event):
    if cancel_event is not None and cancel_event.is_set():
        from .jobs import JobCancellationRequested
        raise JobCancellationRequested("H3プロンプト計画を中止しました")


def request_validated(client, instance_id, system, user_content, response_schema, name, validator, progress=None,
           cancel_event=None, *, translation_chars=None, direct_answer=False):
    from .lmstudio import _request
    # Translation always opts out of reasoning when supported. Still-image
    # planning and rewriting use the user preference; video stays unchanged.
    translating = translation_chars is not None
    max_tokens = client.settings.get("max_tokens", 4096)
    reasoning = ("off" if "off" in getattr(client, "_reasoning_options", ()) else None) if translating else (
        image_reasoning_option(client) if direct_answer else None)
    native = reasoning is not None
    label = name if direct_answer else "H3 " + name
    if translating:
        # Scale with source length, not the worst-case JSON field limit.
        # Allow sufficient room for Japanese, protected markers and JSON.
        max_tokens = min(max_tokens, max(256, 160 + translation_chars +
                                         48 * len(response_schema.get("properties", {}))))
        system += "\nTranslate directly. Return only the completed JSON object; no analysis, discussion or alternatives."
        if progress:
            method = "思考OFF（LM Studio native API）" if native else "思考OFF指定を確認できないモデル（短い出力上限）"
            progress(f"H3 {name}: {method} / 最大{max_tokens} tokens")
    if direct_answer and not translating:
        system += ("\nReturn only the completed JSON as the final answer; no commentary outside JSON."
                   if reasoning != "off" else
                   "\nAnswer directly. Return only the completed JSON; no analysis or alternatives.")
        if progress:
            progress(f"画像プロンプト: {image_reasoning_description(client)} / 最大{max_tokens} tokens")
    if native:
        # The native API has no response_format; validate the actual final
        # answer against the host contract instead of trusting model text.
        system += ("\nRequired JSON schema (return an object matching it):\n" +
                   json.dumps(response_schema, ensure_ascii=False))
    feedback = ""
    for attempt in range(2):
        check_cancel(cancel_event)
        try:
            if native:
                from .llm_usage import inference_purpose
                with inference_purpose(name):
                    reply = _request(client.settings, "/api/v1/chat", {
                        "model": instance_id, "system_prompt": system + feedback,
                        "input": user_content, "stream": False, "store": False,
                        "reasoning": reasoning, "temperature": 0.0 if translating else 0.2,
                        "max_output_tokens": max_tokens,
                    })
                output = reply.get("output")
                if not isinstance(output, list):
                    raise OrchestratorError("LM Studioのnative chat応答形式が不正です")
                content = "\n".join(item["content"] for item in output
                                    if isinstance(item, dict) and item.get("type") == "message"
                                    and isinstance(item.get("content"), str))
                stats = reply.get("stats", {})
                reasoning_tokens = stats.get("reasoning_output_tokens", 0) if isinstance(stats, dict) else 0
                if any(isinstance(item, dict) and item.get("type") == "reasoning"
                       and item.get("content") for item in output):
                    reasoning_tokens = reasoning_tokens or "あり"
                # Do not use reasoning as the answer. Accept only a complete
                # JSON object, optionally inside a single whole-output fence.
                fenced = re.fullmatch(r"\s*\x60{3}(?:json)?\s*(.*?)\s*\x60{3}\s*", content, re.S | re.I)
                if fenced:
                    content = fenced.group(1)
                reply = {"choices": [{"message": {"content": content,
                                                   "reasoning_content": bool(reasoning_tokens)}}]}
            else:
                reply = _request(client.settings, "/v1/chat/completions", structured_payload(
                    instance_id, [{"role": "system", "content": system + feedback},
                                  {"role": "user", "content": user_content}], name, response_schema,
                    max_tokens=max_tokens, temperature=0.0 if translating else 0.2,
                ))
        except OrchestratorError as exc:
            raise OrchestratorError(
                f"{label}（試行{attempt+1} / 出力上限{max_tokens} tokens）: {exc}"
            ) from exc
        check_cancel(cancel_event)
        if translating or direct_answer:
            choices = reply.get("choices")
            choice = choices[0] if isinstance(choices, list) and choices and isinstance(choices[0], dict) else {}
            message = choice.get("message")
            if isinstance(message, dict) and not str(message.get("content") or "").strip():
                raise OrchestratorError(
                    f"{label}: " + ("翻訳の" if translating else "") + "最終回答が空です。"
                    "LM StudioのReasoningをOFFにするか、非思考モデルを選択してください。"
                    f"（出力上限{max_tokens} tokens、同じ推論は再試行しません）"
                )
            if choice.get("finish_reason") == "length":
                raise OrchestratorError(f"{label}: " + ("翻訳が" if translating else "回答が") + f"出力上限{max_tokens} tokensに達しました。"
                                        "LLMの思考設定または出力上限を確認してください")
        try:
            return validator(read_json_reply(reply, label))
        except OrchestratorError as exc:
            if attempt:
                raise
            feedback = "\nCorrect the invalid structured output and return the complete JSON again. Validation error: " + str(exc)[:220]
            if progress:
                progress(("画像: " if direct_answer else "H3: ") + "プロンプト形式を1回修正します: " + str(exc)[:220])
