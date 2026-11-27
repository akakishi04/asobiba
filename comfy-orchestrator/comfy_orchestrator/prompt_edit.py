"""Context-aware long-video prompt rewriting and Japanese-to-English editing."""
from __future__ import annotations

import copy
import json

from . import h3_prompt as hp
from .prompt_inference import check_cancel, request_validated
from .parameters import OrchestratorError, check_param
# Retain the previous review imports as a compatibility entry point.
from .prompt_review import (TranslationCache, protect, restore, TOKEN, prepare_plan_review,
                            JA_FIELDS, TRANSLATION_POLICY, PROTECTED, VERSION,
                            TRANSLATION_CACHE_LIMIT, _translate, translate_pending, ReviewInterrupted)


def cut_context(manifest, plan, cuts, index):
    """Use the executed preceding prompt only when that prefix is still valid."""
    from .long_video_plan import first_changed_cut, project_cut_lengths, schedule_windows
    from . import core
    from .timeline import validate_cut_frames
    if not 0 <= index < len(cuts) or len(plan["segments"]) != len(cuts):
        raise OrchestratorError("カット番号が不正です")
    old_cuts = project_cut_lengths(manifest)
    same = cuts == old_cuts
    if not same:
        validate_cut_frames(cuts)
    windows = schedule_windows(manifest["seconds"] if same else sum(cuts) / 24,
                               manifest["overrides"]["frames"],
                               manifest.get("cut_frames") if same else cuts,
                               overlap_frames=manifest.get("overlap_frames", 0))
    changed = first_changed_cut(manifest, plan, cuts)
    previous = plan["segments"][index-1] if index else ""
    origin = "planned" if previous else "none"
    if index and (changed is None or changed >= index) and len(manifest["segments"]) >= index:
        actual = manifest["segments"][index-1].get("parameters", {}).get("positive_prompt")
        if isinstance(actual, str) and actual.strip():
            previous, origin = actual, "executed_prompt"
    ref = index == 0 and core.h3_ref2va_filename(manifest["overrides"].get("h3_model")) is not None
    w = windows[index]
    return {
        "original_request": manifest["request"], "common": plan["common"],
        "previous_cut_prompt": previous, "previous_prompt_source": origin,
        "current_cut_prompt": plan["segments"][index],
        "next_cut_prompt": plan["segments"][index+1] if index+1 < len(cuts) else "",
        "cut": index + 1, "retained_seconds": cuts[index] / 24,
        "retained_frames": cuts[index], "guide_frames": w.get("guide_frames", 0),
        "trim_frames": w["trim_start_frames"], "reference_only": ref,
        "text_only": index == 0 and manifest["source"] is None,
    }


def _check_common(text, official):
    if not isinstance(text, str) or len(text.strip()) > 1600:
        raise OrchestratorError("共通プロンプトは1600文字以内です")
    return hp.validate_common(text) if official else text.strip()


def _compile_cut(value, official, context, common):
    if official:
        ref = context["reference_only"]
        fields = hp.validate_sections(value, ref, kept_frames=context["retained_frames"],
                                      later_cut=context["cut"] > 1)
        hp.compile_prompt(fields, ref, common=common, kept_frames=context["retained_frames"],
                          trim_frames=context["trim_frames"], guide_frames=context["guide_frames"],
                          later_cut=context["cut"] > 1, text_only=context.get("text_only", False))
        text = hp.section_text(fields, ref)
        if len(text) > 5000:
            raise OrchestratorError("H3カットのプロンプトが長すぎます")
        return text
    if set(value) != {"text"} or not isinstance(value["text"], str):
        raise OrchestratorError("旧形式のカットは自然文で指定してください")
    text = value["text"].strip()
    if not text or len(text) > 1600:
        raise OrchestratorError("旧形式のカットは1～1600文字です")
    check_param("positive_prompt", " ".join((common, text)))
    return text


