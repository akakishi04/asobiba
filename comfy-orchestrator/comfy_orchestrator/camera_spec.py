"""Host-owned still-image camera intent, independent of pose and subject orientation."""
from __future__ import annotations

import re

from .parameters import OrchestratorError, check_param

KEY = "camera_spec"
IDS = frozenset({"wai_t2i_basic", "anima_t2i_basic", "qwen_image_2512_t2i",
                 "qwen_image_2512_lightning_t2i"})

# code: (Japanese label, tag/short clause, natural clause, preview geometry).
# Left/right refer to the subject's own left/right, not the viewer's.
OPTIONS = {
    "azimuth": {
        "front": ("正面", "front view", "View the subject from the front.", 0),
        "front_left": ("斜め前・左", "front three-quarter view from subject's left",
                       "View the subject from their front-left side.", -45),
        "front_right": ("斜め前・右", "front three-quarter view from subject's right",
                        "View the subject from their front-right side.", 45),
        "left": ("左側面", "left profile view", "View the subject from their left side.", -90),
        "right": ("右側面", "right profile view", "View the subject from their right side.", 90),
        "back_left": ("斜め後ろ・左", "rear three-quarter view from subject's left",
                      "View the subject from their rear-left side.", -135),
        "back_right": ("斜め後ろ・右", "rear three-quarter view from subject's right",
                       "View the subject from their rear-right side.", 135),
        "back": ("背面", "from behind", "View the subject from behind.", 180),
    },
    "elevation": {
        "overhead": ("真上", "overhead view", "Use a nearly vertical overhead viewpoint.", 85),
        "high": ("俯瞰", "from above", "Look down at the subject from a high angle.", 30),
        "level": ("水平", "level viewing angle", "Use a level viewing angle.", 0),
        "low": ("煽り", "from below", "Look up at the subject from a low angle.", -25),
        "under": ("真下に近い", "extreme low-angle view", "Use an extreme upward viewing angle.", -75),
    },
    "shot_size": {
        "full": ("全身", "full body", "Frame the entire body, including feet.", (0.90, 2.05)),
        "knees": ("膝上", "cowboy shot", "Frame the subject from the knees upward.", (1.12, 1.48)),
        "waist": ("腰上", "waist-up shot", "Frame the subject from the waist upward.", (1.35, 1.05)),
        "bust": ("胸上", "bust shot", "Frame the subject from the chest upward.", (1.55, 0.75)),
        "face": ("顔アップ", "close-up of face", "Frame a close-up of the face.", (1.66, 0.39)),
    },
    "lens": {
        "wide": ("広角", "wide-angle perspective", "Use a wide-angle perspective with pronounced depth.", 68),
        "normal": ("標準", "natural perspective", "Use a natural, moderate perspective.", 42),
        "tele": ("望遠", "compressed perspective", "Use a long-lens, compressed perspective.", 20),
    },
    "roll": {
        "level": ("水平", "level camera roll", "Keep the image horizon level.", 0),
        "left": ("左傾き", "counterclockwise dutch angle", "Tilt the image counterclockwise.", -18),
        "right": ("右傾き", "clockwise dutch angle", "Tilt the image clockwise.", 18),
    },
}
LABELS = {"azimuth": "水平角度", "elevation": "垂直角度", "shot_size": "撮影範囲",
          "lens": "遠近感", "roll": "傾き"}
PREVIEW_DEFAULTS = {"azimuth": "front", "elevation": "level", "shot_size": "full",
                    "lens": "normal", "roll": "level"}


def normalize(value):
    """Sparse valid fields; absent fields impose no camera constraint."""
    if value is None:
        return {}
    if not isinstance(value, dict) or not set(value) <= set(OPTIONS):
        raise OrchestratorError("カメラ設定の形式が不正です")
    result = {}
    for field, choices in OPTIONS.items():
        if field in value:
            code = value[field]
            if not isinstance(code, str) or code not in choices:
                raise OrchestratorError(f"カメラ設定 {LABELS[field]} が不正です")
            result[field] = code
    return result


