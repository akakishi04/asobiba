"""Editable character-reference review window for the Tk GUI.

No extracted feature is used for generation until the user explicitly
confirms an editable character description.
"""

from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

from .character_refs import (
    MAX_CHARACTER_IMAGES,
    add_character_image_files,
    validate_images,
    normalize_approved,
    suggested_traits,
    format_evidence,
)
from .file_drop import register_file_drop


class CharacterReferenceWindow:
    def __init__(
        self, root: tk.Misc, *,
        images: tuple[Path, ...],
        analysis: dict | None,
        approved: str,
        on_analyze,
        on_confirm,
        on_clear,
    ) -> None:
        self.images = list(images)
        self.analysis = analysis
        self.on_analyze = on_analyze
        self.on_confirm = on_confirm
        self.on_clear = on_clear
        self.busy = False
        self.window = tk.Toplevel(root)
        self.window.title("キャラ参照・共通特徴の確定")
        screen_h = self.window.winfo_screenheight()
        screen_w = self.window.winfo_screenwidth()
        self.window.geometry(
            f"{min(850, max(550, screen_w-80))}x"
            f"{min(750, max(480, screen_h-140))}"
        )
        self.window.minsize(min(600, screen_w - 70), min(430, screen_h - 110))
        self.window.transient(root)
        self.window.protocol("WM_DELETE_WINDOW", self.window.destroy)

        layout = ttk.Frame(self.window, padding=10)
        layout.pack(fill="both", expand=True)

        # Reserve buttons before expanding panels for shorter Windows displays.
        footer = ttk.Frame(layout)
        footer.pack(side="bottom", fill="x", pady=(7, 0))
        self.status = tk.StringVar(value="画像を2～4枚選び、特徴抽出してください")
        ttk.Label(footer, textvariable=self.status, wraplength=530).pack(
            side="left", fill="x", expand=True,
        )
        self.confirm_button = ttk.Button(
            footer, text="修正内容を確定", command=self.confirm,
        )
        self.confirm_button.pack(side="right", padx=(6, 0))
        ttk.Button(footer, text="閉じる", command=self.window.destroy).pack(
            side="right", padx=(6, 0),
        )
        ttk.Button(footer, text="採用を解除", command=self.clear_approved).pack(
            side="right", padx=(6, 0),
        )

        top = ttk.LabelFrame(layout, text="キャラ参照画像（最大4枚）", padding=8)
        top.pack(fill="x")
        self.image_list = tk.Listbox(
            top, height=4, exportselection=False, font=("Meiryo UI", 9),
        )
        self.image_list.pack(side="left", fill="both", expand=True)
        self.drag_drop_ready = register_file_drop(
            self.image_list, self._add_files
        )
        if self.drag_drop_ready:
            top.configure(text="キャラ参照画像（ここにD&D／最大4枚）")
        button_stack = ttk.Frame(top)
        button_stack.pack(side="right", fill="y", padx=(8, 0))
        self.add_button = ttk.Button(button_stack, text="追加...", command=self.add)
        self.add_button.pack(fill="x", pady=(0, 3))
        self.remove_button = ttk.Button(
            button_stack, text="削除", command=self.remove,
        )
        self.remove_button.pack(fill="x", pady=(0, 3))
        self.up_button = ttk.Button(
            button_stack, text="上へ", command=lambda: self.move(-1),
        )
        self.up_button.pack(fill="x", pady=(0, 3))
        self.down_button = ttk.Button(
            button_stack, text="下へ", command=lambda: self.move(1),
        )
        self.down_button.pack(fill="x")

        action = ttk.Frame(layout)
        action.pack(fill="x", pady=(6, 7))
        self.analyze_button = ttk.Button(
            action, text="キャラの特徴を抽出", command=self.analyze,
        )
        self.analyze_button.pack(side="left")
        ttk.Label(
            action, text="画像対応モデルが必要。生成には確定した文章だけを使います。",
            style="Muted.TLabel",
        ).pack(side="left", padx=(10, 0))

        review = ttk.Panedwindow(layout, orient="vertical")
        review.pack(fill="both", expand=True)
        evidence_frame = ttk.LabelFrame(
            review, text="キャラの核・具体的な共通点・根拠", padding=6,
        )
        review.add(evidence_frame, weight=3)
        self.evidence = scrolledtext.ScrolledText(
            evidence_frame, height=9, wrap="word",
            font=("Meiryo UI", 10), state="disabled",
        )
        self.evidence.pack(fill="both", expand=True)
        edit_frame = ttk.LabelFrame(
            review, text="採用するキャラ特徴（仮説を修正・確定）", padding=6,
        )
        review.add(edit_frame, weight=2)
        self.editor = scrolledtext.ScrolledText(
            edit_frame, height=6, wrap="word",
            font=("Meiryo UI", 11), undo=True,
        )
        self.editor.pack(fill="both", expand=True)

        self._refresh()
        if analysis:
            self._show_analysis(analysis)
        if approved:
            self.editor.delete("1.0", "end")
            self.editor.insert("1.0", approved)
            self.status.set("確定済み。修正する場合は再度「修正内容を確定」を押してください")
        elif not self.drag_drop_ready:
            self.status.set(
                "D&Dを有効にするには tkinterdnd2 をインストールしてください"
            )
        self._enable_actions()

    def is_open(self) -> bool:
        try:
            return bool(self.window.winfo_exists())
        except tk.TclError:
            return False

    def _refresh(self) -> None:
        self.image_list.delete(0, "end")
        for i, path in enumerate(self.images, 1):
            self.image_list.insert("end", f"{i}. {path.name}")

    def _enable_actions(self) -> None:
        state = "disabled" if self.busy else "normal"
        for button in (
            self.add_button, self.remove_button, self.up_button,
            self.down_button, self.analyze_button,
        ):
            button.configure(state=state)
        self.confirm_button.configure(
            state="normal" if not self.busy and self.analysis is not None else "disabled"
        )

    def _invalidate(self) -> None:
        self.analysis = None
        self.editor.delete("1.0", "end")
        self.evidence.configure(state="normal")
        self.evidence.delete("1.0", "end")
        self.evidence.configure(state="disabled")
        self.status.set("参照画像が変更されました。特徴を再抽出してください")
        self._enable_actions()

    def add(self) -> None:
        files = filedialog.askopenfilenames(
            parent=self.window,
            filetypes=[("Images", "*.png *.jpg *.jpeg *.webp")],
        )
        self._add_files(files)

    def _add_files(self, files: tuple[str, ...] | list[str]) -> None:
        """Used by both file-picker and Explorer D&D, with identical validation."""
        if self.busy or not files:
            return
        try:
            updated = add_character_image_files(self.images, files)
        except (ValueError, OSError, RuntimeError) as exc:
            messagebox.showerror(
                "キャラ参照", str(exc), parent=self.window,
            )
            return
        if len(updated) == len(self.images):
            self.status.set("指定画像は既に登録されています")
            return
        self.images = list(updated)
        self._refresh()
        self._invalidate()
        self.status.set(
            f"{len(self.images)}枚を登録。共通特徴を再抽出してください"
        )

    def remove(self) -> None:
        selected = self.image_list.curselection()
        if selected:
            self.images.pop(selected[0])
            self._refresh()
            self._invalidate()

    def move(self, offset: int) -> None:
        selected = self.image_list.curselection()
        if not selected:
            return
        idx = selected[0]
        next_idx = idx + offset
        if not 0 <= next_idx < len(self.images):
            return
        self.images[idx], self.images[next_idx] = (
            self.images[next_idx], self.images[idx]
        )
        self._refresh()
        self.image_list.selection_set(next_idx)
        self._invalidate()

    def analyze(self) -> None:
        try:
            paths = validate_images(self.images)
        except Exception as exc:
            messagebox.showwarning("キャラ参照", str(exc), parent=self.window)
            return
        self.busy = True
        self.status.set("LM Studioで画像を観察しています...")
        self._enable_actions()
        self.on_analyze(paths, self)

    def _show_analysis(self, analysis: dict) -> None:
        self.analysis = analysis
        self.evidence.configure(state="normal")
        self.evidence.delete("1.0", "end")
        self.evidence.insert("1.0", format_evidence(analysis))
        self.evidence.configure(state="disabled")
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", suggested_traits(analysis))

    def finish(self, analysis: dict | None = None, error: str | None = None) -> None:
        if not self.is_open():
            return
        self.busy = False
        if error:
            self.status.set("特徴抽出に失敗しました")
            messagebox.showerror("特徴抽出エラー", error, parent=self.window)
        elif analysis is not None:
            self._show_analysis(analysis)
            self.status.set(
                "抽象的な特徴もLLMの仮説です。根拠と反証を見て修正・確定してください"
            )
        self._enable_actions()

    def confirm(self) -> None:
        if self.analysis is None:
            messagebox.showwarning(
                "キャラ参照", "先に共通特徴を抽出してください",
                parent=self.window,
            )
            return
        try:
            paths = validate_images(self.images)
            traits = normalize_approved(self.editor.get("1.0", "end"))
            self.on_confirm(paths, self.analysis, traits)
        except Exception as exc:
            messagebox.showerror("キャラ参照", str(exc), parent=self.window)
            return
        self.window.destroy()

    def clear_approved(self) -> None:
        self.on_clear()
        self.window.destroy()
