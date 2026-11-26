"""Editable character-reference review window for the Tk GUI.

No extracted feature is used for generation until the user explicitly
confirms an editable character description.
"""

from __future__ import annotations

from pathlib import Path
import sqlite3
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, simpledialog, ttk

from .character_refs import (
    MAX_CHARACTER_IMAGES,
    add_character_image_files,
    validate_images,
    normalize_approved,
    suggested_traits,
    format_evidence,
)
from .file_drop import register_file_drop
from .character_features import FeatureExistsError


class CharacterReferenceWindow:
    def __init__(
        self, root: tk.Misc, *,
        images: tuple[Path, ...],
        analysis: dict | None,
        approved: str,
        on_analyze,
        on_confirm,
        on_clear,
        on_revise=None,
        on_history=None,
        feature_store=None,
    ) -> None:
        self.images = list(images)
        self.analysis = analysis
        self.on_analyze = on_analyze
        self.on_confirm = on_confirm
        self.on_clear = on_clear
        self.on_revise = on_revise
        self.on_history = on_history
        self.feature_store = feature_store
        self._feature_name = ""
        self.text_only = bool(approved and analysis is None and not images)
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
        self.status = tk.StringVar(value="画像を2～4枚選び、抽出後に日本語の文章を修正・確定してください")
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
        self.revise_button = ttk.Button(
            action, text="日本語の指示で修正...", command=self.revise,
        )
        self.revise_button.pack(side="left", padx=(8, 0))
        features = ttk.Frame(layout)
        features.pack(fill="x", pady=(0, 7))
        self.save_feature_button = ttk.Button(features, text="特徴を保存", command=self.save_feature)
        self.save_feature_button.pack(side="left")
        self.load_feature_button = ttk.Button(features, text="保存済み特徴", command=self.load_feature)
        self.load_feature_button.pack(side="left", padx=(8, 0))
        self.history_button = ttk.Button(features, text="履歴から特徴", command=self.import_history)
        self.history_button.pack(side="left", padx=(8, 0))

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
            review, text="生成に使うキャラ説明（日本語の文章で自由に修正）", padding=6,
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
        if self.text_only:
            self._text_only_evidence()
        if approved:
            self.editor.delete("1.0", "end")
            self.editor.insert("1.0", approved)
            self.status.set("文章のみ確定済み" if self.text_only else
                            "確定済み。修正する場合は再度「修正内容を確定」を押してください")
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
        # Never overwrite edits typed while a model request is running.
        self.editor.configure(state=state)
        for button in (
            self.add_button, self.remove_button, self.up_button,
            self.down_button, self.analyze_button,
        ):
            button.configure(state=state)
        self.history_button.configure(state="normal" if not self.busy and self.on_history is not None else "disabled")
        feature_state = "normal" if not self.busy and self.feature_store is not None else "disabled"
        self.save_feature_button.configure(state=feature_state)
        self.load_feature_button.configure(state=feature_state)
        self.revise_button.configure(
            state=(
                "normal"
                if not self.busy and (self.analysis is not None or self.text_only)
                and self.on_revise is not None
                else "disabled"
            )
        )
        self.confirm_button.configure(
            state="normal" if not self.busy and (self.analysis is not None or self.text_only) else "disabled"
        )

    def _invalidate(self) -> None:
        if self.text_only:
            self.status.set("文章のみの特徴は保持。画像を分析する場合は再抽出してください")
            self._enable_actions()
            return
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
        if not self.text_only:
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

    def revise(self) -> None:
        """Request a text-only LLM rewrite, keeping manual approval required."""
        if self.busy or (self.analysis is None and not self.text_only) or self.on_revise is None:
            return
        try:
            current = normalize_approved(self.editor.get("1.0", "end"))
        except ValueError as exc:
            messagebox.showwarning(
                "キャラ説明", str(exc), parent=self.window,
            )
            return
        instruction = simpledialog.askstring(
            "自然文でキャラ説明を修正",
            "修正内容を日本語で指示してください。\n"
            "例：衣装の説明は削除し、髪型の説明を短くして",
            parent=self.window,
        )
        if instruction is None:
            return
        instruction = instruction.strip()
        if not instruction:
            return
        if len(instruction) > 1200:
            messagebox.showwarning(
                "キャラ説明", "修正指示は1200文字以下にしてください",
                parent=self.window,
            )
            return
        self.busy = True
        self.status.set("LLMが自然文の修正指示を解釈中...")
        self._enable_actions()
        self.on_revise(current, instruction, self)

    def finish_revision(
        self, revised_text: str | None = None, error: str | None = None,
    ) -> None:
        """Called on Tk's main thread after a local LLM revision finishes."""
        if not self.is_open():
            return
        self.busy = False
        self.editor.configure(state="normal")
        if error:
            self.status.set("自然文の修正に失敗しました（元の文章は保持）")
            messagebox.showerror("キャラ説明", error, parent=self.window)
        elif revised_text is not None:
            self.editor.delete("1.0", "end")
            self.editor.insert("1.0", revised_text)
            self.status.set(
                "修正案を編集欄に反映しました。確認してから「修正内容を確定」を押してください"
            )
        self._enable_actions()

    def _show_analysis(self, analysis: dict) -> None:
        self.text_only = False
        self._feature_name = ""
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
        self.editor.configure(state="normal")
        if error:
            self.status.set("特徴抽出に失敗しました。保存済み特徴・履歴から読み込めます")
            messagebox.showerror("特徴抽出エラー", error, parent=self.window)
        elif analysis is not None:
            self._show_analysis(analysis)
            self.status.set(
                "日本語のキャラ説明を確認・修正して「修正内容を確定」を押してください"
            )
        self._enable_actions()

    def _text_only_evidence(self):
        self.evidence.configure(state="normal")
        self.evidence.delete("1.0", "end")
        self.evidence.insert("1.0", "文章のみのキャラ特徴（画像の再分析なし）\n"
                             "現在の参照画像は根拠として関連付けません。")
        self.evidence.configure(state="disabled")

    def load_feature_traits(self, traits, *, name="", origin="保存済み特徴"):
        """Replace only the editable text; user must confirm it explicitly."""
        if self.busy or not self.is_open():
            return False
        clean = normalize_approved(traits)
        existing = self.editor.get("1.0", "end-1c").strip()
        if existing and existing != clean:
            if not messagebox.askyesno("キャラ特徴", "編集中の文章を履歴の特徴文に置き換えますか？", parent=self.window):
                return False
        self.analysis = None
        self.text_only = True
        self._feature_name = name
        self._text_only_evidence()
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", clean)
        self.status.set(f"{origin}から特徴文を読み込みました。確認・確定してください")
        self._enable_actions()
        return True

    def load_history_traits(self, traits):
        return self.load_feature_traits(traits, origin="履歴")

    def save_feature(self):
        if self.busy or self.feature_store is None:
            return
        try:
            traits = normalize_approved(self.editor.get("1.0", "end-1c"))
            name = simpledialog.askstring("キャラ特徴の保存", "保存する名前",
                                         initialvalue=self._feature_name, parent=self.window)
            if name is None:
                return
            try:
                saved = self.feature_store.save(name, traits)
            except FeatureExistsError:
                if not messagebox.askyesno("上書き確認", "同名の特徴があります。上書きしますか？", parent=self.window):
                    return
                saved = self.feature_store.save(name, traits, overwrite=True)
            self._feature_name = saved.name
            self.status.set(f"「{saved.name}」を保存しました。生成への採用は「修正内容を確定」から")
        except (OSError, ValueError, RuntimeError, sqlite3.Error) as exc:
            messagebox.showerror("キャラ特徴の保存", str(exc), parent=self.window)

    def load_feature(self):
        if self.busy or self.feature_store is None:
            return
        try:
            saved = choose_saved_feature(self.window, self.feature_store)
            if saved is not None:
                self.load_feature_traits(saved.traits, name=saved.name)
        except (OSError, ValueError, RuntimeError, sqlite3.Error) as exc:
            messagebox.showerror("保存済み特徴", str(exc), parent=self.window)

    def import_history(self):
        if self.busy or self.on_history is None:
            return
        self.on_history(self)

    def confirm(self) -> None:
        if self.busy:
            return
        if self.analysis is None and not self.text_only:
            messagebox.showwarning(
                "キャラ参照", "先に共通特徴を抽出してください",
                parent=self.window,
            )
            return
        try:
            paths = () if self.text_only else validate_images(self.images)
            traits = normalize_approved(self.editor.get("1.0", "end"))
            self.on_confirm(paths, None if self.text_only else self.analysis, traits)
        except Exception as exc:
            messagebox.showerror("キャラ参照", str(exc), parent=self.window)
            return
        self.window.destroy()

    def clear_approved(self) -> None:
        self.on_clear()
        self.window.destroy()


