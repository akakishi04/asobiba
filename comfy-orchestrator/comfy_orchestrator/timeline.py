"""Host-timed, editable prompt plans for continuous H3 videos."""
from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

from .parameters import OrchestratorError, check_param

FPS = 24
MIN_CUT_FRAMES = FPS
MAX_CUT_FRAMES = 15 * FPS
H3_MAX_GENERATION_FRAMES = 362
CONTINUATION_OVERLAP_FRAMES = 12
MAX_TOTAL_FRAMES = 300 * FPS
CUSTOM_CUTS = "カット別指定"
MAX_PART = 1600
CONTINUATION = (
    "Continue directly from the supplied opening frame. Preserve the established "
    "identity and visual style. Perform only this segment's progression, without an abrupt cut. "
)


def parse_cut_seconds(value: str) -> int:
    """Convert decimal seconds to the closest frame; no binary-float timing."""
    try:
        seconds = Decimal(value.strip())
        if not seconds.is_finite() or not Decimal(1) <= seconds <= Decimal(15):
            raise ValueError()
        return int((seconds * FPS).to_integral_value(rounding=ROUND_HALF_UP))
    except (AttributeError, InvalidOperation, ValueError, OverflowError) as exc:
        raise OrchestratorError("カット尺は1～15秒の数値で指定してください") from exc


def format_cut_seconds(frames: int) -> str:
    return f"{frames / FPS:.3f}".rstrip("0").rstrip(".")


def validate_cut_frames(cuts: list[int]) -> list[int]:
    if not isinstance(cuts, list) or not 2 <= len(cuts) <= 300:
        raise OrchestratorError("連続動画には2～300カットが必要です")
    if any(type(n) is not int or not MIN_CUT_FRAMES <= n <= MAX_CUT_FRAMES for n in cuts):
        raise OrchestratorError("各カットは1～15秒（24fps）にしてください")
    if sum(cuts) > MAX_TOTAL_FRAMES:
        raise OrchestratorError("カットの合計尺は5分以内にしてください")
    return list(cuts)


