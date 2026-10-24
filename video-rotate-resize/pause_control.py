from __future__ import annotations

import time
from pathlib import Path
from typing import Callable


PAUSE_PREFIX = "APP_PAUSE"
PAUSE_SOFT = "soft"
PAUSE_DEEP = "deep"


def get_pause_mode(pause_file: str | Path | None) -> str | None:
    if not pause_file:
        return None
    marker = Path(pause_file)
    if not marker.exists():
        return None
    try:
        value = marker.read_text(encoding="utf-8").strip().lower()
    except OSError:
        value = ""
    return PAUSE_DEEP if value == PAUSE_DEEP else PAUSE_SOFT


def wait_if_paused(
    pause_file: str | Path | None,
    engine: str,
    *,
    before_wait: Callable[[], None] | None = None,
    after_wait: Callable[[], None] | None = None,
    accepted_modes: set[str] | None = None,
    poll_seconds: float = 0.25,
) -> bool:
    """Cooperatively pause at a safe inference boundary.

    The marker file contains either soft or deep. Callers decide which modes
    are safe at a particular boundary via accepted_modes.
    """
    mode = get_pause_mode(pause_file)
    if mode is None:
        return False
    if accepted_modes is not None and mode not in accepted_modes:
        return False

    marker = Path(pause_file)
    prepared = False
    try:
        if before_wait is not None:
            before_wait()
            prepared = True
        print(f"{PAUSE_PREFIX}|paused|{engine}|{mode}", flush=True)
        while marker.exists():
            time.sleep(max(0.05, poll_seconds))
    finally:
        if prepared and after_wait is not None:
            after_wait()

    print(f"{PAUSE_PREFIX}|resumed|{engine}|{mode}", flush=True)
    return True
