from __future__ import annotations

import time
from pathlib import Path
from typing import Callable


PAUSE_PREFIX = "APP_PAUSE"


def wait_if_paused(
    pause_file: str | Path | None,
    engine: str,
    *,
    before_wait: Callable[[], None] | None = None,
    after_wait: Callable[[], None] | None = None,
    poll_seconds: float = 0.25,
) -> bool:
    """Cooperatively pause at a safe inference boundary.

    The parent GUI signals pause by creating a marker file. Child runners check
    only at safe chunk/batch boundaries, optionally offload the active model,
    then wait until the marker is removed. This avoids suspending a CUDA process
    in the middle of a kernel.
    """
    if not pause_file:
        return False

    marker = Path(pause_file)
    if not marker.exists():
        return False

    offloaded = False
    try:
        if before_wait is not None:
            before_wait()
            offloaded = True
        print(f"{PAUSE_PREFIX}|paused|{engine}", flush=True)
        while marker.exists():
            time.sleep(max(0.05, poll_seconds))
    finally:
        if offloaded and after_wait is not None:
            after_wait()

    print(f"{PAUSE_PREFIX}|resumed|{engine}", flush=True)
    return True