def choose_history_traits(parent, entries):
    """Select a previously approved description without restoring other settings."""
    if not entries:
        messagebox.showinfo("キャラ特徴", "確定済みのキャラ特徴がある履歴がありません", parent=parent)
        return None
    dialog = tk.Toplevel(parent)
    dialog.title("履歴からキャラ特徴")
    dialog.transient(parent)
    dialog.geometry(f"{min(780, parent.winfo_screenwidth()-60)}x{min(540, parent.winfo_screenheight()-100)}")
    dialog.minsize(450, 320)
    outer = ttk.Frame(dialog, padding=10)
    outer.pack(fill="both", expand=True)
    actions = ttk.Frame(outer)
    actions.pack(side="bottom", fill="x", pady=(8, 0))
    rows = tk.Listbox(outer, height=7, exportselection=False, font=("Meiryo UI", 10))
    rows.pack(fill="both", expand=True)
    text = scrolledtext.ScrolledText(outer, height=8, wrap="word", state="disabled",
                                     font=("Meiryo UI", 10))
    text.pack(fill="both", expand=True, pady=(5, 0))
    # Repeated generations with exactly the same confirmed text appear once.
    unique = []
    seen = set()
    for entry in entries:
        traits = normalize_approved(entry.character_traits)
        if traits in seen:
            continue
        seen.add(traits)
        unique.append((entry, traits))
        label = " ".join(traits.split())[:90]
        rows.insert("end", f"{entry.created_at[:10]}  {label}")
    result = None

    def preview(_event=None):
        if not rows.curselection():
            return
        traits = unique[rows.curselection()[0]][1]
        text.configure(state="normal")
        text.delete("1.0", "end")
        text.insert("1.0", traits)
        text.configure(state="disabled")

    def accept(_event=None):
        nonlocal result
        if rows.curselection():
            result = unique[rows.curselection()[0]][1]
            dialog.destroy()

    rows.bind("<<ListboxSelect>>", preview)
    rows.bind("<Double-1>", accept)
    rows.selection_set(0)
    preview()
    ttk.Button(actions, text="取消", command=dialog.destroy).pack(side="right")
    ttk.Button(actions, text="特徴文を読み込む", command=accept).pack(side="right", padx=5)
    dialog.wait_visibility()
    dialog.grab_set()
    parent.wait_window(dialog)
    return result


