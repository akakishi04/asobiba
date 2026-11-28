"""H3 continuous-video schedule, cut validation and continuity parameters.

No persistence, media subprocesses or execution jobs.
"""
from __future__ import annotations

import math

from . import h3_prompt
from .parameters import OrchestratorError, check_param, PARAMS
from .h3 import (
    h3_ref2va_filename,
    h3_hybrid_filename,
    h3_hybrid_mode_key,
    H3_REF2VA_DEFAULT_PROMPT,
    ensure_h3_reference_prompt,
    h3_text_model_options,
)
from .workflow_registry import I2V_DEFAULT_PROMPT
from .timeline import (validate_prompt_plan, prompt_for_segment, validate_cut_frames,
                       generation_frames_for_cuts, segment_windows, validate_overlap_frames,
                       CONTINUATION_OVERLAP_FRAMES, GUIDE_CONNECTION_FRAMES)

LONG_VIDEO_ID = "minimax_h3_long_video"
LONG_TARGETS = {"単発": 0, "30秒": 30, "1分": 60, "2分": 120, "3分": 180, "5分": 300}
FPS = 24


class LongVideoPaused(OrchestratorError):
    pass


def check_cancel(cancel_event):
    if cancel_event is not None and cancel_event.is_set():
        raise LongVideoPaused("長尺生成を中断しました。保存済みの区間から再開できます")


def segment_plan(seconds: int, maximum_frames: int) -> list[int]:
    if seconds not in LONG_TARGETS.values() or seconds == 0:
        raise OrchestratorError("合計尺は30秒～5分のプリセットから選択してください")
    if type(maximum_frames) is not int or not 107 <= maximum_frames <= 362 or (maximum_frames - 5) % 17:
        raise OrchestratorError("H3の区間フレーム数が不正です")
    remaining = seconds * FPS
    plan = []
    while remaining > 0:
        overlap = int(bool(plan))
        # Shorten the final request on the legal 17k+5 grid, trimming only
        # the remaining excess during concatenation.
        wanted = min(maximum_frames, remaining + overlap)
        frames = max(107, 5 + 17 * math.ceil((wanted - 5) / 17))
        plan.append(frames)
        remaining -= frames - overlap
    return plan


def schedule_windows(seconds, nominal_frames, cut_frames=None, *, overlap_frames=0):
    """Derive output intervals from the legacy schedule, then extend raw clips."""
    overlap_frames = validate_overlap_frames(overlap_frames)
    base = (generation_frames_for_cuts(cut_frames) if cut_frames is not None
            else segment_plan(seconds, nominal_frames))
    windows = segment_windows(base, seconds, cut_frames=cut_frames, overlap_frames=overlap_frames)
    # Always expose the exact trim used by the runtime, even in old records.
    for i, w in enumerate(windows):
        w.setdefault("trim_start_frames", int(i > 0))
    return windows


def manifest_windows(manifest):
    return schedule_windows(manifest["seconds"], manifest["overrides"]["frames"],
                            manifest.get("cut_frames"),
                            overlap_frames=manifest.get("overlap_frames", 0))


def manifest_schedule(manifest: dict) -> tuple[list[int], list[int] | None, int]:
    """Validate both legacy and versioned lead-in schedules."""
    cuts = manifest.get("cut_frames")
    overlap = validate_overlap_frames(manifest.get("overlap_frames", 0))
    if cuts is not None:
        cuts = validate_cut_frames(cuts)
        if manifest["seconds"] != sum(cuts) / FPS or "prompt_plan" not in manifest:
            raise OrchestratorError("長尺カット記録が不正です")
    if overlap and "prompt_plan" not in manifest:
        raise OrchestratorError("助走付き長尺には区間プロンプト計画が必要です")
    windows = manifest_windows(manifest)
    plan = [w["generation_frames"] for w in windows]
    if manifest["plan"] != plan:
        raise OrchestratorError("長尺計画が不正です")
    return plan, cuts, sum(w["output_frames"] for w in windows)


def continuation_anchor_count(previous, current):
    """One-based frame number: lead-in ends exactly at the output boundary."""
    return previous["trim_start_frames"] + previous["output_frames"] - current["trim_start_frames"] + 1


def continuation_model(model: str) -> str:
    if h3_ref2va_filename(model) is None:
        return model
    filename = h3_hybrid_filename(model)
    if filename is None:
        raise OrchestratorError("長尺連続生成には開始フレーム対応モデルが必要です。純粋Ref2VAではなくHybridまたはFL2VAを選択してください")
    key = h3_hybrid_mode_key(model, reference_only=False)
    if key is None:
        raise OrchestratorError("Hybridの開始フレームモードを確認できません")
    return key


def long_generation_model(overrides, *, text_only=False):
    """A no-image opening uses the same Hybrid weight in its base mode."""
    if text_only:
        return h3_text_model_options(overrides)
    p = dict(overrides)
    if p.get("h3_model") is not None:
        continuation_model(p["h3_model"])
    return p


