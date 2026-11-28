"""H3 audiovisual prompt compiler and LM Studio rewrite policy.

The section names, shot and reference notation follow the MiniMax-AI
MiniMax-H3 h3-prompt-writing skill (references/base-en.txt and ref-en.txt).
The JSON representation, validation and guide adaptation are host-side.
"""
from __future__ import annotations

import base64
import json
import mimetypes
import re
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from .parameters import OrchestratorError, check_param
from .prompt_inference import (check_cancel as _check_cancel, request_validated as _reply,
                               planning_batch_size, token_policy_description)

FORMAT = "h3_official_v1"
LEGACY = "legacy"
BASE_FIELDS = ("integrated_multimodal_description", "overall_soundscape", "non_diegetic_music")
REF_FIELDS = ("subject_definitions", "summary", "retention_analysis", "detailed_description",
              "overall_soundscape", "non_diegetic_music")
ALL_FIELDS = tuple(dict.fromkeys((*BASE_FIELDS, *REF_FIELDS)))
LIMITS = {"integrated_multimodal_description": 2600, "detailed_description": 3200,
          "subject_definitions": 700, "summary": 450, "retention_analysis": 700,
          "overall_soundscape": 450, "non_diegetic_music": 250}
I2VA_HEADER = (
    "For the target video, at 0.00 seconds into the target video, "
    "<Picture 1> (from [Shot 1]) is fully referenced."
)
HEADINGS = re.compile(r"(?m)^(" + "|".join(ALL_FIELDS) + r"):\s*")
SHOTS = re.compile(r"\[Shot (\d+)\]")
CUT_TIME = re.compile(r"(\[Shot \d+\]\s+At )(\d{2}):(\d{2})\.(\d{3})(?=,)")
LABEL = re.compile(r"<(Subject|Picture|Video|Audio) (\d+)>")
OBS_FIELDS = ("style", "subjects", "appearance", "pose", "composition", "environment", "uncertain")
RETENTION = ("fully_preserved", "partially_preserved", "attribute_transfer", "weak_reference")

# These instructions are for the local LLM, not the H3 diffusion model.
POLICY = """Write an audiovisual generation prompt for MiniMax H3, not a still-image tag list.
Return only the requested JSON fields. The host serializes the exact H3 section order.
Use concrete, temporally ordered, visible and audible detail in natural English.
Start from the supplied visual evidence and the requested change. Treat unknown or
occluded details as unknown; do not invent visual facts or unrelated events.
Respect explicit user changes rather than freezing everything. State the desired
stable appearance and readable motion positively; avoid lists of negative quality tags.
Develop the action through its onset, intermediate movement and resulting state.
Fit the actual action and dialogue within the supplied retained duration.
Keep a continuous shot unless a cut is explicitly requested or essential to the request.
Use [Shot 1] without a timestamp. Additional shots must be sequential and begin
'[Shot N] At MM:SS.mmm,' with increasing clip-local cut times inside the retained duration.
Do not repeat shot markers merely to refer to earlier shots in the description.
Describe camera motion naturally within the shot: distinguish pan from truck,
zoom from push/pull; specify amplitude and speed when relevant. A static shot is valid.
Give actual vocal sources stable (S1), (S2) IDs and put only the original
language-tagged speech or lyrics inside <d>[Language] ...</d>. Keep quoted user
speech verbatim; preserve visible text in double quotes. Use <scenetrans> only
for a line continuing across an actual in-clip cut; do not repeat dialogue.
Describe off-screen voiceover as such and keep the on-screen speaker's lips closed.
Put dialogue, singing and synchronized events in the visual/audio timeline body.
overall_soundscape summarizes actual ambience, action sounds and nonverbal sounds
without repeating dialogue; N/A only for explicitly requested complete silence.
non_diegetic_music describes audience-only music, instrumentation and tempo if
requested; otherwise N/A. Do not invent narration, conversation or score.
For an uncomplicated short base clip, roughly 80–180 English words are usually enough.
For a complex Ref2VA shot sequence, aim for the official guide's 350–500-word
detailed_description when the available token/character budget permits.
Do not pad a simple request or invent events just to reach a word count.
Do not output seeds, model names, dimensions, negative prompts, or section headings
inside field values."""

