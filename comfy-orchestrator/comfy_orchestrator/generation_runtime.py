"""Shared workflow preparation, preflight and submission for all generation paths.

The public core entry points retain their API. No GUI or LLM inference here.
"""
from __future__ import annotations

from pathlib import Path

from .parameters import OrchestratorError
from .model_profiles import ANIMA_ID
from .h3_guide import prepare_guide_workflow, validate_guide_inputs, GUIDE_LENGTHS
from .h3 import prepare_h3_workflow, split_h3_options, prepare_h3_text_workflow
from .workflow_registry import (H3_I2V_ID, QWEN_IDS, VIDEO_KINDS, validate_video_parameters,
                                validate_h3_video_parameters, load_workflow, render_workflow,
                                prepare_checkpoint_workflow)
from .comfy_client import ComfyUI
from .long_video_plan import continuation_model
from .jobs import run_job


def check_cancel(cancel_event, message="生成開始前に処理を中止しました"):
    if cancel_event is not None and cancel_event.is_set():
        raise OrchestratorError(message)


def build_template(config_path, entry, workflow_id, parameters, h3_options, checkpoint_options,
                   *, final=False):

    if final:
        validate_video_parameters(workflow_id, parameters)
        if workflow_id in QWEN_IDS and any(parameters[name] % 16 for name in ("width", "height")):
            raise OrchestratorError("Qwen-Imageの幅・高さは16の倍数にしてください")
    base = Path(config_path).resolve().parent
    path = (base / entry["file"]).resolve()
    if not path.is_relative_to(base):
        raise OrchestratorError("ワークフローは設定ファイルのフォルダ内を指定してください")
    template = load_workflow(path, entry["bindings"])
    if h3_options:
        template = prepare_h3_workflow(template, h3_options, parameters)
    return prepare_checkpoint_workflow(template, checkpoint_options)


def preflight(comfy, config, workflow_id, entry, template, checkpoint_options):
    """One dependency policy for new generation, replay and long-video cuts."""

    kind = entry.get("kind")
    if kind == "pose":
        comfy.ensure_pose_dependencies(template)
    if kind in VIDEO_KINDS or workflow_id in QWEN_IDS or workflow_id == ANIMA_ID or checkpoint_options:
        comfy.ensure_video_dependencies(template)
    if kind in VIDEO_KINDS:
        comfy.extend_video_timeout(config["comfyui"])


def early_preflight(comfy, config, config_path, workflows, parameters, h3_options, checkpoint_options,
                    cancel_event=None):
    """Check known model/node dependencies before loading an LLM."""

    for workflow_id, entry in workflows.items():
        check_cancel(cancel_event)
        effective = {**entry.get("defaults", {}), **parameters}
        template = build_template(config_path, entry, workflow_id, effective,
                                  h3_options, checkpoint_options)
        preflight(comfy, config, workflow_id, entry, template, checkpoint_options)


def preflight_long(config, config_path, overrides, frames, *, cancel_event=None, guide_frame_count=0,
                   text_only_h3=False):
    """Check both H3 reference modes before generating a lengthy prompt plan."""

    entry = config["workflows"][H3_I2V_ID]
    params, options = split_h3_options(overrides, enabled=True)
    defaults = entry.get("defaults", {})
    sizes = list(frames)
    if not sizes:
        raise OrchestratorError("長尺区間がありません")
    for count in sizes:
        validate_h3_video_parameters({**defaults, **params, "frames": count})
    comfy = ComfyUI(config["comfyui"])
    first = options.get("h3_model")
    variants = [options]
    if first is not None:
        following = continuation_model(first)
        if following != first:
            variants.append({**options, "h3_model": following})
    for variant in variants:
        check_cancel(cancel_event)
        effective = {**defaults, **params, "frames": max(sizes)}
        template = build_template(config_path, entry, H3_I2V_ID, effective, variant, {}, final=True)
        preflight(comfy, config, H3_I2V_ID, entry, template, {})
    if text_only_h3:
        check_cancel(cancel_event)
        effective = {**defaults, **params, "frames": sizes[0]}
        template = build_template(config_path, entry, H3_I2V_ID, effective, variants[0], {}, final=True)
        preflight(comfy, config, H3_I2V_ID, entry,
                  prepare_h3_text_workflow(template, entry["bindings"]), {})
    if guide_frame_count:
        if guide_frame_count not in GUIDE_LENGTHS:
            raise OrchestratorError("長尺ガイドの長さが不正です")
        check_cancel(cancel_event)
        following = variants[-1]
        effective = {**defaults, **params, "frames": max(sizes)}
        template = build_template(config_path, entry, H3_I2V_ID, effective, following, {}, final=True)
        guided = prepare_guide_workflow(template, ["guide.png"] * (guide_frame_count - 1))
        preflight(comfy, config, H3_I2V_ID, entry, guided, {})


def submit_prepared(comfy, workflow_id, entry, template, parameters, saved_parameters, *,
                    reference_image=None, mask_image=None, pose_image=None,
                    progress=None, cancel_event=None, journal=None, context=None, guide_images=()):
    """Exactly one upload/render/journal/submit/wait path, with no LLM calls."""

    guide_images = validate_guide_inputs(guide_images)
    if guide_images and (workflow_id != H3_I2V_ID or reference_image is None):
        raise OrchestratorError("H3ガイドには開始画像が必要です")
    uploaded = []
    for source in (reference_image, mask_image, pose_image):
        check_cancel(cancel_event)
        uploaded.append(comfy.upload_image(source) if source is not None else None)
    rendered = render_workflow(template, entry["bindings"], parameters, *uploaded)
    if guide_images:
        names = []
        for source in guide_images:
            check_cancel(cancel_event)
            names.append(comfy.upload_image(source))
        rendered = prepare_guide_workflow(rendered, names)
        if progress:
            progress(f"ComfyUI: {len(names) + 1}fの動画ガイドを設定")
    check_cancel(cancel_event)
    if progress:
        progress("ComfyUI: キューに投入")
    job_context = {**(context or {}), "reference_image": reference_image,
                   "mask_image": mask_image, "pose_image": pose_image}
    if guide_images:
        job_context["guide_images"] = guide_images
    prompt_id, history, job_info = run_job(
        comfy, rendered, workflow_id, entry["kind"], saved_parameters,
        progress=progress, cancel_event=cancel_event, journal=journal, context=job_context,
    )
    if progress:
        progress("ComfyUI: 生成完了")
    return {"status": "completed", "workflow_id": workflow_id, "parameters": saved_parameters,
            **job_info, "prompt_id": prompt_id, "outputs": history.get("outputs", {}),
            "comfy_status": history.get("status", {})}
