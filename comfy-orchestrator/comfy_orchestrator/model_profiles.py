"""Host-owned image model profiles and picker choices.

A model's loader filename is an identity, never an LLM-generated path.
Known Anima derivatives share a graph; other architectures require a profile.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

ANIMA_ID = "anima_t2i_basic"
ANIMA_BASE = "anima-base-v1.0.safetensors"
ANIMA_ENCODER = "qwen_3_06b_base.safetensors"
ANIMA_VAE = "qwen_image_vae.safetensors"
WAI_ID = "wai_t2i_basic"
QWEN_ID = "qwen_image_2512_t2i"
QWEN_FAST_ID = "qwen_image_2512_lightning_t2i"
WAI_FAMILY = frozenset({WAI_ID, "wai_i2i_basic", "wai_inpaint_basic",
                        "wai_pose_skeleton", "wai_pose_detect"})
T2I_ONLY = frozenset({ANIMA_ID, QWEN_ID, QWEN_FAST_ID})


def anima_model_name(value):
    """Conservative basename recognition in the native diffusion loader."""
    if not isinstance(value, str) or not value or len(value) > 1024:
        return False
    parts = value.replace("\\", "/").split("/")
    if any(not part or part in (".", "..") or ":" in part or "\x00" in part for part in parts):
        return False
    name = parts[-1].lower()
    if not name.endswith(".safetensors"):
        return False
    stem = name.rsplit(".", 1)[0]
    return bool(re.search(r"(?:^|[^a-z0-9])anima(?!gine|tion|ted|tor|te(?:_|$))", stem))


def anima_models(inventory):
    return tuple(dict.fromkeys(name for name in (inventory or {}).get("UNETLoader", ())
                               if anima_model_name(name)))


@dataclass(frozen=True)
class ImageModelChoice:
    label: str
    workflow_id: str
    filename: str | None = None


def image_model_choices(workflows, inventory, sdxl_names, current_sdxl, current_anima):
    result = []
    if WAI_ID in workflows:
        for name in dict.fromkeys((*sdxl_names, current_sdxl)):
            if name:
                result.append(ImageModelChoice("SDXL · " + name, WAI_ID, name))
    if QWEN_ID in workflows:
        result.append(ImageModelChoice("Qwen-Image 2512", QWEN_ID))
    if QWEN_FAST_ID in workflows:
        result.append(ImageModelChoice("Qwen-Image 2512 · Lightning 4 Steps", QWEN_FAST_ID))
    if ANIMA_ID in workflows:
        names = anima_models(inventory)
        # A selected, removed file remains visible. On a fresh installation
        # expose the discovered derivatives instead of inventing filenames.
        saved = (current_anima,) if anima_model_name(current_anima) else ()
        for name in dict.fromkeys((*names, *saved)):
            result.append(ImageModelChoice("Anima · " + name, ANIMA_ID, name))
    return tuple(result)


def selected_label(choices, workflow, sdxl, anima):
    family = WAI_ID if workflow == "自動" or workflow in WAI_FAMILY else workflow
    filename = sdxl if family == WAI_ID else anima if family == ANIMA_ID else None
    return next((choice.label for choice in choices
                 if choice.workflow_id == family and choice.filename == filename), None)


def defaults_for(workflows, choice, *, turbo=False):
    defaults = dict(workflows[choice.workflow_id].get("defaults", {}))
    if turbo:
        defaults.update(steps=4, cfg=1)
    return defaults
