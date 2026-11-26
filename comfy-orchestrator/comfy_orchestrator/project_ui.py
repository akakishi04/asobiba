"""Embedded long-video workspace; editing state is independent of Tk."""
from __future__ import annotations

import os
import tkinter as tk
from dataclasses import dataclass
from tkinter import ttk, messagebox, scrolledtext

from .long_video import project_cut_lengths, first_changed_cut
from .parameters import OrchestratorError
from .timeline import FPS, format_cut_seconds, parse_cut_seconds, validate_cut_frames, validate_prompt_plan, GUIDE_CONNECTION_FRAMES
from .ui_theme import style_text_widget
from .video_preview import VideoPreview
from .ime_font import install_native_ime_font


@dataclass(frozen=True)
class ProjectAction:
    action: str
    prompt_plan: dict
    cut_frames: list[int]
    regenerate_from: int | None = None


class ProjectDraft:
    """The persisted manifest is immutable until an action creates a revision."""
    def __init__(self, manifest):
        self.manifest = manifest
        self.original = manifest.get("prompt_plan")
        self.original_cuts = project_cut_lengths(manifest)
        self.cuts = list(self.original_cuts)
        self.common = self.original["common"] if self.original else ""
        self.parts = list(self.original["segments"]) if self.original else []
        self.current = 0

    def plan(self):
        return {"common": self.common.strip(), "segments": [p.strip() for p in self.parts]}

    def changed_from(self):
        if self.original is None:
            return None
        return first_changed_cut(self.manifest, self.plan(), self.cuts)

    def dirty(self):
        return self.changed_from() is not None

    def valid_prefix(self):
        changed = self.changed_from()
        return min(len(self.manifest["segments"]), changed if changed is not None else len(self.cuts))

    def action(self, name, regenerate=False):
        if self.original is None:
            if name not in ("generate_join", "join"):
                raise OrchestratorError("旧形式は従来の再開・結合のみ対応します")
            return ProjectAction(name, {}, self.cuts)
        approved = validate_prompt_plan(self.plan(), len(self.cuts))
        if self.cuts != self.original_cuts:
            validate_cut_frames(self.cuts)
        if name == "join" and (self.dirty() or self.valid_prefix() != len(self.cuts)):
            raise OrchestratorError("変更のない全生成済みカットだけを結合できます")
        return ProjectAction(name, approved, list(self.cuts), self.current if regenerate else None)


