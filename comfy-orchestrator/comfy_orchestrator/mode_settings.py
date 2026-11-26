"""Mode-specific settings backed by the existing Tk variables."""
from __future__ import annotations

import copy

COMMON = ("seed", "steps", "cfg")
H3 = ("h3_size", "h3_duration", "h3_model", "h3_turbo", "h3_encoder_cpu",
      "h3_encoder_model", "h3_steps", "h3_hybrid_steps", "h3_performance", "h3_profile")
MODE_FIELDS = {
    "image": COMMON + ("width", "height", "denoise", "checkpoint_model", "qwen_steps", "qwen_cfg",
                       "pose_mode", "control_strength", "t2i_profile", "i2i_profile", "vision_composition"),
    "video": COMMON + H3 + ("video_size", "video_frames", "video_fps",
                            "hunyuan_size", "hunyuan_frames", "hunyuan_steps"),
    "continuous": COMMON + H3,
}


class ModeSettings:
    """Keep numerical/model settings separate without replacing Tk widgets.

    Natural-language text and primary reference image remain shared.
    Existing flat config values are the migration defaults for every mode.
    """
    def __init__(self, owner, active, stored=None):
        self.active = active
        stored = stored if isinstance(stored, dict) else {}
        self.values = {}
        for mode, fields in MODE_FIELDS.items():
            defaults = {name: getattr(owner, name).get() for name in fields}
            saved = stored.get(mode, {})
            if isinstance(saved, dict):
                for name, default in defaults.items():
                    value = saved.get(name)
                    if type(value) is type(default) and (not isinstance(value, str) or len(value) <= 2048):
                        defaults[name] = value
            self.values[mode] = defaults
        self.restore(owner, active)

    def capture(self, owner):
        self.values[self.active] = {name: getattr(owner, name).get() for name in MODE_FIELDS[self.active]}

    def restore(self, owner, mode):
        for name, value in self.values[mode].items():
            variable = getattr(owner, name)
            if variable.get() != value:
                variable.set(value)

    def switch(self, owner, mode):
        if mode == self.active:
            return False
        self.capture(owner)
        self.active = mode
        self.restore(owner, mode)
        return True

    def snapshot(self, owner):
        self.capture(owner)
        return copy.deepcopy(self.values)
