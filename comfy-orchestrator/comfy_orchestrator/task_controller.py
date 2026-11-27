"""Generation task lifecycle and bounded worker event delivery, without Tk.

Only the UI thread changes active-task state. Worker threads emit messages;
cancellation uses a threading.Event and remote job handling stays in the runtime.
"""
from __future__ import annotations

import queue
import threading
import time

from .jobs import JobCancellationRequested
from .long_video_plan import LongVideoPaused
from .timing import observe, format_elapsed


def worker_events(operation, emit, *, done_event="done", long_video=False, cancel_as_progress=False):
    """Consistent worker terminal events; operation must not access Tk widgets."""
    try:
        with observe(emit):
            result = operation()
        emit((done_event, result))
    except JobCancellationRequested as exc:
        if long_video:
            emit(("progress", str(exc) + " / 長尺再開から続行できます"))
        elif cancel_as_progress:
            emit(("progress", str(exc)))
        else:
            emit(("cancel_requested", str(exc)))
    except LongVideoPaused as exc:
        emit(("progress", str(exc) + " / 長尺再開から続行できます"))
    except Exception as exc:
        emit(("error", str(exc)))
    finally:
        emit(("idle", None))


class TaskController:
    """Single foreground operation and its event queue, independent of widgets."""

    def __init__(self, *, clock=None):
        self.messages = queue.Queue()
        self.stop_event = threading.Event()
        self.working = False
        self._clock = clock if clock is not None else time.monotonic
        self._started = None
        self._estimate = None
        self._label = ""
        self._estimate_at = 0.0
        self._last_update = 0.0
        self._launched = False

    def begin(self):
        if self.working:
            raise RuntimeError("A foreground task is already active")
        self.stop_event.clear()
        self.working = True
        self._started = self._clock()
        self._estimate = None
        self._label = ""
        self._last_update = 0.0
        self._launched = False

    def launch(self, operation, *, done_event="done", long_video=False, cancel_as_progress=False):
        if not self.working or self._launched:
            raise RuntimeError("Begin exactly one foreground task before launching")
        self._launched = True
        worker = threading.Thread(
            target=lambda: worker_events(operation, self.messages.put, done_event=done_event,
                                         long_video=long_video, cancel_as_progress=cancel_as_progress),
            daemon=True,
        )
        worker.start()
        return worker

    def cancel(self):
        self.stop_event.set()

    def finish(self):
        # Called after the terminal idle event is dispatched on the UI thread.
        self.working = False
        self._launched = False
        self._started = None
        self._estimate = None
        self._label = ""

    def drain(self, limit=24):
        """Limit event bursts so the UI can repaint and process input."""
        for _ in range(limit):
            try:
                event = self.messages.get_nowait()
            except queue.Empty:
                return
            yield event

    def update_estimate(self, data):
        self._estimate = data["estimate"]
        self._label = data["label"]
        self._estimate_at = data["at"]
        self._last_update = 0.0

    def timing_text(self, *, finished=False):
        if self._started is None:
            return None
        now = self._clock()
        if not finished and now - self._last_update < 0.8:
            return None
        self._last_update = now
        elapsed = format_elapsed(now - self._started)
        if finished:
            return "処理時間 " + elapsed
        text = "経過 " + elapsed
        if self._label:
            text += " / " + self._label
        if self._estimate is not None:
            remaining = self._estimate.seconds - (now - self._estimate_at)
            text += (" 約" + format_elapsed(remaining) if remaining > 0 else " 推定超過")
            text += f" (実測{self._estimate.samples}件" + ("・尺換算)" if self._estimate.scaled else ")")
        elif self._label in ("生成待ち", "残カット生成待ち"):
            text += " 計測中"
        return text
