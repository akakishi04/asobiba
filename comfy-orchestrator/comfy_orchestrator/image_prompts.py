"""Paired still-image prompts, including Anima mixed conditioning.

A bundle is history metadata, not a workflow binding or an LLM-owned setting.
Missing/stale alternatives are never silently used for another model.
"""
from __future__ import annotations

import copy
import json

from .parameters import OrchestratorError, check_param
from . import camera_spec
from .workflow_registry import SDXL_WORKFLOW_IDS, QWEN_IDS
from .model_profiles import ANIMA_ID
from .prompt_inference import request_validated, check_cancel

KEY = "image_prompt_bundle"
ALT = "alternate_prompt"
FIELDS = ("positive_prompt", "negative_prompt")
FORMATS = ("tags", "natural")
LABELS = {"tags": "タグ形式", "natural": "自然文形式"}
MIXED_VERSION = 2

CLOTHING_FIDELITY_POLICY = (
    "\nAPPEARANCE AND COSTUME FIDELITY: Treat explicitly requested or user-approved "
    "character appearance and outfit details as high-priority visual constraints, not style suggestions. "
    "Keep each specified garment and accessory distinct: garment type, exact color, cut, collar, "
    "sleeve length, hem, layers and their order, trim, patterns, fasteners, footwear, material, "
    "left/right asymmetry and accessory location when specified. Do not collapse them into generic "
    "words such as uniform, dress or casual clothes. Preserve which garment belongs to which subject. "
    "Use concrete visible descriptions in BOTH standalone positive prompts; include a named character "
    "or outfit identifier if requested, but never rely on the name alone when details are provided. "
    "Do not add or replace clothing to match a default style. Do not introduce contradictory colors, "
    "layers or negatives. Give explicit costume attributes priority over decorative quality tags. "
    "A newer explicit user instruction overrides only the affected approved trait; preserve the rest. "
    "Never guess unspecified or unseen details, or copy clothes from pose/composition-only references."
)


def prompt_format(workflow_id):
    return "tags" if workflow_id in SDXL_WORKFLOW_IDS or workflow_id == ANIMA_ID else "natural" if workflow_id in QWEN_IDS else None


def other_format(fmt):
    return FORMATS[1] if fmt == FORMATS[0] else FORMATS[0]


def pair(values):
    if not isinstance(values, dict) or set(values) != set(FIELDS):
        raise OrchestratorError("画像プロンプトのPositive/Negativeが揃っていません")
    result = {}
    for field in FIELDS:
        value = values[field]
        check_param(field, value)
        if field == "positive_prompt" and not value.strip():
            raise OrchestratorError("画像のPositiveプロンプトが空です")
        result[field] = value
    return result


def active_pair(parameters):
    return pair({field: parameters.get(field, "") for field in FIELDS})


def pair_schema():
    return {"type": "object", "properties": {
        field: {"type": "string", "maxLength": 5000} for field in FIELDS},
        "required": list(FIELDS), "additionalProperties": False}


def supports_plan(workflows):
    return bool(workflows) and all(prompt_format(key) for key in workflows)


def extend_schema(schema, workflows):
    if not supports_plan(workflows):
        return schema
    schema = copy.deepcopy(schema)
    schema["properties"][ALT] = pair_schema()
    schema["required"].append(ALT)
    return schema


def dual_policy(workflows):
    if not supports_plan(workflows):
        return ""
    formats = json.dumps({key: prompt_format(key) for key in workflows})
    policy = (
        "\nPAIRED STILL-IMAGE PROMPTS (overrides conflicting format instructions): "
        "From the same user intent and observed evidence, write BOTH English formats. "
        "The selected workflow's parameters.positive_prompt and negative_prompt use its format "
        + formats + ". The top-level alternate_prompt contains positive_prompt and negative_prompt "
        "in the OTHER format. tags = concise comma-separated visual tags, natural = coherent "
        "descriptive English sentences. Keep identity, composition, lighting, exclusions and "
        "requested edits semantically aligned. Preserve unknowns; do not invent reference details. "
        "Do not put the alternative into parameters. Do not output Japanese or model settings."
    )
    policy += CLOTHING_FIDELITY_POLICY
    if ANIMA_ID in workflows:
        policy += anima_policy()
    return policy


def anima_policy():
    """Keep both standalone representations useful when composed."""
    return (
        "\nANIMA MIXED CONDITIONING: the host combines the tag Positive and natural "
        "Positive as one prompt, while using the tag Negative only. Each format must "
        "also work independently on a different still-image model. Use short lowercase "
        "visual tags with spaces (score_* tags are an exception), and group quality/meta, "
        "subject count, identity and other visual attributes in that order. "
        "Only add artist/style or quality/score tags when appropriate to the request "
        "and checkpoint; do not blindly import SDXL presets or add artist names. "
        "In the natural Positive use complete descriptive sentences emphasizing spatial "
        "relationships, camera/viewpoint, pose, materials, fabric folds, light and shadow "
        "when relevant. Avoid merely repeating the comma-separated list in prose. "
        "Both formats must describe the same scene and exclusions; no invented details. "
        "Express unwanted features in the tag Negative as actual undesirable concepts, "
        "not as negated commands. Keep the combined Positive concise, below 4000 characters."
    )