BASE_POLICY = """Base I2VA: integrated_multimodal_description starts with [Shot 1],
then style, composition, visible subject and scene anchors, action progression and
camera/audio. The host writes the exact first-frame alignment instruction.
Do not write that instruction yourself. The opening image is a concrete first frame."""

T2VA_POLICY = """Base T2VA: no source image or other reference assets exist for this initial clip.
integrated_multimodal_description starts with [Shot 1] and establishes the requested
subject, appearance, visual medium, setting, lighting and camera composition in
concrete terms, followed by the action and its ending state. Fill only details
needed to make the user's scene coherent. No Picture, Subject, Video or Audio
reference labels and no first-frame alignment instruction. The first generated
clip establishes the visual continuity for subsequent clips."""
RETENTION_POLICY = """In retention_analysis, write exactly one line for every label
defined at the start of a subject_definitions line. Use this literal syntax:
<Subject 1> (appears in [Shot 1]): fully_preserved - retain the subject's appearance.
If <Picture 1> itself has its own definition, it also needs its own retention line.
Choose exactly ONE of fully_preserved, partially_preserved, attribute_transfer,
weak_reference for each label, according to the user's intended changes. Keep the
underscores, colon before the category, and ASCII hyphen before a concrete reason.
Use the label at the start of the line, no Markdown bullets or bold formatting.
A source-picture citation inside a Subject definition does not define another label.
The example is formatting only; do not copy its retention decision or content."""

REF_POLICY = """Ref2VA: the one input image is a visual reference, not automatically
the opening frame. Return six fields. In subject_definitions define each used
<Subject N> on its own line, citing the source <Picture 1>; a standalone
<Picture 1> definition is appropriate only for a concrete frame/composition role.
Never refer to other source pictures, videos or audio assets that do not exist.
summary begins with [reference generation] (or [keyframe completion] if requested).
retention_analysis gives one line per defined label, using fully_preserved,
partially_preserved, attribute_transfer or weak_reference, restricted to its role.
detailed_description starts with a style sentence before [Shot 1], then the
concrete audiovisual timeline using the defined labels consistently.
Distinguish which attributes are retained from changes in pose, scene and framing.
""" + RETENTION_POLICY

LONG_POLICY = """Plan the entire continuous video as ordered host cut windows.
Here a host cut means a generation interval, not necessarily a cinematic cut.
Use each window's retained duration, not the longer raw generation length.
All shot timestamps are local to the retained portion, not global video time;
the host will shift them for a leading guide. Keep actions and speech inside that
portion, not in discarded frames. Subsequent intervals begin from the prior end
state; do not reset the scene or repeat earlier events or lines. Speaker IDs are
stable across all intervals. The host adds guide/first-frame alignment itself.
Only the first cut may use full Ref2VA sections if requested. Later cuts use the
three base fields with no asset labels, since the opening frame or latent guide
comes from the preceding generated video. common contains ONLY persistent visual
constraints that remain true throughout all cuts: no changing state, no speech,
no music or ambience instruction, no shot markers, no asset labels. Each interval
has its own soundscape and score. Do not force each interval to introduce a new event."""


def enabled(settings):
    return settings.get("h3_prompt_format", LEGACY) == FORMAT


def fields_for(reference_only):
    return REF_FIELDS if reference_only else BASE_FIELDS


def object_schema(fields, limits=LIMITS):
    return {"type": "object", "properties": {
        name: {"type": "string", "minLength": 1, "maxLength": limits[name]} for name in fields
    }, "required": list(fields), "additionalProperties": False}


def schema(reference_only):
    value = object_schema(fields_for(reference_only))
    if reference_only:
        value["properties"]["retention_analysis"]["description"] = (
            "One line per defined label. Example: <Subject 1> (appears in [Shot 1]): "
            "fully_preserved - retain the subject's appearance. Choose exactly one of "
            + ", ".join(RETENTION) + ". Preserve the literal colon, underscores and hyphen."
        )
    return value


def _bad(message):
    return OrchestratorError("H3プロンプト形式: " + message)


def _milliseconds(frames):
    return int((Decimal(frames) * 1000 / 24).to_integral_value(rounding=ROUND_HALF_UP))


def _time_text(ms):
    seconds, milli = divmod(ms, 1000)
    minute, second = divmod(seconds, 60)
    return f"{minute:02d}:{second:02d}.{milli:03d}"


