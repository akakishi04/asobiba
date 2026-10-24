from __future__ import annotations

import os
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path

from pause_control import PAUSE_PREFIX
from resource_policy import child_creation_flags


PROGRESS_PREFIX = "APP_PROGRESS|"


def _format_remaining(seconds: float) -> str:
    seconds = max(0, int(round(seconds)))
    if seconds < 60:
        return f"{seconds}秒"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}分"
    hours, minutes = divmod(minutes, 60)
    if hours < 24:
        return f"{hours}時間{minutes:02d}分"
    days, hours = divmod(hours, 24)
    return f"{days}日{hours}時間"


def _format_finish(seconds: float) -> str:
    finish = datetime.now() + timedelta(seconds=max(0.0, seconds))
    now = datetime.now()
    if finish.date() == now.date():
        return finish.strftime("%H:%M")
    return finish.strftime("%m/%d %H:%M")


def enable_eta(app_ai) -> None:
    """Patch the GUI runner to display remaining time and predicted finish time."""
    original_init = app_ai.App.__init__
    original_launch = app_ai.App._launch
    original_stage = app_ai.App._stage
    original_idle = app_ai.App._idle

    def init_with_eta(self, root):
        original_init(self, root)
        self._eta_job_started = None
        self._eta_stage_started = None
        self._eta_stage_label = ""
        self._eta_stage_base = 0.0
        self._eta_stage_end = 100.0
        self._eta_last_current = 0.0
        self._eta_last_tick = None
        self._eta_seconds_per_unit = None

    def launch_with_eta(self, worker, *args):
        self._eta_job_started = time.monotonic()
        self._eta_stage_started = None
        self._eta_seconds_per_unit = None
        return original_launch(self, worker, *args)

    def _selected_mode(self):
        try:
            return app_ai.AI_CHOICES[self.ai_mode.get()]
        except Exception:
            return app_ai.AI_NONE

    def _stage_end(self, n: float, text: str) -> float:
        mode = _selected_mode(self)
        if "RVRT復元" in text:
            return 55.0 if mode == app_ai.AI_RVRT_SEEDVR2 else 92.0
        if "SeedVR2復元" in text:
            return 92.0
        if "通常変換" in text:
            return 100.0
        if "最終MP4" in text:
            return 100.0
        return min(100.0, max(float(n) + 5.0, float(n)))

    def stage_with_eta(self, n, text):
        self._eta_stage_started = time.monotonic()
        self._eta_stage_label = text
        self._eta_stage_base = float(n)
        self._eta_stage_end = _stage_end(self, float(n), text)
        self._eta_last_current = 0.0
        self._eta_last_tick = None
        self._eta_seconds_per_unit = None
        result = original_stage(self, n, text)
        if any(key in text for key in ("RVRT復元", "SeedVR2復元", "通常変換")):
            self.root.after(0, lambda t=text: self.status.set(f"{t} / ETA計測中"))
        return result

    def update_progress_eta(self, engine: str, current: float, total: float):
        if total <= 0:
            return
        current = max(0.0, min(float(current), float(total)))
        now = time.monotonic()

        if current <= 0:
            self._eta_last_current = 0.0
            self._eta_last_tick = now
            self._eta_seconds_per_unit = None
            return

        if self._eta_last_tick is None:
            self._eta_last_tick = self._eta_stage_started or now

        delta_units = current - self._eta_last_current
        if delta_units > 0:
            sample = (now - self._eta_last_tick) / delta_units
            if sample > 0:
                if self._eta_seconds_per_unit is None:
                    self._eta_seconds_per_unit = sample
                else:
                    self._eta_seconds_per_unit = (
                        self._eta_seconds_per_unit * 0.65 + sample * 0.35
                    )
            self._eta_last_current = current
            self._eta_last_tick = now

        fraction = current / total
        global_percent = self._eta_stage_base + fraction * (
            self._eta_stage_end - self._eta_stage_base
        )
        self.root.after(
            0,
            lambda p=max(0.0, min(100.0, global_percent)): self.progress.set(p),
        )

        if self._eta_seconds_per_unit is None:
            return
        remaining = self._eta_seconds_per_unit * max(0.0, total - current)
        mode = _selected_mode(self)
        stage = self._eta_stage_label or engine

        if engine == "RVRT" and mode == app_ai.AI_RVRT_SEEDVR2:
            status = (
                f"{stage} / RVRT残り 約{_format_remaining(remaining)} / "
                "全体完了予定はSeedVR2開始後に算出"
            )
        else:
            status = (
                f"{stage} / 残り 約{_format_remaining(remaining)} / "
                f"完了予定 {_format_finish(remaining)}"
            )
        self.root.after(0, lambda s=status: self.status.set(s))

    def _ffmpeg_duration(self):
        try:
            source = Path(self.input.get().strip())
            if not source.is_file():
                return None
            info = app_ai.probe_media(source)
            return info.duration_seconds
        except Exception:
            return None

    def run_with_eta(self, cmd, label, cwd=None):
        if self.cancelled:
            raise app_ai.Cancelled()
        self._log_async(f"\n[{label}]\n{subprocess.list2cmdline(cmd)}\n")
        flags = child_creation_flags(self.config)
        p = subprocess.Popen(
            cmd,
            cwd=str(cwd) if cwd else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            creationflags=flags,
        )
        self.proc = p
        ffmpeg_duration = _ffmpeg_duration(self) if label == "FFmpeg" else None
        try:
            for line in p.stdout or ():
                text = line.strip()
                if text.startswith(PROGRESS_PREFIX):
                    parts = text.split("|")
                    if len(parts) == 4:
                        try:
                            update_progress_eta(
                                self, parts[1], float(parts[2]), float(parts[3])
                            )
                        except ValueError:
                            pass
                    continue

                if text.startswith(PAUSE_PREFIX + "|"):
                    parts = text.split("|")
                    if len(parts) >= 3:
                        state, engine = parts[1], parts[2]
                        mode = parts[3] if len(parts) >= 4 else "soft"
                        # Paused wall time must not pollute inference ETA samples.
                        self._eta_last_tick = None
                        handler = getattr(self, "_child_pause_state", None)
                        if handler is not None:
                            handler(state, engine, mode)
                    self._log_async(line)
                    continue

                if ffmpeg_duration and text.startswith("out_time_us="):
                    try:
                        elapsed = int(text.split("=", 1)[1]) / 1_000_000.0
                        update_progress_eta(self, "FFmpeg", elapsed, ffmpeg_duration)
                    except (ValueError, ZeroDivisionError):
                        pass

                if text:
                    self._log_async(line)
                if self.cancelled:
                    self._kill(p)
                    break
            code = p.wait()
        finally:
            if self.proc is p:
                self.proc = None
        if self.cancelled:
            raise app_ai.Cancelled()
        if code:
            raise app_ai.VideoToolError(f"{label} failed (code {code})")

    def idle_with_eta(self):
        result = original_idle(self)
        self._eta_stage_started = None
        self._eta_last_tick = None
        self._eta_seconds_per_unit = None
        return result

    app_ai.App.__init__ = init_with_eta
    app_ai.App._launch = launch_with_eta
    app_ai.App._stage = stage_with_eta
    app_ai.App._run = run_with_eta
    app_ai.App._idle = idle_with_eta