def split(parameters, workflow_ids):
    clean = dict(parameters)
    spec = normalize(clean.pop(KEY, None))
    if spec and (not workflow_ids or not set(workflow_ids) <= IDS):
        raise OrchestratorError("カメラ設定は対応するT2I専用です")
    return clean, spec


def summary(spec):
    spec = normalize(spec)
    return " / ".join(OPTIONS[k][v][0] for k, v in spec.items()) if spec else "未指定"


def clauses(spec, fmt):
    spec = normalize(spec)
    if fmt not in ("tags", "natural"):
        raise OrchestratorError("カメラ指定のプロンプト形式が不正です")
    index = 1 if fmt == "tags" else 2
    return tuple(OPTIONS[field][code][index] for field, code in spec.items())


def policy(spec):
    """The host inserts deterministic phrases; the LLM resolves conflicting context."""
    spec = normalize(spec)
    if not spec:
        return ""
    return (
        "\nHOST CAMERA CONSTRAINTS (higher priority than free text and reference framing): "
        + " ".join(clauses(spec, "natural")) +
        " Camera viewpoint, framing and lens are independent of the subject's pose, gaze and orientation. "
        "Preserve the requested subject and costume. Do not add conflicting framing, angles, lens or roll "
        "to either positive or negative prompt. Unspecified camera fields remain free. "
        "The host appends the specified camera phrases to the positives; do not repeat them."
    )


def apply_pair(values, spec, fmt):
    """Append host terms to a standalone positive without changing its negative."""
    terms = clauses(spec, fmt)
    result = dict(values)
    if not terms:
        return result
    positive = result.get("positive_prompt")
    if not isinstance(positive, str) or not positive.strip():
        raise OrchestratorError("カメラ指定を適用するPositiveが空です")
    existing = {part.strip().casefold() for part in positive.split(",")} if fmt == "tags" else None
    missing = [term for term in terms if (term.casefold() not in existing if existing is not None
                                          else term.casefold() not in positive.casefold())]
    if missing:
        separator = ", " if fmt == "tags" else " "
        positive = positive.rstrip().rstrip(",")
        if fmt == "natural" and positive[-1:] not in (".", "!", "?"):
            positive += "."
        positive += separator + separator.join(missing)
    check_param("positive_prompt", positive)
    result["positive_prompt"] = positive
    return result


def remove_superseded(values, old, new, fmt):
    """Remove only exact host phrases of replaced fields; do not rewrite other content."""
    old, new = normalize(old), normalize(new)
    if fmt not in ("tags", "natural"):
        raise OrchestratorError("カメラ指定のプロンプト形式が不正です")
    result = dict(values)
    positive = result["positive_prompt"]
    index = 1 if fmt == "tags" else 2
    for field, code in old.items():
        if field not in new or new[field] == code:
            continue
        term = OPTIONS[field][code][index]
        if fmt == "tags":
            positive = re.sub(r"(^|,\s*)" + re.escape(term) + r"(?=\s*(?:,|$))",
                              "", positive, flags=re.I).lstrip(" ,")
        else:
            positive = re.sub(r"(?:^|\s+)" + re.escape(term) + r"(?=\s|$)",
                              "", positive, flags=re.I).strip()
    result["positive_prompt"] = positive
    return result


def update_policy(old, new):
    """On a camera-only adjustment, resolve old camera wording before appending new terms."""
    old, new = normalize(old), normalize(new)
    return (
        "\nCAMERA-ONLY CHANGE: change only the explicitly selected camera fields and remove incompatible "
        "old camera terms from both prompts. Do not alter subject identity, pose, costume, background or lighting. "
        "Fields omitted in the new specification are not constrained; retain their existing visual meaning "
        "unless incompatible with a newly selected field. Prior host camera clauses: "
        + (" ".join(clauses(old, "natural")) or "none") + "."
        + policy(new)
    )