def split_plan(plan, workflows):
    if not isinstance(plan, dict) or ALT not in plan or not supports_plan(workflows):
        return plan, None
    clean = dict(plan)
    return_clean = clean.pop(ALT)
    return clean, return_clean


def make_bundle(workflow_id, parameters, alternate, instructions=()):
    fmt = prompt_format(workflow_id)
    if fmt is None:
        raise OrchestratorError("画像プロンプト形式に対応していません")
    prompts = {fmt: active_pair(parameters)}
    if alternate is not None:
        prompts[other_format(fmt)] = pair(alternate)
    return {"version": 1, "active_format": fmt, "prompts": prompts,
            "instructions": list(instructions)}


def execution_pair(bundle):
    """Version 1 uses the stored active pair; version 2 has fixed Anima composition.

    Never alter either source representation. In particular, a natural negative
    such as "Avoid blur" is not a safe literal negative-conditioning phrase.
    """
    active = pair(bundle["prompts"][bundle["active_format"]])
    if bundle["version"] != MIXED_VERSION:
        return active
    natural = pair(bundle["prompts"]["natural"])
    return pair({
        "positive_prompt": active["positive_prompt"].rstrip() + "\n\n" + natural["positive_prompt"].lstrip(),
        "negative_prompt": active["negative_prompt"],
    })


def bind_bundle(workflow_id, parameters, alternate, instructions=()):
    """Publish both source formats and the exact execution text atomically."""
    bundle = make_bundle(workflow_id, parameters, alternate, instructions)
    if workflow_id == ANIMA_ID and alternate is not None:
        bundle["version"] = MIXED_VERSION
    return {**parameters, **execution_pair(bundle), KEY: bundle}


def is_mixed(parameters):
    bundle = parameters.get(KEY)
    return isinstance(bundle, dict) and bundle.get("version") == MIXED_VERSION


def editor_pair(parameters, workflow_id):
    """Direct editing targets the standalone active representation."""
    if not is_mixed(parameters):
        return active_pair(parameters)
    _, bundle = split_saved(parameters, workflow_id)
    return dict(bundle["prompts"][bundle["active_format"]])


def split_saved(parameters, workflow_id):
    clean = dict(parameters)
    if KEY not in clean:
        return clean, None
    bundle = clean.pop(KEY)
    fmt = prompt_format(workflow_id)
    if (fmt is None or not isinstance(bundle, dict) or set(bundle) !=
            {"version", "active_format", "prompts", "instructions"}
            or type(bundle["version"]) is not int or bundle["version"] not in (1, MIXED_VERSION)
            or (bundle["version"] == MIXED_VERSION and workflow_id != ANIMA_ID)
            or bundle["active_format"] != fmt):
        raise OrchestratorError("保存された画像プロンプト形式が不正です")
    prompts, instructions = bundle["prompts"], bundle["instructions"]
    if (not isinstance(prompts, dict) or fmt not in prompts or not set(prompts) <= set(FORMATS)
            or not isinstance(instructions, list) or len(instructions) > 100
            or any(not isinstance(s, str) or not s.strip() or len(s) > 2000 for s in instructions)):
        raise OrchestratorError("保存された画像プロンプトの構造が不正です")
    checked = {key: pair(value) for key, value in prompts.items()}
    if bundle["version"] == MIXED_VERSION and set(checked) != set(FORMATS):
        raise OrchestratorError("Anima混合プロンプトには両形式が必要です")
    checked_bundle = {"version": bundle["version"], "active_format": fmt, "prompts": checked,
                      "instructions": list(instructions)}
    if execution_pair(checked_bundle) != active_pair(clean):
        raise OrchestratorError("保存された画像プロンプトと実行用プロンプトが一致しません")
    return clean, checked_bundle


def synchronize(parameters, workflow_id, previous):
    """Direct edits invalidate the other format instead of preserving stale text."""
    if camera_spec.KEY in previous and any(
            str(parameters.get(field, "")).strip() != str(editor_pair(previous, workflow_id).get(field, "")).strip()
            for field in FIELDS):
        # Direct text edits may replace the camera clauses; do not claim the
        # old structured intent still governs those manually edited prompts.
        parameters = {k: v for k, v in parameters.items() if k != camera_spec.KEY}
    if KEY not in previous:
        return parameters
    _, bundle = split_saved(previous, workflow_id)
    fmt = bundle["active_format"]
    edited = active_pair(parameters)
    original = bundle["prompts"][fmt]
    if edited == original or (is_mixed(previous) and all(
            edited[field].strip() == original[field].strip() for field in FIELDS)):
        # The editor may be displaying just the tag component of a mixed prompt.
        return {**parameters, **execution_pair(bundle), KEY: bundle}
    result = dict(parameters)
    result[KEY] = make_bundle(workflow_id, result, None, bundle["instructions"])
    return result


