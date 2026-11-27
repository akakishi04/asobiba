"""Embedded long-video workspace; editing state is independent of Tk."""
from __future__ import annotations

import os
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog

from .project_draft import ProjectDraft, ProjectAction, available_project_actions
from .parameters import OrchestratorError
from .h3_prompt import FORMAT as H3_OFFICIAL_FORMAT
from .prompt_review import TranslationCache
from .timeline import FPS, format_cut_seconds, parse_cut_seconds, validate_cut_frames, validate_prompt_plan, GUIDE_CONNECTION_FRAMES
from .ui_theme import style_text_widget
from .video_preview import VideoPreview
from .ime_font import install_native_ime_font


class ProjectWorkspace(ttk.Frame):
    """Project picker, cut editor and video preview in the main application."""
    def __init__(self, master, store, *, on_refresh, on_action, on_load=None, on_actions_changed=None,
                 on_prompt_action=None):
        super().__init__(master, padding=6)
        self.store = store
        self.on_refresh = on_refresh
        self.on_action = on_action
        self.on_load = on_load
        self.on_actions_changed = on_actions_changed
        self.on_prompt_action = on_prompt_action
        self.translation_cache = TranslationCache(store.root.parent / "h3_japanese.sqlite3")
        self._display_language = "日本語"
        self._ja_baseline = {"common": None, "cut": None}
        self.draft = None
        self.projects = []
        self.enabled = True
        self._updating = False
        self._row_update_pending = None
        self._missing_clips = set()

        picker = ttk.Frame(self)
        picker.pack(fill="x", pady=(0, 4))
        self.selection = ttk.Combobox(picker, state="readonly", width=22)
        self.selection.pack(side="left", fill="x", expand=True)
        self.selection.bind("<<ComboboxSelected>>", self._choose)
        self.refresh_button = ttk.Button(picker, text="更新", command=on_refresh, width=5)
        self.refresh_button.pack(side="right", padx=(4, 0))
        self.summary = tk.StringVar(value="")
        ttk.Label(self, textvariable=self.summary, style="Muted.TLabel").pack(fill="x", pady=(0, 2))
        actions = ttk.Frame(self)
        actions.pack(side="bottom", fill="x", pady=(4, 0))
        self.action_buttons = {}
        for i, (key, label) in enumerate((
            ("save", "計画保存"), ("preview", "カット確認"),
        )):
            command = self._show_preview if key == "preview" else lambda k=key: self._accept(k)
            button = ttk.Button(actions, text=label, command=command, style="Compact.TButton")
            button.grid(row=0, column=i, sticky="ew", padx=2, pady=2)
            actions.columnconfigure(i, weight=1)
            self.action_buttons[key] = button

        self.views = ttk.Notebook(self)
        self.views.pack(fill="both", expand=True)
        self.edit_page = ttk.Frame(self.views, padding=4)
        self.preview_page = ttk.Frame(self.views, padding=4)
        self.views.add(self.edit_page, text="カット編集")
        self.views.add(self.preview_page, text="プレビュー")
        self.views.bind("<<NotebookTabChanged>>", self._view_changed)
        self.preview = VideoPreview(self.preview_page, height=160)
        self.preview.pack(fill="both", expand=True)
        self.preview_info = tk.StringVar(value="")
        ttk.Label(self.preview_page, textvariable=self.preview_info, wraplength=420).pack(fill="x")
        self.external_button = ttk.Button(self.preview_page, text="外部で開く", command=self._external)
        self.external_button.pack(fill="x", pady=(4, 0))

        language_bar = ttk.Frame(self.edit_page)
        language_bar.pack(fill="x", pady=(0, 3))
        self.prompt_language = tk.StringVar(value=self._display_language)
        self.language_box = ttk.Combobox(language_bar, textvariable=self.prompt_language,
                                         values=("日本語", "H3用英語"), state="readonly", width=8)
        language_bar.columnconfigure(0, weight=1)
        self.language_box.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self.language_box.bind("<<ComboboxSelected>>", self._switch_language)
        self.translate_button = ttk.Button(language_bar, text="日本語訳", command=lambda: self._prompt_action("translate"),
                                           style="Compact.TButton")
        self.translate_button.grid(row=0, column=1, padx=2, sticky="ew")
        self.translate_all_button = ttk.Button(language_bar, text="一括翻訳",
                                               command=lambda: self._prompt_action("translate_all"),
                                               style="Compact.TButton")
        self.translate_all_button.grid(row=0, column=2, padx=2, sticky="ew")
        self.apply_ja_button = ttk.Button(language_bar, text="編集反映", command=lambda: self._prompt_action("apply"),
                                          style="Compact.TButton")
        self.apply_ja_button.grid(row=0, column=1, padx=2, sticky="ew")
        self.revert_ja_button = ttk.Button(language_bar, text="元に戻す", command=self._revert_japanese,
                                           style="Compact.TButton")
        self.revert_ja_button.grid(row=0, column=2, padx=2, sticky="ew")
        self.apply_ja_button.grid_remove()
        self.revert_ja_button.grid_remove()
        ttk.Label(self.edit_page, text="共通プロンプト", style="FieldHeading.TLabel").pack(anchor="w")
        self.common = scrolledtext.ScrolledText(self.edit_page, height=2, wrap="word",
                                                undo=True, font=("Meiryo UI", 10))
        self.common.pack(fill="x", pady=(0, 4))
        self.common.bind("<<Modified>>", self._changed)
        install_native_ime_font(self.common)
        cut_panes = ttk.Panedwindow(self.edit_page, orient="vertical")
        cut_panes.pack(fill="both", expand=True)
        cut_list = ttk.Frame(cut_panes)
        cut_editor = ttk.Frame(cut_panes)
        cut_panes.add(cut_list, weight=1)
        cut_panes.add(cut_editor, weight=2)

        selection_bar = ttk.Frame(cut_list)
        selection_bar.pack(side="bottom", fill="x", pady=(3, 0))
        self.select_all_button = ttk.Button(selection_bar, text="全選択", command=self._select_all,
                                            style="Compact.TButton")
        self.select_all_button.pack(side="left")
        self.rewrite_button = ttk.Button(selection_bar, text="プロンプト再生成",
                                         command=lambda: self._prompt_action("regenerate"),
                                         style="Compact.TButton")
        self.rewrite_button.pack(side="right")

        timeline = ttk.Frame(cut_list)
        timeline.pack(fill="both", expand=True)
        self.cuts = ttk.Treeview(timeline, columns=("time", "state"), show="tree headings",
                                 selectmode="extended", height=3)
        self.cuts.heading("#0", text="カット")
        self.cuts.heading("time", text="時間")
        self.cuts.heading("state", text="状態")
        self.cuts.column("#0", width=52, minwidth=44, stretch=False)
        self.cuts.column("time", width=110, minwidth=80)
        self.cuts.column("state", width=85, minwidth=65)
        scroll = ttk.Scrollbar(timeline, orient="vertical", command=self.cuts.yview)
        self.cuts.configure(yscrollcommand=scroll.set)
        self.cuts.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.cuts.bind("<<TreeviewSelect>>", self._select_cut)
        self.cuts.bind("<Control-a>", self._select_all)
        self.cuts.bind("<Control-A>", self._select_all)

        bar = ttk.Frame(cut_editor)
        bar.pack(fill="x", pady=3)
        self.duration = tk.StringVar()
        self.cut_title = tk.StringVar(value="カット")
        ttk.Label(bar, textvariable=self.cut_title, style="FieldHeading.TLabel").pack(side="left", padx=(0, 6))
        ttk.Label(bar, text="秒").pack(side="left")
        self.duration_entry = ttk.Entry(bar, width=7, textvariable=self.duration)
        self.duration_entry.pack(side="left", padx=3)
        self.duration_entry.bind("<Return>", self._apply)
        self.apply_button = ttk.Button(bar, text="反映", command=self._apply, style="Compact.TButton")
        self.apply_button.pack(side="left")
        self.delete_button = ttk.Button(bar, text="削除", command=self._delete, style="Compact.TButton")
        self.delete_button.pack(side="right")
        self.add_button = ttk.Button(bar, text="追加", command=self._add, style="Compact.TButton")
        self.add_button.pack(side="right", padx=3)
        self.cut_prompt = scrolledtext.ScrolledText(cut_editor, height=5, wrap="word",
                                                     undo=True, font=("Meiryo UI", 10))
        self.cut_prompt.pack(fill="both", expand=True, pady=(0, 2))
        self.cut_prompt.bind("<<Modified>>", self._changed)
        install_native_ime_font(self.cut_prompt)
        self._states()

    def apply_theme(self, colors):
        style_text_widget(self.common, colors)
        style_text_widget(self.cut_prompt, colors)

    def set_enabled(self, enabled):
        self.enabled = bool(enabled)
        self._states()
        self.preview.set_enabled(self.enabled)

    def stop_preview(self):
        self.preview.stop()

    def _states(self):
        exists = self.draft is not None
        editable = exists and self.draft.original is not None and self.enabled
        pending = bool(self._edited_japanese()) if editable else False
        japanese = self._display_language == "日本語"
        count = len(self.draft.selected_indices()) if exists else 0
        single = count == 1
        for kind, widget in (("common", self.common), ("cut", self.cut_prompt)):
            ready = editable and (kind == "common" or single) and (not japanese or self._ja_baseline[kind] is not None)
            widget.configure(state="normal" if ready else "disabled")
        for widget in (self.duration_entry, self.apply_button):
            widget.configure(state="normal" if editable and single and not pending else "disabled")
        self.add_button.configure(state="normal" if editable and single and not pending and len(self.draft.cuts) < 300
                                  else "disabled")
        self.delete_button.configure(state="normal" if editable and single and not pending and len(self.draft.cuts) > 2
                                     else "disabled")
        self.language_box.configure(state="readonly" if editable and not pending else "disabled")
        for widget in (self.translate_button, self.translate_all_button):
            widget.grid() if japanese and not pending else widget.grid_remove()
        for widget in (self.apply_ja_button, self.revert_ja_button):
            widget.grid() if japanese and pending else widget.grid_remove()
        self.select_all_button.configure(state="normal" if editable and not pending and count < len(self.draft.cuts)
                                         else "disabled")
        service = editable and self.on_prompt_action is not None
        self.translate_button.configure(state="normal" if service and single and japanese and not pending
                                        and any(v is None for v in self._ja_baseline.values()) else "disabled")
        untranslated = (len(self.translation_cache.missing(self.draft.plan()))
                        if service and japanese and not pending else 0)
        self.translate_all_button.configure(
            text=f"一括翻訳({untranslated})" if untranslated else "一括翻訳",
            state="normal" if untranslated else "disabled",
        )
        self.apply_ja_button.configure(state="normal" if service and japanese and pending else "disabled")
        self.revert_ja_button.configure(state="normal" if editable and japanese and pending else "disabled")
        self.rewrite_button.configure(
            text=f"プロンプト再生成 ({count})" if count > 1 else "プロンプト再生成",
            state="normal" if service and not pending else "disabled",
        )
        self.selection.configure(state="readonly" if self.enabled else "disabled")
        self.refresh_button.configure(state="normal" if self.enabled else "disabled")
        available = self.available_actions()
        for key, button in self.action_buttons.items():
            button.configure(state="normal" if available[key] else "disabled")
        if self.on_actions_changed is not None:
            self.on_actions_changed(available)
        self.external_button.configure(state="normal" if self.enabled and self.preview.source is not None else "disabled")

    def available_actions(self):
        pending = bool(getattr(self, "_ja_baseline", None) and self._edited_japanese())
        return available_project_actions(self.draft, enabled=self.enabled, pending=pending,
                                         missing_clips=self._missing_clips)

    def _read(self, *, strict=True, allow_japanese_edits=False):
        if not self.draft or self.draft.original is None:
            return True
        d = self.draft
        raw = self.duration.get().strip()
        try:
            if raw != format_cut_seconds(d.cuts[d.current]):
                d.cuts[d.current] = parse_cut_seconds(raw)
        except OrchestratorError as exc:
            if strict:
                messagebox.showerror("カット設定", str(exc), parent=self)
                return False
        if self._display_language == "日本語":
            if self._edited_japanese() and not allow_japanese_edits:
                if strict:
                    messagebox.showwarning("日本語の未反映編集",
                                           "「編集反映」で英語に反映するか「元に戻す」を押してください。",
                                           parent=self)
                return False
        else:
            d.common = self.common.get("1.0", "end-1c")
            d.parts[d.current] = self.cut_prompt.get("1.0", "end-1c")
        return True

    def confirm_replace(self):
        if self.draft is None:
            return True
        if self._edited_japanese():
            return messagebox.askyesno("未反映の日本語編集",
                                       "未反映の日本語編集と未保存の計画編集を破棄しますか？", parent=self)
        if not self._read():
            return messagebox.askyesno("未保存の編集", "不正な秒数を含む未保存の編集を破棄しますか？", parent=self)
        if not self.draft.dirty():
            return True
        return messagebox.askyesno("未保存の編集", "未保存のカット編集を破棄しますか？", parent=self)

    def set_projects(self, projects, preferred=None, *, open_preferred=False):
        self.projects = list(projects)
        names = []
        for p in self.projects:
            title = " ".join(p["request"].split())[:32] or "参照画像のみ"
            if p.get("revision"):
                title = f"改訂{p['revision']} · {title}"
            names.append(f"{title} [{len(p['segments'])}/{len(p['plan'])}] {p['run_id'][:8]}")
        self.selection.configure(values=names)
        current = self.draft.manifest["run_id"] if self.draft else None
        target = preferred if open_preferred and preferred else current or preferred
        index = next((i for i, p in enumerate(self.projects) if p["run_id"] == target), None)
        if index is not None:
            self.selection.current(index)
            if open_preferred or self.draft is None:
                self.load(self.projects[index])
            elif self.enabled and self._read(strict=False) and not self.draft.dirty():
                self.checkpoint(self.projects[index])
        elif self.draft is None:
            # Entering the mode must not silently overwrite the shared
            # reference image/prompt with an unrelated previous project.
            self.selection.set("")

    def load(self, manifest, *, preserve_selection=False, restore_inputs=True):
        old = self.draft
        self.draft = ProjectDraft(manifest)
        self._update_clip_presence()
        if preserve_selection and old is not None:
            self.draft.current = min(old.current, len(self.draft.cuts) - 1)
        self._updating = True
        self.preview.set_source(None)
        self.preview_info.set("")
        self.views.select(self.edit_page)
        self._load_cut()
        self._updating = False
        self._refresh_rows()
        if restore_inputs and self.on_load is not None:
            self.on_load(manifest)

    def checkpoint(self, manifest):
        # Checkpoints arrive only while the project is being executed; no edits
        # can race with the worker's persisted state.
        if self.draft and self.draft.manifest["run_id"] == manifest["run_id"]:
            self.draft.manifest = manifest
            self._update_clip_presence()
            self._refresh_rows()

    def _choose(self, _event=None):
        if not self.enabled:
            return
        i = self.selection.current()
        if not 0 <= i < len(self.projects):
            return
        if self.draft and self.projects[i]["run_id"] == self.draft.manifest["run_id"]:
            return
        if not self.confirm_replace():
            old = self.draft.manifest["run_id"]
            j = next((j for j, p in enumerate(self.projects) if p["run_id"] == old), None)
            if j is not None:
                self.selection.current(j)
            return
        self.load(self.projects[i])

    def _edited_japanese(self):
        if self._display_language != "日本語" or not self.draft or not self.draft.original:
            return {}
        edited = {}
        for kind, widget in (("common", self.common), ("cut", self.cut_prompt)):
            baseline = self._ja_baseline[kind]
            if baseline is not None:
                value = widget.get("1.0", "end-1c").strip()
                if value != baseline.strip():
                    edited[kind] = value
        return edited

    def _load_cut(self):
        d = self.draft
        self.duration.set(format_cut_seconds(d.cuts[d.current]))
        self.cut_title.set(f"カット {d.current+1:02d}")
        raw = {"common": d.common.strip(), "cut": d.parts[d.current].strip() if d.original else ""}
        official = bool(d.original and d.original.get("format") == H3_OFFICIAL_FORMAT)
        self._ja_baseline = {"common": None, "cut": None}
        for kind, widget in (("common", self.common), ("cut", self.cut_prompt)):
            value = raw[kind]
            if not d.original:
                value = "旧形式の区間" if kind == "cut" else ""
            elif self._display_language == "日本語":
                translated = self.translation_cache.get(kind, value, official)
                self._ja_baseline[kind] = translated
                value = translated if translated is not None else "未翻訳"
            widget.configure(state="normal")
            widget.delete("1.0", "end")
            widget.insert("1.0", value)
            widget.edit_modified(False)
            widget.edit_reset()

    def _switch_language(self, _event=None):
        target = self.prompt_language.get()
        if target == self._display_language:
            return
        if not self.enabled or not self.draft or not self._read():
            self.prompt_language.set(self._display_language)
            return
        self._display_language = target
        self._updating = True
        try:
            self._load_cut()
        finally:
            self._updating = False
        self._refresh_rows()

    def _revert_japanese(self):
        if self.enabled and self.draft and self._display_language == "日本語":
            self._updating = True
            try:
                self._load_cut()
            finally:
                self._updating = False
            self._refresh_rows()

    def _prompt_action(self, operation):
        d = self.draft
        if not self.enabled or not d or not d.original or self.on_prompt_action is None:
            return
        if not self._read(allow_japanese_edits=operation == "apply"):
            return
        edited = self._edited_japanese() if operation == "apply" else {}
        if operation == "apply" and not edited:
            return
        instruction = ""
        options = {}
        if operation == "regenerate":
            targets = d.selected_indices()
            label = f"カット{targets[0]+1}" if len(targets) == 1 else f"選択 {len(targets)}カット"
            instruction = simpledialog.askstring(
                f"{label}のプロンプト再生成", "修正指示（任意）", parent=self,
            )
            if instruction is None:
                return
            options["selected_indices"] = targets
        try:
            self.on_prompt_action(d.manifest, d.plan(), list(d.cuts), d.current,
                                  operation, edited, instruction, self.translation_cache, **options)
        except (OSError, ValueError, KeyError, OrchestratorError) as exc:
            messagebox.showerror("プロンプト編集", str(exc), parent=self)

    def accept_prompt_result(self, run_id, cuts, result):
        if self.draft is None or not self.draft.accept_prompt_result(run_id, cuts, result):
            return False
        self._updating = True
        try:
            self._load_cut()
        finally:
            self._updating = False
        self._refresh_rows()
        return True

    def _update_clip_presence(self):
        self._missing_clips = {i for i, segment in enumerate(self.draft.manifest["segments"])
                               if not self.store.asset(self.draft.manifest, segment["file"]).is_file()}

    def _refresh_rows(self):
        d = self.draft
        if d is None:
            return
        self._updating = True
        try:
            changed = d.changed_from()
            existing = self.cuts.get_children()
            if len(existing) != len(d.cuts):
                self.cuts.delete(*existing)
                for i in range(len(d.cuts)):
                    self.cuts.insert("", "end", iid=str(i))
            start = 0
            for i, count in enumerate(d.cuts):
                status = "未生成"
                if i < len(d.manifest["segments"]):
                    status = "生成済" if changed is None or i < changed else "要再生成"
                    if i in self._missing_clips:
                        status = "ファイルなし"
                self.cuts.item(str(i), text=f"{i+1:02d}",
                               values=(f"{start/FPS:.2f}–{(start+count)/FPS:.2f}s", status))
                start += count
            selected = tuple(str(i) for i in d.selected_indices())
            if set(self.cuts.selection()) != set(selected):
                self.cuts.selection_set(*selected)
            if self.cuts.focus() != str(d.current):
                self.cuts.focus(str(d.current))
                self.cuts.see(str(d.current))
            status = "日本語の未反映編集あり" if self._edited_japanese() else "未保存の編集あり" if d.dirty() else {
                "draft": "計画保存", "generating": "途中", "ready_to_join": "結合待ち", "completed": "完成",
            }.get(d.manifest["state"], d.manifest["state"])
            overlap = d.manifest.get("overlap_frames", 0)
            legacy = f" · 旧助走 {overlap}f" if overlap and overlap != GUIDE_CONNECTION_FRAMES else ""
            self.summary.set(f"{format_cut_seconds(sum(d.cuts))}秒 · "
                             f"有効 {d.valid_prefix()}/{len(d.cuts)} · {status}{legacy}")
        finally:
            self._updating = False
        self._states()

    def _changed(self, event):
        widget = event.widget
        if not widget.edit_modified():
            return
        widget.edit_modified(False)
        if self._updating or not self.enabled or self.draft is None:
            return
        self._read(strict=False)
        if self._row_update_pending is not None:
            self.after_cancel(self._row_update_pending)
        self._row_update_pending = self.after(120, self._flush_rows)

    def _flush_rows(self):
        self._row_update_pending = None
        self._refresh_rows()

    def _select_all(self, _event=None):
        if self.enabled and self.draft and self.draft.original and self._read():
            self.cuts.selection_set(*self.cuts.get_children())
            self._select_cut()
        return "break"

    def _select_cut(self, _event=None):
        if self._updating or not self.draft:
            return
        d = self.draft
        selected = tuple(sorted(int(i) for i in self.cuts.selection()))
        focus = self.cuts.focus()
        focus = int(focus) if focus else None
        old = d.selected_indices()
        current = d.current
        if selected == old and (focus not in selected or focus == current):
            return
        if not self.enabled or not selected or not self._read():
            self.cuts.focus(str(current))
            if selected != old:
                self.cuts.selection_set(*(str(i) for i in old))
            return
        if not d.original:
            selected = (focus if focus in selected else selected[0],)
        d.select_cuts(selected, focus)
        if d.current != current:
            self._updating = True
            try:
                self._load_cut()
            finally:
                self._updating = False
        self._refresh_rows()

    def _apply(self, _event=None):
        if self.enabled and self._read():
            self._refresh_rows()

    def _add(self):
        d = self.draft
        if self.enabled and d and len(d.selected_indices()) == 1 and len(d.cuts) < 300 and self._read():
            d.current += 1
            d.cuts.insert(d.current, 5 * FPS)
            d.parts.insert(d.current, "")
            d.selected = (d.current,)
            self._updating = True
            self._load_cut()
            self._updating = False
            self._refresh_rows()

    def _delete(self):
        d = self.draft
        if self.enabled and d and len(d.selected_indices()) == 1 and len(d.cuts) > 2 and self._read():
            d.cuts.pop(d.current)
            d.parts.pop(d.current)
            d.current = min(d.current, len(d.cuts) - 1)
            d.selected = (d.current,)
            self._updating = True
            self._load_cut()
            self._updating = False
            self._refresh_rows()

    def _show_preview(self):
        d = self.draft
        if not self.enabled or not d or len(d.selected_indices()) != 1 or d.current >= len(d.manifest["segments"]):
            return
        path = self.store.asset(d.manifest, d.manifest["segments"][d.current]["file"])
        if not path.is_file():
            messagebox.showerror("動画確認", "生成動画が見つかりません", parent=self)
            return
        self.preview.set_source(path)
        self.preview_info.set(f"カット {d.current+1:02d} · 元クリップ")
        self.views.select(self.preview_page)
        self._states()

    def _view_changed(self, _event=None):
        if self.views.select() != str(self.preview_page):
            self.preview.stop()

    def _external(self):
        try:
            if self.preview.source is None or os.name != "nt":
                raise OSError("動画を開く機能はWindows専用です")
            os.startfile(str(self.preview.source))
        except OSError as exc:
            messagebox.showerror("動画確認", str(exc), parent=self)

    def _accept(self, key):
        if not self.enabled or not self.draft or not self._read():
            return
        try:
            d = self.draft
            if key == "regenerate" and len(d.selected_indices()) != 1:
                return
            action = d.action("generate" if key == "regenerate" else key, key == "regenerate")
            # The application confirms once, after accounting for BOTH the
            # live generation settings and the edited cut plan.
            self.on_action(d.manifest, action)
        except (OSError, ValueError, KeyError, OrchestratorError) as exc:
            messagebox.showerror("長尺プロジェクト", str(exc), parent=self)
