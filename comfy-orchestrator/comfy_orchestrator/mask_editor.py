"""Simple Pillow-powered inpainting mask editor for the Tk desktop GUI.

White mask pixels are editable, black pixels remain protected. The editor
does not modify the source image and saves an RGB PNG mask at full resolution.
Pillow is optional for normal T2I/I2I operation.
"""

from __future__ import annotations

import uuid
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk


def export_strokes(size: tuple[int, int], view_size: tuple[int, int],
                   strokes: list[tuple[int, list[tuple[float, float]]]],
                   destination: Path) -> Path:
    """Rasterize display-coordinates brush paths as a full-resolution mask."""
    from PIL import Image, ImageDraw

    width, height = size
    view_w, view_h = view_size
    if min(width, height, view_w, view_h) < 1 or width * height > 80_000_000:
        raise ValueError("画像サイズが無効か、大きすぎます")
    if not strokes:
        raise ValueError("修正する場所をブラシで指定してください")

    mask = Image.new("L", (view_w, view_h), 0)
    painter = ImageDraw.Draw(mask)
    for diameter, points in strokes:
        if not points:
            continue
        d = max(1, int(diameter))
        if len(points) > 1:
            painter.line(points, fill=255, width=d, joint="curve")
        radius = d / 2
        for x, y in (points[0], points[-1]):
            painter.ellipse((x-radius, y-radius, x+radius, y+radius), fill=255)
    if mask.getbbox() is None:
        raise ValueError("修正範囲が空です")
    full_mask = mask.resize((width, height), Image.Resampling.NEAREST)
    destination.parent.mkdir(parents=True, exist_ok=True)
    full_mask.convert("RGB").save(destination, format="PNG")
    return destination


class MaskEditor(tk.Toplevel):
    def __init__(self, parent: tk.Misc, source: Path, save_directory: Path):
        from PIL import Image, ImageOps, ImageTk

        super().__init__(parent)
        self.title("部分修正：塗った部分だけを描き直す")
        self.geometry("1050x810")
        self.minsize(660, 540)
        self.transient(parent)
        self.result: Path | None = None
        self._save_directory = save_directory
        self._strokes: list[tuple[int, list[tuple[float, float]]]] = []
        self._drawing = False
        self.brush = tk.IntVar(value=28)

        with Image.open(source) as opened:
            self._original_size = ImageOps.exif_transpose(opened).size
            if self._original_size[0] * self._original_size[1] > 80_000_000:
                raise ValueError("画像が大きすぎます（8000万画素超）")
            preview = ImageOps.exif_transpose(opened).convert("RGBA")
        preview.thumbnail((940, 640), Image.Resampling.LANCZOS)
        self._view_size = preview.size
        self._image = ImageTk.PhotoImage(preview, master=self)

        bar = ttk.Frame(self, padding=(12, 10))
        bar.pack(fill="x")
        ttk.Label(
            bar, text="赤く塗った場所だけ変更します（塗らない場所は元画像を維持）。",
        ).pack(side="left")
        ttk.Label(bar, text="ブラシ幅").pack(side="left", padx=(18, 4))
        tk.Scale(bar, from_=4, to=100, orient="horizontal",
                 variable=self.brush, length=145, showvalue=True).pack(side="left")

        holder = ttk.Frame(self, padding=(10, 0, 10, 8))
        holder.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(
            holder, width=preview.width, height=preview.height,
            background="#333333", highlightthickness=0, cursor="crosshair",
        )
        self.canvas.pack(expand=True)
        self.canvas.create_image(0, 0, anchor="nw", image=self._image)
        self.canvas.bind("<ButtonPress-1>", self._begin)
        self.canvas.bind("<B1-Motion>", self._drag)
        self.canvas.bind("<ButtonRelease-1>", self._end)

        footer = ttk.Frame(self, padding=12)
        footer.pack(fill="x")
        ttk.Button(footer, text="1画分戻す", command=self._undo).pack(side="left")
        ttk.Button(footer, text="すべて消す", command=self._clear).pack(side="left", padx=8)
        ttk.Button(footer, text="キャンセル", command=self.destroy).pack(side="right")
        ttk.Button(footer, text="この範囲を使う", command=self._save).pack(side="right", padx=8)
        self.grab_set()

    def _point(self, event) -> tuple[float, float]:
        w, h = self._view_size
        return (float(max(0, min(w-1, event.x))), float(max(0, min(h-1, event.y))))

    def _begin(self, event):
        self._drawing = True
        point = self._point(event)
        self._strokes.append((self.brush.get(), [point]))
        self._draw_dot(point, self.brush.get())

    def _draw_dot(self, point, diameter):
        x, y = point
        r = diameter / 2
        self.canvas.create_oval(x-r, y-r, x+r, y+r,
                                outline="#ff5268", fill="#ff5268", tags=("mask",))

    def _drag(self, event):
        if not self._drawing or not self._strokes:
            return
        point = self._point(event)
        diameter, points = self._strokes[-1]
        prev = points[-1]
        points.append(point)
        self.canvas.create_line(
            *prev, *point, width=diameter, fill="#ff5268",
            capstyle="round", joinstyle="round", tags=("mask",),
        )

    def _end(self, event):
        self._drag(event)
        self._drawing = False

    def _redraw(self):
        self.canvas.delete("mask")
        for diameter, points in self._strokes:
            if not points:
                continue
            self._draw_dot(points[0], diameter)
            for a, b in zip(points, points[1:]):
                self.canvas.create_line(
                    *a, *b, width=diameter, fill="#ff5268",
                    capstyle="round", tags=("mask",),
                )

    def _undo(self):
        if self._strokes:
            self._strokes.pop()
            self._redraw()

    def _clear(self):
        self._strokes.clear()
        self.canvas.delete("mask")

    def _save(self):
        try:
            target = self._save_directory / f"mask_{uuid.uuid4().hex}.png"
            export_strokes(
                self._original_size, self._view_size, self._strokes, target,
            )
        except (ValueError, OSError) as exc:
            messagebox.showerror("マスク保存エラー", str(exc), parent=self)
            return
        self.result = target
        self.destroy()


def edit_mask(parent: tk.Misc, source: Path, save_directory: Path) -> Path | None:
    try:
        import PIL  # noqa: F401
    except ImportError:
        messagebox.showerror(
            "Pillowが必要です",
            "範囲指定エディタにはPillowが必要です。\n"
            "Comfy Orchestratorを起動するPythonで次を実行してください:\n"
            "python -m pip install Pillow",
            parent=parent,
        )
        return None
    if not source.is_file():
        messagebox.showerror("画像なし", "編集する画像が見つかりません", parent=parent)
        return None
    try:
        editor = MaskEditor(parent, source, save_directory)
    except (ValueError, OSError, tk.TclError) as exc:
        messagebox.showerror("部分修正", str(exc), parent=parent)
        return None
    parent.wait_window(editor)
    return editor.result
