"""Optional Windows embedded libVLC player; no decoder is started until Play."""
from __future__ import annotations

import ctypes
import importlib
import sys
import tkinter as tk
from tkinter import ttk
from pathlib import Path


def format_time(ms: int) -> str:
    seconds = max(0, ms) // 1000
    return f"{seconds // 60}:{seconds % 60:02d}"


def preview_error_message(exc):
    if isinstance(exc, ModuleNotFoundError) and exc.name == "vlc":
        return ("現在のPythonに python-vlc がありません。run_gui.bat から起動して導入するか、"
                "外部プレイヤーで開いてください。\n使用中のPython: " + sys.executable)
    return "アプリ内再生に失敗しました。64bit VLCを確認、または外部プレイヤーで開いてください: " + str(exc)[:100]


def attach_windows(player, hwnd: int) -> None:
    # libVLC requires WS_CLIPCHILDREN for the host window.
    from ctypes import wintypes
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    get_style = user32.GetWindowLongW
    get_style.argtypes = (wintypes.HWND, ctypes.c_int)
    get_style.restype = ctypes.c_long
    set_style = user32.SetWindowLongW
    set_style.argtypes = (wintypes.HWND, ctypes.c_int, ctypes.c_long)
    set_style.restype = ctypes.c_long
    set_style(hwnd, -16, get_style(hwnd, -16) | 0x02000000)
    player.set_hwnd(hwnd)


class VLCSession:
    """Own one player and its native references, including partial-open cleanup."""

    def __init__(self, path: Path, hwnd: int):
        self.instance = self.player = self.media = None
        if sys.platform != "win32":
            raise RuntimeError("アプリ内再生は現在Windows版に対応しています")
        try:
            self.vlc = importlib.import_module("vlc")
            self.instance = self.vlc.Instance("--no-video-title-show", "--avcodec-hw=none")
            if self.instance is None:
                raise RuntimeError("libVLCの初期化に失敗しました")
            self.player = self.instance.media_player_new()
            self.media = self.instance.media_new_path(str(path.resolve()))
            if self.player is None or self.media is None:
                raise RuntimeError("動画を開けません")
            attach_windows(self.player, hwnd)
            self.player.set_media(self.media)
            self.player.video_set_mouse_input(False)
            self.player.video_set_key_input(False)
        except Exception:
            self.close()
            raise

    def close(self):
        # Stop before releasing the native rendering window and references.
        player, media, instance = self.player, self.media, self.instance
        self.player = self.media = self.instance = None
        if player is not None:
            try:
                player.stop()
            except Exception:
                pass
        for item in (player, media, instance):
            if item is not None:
                try:
                    item.release()
                except Exception:
                    pass


