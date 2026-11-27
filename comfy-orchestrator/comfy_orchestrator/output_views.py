"""Independent result and history views. All operations are injected commands."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable
from pathlib import Path
import tkinter as tk
from tkinter import ttk

from .video_preview import VideoPreview
from .preview_geometry import preview_subsample
from .output_collection import IMAGE_EXTENSIONS, is_video_output
from .history import HistoryEntry
from .history_presentation import history_row, history_summary, history_can_replay, history_action_state


@dataclass(frozen=True)
class ResultActions:
    open_image: Callable
    open_outputs: Callable
    show_prompt: Callable
    use_material: Callable


class ResultView(ttk.Frame):
    def __init__(self, master, actions: ResultActions):
        super().__init__(master, padding=8)
        self.image_paths: list[Path] = []
        self.preview_photo = None
        self.result_info = tk.StringVar(master=self, value="")
        preview_actions = ttk.Frame(self)
        preview_actions.pack(side="bottom", fill="x", pady=(5, 0))
        preview_meta = ttk.Frame(self)
        preview_meta.pack(side="bottom", fill="x")
        self.image_label = ttk.Label(self, text="生成結果なし", anchor="center")
        self.image_label.pack(fill="both", expand=True)
        self.result_video = VideoPreview(self, height=240)
        ttk.Label(preview_meta, textvariable=self.result_info, wraplength=350).pack(anchor="w", pady=(3, 4))
        self.images_list = tk.Listbox(
            preview_meta, height=2, exportselection=False, font=("Meiryo UI", 9),
        )
        # Show a file chooser only when multiple outputs exist.
        self.images_list.bind("<<ListboxSelect>>", self.show_selected_image)
        row = ttk.Frame(preview_actions)
        row.pack(fill="x")
        for col in range(3):
            row.columnconfigure(col, weight=1)
        self.open_button = ttk.Button(row, text="開く", command=actions.open_image, state="disabled")
        self.open_button.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(row, text="保存先", command=actions.open_outputs).grid(row=0, column=1, sticky="ew", padx=(0, 4))
        self.result_prompt_button = ttk.Button(row, text="プロンプト", command=actions.show_prompt, state="disabled")
        self.result_prompt_button.grid(row=0, column=2, sticky="ew")
        self.result_tools = ttk.Frame(preview_actions)
        self.material_button = ttk.Button(self.result_tools, text="素材として使用…", command=actions.use_material)
        self.material_button.pack(fill="x")

    def set_video(self, path: Path | None) -> None:
        self.result_video.set_source(path)
        if path is not None:
            self.image_label.pack_forget()
            self.result_video.pack(fill="both", expand=True)
        else:
            self.result_video.pack_forget()
            if not self.image_label.winfo_manager():
                self.image_label.pack(fill="both", expand=True)

    def show_selected_image(self, _event=None) -> None:
        selected = self.images_list.curselection()
        if selected and selected[0] < len(self.image_paths):
            self.display_image(self.image_paths[selected[0]])

    def display_image(self, path: Path) -> None:
        self.set_video(path if is_video_output(path) else None)
        if path.is_file() and (path.suffix.lower() in IMAGE_EXTENSIONS or is_video_output(path)):
            self.result_tools.pack(fill="x", pady=(5, 0))
        else:
            self.result_tools.pack_forget()
        if is_video_output(path):
            self.preview_photo = None
            self.image_label.configure(image="", text="動画")
            self.result_info.set(path.name if len(self.image_paths) == 1 else "")
            return
        try:
            photo = tk.PhotoImage(file=str(path))
            scale = preview_subsample(
                photo.width(), photo.height(),
                self.image_label.winfo_width(), self.image_label.winfo_height(), 400,
            )
            self.preview_photo = photo.subsample(scale, scale)
            self.image_label.configure(image=self.preview_photo, text="")
        except tk.TclError:
            self.preview_photo = None
            self.image_label.configure(image="", text="プレビュー非対応")
        self.result_info.set(path.name if len(self.image_paths) == 1 else "")

    def selected_path(self):
        selected = self.images_list.curselection()
        index = selected[0] if selected else 0
        return self.image_paths[index] if index < len(self.image_paths) else None

    def mark_prompt_available(self):
        self.result_prompt_button.configure(state="normal")

    def show_outputs(self, images):
        self.image_paths = list(images)
        self.images_list.delete(0, "end")
        for file in self.image_paths:
            self.images_list.insert("end", file.name)
        if len(self.image_paths) > 1:
            self.images_list.pack(fill="x", pady=(0, 5))
        else:
            self.images_list.pack_forget()
        if self.image_paths:
            self.images_list.selection_set(0)
            self.display_image(self.image_paths[0])
            self.open_button.configure(state="normal")
        else:
            self.set_video(None)
            self.preview_photo = None
            self.image_label.configure(image="", text="出力なし")
            self.result_info.set("")
            self.result_tools.pack_forget()
            self.open_button.configure(state="disabled")

    def set_busy(self, busy):
        self.result_video.set_enabled(not busy)
        self.material_button.configure(state="disabled" if busy else "normal")


@dataclass(frozen=True)
class HistoryActions:
    select: Callable
    restore: Callable
    open_output: Callable
    restore_request: Callable
    compare: Callable
    replay: Callable
    show_prompt: Callable
    refresh: Callable
    restore_character: Callable
    use_material: Callable


class HistoryView(ttk.Frame):
    def __init__(self, master, actions: HistoryActions):
        super().__init__(master, padding=8)
        self.history_entries: dict[str, HistoryEntry] = {}
        self._history_selection_key = None
        self._history_preview_key = None
        self.history_preview_photo = None
        self.on_selection = actions.select
        history_actions = ttk.Frame(self)
        history_actions.pack(side="bottom", fill="x", pady=(5, 0))
        history_meta = ttk.Frame(self)
        history_meta.pack(side="bottom", fill="x", pady=(5, 0))
        history_columns = ("date", "workflow", "seed")
        table_holder = ttk.Frame(self)
        table_holder.pack(fill="both", expand=True)
        self.history_table = ttk.Treeview(
            table_holder, columns=history_columns, show="tree headings",
            selectmode="extended", height=6,
        )
        self.history_table.heading("#0", text="プロンプト")
        self.history_table.column("#0", width=160, minwidth=90, stretch=True)
        self.history_table.heading("date", text="日時")
        self.history_table.column("date", width=94, minwidth=80, stretch=False)
        self.history_table.heading("workflow", text="種別")
        self.history_table.column("workflow", width=62, minwidth=54, stretch=False)
        self.history_table.heading("seed", text="Seed")
        self.history_table.column("seed", width=82, minwidth=65, stretch=False)
        history_y = ttk.Scrollbar(table_holder, orient="vertical", command=self.history_table.yview)
        history_x = ttk.Scrollbar(table_holder, orient="horizontal", command=self.history_table.xview)
        self.history_table.configure(yscrollcommand=history_y.set, xscrollcommand=history_x.set)
        self.history_table.grid(row=0, column=0, sticky="nsew")
        history_y.grid(row=0, column=1, sticky="ns")
        history_x.grid(row=1, column=0, sticky="ew")
        table_holder.columnconfigure(0, weight=1)
        table_holder.rowconfigure(0, weight=1)
        self.history_table.bind("<<TreeviewSelect>>", actions.select)
        self.history_table.bind("<Double-1>", lambda _e: actions.restore())

        self.history_details = tk.StringVar(value="")
        ttk.Label(
            history_meta, textvariable=self.history_details,
            wraplength=420, style="Muted.TLabel",
        ).pack(anchor="w", fill="x", pady=(8, 5))
        self.history_image = ttk.Label(
            history_meta, text="履歴画像", anchor="center",
        )
        self.history_image.pack(fill="x", pady=(0, 4))
        self.history_video = VideoPreview(history_meta, height=180)
        first_row = ttk.Frame(history_actions)
        first_row.pack(fill="x", pady=(2, 4))
        for col in range(4):
            first_row.columnconfigure(col, weight=1)
        self.history_open_button = ttk.Button(first_row, text="開く", command=actions.open_output, style="Compact.TButton")
        self.history_open_button.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self.history_request_button = ttk.Button(first_row, text="プロンプト復元",
            command=actions.restore_request, state="disabled", style="Compact.TButton")
        self.history_request_button.grid(row=0, column=1, sticky="ew", padx=(0, 4))
        self.history_restore_button = ttk.Button(first_row, text="設定復元", command=actions.restore, style="Compact.TButton")
        self.history_restore_button.grid(row=0, column=2, sticky="ew", padx=(0, 4))
        self.history_compare_button = ttk.Button(first_row, text="比較", command=actions.compare, style="Compact.TButton")
        self.history_compare_button.grid(row=0, column=3, sticky="ew")
        second_row = ttk.Frame(history_actions)
        second_row.pack(fill="x")
        for col in range(4):
            second_row.columnconfigure(col, weight=1)
        self.same_seed_button = ttk.Button(second_row, text="同Seed再生成",
            command=lambda: actions.replay(new_seed=False), state="disabled", style="Compact.TButton")
        self.same_seed_button.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self.new_seed_button = ttk.Button(second_row, text="別Seed再生成",
            command=lambda: actions.replay(new_seed=True), state="disabled", style="Compact.TButton")
        self.new_seed_button.grid(row=0, column=1, sticky="ew", padx=(0, 4))
        self.history_prompt_button = ttk.Button(second_row, text="詳細", command=actions.show_prompt, style="Compact.TButton")
        self.history_prompt_button.grid(row=0, column=2, sticky="ew", padx=(0, 4))
        ttk.Button(second_row, text="更新", command=actions.refresh, style="Compact.TButton").grid(row=0, column=3, sticky="ew")
        self.history_character_button = ttk.Button(history_actions, text="キャラ特徴復元",
            command=actions.restore_character, state="disabled", style="Compact.TButton")
        self.history_character_button.pack(fill="x", pady=(4, 0))
        self.history_tools = ttk.Frame(history_actions)
        ttk.Button(self.history_tools, text="素材として使用…", command=actions.use_material,
                   style="Compact.TButton").pack(fill="x")

    def apply_entries(self, entries, select_id: str | None = None) -> None:
        """Apply only changed rows; preserve scroll/selection on normal refresh."""
        table = self.history_table
        old_selected = tuple(table.selection())
        old_entries = self.history_entries
        new_entries = {entry.id: entry for entry in entries}
        self.history_entries = new_entries
        obsolete = [item for item in table.get_children() if item not in new_entries]
        if obsolete:
            table.delete(*obsolete)
        for entry in entries:
            old = old_entries.get(entry.id)
            if old is not None and old == entry:
                continue
            title, values = history_row(entry)
            if old is None:
                table.insert("", "end", iid=entry.id, text=title, values=values)
            else:
                table.item(entry.id, text=title, values=values)
        ordered = tuple(new_entries)
        if tuple(table.get_children()) != ordered:
            table.set_children("", *ordered)
        requested = (select_id,) if select_id else old_selected
        available = tuple(entry_id for entry_id in requested if entry_id in new_entries)
        if available != tuple(table.selection()):
            table.selection_set(*available)
        if select_id and available:
            table.see(available[0])
        if (old_selected != available or any(old_entries.get(key) != new_entries.get(key) for key in available)):
            self._history_selection_key = None
            self._history_preview_key = None
        self.on_selection()
        if not entries:
            self.history_details.set("まだ保存された生成結果がありません")

    def selected_entries(self) -> list[HistoryEntry]:
        return [
            self.history_entries[entry_id]
            for entry_id in self.history_table.selection()
            if entry_id in self.history_entries
        ]

    def set_video(self, path: Path | None) -> None:
        self.history_video.set_source(path)
        if path is not None:
            self.history_image.pack_forget()
            self.history_video.pack(fill="x", pady=(0, 4))
        else:
            self.history_video.pack_forget()
            if not self.history_image.winfo_manager():
                self.history_image.pack(fill="x", pady=(0, 4))

    def refresh_selection(self, workflows, *, working, visible) -> None:
        # The Result tab does not need hidden history thumbnails or file checks.
        if not visible:
            return
        selected = self.selected_entries()
        selection_key = (tuple(entry.id for entry in selected), working)
        if getattr(self, "_history_selection_key", None) == selection_key:
            return
        self._history_selection_key = selection_key
        state = "normal" if history_can_replay(selected, workflows, working=working) else "disabled"
        self.same_seed_button.configure(state=state)
        self.new_seed_button.configure(state=state)

        if hasattr(self, "history_open_button"):
            actions = history_action_state(selected, workflows, working=working)
            for button, key in (
                (self.history_open_button, "open"), (self.history_restore_button, "restore"),
                (self.history_compare_button, "compare"), (self.history_prompt_button, "prompt"),
            ):
                button.configure(state="normal" if actions[key] else "disabled")
            if hasattr(self, "history_request_button"):
                self.history_request_button.configure(state="normal" if actions["request"] else "disabled")
            if hasattr(self, "history_character_button"):
                self.history_character_button.configure(state="normal" if actions["character"] else "disabled")
            if actions["use_as_source"]:
                self.history_tools.pack(fill="x", pady=(4, 0))
            else:
                self.history_tools.pack_forget()
        if not selected:
            self.set_video(None)
            self._history_preview_key = None
            self.history_details.set("")
            self.history_image.configure(image="", text="")
            self.history_preview_photo = None
            return
        if len(selected) > 1:
            self.set_video(None)
            self._history_preview_key = None
            self.history_details.set(f"{len(selected)}件選択中")
            self.history_image.configure(image="", text="")
            self.history_preview_photo = None
            return

        entry = selected[0]
        self.history_details.set(history_summary(entry))
        image = entry.first_image
        exists = image is not None and image.is_file()
        preview_key = (entry.id, image, exists)
        if getattr(self, "_history_preview_key", None) == preview_key:
            return
        self._history_preview_key = preview_key
        self.set_video(image if exists and is_video_output(image) else None)
        if not exists:
            self.history_preview_photo = None
            self.history_image.configure(image="", text="画像ファイルが見つかりません")
            return
        if is_video_output(image):
            self.history_preview_photo = None
            self.history_image.configure(image="", text="動画")
            return
        try:
            photo = tk.PhotoImage(file=str(image))
            scale = preview_subsample(
                photo.width(), photo.height(),
                self.history_image.winfo_width(), self.history_image.winfo_height(), 120,
            )
            self.history_preview_photo = photo.subsample(scale, scale)
            self.history_image.configure(image=self.history_preview_photo, text="")
        except (tk.TclError, OSError):
            self.history_preview_photo = None
            self.history_image.configure(
                image="", text="プレビュー非対応"
            )

    def set_busy(self, busy):
        self.history_video.set_enabled(not busy)
        if busy:
            for button in (self.same_seed_button, self.new_seed_button, self.history_request_button,
                           self.history_character_button, self.history_restore_button):
                button.configure(state="disabled")
            self.history_tools.pack_forget()
        # A visible selection must re-evaluate action availability when the
        # task ends, even if no selection event arrived while it was busy.
        self._history_selection_key = None