def _time_value(match):
    minute, second, milli = map(int, match.groups()[1:])
    if second >= 60:
        raise _bad("カット時刻の秒は00～59にしてください")
    return (minute * 60 + second) * 1000 + milli


# Preserve already canonical lines. Only normalize an otherwise unambiguous
# label/category/reason line; never choose a category or invent a missing reason.
_RETENTION_VARIANTS = "|".join(re.escape(kind).replace("_", r"[_ \t-]+") for kind in RETENTION)
_RETENTION_LINE = re.compile(
    r"^\s*(?:[-*•]\s+|\d+[.)]\s+)?(?:\*\*)?"
    r"(?P<label><(?:Subject|Picture) \d+>)(?:\*\*)?"
    r"(?P<qualifier>\s*\([^()\n]+\))?"
    r"\s*(?::|：|[-–—])\s*(?:\*\*|\x60)?"
    r"(?P<category>" + _RETENTION_VARIANTS + r")(?:\*\*|\x60)?"
    r"\s*(?:(?:[-–—:：])\s*(?P<reason>\S.*)|\((?P<parenthesized>[^()\n]+)\))$",
    re.IGNORECASE,
)


def _retention_error(label, reason):
    return _bad(
        f"{label} のretention_analysisが不正です（{reason}）。"
        f"Use one line: {label}: fully_preserved - reason; "
        "or partially_preserved / attribute_transfer / weak_reference as appropriate."
    )


def normalize_retention(text, defined):
    seen = set()
    lines = []
    for line in text.splitlines():
        if not line.strip():
            continue
        match = _RETENTION_LINE.fullmatch(line)
        if match is None:
            label_match = LABEL.search(line)
            label = label_match.group(0) if label_match else next(iter(sorted(defined)))
            raise _retention_error(label, "書式・分類・理由のいずれかが不正")
        label = match["label"]
        if label not in defined:
            raise _retention_error(label, "未定義のラベル")
        if label in seen:
            raise _retention_error(label, "複数の維持方針")
        seen.add(label)
        category = re.sub(r"[_ \t-]+", "_", match["category"].lower())
        qualifier = match["qualifier"] or ""
        reason = (match["reason"] or match["parenthesized"]).strip()
        # Do not treat an alternative category as the explanation.
        if not reason or re.match(r"^(?:" + _RETENTION_VARIANTS + r")(?:\b|$)", reason, re.IGNORECASE):
            raise _retention_error(label, "維持方針が曖昧")
        canonical = f"{label}{qualifier}: {category} - {reason}"
        # Keep already documented forms byte-for-byte when possible.
        lines.append(line if line == canonical else canonical)
    for label in sorted(defined - seen):
        raise _retention_error(label, "維持方針が未記述")
    result = "\n".join(lines)
    if len(result) > LIMITS["retention_analysis"]:
        raise _bad("retention_analysis が長すぎます")
    return result