class ProjectWorkspace(ttk.Frame):
    """Project picker, cut editor and video preview in the main application."""
    def __init__(self, master, store, *, on_refresh, on_action, on_load=None, on_actions_changed=None):
        super().__init__(master, padding=6)
        self.store = store
        self.on_refresh = on_refresh
        self.on_action = on_action
        self.on_load = on_load
        self.on_actions_changed = on_actions_changed
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
        self.summary = tk.StringVar(value="新規計画を作成するか、保存済みプロジェクトを選択")
        ttk.Label(self, textvariable=self.summary, wraplength=420).pack(fill="x", pady=(0, 2))
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
        self.preview_info = tk.StringVar(value="生成済みカットを選択してください")
        ttk.Label(self.preview_page, textvariable=self.preview_info, wraplength=420).pack(fill="x")
        self.external_button = ttk.Button(self.preview_page, text="外部プレイヤーで開く", command=self._external)
        self.external_button.pack(fill="x", pady=(4, 0))

        ttk.Label(self.edit_page, text="共通プロンプト").pack(anchor="w")
        self.common = scrolledtext.ScrolledText(self.edit_page, height=2, wrap="word",
                                                undo=True, font=("Meiryo UI", 10))
        self.common.pack(fill="x", pady=(0, 4))
        self.common.bind("<<Modified>>", self._changed)
        install_native_ime_font(self.common)
        timeline = ttk.Frame(self.edit_page)
        timeline.pack(fill="both", expand=True)
        self.cuts = ttk.Treeview(timeline, columns=("time", "state"), show="tree headings",
                                 selectmode="browse", height=4)
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

        bar = ttk.Frame(self.edit_page)
        bar.pack(fill="x", pady=3)
        self.duration = tk.StringVar()
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
        self.cut_prompt = scrolledtext.ScrolledText(self.edit_page, height=3, wrap="word",
                                                     undo=True, font=("Meiryo UI", 10))
        self.cut_prompt.pack(fill="x", pady=(0, 2))
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
        for widget in (self.common, self.cut_prompt, self.duration_entry,
                       self.apply_button, self.add_button, self.delete_button):
            widget.configure(state="normal" if editable else "disabled")
        self.selection.configure(state="readonly" if self.enabled else "disabled")
        self.refresh_button.configure(state="normal" if self.enabled else "disabled")
        available = self.available_actions()
        for key, button in self.action_buttons.items():
            button.configure(state="normal" if available[key] else "disabled")
        if self.on_actions_changed is not None:
            self.on_actions_changed(available)
        self.external_button.configure(state="normal" if self.enabled and self.preview.source is not None else "disabled")

    def available_actions(self):
        d = self.draft
        active = self.enabled and d is not None
        editable = active and d.original is not None
        return {"save": editable, "generate": editable, "regenerate": editable,
                "generate_join": active,
                "join": active and d.valid_prefix() == len(d.cuts) and not d.dirty() and not self._missing_clips,
                "preview": active and d.current < len(d.manifest["segments"])}

    def _read(self, *, strict=True):
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
        d.common = self.common.get("1.0", "end-1c")
        d.parts[d.current] = self.cut_prompt.get("1.0", "end-1c")
        return True

    def confirm_replace(self):
        if self.draft is None:
            return True
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
        self.views.select(self.edit_page)
        self.common.configure(state="normal")
        self.common.delete("1.0", "end")
        self.common.insert("1.0", self.draft.common)
        self.common.edit_modified(False)
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

    def _load_cut(self):
        d = self.draft
        self.duration.set(format_cut_seconds(d.cuts[d.current]))
        self.cut_prompt.configure(state="normal")
        self.cut_prompt.delete("1.0", "end")
        self.cut_prompt.insert("1.0", d.parts[d.current] if d.original else "旧形式の区間")
        self.cut_prompt.edit_modified(False)
        self.cut_prompt.edit_reset()

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
            if self.cuts.selection() != (str(d.current),):
                self.cuts.selection_set(str(d.current))
                self.cuts.see(str(d.current))
            status = "未保存の編集あり" if d.dirty() else {
                "draft": "計画保存", "generating": "途中", "ready_to_join": "結合待ち", "completed": "完成",
            }.get(d.manifest["state"], d.manifest["state"])
            overlap = d.manifest.get("overlap_frames", 0)
            method = ("ガイド 最大22f" if overlap == GUIDE_CONNECTION_FRAMES
                      else f"助走 最大{overlap}f" if overlap else "従来接続")
            self.summary.set(f"{len(d.cuts)}カット / {format_cut_seconds(sum(d.cuts))}秒 / "
                             f"有効 {d.valid_prefix()}件 · {status} · {method}")
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

    def _select_cut(self, _event=None):
        if self._updating or not self.enabled or not self.draft or not self.cuts.selection():
            return
        i = int(self.cuts.selection()[0])
        if i == self.draft.current:
            return
        if not self._read():
            self.cuts.selection_set(str(self.draft.current))
            return
        self.draft.current = i
        self._updating = True
        self._load_cut()
        self._updating = False
        self._refresh_rows()

    def _apply(self, _event=None):
        if self.enabled and self._read():
            self._refresh_rows()

    def _add(self):
        d = self.draft
        if self.enabled and d and len(d.cuts) < 300 and self._read():
            d.current += 1
            d.cuts.insert(d.current, 5 * FPS)
            d.parts.insert(d.current, "")
            self._updating = True
            self._load_cut()
            self._updating = False
            self._refresh_rows()

    def _delete(self):
        d = self.draft
        if self.enabled and d and len(d.cuts) > 2 and self._read():
            d.cuts.pop(d.current)
            d.parts.pop(d.current)
            d.current = min(d.current, len(d.cuts) - 1)
            self._updating = True
            self._load_cut()
            self._updating = False
            self._refresh_rows()

    def _show_preview(self):
        d = self.draft
        if not d or d.current >= len(d.manifest["segments"]):
            return
        path = self.store.asset(d.manifest, d.manifest["segments"][d.current]["file"])
        if not path.is_file():
            messagebox.showerror("動画確認", "生成動画が見つかりません", parent=self)
            return
        self.preview.set_source(path)
        self.preview_info.set(f"カット{d.current+1} · 元クリップ（トリミング前）")
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
            action = d.action("generate" if key == "regenerate" else key, key == "regenerate")
            # The application confirms once, after accounting for BOTH the
            # live generation settings and the edited cut plan.
            self.on_action(d.manifest, action)
        except (OSError, ValueError, KeyError, OrchestratorError) as exc:
            messagebox.showerror("長尺プロジェクト", str(exc), parent=self)
