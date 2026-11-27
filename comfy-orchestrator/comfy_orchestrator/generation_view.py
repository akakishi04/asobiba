"""Shared generation input view. It owns widgets and scroll geometry.

Configuration variables and application commands are injected; no dependency on
Application, worker threads or external generation services.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable
import tkinter as tk
from tkinter import ttk, scrolledtext

from .h3 import H3_MODEL_LABELS, H3_TURBO_LABELS, H3_PERFORMANCE_LABELS
from .file_drop import register_file_drop
from .generation_form import (
    RESOLUTION_PRESETS, CUSTOM_RESOLUTION, VIDEO_RESOLUTIONS, VIDEO_FRAME_COUNTS,
    H3_RESOLUTIONS, H3_DURATIONS, H3_CONNECTION_LABELS, CONTINUOUS_TARGETS, HUNYUAN_RESOLUTIONS,
)
from .timeline import CUSTOM_CUTS
from .prompt_profiles import T2I_PROFILE_LABELS, I2I_PROFILE_LABELS, H3_PROFILE_LABELS


@dataclass(frozen=True)
class GenerationVariables:
    editor_font_size: tk.Variable
    reference_image: tk.Variable
    mask_image: tk.Variable
    character_status: tk.Variable
    composition_image: tk.Variable
    pose_image: tk.Variable
    pose_mode: tk.Variable
    vision_composition: tk.Variable
    resolution_preset: tk.Variable
    width: tk.Variable
    height: tk.Variable
    video_size: tk.Variable
    video_frames: tk.Variable
    video_fps: tk.Variable
    h3_size: tk.Variable
    h3_duration: tk.Variable
    h3_connection: tk.Variable
    h3_long_target: tk.Variable
    h3_cut_summary: tk.Variable
    hunyuan_size: tk.Variable
    hunyuan_frames: tk.Variable
    hunyuan_steps: tk.Variable
    steps: tk.Variable
    cfg: tk.Variable
    qwen_steps: tk.Variable
    qwen_cfg: tk.Variable
    qwen_fixed_steps: tk.Variable
    qwen_fixed_cfg: tk.Variable
    seed: tk.Variable
    denoise: tk.Variable
    control_strength: tk.Variable
    t2i_profile: tk.Variable
    i2i_profile: tk.Variable
    h3_profile: tk.Variable
    checkpoint_model: tk.Variable
    h3_model: tk.Variable
    h3_turbo: tk.Variable
    h3_performance: tk.Variable


@dataclass(frozen=True)
class GenerationActions:
    change_font: Callable
    browse_image: Callable
    edit_mask: Callable
    toggle_extra: Callable
    open_character: Callable
    drop_character: Callable
    browse_composition: Callable
    browse_pose: Callable
    pose_changed: Callable
    show_composition: Callable
    apply_resolution: Callable
    edit_cut_durations: Callable
    sync_steps: Callable
    performance_changed: Callable
    model_changed: Callable
    run: Callable
    preview: Callable
    cancel: Callable
    long_action: Callable


class GenerationView(ttk.Frame):
    def __init__(self, master, root, colors, variables: GenerationVariables, actions: GenerationActions):
        super().__init__(master, padding=(8, 4))
        self._form_width = None
        self._form_bounds = None
        prompt_panel = self

        # Reserve space for actions FIRST so a short screen never hides "Generate".
        action_row = ttk.Frame(prompt_panel)
        action_row.pack(side="bottom", fill="x", pady=(8, 0))

        # The editor and optional image controls now scroll independently of the
        # generate/cancel buttons and the output/history pane.
        form_holder = ttk.Frame(prompt_panel)
        form_holder.pack(fill="both", expand=True)
        self.form_canvas = tk.Canvas(
            form_holder, background=colors["surface"],
            highlightthickness=0, borderwidth=0, width=320, height=250,
        )
        form_scrollbar = ttk.Scrollbar(
            form_holder, orient="vertical", command=self.form_canvas.yview
        )
        self.form_canvas.configure(yscrollcommand=form_scrollbar.set)
        self.form_canvas.pack(side="left", fill="both", expand=True)
        form_scrollbar.pack(side="right", fill="y")
        self.options_form = ttk.Frame(self.form_canvas)
        self.form_window = self.form_canvas.create_window(
            (0, 0), window=self.options_form, anchor="nw",
        )
        self.options_form.bind(
            "<Configure>", lambda _e: self._sync_form_scrollregion(),
        )
        self.form_canvas.bind(
            "<Configure>", lambda event: self._size_form_to_canvas(event.width),
        )
        root.bind("<MouseWheel>", self._on_form_mousewheel, add="+")
        root.bind("<Button-4>", self._on_form_mousewheel, add="+")
        root.bind("<Button-5>", self._on_form_mousewheel, add="+")

        # One shared work surface: prompt, references, parameters, actions.
        editor_toolbar = ttk.Frame(self.options_form)
        editor_toolbar.pack(fill="x", pady=(0, 4))
        self.prompt_title = ttk.Label(editor_toolbar, text="プロンプト", style="FieldHeading.TLabel")
        self.prompt_title.pack(side="left")
        ttk.Button(editor_toolbar, text="A+", width=3, command=lambda: actions.change_font(1),
                   style="Compact.TButton").pack(side="right", padx=(4, 0))
        ttk.Button(editor_toolbar, text="A−", width=3, command=lambda: actions.change_font(-1),
                   style="Compact.TButton").pack(side="right")
        self.prompt = scrolledtext.ScrolledText(
            self.options_form, height=6, wrap="word",
            font=("Meiryo UI", variables.editor_font_size.get()),
            undo=True, autoseparators=True, maxundo=100,
            padx=14, pady=12, spacing1=3, spacing3=3,
        )
        self.prompt.pack(fill="x", expand=False, pady=(0, 8))

        inputs = ttk.Frame(self.options_form)
        inputs.pack(fill="x", pady=(0, 6))
        inputs.columnconfigure(0, weight=1)

        def input_row(row, label, variable, command, *, button_text="選択", editable=False):
            frame = ttk.Frame(inputs)
            frame.grid(row=row, column=0, sticky="ew", pady=(0, 4))
            frame.columnconfigure(1, weight=1)
            ttk.Label(frame, text=label, width=11, anchor="w").grid(row=0, column=0, sticky="w", padx=(0, 5))
            entry = ttk.Entry(frame, textvariable=variable, width=8,
                              state="normal" if editable else "readonly")
            entry.grid(row=0, column=1, sticky="ew")
            button = ttk.Button(frame, text=button_text, command=command, style="Compact.TButton")
            button.grid(row=0, column=2, padx=(5, 0))
            ttk.Button(frame, text="解除", command=lambda: variable.set(""),
                       style="Compact.TButton").grid(row=0, column=3, padx=(4, 0))
            return frame, button

        self.reference_row, _ = input_row(0, "参照画像", variables.reference_image, actions.browse_image, editable=True)
        self.mask_row, self.mask_button = input_row(1, "修正範囲", variables.mask_image, actions.edit_mask, button_text="範囲を塗る")

        self.reference_tools = reference_tools = ttk.Frame(inputs)
        reference_tools.grid(row=2, column=0, sticky="ew", pady=(0, 4))
        self.extra_button = ttk.Button(reference_tools, text="追加参照 ▸",
                                       command=actions.toggle_extra, style="Compact.TButton")
        self.extra_button.pack(side="left")
        self.character_button = ttk.Button(reference_tools, textvariable=variables.character_status,
                                           command=actions.open_character, style="Compact.TButton")
        self.character_button.pack(side="left", padx=(6, 0))
        for target in (reference_tools, self.character_button):
            register_file_drop(target, actions.drop_character)
        self.composition_row, _ = input_row(3, "構図参考", variables.composition_image, actions.browse_composition)
        self.pose_row, _ = input_row(4, "ポーズ画像", variables.pose_image, actions.browse_pose)
        self.pose_modes = ttk.Frame(inputs)
        self.pose_modes.grid(row=5, column=0, sticky="ew", pady=(0, 5))
        ttk.Radiobutton(self.pose_modes, text="骨格PNG", variable=variables.pose_mode,
                        value="skeleton", command=actions.pose_changed).pack(side="left", padx=(0, 14))
        ttk.Radiobutton(self.pose_modes, text="画像から骨格検出", variable=variables.pose_mode,
                        value="photo", command=actions.pose_changed).pack(side="left")
        self.vision_row = ttk.Frame(inputs)
        self.vision_row.grid(row=6, column=0, sticky="ew", pady=(0, 4))
        self.vision_checkbox = ttk.Checkbutton(self.vision_row, text="LLMで画像を解析",
                                              variable=variables.vision_composition)
        self.vision_checkbox.pack(side="left")
        ttk.Button(self.vision_row, text="認識結果", command=actions.show_composition,
                   style="Compact.TButton").pack(side="right")
        settings = ttk.Frame(self.options_form)
        settings.pack(fill="x", pady=(0, 4))
        for col in (1, 3):
            settings.columnconfigure(col, weight=1)
        ttk.Separator(settings).grid(row=0, column=0, columnspan=4, sticky="ew", pady=(0, 8))
        self.parameter_widgets = {}

        def field(row, column, label, variable, key, *, choices=None, span=1, width=8):
            title = ttk.Label(settings, text=label)
            title.grid(row=row, column=column, sticky="w", padx=(0, 6), pady=3)
            if choices is None:
                widget = ttk.Entry(settings, textvariable=variable, width=width)
            else:
                widget = ttk.Combobox(settings, textvariable=variable, values=choices,
                                      state="readonly", width=width)
            widget.grid(row=row, column=column+1, columnspan=span, sticky="ew",
                        padx=(0, 8) if span == 1 and column == 0 else 0, pady=3)
            self.parameter_widgets.setdefault(key, []).extend((title, widget))
            return widget

        # Resolution always occupies the same row, irrespective of workflow.
        self.resolution_box = field(2, 0, "解像度", variables.resolution_preset, "resolution",
                                    choices=(*RESOLUTION_PRESETS, CUSTOM_RESOLUTION), span=3, width=18)
        self.resolution_box.bind("<<ComboboxSelected>>", actions.apply_resolution)
        self.width_entry = field(3, 0, "幅", variables.width, "custom_size")
        self.height_entry = field(3, 2, "高さ", variables.height, "custom_size")
        source_title = ttk.Label(settings, text="解像度")
        source_title.grid(row=2, column=0, sticky="w", padx=(0, 6), pady=3)
        source_value = ttk.Label(settings, text="元画像サイズ")
        source_value.grid(row=2, column=1, columnspan=3, sticky="w", pady=3)
        self.parameter_widgets["source_size"] = [source_title, source_value]

        field(2, 0, "解像度", variables.video_size, "wan", choices=VIDEO_RESOLUTIONS, span=3, width=18)
        field(3, 0, "フレーム数", variables.video_frames, "wan", choices=VIDEO_FRAME_COUNTS)
        field(3, 2, "FPS", variables.video_fps, "wan", choices=("16", "24", "30"), width=5)
        field(2, 0, "解像度", variables.h3_size, "h3", choices=H3_RESOLUTIONS, span=3, width=18)
        field(3, 0, "長さ (24fps)", variables.h3_duration, "h3", choices=tuple(H3_DURATIONS), span=3, width=18)
        self.h3_duration_title = self.parameter_widgets["h3"][-2]
        field(10, 0, "接続方式", variables.h3_connection, "h3_long",
              choices=tuple(H3_CONNECTION_LABELS.values()), span=3, width=18)
        field(11, 0, "計画用合計尺", variables.h3_long_target, "h3_long",
              choices=(*CONTINUOUS_TARGETS, CUSTOM_CUTS), span=3, width=8)
        cut_button = ttk.Button(settings, text="カット尺…", command=actions.edit_cut_durations)
        cut_button.grid(row=12, column=0, columnspan=2, sticky="ew", pady=3)
        cut_summary = ttk.Label(settings, textvariable=variables.h3_cut_summary)
        cut_summary.grid(row=12, column=2, columnspan=2, sticky="w", padx=(6, 0))
        self.parameter_widgets["h3_long"].extend((cut_button, cut_summary))

        field(2, 0, "解像度", variables.hunyuan_size, "hunyuan", choices=HUNYUAN_RESOLUTIONS, span=3, width=18)
        field(3, 0, "フレーム数 (24fps)", variables.hunyuan_frames, "hunyuan",
              choices=VIDEO_FRAME_COUNTS, span=3)
        field(4, 0, "Steps", variables.hunyuan_steps, "hunyuan", choices=("8", "12"), span=3)
        self.steps_entry = field(4, 0, "Steps", variables.steps, "steps")
        self.cfg_entry = field(4, 2, "CFG", variables.cfg, "cfg")
        field(4, 0, "Steps", variables.qwen_steps, "qwen_steps")
        field(4, 2, "CFG", variables.qwen_cfg, "qwen_steps")
        field(4, 0, "Steps", variables.qwen_fixed_steps, "qwen_fixed").configure(state="readonly")
        field(4, 2, "CFG", variables.qwen_fixed_cfg, "qwen_fixed").configure(state="readonly")
        self.seed_entry = field(5, 0, "Seed", variables.seed, "seed", span=2)
        self.random_seed_button = ttk.Button(settings, text="ランダム", style="Compact.TButton",
                                             command=lambda: variables.seed.set(""))
        self.random_seed_button.grid(row=5, column=3, sticky="ew", pady=3)
        self.parameter_widgets["seed"].append(self.random_seed_button)
        self.denoise_entry = field(6, 0, "Denoise", variables.denoise, "denoise", span=3)
        self.strength_entry = field(6, 0, "ポーズ強度", variables.control_strength, "strength", span=3)
        self.t2i_profile_box = field(7, 0, "プロンプト方式", variables.t2i_profile, "t2i_profile",
                                     choices=tuple(T2I_PROFILE_LABELS.values()), span=3, width=18)
        self.i2i_profile_box = field(7, 0, "プロンプト方式", variables.i2i_profile, "i2i_profile",
                                     choices=tuple(I2I_PROFILE_LABELS.values()), span=3, width=18)
        self.h3_profile_box = field(7, 0, "プロンプト方式", variables.h3_profile, "h3_profile",
                                    choices=tuple(H3_PROFILE_LABELS.values()), span=3, width=18)
        self.checkpoint_box = field(8, 0, "モデル", variables.checkpoint_model, "checkpoint",
                                    choices=(variables.checkpoint_model.get(),), span=3, width=18)
        self.checkpoint_box.bind("<<ComboboxSelected>>", actions.sync_steps)
        self.h3_model_box = field(8, 0, "モデル", variables.h3_model, "h3",
                                  choices=tuple(dict.fromkeys((*H3_MODEL_LABELS.values(), variables.h3_model.get()))),
                                  span=3, width=18)
        self.h3_turbo_box = field(9, 0, "追加Turbo", variables.h3_turbo, "h3_turbo",
                                  choices=tuple(H3_TURBO_LABELS.values()), span=3, width=18)
        self.h3_performance_box = field(9, 0, "高速化", variables.h3_performance, "h3_performance",
                                        choices=tuple(H3_PERFORMANCE_LABELS.values()), span=3, width=18)
        self.h3_performance_box.bind("<<ComboboxSelected>>", actions.performance_changed)
        self.h3_model_box.bind("<<ComboboxSelected>>", actions.model_changed)
        self.h3_turbo_box.bind("<<ComboboxSelected>>", actions.sync_steps)
        for widgets in self.parameter_widgets.values():
            for widget in widgets:
                widget.grid_remove()

        self.run_button = ttk.Button(
            action_row, text="画像生成", style="Run.TButton", command=actions.run
        )
        self.run_button.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.preview_button = ttk.Button(action_row, text="プロンプト確認", command=actions.preview)
        self.preview_button.pack(side="left", padx=(0, 6))
        self.cancel_button = ttk.Button(
            action_row, text="生成中止", command=actions.cancel, state="disabled"
        )
        self.cancel_button.pack(side="left")
        self.long_actions_button = ttk.Menubutton(action_row, text="その他 ▾", style="Compact.TButton")
        self.long_actions_menu = tk.Menu(self.long_actions_button, tearoff=False)
        self.long_actions_button.configure(menu=self.long_actions_menu)
        self._long_menu_keys = ("generate", "regenerate", "join")
        for key, label in zip(self._long_menu_keys, ("カット生成（結合なし）", "選択以降再生成", "結合のみ")):
            self.long_actions_menu.add_command(label=label, command=lambda k=key: actions.long_action(k),
                                               state="disabled")

    def _size_form_to_canvas(self, width: int) -> None:
        """Match the scrollable form to its viewport without growing the window."""
        width = max(1, width)
        if getattr(self, "_form_width", None) != width:
            self._form_width = width
            self.form_canvas.itemconfigure(self.form_window, width=width)
        self._sync_form_scrollregion()

    def _sync_form_scrollregion(self) -> None:
        bounds = self.form_canvas.bbox("all")
        if bounds and bounds != getattr(self, "_form_bounds", None):
            self._form_bounds = bounds
            self.form_canvas.configure(scrollregion=bounds)

    def _on_form_mousewheel(self, event):
        """Scroll just the option form; preserve normal text-editor scrolling."""
        widget = event.widget
        inside_form = False
        while widget is not None:
            if widget is self.options_form:
                inside_form = True
                break
            if isinstance(widget, (tk.Text, tk.Scrollbar, ttk.Scrollbar, tk.Listbox, ttk.Treeview)):
                return None
            widget = getattr(widget, "master", None)
        if not inside_form:
            return None
        first, last = self.form_canvas.yview()
        if first <= 0.0 and last >= 1.0:
            return None
        if getattr(event, "num", None) == 4:
            amount = -3
        elif getattr(event, "num", None) == 5:
            amount = 3
        else:
            delta = getattr(event, "delta", 0)
            if delta == 0:
                return None
            amount = -3 if delta > 0 else 3
        self.form_canvas.yview_scroll(amount, "units")
        return "break"
