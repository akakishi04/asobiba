"""Generation orchestration and compatibility API for fixed local workflows."""

from __future__ import annotations

import secrets
from pathlib import Path
from typing import Any, Callable


from .parameters import OrchestratorError, PARAMS, check_param
from . import image_prompts, camera_spec
from .model_profiles import ANIMA_ID
from .model_registry import model_filename
from .jobs import (JobJournal, JobCancellationRequested, JobExecutionFailed,
                   JobSubmissionRejected, run_job)
from .input_snapshot import freeze_generation_inputs
from .h3_guide import prepare_guide_workflow, validate_guide_inputs
from . import h3_prompt
from .generation_runtime import build_template, preflight, early_preflight, submit_prepared
from .model_runtime import release_comfy_before_llm, record_model_event
from .prompt_cache import PromptCache, CACHE_ERRORS, make_cache_key
from .h3 import (
    H3_MODELS,
    H3_TURBOS,
    H3_REF2VA_TURBOS,
    H3_MODEL_LABELS,
    H3_TURBO_LABELS,
    H3_ENCODERS,
    H3_ENCODER_LABELS,
    H3_CLIPPROJ_MATRIX,
    H3_OPTION_KEYS,
    H3_REF2VA_PREFIX,
    H3_REF2VA_LABEL,
    H3_HYBRID_FILES,
    H3_HYBRID_PREFIXES,
    H3_HYBRID_DEFAULT_STEPS,
    H3_PERFORMANCE_LABELS,
    H3_SOL_VAE,
    H3_REF2VA_DEFAULT_PROMPT,
    h3_hybrid_model_key,
    h3_hybrid_filename,
    validate_h3_hybrid_steps,
    h3_ref2va_model_key,
    h3_ref2va_filename,
    h3_model_label,
    h3_model_from_label,
    ensure_h3_reference_prompt,
    split_h3_options,
    prepare_h3_workflow,
    prepare_h3_text_workflow,
    h3_text_model_options,
)


# Public compatibility entry points. The implementation lives in the owner modules.
from .workflow_registry import (
    ALLOWED_KINDS,
    WAN_I2V_ID,
    H3_I2V_ID,
    HUNYUAN_I2V_ID,
    QWEN_T2I_ID,
    QWEN_LIGHTNING_ID,
    QWEN_IDS,
    SDXL_WORKFLOW_IDS,
    DEFAULT_SDXL_CHECKPOINT,
    HOST_VIDEO_IDS,
    VIDEO_KINDS,
    IMAGE_INPUTS,
    I2V_DEFAULT_PROMPT,
    supports_empty_i2v_request,
    needs_prompt_llm,
    sdxl_checkpoint_kind,
    split_checkpoint_option,
    prepare_checkpoint_workflow,
    installed_model_choices,
    supplied_inputs,
    compatible_workflows,
    validate_wan_video_parameters,
    validate_h3_video_parameters,
    validate_hunyuan_video_parameters,
    validate_video_parameters,
    load_workflow,
    plan_schema,
    validate_plan,
    render_workflow,
)
from .configuration import load_config
from .http_api import http_json, APIHTTPError, _open_json, _positive_number
from .comfy_client import ComfyUI, combo_choices
from .ollama_client import Ollama


