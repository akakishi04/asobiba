"""Modeless image refinement workspace; generation shares the application's worker."""
from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, simpledialog

from .comparison import ComparisonWindow, Image, ImageOps, ImageTk
from .generation_form import WORKFLOW_NAMES
from .ime_font import install_native_ime_font
from .parameters import OrchestratorError
from .single_prompt import LABELS
from .workflow_registry import sdxl_checkpoint_kind

DEFAULT_MODEL = "ワークフロー既定"
FIELD_LABELS = {"width": "幅", "height": "高さ", "steps": "Steps", "cfg": "CFG",
                "denoise": "Denoise", "control_strength": "ポーズ強度", "seed": "Seed"}


class ImageAdjustWindow(tk.Toplevel):
    def __init__(self, parent, draft, cache, models, *, on_action, on_close, on_cancel, status):
        super().__init__(parent)
        self.title("画像調整 | Asobiba")
        self.geometry("1260x760")
        self.minsize(880, 560)
        self.draft, self.cache = draft, cache
        self.models = tuple(models)
        self.on_action, self.on_close = on_action, on_close
        self.busy = False
        self.own_task = False
        self.editors, self.numeric, self.numeric_widgets = {}, {}, {}
        self.photos = {}
        self.language = tk.StringVar(master=self, value="英語")
        self._display_language = "英語"
        self.baseline = {}
        self.fixed_seed = tk.BooleanVar(master=self, value=True)
        self.checkpoint = tk.StringVar(master=self)
        self.workflow_label = tk.StringVar(master=self)
        self.input_label = tk.StringVar(master=self)
        self.base_title = tk.StringVar(master=self)
        self.result_title = tk.StringVar(master=self, value="調整結果")
        self.result_index = tk.StringVar(master=self)
        self.result_settings = tk.StringVar(master=self, value="")

        outer = ttk.Frame(self, padding=10)
        outer.pack(fill="both", expand=True)
        footer = ttk.Frame(outer)
        footer.pack(side="bottom", fill="x", pady=(8, 0))
        ttk.Label(footer, textvariable=status, wraplength=520).pack(side="left", fill="x", expand=True)
        self.close_button = ttk.Button(footer, text="閉じる", command=self._close)
        self.close_button.pack(side="right")
        self.generate_button = ttk.Button(footer, text="再生成", command=lambda: self._act("generate"))
        self.generate_button.pack(side="right", padx=6)
        self.cancel_button = ttk.Button(footer, text="中止", command=on_cancel)
        self.cancel_button.pack(side="right")
        self.seed_box = ttk.Checkbutton(footer, text="Seed固定", variable=self.fixed_seed)
        self.seed_box.pack(side="right", padx=6)

        panes = ttk.Panedwindow(outer, orient="horizontal")
        panes.pack(fill="both", expand=True)
        comparison, controls = ttk.Frame(panes), ttk.Frame(panes, padding=(8, 0, 0, 0))
        panes.add(comparison, weight=3)
        panes.add(controls, weight=2)
        images = ttk.Frame(comparison)
        images.pack(fill="both", expand=True)
        images.rowconfigure(1, weight=1)
        for col, (key, title) in enumerate((("base", self.base_title), ("latest", self.result_title))):
            images.columnconfigure(col, weight=1, uniform="images")
            ttk.Label(images, textvariable=title, anchor="center", wraplength=350).grid(
                row=0, column=col, sticky="ew", pady=(0, 4))
            label = ttk.Label(images, anchor="center", text="未生成" if key == "latest" else "")
            label.grid(row=1, column=col, sticky="nsew", padx=4)
            setattr(self, key + "_preview", label)
        bar = ttk.Frame(comparison)
        bar.pack(fill="x", pady=(6, 0))
        self.prev_button = ttk.Button(bar, text="‹", width=4, command=lambda: self._select(-1))
        self.prev_button.pack(side="left")
        ttk.Label(bar, textvariable=self.result_index, width=11, anchor="center").pack(side="left")
        self.next_button = ttk.Button(bar, text="›", width=4, command=lambda: self._select(1))
        self.next_button.pack(side="left")
        self.compare_button = ttk.Button(bar, text="拡大比較", command=self._compare)
        self.compare_button.pack(side="right")
        self.adopt_button = ttk.Button(bar, text="比較基準に採用", command=lambda: self._act("adopt"))
        self.adopt_button.pack(side="right", padx=4)
        self.result_position = -1
        ttk.Label(comparison, textvariable=self.result_settings, wraplength=680).pack(fill="x", pady=(4, 0))

        ttk.Label(controls, textvariable=self.workflow_label, style="FieldHeading.TLabel").pack(anchor="w", pady=(0, 6))
        tabs = ttk.Notebook(controls)
        tabs.pack(fill="both", expand=True)
        prompt, settings, sources = (ttk.Frame(tabs, padding=8) for _ in range(3))
        tabs.add(prompt, text="プロンプト")
        tabs.add(settings, text="生成設定")
        tabs.add(sources, text="参照素材")
        self.settings_frame = settings
        toolbar = ttk.Frame(prompt)
        toolbar.pack(fill="x", pady=(0, 6))
        self.language_box = ttk.Combobox(toolbar, textvariable=self.language, state="readonly",
                                         values=("英語", "日本語"), width=7)
        self.language_box.pack(side="left")
        self.language_box.bind("<<ComboboxSelected>>", self._switch)
        self.translate_button = ttk.Button(toolbar, text="日本語訳", command=lambda: self._act("translate"))
        self.translate_button.pack(side="left", padx=4)
        self.apply_button = ttk.Button(toolbar, text="編集反映", command=lambda: self._act("apply"))
        self.apply_button.pack(side="left")
        self.rewrite_button = ttk.Button(toolbar, text="修正指示", command=lambda: self._act("regenerate"))
        self.rewrite_button.pack(side="right")
        for key in draft.fields:
            ttk.Label(prompt, text=LABELS[key]).pack(anchor="w")
            editor = scrolledtext.ScrolledText(prompt, height=6 if key == "negative_prompt" else 12,
                                               wrap="word", undo=True, font=("Meiryo UI", 11))
            editor.pack(fill="both", expand=True, pady=(0, 6))
            install_native_ime_font(editor)
            self.editors[key] = editor
        self.revert_button = ttk.Button(prompt, text="編集を戻す", command=self.reload)
        self.revert_button.pack(anchor="e")
        ttk.Label(sources, textvariable=self.input_label, justify="left", wraplength=360).pack(fill="x", pady=(0, 8))
        self.i2i_button = ttk.Button(sources, text="比較基準を参照画像にする (I2I)",
                                     command=lambda: self._act("i2i"))
        self.i2i_button.pack(fill="x")
        ttk.Label(sources, text="I2Iへ切り替えると、元のマスク・ポーズ・構図参照は引き継ぎません。",
                  wraplength=340).pack(anchor="w", pady=8)
        self.protocol("WM_DELETE_WINDOW", self._close)
        self._build_settings()
        self.reload()
        self._show_images()

    def _build_settings(self):
        for widget in self.settings_frame.winfo_children():
            widget.destroy()
        self.numeric, self.numeric_widgets = {}, {}
        parent = self.settings_frame
        parent.columnconfigure(1, weight=1)
        row = 0
        self.model_box = None
        if self.draft.checkpoint_selectable:
            current = self.draft.parameters.get("checkpoint_model", DEFAULT_MODEL)
            names = tuple(dict.fromkeys((DEFAULT_MODEL, current, *(
                p for p in self.models if sdxl_checkpoint_kind(p) is not None
                and (self.draft.workflow_id == "wai_t2i_basic" or sdxl_checkpoint_kind(p) != "turbo")))))
            self.checkpoint.set(current)
            ttk.Label(parent, text="モデル").grid(row=row, column=0, sticky="w", pady=4, padx=(0, 8))
            self.model_box = ttk.Combobox(parent, textvariable=self.checkpoint, values=names, state="readonly")
            self.model_box.grid(row=row, column=1, sticky="ew", pady=4)
            self.model_box.bind("<<ComboboxSelected>>", self._model_changed)
            row += 1
        for key in self.draft.numeric_fields:
            variable = tk.StringVar(master=self, value=str(self.draft.parameters[key]))
            self.numeric[key] = variable
            ttk.Label(parent, text=FIELD_LABELS[key]).grid(row=row, column=0, sticky="w", padx=(0, 8), pady=4)
            widget = ttk.Entry(parent, textvariable=variable)
            widget.grid(row=row, column=1, sticky="ew", pady=4)
            self.numeric_widgets[key] = widget
            row += 1
        if "width" not in self.numeric:
            ttk.Label(parent, text="解像度: 参照画像に準拠").grid(row=row, column=0, columnspan=2, sticky="w", pady=4)
        self._model_changed()

    def _model_changed(self, _event=None):
        fixed = self.draft.fixed_sampler(self._checkpoint() or "")
        for key, value in (("steps", "4"), ("cfg", "1")):
            if fixed and key in self.numeric:
                self.numeric[key].set(value)
        self.set_busy(self.busy, own_task=self.own_task)

    def _checkpoint(self):
        return self.checkpoint.get() if self.model_box is not None and self.checkpoint.get() != DEFAULT_MODEL else None

    def _values(self):
        return {key: widget.get("1.0", "end-1c") for key, widget in self.editors.items()}

    def _read(self, *, applying=False):
        values = self._values()
        if self._display_language == "日本語":
            if not applying and values != self.baseline:
                raise OrchestratorError("日本語の編集を反映してから操作してください")
            values = self.draft.english()
        self.draft.apply_edits(values, {k: v.get() for k, v in self.numeric.items()}, self._checkpoint())

    def reload(self, *, rebuild=False):
        if rebuild:
            self._build_settings()
        ja = self.draft.japanese(self.cache)
        if self._display_language == "日本語" and not all(v is not None for v in ja.values()):
            self._display_language = "英語"
        self.language.set(self._display_language)
        values = ja if self._display_language == "日本語" else self.draft.english()
        for key, widget in self.editors.items():
            widget.configure(state="normal")
            widget.delete("1.0", "end")
            widget.insert("1.0", values[key] or "")
            widget.edit_reset()
        for key, variable in self.numeric.items():
            variable.set(str(self.draft.parameters[key]))
        if self.model_box is not None:
            self.checkpoint.set(self.draft.parameters.get("checkpoint_model", DEFAULT_MODEL))
        self.baseline = self._values()
        self.workflow_label.set("次の生成: " + WORKFLOW_NAMES.get(self.draft.workflow_id, self.draft.workflow_id))
        roles = (("実際の参照画像", "image"), ("マスク", "mask_image"), ("ポーズ", "pose_image"),
                 ("構図参考（プロンプト由来）", "composition_image"))
        self.input_label.set("\n".join(f"{label}: {'あり' if self.draft.assets.get(key) else 'なし'}"
                                       for label, key in roles))
        self.set_busy(self.busy, own_task=self.own_task)

    def set_busy(self, busy, *, own_task=False):
        self.busy, self.own_task = busy, own_task
        state = "disabled" if busy else "normal"
        for widget in (*self.editors.values(), self.generate_button, self.close_button, self.seed_box,
                       self.translate_button, self.rewrite_button, self.revert_button):
            widget.configure(state=state)
        self.language_box.configure(state="disabled" if busy else "readonly")
        self.apply_button.configure(state="normal" if not busy and self._display_language == "日本語" else "disabled")
        self.cancel_button.configure(state="normal" if busy and own_task else "disabled")
        fixed = self.draft.fixed_sampler(self._checkpoint() or "")
        for key, widget in self.numeric_widgets.items():
            widget.configure(state="disabled" if busy else "readonly" if fixed and key in ("steps", "cfg") else "normal")
        if self.model_box is not None:
            self.model_box.configure(state="disabled" if busy else "readonly")
        self.i2i_button.configure(state="normal" if not busy and self.draft.can_use_base_as_input() else "disabled")
        self._result_controls()

    def _switch(self, _event=None):
        desired = self.language.get()
        try:
            self._read()
            if desired == "日本語" and not all(v is not None for v in self.draft.japanese(self.cache).values()):
                self.language.set(self._display_language)
                self.on_action("translate")
                return
            self._display_language = desired
            self.reload()
        except OrchestratorError as exc:
            self.language.set(self._display_language)
            messagebox.showwarning("画像調整", str(exc), parent=self)

    def _act(self, operation):
        if self.busy:
            return
        try:
            self._read(applying=operation == "apply")
            if operation == "apply":
                self.on_action(operation, japanese=self._values())
            elif operation == "regenerate":
                text = simpledialog.askstring("修正指示", "変更したい内容", parent=self)
                if text is not None:
                    self.on_action(operation, instruction=text)
            elif operation == "adopt":
                self.draft.adopt_result(self.selected_result())
                self._show_images()
            elif operation == "i2i":
                if messagebox.askyesno("I2I編集", "比較基準を実際の参照画像に変更しますか？", parent=self):
                    self.draft.use_base_as_input()
                    self._display_language = "英語"
                    self.reload(rebuild=True)
            elif operation == "generate":
                self.on_action(operation, fixed_seed=self.fixed_seed.get())
            else:
                self.on_action(operation)
        except (OrchestratorError, OSError, ValueError) as exc:
            messagebox.showwarning("画像調整", str(exc), parent=self)

    def selected_result(self):
        return self.draft.results[self.result_position] if 0 <= self.result_position < len(self.draft.results) else None

    def _select(self, step):
        target = self.result_position + step
        if not self.busy and 0 <= target < len(self.draft.results):
            self.result_position = target
            self._show_images()

    def _result_controls(self):
        selected = self.selected_result()
        self.result_index.set(f"{self.result_position + 1}/{len(self.draft.results)}" if selected else "0/0")
        for widget, enabled in ((self.adopt_button, selected is not None),
                                (self.compare_button, selected is not None),
                                (self.prev_button, self.result_position > 0),
                                (self.next_button, self.result_position < len(self.draft.results) - 1)):
            widget.configure(state="normal" if enabled and not self.busy else "disabled")

    def _preview(self, key, path):
        label = getattr(self, key + "_preview")
        self.photos.pop(key, None)
        if path is None:
            label.configure(image="", text="未生成")
            return
        try:
            if Image is not None:
                with Image.open(path) as source:
                    if source.width * source.height > 80_000_000:
                        raise ValueError("画像が大きすぎます")
                    image = ImageOps.exif_transpose(source).convert("RGBA")
                    image.thumbnail((340, 510), Image.Resampling.LANCZOS)
                    photo = ImageTk.PhotoImage(image, master=self)
            else:
                full = tk.PhotoImage(master=self, file=str(path))
                scale = max(1, (full.width() + 339) // 340, (full.height() + 509) // 510)
                photo = full.subsample(scale, scale)
            self.photos[key] = photo
            label.configure(image=photo, text="")
        except (OSError, ValueError, tk.TclError):
            label.configure(image="", text="プレビュー非対応")

    def _show_images(self):
        self.base_title.set("比較基準 · " + self.draft.base_name)
        path = self.selected_result()
        self.result_title.set("調整結果 · " + path.name if path else "調整結果")
        params = self.draft.result_parameters[self.result_position] if path else {}
        self.result_settings.set("  ·  ".join(f"{FIELD_LABELS[k]} {params[k]}" for k in
                                 ("seed", "steps", "cfg", "denoise", "control_strength") if k in params))
        self._preview("base", self.draft.base_image)
        self._preview("latest", path)
        self._result_controls()

    def show_prompt_change(self, operation):
        if operation == "translate" and all(v is not None for v in self.draft.japanese(self.cache).values()):
            self._display_language = "日本語"
        self.reload()

    def show_completed(self):
        self.result_position = len(self.draft.results) - 1
        self.reload()
        self._show_images()

    def _compare(self):
        if self.selected_result() is not None:
            try:
                ComparisonWindow(self, self.draft.base_image, self.selected_result(), "比較基準", "調整結果")
            except (ValueError, OSError, tk.TclError) as exc:
                messagebox.showwarning("画像比較", str(exc), parent=self)

    def _close(self):
        if not self.busy:
            self.on_close()
