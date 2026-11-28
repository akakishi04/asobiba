"""Presentation data and action eligibility for saved generation records."""
from __future__ import annotations

from pathlib import Path
import copy

from .image_prompts import KEY as IMAGE_PROMPT_BUNDLE

from .workflow_registry import H3_I2V_ID, VIDEO_KINDS
from .model_registry import model_filename
from .h3 import h3_model_label, H3_TURBO_LABELS
from .generation_form import WORKFLOW_NAMES
from .history import HistoryEntry
from .long_video_plan import LONG_VIDEO_ID
from .output_collection import IMAGE_EXTENSIONS, VIDEO_EXTENSIONS, is_video_output
from .prompt_profiles import T2I_PROFILE_LABELS, I2I_PROFILE_LABELS, H3_PROFILE_LABELS


def history_request_text(entry: HistoryEntry | None) -> str | None:
    """Return the original editable request, never invented text or generated tags."""
    if entry is None or entry.legacy:
        return None
    text = entry.request_text
    return text if isinstance(text, str) and text.strip() else None


def history_prompt_details(entry: HistoryEntry | None) -> dict | None:
    """Expose only the literal prompts and metadata stored for this exact run.

    Never call an LLM, infer a missing negative prompt or consult the latest run.
    Pre-history imported images have no known generation parameters.
    """
    if entry is None or entry.legacy or not isinstance(entry.parameters, dict):
        return None
    positive = entry.parameters.get("positive_prompt")
    if not isinstance(positive, str) or not positive.strip():
        return None
    negative = entry.parameters.get("negative_prompt")
    return {
        "workflow_id": entry.workflow_id,
        "kind": entry.kind,
        "profile": entry.prompt_profile,
        "request_text": entry.request_text,
        "positive_prompt": positive,
        "negative_prompt": negative if isinstance(negative, str) else None,
        **({IMAGE_PROMPT_BUNDLE: copy.deepcopy(entry.parameters[IMAGE_PROMPT_BUNDLE])}
           if IMAGE_PROMPT_BUNDLE in entry.parameters else {}),
        "seed": entry.parameters.get("seed"),
        "steps": entry.parameters.get("steps"),
        "cfg": entry.parameters.get("cfg"),
        "denoise": entry.parameters.get("denoise"),
        "character_traits": entry.character_traits,
        "character_analysis": entry.character_analysis,
        "character_references": entry.character_references,
    }


def history_row(entry: HistoryEntry) -> tuple:
    short = entry.request_text.replace("\n", " ").strip()[:80]
    timestamp = entry.created_at
    try:
        from datetime import datetime
        timestamp = datetime.fromisoformat(timestamp).astimezone().strftime("%m/%d %H:%M")
    except (ValueError, OverflowError):
        timestamp = timestamp[:16]
    title = short or "(プロンプトなし)"
    if getattr(entry, "favorite", False):
        title = "★ " + title
    kind = "連続" if entry.workflow_id == LONG_VIDEO_ID else "素材" if entry.kind == "frame" else entry.kind.upper()
    return (title, (timestamp, kind, str(entry.parameters.get("seed", "—"))))

def history_summary(entry: HistoryEntry) -> str:
    p = entry.parameters
    if entry.kind == "t2i":
        policy_label = T2I_PROFILE_LABELS.get(
            entry.prompt_profile, entry.prompt_profile or "記録なし"
        )
    elif entry.kind in ("i2i", "inpaint"):
        policy_label = I2I_PROFILE_LABELS.get(
            entry.prompt_profile, entry.prompt_profile or "記録なし"
        )
    elif entry.workflow_id == H3_I2V_ID:
        policy_label = H3_PROFILE_LABELS.get(
            entry.prompt_profile, entry.prompt_profile or "記録なし"
        )
    else:
        policy_label = None
    details = [WORKFLOW_NAMES.get(entry.workflow_id, entry.workflow_id)]
    if entry.workflow_id == H3_I2V_ID and p.get("text_only_h3") is True:
        details.append("T2VA")
    if "width" in p and "height" in p:
        details.append(f"{p['width']}×{p['height']}")
    if entry.kind in VIDEO_KINDS and isinstance(p.get("fps"), (int, float)) and p["fps"] > 0 and isinstance(p.get("frames"), int):
        details.append(f"{p['frames'] / p['fps']:.1f}秒")
    if "steps" in p:
        details.append(f"{p['steps']} steps")
    if "checkpoint_model" in p:
        details.append(Path(model_filename(p["checkpoint_model"]).replace("\\", "/")).stem)
    if entry.workflow_id == H3_I2V_ID and "h3_model" in p:
        details.append(h3_model_label(p["h3_model"]))
        turbo = H3_TURBO_LABELS.get(p.get("h3_turbo", "off"), "")
        if turbo and turbo != "OFF":
            details.append("Turbo " + turbo)
    if policy_label:
        details.append(policy_label)
    if entry.kind == "frame":
        details = [f"動画フレーム · {p.get('material_frame', '?')}f"]
    elif entry.legacy:
        details = ["旧履歴"]
    return "  ·  ".join(details)


def history_can_replay(selected, workflows, *, working):
    return (
        len(selected) == 1
        and not selected[0].legacy
        and selected[0].workflow_id in workflows
        and (selected[0].workflow_id != H3_I2V_ID
             or ((selected[0].parameters.get("text_only_h3") is True)
                 == (selected[0].reference_image is None)))
        and selected[0].first_image is not None
        and (selected[0].reference_image is None or selected[0].reference_image.is_file())
        and (selected[0].mask_image is None or selected[0].mask_image.is_file())
        and (selected[0].pose_image is None or selected[0].pose_image.is_file())
        and not working
    )


def history_action_state(selected, workflows, *, working):
    single = selected[0] if len(selected) == 1 else None
    output = single.first_image if single else None
    exists = bool(output and output.is_file())
    still = exists and not is_video_output(output)
    restorable = bool(single and not single.legacy and
                      (single.workflow_id in workflows or single.workflow_id == LONG_VIDEO_ID) and not working)
    comparable = ((len(selected) == 2 and all(e.first_image and e.first_image.is_file()
                                            and not is_video_output(e.first_image) for e in selected))
                  or bool(still and single.reference_image and single.reference_image.is_file()))
    material = bool(single and any(
        path is not None and path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS | VIDEO_EXTENSIONS
        for path in (*getattr(single, "images", (single.first_image,)), single.reference_image)
    ))
    return {
        "open": exists, "restore": restorable, "compare": comparable,
        "prompt": bool(single and history_prompt_details(single)),
        "request": history_request_text(single) is not None and not working,
        "character": bool(single and single.character_traits and not working),
        "use_as_source": material and not working,
    }
