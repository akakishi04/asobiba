"""Sequential H3 continuation and resumable generation execution.

Existing long_video imports remain available for callers. Scheduling, storage
and media handling are implemented by their respective modules.
"""
from __future__ import annotations

from contextlib import nullcontext
import tempfile
import time
from pathlib import Path

from . import core, h3_prompt
from .jobs import JobCancellationRequested, JobExecutionFailed, UnknownLongJob
from .timeline import (validate_prompt_plan, prompt_for_segment, validate_cut_frames,
                       generation_frames_for_cuts, segment_windows, validate_overlap_frames,
                       CONTINUATION_OVERLAP_FRAMES, GUIDE_CONNECTION_FRAMES)
from .timing import report_estimate, ERRORS as TIMING_ERRORS
from .project_lock import lock_project
from .long_video_plan import (
    LONG_VIDEO_ID, LONG_TARGETS, FPS, LongVideoPaused, check_cancel,
    segment_plan, schedule_windows, manifest_windows, manifest_schedule,
    continuation_anchor_count, continuation_model, long_generation_model,
    continuation_parameters, planned_segment_parameters, validate_structured_timing,
    project_cut_lengths, first_changed_cut, connection_changed_from,
)
from .project_store import LongVideoStore, project_generation_inputs, edit_project, restore_project_plan
from .video_media import FFmpeg


def series_index(journal, run_id, backend):
    """One journal scan per series execution, keyed by its stable cut index."""
    indexed = {}
    for record in journal.records():
        ctx = record.get("context", {})
        if (record["backend"] == backend.rstrip("/") and ctx.get("long_run_id") == run_id
                and type(ctx.get("long_segment")) is int and record["state"] != "failed"):
            indexed.setdefault(ctx["long_segment"], []).append(record)
    for records in indexed.values():
        records.sort(key=lambda r: r["created_at"], reverse=True)
    return indexed


def series_records(journal, run_id, index, backend):
    return series_index(journal, run_id, backend).get(index, [])


def estimate_remaining(journal, manifest, config, start, plan, indexed=None):
    """Approximate outstanding generation waits, not LLM, downloads or joining."""
    try:
        workflow = config.get("workflows", {}).get(core.H3_I2V_ID, {})
        base = {**workflow.get("defaults", {}), **manifest["overrides"],
                **(manifest.get("first_parameters") or {})}
        inputs = []
        for i in range(start, len(plan)):
            matches = (indexed or {}).get(i, ())
            if matches and matches[0]["state"] in ("completed", "collected"):
                continue
            params = {**base, "frames": plan[i]}
            if i and params.get("h3_model") is not None:
                params["h3_model"] = continuation_model(params["h3_model"])
            inputs.append(params)
        return journal.timings.sequence(manifest["backend"], core.H3_I2V_ID, inputs)
    except TIMING_ERRORS:
        return None


def existing_result(journal, comfy, manifest, index, cancel_event, *, confirm_unknown=None, indexed=None):
    matches = (series_records(journal, manifest["run_id"], index, comfy.base) if indexed is None
               else [journal.read(row["job_id"]) for row in indexed.get(index, [])])
    matches = [row for row in matches if row["state"] != "failed"]
    if not matches:
        return None
    record = matches[0]
    if record["state"] in ("completed", "collected") and isinstance(record.get("outputs"), dict):
        info = {"outputs": record["outputs"], "status": record.get("comfy_status", {})}
        state = "completed"
    else:
        state, info = journal.inspect(comfy, record)
    if state in ("pending", "running"):
        try:
            info = comfy.wait(record["prompt_id"], cancel_event=cancel_event, cancel_remote=True)
        except JobCancellationRequested:
            journal.update(record["job_id"], state="cancel_requested")
            raise
        except JobExecutionFailed:
            journal.update(record["job_id"], state="failed")
            raise
        journal.update(record["job_id"], state="completed", outputs=info.get("outputs", {}),
                       comfy_status=info.get("status", {}))
    elif state == "failed":
        return None
    elif state == "unknown":
        if record["state"] == "cancel_requested":
            # The user explicitly resumed after a targeted cancel, and the
            # server has no running/pending job for this ID.
            journal.update(record["job_id"], state="failed", error="cancelled; no active job")
            return None
        if confirm_unknown is not None and confirm_unknown(record):
            if journal.abandon_unknown(comfy, record["job_id"]):
                return None
            raise core.OrchestratorError("ジョブの状態が変化したか、ComfyUIに実行・待機ジョブがあります。再度長尺再開してください")
        raise UnknownLongJob(record)
    return {"job_id": record["job_id"], "prompt_id": record["prompt_id"],
            "parameters": record["parameters"], "outputs": info.get("outputs", {})}