def validate_sections(value, reference_only, *, kept_frames=None, later_cut=False):
    fields = fields_for(reference_only)
    if not isinstance(value, dict) or set(value) != set(fields):
        raise _bad("必要なセクションが不足または重複しています")
    result = {}
    for key in fields:
        part = value[key]
        if not isinstance(part, str) or not part.strip() or len(part.strip()) > LIMITS[key]:
            raise _bad(f"{key} が空欄または長すぎます")
        part = part.strip()
        if HEADINGS.search(part) or part.startswith("\x60\x60\x60"):
            raise _bad(f"{key} に余分なセクション見出しがあります")
        result[key] = part
    body = result["detailed_description" if reference_only else BASE_FIELDS[0]]
    shots = list(SHOTS.finditer(body))
    if not shots or [int(m.group(1)) for m in shots] != list(range(1, len(shots) + 1)):
        raise _bad("[Shot 1]から連番でショットを記述してください")
    if (not reference_only and shots[0].start() != 0
            or reference_only and not body[:shots[0].start()].strip()):
        raise _bad("開始ショットの形式がモードと一致しません")
    if any(not body[shot.end():shots[i+1].start() if i+1 < len(shots) else len(body)].strip()
           for i, shot in enumerate(shots)):
        raise _bad("ショット本文が空欄です")
    if re.match(r"\s+At \d{2}:\d{2}\.\d{3}", body[shots[0].end():]):
        raise _bad("[Shot 1]には開始時刻を書かないでください")
    last = 0
    for shot in shots[1:]:
        match = CUT_TIME.match(body, shot.start())
        if match is None:
            raise _bad("第2ショット以降は At MM:SS.mmm, が必要です")
        ms = _time_value(match)
        if ms <= last or kept_frames is not None and ms >= _milliseconds(kept_frames):
            raise _bad("ショット時刻が順序または採用尺と一致しません")
        last = ms
    blocks = re.findall(r"<d>(.*?)</d>", body, flags=re.S)
    if (body.count("<d>") != len(blocks) or body.count("</d>") != len(blocks)
            or any(not re.match(r"\[[^\]\n]+\]\s+\S", b) for b in blocks)):
        raise _bad("台詞は <d>[Language] 原文</d> で記述してください")
    for key in fields:
        if key not in ("integrated_multimodal_description", "detailed_description") and (
                "<d>" in result[key] or "</d>" in result[key]):
            raise _bad("台詞はショット本文にだけ記述してください")
    labels = set(LABEL.findall("\n".join(result.values())))
    if any(kind in ("Video", "Audio") or (kind == "Picture" and num != "1") for kind, num in labels):
        raise _bad("入力されていない参照素材のラベルがあります")
    if reference_only:
        definitions = result["subject_definitions"]
        if "<Picture 1>" not in definitions:
            raise _bad("Ref2VAは参照画像<Picture 1>の定義が必要です")
        defined = {m.group(0) for line in definitions.splitlines()
                   if (m := LABEL.match(line.strip()))}
        if not defined or any(f"<Subject {num}>" not in defined for kind, num in labels if kind == "Subject"):
            raise _bad("未定義のSubjectラベルがあります")
        task = re.match(r"^\[([^\]]+)\]", result["summary"])
        types = task.group(1).split(" + ") if task else []
        if not types or len(types) != len(set(types)) or not set(types) <= {"reference generation", "keyframe completion"}:
            raise _bad("Ref2VA summaryのタスク種別が不正です")
        result["retention_analysis"] = normalize_retention(result["retention_analysis"], defined)
    elif any(kind == "Subject" for kind, _ in labels) or (later_cut and labels):
        raise _bad("開始フレーム/ガイド用本文にRef2VAラベルがあります")
    return result


def section_text(value, reference_only):
    fields = fields_for(reference_only)
    separator = "\n" if reference_only else " "
    return "\n\n".join(f"{name}:{separator}{value[name]}" for name in fields)


def parse_sections(text):
    """Editable project cuts store section text, without a runtime anchor line."""
    if not isinstance(text, str):
        raise _bad("カットはテキストで指定してください")
    text = text.strip()
    matches = list(HEADINGS.finditer(text))
    if not matches or matches[0].start() != 0:
        raise _bad("カットにはH3のセクション見出しが必要です")
    keys = tuple(m.group(1) for m in matches)
    if keys not in (BASE_FIELDS, REF_FIELDS):
        raise _bad("セクションの順序または項目が不正です")
    value = {m.group(1): text[m.end():matches[i+1].start() if i+1 < len(matches) else len(text)].strip()
             for i, m in enumerate(matches)}
    ref = keys == REF_FIELDS
    return validate_sections(value, ref), ref


def validate_common(common):
    if not isinstance(common, str) or len(common) > 1600:
        raise _bad("共通プロンプトは1600文字以内にしてください")
    if HEADINGS.search(common) or LABEL.search(common) or SHOTS.search(common) or "<d>" in common:
        raise _bad("共通プロンプトには持続する外見・画風・シーンの条件だけを記述してください")
    return common.strip()