def choose_saved_feature(parent, store):
    dialog = tk.Toplevel(parent)
    dialog.title("保存済みキャラ特徴")
    dialog.transient(parent)
    dialog.geometry(f"{min(700, parent.winfo_screenwidth()-60)}x{min(500, parent.winfo_screenheight()-100)}")
    dialog.minsize(420, 300)
    outer = ttk.Frame(dialog, padding=10)
    outer.pack(fill="both", expand=True)
    actions = ttk.Frame(outer)
    actions.pack(side="bottom", fill="x", pady=(8, 0))
    rows = tk.Listbox(outer, height=6, exportselection=False, font=("Meiryo UI", 10))
    rows.pack(fill="both", expand=True)
    text = scrolledtext.ScrolledText(outer, height=8, wrap="word", state="disabled",
                                     font=("Meiryo UI", 10))
    text.pack(fill="both", expand=True, pady=(5, 0))
    features = []
    result = None

    def selected():
        items = rows.curselection()
        return features[items[0]] if items else None

    def preview(_event=None):
        item = selected()
        text.configure(state="normal")
        text.delete("1.0", "end")
        if item is not None:
            text.insert("1.0", item.traits)
        text.configure(state="disabled")
        for button in (load, remove):
            button.configure(state="normal" if item is not None else "disabled")

    def refresh():
        nonlocal features
        features = store.list()
        rows.delete(0, "end")
        for item in features:
            rows.insert("end", item.name)
        if features:
            rows.selection_set(0)
        preview()

    def accept(_event=None):
        nonlocal result
        item = selected()
        if item is not None:
            result = item
            dialog.destroy()

    def delete():
        item = selected()
        if item is None or not messagebox.askyesno("特徴を削除", f"「{item.name}」を削除しますか？\n生成履歴・現在の確定特徴には影響しません。", parent=dialog):
            return
        try:
            store.delete(item.name)
            refresh()
        except (OSError, ValueError, sqlite3.Error) as exc:
            messagebox.showerror("特徴削除", str(exc), parent=dialog)

    remove = ttk.Button(actions, text="削除", command=delete)
    remove.pack(side="left")
    ttk.Button(actions, text="取消", command=dialog.destroy).pack(side="right")
    load = ttk.Button(actions, text="読み込む", command=accept)
    load.pack(side="right", padx=5)
    rows.bind("<<ListboxSelect>>", preview)
    rows.bind("<Double-1>", accept)
    try:
        refresh()
    except Exception:
        dialog.destroy()
        raise
    dialog.wait_visibility()
    dialog.grab_set()
    parent.wait_window(dialog)
    return result