@lock_project
def run_long_video(store, manifest, config, config_path, journal, output_dir,
                   download, progress=None, cancel_event=None, prompt_cache=None, media=None,
                   confirm_unknown=None, join_only=False, auto_join=True, on_checkpoint=None):
    """Run/resume a series, or join saved cuts without connecting to ComfyUI."""
    media = media or FFmpeg()
    backend = config["comfyui"]["base_url"].rstrip("/")
    if not join_only and manifest["backend"] != backend:
        raise core.OrchestratorError("長尺生成の接続先が保存時と異なります")
    p = manifest["overrides"]
    core.validate_h3_video_parameters(p)
    if p.get("h3_model") is not None:
        continuation_model(p["h3_model"])
    plan, cut_frames, target_frames = manifest_schedule(manifest)
    windows = manifest_windows(manifest)
    overlap = manifest.get("overlap_frames", 0)
    if len(manifest["segments"]) > len(plan):
        raise core.OrchestratorError("長尺計画が不正です")
    prompt_plan = None
    if "prompt_plan" in manifest:
        prompt_plan = validate_prompt_plan(manifest["prompt_plan"], len(plan))
        validate_structured_timing(prompt_plan, windows, p, text_only=manifest["source"] is None)
    folder = store.folder(manifest["run_id"])
    source = store.source_asset(manifest)
    if source is None:
        if (not manifest["request"].strip() or prompt_plan is None or prompt_plan.get("format") != h3_prompt.FORMAT
                or core.h3_ref2va_filename(p.get("h3_model")) is not None):
            raise core.OrchestratorError("参照なし長尺プロジェクトの計画が不正です")
    elif not source.is_file():
        raise core.OrchestratorError("長尺生成の元画像がありません")
    if join_only and len(manifest["segments"]) != len(plan):
        raise core.OrchestratorError("全カット生成後に結合してください")
    comfy = None
    indexed = {}
    if not join_only:
        comfy = core.ComfyUI(config["comfyui"])
        comfy.extend_video_timeout(config["comfyui"])
        if len(manifest["segments"]) < len(plan):
            indexed = series_index(journal, manifest["run_id"], comfy.base)
            try:
                journal.timings.bootstrap(journal.root)
            except TIMING_ERRORS:
                pass
        if manifest["state"] == "draft":
            manifest["state"] = "generating"
            store.save(manifest)
            if on_checkpoint:
                on_checkpoint(manifest)
    clips = []
    for i, segment in enumerate(manifest["segments"]):
        check_cancel(cancel_event)
        clip = store.asset(manifest, segment["file"])
        info = media.probe(clip, cancel_event)
        _check_segment(info, p, plan[i])
        clips.append((clip, info))
    for i in range(len(clips), len(plan)):
        check_cancel(cancel_event)
        if progress:
            progress(f"長尺生成 {i + 1}/{len(plan)}")
            if overlap:
                w = windows[i]
                mode = (f"ガイド {w.get('guide_frames', 0)}f" if w.get("guide_frames", 0)
                        else "従来接続（ガイド長不足）" if i and overlap == GUIDE_CONNECTION_FRAMES
                        else f"助走 {w['trim_start_frames']}f")
                progress(f"カット{i + 1}: 採用 {w['output_frames']}f / {mode} / 生成 {plan[i]}f")
        report_estimate(estimate_remaining(journal, manifest, config, i, plan, indexed), label="残カット生成待ち")
        cut_started = time.monotonic()
        result = existing_result(journal, comfy, manifest, i, cancel_event,
                                 confirm_unknown=confirm_unknown, indexed=indexed)
        recovered = result is not None
        if result is None:
            if prompt_plan is not None:
                guide_count = windows[i].get("guide_frames", 0)
                # The previous raw clip may include both discarded opening
                # frames and a discarded tail. Anchor inside its kept window.
                scratch = tempfile.TemporaryDirectory(prefix="guide-", dir=folder) if guide_count else nullcontext(None)
                with scratch as temporary:
                    image = source
                    extra = {"text_only_h3": True} if i == 0 and source is None else {}
                    if i:
                        anchor_frames = continuation_anchor_count(windows[i - 1], windows[i])
                        if guide_count:
                            images = media.extract_guide_frames(clips[-1][0], anchor_frames - 1, guide_count,
                                                                Path(temporary), cancel_event)
                            if len(images) != guide_count:
                                raise core.OrchestratorError("H3ガイド画像数が計画と一致しません")
                            image = images[0]
                            extra["guide_images"] = tuple(images[1:])
                            if progress:
                                progress(f"カット{i + 1}: 前カットの採用末尾{guide_count}fを動画ガイドに使用")
                        else:
                            image = folder / f"anchor_{i:03d}.png"
                            if overlap and progress:
                                progress(f"カット{i + 1}: 前カットのフレーム {anchor_frames}（1始まり）を開始画像に使用")
                            media.last_frame(clips[-1][0], anchor_frames, image, cancel_event)
                    params = planned_segment_parameters(
                        manifest["first_parameters"] if i else p, prompt_plan, i, plan[i],
                        lead_in_frames=(windows[i]["trim_start_frames"]
                                        if overlap or prompt_plan.get("format") == h3_prompt.FORMAT else 0),
                        guide_frames=guide_count, kept_frames=windows[i]["output_frames"],
                        text_only=i == 0 and source is None,
                    )
                    if manifest.get("cut_seeds") is not None:
                        params["seed"] = manifest["cut_seeds"][i]
                    result = core.execute_saved(
                        config, config_path, core.H3_I2V_ID, params, reference_image=image,
                        progress=progress, cancel_event=cancel_event, job_journal=journal,
                        job_context={"long_run_id": manifest["run_id"], "long_segment": i,
                                     "request_text": manifest["request"], "prompt_profile": manifest["profile"]},
                        **extra,
                    )
            elif i == 0:
                image = source
                overrides = {**p, "frames": plan[i]}
                # A legacy unplanned run repeats segment zero's prose; keep
                # its original prompt contract rather than mixing H3 schemas.
                legacy_config = ({**config, "llm": {**config["llm"], "h3_prompt_format": h3_prompt.LEGACY}}
                                 if "llm" in config and h3_prompt.enabled(config["llm"]) else config)
                result = core.execute(
                    legacy_config, config_path, manifest["request"], image=image,
                    selected_workflow=core.H3_I2V_ID, overrides=overrides,
                    progress=progress, cancel_event=cancel_event, job_journal=journal,
                    job_context={"long_run_id": manifest["run_id"], "long_segment": i,
                                 "prompt_profile": manifest["profile"]},
                    prompt_cache=prompt_cache,
                )
            else:
                anchor = folder / f"anchor_{i:03d}.png"
                media.last_frame(clips[-1][0], clips[-1][1]["frames"], anchor, cancel_event)
                params = continuation_parameters(manifest["first_parameters"], i, plan[i])
                result = core.execute_saved(
                    config, config_path, core.H3_I2V_ID, params, reference_image=anchor,
                    progress=progress, cancel_event=cancel_event, job_journal=journal,
                    job_context={"long_run_id": manifest["run_id"], "long_segment": i,
                                 "request_text": manifest["request"], "prompt_profile": manifest["profile"]},
                )
        check_cancel(cancel_event)
        segment_folder = folder / f"segment_{i:03d}"
        segment_folder.mkdir(exist_ok=True)
        clip = Path(download(result, segment_folder)).resolve()
        if not clip.is_relative_to(segment_folder.resolve()):
            raise core.OrchestratorError("長尺区間の保存先が不正です")
        info = media.probe(clip, cancel_event)
        _check_segment(info, p, plan[i])
        if i == 0:
            manifest["first_parameters"] = result["parameters"]
        manifest["segments"].append({"file": clip.relative_to(folder).as_posix(),
                                     "job_id": result["job_id"], "prompt_id": result["prompt_id"],
                                     "parameters": result["parameters"], "frames": info["frames"],
                                     "cut_processing_seconds": round(time.monotonic() - cut_started, 3),
                                     "generation_wait_seconds": result.get("elapsed_seconds") if not recovered else None})
        if overlap == GUIDE_CONNECTION_FRAMES:
            manifest["segments"][-1]["guide_frames"] = windows[i].get("guide_frames", 0)
        store.save(manifest)
        journal.update(result["job_id"], state="collected", collection_state="collected")
        clips.append((clip, info))
        if on_checkpoint:
            on_checkpoint(manifest)
    check_cancel(cancel_event)
    report_estimate(None, label="結合・保存" if auto_join or join_only else "保存")
    if not auto_join and not join_only:
        if manifest["state"] != "completed":
            manifest["state"] = "ready_to_join"
            store.save(manifest)
            if on_checkpoint:
                on_checkpoint(manifest)
        return None, None
    output = Path(output_dir) / f"long_{manifest['run_id']}.mp4"
    if manifest["state"] != "completed" or not output.is_file():
        join_options = {"keep_frames": cut_frames} if cut_frames is not None else {}
        if overlap:
            join_options = {"keep_frames": [w["output_frames"] for w in windows],
                            "trim_start_frames": [w["trim_start_frames"] for w in windows]}
        join_started = time.monotonic()
        media.join(clips, target_frames, output, cancel_event, progress, **join_options)
        manifest["join_seconds"] = round(time.monotonic() - join_started, 3)
        manifest["state"] = "completed"
        store.save(manifest)
        if on_checkpoint:
            on_checkpoint(manifest)
    first = dict(manifest["first_parameters"])
    first.update(frames=target_frames, long_segment_frames=p["frames"],
                 long_seconds=manifest["seconds"], long_run_id=manifest["run_id"])
    if source is None:
        first["long_text_only"] = True
    if cut_frames is not None:
        first["long_cut_frames"] = cut_frames
    if overlap:
        first["long_overlap_frames"] = overlap
    if prompt_plan is not None:
        first["long_prompt_plan"] = prompt_plan
        first["long_base_overrides"] = dict(manifest["overrides"])
        first["long_backend"] = manifest["backend"]
        first["long_cut_seeds"] = [segment["parameters"]["seed"] for segment in manifest["segments"]]
    return {"status": "completed", "workflow_id": LONG_VIDEO_ID, "kind": "i2v",
            "parameters": first, "prompt_id": manifest["run_id"], "outputs": {}}, output


def _check_segment(info, p, frames):
    if (info["frames"] != frames or info["width"] != p["width"] or info["height"] != p["height"]
            or abs(info["fps"] - FPS) > 0.01):
        raise core.OrchestratorError(f"H3区間の実測情報が計画と異なります: {info} / {frames}f")
