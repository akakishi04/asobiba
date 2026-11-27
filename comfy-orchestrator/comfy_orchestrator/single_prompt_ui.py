"""Small modal editor for reviewed single images and videos."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog

from .ime_font import install_native_ime_font
from .parameters import OrchestratorError
from .single_prompt import LABELS


class SinglePromptWindow(tk.Toplevel):
    def __init__(self, parent, draft, cache, *, on_action, on_close, on_cancel, status):
        super().__init__(parent)
        self.title("プロンプト確認")
        self.transient(parent)
        self.geometry("720x600")
        self.minsize(440, 320)
        self.draft = draft
        self.cache = cache
        self.on_action = on_action
        self.on_close = on_close
        self.busy = False
        self.language = tk.StringVar(master=self, value="日本語" if self._has_japanese() else "英語")
        self._display_language = self.language.get()
        self.baseline = {}
        self.editors = {}
        panel = ttk.Frame(self, padding=10)
        panel.pack(fill="both", expand=True)
        toolbar = ttk.Frame(panel)
        toolbar.pack(fill="x", pady=(0, 6))
        self.language_box = ttk.Combobox(toolbar, values=("日本語", "英語"), textvariable=self.language,
                                         state="readonly", width=8)
        self.language_box.pack(side="left")
        self.language_box.bind("<<ComboboxSelected>>", self._switch)
        self.translate_button = ttk.Button(toolbar, text="日本語訳", command=lambda: self._act("translate"))
        self.translate_button.pack(side="left", padx=(6, 0))
        self.apply_button = ttk.Button(toolbar, text="編集反映", command=lambda: self._act("apply"))
        self.apply_button.pack(side="left", padx=(6, 0))
        self.revert_button = ttk.Button(toolbar, text="元に戻す", command=self.reload)
        self.revert_button.pack(side="left", padx=(6, 0))
        self.rewrite_button = ttk.Button(toolbar, text="プロンプト再生成", command=lambda: self._act("regenerate"))
        self.rewrite_button.pack(side="right")
        footer = ttk.Frame(panel)
        footer.pack(side="bottom", fill="x", pady=(6, 0))
        self.generate_button = ttk.Button(footer, text="生成", command=lambda: self._act("generate"))
        self.generate_button.pack(side="right")
        self.close_button = ttk.Button(footer, text="閉じる", command=self._close)
        self.close_button.pack(side="right", padx=(0, 6))
        self.cancel_button = ttk.Button(footer, text="中止", command=on_cancel, state="disabled")
        self.cancel_button.pack(side="right", padx=(0, 6))
        ttk.Label(footer, textvariable=status, wraplength=330).pack(side="left", fill="x", expand=True)
        for key in draft.fields:
            ttk.Label(panel, text=LABELS[key]).pack(anchor="w")
            editor = scrolledtext.ScrolledText(panel, height=4 if key == "negative_prompt" else 12,
                                                wrap="word", undo=True, font=("Meiryo UI", 11))
            editor.pack(fill="both", expand=key == "positive_prompt", pady=(0, 5))
            install_native_ime_font(editor)
            self.editors[key] = editor
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.reload()
        self.grab_set()

    def _has_japanese(self):
        return all(value is not None for value in self.draft.japanese(self.cache).values())

    def _values(self):
        return {key: widget.get("1.0", "end-1c") for key, widget in self.editors.items()}

    def _read(self):
        values = self._values()
        if self._display_language == "英語":
            self.draft.set_english(values)
        elif values != self.baseline:
            raise OrchestratorError("日本語の編集を反映してから操作してください")

    def reload(self):
        if self._display_language == "日本語" and not self._has_japanese():
            self._display_language = "英語"
        self.language.set(self._display_language)
        values = (self.draft.japanese(self.cache) if self._display_language == "日本語" else self.draft.english())
        for key, widget in self.editors.items():
            widget.configure(state="normal")
            widget.delete("1.0", "end")
            widget.insert("1.0", values[key] or "")
            widget.edit_reset()
        self.baseline = self._values()
        self.set_busy(self.busy)

    def set_busy(self, busy):
        self.busy = busy
        for widget in self.editors.values():
            widget.configure(state="disabled" if busy else "normal")
        for button in (self.translate_button, self.rewrite_button, self.generate_button, self.close_button):
            button.configure(state="disabled" if busy else "normal")
        self.apply_button.configure(state="normal" if not busy and self._display_language == "日本語" else "disabled")
        self.revert_button.configure(state="disabled" if busy else "normal")
        self.cancel_button.configure(state="normal" if busy else "disabled")
        self.language_box.configure(state="disabled" if busy else "readonly")

    def _switch(self, _event=None):
        desired = self.language.get()
        try:
            self._read()
        except OrchestratorError as exc:
            self.language.set(self._display_language)
            messagebox.showwarning("プロンプト確認", str(exc), parent=self)
            return
        self._display_language = desired
        if desired == "日本語" and not self._has_japanese():
            self._display_language = "英語"
            self.language.set("英語")
            self.on_action("translate")
        else:
            self.reload()

    def _act(self, operation):
        if self.busy:
            return
        try:
            if operation == "apply":
                if self._display_language != "日本語":
                    return
                self.on_action(operation, japanese=self._values())
                return
            self._read()
            if operation == "regenerate":
                instruction = simpledialog.askstring("プロンプト再生成", "修正指示（空欄可）", parent=self)
                if instruction is None:
                    return
                self.on_action(operation, instruction=instruction)
            else:
                self.on_action(operation)
        except OrchestratorError as exc:
            messagebox.showwarning("プロンプト確認", str(exc), parent=self)

    def _close(self):
        if not self.busy:
            self.on_close()