def apply_patches(prompts, edits):
    """Apply exact, unambiguous substrings, retaining every untouched character."""
    if not isinstance(edits, list) or len(edits) > 24:
        raise OrchestratorError("修正差分は24件以内のリストにしてください")
    result = copy.deepcopy(prompts)
    for edit in edits:
        if not isinstance(edit, dict) or set(edit) != {"format", "field", "old", "new"}:
            raise OrchestratorError("画像プロンプト差分の形式が不正です")
        fmt, field, old, new = (edit[k] for k in ("format", "field", "old", "new"))
        if (not isinstance(fmt, str) or fmt not in result or not isinstance(field, str)
                or field not in FIELDS or not isinstance(old, str) or not isinstance(new, str)
                or len(old) > 5000 or len(new) > 5000):
            raise OrchestratorError("画像プロンプト差分の対象が不正です")
        source = result[fmt][field]
        if old:
            first = source.find(old)
            if first < 0 or source.find(old, first + 1) >= 0:
                raise OrchestratorError("置換対象は現在のプロンプト中に一度だけ存在する必要があります")
            source = source.replace(old, new, 1)
        elif new:
            source += new
        else:
            raise OrchestratorError("空の修正差分です")
        result[fmt][field] = source
    return {fmt: pair(values) for fmt, values in result.items()}


def revise_bundle(draft, instruction, *, camera_update=None):
    if not isinstance(instruction, str) or not instruction.strip() or len(instruction) > 2000:
        raise OrchestratorError("修正指示を1～2000文字で入力してください")
    instruction = instruction.strip()
    clean, saved = split_saved(draft.parameters, draft.workflow_id)
    clean, old_camera = camera_spec.split(clean, {draft.workflow_id})
    new_camera = old_camera if camera_update is None else camera_spec.normalize(camera_update)
    if new_camera and draft.workflow_id not in camera_spec.IDS:
        raise OrchestratorError("カメラ設定は対応するT2I専用です")
    bundle = saved or make_bundle(draft.workflow_id, clean, None)
    fmt = bundle["active_format"]
    other = other_format(fmt)
    prompts = bundle["prompts"]
    missing = other not in prompts
    if len(bundle["instructions"]) >= 100:
        raise OrchestratorError("修正履歴が上限です。生成結果から新しい調整を開いてください")
    item = {"type": "object", "properties": {
        "format": {"type": "string", "enum": list(prompts)},
        "field": {"type": "string", "enum": list(FIELDS)},
        "old": {"type": "string", "maxLength": 5000},
        "new": {"type": "string", "maxLength": 5000}},
        "required": ["format", "field", "old", "new"], "additionalProperties": False}
    schema = {"type": "object", "properties": {"edits": {
        "type": "array", "items": item, "maxItems": 24}},
        "required": ["edits"], "additionalProperties": False}
    if missing:
        schema["properties"][ALT] = pair_schema()
        schema["required"].append(ALT)
    system = (
        "Edit paired English still-image generation prompts according to the Japanese instruction. "
        "Only output exact local edits; preserve all unrequested content, weights and constraints. "
        "tags uses comma-separated visual tags; natural uses coherent English sentences. "
        "Each old must occur exactly once in its field at the point of application; use old='' "
        "only for appending new text, including necessary punctuation. Edits apply in order. "
        "For each stored format implement the requested change consistently, including relevant "
        "negative constraints. If nothing needs changing in a format, leave it unchanged. "
        "If alternate_prompt is required, produce the missing format from the resulting intent "
        "and edited active prompt. Never invent unseen visual details or output settings."
    )
    system += CLOTHING_FIDELITY_POLICY
    if draft.workflow_id == ANIMA_ID:
        system += anima_policy()
    if camera_update is not None:
        system += camera_spec.update_policy(old_camera, new_camera)
    elif old_camera:
        system += camera_spec.policy(old_camera)
    payload = json.dumps({"original_request": draft.request, "current_prompts": prompts,
                          "active_format": fmt, "instruction": instruction}, ensure_ascii=False)

    def validate(reply):
        if set(reply) != set(schema["required"]):
            raise OrchestratorError("画像プロンプト修正の応答形式が不正です")
        changed = apply_patches(prompts, reply["edits"])
        if missing:
            changed[other] = pair(reply[ALT])
        if camera_update is not None:
            changed = {key: camera_spec.remove_superseded(value, old_camera, new_camera, key)
                       for key, value in changed.items()}
        if new_camera:
            changed = {key: camera_spec.apply_pair(value, new_camera, key)
                       for key, value in changed.items()}
        if changed == prompts and (camera_update is None or new_camera == old_camera):
            raise OrchestratorError("修正指示に対する変更がありません")
        updated = {**clean, **changed[fmt]}
        if new_camera:
            updated[camera_spec.KEY] = new_camera
        return bind_bundle(draft.workflow_id, updated, changed[other],
                           [*bundle["instructions"], instruction])

    result = draft._session(lambda client, instance: request_validated(
        client, instance, system, payload, schema, "image_prompt_patch", validate,
        draft.controller.note, draft.controller.cancel_event, direct_answer=True))
    check_cancel(draft.controller.cancel_event)
    return result
