"""Host-timed, editable prompt plans for continuous H3 videos."""
from __future__ import annotations

import json
from pathlib import Path

from .parameters import OrchestratorError, check_param

FPS = 24
MAX_PART = 1600
CONTINUATION = (
    "Continue directly from the supplied opening frame. Preserve the established "
    "identity and visual style. Perform only this segment's progression, without an abrupt cut. "
)


def segment_windows(frames: list[int], seconds: int) -> list[dict]:
    """Effective output time, excluding the shared boundary and trimmed tail."""
    end = 0
    windows = []
    for index, count in enumerate(frames):
        start = end
        end = min(seconds * FPS, start + count - int(index > 0))
        if end <= start:
            raise OrchestratorError("長尺タイムラインの区間が不正です")
        windows.append({"index": index + 1, "start_frame": start,
                        "end_frame": end, "generation_frames": count})
    if end != seconds * FPS:
        raise OrchestratorError("長尺タイムラインの合計尺が一致しません")
    return windows


def validate_prompt_plan(value: dict, count: int) -> dict:
    """Reject missing, extra or empty segments rather than guessing or repeating."""
    if not isinstance(value, dict) or set(value) != {"common", "segments"}:
        raise OrchestratorError("長尺計画には共通プロンプトと区間別プロンプトが必要です")
    common, segments = value["common"], value["segments"]
    if not isinstance(common, str) or len(common) > MAX_PART:
        raise OrchestratorError(f"共通プロンプトは{MAX_PART}文字以内にしてください")
    if not isinstance(segments, list) or len(segments) != count:
        raise OrchestratorError(f"区間別プロンプトは{count}件必要です")
    result = []
    for i, part in enumerate(segments):
        if not isinstance(part, str) or not part.strip() or len(part) > MAX_PART:
            raise OrchestratorError(f"区間{i + 1}のプロンプトが空欄または長すぎます")
        result.append(part.strip())
    return {"common": common.strip(), "segments": result}


def prompt_for_segment(plan: dict, index: int) -> str:
    text = " ".join(part for part in (plan["common"], plan["segments"][index]) if part)
    if index:
        text = CONTINUATION + text
    check_param("positive_prompt", text)
    return text


def prompt_plan_schema(count: int) -> dict:
    return {
        "type": "object",
        "properties": {
            "common": {"type": "string", "maxLength": MAX_PART},
            "segments": {"type": "array", "minItems": count, "maxItems": count,
                         "items": {"type": "string", "minLength": 1, "maxLength": MAX_PART}},
        },
        "required": ["common", "segments"],
        "additionalProperties": False,
    }


def plan_long_prompts(config: dict, request: str, frames: list[int], seconds: int,
                      reference_only: bool = False, *, progress=None,
                      cancel_event=None, prompt_cache=None, release_comfy=True) -> dict:
    """One structured text-only LM Studio inference; never generate media here."""
    from . import core
    from .lmstudio import LMStudio, _request, read_json_reply
    from .prompt_cache import CACHE_ERRORS, content_sha256, make_cache_key
    from .prompt_profiles import DEFAULT_H3_PROFILE, apply_h3_profile

    def note(text):
        if progress:
            progress(text)

    def check_cancel():
        if cancel_event is not None and cancel_event.is_set():
            raise core.JobCancellationRequested("長尺プロンプト計画を中止しました")

    windows = segment_windows(frames, seconds)
    count = len(windows)
    check_cancel()
    if not request.strip():
        # Preserve the existing image-only option, which needs no LLM.
        return validate_prompt_plan({
            "common": "Preserve the supplied subject appearance and visual style.",
            "segments": ["Natural coherent motion, without introducing new actions or scenery."] * count,
        }, count)
    settings = {**config["llm"], "send_reference_to_llm": False}
    if not settings.get("model") or settings["model"] == "SELECT_IN_GUI":
        raise OrchestratorError("LM Studioのモデルを選択してください")
    workflow = {core.H3_I2V_ID: config["workflows"][core.H3_I2V_ID]}
    profile = settings.get("h3_prompt_profile", DEFAULT_H3_PROFILE)
    key = None
    if prompt_cache is not None:
        try:
            key = make_cache_key(request, settings, workflow, {
                "task": "long_prompt_plan", "policy": content_sha256(Path(__file__)),
                "seconds": seconds, "frames": frames, "reference_only": reference_only,
            }, {}, None)
            cached = prompt_cache.get(key)
            if cached is not None:
                try:
                    result = validate_prompt_plan(cached, count)
                except OrchestratorError:
                    pass
                else:
                    note("長尺プロンプト: 解釈キャッシュを使用")
                    return result
        except CACHE_ERRORS as exc:
            note(f"長尺キャッシュ読込失敗（通常処理を継続）: {exc}")
    if release_comfy and config["comfyui"].get("free_before_llm", True):
        note("ComfyUI: 長尺計画の前に生成モデルを解放")
        core.ComfyUI(config["comfyui"]).free_if_idle()
    check_cancel()
    system = apply_h3_profile(
        "You plan one continuous H3 image-to-video sequence. "
        "Return JSON matching the schema. The host owns all times and technical parameters.",
        workflow, profile, reference_only=reference_only,
    ) + (
        "\nSplit the user's entire request into exactly the ordered host segments. "
        "Use concise natural English sentences. Preserve quoted speech and its requested language. "
        "common is ONLY persistent visual, character, setting and audio constraints; "
        "never put a one-time action or a changing state in common. "
        "Each segments item is the motion, camera and audio for that interval only, "
        "with a clear progression from the preceding interval's end state. "
        "Do not restart an earlier action or repeat dialogue at every interval. "
        "The first segment must establish the scene; subsequent segments start from "
        "the previous clip's last frame. Make each action feasible within its effective time. "
        "If a simple action finishes early, maintain the resulting state instead of inventing events. "
        "Do not invent reference-image details: you cannot see the image. "
        "Do not output picture markers or workflow/model parameters. "
        "Keep each segment concise (usually one or two short sentences), even for a long timeline."
    )
    payload = {
        "request": request, "total_seconds": seconds, "fps": FPS,
        "first_reference_mode": "visual reference" if reference_only else "opening frame",
        "timeline": windows,
    }
    client = LMStudio(settings)
    instance_id = None
    try:
        note(f"LM Studio: {count}区間のプロンプトを一括作成")
        instance_id = client._ensure_loaded()
        check_cancel()
        reply = _request(settings, "/v1/chat/completions", {
            "model": instance_id,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
            "stream": False, "temperature": 0.2,
            "max_tokens": settings.get("max_tokens", 4096),
            "response_format": {"type": "json_schema", "json_schema": {
                "name": "continuous_video_prompt_plan", "schema": prompt_plan_schema(count)}},
        })
        result = validate_prompt_plan(read_json_reply(reply, "長尺プロンプト計画"), count)
    finally:
        if instance_id and client.unload_after:
            note("LM Studio: 選択モデルをアンロード")
            response = _request(settings, "/api/v1/models/unload", {"instance_id": instance_id})
            if response.get("instance_id") != instance_id:
                raise OrchestratorError("LM Studioのアンロード完了を確認できません")
    check_cancel()
    if key is not None:
        try:
            prompt_cache.put(key, result)
        except CACHE_ERRORS as exc:
            note(f"長尺キャッシュ保存失敗（通常処理を継続）: {exc}")
    return result
