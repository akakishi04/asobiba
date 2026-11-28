"""Presentation-only grouping of H3 weights and their conditioning modes.

A short name never replaces a loader filename or persisted model key.
The old full labels remain the internal ModeSettings representation.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, replace

from .h3 import (H3_MODEL_LABELS, h3_hybrid_filename, h3_hybrid_model_key,
                 h3_ref2va_filename)
from .model_registry import parse_h3_key, h3_key, PROFILES


OPENING = "開始フレーム"
REFERENCE = "参考画像"
TEXT_ONLY = "参照なし (T2VA)"
REQUIRED_REFERENCE = "参考画像（必須）"

# Exact registered basenames. Do not infer a quantization or size from
# filenames that do not explicitly identify one.
_HYBRID_NAMES = {
    "10eros_max_8stepturbo_v1.0_hybrid.safetensors": "10Eros Max v1.0",
    "10eros_max_8stepturbo_v1.0_hybrid-int8_hq.safetensors": "10Eros Max · INT8 HQ",
    "10eros_max_8stepturbo_v1.0_hybrid_activation_learned_hq.safetensors": "10Eros Max · Learned HQ",
    "10eros_max_8stepturbo_v1.0_hybrid_activation_learned_compact_w4w6int8_14.50gb.safetensors":
        "10Eros Max · Compact 14.5GB",
    "10eros_max_8stepturbo_v1.0_hybrid_activation_learned_micro.safetensors": "10Eros Max · Micro",
}
_REF_NAMES = {"s3_ref2va_w4a8.safetensors": "S3 W4A8 · Ref2VA"}


@dataclass(frozen=True)
class ModelChoice:
    label: str
    identity: str
    opening: str | None = None
    reference: str | None = None

    def contains(self, key):
        return key is not None and key in (self.opening, self.reference)

    def mode_options(self, *, has_image):
        if not has_image:
            return (TEXT_ONLY,) if self.opening is not None else (REQUIRED_REFERENCE,)
        return tuple(label for label, key in ((OPENING, self.opening), (REFERENCE, self.reference))
                     if key is not None)

    def display_mode(self, key, *, has_image):
        modes = self.mode_options(has_image=has_image)
        return REFERENCE if has_image and key == self.reference and self.reference is not None else modes[0]

    def key_for_mode(self, mode):
        if mode in (OPENING, TEXT_ONLY):
            return self.opening
        if mode in (REFERENCE, REQUIRED_REFERENCE):
            return self.reference
        return None


def _basename(filename):
    return filename.replace("\\", "/").rsplit("/", 1)[-1]


def _choice(key):
    manual = parse_h3_key(key)
    if manual is not None:
        profile, _, filename = manual
        label = _basename(filename).rsplit(".", 1)[0] + " [登録]"
        return ModelChoice(label, "registered:" + profile + ":" + filename,
                           h3_key(profile, "opening", filename), h3_key(profile, "reference", filename))
    filename = h3_hybrid_filename(key)
    if filename is not None:
        label = _HYBRID_NAMES.get(_basename(filename).lower(), _basename(filename).rsplit(".", 1)[0])
        # One exact weight, two supported conditioning modes.
        return ModelChoice(label, "hybrid:" + filename,
                           h3_hybrid_model_key(filename, reference_only=False),
                           h3_hybrid_model_key(filename, reference_only=True))
    filename = h3_ref2va_filename(key)
    if filename is not None:
        base = _basename(filename)
        label = _REF_NAMES.get(base.lower(), base.rsplit(".", 1)[0])
        return ModelChoice(label, "reference:" + filename, reference=key)
    if key in H3_MODEL_LABELS:
        return ModelChoice(H3_MODEL_LABELS[key], "base:" + key, opening=key)
    return None


def model_choices(installed, current):
    """Preserve the selected exact weight even if it is no longer installed."""
    unique = {}
    for key in (*installed, current):
        item = _choice(key)
        if item is not None:
            unique.setdefault(item.identity, item)
    counts = Counter(item.label for item in unique.values())
    result = []
    for item in unique.values():
        if counts[item.label] > 1:
            # Subfolders and spelling differences are real loader identities.
            # Only disambiguate on collision, never silently choose one.
            item = replace(item, label=f"{item.label} [{item.identity.split(':', 1)[1]}]")
        result.append(item)
    return tuple(result)


def select_model_key(choice, previous, *, has_image):
    """Choose the new weight, retaining the old mode when it is supported."""
    if choice.contains(previous):
        return previous
    prefer_reference = has_image and h3_ref2va_filename(previous) is not None
    if prefer_reference and choice.reference is not None:
        return choice.reference
    return choice.opening if choice.opening is not None else choice.reference