@freeze_generation_inputs
def execute(
    config: dict, config_path: Path, request: str, image: Path | None = None,
    dry_run: bool = False, selected_workflow: str | None = None,
    overrides: dict | None = None, progress: Callable[[str], None] | None = None,
    cancel_event: Any = None, mask_image: Path | None = None, pose_image: Path | None = None,
    composition_image: Path | None = None,
    character_traits: str | None = None,
    job_journal: JobJournal | None = None, job_context: dict | None = None,
    prompt_cache: PromptCache | None = None,
    release_before_dry_run: bool = False,
) -> dict:
    """Interpret natural language, unload the chosen LLM, then run a fixed workflow.

    Journal-backed GUI jobs support targeted cancellation. Legacy callers without
    a journal keep the wait-only cancellation contract.
    """
    workflows = config["workflows"]
    if not workflows:
        raise OrchestratorError(
            "workflowsが空です。先にAPI形式JSONを配置してconfig.jsonへ登録してください"
        )
    # Still-image analysis settings do not apply to I2V. Preserve their
    # persistent configuration, but exclude them from this generation job.
    explicit_i2v = workflows.get(selected_workflow, {}).get("kind") == "i2v"
    text_only_h3 = selected_workflow == H3_I2V_ID and explicit_i2v and image is None
    registered_h3 = workflows[selected_workflow] if text_only_h3 else None
    if text_only_h3:
        # Only an explicit H3 selection enables this route. Never auto-select
        # a costly video when ordinary text-to-image was requested.
        if IMAGE_INPUTS.intersection(registered_h3["bindings"]) != {"image"}:
            raise OrchestratorError("参照画像なしのH3生成には標準のH3ワークフローが必要です")
        if not request.strip():
            raise OrchestratorError("参照画像なしのH3生成には自然文が必要です")
        if config.get("llm", {}).get("provider", "lmstudio") != "lmstudio" or "llm" not in config:
            raise OrchestratorError("H3 T2VAはLM Studio接続を使用してください")
        overrides = h3_text_model_options(overrides)
    if explicit_i2v:
        composition_image = None
        character_traits = None
    empty_request = not request.strip()
    if empty_request and not supports_empty_i2v_request(
        config, selected_workflow, image, mask_image, pose_image, composition_image,
    ):
        raise OrchestratorError("自然文の指示を入力してください（I2Vの参照画像のみ指定時は省略できます）")
    use_prompt_llm = needs_prompt_llm(
        config, request, character_traits, composition_image, workflow_id=selected_workflow,
    )
    if character_traits is not None:
        from .character_refs import normalize_approved
        character_traits = normalize_approved(character_traits)
    for field, path_value in (
        ("参照画像", image), ("マスク", mask_image), ("ポーズ画像", pose_image),
        ("構図参考画像", composition_image),
    ):
        if path_value is not None and not Path(path_value).is_file():
            raise OrchestratorError(f"{field}が見つかりません: {path_value}")
    if image is not None:
        image = Path(image).resolve()
    if mask_image is not None:
        mask_image = Path(mask_image).resolve()
    if pose_image is not None:
        pose_image = Path(pose_image).resolve()
    if composition_image is not None:
        composition_image = Path(composition_image).resolve()
        if not config.get("llm", {}).get("send_reference_to_llm", False):
            raise OrchestratorError(
                "構図参考画像をLLMで解析するには「画像をLLMで構図解析」をONにしてください"
            )

    # Filter by exact required image sources before asking the LLM.
    # This prevents the LLM from choosing T2I when the user supplied an I2I
    # reference, or choosing I2I with no image to upload.
    if selected_workflow is not None:
        if selected_workflow not in workflows:
            raise OrchestratorError(f"登録されていないワークフローです: {selected_workflow}")
        workflows = {selected_workflow: workflows[selected_workflow]}
    if text_only_h3:
        workflows = {H3_I2V_ID: {**registered_h3,
                     "description": "MiniMax H3 native text-to-video and audio; no reference assets.",
                     "bindings": {k: v for k, v in registered_h3["bindings"].items() if k != "image"}}}
    workflows = compatible_workflows(workflows, image, mask_image, pose_image)
    if selected_workflow is None:
        # Ordinary image generation must never switch into a costly video job.
        still = {key: entry for key, entry in workflows.items()
                 if entry.get("kind") not in VIDEO_KINDS and key not in QWEN_IDS and key != ANIMA_ID}
        if still:
            workflows = still
    if not workflows:
        if selected_workflow is not None:
            raise OrchestratorError(
                f"{selected_workflow} と参照画像・マスク・ポーズ画像の指定が一致しません"
            )
        raise OrchestratorError(
            "指定された入力に対応するワークフローが未登録です。"
            "T2Iは入力画像なし、I2Iは参照画像、部分修正は画像とマスク、"
            "ポーズ生成はポーズ画像を指定してください"
        )

    i2v_only = all(entry.get("kind") == "i2v" for entry in workflows.values())

    def note(message: str) -> None:
        if progress:
            progress(message)

    def check_cancelled() -> None:
        if cancel_event is not None and cancel_event.is_set():
            raise OrchestratorError("生成開始前に処理を中止しました")

    overrides, camera = camera_spec.split(overrides or {}, workflows)
    if camera and any(k in overrides for k in image_prompts.FIELDS):
        raise OrchestratorError("カメラ設定と直接プロンプト上書きは併用できません")
    if camera and config.get("llm", {}).get("provider", "lmstudio") != "lmstudio":
        raise OrchestratorError("カメラ設定はLM Studio接続を使用してください")
    overrides, h3_options = split_h3_options(
        overrides, enabled=set(workflows) == {H3_I2V_ID},
    )
    reference_only = h3_ref2va_filename(h3_options.get("h3_model")) is not None
    if h3_hybrid_filename(h3_options.get("h3_model")) is not None:
        overrides.setdefault("steps", H3_HYBRID_DEFAULT_STEPS)
        validate_h3_hybrid_steps(overrides["steps"], h3_options.get("h3_performance", "standard"))
    if h3_options:
        fixed_steps = H3_TURBOS[h3_options["h3_turbo"]][1]
        if fixed_steps is not None:
            overrides["steps"] = fixed_steps
    overrides, checkpoint_options = split_checkpoint_option(overrides, workflows)
    if sdxl_checkpoint_kind(checkpoint_options.get("checkpoint_model", "")) == "turbo":
        overrides.update(steps=4, cfg=1)
    if set(workflows) == {QWEN_LIGHTNING_ID}:
        overrides.update(steps=4, cfg=1)
    check_cancelled()
    comfy = ComfyUI(config["comfyui"])
    if not dry_run:
        if text_only_h3:
            effective = {**registered_h3.get("defaults", {}), **overrides}
            checked = build_template(config_path, registered_h3, H3_I2V_ID, effective,
                                     h3_options, checkpoint_options, final=True)
            checked = prepare_h3_text_workflow(checked, registered_h3["bindings"])
            preflight(comfy, config, H3_I2V_ID, workflows[H3_I2V_ID], checked, checkpoint_options)
        else:
            early_preflight(comfy, config, config_path, workflows, overrides, h3_options,
                            checkpoint_options, cancel_event)
    llm_key = "llm" if "llm" in config else "ollama"
    settings = config[llm_key]
    if camera:
        if llm_key != "llm":
            raise OrchestratorError("カメラ設定はLM Studio接続を使用してください")
        settings = {**settings, "_camera_spec": camera}
        note("カメラ設定: " + camera_spec.summary(camera))
    if text_only_h3:
        settings = {**settings, "h3_prompt_format": h3_prompt.FORMAT, "_h3_text_only": True,
                    "send_reference_to_llm": False}
    official_h3 = (set(workflows) == {H3_I2V_ID} and h3_prompt.enabled(settings)
                   and settings.get("provider", "lmstudio" if llm_key == "llm" else "ollama") == "lmstudio")
    cache_key = None
    cached_plan = None
    if use_prompt_llm and prompt_cache is not None:
        try:
            # Seed, resolution and sampler choices are host-owned. H3 duration
            # and the I2I denoise hint do affect the interpreter.
            hints = {"i2v_only": i2v_only, "reference_only": reference_only,
                     "text_only_h3": text_only_h3,
                     "frames": overrides.get("frames") if H3_I2V_ID in workflows else None,
                     "denoise": overrides.get("denoise")}
            if official_h3:
                sources = {"image": image} if settings.get("h3_reference_vision", True) else {}
            else:
                sources = {} if i2v_only else {"image": image, "pose": pose_image,
                                               "mask": mask_image, "composition": composition_image}
            cache_key = make_cache_key(request, settings, workflows, hints, sources, character_traits)
            cached_plan = prompt_cache.get(cache_key)
        except CACHE_ERRORS as exc:
            note(f"解釈キャッシュ読込失敗（通常処理を継続）: {exc}")
        if cached_plan is not None:
            try:
                _, checked_params = validate_plan(image_prompts.split_plan(cached_plan, workflows)[0], workflows, image is not None)
                if text_only_h3:
                    effective_frames = overrides.get("frames", checked_params.get("frames"))
                    check_param("frames", effective_frames)
                    h3_prompt.validate_text_prompt(checked_params["positive_prompt"], effective_frames)
            except OrchestratorError:
                cached_plan = None
    if use_prompt_llm and cached_plan is None:
        release_comfy_before_llm(config["comfyui"], comfy=comfy, progress=note,
                                 enabled=not dry_run or release_before_dry_run)
    elif not dry_run and (not use_prompt_llm or cached_plan is not None):
        record_model_event("comfy_preserve_jobs")
        note("ComfyUI: LLMを使用しないためモデルキャッシュを維持")
    check_cancelled()

    if i2v_only:
        settings = {**settings, "send_reference_to_llm": False}
    if reference_only:
        settings = {**settings, "_h3_reference_only": True}
        # Keep the existing binding schema and ID; only replace the job's
        # descriptive catalog so the LLM sees the actual conditioning mode.
        workflows = {key: {**entry, "description":
                           "MiniMax H3 Ref2VA: reference image <Picture 1> is a visual guide, "
                           "not an initial frame. Generate the requested new scene and motion with "
                           "independent framing and synchronized audio."}
                     for key, entry in workflows.items()}
    provider = settings.get("provider", "lmstudio" if llm_key == "llm" else "ollama")
    if cached_plan is not None:
        note("LLM: 解釈キャッシュを使用")
        plan = cached_plan
    elif not use_prompt_llm:
        # The image is the primary conditioning; avoid a needless LLM load.
        note("I2V: 参照画像のみ（LLMを使用しません）")
        default_prompt = H3_REF2VA_DEFAULT_PROMPT if reference_only else I2V_DEFAULT_PROMPT
        if official_h3:
            default_prompt = h3_prompt.compile_prompt(h3_prompt.default_sections(reference_only), reference_only)
        plan = {"workflow_id": selected_workflow, "parameters": {"positive_prompt": default_prompt}}
    elif provider == "lmstudio":
        from .lmstudio import LMStudio
        from .prompt_profiles import is_i2i_context
        # An edit-strength hint is provided to the prompt designer only.
        # Keep it out of config.json, the LLM output schema and ComfyUI nodes.
        if is_i2i_context(workflows):
            settings = dict(settings)
            if len(workflows) == 1:
                edit_workflow = next(iter(workflows.values()))
                effective_denoise = (overrides or {}).get(
                    "denoise", edit_workflow.get("defaults", {}).get("denoise")
                )
                if effective_denoise is not None:
                    check_param("denoise", effective_denoise)
                    settings["_edit_denoise"] = float(effective_denoise)
        if set(workflows) == {H3_I2V_ID}:
            settings = dict(settings)
            h3 = workflows[H3_I2V_ID]
            frames = (overrides or {}).get("frames", h3.get("defaults", {}).get("frames", 124))
            check_param("frames", frames)
            settings["_h3_duration_seconds"] = frames / 24
        # A pose reference is also a valid vision input. The VLM receives the
        # same image used by pose ControlNet, while ComfyUI still receives it
        # through the separate "pose" binding. In I2I, prefer the source image.
        vision_reference = (
            image if official_h3 else None if i2v_only else
            composition_image if composition_image is not None else
            image if image is not None else pose_image
        )
        # Keep the existing call signature unchanged without a confirmed
        # character sheet; offline mocks and older integrations still work.
        extra = {"character_traits": character_traits} if character_traits and not i2v_only else {}
        if composition_image is not None and not i2v_only:
            plan = LMStudio(settings).interpret(
                request, workflows, vision_reference, progress=note,
                reference_role="composition", **extra,
            )
        else:
            plan = LMStudio(settings).interpret(
                request, workflows, vision_reference, progress=note, **extra,
            )
    else:
        if composition_image is not None and not i2v_only:
            raise OrchestratorError("LLM専用の構図参考画像は現在LM Studio接続で利用してください")
        note("Ollama: 自然文を解釈しモデルをアンロード")
        plan = Ollama(settings).interpret(request, workflows, None if i2v_only else image)
    check_cancelled()
    # Treat an LLM-proposed seed as untrusted and ignore it, even if the model
    # disregards the schema. An explicit GUI/CLI override always takes priority.
    if isinstance(plan, dict) and isinstance(plan.get("parameters"), dict):
        if "seed" in plan["parameters"]:
            note("LLMが返したSeedは使用せず、GUI指定または乱数で設定します")
        plan = {**plan, "parameters": {k: v for k, v in plan["parameters"].items() if k != "seed"}}
    if bool(workflows) and workflows.keys() <= HOST_VIDEO_IDS and isinstance(plan, dict) and isinstance(plan.get("parameters"), dict):
        # Video dimensions, length, FPS and sampler settings belong to the host.
        plan = {**plan, "parameters": {
            k: v for k, v in plan["parameters"].items()
            if k in ("positive_prompt", "negative_prompt")
            and any(k in e["bindings"] for e in workflows.values())
        }}
    clean_plan, alternate = image_prompts.split_plan(plan, workflows)
    workflow_id, params = validate_plan(clean_plan, workflows, image is not None)
    if camera:
        fmt = image_prompts.prompt_format(workflow_id)
        params = camera_spec.apply_pair(params, camera, fmt)
        if alternate is not None:
            try:
                alternate = camera_spec.apply_pair(image_prompts.pair(alternate), camera,
                                                   image_prompts.other_format(fmt))
            except OrchestratorError as exc:
                note("別形式へのカメラ指定を適用できません: " + str(exc))
                alternate = None
    original_prompts = {key: params.get(key) for key in image_prompts.FIELDS}
    selection = workflows[workflow_id]
    if overrides:
        for name, value in overrides.items():
            if name not in selection["bindings"] or name in IMAGE_INPUTS:
                raise OrchestratorError(f"指定したワークフローでは {name} を変更できません")
            check_param(name, value)
            params[name] = value
    if "seed" in selection["bindings"] and (not overrides or "seed" not in overrides):
        # Seed empty in the GUI => an independent reproducible 32-bit seed.
        # Never silently inherit the fixed seed from the template JSON.
        params["seed"] = secrets.randbits(32)
    if reference_only:
        params["positive_prompt"] = ensure_h3_reference_prompt(params["positive_prompt"])
    if text_only_h3:
        # Cache hits and LLM replies must satisfy the same no-reference contract.
        params["positive_prompt"] = h3_prompt.validate_text_prompt(params["positive_prompt"], params["frames"])
    template = build_template(config_path, registered_h3 if text_only_h3 else selection,
                              workflow_id, params, h3_options, checkpoint_options, final=True)
    if text_only_h3:
        template = prepare_h3_text_workflow(template, registered_h3["bindings"])
        note("H3 T2VA: 参照画像なし")
    if h3_options:
        note("H3: " + h3_model_label(h3_options["h3_model"])
             + " / Turbo " + H3_TURBO_LABELS[h3_options["h3_turbo"]]
             + f" / {params['steps']} Steps"
             + (f" / Text encoder={h3_options['h3_encoder_device']}" if "h3_encoder_device" in h3_options else "")
             + (f" / TE model={H3_ENCODER_LABELS[h3_options['h3_encoder_model']]}" if "h3_encoder_model" in h3_options else ""))
    if checkpoint_options:
        note("画像モデル: " + model_filename(checkpoint_options["checkpoint_model"]))
    saved_params = {**params, **h3_options, **checkpoint_options}
    if camera:
        saved_params[camera_spec.KEY] = camera
    if image_prompts.supports_plan(workflows) and provider == "lmstudio":
        if alternate is not None and all(params.get(key) == value for key, value in original_prompts.items()):
            try:
                bundle_params = image_prompts.bind_bundle(workflow_id, params, alternate)
            except OrchestratorError as exc:
                # A valid standalone alternative can still be retained if the
                # combined conditioning exceeds the execution text limit.
                try:
                    saved_params[image_prompts.KEY] = image_prompts.make_bundle(workflow_id, params, alternate)
                except OrchestratorError:
                    note("別形式プロンプトを保存できません（実行用は保持）: " + str(exc))
                else:
                    note("Anima混合プロンプトを構成できません（タグ形式で生成）: " + str(exc))
            else:
                params = {key: value for key, value in bundle_params.items() if key != image_prompts.KEY}
                saved_params.update(bundle_params)
                if image_prompts.is_mixed(bundle_params):
                    note("Anima: タグ＋自然文の混合プロンプトを使用")
        else:
            note("別形式プロンプトは未取得または直接上書きされたため未保存")
    if text_only_h3:
        saved_params["text_only_h3"] = True
    if cache_key is not None and cached_plan is None:
        try:
            prompt_cache.put(cache_key, plan)
        except CACHE_ERRORS as exc:
            note(f"解釈キャッシュ保存失敗（通常処理を継続）: {exc}")
    note(f"ワークフロー確定: {workflow_id}")
    if dry_run:
        return {"status": "dry_run", "workflow_id": workflow_id, "parameters": saved_params}

    return submit_prepared(
        comfy, workflow_id, selection, template, params, saved_params,
        reference_image=image, mask_image=mask_image, pose_image=pose_image,
        progress=note, cancel_event=cancel_event, journal=job_journal,
        context={**(job_context or {}), "request_text": request, "composition_image": composition_image,
                 **({"text_only_h3": True} if text_only_h3 else {})},
    )


