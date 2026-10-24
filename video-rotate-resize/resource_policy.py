from __future__ import annotations

import os
import subprocess
import time

PROFILE_MAX = "max"
PROFILE_BALANCED = "balanced"
PROFILE_BACKGROUND = "background"
PROFILE_CUSTOM = "custom"

RESOURCE_PROFILE_CHOICES = {
    "最大速度": PROFILE_MAX,
    "バランス": PROFILE_BALANCED,
    "他作業優先": PROFILE_BACKGROUND,
    "カスタム": PROFILE_CUSTOM,
}

PROFILE_DEFAULT_DUTY = {
    PROFILE_MAX: 100,
    PROFILE_BALANCED: 75,
    PROFILE_BACKGROUND: 50,
}

VALID_PROFILES = set(RESOURCE_PROFILE_CHOICES.values())


def validate_resource_profile(profile: str, custom_duty: int) -> None:
    if profile not in VALID_PROFILES:
        raise ValueError(f"Unknown resource profile: {profile}")
    if not 20 <= int(custom_duty) <= 100:
        raise ValueError("GPU duty cycle must be between 20 and 100")


def effective_gpu_duty_percent(config) -> int:
    profile = getattr(config, "resource_profile", PROFILE_MAX)
    if profile in PROFILE_DEFAULT_DUTY:
        return PROFILE_DEFAULT_DUTY[profile]
    value = int(getattr(config, "gpu_duty_cycle_percent", 100))
    return max(20, min(100, value))


def effective_seedvr2_blocks_to_swap(config) -> int:
    """Increase offload for low-load profiles without changing image settings."""
    base = int(getattr(config, "seedvr2_blocks_to_swap", 20))
    profile = getattr(config, "resource_profile", PROFILE_MAX)
    if profile == PROFILE_BALANCED:
        return max(base, 24)
    if profile == PROFILE_BACKGROUND:
        return max(base, 28)
    return base


def child_creation_flags(config) -> int:
    if os.name != "nt":
        return 0
    flags = subprocess.CREATE_NO_WINDOW
    profile = getattr(config, "resource_profile", PROFILE_MAX)
    if profile in {PROFILE_BALANCED, PROFILE_BACKGROUND}:
        flags |= subprocess.BELOW_NORMAL_PRIORITY_CLASS
    return flags


def pacing_sleep_seconds(active_seconds: float, duty_percent: int) -> float:
    """Return idle time needed to approximate the requested compute duty cycle."""
    duty = max(20, min(100, int(duty_percent)))
    active = max(0.0, float(active_seconds))
    if duty >= 100 or active <= 0:
        return 0.0
    return active * (100.0 / duty - 1.0)


class DutyPacer:
    """Approximate GPU compute duty by sleeping after measurable inference units."""

    def __init__(self, duty_percent: int):
        self.duty_percent = max(20, min(100, int(duty_percent)))
        self._started: float | None = None

    def begin(self) -> None:
        self._started = time.monotonic()

    def pace(self) -> float:
        if self._started is None:
            self.begin()
            return 0.0
        active = time.monotonic() - self._started
        delay = pacing_sleep_seconds(active, self.duty_percent)
        if delay > 0:
            time.sleep(delay)
        self._started = time.monotonic()
        return delay
