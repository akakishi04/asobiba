from __future__ import annotations

import tempfile
import uuid
from pathlib import Path


def enable_pause_support(app_ai) -> None:
    """Add cooperative Pause/Resume controls for AI inference stages."""

    original_init = app_ai.App.__init__
    original_launch = app_ai.App._launch
    original_stage = app_ai.App._stage
    original_idle = app_ai.App._idle
    original_cancel = app_ai.App._cancel
    original_close = app_ai.App._close

    def _cleanup_pause_marker(self) -> None:
        marker = getattr(self, "_pause_file", None)
        if marker is not None:
            try:
                Path(marker).unlink(missing_ok=True)
            except OSError:
                pass

    def _set_pause_button(self, enabled: bool, text: str = "一時停止") -> None:
        button = getattr(self, "pause_button", None)
        if button is None:
            return
        state = "normal" if enabled else "disabled"
        self.root.after(
            0,
            lambda: button.configure(state=state, text=text),
        )

    def init_with_pause(self, root):
        original_init(self, root)
        self._pause_file = (
            Path(tempfile.gettempdir())
            / f"video_rotate_resize_pause_{uuid.uuid4().hex}.flag"
        )
        self._pause_requested = False
        self._pause_active = False
        self._pause_stage_supported = False

        self.pause_button = app_ai.ttk.Button(
            self.stop.master,
            text="一時停止",
            command=self._toggle_pause,
            state="disabled",
        )
        self.pause_button.pack(side="left", padx=(8, 0))

    def toggle_pause(self):
        if not self.running or not self._pause_stage_supported:
            return
        marker = Path(self._pause_file)
        if marker.exists():
            try:
                marker.unlink()
            except OSError as exc:
                self.status.set(f"再開要求に失敗: {exc}")
                return
            self._pause_requested = False
            self.status.set("再開要求中...")
            _set_pause_button(self, True, "一時停止")
        else:
            try:
                marker.parent.mkdir(parents=True, exist_ok=True)
                marker.touch(exist_ok=True)
            except OSError as exc:
                self.status.set(f"一時停止要求に失敗: {exc}")
                return
            self._pause_requested = True
            self.status.set(
                "一時停止要求中...（現在のAI処理単位が終わると停止します）"
            )
            _set_pause_button(self, True, "再開")

    def child_pause_state(self, state: str, engine: str):
        if state == "paused":
            self._pause_active = True
            self._pause_requested = True
            self.root.after(
                0,
                lambda: self.status.set(
                    f"{engine}: 一時停止中（モデルをCPUへ退避 / VRAM解放）"
                ),
            )
            _set_pause_button(self, True, "再開")
        elif state == "resumed":
            self._pause_active = False
            self._pause_requested = False
            self.root.after(
                0,
                lambda: self.status.set(f"{engine}: 再開しました / ETA再計測中"),
            )
            _set_pause_button(self, True, "一時停止")

    def launch_with_pause(self, worker, *args):
        _cleanup_pause_marker(self)
        self._pause_requested = False
        self._pause_active = False
        self._pause_stage_supported = False
        _set_pause_button(self, False)
        return original_launch(self, worker, *args)

    def stage_with_pause(self, n, text):
        result = original_stage(self, n, text)
        supported = any(
            key in text for key in ("RVRT復元", "SeedVR2復元")
        )
        self._pause_stage_supported = supported
        if supported:
            marker = Path(self._pause_file)
            if marker.exists():
                _set_pause_button(self, True, "再開")
            else:
                _set_pause_button(self, True, "一時停止")
        else:
            # A pause marker should never leak into a non-AI stage.
            _cleanup_pause_marker(self)
            self._pause_requested = False
            self._pause_active = False
            _set_pause_button(self, False)
        return result

    def idle_with_pause(self):
        _cleanup_pause_marker(self)
        self._pause_requested = False
        self._pause_active = False
        self._pause_stage_supported = False
        _set_pause_button(self, False)
        return original_idle(self)

    def cancel_with_pause(self):
        _cleanup_pause_marker(self)
        self._pause_requested = False
        self._pause_active = False
        return original_cancel(self)

    def close_with_pause(self):
        _cleanup_pause_marker(self)
        return original_close(self)

    app_ai.App._toggle_pause = toggle_pause
    app_ai.App._child_pause_state = child_pause_state
    app_ai.App.__init__ = init_with_pause
    app_ai.App._launch = launch_with_pause
    app_ai.App._stage = stage_with_pause
    app_ai.App._idle = idle_with_pause
    app_ai.App._cancel = cancel_with_pause
    app_ai.App._close = close_with_pause