class VideoPreview(ttk.Frame):
    """Lazy, audio-capable local-file preview with a small transport bar."""

    def __init__(self, master, *, height: int):
        super().__init__(master)
        self.source: Path | None = None
        self.session: VLCSession | None = None
        self.enabled = True
        self.muted = False
        self._timer = None
        self._dragging = False
        self._syncing = False
        bar = ttk.Frame(self)
        bar.pack(side="bottom", fill="x", pady=(4, 0))
        self.play_button = ttk.Button(bar, text="再生", width=5, command=self.toggle)
        self.play_button.pack(side="left")
        self.stop_button = ttk.Button(bar, text="停止", width=5, command=self.stop)
        self.stop_button.pack(side="left", padx=(4, 4))
        self.position = tk.DoubleVar(value=0)
        self.seek = ttk.Scale(bar, from_=0, to=1, variable=self.position,
                              command=self._seek_changed)
        self.seek.pack(side="left", fill="x", expand=True)
        self.seek.bind("<ButtonPress-1>", self._seek_begin)
        self.seek.bind("<ButtonRelease-1>", self._seek_end)
        self.time = tk.StringVar(value="0:00 / --:--")
        ttk.Label(bar, textvariable=self.time).pack(side="left", padx=(4, 4))
        self.mute_button = ttk.Button(bar, text="消音", width=5, command=self.toggle_mute)
        self.mute_button.pack(side="right")
        self.info = tk.StringVar(value="")
        ttk.Label(self, textvariable=self.info, wraplength=360).pack(side="bottom", fill="x")
        self.surface = tk.Frame(self, background="#000000", height=height)
        self.surface.pack(fill="both", expand=True)
        self.bind("<Unmap>", self._unmapped, add="+")
        self._controls()

    def _unmapped(self, event):
        if event.widget is self:
            self.stop()

    def _controls(self):
        active = self.enabled and self.session is not None
        self.play_button.configure(state="normal" if self.enabled and self.source is not None else "disabled")
        self.stop_button.configure(state="normal" if active else "disabled")
        self.seek.configure(state="normal" if active else "disabled")
        self.mute_button.configure(state="normal" if active else "disabled")

    def set_source(self, path: Path | None):
        if path == self.source:
            return
        self.stop()
        self.source = path
        self.info.set("")
        self._controls()

    def set_enabled(self, enabled: bool):
        self.enabled = enabled
        if not enabled:
            self.stop()
        self._controls()

    def toggle(self):
        if not self.enabled or self.source is None or not self.winfo_ismapped():
            return
        try:
            if self.session is None:
                if not self.source.is_file():
                    raise RuntimeError("動画ファイルが見つかりません")
                self.info.set("")
                self.session = VLCSession(self.source, self.surface.winfo_id())
                if self.session.player.play() == -1:
                    raise RuntimeError("動画の再生を開始できません")
                self.session.player.audio_set_mute(self.muted)
                self._controls()
                self.play_button.configure(text="一時停止")
                self._poll()
            elif self.session.player.get_state() == self.session.vlc.State.Paused:
                self.session.player.set_pause(0)
            else:
                self.session.player.set_pause(1)
        except Exception as exc:
            self._fail(exc)

    def _fail(self, exc):
        self.stop()
        self.info.set(preview_error_message(exc))

    def toggle_mute(self):
        if self.session is None:
            return
        self.muted = not self.muted
        self.session.player.audio_set_mute(self.muted)
        self.mute_button.configure(text="消音解除" if self.muted else "消音")

    def _seek_begin(self, _event):
        self._dragging = True

    def _seek_end(self, _event):
        self._dragging = False
        self._seek_changed(self.position.get())

    def _seek_changed(self, value):
        if self._syncing or self._dragging or self.session is None:
            return
        if self.session.player.is_seekable():
            self.session.player.set_position(max(0.0, min(1.0, float(value))))

    def _poll(self):
        self._timer = None
        if self.session is None:
            return
        try:
            if not self.winfo_ismapped() or not self.enabled:
                self.stop()
                return
            player = self.session.player
            state = player.get_state()
            if state == self.session.vlc.State.Error:
                raise RuntimeError("VLCが動画をデコードできません")
            if state in (self.session.vlc.State.Ended, self.session.vlc.State.Stopped):
                self.stop()
                return
            self.play_button.configure(text="再生" if state == self.session.vlc.State.Paused else "一時停止")
            length, current = player.get_length(), player.get_time()
            self.time.set(format_time(current) + " / " + (format_time(length) if length > 0 else "--:--"))
            if length > 0 and not self._dragging:
                self._syncing = True
                try:
                    self.position.set(max(0.0, min(1.0, current / length)))
                finally:
                    self._syncing = False
            self._timer = self.after(150, self._poll)
        except Exception as exc:
            self._fail(exc)

    def stop(self):
        if self._timer is not None:
            self.after_cancel(self._timer)
            self._timer = None
        session, self.session = self.session, None
        if session is not None:
            session.close()
        self._dragging = False
        self._syncing = True
        try:
            self.position.set(0)
        finally:
            self._syncing = False
        self.time.set("0:00 / --:--")
        self.play_button.configure(text="再生")
        self._controls()

    def destroy(self):
        self.stop()
        super().destroy()