def compile_prompt(value, reference_only, *, common="", kept_frames=None, trim_frames=0,
                   guide_frames=0, later_cut=False, text_only=False):
    """Render canonical section order; insert runtime timing inside the body.

    Native AddGuide supplies latent visual conditioning, not a numbered Ref2VA
    asset. The guide adaptation deliberately uses the base body without an
    unsupported Picture/Video alignment instruction.
    """
    if text_only and (reference_only or later_cut or trim_frames or guide_frames):
        raise _bad("T2VAは参照なしの最初のカット専用です")
    value = validate_sections(value, reference_only, kept_frames=kept_frames,
                              later_cut=later_cut or text_only)
    common = validate_common(common)
    key = "detailed_description" if reference_only else BASE_FIELDS[0]
    body = value[key]
    if trim_frames:
        offset = _milliseconds(trim_frames)
        body = CUT_TIME.sub(lambda m: m.group(1) + _time_text(_time_value(m) + offset), body)
    constraints = [common] if common else []
    if later_cut:
        if guide_frames:
            constraints.append(
                f"The opening {guide_frames / 24:.3f} seconds are the preceding retained video guide. "
                "Continue the established movement and camera trajectory directly into the following action."
            )
        elif trim_frames > 1:
            constraints.append(
                f"Sustain the preceding movement through the opening {trim_frames / 24:.3f} seconds, "
                "then develop the next action continuously."
            )
        else:
            constraints.append("Continue the established movement and framing from the supplied first frame.")
    if constraints:
        marker = body.index("[Shot 1]") + len("[Shot 1]")
        body = body[:marker] + " " + " ".join(constraints) + " " + body[marker:].lstrip()
    value[key] = body
    prompt = section_text(value, reference_only)
    if not reference_only and not guide_frames and not text_only:
        prompt = I2VA_HEADER + "\n\n" + prompt
    check_param("positive_prompt", prompt)
    return prompt


def validate_text_prompt(text, frames):
    """Require a canonical native T2VA prompt, with no fabricated input labels."""
    sections, ref = parse_sections(text)
    if ref:
        raise _bad("T2VAでは参照画像用セクションを使用できません")
    return compile_prompt(sections, False, kept_frames=frames, text_only=True)


def compile_cut(plan, index, reference_only, *, kept_frames=None, trim_frames=0, guide_frames=0,
                text_only=False):
    fields, stored_ref = parse_sections(plan["segments"][index])
    if stored_ref != reference_only:
        raise _bad("開始カットの参照方式が変わりました。対応するH3形式へ編集するか新規計画を作成してください")
    return compile_prompt(fields, reference_only, common=plan["common"], kept_frames=kept_frames,
                          trim_frames=trim_frames, guide_frames=guide_frames, later_cut=index > 0,
                          text_only=text_only)


def default_sections(reference_only):
    audio = {"overall_soundscape": "Natural quiet ambience and subtle sounds of the visible motion.",
             "non_diegetic_music": "N/A"}
    if reference_only:
        return {
            "subject_definitions": "<Subject 1> is the visible subject or visual motif in <Picture 1>, including its established appearance and style.",
            "summary": "[reference generation] Bring <Subject 1> into a coherent naturally moving shot.",
            "retention_analysis": "<Subject 1> (appears in [Shot 1]): fully_preserved - retain the defined appearance and visual style.",
            "detailed_description": "The reference determines the visual style. [Shot 1] <Subject 1> moves naturally with consistent proportions and coherent framing.",
            **audio,
        }
    return {BASE_FIELDS[0]: "[Shot 1] The supplied image determines the initial composition, subject and rendering style. Natural coherent movement develops continuously, retaining visible identity and spatial relationships.",
            **audio}


def observe_reference(client, instance_id, image, progress=None, cancel_event=None):
    if image is None or not client.settings.get("h3_reference_vision", True):
        if progress:
            progress("H3参照画像認識: OFF / 未指定")
        return None
    if getattr(client, "_vision_supported", None) is not True:
        if progress:
            progress("H3参照画像認識: 画像対応を確認できないLLMのため自然文のみで解釈")
        return None
    path = Path(image)
    if not path.is_file() or path.stat().st_size > 40 * 1024 * 1024:
        raise OrchestratorError("H3参照画像が存在しないか40MBを超えています")
    mime = mimetypes.guess_type(str(path))[0]
    if mime not in ("image/png", "image/jpeg", "image/webp"):
        raise OrchestratorError("H3参照画像の形式が不正です")
    limits = {name: 350 for name in OBS_FIELDS}
    content = [{"type": "text", "text": "Describe only directly visible facts: rendering style, subjects, visible appearance, pose, camera/composition, environment and uncertainty. Use short English descriptions; write unknown for hidden facts. Do not infer future actions or invent objects."},
               {"type": "image_url", "image_url": {"url": f"data:{mime};base64," +
                                                 base64.b64encode(path.read_bytes()).decode("ascii")}}]

    def validate(value):
        if set(value) != set(OBS_FIELDS):
            raise _bad("参照画像認識の項目が不正です")
        for name in OBS_FIELDS:
            if not isinstance(value[name], str) or not value[name].strip() or len(value[name]) > limits[name]:
                raise _bad("参照画像認識の内容が不正です")
        return {name: value[name].strip() for name in OBS_FIELDS}

    if progress:
        progress("H3: 参照画像の外見・姿勢・画風・背景を認識")
    observed = _reply(client, instance_id, "You observe a still image. Return visible facts only.",
                      content, object_schema(OBS_FIELDS, limits), "h3_visual_observation",
                      validate, progress, cancel_event)
    if progress:
        progress("【H3参照画像認識】\n" + "\n".join(f"{k}: {v}" for k, v in observed.items()))
    return observed


