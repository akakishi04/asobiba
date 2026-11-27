"""Connection bar and expandable settings panel, with injected application actions."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable
import tkinter as tk
from tkinter import ttk

from . import core


@dataclass(frozen=True)
class ConnectionVariables:
    model: tk.Variable
    llm_url: tk.Variable
    comfy_url: tk.Variable
    unload_llm: tk.Variable
    free_comfy: tk.Variable
    use_prompt_cache: tk.Variable
    h3_encoder_model: tk.Variable
    h3_encoder_cpu: tk.Variable
    dark_mode: tk.Variable


@dataclass(frozen=True)
class ConnectionActions:
    refresh_models: Callable
    clear_cache: Callable
    switch_theme: Callable
    save: Callable
    check: Callable
    recover_jobs: Callable
    release_memory: Callable
    show_operations: Callable


class ConnectionPanel:
    def __init__(self, layout, variables: ConnectionVariables, actions: ConnectionActions):
        self.topbar = ttk.Frame(layout)
        self.topbar.pack(fill="x")
        ttk.Label(self.topbar, text="LLM").pack(side="left", padx=(0, 6))
        self.model_box = ttk.Combobox(self.topbar, textvariable=variables.model, state="normal", width=18)
        self.model_box.pack(side="left", fill="x", expand=True)
        ttk.Button(self.topbar, text="モデル更新", command=actions.refresh_models).pack(side="left", padx=(6, 0))
        self.connection_toggle = ttk.Button(self.topbar, text="設定 ▸", command=self.toggle)
        self.connection_toggle.pack(side="left", padx=(6, 0))

        self.connection_visible = False
        self.connection_panel = connection = ttk.Frame(layout, padding=(0, 6, 0, 0))
        connection.columnconfigure(1, weight=1)
        ttk.Label(connection, text="LM Studio").grid(row=0, column=0, sticky="w", padx=(0, 7), pady=3)
        ttk.Entry(connection, textvariable=variables.llm_url).grid(row=0, column=1, sticky="ew", pady=3)
        ttk.Label(connection, text="ComfyUI").grid(row=1, column=0, sticky="w", padx=(0, 7), pady=3)
        ttk.Entry(connection, textvariable=variables.comfy_url).grid(row=1, column=1, sticky="ew", pady=3)
        options_frame = ttk.Frame(connection)
        options_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(4, 2))
        ttk.Checkbutton(options_frame, text="解釈後にLLMを解放",
                        variable=variables.unload_llm).grid(row=0, column=0, sticky="w", padx=(0, 12))
        ttk.Checkbutton(options_frame, text="解釈前にComfyUIを解放",
                        variable=variables.free_comfy).grid(row=0, column=1, sticky="w")
        ttk.Checkbutton(options_frame, text="解釈キャッシュ", variable=variables.use_prompt_cache).grid(
            row=1, column=0, sticky="w", pady=(3, 0))
        ttk.Button(options_frame, text="キャッシュ削除", command=actions.clear_cache).grid(
            row=1, column=1, sticky="w", pady=(3, 0))
        encoder_row = ttk.Frame(connection)
        encoder_row.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(2, 2))
        ttk.Label(encoder_row, text="H3エンコーダー").pack(side="left", padx=(0, 6))
        ttk.Combobox(encoder_row, textvariable=variables.h3_encoder_model,
                     values=tuple(core.H3_ENCODER_LABELS.values()), state="readonly", width=18).pack(side="left")
        ttk.Checkbutton(encoder_row, text="CPU実行", variable=variables.h3_encoder_cpu).pack(side="left", padx=(10, 0))
        settings_actions = ttk.Frame(connection)
        settings_actions.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(4, 0))
        ttk.Checkbutton(settings_actions, text="ダーク表示", variable=variables.dark_mode,
                        command=actions.switch_theme).pack(side="left")
        ttk.Button(settings_actions, text="保存", command=actions.save).pack(side="right")
        ttk.Button(settings_actions, text="接続確認", command=actions.check).pack(side="right", padx=(0, 6))
        self.recover_jobs_button = ttk.Button(settings_actions, text="未回収結果を取得", command=actions.recover_jobs)
        self.recover_jobs_button.pack(side="left", padx=(0, 6))
        self.free_memory_button = ttk.Button(settings_actions, text="生成モデル解放", command=actions.release_memory)
        self.free_memory_button.pack(side="right", padx=(0, 6))
        ttk.Button(connection, text="運用情報・保存容量", command=actions.show_operations).grid(
            row=5, column=0, columnspan=2, sticky="ew", pady=(4, 0))

    def toggle(self) -> None:
        if self.connection_visible:
            self.connection_panel.pack_forget()
        else:
            self.connection_panel.pack(fill="x", after=self.topbar)
        self.connection_visible = not self.connection_visible
        self.connection_toggle.configure(text="設定 ▾" if self.connection_visible else "設定 ▸")
