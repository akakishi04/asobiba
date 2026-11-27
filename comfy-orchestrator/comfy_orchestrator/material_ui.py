"""Compact material transfer and exact frame selection dialogs.

Only the UI thread touches Tk. FFmpeg probing and preview decoding run in a
cancellable worker, independently of VLC or a live generation backend.
"""
from __future__ import annotations

import base64
from pathlib import Path
import queue
import tempfile
import threading
import tkinter as tk
from tkinter import ttk, simpledialog

from .material_transfer import DESTINATIONS, Transfer, source_stamp, transfer_settings
from .parameters import OrchestratorError
from .video_media import FFmpeg
from .preview_geometry import preview_subsample


class MaterialDialog(simpledialog.Dialog):
    def __init__(self, parent, materials, destinations, *, workflow="", parameters=None,
                 profile=None, request=None, preferred=None, mode=None):
        self.materials = materials
        self.destinations = destinations
        self.workflow = workflow
        self.parameters = parameters or {}
        self.profile = profile
        self.request = request
        self.preferred = preferred
        self.initial_mode = mode
        super().__init__(parent, title="素材を使用")

    def body(self, master):
        master.columnconfigure(1, weight=1)
        ttk.Label(master, text="素材").grid(row=0, column=0, sticky="w", padx=4, pady=4)
        self.source_box = ttk.Combobox(master, state="readonly", width=44,
                                      values=[m.label for m in self.materials])
        self.source_box.grid(row=0, column=1, sticky="ew", pady=4)
        selected = next((i for i, m in enumerate(self.materials) if m.path == self.preferred), 0)
        self.source_box.current(selected)
        ttk.Label(master, text="使用先").grid(row=1, column=0, sticky="w", padx=4, pady=4)
        self.mode_box = ttk.Combobox(master, state="readonly",
                                    values=[DESTINATIONS[m][0] for m in self.destinations])
        self.mode_box.grid(row=1, column=1, sticky="ew", pady=4)
        self.mode_box.current(self.destinations.index(self.initial_mode) if self.initial_mode in self.destinations else 0)
        self.mode_box.bind("<<ComboboxSelected>>", self._mode_changed)
        self.use_request = tk.BooleanVar(master=self, value=False)
        self.use_settings = tk.BooleanVar(master=self, value=False)
        self.request_box = ttk.Checkbutton(master, text="元のプロンプトも引き継ぐ", variable=self.use_request)
        self.request_box.grid(row=2, column=1, sticky="w", pady=3)
        if not isinstance(self.request, str) or not self.request.strip():
            self.request_box.state(["disabled"])
        self.settings_box = ttk.Checkbutton(master, text="互換性のある生成設定・Seedも引き継ぐ",
                                            variable=self.use_settings)
        self.settings_box.grid(row=3, column=1, sticky="w", pady=3)
        self._mode_changed()
        return self.source_box

    def _mode_changed(self, _event=None):
        try:
            self.settings = transfer_settings(self.workflow, self.parameters, self.profile,
                                              self.destinations[self.mode_box.current()])
        except (OrchestratorError, KeyError, TypeError, ValueError):
            self.settings = {}
        self.settings_box.state(["!disabled"] if self.settings else ["disabled"])
        if not self.settings:
            self.use_settings.set(False)

    def apply(self):
        self.result = Transfer(self.materials[self.source_box.current()],
                               self.destinations[self.mode_box.current()],
                               self.request if self.use_request.get() else None,
                               dict(self.settings) if self.use_settings.get() else {})