def _system(workflows, settings, reference_only, *, text_only=False):
    from .prompt_profiles import H3_PROFILE_INSTRUCTIONS, DEFAULT_H3_PROFILE
    style = H3_PROFILE_INSTRUCTIONS.get(settings.get("h3_prompt_profile", DEFAULT_H3_PROFILE), "")
    return ("You are a local MiniMax H3 audiovisual prompt writer. "
            "Explicit user directions take precedence over style-preset defaults. "
            + style + "\n\n" + POLICY + "\n" + (
                T2VA_POLICY if text_only else REF_POLICY if reference_only else BASE_POLICY
            )
            + ("\nThe preset controls rendering and motion; do not force the reference's pose, composition, "
               "background or framing unless requested." if reference_only else ""))


def interpret_single(client, text, workflows, image, progress=None):
    from .workflow_registry import H3_I2V_ID
    ref = bool(client.settings.get("_h3_reference_only", False))
    text_only = client.settings.get("_h3_text_only", False) is True
    if text_only and (ref or image is not None or not text.strip()):
        raise OrchestratorError("参照画像なしのH3生成には自然文が必要です（T2VA）")
    seconds = client.settings.get("_h3_duration_seconds", 124 / 24)
    frames = round(seconds * 24)
    instance_id = None
    try:
        # H3 has an independent, capability-aware visual path. The existing
        # still-image composition flag must not reject a text-only H3 model.
        client._has_visual_input = False
        instance_id = client._ensure_loaded()
        observed = None if text_only else observe_reference(client, instance_id, image, progress)
        payload = {"request": text, "reference_observations": observed,
                   "reference_mode": "T2VA" if text_only else "Ref2VA" if ref else "I2VA",
                   "retained_seconds": seconds}
        if progress:
            progress("H3: 公式形式で映像・音声プロンプトを構成")
        prompt = _reply(client, instance_id, _system(workflows, client.settings, ref, text_only=text_only),
                        json.dumps(payload, ensure_ascii=False), schema(ref), "h3_official_prompt",
                        lambda value: compile_prompt(value, ref, kept_frames=frames, text_only=text_only),
                        progress)
        return {"workflow_id": H3_I2V_ID, "parameters": {"positive_prompt": prompt}}
    finally:
        client.unload_selected(instance_id, progress)


def _window_payload(window, ref, *, text_only=False):
    return {"cut": window["index"], "mode": "T2VA" if text_only and window["index"] == 1
            else "Ref2VA" if ref else "I2VA/base",
            "global_start_seconds": round(window["start_frame"] / 24, 3),
            "global_end_seconds": round(window["end_frame"] / 24, 3),
            "retained_seconds": round(window["output_frames"] / 24, 3),
            "guide_frames": window.get("guide_frames", 0),
            "discarded_opening_frames": window.get("trim_start_frames", int(window["index"] > 1))}


def _batch_schema(batch, first_ref, include_common):
    properties = {"segments": {"type": "object", "properties": {
        f"cut_{w['index']}": schema(first_ref and w["index"] == 1) for w in batch
    }, "required": [f"cut_{w['index']}" for w in batch], "additionalProperties": False}}
    if include_common:
        properties["common"] = {"type": "string", "maxLength": 650}
    return {"type": "object", "properties": properties, "required": list(properties),
            "additionalProperties": False}


