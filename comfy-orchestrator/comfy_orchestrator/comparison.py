"""Side-by-side image comparison with synced zoom and independent panning.

Pillow is optional: when available, PNG/JPEG/WebP are smoothly scaled.
Without Pillow, the standard Tk PNG/GIF reader still supports integer zoom
and approximate thumbnail downscaling, preserving the no-extra-deps install.
"""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import ttk

try:
    from PIL import Image, ImageOps, ImageTk
except ImportError:
    Image = ImageOps = ImageTk = None


ZOOM_STEPS = (0.25, 0.5, 0.75, 1.0, 1.5, 2.0)


def clamp_zoom(value: float) -> float:
    if not isinstance(value, (int, float)) or not 0.25 <= value <= 2:
        raise ValueError("表示倍率は0.25～2.0です")
    return float(value)


def fit_zoom(image_width: int, image_height: int, view_width: int, view_height: int) -> float:
    if min(image_width, image_height, view_width, view_height) <= 0:
        return 1.0
    raw = min(view_width / image_width, view_height / image_height, 1.0)
    return next((step for step in reversed(ZOOM_STEPS) if step <= raw), ZOOM_STEPS[0])


class ImagePane(ttk.Frame):
    def __init__(self, parent, path: Path, title: str):
        super().__init__(parent)
        self.path = Path(path)
        self.title = title
        self._photo = None
        self._source_tk = None
        self._source_pil = None
        self._image_id = None
        self._opened = False

        ttk.Label(self, text=title, anchor="center").pack(fill="x", pady=(2, 5))
        holder = ttk.Frame(self)
        holder.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(holder, background="#252D3A", highlightthickness=0)
        hbar = ttk.Scrollbar(holder, orient="horizontal", command=self.canvas.xview)
        vbar = ttk.Scrollbar(holder, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=hbar.set, yscrollcommand=vbar.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        vbar.grid(row=0, column=1, sticky="ns")
        hbar.grid(row=1, column=0, sticky="ew")
        holder.rowconfigure(0, weight=1)
        holder.columnconfigure(0, weight=1)

        self.canvas.bind("<ButtonPress-2>", self._mark)
        self.canvas.bind("<B2-Motion>", self._drag)
        self._load()
        self.set_zoom(0.5)

    def _load(self):
        if not self.path.is_file():
            raise FileNotFoundError(f"画像がありません: {self.path}")
        if Image is not None:
            with Image.open(self.path) as src:
                if src.width * src.height > 80_000_000:
                    raise ValueError("比較画像が大きすぎます（8000万画素超）")
                self._source_pil = ImageOps.exif_transpose(src).convert("RGBA")
        else:
            # Tk PhotoImage directly supports PNG and GIF, not JPEG or WebP.
            self._source_tk = tk.PhotoImage(file=str(self.path))
        self._opened = True

    def size(self):
        if self._source_pil is not None:
            return self._source_pil.size
        return self._source_tk.width(), self._source_tk.height()

    def set_zoom(self, scale: float):
        scale = clamp_zoom(scale)
        if not self._opened:
            return
        if self._source_pil is not None:
            w, h = self._source_pil.size
            w, h = max(1, round(w * scale)), max(1, round(h * scale))
            scaled = self._source_pil.resize((w, h), Image.Resampling.LANCZOS)
            self._photo = ImageTk.PhotoImage(scaled, master=self)
        else:
            if scale < 1:
                self._photo = self._source_tk.subsample(max(1, round(1.0 / scale)))
            else:
                self._photo = self._source_tk.zoom(max(1, round(scale)))
        if self._image_id is None:
            self._image_id = self.canvas.create_image(0, 0, anchor="nw", image=self._photo)
        else:
            self.canvas.itemconfigure(self._image_id, image=self._photo)
        self.canvas.configure(scrollregion=(0, 0, self._photo.width(), self._photo.height()))
        self.canvas.xview_moveto(0)
        self.canvas.yview_moveto(0)

    def _mark(self, event):
        self.canvas.scan_mark(event.x, event.y)

    def _drag(self, event):
        self.canvas.scan_dragto(event.x, event.y, gain=1)


class ComparisonWindow(tk.Toplevel):
    def __init__(
        self, parent: tk.Misc,
        left_image: Path, right_image: Path,
        left_title: str = "元画像", right_title: str = "生成画像",
    ):
        super().__init__(parent)
        self.title("画像比較 | Comfy Orchestrator")
        self.geometry("1180x780")
        self.minsize(740, 470)
        self.zoom = 0.5

        bar = ttk.Frame(self, padding=10)
        bar.pack(fill="x")
        ttk.Label(
            bar, text="左右に比較表示。ホイールで各画像をスクロール、中央ボタンでドラッグ移動。",
        ).pack(side="left", fill="x", expand=True)
        ttk.Button(bar, text="−", width=4, command=self.zoom_out).pack(side="right", padx=(4, 0))
        ttk.Button(bar, text="+", width=4, command=self.zoom_in).pack(side="right", padx=(4, 0))
        ttk.Button(bar, text="等倍", command=lambda: self.set_zoom(1.0)).pack(side="right", padx=(4, 0))
        self.zoom_label = ttk.Label(bar, text="50%")
        self.zoom_label.pack(side="right", padx=(4, 9))

        content = ttk.Frame(self, padding=(8, 0, 8, 8))
        content.pack(fill="both", expand=True)
        content.columnconfigure(0, weight=1)
        content.columnconfigure(1, weight=1)
        content.rowconfigure(0, weight=1)
        try:
            self.left = ImagePane(content, left_image, left_title)
            self.right = ImagePane(content, right_image, right_title)
        except (OSError, ValueError, tk.TclError) as exc:
            self.destroy()
            raise ValueError(
                f"画像比較を開けません: {exc}。JPEG/WebPが表示できない場合はPillowをインストールしてください"
            ) from exc
        self.left.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        self.right.grid(row=0, column=1, sticky="nsew", padx=(4, 0))
        self.bind("<Control-plus>", lambda _e: self.zoom_in())
        self.bind("<Control-minus>", lambda _e: self.zoom_out())
        self.after_idle(self._fit_initial)

    def _fit_initial(self):
        w = max(250, self.winfo_width() // 2 - 45)
        h = max(250, self.winfo_height() - 100)
        candidates = [
            fit_zoom(*pane.size(), w, h)
            for pane in (self.left, self.right)
        ]
        self.set_zoom(min(candidates))

    def set_zoom(self, value: float):
        self.zoom = clamp_zoom(value)
        self.left.set_zoom(self.zoom)
        self.right.set_zoom(self.zoom)
        self.zoom_label.configure(text=f"{self.zoom:.0%}")

    def zoom_in(self):
        ix = next((i for i, v in enumerate(ZOOM_STEPS) if v > self.zoom), len(ZOOM_STEPS) - 1)
        self.set_zoom(ZOOM_STEPS[ix])

    def zoom_out(self):
        ix = next((i for i in range(len(ZOOM_STEPS) - 1, -1, -1) if ZOOM_STEPS[i] < self.zoom), 0)
        self.set_zoom(ZOOM_STEPS[ix])