@freeze_generation_inputs
def execute_saved(
    config: dict, config_path: Path, workflow_id: str, parameters: dict,
    reference_image: Path | None = None, new_seed: bool = False,
    progress: Callable[[str], None] | None = None, cancel_event: Any = None,
    mask_image: Path | None = None, pose_image: Path | None = None,
    job_journal: JobJournal | None = None, job_context: dict | None = None,
    guide_images=(), text_only_h3=False,
) -> dict:
    """Replay exact validated workflow inputs, without invoking or loading an LLM.

    With new_seed=True only seed changes; for exact replay the original seed
    and prompts are reused byte-for-byte. Does not stop other ComfyUI jobs.
    """
    if workflow_id not in config["workflows"]:
        raise OrchestratorError(f"保存されたワークフローが未登録です: {workflow_id}")
    if not isinstance(parameters, dict):
        raise OrchestratorError("保存された生成パラメータが不正です")
    parameters, camera = camera_spec.split(parameters, {workflow_id})
    parameters, image_bundle = image_prompts.split_saved(parameters, workflow_id)
    # A host-owned explicit marker is persisted for single-clip replay. Older
    # long-project callers still use their separate text_only_h3 argument.
    saved_text_mode = "text_only_h3" in parameters
    if saved_text_mode:
        if parameters.pop("text_only_h3") is not True:
            raise OrchestratorError("保存されたH3参照なしモードが不正です")
        text_only_h3 = True
    registered = config["workflows"][workflow_id]
    selected = registered
    if text_only_h3:
        if (workflow_id != H3_I2V_ID or reference_image is not None
                or mask_image is not None or pose_image is not None or guide_images
                or "image" not in registered["bindings"]):
            raise OrchestratorError("画像なし生成はH3の参照なしモード専用です")
        # Validate and render against a derived binding set, but load the
        # registered graph normally before removing its image condition.
        selected = {**registered, "bindings": {
            k: v for k, v in registered["bindings"].items() if k != "image"
        }}
    bindings = selected["bindings"]
    required = IMAGE_INPUTS.intersection(bindings)
    if required != supplied_inputs(reference_image, mask_image, pose_image):
        raise OrchestratorError("再生成に必要な参照画像・マスク・ポーズ画像が揃っていません")
    for field, value in (("参照画像", reference_image), ("マスク", mask_image), ("ポーズ画像", pose_image)):
        if value is not None and not Path(value).is_file():
            raise OrchestratorError(f"{field}がありません: {value}")
    guide_images = validate_guide_inputs(guide_images)
    if guide_images and (workflow_id != H3_I2V_ID or reference_image is None):
        raise OrchestratorError("動画ガイドはMiniMax H3の開始画像付き生成専用です")
    for guide in guide_images:
        if not Path(guide).is_file():
            raise OrchestratorError(f"H3ガイド画像がありません: {guide}")
    has_image = reference_image is not None
    if "seed" in bindings and not new_seed and "seed" not in parameters:
        raise OrchestratorError("元のSeedが履歴にありません。同条件の再生成はできません")

    copied, h3_options = split_h3_options(parameters, enabled=workflow_id == H3_I2V_ID)
    copied, checkpoint_options = split_checkpoint_option(copied, {workflow_id})
    fixed_turbo = sdxl_checkpoint_kind(checkpoint_options.get("checkpoint_model", "")) == "turbo"
    if fixed_turbo or workflow_id == QWEN_LIGHTNING_ID:
        if copied.get("steps") != 4 or copied.get("cfg") != 1:
            raise OrchestratorError("高速蒸留モデルの履歴には4 Steps、CFG 1が必要です")
    if new_seed and "seed" in bindings:
        copied["seed"] = secrets.randbits(32)
    workflow_id, params = validate_plan(
        {"workflow_id": workflow_id, "parameters": copied},
        {workflow_id: selected}, has_image,
    )
    template = build_template(config_path, registered, workflow_id, params, h3_options,
                              checkpoint_options, final=True)
    if text_only_h3:
        if saved_text_mode:
            # Only newly saved standalone prompts require the official
            # validator; preserve old long-project replay byte-for-byte.
            canonical = h3_prompt.validate_text_prompt(params["positive_prompt"], params["frames"])
            if canonical != params["positive_prompt"]:
                raise OrchestratorError("保存されたH3 T2VAプロンプトの形式が不正です")
        template = prepare_h3_text_workflow(template, registered["bindings"])
    if cancel_event is not None and cancel_event.is_set():
        raise OrchestratorError("再生成開始前に中止しました")

    comfy = ComfyUI(config["comfyui"])
    checked = (prepare_guide_workflow(template, ["guide.png"] * len(guide_images))
               if guide_images else template)
    preflight(comfy, config, workflow_id, selected, checked, checkpoint_options)
    record_model_event("comfy_preserve_jobs")
    if progress:
        progress("保存済みのプロンプトと生成設定を復元（LLMは使用しません）")
        if text_only_h3:
            progress("H3 T2VA: 参照画像を使用せず生成")
    if text_only_h3:
        job_context = {**(job_context or {}), "text_only_h3": True}
    return submit_prepared(
        comfy, workflow_id, selected, template, params,
        {**params, **h3_options, **checkpoint_options, **({"text_only_h3": True} if saved_text_mode else {}),
         **({image_prompts.KEY: image_bundle} if image_bundle is not None else {}),
         **({camera_spec.KEY: camera} if camera else {})},
        reference_image=reference_image, mask_image=mask_image, pose_image=pose_image,
        progress=progress, cancel_event=cancel_event, journal=job_journal, context=job_context,
        guide_images=guide_images,
    )