def generation_frames_for_cuts(cuts: list[int]) -> list[int]:
    """Smallest legal H3 clip covering kept frames plus the repeated anchor."""
    cuts = validate_cut_frames(cuts)
    return [max(107, 5 + 17 * ((count + int(i > 0) - 5 + 16) // 17))
            for i, count in enumerate(cuts)]


def default_cut_frames(seconds: int, nominal_frames: int) -> list[int]:
    """Seed the editable duration list from the preset, without tiny tail cuts."""
    if type(seconds) is not int or not 2 <= seconds <= 300:
        raise OrchestratorError("初期合計尺が不正です")
    limit = min(MAX_CUT_FRAMES, max(MIN_CUT_FRAMES, nominal_frames - 1))
    total = seconds * FPS
    full, remainder = divmod(total, limit)
    cuts = [limit] * full
    if remainder:
        if remainder < MIN_CUT_FRAMES and cuts:
            cuts[-1] -= MIN_CUT_FRAMES - remainder
            remainder = MIN_CUT_FRAMES
        cuts.append(remainder)
    if len(cuts) == 1:
        cuts = [total // 2, total - total // 2]
    return validate_cut_frames(cuts)


def validate_overlap_frames(value):
    """Zero is the legacy one-anchor-frame continuation, not a hard cut."""
    if type(value) is not int or not 0 <= value <= CONTINUATION_OVERLAP_FRAMES:
        raise OrchestratorError("長尺助走フレーム数が不正です")
    return value


def continuation_skip_frames(kept_frames, overlap_frames):
    """Number of frames discarded at the start, including the opening anchor."""
    overlap_frames = validate_overlap_frames(overlap_frames)
    skips = []
    for i, kept in enumerate(kept_frames):
        if type(kept) is not int or not 1 <= kept <= H3_MAX_GENERATION_FRAMES:
            raise OrchestratorError("長尺区間の採用フレーム数が不正です")
        if not i:
            skips.append(0)
            continue
        # Preserve the exact output duration even at H3's 362-frame ceiling.
        skip = min(max(1, overlap_frames), kept_frames[i - 1],
                   max(1, kept - 1), H3_MAX_GENERATION_FRAMES - kept)
        if skip < 1:
            raise OrchestratorError("助走を含めるとH3の最大生成フレーム数を超えます")
        skips.append(skip)
    return skips


def segment_windows(frames: list[int], seconds: int | float, *, cut_frames=None,
                    overlap_frames=0) -> list[dict]:
    """Effective output time, excluding the shared boundary and trimmed tails."""
    if cut_frames is not None:
        cut_frames = validate_cut_frames(cut_frames)
        if frames != generation_frames_for_cuts(cut_frames) or seconds != sum(cut_frames) / FPS:
            raise OrchestratorError("カット尺とH3生成フレーム数が一致しません")
        total = sum(cut_frames)
    else:
        total = seconds * FPS
    end = 0
    windows = []
    for index, count in enumerate(frames):
        start = end
        kept = cut_frames[index] if cut_frames is not None else min(total - start, count - int(index > 0))
        end = start + kept
        if kept <= 0 or kept + int(index > 0) > count:
            raise OrchestratorError("長尺タイムラインの区間が不正です")
        windows.append({"index": index + 1, "start_frame": start,
                        "end_frame": end, "generation_frames": count,
                        "output_frames": kept, "duration_seconds": kept / FPS})
    if end != total:
        raise OrchestratorError("長尺タイムラインの合計尺が一致しません")
    overlap_frames = validate_overlap_frames(overlap_frames)
    if overlap_frames:
        kept = [w["output_frames"] for w in windows]
        skips = continuation_skip_frames(kept, overlap_frames)
        for w, skip in zip(windows, skips):
            needed = w["output_frames"] + skip
            w["generation_frames"] = max(107, 5 + 17 * ((needed - 5 + 16) // 17))
            w["trim_start_frames"] = skip
            w["lead_in_seconds"] = skip / FPS
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


def _request_plan(settings, request_fn, instance_id, system, payload, schema, name):
    from .lmstudio import read_json_reply
    reply = request_fn(settings, "/v1/chat/completions", {
        "model": instance_id,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
        "stream": False, "temperature": 0.2,
        "max_tokens": settings.get("max_tokens", 4096),
        "response_format": {"type": "json_schema", "json_schema": {"name": name, "schema": schema}},
    })
    return read_json_reply(reply, "長尺プロンプト計画")


def _batched_plan(settings, request_fn, instance_id, system, payload, note, check_cancel):
    windows = payload["timeline"]
    max_tokens = settings.get("max_tokens", 4096)
    context = settings.get("context_length") or 8192
    if max_tokens < 1024 or context < 4096:
        raise OrchestratorError("多数カットの計画にはmax_tokens 1024以上、context_length 4096以上を推奨します")
    batch_size = max(4, min(12, max_tokens // 180, context // 500))
    batches = [windows[i:i + batch_size] for i in range(0, len(windows), batch_size)]
    # Group outline into at most 12 major stages so a 300-cut timeline never
    # requires a 300-item input or output in the initial inference.
    stride = max(1, (len(batches) + 11) // 12)
    groups = [batches[i:i + stride] for i in range(0, len(batches), stride)]
    summaries = [{"first_cut": group[0][0]["index"], "last_cut": group[-1][-1]["index"],
                  "start_frame": group[0][0]["start_frame"], "end_frame": group[-1][-1]["end_frame"]}
                 for group in groups]
    base = {k: v for k, v in payload.items() if k != "timeline"}
    note(f"LM Studio: 全体構成を{len(groups)}章に分割")
    check_cancel()
    outline = validate_prompt_plan(_request_plan(
        settings, request_fn, instance_id,
        system + "\nOUTLINE ONLY: each supplied group is a broad story stage, not an individual cut. "
        "Return shared constraints in common and one concise stage summary per group. "
        "Distribute the requested story across the full duration.",
        {**base, "timeline_groups": summaries}, prompt_plan_schema(len(groups)), "continuous_outline",
    ), len(groups))
    details = []
    for group_index, group in enumerate(groups):
        for batch in group:
            check_cancel()
            note(f"LM Studio: カット{batch[0]['index']}～{batch[-1]['index']}の詳細計画")
            schema = {"type": "object", "properties": {"segments": {
                "type": "array", "minItems": len(batch), "maxItems": len(batch),
                "items": {"type": "string", "minLength": 1, "maxLength": MAX_PART}}},
                "required": ["segments"], "additionalProperties": False}
            previous = details[-1] if details else ""
            part = _request_plan(
                settings, request_fn, instance_id,
                system + "\nDETAIL ONLY: shared constraints are already fixed. Return only segments "
                "for the supplied cut windows. Do not repeat the whole stage in each batch. "
                "Use the preceding cut and the current stage's start/end to determine progression.",
                {**base, "common": outline["common"], "stage": summaries[group_index],
                 "stage_summary": outline["segments"][group_index],
                 "next_stage": outline["segments"][group_index + 1] if group_index + 1 < len(groups) else "",
                 "previous_cut": previous, "timeline": batch},
                schema, "continuous_cut_batch",
            )
            if set(part) != {"segments"}:
                raise OrchestratorError("区間別の詳細計画形式が不正です")
            validated = validate_prompt_plan({"common": outline["common"], "segments": part["segments"]}, len(batch))
            details.extend(validated["segments"])
    return validate_prompt_plan({"common": outline["common"], "segments": details}, len(windows))


def plan_long_prompts(config: dict, request: str, frames: list[int], seconds: int,
                      reference_only: bool = False, *, cut_frames=None, progress=None,
                      cancel_event=None, prompt_cache=None, release_comfy=True,
                      overlap_frames=0) -> dict:
    """Plan text in one model session; large timelines use outline plus batches."""
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

    windows = segment_windows(frames, seconds, cut_frames=cut_frames, overlap_frames=overlap_frames)
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
                "seconds": seconds, "frames": frames, "cut_frames": cut_frames,
                "overlap_frames": overlap_frames, "reference_only": reference_only,
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
    if release_comfy:
        from .model_runtime import release_comfy_before_llm
        release_comfy_before_llm(config["comfyui"], progress=note)
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
        "The first segment must establish the scene; later segments continue from a supplied frame "
        "near the preceding clip's retained end. Make each action feasible within its effective time. "
        "Complete requested actions within the retained output window; discard any lead-in and unused tail. "
        "If trim_start_frames is supplied, the initial lead-in is continuity of prior motion only. "
        "Do not place new actions or dialogue exclusively in that discarded lead-in or tail. "
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
        instance_id = client._ensure_loaded()
        check_cancel()
        if count <= 12:
            note(f"LM Studio: {count}区間のプロンプトを一括作成")
            result = validate_prompt_plan(_request_plan(
                settings, _request, instance_id, system, payload,
                prompt_plan_schema(count), "continuous_video_prompt_plan",
            ), count)
        else:
            result = _batched_plan(settings, _request, instance_id, system, payload, note, check_cancel)
    finally:
        client.unload_selected(instance_id, note)
    check_cancel()
    if key is not None:
        try:
            prompt_cache.put(key, result)
        except CACHE_ERRORS as exc:
            note(f"長尺キャッシュ保存失敗（通常処理を継続）: {exc}")
    return result
