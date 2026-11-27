"""Independent result and history views. All operations are injected commands."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable
import tkinter as tk
from tkinter import ttk

from .video_preview import VideoPreview


@dataclass(frozen=True)
class ResultActions:
    select_image: Callable
    open_image: Callable
    open_outputs: Callable
    show_prompt: Callable
    use_i2i: Callable
    use_i2v: Callable


class ResultView(ttk.Frame):
    def __init__(self, master, result_info, actions: ResultActions):
        super().__init__(master, padding=8)
        preview_actions = ttk.Frame(self)
        preview_actions.pack(side="bottom", fill="x", pady=(5, 0))
        preview_meta = ttk.Frame(self)
        preview_meta.pack(side="bottom", fill="x")
        self.image_label = ttk.Label(self, text="生成結果なし", anchor="center")
        self.image_label.pack(fill="both", expand=True)
        self.result_video = VideoPreview(self, height=240)
        ttk.Label(preview_meta, textvariable=result_info, wraplength=350).pack(anchor="w", pady=(3, 4))
        self.images_list = tk.Listbox(
            preview_meta, height=2, exportselection=False, font=("Meiryo UI", 9),
        )
        # Show a file chooser only when multiple outputs exist.
        self.images_list.bind("<<ListboxSelect>>", actions.select_image)
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
        self.result_tools.columnconfigure(0, weight=1)
        self.result_tools.columnconfigure(1, weight=1)
        ttk.Button(self.result_tools, text="I2Iに使用", command=actions.use_i2i).grid(
            row=0, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(self.result_tools, text="I2Vに使用", command=actions.use_i2v).grid(
            row=0, column=1, sticky="ew")


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
    use_i2i: Callable
    use_i2v: Callable


class HistoryView(ttk.Frame):
    def __init__(self, master, actions: HistoryActions):
        super().__init__(master, padding=8)
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
        self.history_tools.columnconfigure(0, weight=1)
        self.history_tools.columnconfigure(1, weight=1)
        ttk.Button(self.history_tools, text="I2Iに使用", command=actions.use_i2i, style="Compact.TButton").grid(
            row=0, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(self.history_tools, text="I2Vに使用", command=actions.use_i2v, style="Compact.TButton").grid(
            row=0, column=1, sticky="ew")