def _english_common(client, instance, japanese, official, progress, cancel_event):
    if not japanese.strip():
        return ""
    def validate(value):
        if set(value) != {"text"}:
            raise OrchestratorError("共通プロンプトの翻訳形式が不正です")
        return _check_common(value["text"], official)
    return request_validated(client, instance,
                     "Translate the edited Japanese text faithfully into natural English. "
                     "Preserve all constraints and user edits; add no events, labels or details. "
                     "Return only persistent common conditions, not individual cut actions.",
                     japanese, hp.object_schema(("text",), {"text": 1600}),
                     "h3_common_from_japanese", validate, progress, cancel_event,
                     translation_chars=len(japanese))


def _english_cut(client, instance, context, common, official, operation, japanese, instruction,
                 progress, cancel_event, style=""):
    if operation == "apply":
        system = (
            "Translate the edited Japanese cut into English faithfully, retaining all its visual, "
            "camera, motion, timing and audio conditions and exact spoken/visible text. "
            "Do not re-plan, invent or delete actions. The Japanese section headings are editorial guides. "
            "The previous English prompt is context only; the edited Japanese is authoritative."
        )
        payload = {**context, "edited_japanese": japanese}
    else:
        system = (
            "Rewrite ONLY the selected cut as a physically coherent continuation. Infer the "
            "preceding end state from the previous cut prompt, not from observed video. "
            "Preserve object identity, color, shape, position, hand contacts and clothing; "
            "describe how the body and objects interact and transition through actual movement. "
            "If an important object was outside the frame, bring it into view coherently rather "
            "than conjuring another object. Avoid resetting pose, repeating prior actions or speech, "
            "and unnecessary events. Preserve the intended next cut's starting state where feasible. "
            "Use the existing selected cut's intended action unless the user's repair instruction changes it. "
            "Do not rewrite the common prompt or any neighboring cut. Fit action to the retained duration."
        )
        payload = {**context, "repair_instruction": instruction}
    if operation == "regenerate" and style:
        system += "\nRendering/motion preset (user instructions take priority):\n" + style
    if official:
        ref = context["reference_only"]
        system += "\n" + hp.POLICY + "\n" + (
            hp.T2VA_POLICY if context.get("text_only") else hp.REF_POLICY if ref else hp.BASE_POLICY
        )
        if context["cut"] > 1:
            system += "\nUse three base fields and no Picture/Subject/Video/Audio labels. The host adds continuity and shifts cut-local times."
        schema = hp.schema(ref)
    else:
        system += (
            "\nReturn a single concise natural English text field, without H3 section headings or "
            "technical settings. This project retains its legacy prompt format."
        )
        schema = hp.object_schema(("text",), {"text": 1600})
    return request_validated(client, instance, system, json.dumps(payload, ensure_ascii=False),
                     schema, "h3_cut_from_japanese" if operation == "apply" else "h3_cut_rewrite",
                     lambda value: _compile_cut(value, official, context, common), progress, cancel_event,
                     translation_chars=len(japanese) if operation == "apply" else None)