class FramePicker(tk.Toplevel):
    def __init__(self, parent, path, *, initial_ratio=0.0):
        super().__init__(parent)
        self.title("フレームを選択")
        self.transient(parent)
        self.geometry("650x480")
        self.minsize(400, 280)
        self.path = Path(path)
        self.ratio = max(0.0, min(1.0, initial_ratio))
        self.result = None
        self.info = None
        self.stamp = None
        self.photo = None
        self.previewed = None
        self.busy = False
        self.cancel = threading.Event()
        self.messages = queue.Queue()
        self._timer = None
        outer = ttk.Frame(self, padding=8)
        outer.pack(fill="both", expand=True)
        bar = ttk.Frame(outer)
        bar.pack(fill="x", side="bottom")
        self.number = tk.StringVar(master=self, value="1")
        self.frame_box = ttk.Spinbox(bar, from_=1, to=1, textvariable=self.number, width=9)
        self.frame_box.pack(side="left")
        self.range_text = tk.StringVar(master=self, value=" / —")
        ttk.Label(bar, textvariable=self.range_text).pack(side="left", padx=4)
        self.preview_button = ttk.Button(bar, text="確認", command=self._preview)
        self.preview_button.pack(side="left", padx=4)
        self.last_button = ttk.Button(bar, text="末尾", command=self._last)
        self.last_button.pack(side="left")
        self.accept = ttk.Button(bar, text="このフレームを使用", command=self._accept)
        self.accept.pack(side="right", padx=(4, 0))
        ttk.Button(bar, text="閉じる", command=self._close).pack(side="right")
        self.status = tk.StringVar(master=self, value="動画を確認中…")
        ttk.Label(outer, textvariable=self.status, wraplength=600).pack(side="bottom", fill="x", pady=4)
        self.image = ttk.Label(outer, anchor="center")
        self.image.pack(fill="both", expand=True)
        self.number.trace_add("write", self._sync)
        self.protocol("WM_DELETE_WINDOW", self._close)
        self._launch(self._probe)

    def _sync(self, *_args):
        ready = self.info is not None and not self.busy
        for button in (self.preview_button, self.last_button):
            button.configure(state="normal" if ready else "disabled")
        self.frame_box.configure(state="normal" if ready else "disabled")
        self.accept.configure(state="normal" if ready and self.number.get() == str(self.previewed)
                              else "disabled")

    def _launch(self, operation):
        self.busy = True
        self._sync()
        def task():
            try:
                self.messages.put(("ok", operation()))
            except Exception as exc:
                self.messages.put(("error", str(exc)))
        threading.Thread(target=task, daemon=True).start()
        self._timer = self.after(50, self._poll)

    def _probe(self):
        stamp = source_stamp(self.path)
        info = FFmpeg().probe(self.path, self.cancel)
        if info["frames"] < 1:
            raise OrchestratorError("動画にフレームがありません")
        number = max(1, min(info["frames"], round(self.ratio * (info["frames"] - 1)) + 1))
        return info, stamp, number, self._decode(number, stamp)

    def _decode(self, number, stamp):
        if source_stamp(self.path) != stamp:
            raise OrchestratorError("動画が変更されました")
        with tempfile.TemporaryDirectory(prefix="asobiba-preview-") as folder:
            path = Path(folder) / "preview.png"
            FFmpeg().extract_frame(self.path, number, path, self.cancel)
            if source_stamp(self.path) != stamp:
                raise OrchestratorError("動画が変更されました")
            if path.stat().st_size > 40 * 1024 * 1024:
                raise OrchestratorError("画像が40MBを超えています")
            return path.read_bytes()

    def _poll(self):
        self._timer = None
        try:
            kind, value = self.messages.get_nowait()
        except queue.Empty:
            self._timer = self.after(50, self._poll)
            return
        self.busy = False
        try:
            if kind == "error":
                self.status.set(value)
                self.previewed = None
            else:
                if self.info is None:
                    self.info, self.stamp, number, raw = value
                    self.frame_box.configure(to=self.info["frames"])
                    self.range_text.set(f" / {self.info['frames']}f")
                    self.number.set(str(number))
                else:
                    number, raw = value
                photo = tk.PhotoImage(master=self, data=base64.b64encode(raw), format="png")
                factor = preview_subsample(photo.width(), photo.height(),
                                           max(300, self.image.winfo_width()), max(180, self.image.winfo_height()), 400)
                self.photo = photo.subsample(factor, factor)
                self.image.configure(image=self.photo)
                self.previewed = number
                self.status.set(f"{number}f · {photo.width()} × {photo.height()}")
        except (tk.TclError, ValueError, OSError) as exc:
            self.previewed = None
            self.status.set(str(exc))
        self._sync()

    def _last(self):
        if self.info is not None:
            self.number.set(str(self.info["frames"]))
            self._preview()

    def _preview(self):
        if self.info is None or self.busy:
            return
        try:
            number = int(self.number.get())
            if not 1 <= number <= self.info["frames"]:
                raise ValueError
        except ValueError:
            self.status.set("有効範囲のフレーム番号を入力してください")
            return
        self.number.set(str(number))
        self.status.set("フレームを取得中…")
        stamp = self.stamp
        self._launch(lambda: (number, self._decode(number, stamp)))

    def _accept(self):
        if not self.busy and self.number.get() == str(self.previewed):
            self.result = (self.previewed, self.stamp)
            self._close()

    def _close(self):
        self.cancel.set()
        if self._timer is not None:
            self.after_cancel(self._timer)
            self._timer = None
        self.destroy()