def continuation_parameters(first: dict, index: int, frames: int) -> dict:
    p = dict(first)
    model = p.get("h3_model")
    if model is not None:
        p["h3_model"] = continuation_model(model)
    prompt = p["positive_prompt"]
    if prompt == H3_REF2VA_DEFAULT_PROMPT:
        prompt = I2V_DEFAULT_PROMPT
    prefix = "Use <Picture 1> as a visual reference, not as the first frame. "
    if prompt.startswith(prefix):
        prompt = prompt[len(prefix):]
    p.update(frames=frames, seed=(int(first["seed"]) + index) % (2 ** 64),
             positive_prompt="Continue the same shot directly from this supplied opening frame. "
                             "Maintain the subject, setting, camera and motion continuity without a cut. " + prompt)
    check_param("seed", p["seed"])
    check_param("positive_prompt", p["positive_prompt"])
    return p


def planned_segment_parameters(base: dict, prompt_plan: dict, index: int, frames: int,
                               *, lead_in_frames=0, guide_frames=0, kept_frames=None,
                               text_only=False) -> dict:
    """Apply only the approved prompt for this interval, including segment zero."""
    p = dict(base)
    model = p.get("h3_model")
    if index and model is not None:
        p["h3_model"] = continuation_model(model)
    p["frames"] = frames
    # The ordinary parameter validator accepts signed 63-bit nonnegative seeds.
    # Wrap on its actual domain, not an unsigned 64-bit domain.
    p["seed"] = (int(base["seed"]) + index) % (PARAMS["seed"][2] + 1)
    if prompt_plan.get("format") == h3_prompt.FORMAT:
        p["positive_prompt"] = h3_prompt.compile_cut(
            prompt_plan, index, index == 0 and h3_ref2va_filename(model) is not None,
            kept_frames=kept_frames, trim_frames=lead_in_frames, guide_frames=guide_frames,
            text_only=text_only and index == 0,
        )
        check_param("seed", p["seed"])
        return p
    p["positive_prompt"] = prompt_for_segment(prompt_plan, index, guide_frames=guide_frames)
    if index and guide_frames:
        p["positive_prompt"] = (
            f"The first {guide_frames / FPS:.3f} seconds are an anchored video clip. "
            "Extend its existing movement immediately after the guide, without replaying or resetting it. "
            + p["positive_prompt"]
        )
        check_param("positive_prompt", p["positive_prompt"])
    elif index and lead_in_frames > 1:
        p["positive_prompt"] = (
            f"Immediately continue the preceding ongoing motion without pausing. "
            f"For the first {lead_in_frames / FPS:.3f} seconds, sustain that motion and the camera trajectory; "
            "then progress into this segment's new action smoothly. "
            "Do not start with a stationary hold or repeat earlier dialogue. "
            + p["positive_prompt"]
        )
        check_param("positive_prompt", p["positive_prompt"])
    if index == 0 and h3_ref2va_filename(model) is not None:
        p["positive_prompt"] = ensure_h3_reference_prompt(p["positive_prompt"])
    check_param("seed", p["seed"])
    return p


def validate_structured_timing(prompt_plan, windows, overrides, *, text_only=False):
    """Fail before creating a revision or submitting any generation job."""
    if prompt_plan is None or prompt_plan.get("format") != h3_prompt.FORMAT:
        return
    reference_only = h3_ref2va_filename(overrides.get("h3_model")) is not None
    for i, w in enumerate(windows):
        try:
            h3_prompt.compile_cut(prompt_plan, i, reference_only and i == 0,
                                  kept_frames=w["output_frames"],
                                  trim_frames=w["trim_start_frames"],
                                  guide_frames=w.get("guide_frames", 0),
                                  text_only=text_only and i == 0)
        except OrchestratorError as exc:
            raise OrchestratorError(f"カット{i+1}: {exc}") from exc


def project_cut_lengths(manifest):
    manifest_schedule(manifest)
    return [w["output_frames"] for w in manifest_windows(manifest)]


def first_changed_cut(manifest, prompt_plan, cut_frames):
    old = manifest.get("prompt_plan")
    if old is None:
        raise OrchestratorError("旧形式の計画なしプロジェクトは編集できません")
    old_cuts = project_cut_lengths(manifest)
    if old["common"] != prompt_plan["common"] or old.get("format") != prompt_plan.get("format"):
        return 0
    for i, (old_text, new_text) in enumerate(zip(old["segments"], prompt_plan["segments"])):
        if old_text != new_text or old_cuts[i] != cut_frames[i]:
            return i
    return min(len(old_cuts), len(cut_frames)) if len(old_cuts) != len(cut_frames) else None


def connection_changed_from(manifest, cut_frames, overlap_frames):
    """Earliest affected cut when the connection policy changes."""
    old_overlap = manifest.get("overlap_frames", 0)
    overlap = validate_overlap_frames(old_overlap if overlap_frames is None else overlap_frames)
    if overlap == old_overlap:
        return None
    same_schedule = list(cut_frames) == project_cut_lengths(manifest)
    new_cuts = manifest.get("cut_frames") if same_schedule else validate_cut_frames(list(cut_frames))
    seconds = manifest["seconds"] if same_schedule else sum(new_cuts) / FPS
    old_windows = manifest_windows(manifest)
    new_windows = schedule_windows(seconds, manifest["overrides"]["frames"], new_cuts,
                                   overlap_frames=overlap)
    return next((i for i, (a, b) in enumerate(zip(old_windows, new_windows))
                 if a["generation_frames"] != b["generation_frames"]
                 or a["trim_start_frames"] != b["trim_start_frames"]
                 or a.get("guide_frames", 0) != b.get("guide_frames", 0)), len(new_windows))