def edit_prompts(config, manifest, plan, cuts, index, operation, cache, *,
                 japanese=None, instruction="", progress=None, cancel_event=None, selected_indices=None):
    """Run one model session if needed. Returns new draft text, never saves a revision."""
    from .lmstudio import LMStudio
    from .model_runtime import release_comfy_before_llm
    from .prompt_profiles import H3_PROFILE_INSTRUCTIONS, DEFAULT_H3_PROFILE
    if operation not in ("translate", "translate_all", "apply", "regenerate"):
        raise OrchestratorError("プロンプト操作が不正です")
    if type(index) is not int or not 0 <= index < len(cuts) or len(plan["segments"]) != len(cuts):
        raise OrchestratorError("カット番号が不正です")
    targets = (index,)
    if selected_indices is not None:
        if operation != "regenerate" or not isinstance(selected_indices, (list, tuple)):
            raise OrchestratorError("再生成対象の指定が不正です")
        if not selected_indices or any(type(i) is not int or not 0 <= i < len(cuts)
                                       for i in selected_indices) or index not in selected_indices:
            raise OrchestratorError("再生成対象のカット番号が不正です")
        targets = tuple(sorted(set(selected_indices)))
    official = plan.get("format") == hp.FORMAT
    before = copy.deepcopy(plan)
    after = copy.deepcopy(plan)
    japanese = dict(japanese or {})
    if not set(japanese) <= {"common", "cut"} or any(
            not isinstance(v, str) or len(v) > 18000 for v in japanese.values()):
        raise OrchestratorError("日本語の編集内容が不正です")
    if operation == "apply" and not japanese:
        raise OrchestratorError("日本語の編集内容がありません")
    if operation != "apply" and japanese:
        raise OrchestratorError("日本語の変更を反映してから操作してください")
    if not isinstance(instruction, str) or len(instruction) > 2000:
        raise OrchestratorError("修正指示は2000文字以内です")

    def note(line):
        if progress:
            progress(line)

    def source(kind):
        return after["common"] if kind == "common" else after["segments"][index]

    def review_result(translated_count=0):
        result = {"before": before, "after": after, "index": index,
                  "japanese": {kind: cache.get(kind, source(kind), official) for kind in ("common", "cut")}}
        if operation == "translate_all":
            result["translated_count"] = translated_count
        if operation == "regenerate":
            result["rewritten_indices"] = list(targets)
        return result

    check_cancel(cancel_event)
    review_only = operation in ("translate", "translate_all")
    # Cache-only review never loads/unloads models or frees ComfyUI.
    if review_only and not cache.missing(after, None if operation == "translate_all" else index):
        return review_result()
    context = cut_context(manifest, plan, cuts, index) if operation == "apply" else None
    settings = dict(config["llm"], send_reference_to_llm=False)
    if settings.get("model", "") in ("", "SELECT_IN_GUI"):
        raise OrchestratorError("LM Studioのモデルを選択してください")
    client = LMStudio(settings)
    instance = None
    try:
        release_comfy_before_llm(config["comfyui"], progress=note)
        check_cancel(cancel_event)
        instance = client._ensure_loaded()
        if operation == "apply" and "common" in japanese:
            note("共通プロンプトの日本語編集を英語へ反映")
            after["common"] = _english_common(client, instance, japanese["common"], official, note, cancel_event)
        if operation == "regenerate":
            # All selected rewrites are staged in a private draft. Recompute
            # context on the evolving plan, in playback order; no job or saved
            # revision is touched, and a failed/cancelled batch is not published.
            for done, target in enumerate(targets, 1):
                check_cancel(cancel_event)
                note(f"プロンプト再生成 {done}/{len(targets)}: カット{target+1}")
                context = cut_context(manifest, after, cuts, target)
                after["segments"][target] = _english_cut(
                    client, instance, context, after["common"], official, operation, "",
                    instruction, note, cancel_event, H3_PROFILE_INSTRUCTIONS.get(
                        settings.get("h3_prompt_profile", DEFAULT_H3_PROFILE), ""))
        elif operation == "apply" and "cut" in japanese:
            note(f"カット{index+1}: 日本語編集を英語へ反映")
            context["common"] = after["common"]
            after["segments"][index] = _english_cut(
                client, instance, context, after["common"], official, operation, japanese["cut"],
                instruction, note, cancel_event)
        if operation == "apply" and "common" in japanese and official:
            # A changed common field must fit the already-authored selected cut.
            text = after["segments"][index]
            if text.strip():
                hp.compile_cut(after, index, context["reference_only"],
                               kept_frames=context["retained_frames"], trim_frames=context["trim_frames"],
                               guide_frames=context["guide_frames"], text_only=context.get("text_only", False))
        # Review actual English, not the user's edited Japanese.
        pending = (cache.missing(after, indices=targets) if operation == "regenerate"
                   else cache.missing(after, None if operation == "translate_all" else index))
        try:
            completed = translate_pending(
                client, instance, pending, cache, official, note, cancel_event,
                numbered=operation == "translate_all" or len(targets) > 1,
                detailed_progress=operation == "translate_all",
            )
        except ReviewInterrupted as exc:
            if operation == "translate_all":
                raise OrchestratorError(
                    f"{exc.label}の日本語訳で停止しました（{exc.completed}/{exc.total}件完了）。"
                    f"完了分は保持しています。\n{exc.original}"
                ) from exc.original
            raise exc.original from None
        if operation == "translate_all":
            note(f"一括翻訳完了: {completed}件")
        return review_result(completed)
    finally:
        client.unload_selected(instance, note)