def _validate_batch(value, batch, first_ref, common=None, *, text_only=False):
    expect = {"segments", "common"} if common is None else {"segments"}
    if set(value) != expect or not isinstance(value["segments"], dict):
        raise _bad("長尺カットのJSON形式が不正です")
    if common is None:
        common = validate_common(value["common"])
        if len(common) > 650:
            raise _bad("共通条件が長すぎます")
    if set(value["segments"]) != {f"cut_{w['index']}" for w in batch}:
        raise _bad("長尺カットの番号・件数が一致しません")
    segments = []
    for w in batch:
        ref = first_ref and w["index"] == 1
        fields = validate_sections(value["segments"][f"cut_{w['index']}"], ref,
                                  kept_frames=w["output_frames"], later_cut=w["index"] > 1)
        compile_prompt(fields, ref, common=common, kept_frames=w["output_frames"],
                       trim_frames=w.get("trim_start_frames", int(w["index"] > 1)),
                       guide_frames=w.get("guide_frames", 0), later_cut=w["index"] > 1,
                       text_only=text_only and w["index"] == 1)
        segments.append(section_text(fields, ref))
    return common, segments


def plan_long(config, request, windows, reference_only, *, image=None, progress=None,
              cancel_event=None, prompt_cache=None, release_comfy=True, text_only=False,
              translation_cache=None):
    from .workflow_registry import H3_I2V_ID
    from .lmstudio import LMStudio
    from .prompt_cache import CACHE_ERRORS, make_cache_key
    from .model_runtime import release_comfy_before_llm
    from .prompt_review import prepare_plan_review
    from .timeline import validate_prompt_plan, prompt_plan_schema

    def note(message):
        if progress:
            progress(message)

    _check_cancel(cancel_event)
    if text_only and (image is not None or reference_only or not request.strip()):
        raise OrchestratorError("参照画像なしの連続生成には自然文が必要です（T2VA）")
    if not request.strip():
        result = validate_prompt_plan({"format": FORMAT, "common": "",
            "segments": [section_text(default_sections(reference_only and w["index"] == 1),
                                       reference_only and w["index"] == 1) for w in windows]}, len(windows))
        prepare_plan_review(config, result, translation_cache, progress=note,
                            cancel_event=cancel_event, fixed=True)
        return result
    settings = dict(config["llm"], send_reference_to_llm=False)
    if not settings.get("model") or settings["model"] == "SELECT_IN_GUI":
        raise OrchestratorError("LM Studioのモデルを選択してください")
    workflows = {H3_I2V_ID: config["workflows"][H3_I2V_ID]}
    key = None
    if prompt_cache is not None:
        try:
            key = make_cache_key(request, settings, workflows,
                                 {"task": FORMAT + "_long", "windows": windows, "reference_only": reference_only,
                                  "text_only": text_only},
                                 {"image": image} if settings.get("h3_reference_vision", True) else {}, None)
            cached = prompt_cache.get(key)
            if cached is not None:
                try:
                    valid = validate_prompt_plan(cached, len(windows))
                    if valid.get("format") != FORMAT:
                        raise _bad("旧プロンプトキャッシュ")
                    for i, w in enumerate(windows):
                        compile_cut(valid, i, reference_only and i == 0, kept_frames=w["output_frames"],
                                    trim_frames=w.get("trim_start_frames", int(i > 0)), guide_frames=w.get("guide_frames", 0),
                                    text_only=text_only and i == 0)
                except OrchestratorError:
                    pass
                else:
                    note("H3長尺: 解釈キャッシュを使用")
                    prepare_plan_review(config, valid, translation_cache, progress=note,
                                        cancel_event=cancel_event, release_comfy=release_comfy)
                    return valid
        except CACHE_ERRORS as exc:
            note(f"H3キャッシュ読込失敗: {exc}")
    if release_comfy:
        release_comfy_before_llm(config["comfyui"], progress=note)
    client = LMStudio(settings)
    instance_id = None
    try:
        _check_cancel(cancel_event)
        instance_id = client._ensure_loaded()
        observed = None if text_only else observe_reference(client, instance_id, image, note, cancel_event)
        system = _system(workflows, settings, reference_only, text_only=text_only) + (
            "\nFor three-field continuation cuts, integrated_multimodal_description begins with [Shot 1]."
            "\nUse the preceding end state as their opening, not the original reference."
            if reference_only or text_only else ""
        ) + "\n" + LONG_POLICY
        if text_only:
            system += ("\nCut 1 establishes the subject, visual style, setting and spatial details entirely "
                       "from text. Set common to the concrete persistent visual traits that all subsequent "
                       "cuts should preserve; do not claim an input image exists.")
        base = {"request": request, "reference_observations": observed,
                "first_reference_mode": "T2VA" if text_only else "Ref2VA" if reference_only else "I2VA",
                "total_seconds": round(windows[-1]["end_frame"] / 24, 3)}
        # Structured audiovisual descriptions cost more tokens than the former
        # free sentences. Bound detail batches and reuse one loaded LLM.
        size = planning_batch_size(client, maximum=6, context_per_cut=1100)
        note(f"H3長尺: {token_policy_description(client)} / 1回最大{size}カット")
        batches = [windows[i:i+size] for i in range(0, len(windows), size)]
        common = None
        segments = []
        if len(batches) == 1:
            batch = batches[0]
            note(f"H3長尺: {len(batch)}カットの公式プロンプト計画")
            common, segments = _reply(client, instance_id, system,
                json.dumps({**base, "timeline": [_window_payload(w, reference_only and w["index"] == 1,
                                                                  text_only=text_only)
                                                 for w in batch]}, ensure_ascii=False),
                _batch_schema(batch, reference_only, True), "h3_long_batch",
                lambda value: _validate_batch(value, batch, reference_only, text_only=text_only), note, cancel_event)
        else:
            stride = max(1, (len(batches) + 11) // 12)
            groups = [batches[i:i+stride] for i in range(0, len(batches), stride)]
            summaries = [{"first_cut": group[0][0]["index"], "last_cut": group[-1][-1]["index"],
                          "start_seconds": round(group[0][0]["start_frame"]/24, 3),
                          "end_seconds": round(group[-1][-1]["end_frame"]/24, 3)} for group in groups]
            note(f"H3長尺: {len(groups)}章の全体構成")
            outline = _reply(client, instance_id,
                "Plan the requested continuous audiovisual scene across the given chapter ranges. "
                "Return a short common field of persistent visual constraints only (no tags, speech or changing state), "
                "and one concise natural-English progression summary per chapter. Preserve exact quoted speech and "
                "visual evidence; do not invent new events, props or scenery. Assign vocal IDs consistently.",
                json.dumps({**base, "chapters": summaries}, ensure_ascii=False),
                prompt_plan_schema(len(groups)), "h3_long_outline",
                lambda value: validate_prompt_plan(value, len(groups)), note, cancel_event)
            common = validate_common(outline["common"])
            if len(common) > 650:
                raise _bad("全体構成の共通条件が長すぎます")
            for gi, group in enumerate(groups):
                for batch in group:
                    note(f"H3長尺: カット{batch[0]['index']}～{batch[-1]['index']}の詳細計画")
                    previous = segments[-1] if segments else ""
                    _, parts = _reply(client, instance_id, system,
                        json.dumps({**base, "common": common, "chapter": summaries[gi],
                                    "chapter_summary": outline["segments"][gi],
                                    "next_chapter": outline["segments"][gi+1] if gi+1 < len(groups) else "",
                                    "previous_cut": previous,
                                    "timeline": [_window_payload(w, reference_only and w["index"] == 1,
                                                                 text_only=text_only) for w in batch]},
                                   ensure_ascii=False),
                        _batch_schema(batch, reference_only, False), "h3_long_batch",
                        lambda value: _validate_batch(value, batch, reference_only, common,
                                                      text_only=text_only), note, cancel_event)
                    segments.extend(parts)
        result = validate_prompt_plan({"format": FORMAT, "common": common, "segments": segments}, len(windows))
        _check_cancel(cancel_event)
        if key is not None:
            try:
                prompt_cache.put(key, result)
            except CACHE_ERRORS as exc:
                note(f"H3キャッシュ保存失敗: {exc}")
        prepare_plan_review(config, result, translation_cache, client=client, instance_id=instance_id,
                            progress=note, cancel_event=cancel_event)
    finally:
        client.unload_selected(instance_id, note)
    _check_cancel(cancel_event)
    return result
