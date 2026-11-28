"""Windows desktop GUI for the fixed-workflow ComfyUI orchestrator.

Runs model inference in worker threads; Tk widgets are updated on the main thread.
No third-party GUI dependencies.
"""

from __future__ import annotations

import copy
from dataclasses import replace
import json
import os
import secrets
import sqlite3
import threading
import uuid
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

from . import core, output_collection, camera_spec
from .generation_controller import GenerationController, record_history, active_aux_inputs
from .generation_runtime import preflight_long
from .model_runtime import release_comfy_before_llm, memory_stats
from .storage_report import storage_report
from .operations_ui import OperationsWindow
# Keep historical public helper imports for external callers.
from .output_collection import output_media, output_images, output_destination
from .comparison import ComparisonWindow
from .history import HistoryStore, HistoryEntry
from .jobs import JobJournal, JobCancellationRequested
from .prompt_cache import PromptCache, CACHE_ERRORS
from .long_video_plan import (LONG_VIDEO_ID, LONG_TARGETS, segment_plan, first_changed_cut,
                              connection_changed_from, manifest_windows, long_generation_model)
from .project_store import LongVideoStore, edit_project, restore_project_plan, project_generation_inputs
from .video_media import FFmpeg
from .timeline import (plan_long_prompts, CUSTOM_CUTS, validate_cut_frames,
                       GUIDE_CONNECTION_FRAMES,
                       default_cut_frames, generation_frames_for_cuts, format_cut_seconds)
from .timeline_ui import edit_cut_durations
from .project_ui import ProjectWorkspace
from .prompt_edit import edit_prompts
from .prompt_inference import IMAGE_REASONING_LABELS, IMAGE_REASONING_BY_LABEL
from .mode_settings import ModeSettings
from .input_snapshot import copy_frozen_asset
from .mask_editor import edit_mask
from .lmstudio import list_models, LMStudio
from .character_ui import CharacterReferenceWindow, choose_history_traits
from .character_features import CharacterFeatureStore
from .file_drop import enable_native_dnd
from .character_refs import (
    validate_character_selection, character_status_label,
    save_character_sheet, load_character_sheet, clear_character_sheet,
)
from .prompt_profiles import (
    DEFAULT_T2I_PROFILE, T2I_PROFILE_LABELS, T2I_LABEL_TO_PROFILE,
    DEFAULT_I2I_PROFILE, I2I_PROFILE_LABELS, I2I_LABEL_TO_PROFILE,
    DEFAULT_H3_PROFILE, H3_PROFILE_GENERAL, H3_PROFILE_LABELS, H3_LABEL_TO_PROFILE,
)
from .ime_font import install_native_ime_font, sync_native_ime_font
from .ui_theme import apply_ttk_theme, style_text_widget
from .generation_form import (
    CUSTOM_RESOLUTION, VIDEO_RESOLUTIONS, VIDEO_FRAME_COUNTS, HUNYUAN_RESOLUTIONS,
    H3_RESOLUTIONS, H3_DURATIONS, H3_CONNECTION_LABELS, LEGACY_CONNECTION_LABELS,
    preferred_connection_frames, connection_label, connection_frames,
    RESOLUTION_PRESETS, resolution_preset_label, resolve_generation_workflow, WORKFLOW_NAMES,
    workflow_display_names, GENERATION_MODE_LABELS, CONTINUOUS_TARGETS,
    workflow_generation_mode, mode_workflow_ids, choose_mode_workflow, parameter_visibility,
    reference_visibility, image_aware_overrides, common_overrides, wan_overrides,
    qwen_overrides, hunyuan_overrides, h3_overrides,
)
from .app_config import load_local_config, write_local_config
from .history_presentation import history_request_text, history_prompt_details
from .prompt_viewer import show_prompt_details, show_saved_character_features, show_composition_report
from .output_views import ResultView, HistoryView, ResultActions, HistoryActions
from .settings_ui import ConnectionPanel, ConnectionVariables, ConnectionActions
from .generation_view import GenerationView, GenerationVariables, GenerationActions
from .h3_model_picker import model_choices as h3_picker_choices, select_model_key
from .task_controller import TaskController, EventRouter
from .history_refresh import HistoryRefresh
from .result_state import ResultReviewState
from .llm_usage import UsageStore
from .material_transfer import DESTINATIONS, available_materials, extract_material
from .material_ui import MaterialDialog, FramePicker
from .single_prompt import SinglePromptDraft
from .single_prompt_ui import SinglePromptWindow
from .image_adjust import ImageAdjustDraft, can_adjust, supported_workflow, image_file
from .image_adjust_ui import ImageAdjustWindow
from .model_profiles import (ANIMA_ID, ANIMA_BASE, T2I_ONLY, WAI_FAMILY, image_model_choices,
                             selected_label, defaults_for)
from .model_registry import (load_registrations, save_registrations, registered_h3_turbo,
                             parse_h3_key, registration_for_key)
from .model_manager_ui import ModelManagerWindow
from .model_comparison import ComparisonStore, prepare_targets, run_comparison
from .model_comparison_ui import ModelComparisonWindow
from .camera_ui import choose_camera
from .preview_geometry import preview_subsample


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config.json"
EXAMPLE = ROOT / "config.example.json"
OUTPUTS = ROOT / "outputs"

VIDEO_EXTENSIONS = output_collection.VIDEO_EXTENSIONS
IMAGE_EXTENSIONS = output_collection.IMAGE_EXTENSIONS
is_video_output = output_collection.is_video_output


def bootstrap_config() -> dict:
    return load_local_config(CONFIG, EXAMPLE)


# Preserve these public helpers for existing callers and local tests.
def save_output_image(base_url: str, metadata: dict, prompt_id: str, *, output_dir=None) -> Path:
    return output_collection.save_output_image(
        base_url, metadata, prompt_id, output_dir=OUTPUTS if output_dir is None else output_dir,
    )


def collect_generation_outputs(base_url, result, kind, *, journal=None, cancel_event=None):
    return output_collection.collect_generation_outputs(
        base_url, result, kind, output_dir=OUTPUTS, journal=journal,
        cancel_event=cancel_event, downloader=save_output_image,
    )


def set_grid_visible(widget, visible: bool) -> None:
    """Avoid no-op geometry requests (including while parent is unmapped)."""
    if (widget.winfo_manager() == "grid") != visible:
        widget.grid() if visible else widget.grid_remove()


def initial_window_bounds(screen_width: int, screen_height: int) -> tuple[int, int, int, int, int, int]:
    """Screen-aware startup geometry with room for the Windows taskbar/title bar.

    Return (width, height, left, top, min_width, min_height).
    Avoid a minimum size taller than the user's actual display.
    """
    width = max(320, min(1240, screen_width - 72))
    height = max(280, min(820, screen_height - 130))
    x = max(0, (screen_width - width) // 2)
    y = max(0, min(28, (screen_height - height) // 4))
    min_width = min(width, max(320, min(840, screen_width - 90)))
    min_height = min(height, max(280, min(540, screen_height - 150)))
    return width, height, x, y, min_width, min_height


class Application:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Asobiba | Comfy Orchestrator")
        width, height, x, y, min_width, min_height = initial_window_bounds(
            self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        )
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        self.root.minsize(min_width, min_height)
        self.tasks = TaskController()
        self.messages = self.tasks.messages
        self.stop_event = self.tasks.stop_event
        self.config = bootstrap_config()
        self.history_store = HistoryStore(ROOT)
        self.comparison_store = ComparisonStore(self.history_store)
        self.comparison_window = None
        self._comparison_active = None
        self._registry_path = self.history_store.data / "model_registry.json"
        self._registry_error = None
        try:
            self._registered_models = load_registrations(self._registry_path)
        except (OSError, core.OrchestratorError) as exc:
            self._registered_models = ()
            self._registry_error = str(exc)
        self.model_manager = None
        self.llm_usage = UsageStore(self.history_store.data / "llm_usage.sqlite3")
        self._single_usage_group = None
        self.job_journal = JobJournal(self.history_store.data / "jobs")
        self.long_video_store = LongVideoStore(self.history_store.data / "long_videos")
        self.prompt_cache = PromptCache(ROOT / ".cache" / "prompt_plans.sqlite3")
        self.history_refresh = HistoryRefresh(self.history_store, self.messages.put)
        self._generation_ui_key = None
        self.latest_composition_report = ""
        self.review = ResultReviewState()
        self._result_material_context = {}
        self._pending_material_transfer = None
        self.adjust_draft = None
        self.adjust_window = None
        self._adjust_operation = None
        self.single_draft = None
        self.single_window = None
        self._single_refresh = False
        self._single_submit = False
        self._single_success = False
        self.character_references, self.character_analysis, self.character_traits = (
            load_character_sheet(ROOT)
        )
        self.character_analysis_running = False
        self.character_dialog: CharacterReferenceWindow | None = None
        self.character_feature_store = CharacterFeatureStore(self.history_store.data / "character_features.sqlite3")
        self._variables()
        self._build()
        self.event_router = self._build_event_router()
        self._refresh_generation_models()
        self._refresh_history()
        self.root.after(100, self._consume_messages)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    @property
    def working(self):
        return self.tasks.working if hasattr(self, "tasks") else False

    def _variables(self) -> None:
        llm = self.config["llm"]
        comfy = self.config["comfyui"]
        options = self.config.get("ui", {})
        self.llm_url = tk.StringVar(value=llm.get("base_url", "http://127.0.0.1:1234"))
        self.comfy_url = tk.StringVar(value=comfy.get("base_url", "http://127.0.0.1:8188"))
        self.use_prompt_cache = tk.BooleanVar(value=options.get("use_prompt_cache", True))
        self.model = tk.StringVar(value="" if llm.get("model") == "SELECT_IN_GUI" else llm.get("model", ""))
        self.image_reasoning = tk.StringVar(value=IMAGE_REASONING_LABELS.get(llm.get("image_reasoning", "off"), "OFF"))
        try:
            self.camera_spec = camera_spec.normalize(options.get(camera_spec.KEY))
        except core.OrchestratorError:
            self.camera_spec = {}
        workflows = list(self.config.get("workflows", {}))
        preferred = options.get("workflow", workflows[0] if workflows else "自動")
        mode = options.get("generation_mode", workflow_generation_mode(self.config, preferred))
        if mode not in GENERATION_MODE_LABELS:
            mode = "image"
        self.generation_mode = tk.StringVar(value=mode)
        remembered = options.get("mode_workflows", {})
        if not isinstance(remembered, dict):
            remembered = {}
        self._mode_workflows = {
            key: choose_mode_workflow(self.config, key, remembered.get(key))
            for key in GENERATION_MODE_LABELS
        }
        chosen = choose_mode_workflow(self.config, mode, preferred)
        self._mode_workflows[mode] = chosen
        self.workflow = tk.StringVar(value=chosen)
        self.workflow_names = workflow_display_names(self.config)
        self.workflow_choice = tk.StringVar(value=self.workflow_names.get(chosen, ""))
        self.workflow.trace_add("write", self._sync_workflow_choice)
        self._extra_references = False
        self.width = tk.StringVar(value=str(options.get("width", 768)))
        self.height = tk.StringVar(value=str(options.get("height", 768)))
        self.resolution_preset = tk.StringVar(
            value=resolution_preset_label(self.width.get(), self.height.get())
        )
        self._custom_size_editing = self.resolution_preset.get() == CUSTOM_RESOLUTION
        self.width.trace_add("write", self._sync_resolution_preset)
        self.height.trace_add("write", self._sync_resolution_preset)
        self.video_size = tk.StringVar(value=str(options.get("video_size", VIDEO_RESOLUTIONS[0])))
        self.video_frames = tk.StringVar(value=str(options.get("video_frames", 49)))
        self.video_fps = tk.StringVar(value=str(options.get("video_fps", 24)))
        self.hunyuan_size = tk.StringVar(value=str(options.get("hunyuan_size", HUNYUAN_RESOLUTIONS[0])))
        self.hunyuan_frames = tk.StringVar(value=str(options.get("hunyuan_frames", 121)))
        self.hunyuan_steps = tk.StringVar(value=str(options.get("hunyuan_steps", 8)))
        self.h3_size = tk.StringVar(value=str(options.get("h3_size", H3_RESOLUTIONS[0])))
        self.h3_duration = tk.StringVar(value=str(options.get("h3_duration", next(iter(H3_DURATIONS)))))
        self.h3_connection = tk.StringVar(value=connection_label(
            preferred_connection_frames(options.get("h3_overlap_frames"))))
        target = options.get("h3_long_target", "30秒")
        try:
            self._custom_cut_frames = validate_cut_frames(options.get("h3_cut_frames", []))
        except core.OrchestratorError:
            self._custom_cut_frames = None
        if target == CUSTOM_CUTS and self._custom_cut_frames is None:
            target = "30秒"
        self.h3_long_target = tk.StringVar(value=target if target in (*CONTINUOUS_TARGETS, CUSTOM_CUTS) else "30秒")
        self.h3_cut_summary = tk.StringVar()
        self.h3_long_target.trace_add("write", self._sync_cut_summary)
        self._sync_cut_summary()
        model_key = options.get("h3_model", "int8")
        turbo_key = options.get("h3_turbo", "off")
        # The existing full label is the stable, mode-specific saved state.
        # The short model name and input mode are presentation variables only.
        self.h3_model = tk.StringVar(value=core.h3_model_label(model_key))
        self.h3_model_display = tk.StringVar(value="")
        self.h3_input_mode = tk.StringVar(value="")
        self._h3_picker_models = ()
        self._h3_picker_state = None
        self.generation_inventory = None
        self.checkpoint_model = tk.StringVar(value=options.get("checkpoint_model", core.DEFAULT_SDXL_CHECKPOINT))
        self.anima_model = tk.StringVar(value=options.get("anima_model", ANIMA_BASE))
        self.qwen_model = tk.StringVar(value=options.get("qwen_model", ""))
        self.qwen_steps = tk.StringVar(value=str(options.get("qwen_steps", 50)))
        self.qwen_cfg = tk.StringVar(value=str(options.get("qwen_cfg", 4)))
        self.qwen_fixed_steps = tk.StringVar(value="4")
        self.qwen_fixed_cfg = tk.StringVar(value="1")
        self.h3_turbo = tk.StringVar(value=core.H3_TURBO_LABELS.get(turbo_key, "OFF"))
        self.h3_encoder_cpu = tk.BooleanVar(value=options.get("h3_encoder_device", "cpu") == "cpu")
        self.h3_encoder_model = tk.StringVar(value=core.H3_ENCODER_LABELS.get(
            options.get("h3_encoder_model", "nvfp4"), "NVFP4 AWQ"))
        self.h3_steps = tk.StringVar(value=str(options.get("h3_steps", options.get("steps", 20))))
        self.h3_hybrid_steps = tk.StringVar(value=str(options.get("h3_hybrid_steps", core.H3_HYBRID_DEFAULT_STEPS)))
        self.h3_performance = tk.StringVar(value=core.H3_PERFORMANCE_LABELS.get(
            options.get("h3_hybrid_performance", options.get("h3_performance", "standard")),
            core.H3_PERFORMANCE_LABELS["standard"]))
        self.h3_fixed_steps = tk.StringVar(value="")
        self.steps = tk.StringVar(value=str(options.get("steps", 20)))
        self.cfg = tk.StringVar(value=str(options.get("cfg", 5.0)))
        self.seed = tk.StringVar(value=str(options.get("seed", "")))
        self.denoise = tk.StringVar(value=str(options.get("denoise", 0.53)))
        self.reference_image = tk.StringVar(value="")
        self.composition_image = tk.StringVar(value="")
        self.mask_image = tk.StringVar(value="")
        self.pose_image = tk.StringVar(value="")
        self.pose_mode = tk.StringVar(value=str(options.get("pose_mode", "skeleton")))
        self.control_strength = tk.StringVar(value=str(options.get("control_strength", 0.85)))
        self._source_change_lock = False
        self._last_reference_image = ""
        self.dark_mode = tk.BooleanVar(value=bool(options.get("dark_mode", False)))
        requested_font = options.get("font_size", 12)
        if isinstance(requested_font, bool) or not isinstance(requested_font, int):
            requested_font = 12
        self.editor_font_size = tk.IntVar(value=max(10, min(20, requested_font)))
        self.unload_llm = tk.BooleanVar(value=llm.get("unload_after_inference", True))
        self.vision_composition = tk.BooleanVar(
            value=bool(llm.get("send_reference_to_llm", False))
        )
        self.t2i_profile = tk.StringVar(
            value=T2I_PROFILE_LABELS.get(
                llm.get("t2i_prompt_profile", DEFAULT_T2I_PROFILE),
                T2I_PROFILE_LABELS[DEFAULT_T2I_PROFILE],
            )
        )
        self.i2i_profile = tk.StringVar(
            value=I2I_PROFILE_LABELS.get(
                llm.get("i2i_prompt_profile", DEFAULT_I2I_PROFILE),
                I2I_PROFILE_LABELS[DEFAULT_I2I_PROFILE],
            )
        )
        self.h3_profile = tk.StringVar(
            value=H3_PROFILE_LABELS.get(
                llm.get("h3_prompt_profile", DEFAULT_H3_PROFILE),
                H3_PROFILE_LABELS[DEFAULT_H3_PROFILE],
            )
        )
        self.free_comfy = tk.BooleanVar(value=comfy.get("free_before_llm", True))
        self._mode_settings = ModeSettings(self, mode, options.get("mode_settings"))
        self.status = tk.StringVar(value="準備完了")
        self.timing_status = tk.StringVar(value="")
        self._operations_window = None
        self._operations_pending = False
        self.character_status = tk.StringVar(
            value=character_status_label(self.character_references, self.character_traits)
        )

    def _build(self) -> None:
        colors = apply_ttk_theme(self.root, self.dark_mode.get())

        layout = ttk.Frame(self.root, padding=10)
        layout.pack(fill="both", expand=True)
        self.settings_panel = ConnectionPanel(
            layout, ConnectionVariables(
                model=self.model,
                llm_url=self.llm_url,
                comfy_url=self.comfy_url,
                unload_llm=self.unload_llm,
                free_comfy=self.free_comfy,
                use_prompt_cache=self.use_prompt_cache,
                h3_encoder_model=self.h3_encoder_model,
                h3_encoder_cpu=self.h3_encoder_cpu,
                dark_mode=self.dark_mode,
            ), ConnectionActions(
                refresh_models=self._refresh_models,
                clear_cache=self._clear_prompt_cache,
                switch_theme=self._switch_theme,
                save=self._save_settings,
                check=self._check_connections,
                recover_jobs=self._recover_jobs,
                release_memory=self._release_comfy_memory,
                show_operations=self._show_operations,
            ),
        )
        self.model_box = self.settings_panel.model_box
        ttk.Button(self.settings_panel.topbar, text="生成モデル管理…",
                   command=self._open_model_manager).pack(side="left", padx=(6, 0))
        self.recover_jobs_button = self.settings_panel.recover_jobs_button
        self.free_memory_button = self.settings_panel.free_memory_button

        # Keep the generation tabs and their own workflow selectors above the
        # shared editor/result area, outside the scrollable option form.
        self.generation_tabs = ttk.Notebook(layout, style="Generation.TNotebook")
        self.generation_tabs.pack(fill="x", pady=(8, 0))
        self._mode_pages = {}
        self._mode_boxes = {}
        self._mode_vars = {}
        for mode, label in GENERATION_MODE_LABELS.items():
            page = ttk.Frame(self.generation_tabs, padding=(8, 6))
            self.generation_tabs.add(page, text=label)
            self._mode_pages[mode] = page
            chosen = self._mode_workflows[mode]
            variable = tk.StringVar(value=self.workflow_names.get(chosen, ""))
            self._mode_vars[mode] = variable
            choices = mode_workflow_ids(self.config, mode)
            ttk.Label(page, text="モデル" if mode == "image" else "動画方式").pack(side="left", padx=(0, 6))
            box = ttk.Combobox(
                page, textvariable=variable, width=30,
                values=tuple(self.workflow_names[key] for key in choices),
                state="readonly" if len(choices) > 1 else "disabled",
            )
            box.pack(side="left", fill="x", expand=True)
            box.bind("<<ComboboxSelected>>", self._on_workflow_choice)
            self._mode_boxes[mode] = box
            if mode == "image":
                ttk.Label(page, text="LLM思考").pack(side="left", padx=(10, 4))
                self.image_reasoning_box = ttk.Combobox(page, textvariable=self.image_reasoning,
                    values=tuple(IMAGE_REASONING_LABELS.values()), state="readonly", width=5)
                self.image_reasoning_box.pack(side="left")
                self.model_compare_button = ttk.Button(page, text="モデル比較…", command=self._open_model_comparison)
                self.model_compare_button.pack(side="left", padx=(8, 0))
                self.camera_button = ttk.Button(page, text="画角…", command=self._edit_camera)
                self.camera_button.pack(side="left", padx=(6, 0))
                self._sync_camera_button()
        self._sync_workflow_choice()
        self.generation_tabs.bind("<<NotebookTabChanged>>", self._on_generation_tab_changed)

        # The footer is laid out before the resizable main panes to guarantee
        # that status and the optional log never fall below the visible screen.
        footer = ttk.Frame(layout)
        footer.pack(side="bottom", fill="x")
        status_bar = ttk.Frame(footer)
        status_bar.pack(side="bottom", fill="x", pady=(3, 0))
        ttk.Label(
            status_bar, textvariable=self.status, width=40, anchor="w",
        ).pack(side="left", fill="x", expand=True)
        self.logs_visible = False
        self.log_toggle = ttk.Button(
            status_bar, text="ログを表示", command=self._toggle_logs,
        )
        self.log_toggle.pack(side="right", padx=(8, 0))
        self.progress_bar = ttk.Progressbar(status_bar, mode="indeterminate", length=125)
        self.progress_bar.pack(side="right")
        ttk.Label(footer, textvariable=self.timing_status, anchor="w").pack(side="bottom", fill="x")
        # Hidden on startup: logs remain buffered, without consuming screen height.
        self.logs_panel = ttk.LabelFrame(footer, text="実行ログ", padding=5)
        self.log = scrolledtext.ScrolledText(
            self.logs_panel, height=4, wrap="word", state="disabled",
            font=("Meiryo UI", 9), padx=9, pady=7,
        )
        self.log.pack(fill="x")

        main = ttk.Panedwindow(layout, orient="horizontal")
        main.pack(fill="both", expand=True, pady=(8, 5))

        left = ttk.Frame(main)
        right = ttk.Frame(main)
        main.add(left, weight=3)
        main.add(right, weight=2)

        self.generation_view = GenerationView(
            left, self.root, colors, GenerationVariables(
                editor_font_size=self.editor_font_size,
                reference_image=self.reference_image,
                mask_image=self.mask_image,
                character_status=self.character_status,
                composition_image=self.composition_image,
                pose_image=self.pose_image,
                pose_mode=self.pose_mode,
                vision_composition=self.vision_composition,
                resolution_preset=self.resolution_preset,
                width=self.width,
                height=self.height,
                video_size=self.video_size,
                video_frames=self.video_frames,
                video_fps=self.video_fps,
                h3_size=self.h3_size,
                h3_duration=self.h3_duration,
                h3_connection=self.h3_connection,
                h3_long_target=self.h3_long_target,
                h3_cut_summary=self.h3_cut_summary,
                hunyuan_size=self.hunyuan_size,
                hunyuan_frames=self.hunyuan_frames,
                hunyuan_steps=self.hunyuan_steps,
                steps=self.steps,
                cfg=self.cfg,
                qwen_steps=self.qwen_steps,
                qwen_cfg=self.qwen_cfg,
                qwen_fixed_steps=self.qwen_fixed_steps,
                qwen_fixed_cfg=self.qwen_fixed_cfg,
                seed=self.seed,
                denoise=self.denoise,
                control_strength=self.control_strength,
                t2i_profile=self.t2i_profile,
                i2i_profile=self.i2i_profile,
                h3_profile=self.h3_profile,
                checkpoint_model=self.checkpoint_model,
                h3_model=self.h3_model_display,
                h3_input_mode=self.h3_input_mode,
                h3_turbo=self.h3_turbo,
                h3_performance=self.h3_performance,
            ), GenerationActions(
                change_font=self._change_editor_font,
                browse_image=self._browse_image,
                edit_mask=self._edit_mask,
                toggle_extra=self._toggle_extra_references,
                open_character=self._open_character_references,
                drop_character=self._drop_character_files,
                browse_composition=self._browse_composition,
                browse_pose=self._browse_pose,
                pose_changed=self._on_pose_image_changed,
                show_composition=self._show_composition_report,
                apply_resolution=self._apply_resolution_preset,
                edit_cut_durations=self._edit_cut_durations,
                sync_steps=self._sync_h3_steps,
                performance_changed=self._on_h3_performance_choice,
                model_changed=self._on_h3_model_choice,
                input_mode_changed=self._on_h3_input_mode_choice,
                run=self._run_primary,
                preview=self._run_secondary,
                cancel=self._request_cancel,
                long_action=lambda key: self.project_workspace._accept(key),
            ),
        )
        self.generation_view.pack(fill="both", expand=True, padx=(0, 6))
        # Existing application actions still use these handles; the view owns
        # their construction and local geometry.
        self.prompt_panel = self.generation_view
        self.form_canvas = self.generation_view.form_canvas
        self.options_form = self.generation_view.options_form
        self.form_window = self.generation_view.form_window
        self.prompt_title = self.generation_view.prompt_title
        self.prompt = self.generation_view.prompt
        self.reference_row = self.generation_view.reference_row
        self.mask_row = self.generation_view.mask_row
        self.reference_tools = self.generation_view.reference_tools
        self.extra_button = self.generation_view.extra_button
        self.character_button = self.generation_view.character_button
        self.composition_row = self.generation_view.composition_row
        self.pose_row = self.generation_view.pose_row
        self.pose_modes = self.generation_view.pose_modes
        self.vision_row = self.generation_view.vision_row
        self.vision_checkbox = self.generation_view.vision_checkbox
        self.parameter_widgets = self.generation_view.parameter_widgets
        self.resolution_box = self.generation_view.resolution_box
        self.width_entry = self.generation_view.width_entry
        self.height_entry = self.generation_view.height_entry
        self.h3_duration_title = self.generation_view.h3_duration_title
        self.steps_entry = self.generation_view.steps_entry
        self.cfg_entry = self.generation_view.cfg_entry
        self.seed_entry = self.generation_view.seed_entry
        self.random_seed_button = self.generation_view.random_seed_button
        self.denoise_entry = self.generation_view.denoise_entry
        self.strength_entry = self.generation_view.strength_entry
        self.t2i_profile_box = self.generation_view.t2i_profile_box
        self.i2i_profile_box = self.generation_view.i2i_profile_box
        self.h3_profile_box = self.generation_view.h3_profile_box
        self.checkpoint_box = self.generation_view.checkpoint_box
        self.h3_model_box = self.generation_view.h3_model_box
        self.h3_input_mode_box = self.generation_view.h3_input_mode_box
        self.h3_model.trace_add("write", self._sync_h3_model_picker)
        self._sync_h3_model_picker()
        self.h3_turbo_box = self.generation_view.h3_turbo_box
        self.h3_performance_box = self.generation_view.h3_performance_box
        self.run_button = self.generation_view.run_button
        self.preview_button = self.generation_view.preview_button
        self.cancel_button = self.generation_view.cancel_button
        self.long_actions_button = self.generation_view.long_actions_button
        self.long_actions_menu = self.generation_view.long_actions_menu
        self._long_menu_keys = self.generation_view._long_menu_keys
        self.mask_button = self.generation_view.mask_button
        self.reference_image.trace_add("write", lambda *_args: self._on_reference_image_changed())
        self.mask_image.trace_add("write", lambda *_args: self._on_mask_image_changed())
        self.pose_image.trace_add("write", lambda *_args: self._on_pose_image_changed())
        self.composition_image.trace_add("write", self._on_composition_image_changed)

        self.tabs = ttk.Notebook(right)
        self.tabs.pack(fill="both", expand=True)
        self.result_panel = ResultView(
            self.tabs, ResultActions(
                open_image=self._open_image,
                open_outputs=self._open_outputs,
                show_prompt=self._show_prompt_preview,
                use_material=self._current_output_material,
                adjust=self._open_adjust_current,
            ),
        )
        self.tabs.add(self.result_panel, text="結果")
        self.history_panel = HistoryView(
            self.tabs, HistoryActions(
                select=self._history_selection_changed,
                restore=self._restore_selected_history,
                open_output=self._open_history_output,
                restore_request=self._restore_selected_history_request,
                compare=self._compare_selected_history,
                replay=self._regenerate_selected_history,
                show_prompt=self._show_selected_history_prompt,
                refresh=self._refresh_history,
                restore_character=self._restore_selected_character_traits,
                use_material=self._history_output_material,
                adjust=self._open_adjust_history,
                change_flags=self._change_history_flags,
            ),
        )
        self.tabs.add(self.history_panel, text="履歴")
        self.project_workspace = ProjectWorkspace(
            self.tabs, self.long_video_store, on_refresh=self._refresh_projects,
            on_action=self._project_action, on_load=self._restore_project_inputs,
            on_actions_changed=self._project_actions_changed,
            on_prompt_action=self._edit_project_prompt,
        )
        self.tabs.add(self.project_workspace, text="プロジェクト")
        self.tabs.hide(self.project_workspace)
        self._project_visible = False
        self._project_refresh_serial = 0

        self.tabs.bind("<<NotebookTabChanged>>", self._output_tab_changed)
        self._switch_theme()
        self._update_generation_controls()
        install_native_ime_font(self.prompt)
        self._log("GUI起動。LM StudioのDeveloper画面でLocal Serverを起動してください。")
        self._log("設定は comfy-orchestrator/config.json に保存され、Gitには含まれません。")

    def _toggle_extra_references(self) -> None:
        self._extra_references = not self._extra_references
        self._update_generation_controls()

    def _sync_workflow_choice(self, *_args) -> None:
        chosen = self.workflow.get()
        if hasattr(self, "generation_mode"):
            mode = self.generation_mode.get()
            if hasattr(self, "_mode_settings") and self._mode_settings.switch(self, mode):
                self._custom_size_editing = self.resolution_preset.get() == CUSTOM_RESOLUTION
            choices = mode_workflow_ids(self.config, mode)
            if chosen in choices:
                self._mode_workflows[mode] = chosen
            values = tuple(self.workflow_names[key] for key in choices)
            if hasattr(self, "_mode_pages"):
                page = self._mode_pages[mode]
                self.workflow_box = self._mode_boxes[mode]
                self.workflow_choice = self._mode_vars[mode]
                if self.generation_tabs.select() != str(page):
                    self.generation_tabs.select(page)
            if mode == "image" and hasattr(self, "_mode_boxes") and hasattr(self, "anima_model"):
                self._refresh_image_picker()
                self._mode_choices_key = None
                return
            key = (mode, values)
            if hasattr(self, "workflow_box") and getattr(self, "_mode_choices_key", None) != key:
                self.workflow_box.configure(values=values, state="readonly" if len(values) > 1 else "disabled")
                self._mode_choices_key = key
        label = self.workflow_names.get(chosen, chosen)
        if self.workflow_choice.get() != label:
            self.workflow_choice.set(label)

    def _on_generation_tab_changed(self, _event=None) -> None:
        selected = self.generation_tabs.select()
        mode = next((key for key, page in self._mode_pages.items()
                     if str(page) == selected), None)
        if mode is None or self.generation_mode.get() == mode:
            return
        self.generation_mode.set(mode)
        self._on_generation_mode_choice()

    def _on_generation_mode_choice(self) -> None:
        mode = self.generation_mode.get()
        chosen = choose_mode_workflow(self.config, mode, self._mode_workflows.get(mode))
        self.workflow.set(chosen)
        self._sync_workflow_choice()
        self._update_generation_controls()

    def _refresh_image_picker(self):
        if not hasattr(self, "_mode_boxes") or "image" not in self._mode_boxes:
            return
        inventory = self.generation_inventory
        registrations = getattr(self, "_registered_models", ())
        installed = core.installed_model_choices(inventory, registrations)["sdxl"]
        choices = image_model_choices(self.config["workflows"], inventory, installed,
                                      self.checkpoint_model.get(), self.anima_model.get(),
                                      registrations, self.qwen_model.get())
        self._image_choices = {item.label: item for item in choices}
        comparison = getattr(self, "comparison_window", None)
        if comparison is not None and comparison.winfo_exists() and not comparison.busy:
            comparison.set_choices(choices)
        box = self._mode_boxes["image"]
        box.configure(values=tuple(self._image_choices), state="readonly" if choices else "disabled")
        if self.generation_mode.get() == "image":
            label = selected_label(choices, self.workflow.get(),
                                   self.checkpoint_model.get(), self.anima_model.get(), self.qwen_model.get())
            self._mode_vars["image"].set(label or self.workflow_names.get(self.workflow.get(), self.workflow.get()))

    def _select_image_model(self):
        choice = self._image_choices.get(self.workflow_choice.get())
        if choice is None or self.working:
            self._refresh_image_picker()
            return
        has_input = any(v.get().strip() for v in (self.reference_image, self.mask_image, self.pose_image))
        turbo = choice.filename is not None and core.sdxl_checkpoint_kind(choice.filename) == "turbo"
        if has_input and (choice.workflow_id in T2I_ONLY or turbo):
            messagebox.showwarning("モデル選択", "このモデルはT2I専用です。参照画像・マスク・ポーズを解除してください。")
            self._refresh_image_picker()
            return
        if choice.workflow_id == "wai_t2i_basic":
            self.checkpoint_model.set(choice.filename)
        elif choice.workflow_id == ANIMA_ID:
            self.anima_model.set(choice.filename)
        elif choice.workflow_id == core.QWEN_T2I_ID:
            self.qwen_model.set(choice.filename or "")
        selected = resolve_generation_workflow(self.config, choice.workflow_id,
                    bool(self.reference_image.get().strip()), bool(self.mask_image.get().strip()),
                    bool(self.pose_image.get().strip()), self.pose_mode.get()) or choice.workflow_id
        # Start from the target graph defaults, not the previous family's sampler.
        defaults = defaults_for(self.config["workflows"],
                               type(choice)(choice.label, selected, choice.filename), turbo=turbo,
                               registrations=getattr(self, "_registered_models", ()))
        if selected == core.QWEN_T2I_ID:
            self.qwen_steps.set(str(defaults["steps"]))
            self.qwen_cfg.set(str(defaults["cfg"]))
        else:
            for name in ("steps", "cfg"):
                if name in defaults:
                    getattr(self, name).set(str(defaults[name]))
        for name in ("width", "height", "denoise", "control_strength"):
            if name in defaults:
                getattr(self, name).set(str(defaults[name]))
        self.workflow.set(selected)
        self._generation_ui_key = None
        self._update_generation_controls()
        self._sync_h3_steps()
        self._refresh_image_picker()

    def _on_workflow_choice(self, _event=None) -> None:
        # Ignore queued events from a hidden selector after changing tabs.
        if (_event is not None and hasattr(self, "_mode_boxes")
                and _event.widget is not self.workflow_box):
            return
        if hasattr(self, "_image_choices") and self.generation_mode.get() == "image":
            self._select_image_model()
            return
        choices = (mode_workflow_ids(self.config, self.generation_mode.get())
                   if hasattr(self, "generation_mode") else self.workflow_names)
        by_label = {self.workflow_names[key]: key for key in choices}
        if self.workflow_choice.get() in by_label:
            self.workflow.set(by_label[self.workflow_choice.get()])
        self._update_generation_controls()

    def _on_composition_image_changed(self, *_args) -> None:
        if not self._source_change_lock:
            self._update_generation_controls()

    def _toggle_logs(self) -> None:
        if self.logs_visible:
            self.logs_panel.pack_forget()
            self.log_toggle.configure(text="ログを表示")
        else:
            self.logs_panel.pack(fill="x", pady=(5, 0))
            self.log_toggle.configure(text="ログを隠す")
        self.logs_visible = not self.logs_visible

    def _switch_theme(self) -> None:
        """Recolor widgets without rebuilding the window or resetting user text."""
        colors = apply_ttk_theme(self.root, self.dark_mode.get())
        style_text_widget(self.prompt, colors)
        style_text_widget(self.log, colors, muted=True)
        style_text_widget(self.result_panel.images_list, colors)
        if hasattr(self, "project_workspace"):
            self.project_workspace.apply_theme(colors)
        self.form_canvas.configure(background=colors["surface"])
        self.prompt.configure(
            font=("Meiryo UI", self.editor_font_size.get()),
            padx=14, pady=12,
        )
        # The active IME overlay has its own font; update it as well.
        sync_native_ime_font(self.prompt)

    def _change_editor_font(self, delta: int) -> None:
        """Adjust readability without disturbing focus, text, or IME input."""
        size = max(10, min(20, self.editor_font_size.get() + delta))
        self.editor_font_size.set(size)
        self.prompt.configure(font=("Meiryo UI", size))
        sync_native_ime_font(self.prompt)

    def _active_workflow(self) -> str | None:
        chosen = self.workflow.get()
        if hasattr(self, "generation_mode"):
            mode = self.generation_mode.get()
            chosen = choose_mode_workflow(self.config, mode, chosen)
            if mode != "image":
                return chosen or None
        get = lambda name: bool(getattr(self, name, None) and getattr(self, name).get().strip())
        pose_mode = getattr(self, "pose_mode", None)
        return resolve_generation_workflow(
            self.config, chosen,
            get("reference_image"), get("mask_image"), get("pose_image"),
            pose_mode.get() if pose_mode is not None else "skeleton",
        )

    def _on_reference_image_changed(self) -> None:
        """Reference removed -> T2I; reference added -> I2I automatically."""
        if getattr(self, "_source_change_lock", False):
            return
        self._source_change_lock = True
        try:
            source = self.reference_image.get().strip()
            previous = getattr(self, "_last_reference_image", "")
            self._last_reference_image = source
            if hasattr(self, "mask_image") and source != previous and self.mask_image.get():
                self.mask_image.set("")
            if source and hasattr(self, "pose_image") and self.pose_image.get():
                self.pose_image.set("")
        finally:
            self._source_change_lock = False
        chosen = self._active_workflow()
        if chosen and chosen != self.workflow.get():
            self.workflow.set(chosen)
        self._update_generation_controls()

    def _on_pose_image_changed(self) -> None:
        if self._source_change_lock:
            return
        self._source_change_lock = True
        try:
            if self.pose_image.get().strip():
                self.reference_image.set("")
                self.mask_image.set("")
                self._last_reference_image = ""
        finally:
            self._source_change_lock = False
        chosen = self._active_workflow()
        if chosen and chosen != self.workflow.get():
            self.workflow.set(chosen)
        self._update_generation_controls()

    def _on_mask_image_changed(self) -> None:
        if self._source_change_lock:
            return
        chosen = self._active_workflow()
        if chosen and chosen != self.workflow.get():
            self.workflow.set(chosen)
        self._update_generation_controls()

    def _sync_resolution_preset(self, *_args) -> None:
        label = resolution_preset_label(self.width.get(), self.height.get())
        if self.resolution_preset.get() != label:
            self.resolution_preset.set(label)
        if hasattr(self, "parameter_widgets"):
            self._refresh_custom_dimensions()

    def _refresh_custom_dimensions(self) -> None:
        visible = parameter_visibility(
            self.config, self._active_workflow(),
            self._custom_size_editing or self.resolution_preset.get() == CUSTOM_RESOLUTION,
        )["custom_size"]
        for widget in self.parameter_widgets["custom_size"]:
            set_grid_visible(widget, visible)

    def _apply_resolution_preset(self, _event=None) -> None:
        dimensions = RESOLUTION_PRESETS.get(self.resolution_preset.get())
        self._custom_size_editing = dimensions is None
        if dimensions is None:
            if hasattr(self, "parameter_widgets"):
                self._refresh_custom_dimensions()
            self.width_entry.focus_set()
            return
        width, height = dimensions
        self.width.set(str(width))
        self.height.set(str(height))
        if hasattr(self, "parameter_widgets"):
            self._refresh_custom_dimensions()

    def _h3_choices(self) -> dict:
        model = core.h3_model_from_label(self.h3_model.get())
        turbo = ("off" if core.h3_hybrid_filename(model) is not None else
                 next((key for key, label in core.H3_TURBO_LABELS.items() if label == self.h3_turbo.get()), None))
        if model is None or turbo is None:
            raise core.OrchestratorError("H3モデルまたはTurbo設定が不正です")
        options = {"h3_model": model, "h3_turbo": turbo}
        if registered_h3_turbo(model):
            options["h3_performance"] = "euler_dense"
        elif core.h3_hybrid_filename(model) is not None and hasattr(self, "h3_performance"):
            performance = next((key for key, label in core.H3_PERFORMANCE_LABELS.items()
                                if label == self.h3_performance.get()), None)
            if performance is None:
                raise core.OrchestratorError("H3高速化設定が不正です")
            if performance != "standard":
                options["h3_performance"] = performance
        if hasattr(self, "h3_encoder_cpu"):
            options["h3_encoder_device"] = "cpu" if self.h3_encoder_cpu.get() else "default"
        if hasattr(self, "h3_encoder_model"):
            encoder = next((key for key, label in core.H3_ENCODER_LABELS.items()
                            if label == self.h3_encoder_model.get()), None)
            if encoder is None:
                raise core.OrchestratorError("H3テキストエンコーダーの選択が不正です")
            options["h3_encoder_model"] = encoder
        return options

    def _sync_h3_model_picker(self, *_args):
        """Project the exact model key into two short, independent controls."""
        if not hasattr(self, "h3_input_mode_box"):
            return
        current = core.h3_model_from_label(self.h3_model.get())
        local = core.installed_model_choices(self.generation_inventory, getattr(self, "_registered_models", ()))["h3"]
        installed = (*core.H3_MODEL_LABELS, *local) if self.generation_inventory is None else local
        models = h3_picker_choices(installed, current)
        choice = next((item for item in models if item.contains(current)), None)
        if choice is None:
            # Keep invalid stored configuration visible as invalid rather than
            # silently selecting another model.
            self.h3_model_display.set(self.h3_model.get())
            self.h3_input_mode.set("")
            self.h3_model_box.configure(values=tuple(item.label for item in models))
            self.h3_input_mode_box.configure(values=(), state="disabled")
            self._h3_picker_models = models
            self._h3_picker_state = None
            return
        has_image = bool(self.reference_image.get().strip())
        mode = choice.display_mode(current, has_image=has_image)
        modes = choice.mode_options(has_image=has_image)
        labels = tuple(item.label for item in models)
        state = (models, choice.label, mode, modes)
        self._h3_picker_models = models
        if self._h3_picker_state != state:
            self._h3_picker_state = state
            self.h3_model_box.configure(values=labels)
            self.h3_input_mode_box.configure(values=modes, state="readonly" if len(modes) > 1 else "disabled")
        if self.h3_model_display.get() != choice.label:
            self.h3_model_display.set(choice.label)
        if self.h3_input_mode.get() != mode:
            self.h3_input_mode.set(mode)

    def _on_h3_model_choice(self, _event=None) -> None:
        choice = next((item for item in self._h3_picker_models
                       if item.label == self.h3_model_display.get()), None)
        if choice is None:
            self._sync_h3_model_picker()
            return
        previous = core.h3_model_from_label(self.h3_model.get())
        key = select_model_key(choice, previous, has_image=bool(self.reference_image.get().strip()))
        self.h3_model.set(core.h3_model_label(key))
        # Different merged/quantized weights have not been validated with Turbo.
        # Start their comparison without an additional LoRA; user may opt in.
        if key not in ("int8", "w4a8"):
            self.h3_turbo.set("OFF")
        if parse_h3_key(key) is not None:
            item = registration_for_key(getattr(self, "_registered_models", ()), key)
            if registered_h3_turbo(key):
                self.h3_hybrid_steps.set("8")
            elif item is not None:
                self.h3_steps.set(str(item.steps if item.steps is not None else item.spec.default_steps))
        self._sync_h3_steps()

    def _on_h3_input_mode_choice(self, _event=None) -> None:
        current = core.h3_model_from_label(self.h3_model.get())
        choice = next((item for item in self._h3_picker_models if item.contains(current)), None)
        if choice is None:
            self._sync_h3_model_picker()
            return
        mode = self.h3_input_mode.get()
        if mode not in choice.mode_options(has_image=bool(self.reference_image.get().strip())):
            self._sync_h3_model_picker()
            return
        key = choice.key_for_mode(mode)
        if key is not None and key != current:
            self.h3_model.set(core.h3_model_label(key))
            self._sync_h3_steps()
        self._sync_h3_model_picker()

    def _on_h3_performance_choice(self, _event=None) -> None:
        performance = self._h3_choices().get("h3_performance", "standard")
        try:
            core.validate_h3_hybrid_steps(int(self.h3_hybrid_steps.get()), performance)
        except (ValueError, core.OrchestratorError):
            self.h3_hybrid_steps.set("8")
        self._sync_h3_steps()

    def _sdxl_turbo_active(self) -> bool:
        return (self._active_workflow() == "wai_t2i_basic"
                and hasattr(self, "checkpoint_model")
                and core.sdxl_checkpoint_kind(self.checkpoint_model.get()) == "turbo")

    def _sync_h3_steps(self, _event=None) -> None:
        if not hasattr(self, "h3_steps"):
            return
        is_h3 = self._active_workflow() == core.H3_I2V_ID
        turbo_checkpoint = (self._sdxl_turbo_active() if hasattr(self, "checkpoint_model") else False)
        h3_choices = self._h3_choices() if is_h3 else {}
        hybrid = core.h3_hybrid_filename(h3_choices.get("h3_model")) is not None
        fixed_manual = registered_h3_turbo(h3_choices.get("h3_model"))
        if hasattr(self, "parameter_widgets"):
            for widget in self.parameter_widgets.get("h3_turbo", ()):
                set_grid_visible(widget, is_h3 and not hybrid)
            for widget in self.parameter_widgets.get("h3_performance", ()):
                set_grid_visible(widget, hybrid and not fixed_manual)
        if is_h3 and hasattr(self, "h3_turbo_box"):
            if hybrid:
                self.h3_turbo.set("OFF")
            self.h3_turbo_box.configure(state="disabled" if hybrid else "readonly")
        fixed = core.H3_TURBOS[h3_choices["h3_turbo"]][1] if is_h3 else 4 if turbo_checkpoint else None
        if hybrid and h3_choices.get("h3_performance") in ("euler_dense", "kitchen_int8"):
            fixed = 8
        if hasattr(self, "checkpoint_model") and hasattr(self, "cfg_entry"):
            entry = self.config["workflows"].get(self._active_workflow(), {})
            cfg_variable = self.qwen_fixed_cfg if turbo_checkpoint else self.cfg
            self.cfg_entry.configure(textvariable=cfg_variable, state="readonly" if turbo_checkpoint
                                     else "normal" if "cfg" in entry.get("bindings", {}) else "disabled")
        if fixed is not None:
            if self.h3_fixed_steps.get() != str(fixed):
                self.h3_fixed_steps.set(str(fixed))
            variable = self.h3_fixed_steps
        else:
            variable = self.h3_hybrid_steps if hybrid else self.h3_steps if is_h3 else self.steps
        key = (str(variable), fixed is not None)
        if getattr(self, "_steps_binding_key", None) != key:
            self.steps_entry.configure(textvariable=variable, state="readonly" if fixed is not None else "normal")
            self._steps_binding_key = key

    def _update_generation_controls(self) -> None:
        """Refresh fields in place; never replace the prompt, references or result pane."""
        workflow_id = self._active_workflow()
        self._sync_camera_button()
        if workflow_id and self.workflow.get() not in ("自動", workflow_id):
            self.workflow.set(workflow_id)
        entry = self.config["workflows"].get(workflow_id, {})
        is_video = entry.get("kind") in core.VIDEO_KINDS
        generation_mode = self.generation_mode.get() if hasattr(self, "generation_mode") else None
        state = parameter_visibility(
            self.config, workflow_id,
            getattr(self, "_custom_size_editing", False)
            or (hasattr(self, "resolution_preset") and self.resolution_preset.get() == CUSTOM_RESOLUTION),
            generation_mode=generation_mode,
        )
        if generation_mode == "image" and hasattr(self, "_image_choices"):
            state["checkpoint"] = False  # The image-tab model picker owns selection.
        has = lambda name: bool(getattr(self, name, None) and getattr(self, name).get().strip())
        reference = has("reference_image")
        pose = has("pose_image")
        composition = has("composition_image")
        expanded = getattr(self, "_extra_references", False)
        refs = reference_visibility(
            video=is_video, expanded=expanded,
            reference=reference, mask=has("mask_image"),
            pose=pose, composition=composition,
        )
        # Source path edits may emit dozens of traces with identical visibility.
        # Never issue geometry/configure writes when the effective UI is unchanged.
        ui_key = (workflow_id, generation_mode, tuple(state.items()), tuple(refs.items()), expanded,
                  reference, pose, composition)
        if getattr(self, "_generation_ui_key", None) == ui_key:
            return
        self._generation_ui_key = ui_key
        if hasattr(self, "project_workspace"):
            self._sync_project_visibility(generation_mode == "continuous")
        if hasattr(self, "prompt_title"):
            self.prompt_title.configure(text="計画プロンプト" if generation_mode == "continuous" else "プロンプト")
        if hasattr(self, "parameter_widgets"):
            for key, widgets in self.parameter_widgets.items():
                for widget in widgets:
                    set_grid_visible(widget, state[key])
            if state["steps"]:
                span = 3 if not state["cfg"] else 1
                if getattr(self, "_steps_span", None) != span:
                    self._steps_span = span
                    self.steps_entry.grid_configure(columnspan=span, padx=0 if span == 3 else (0, 8))
            self._sync_h3_steps()
        if hasattr(self, "reference_row"):
            if hasattr(self, "reference_tools"):
                set_grid_visible(self.reference_tools, not is_video)
            for key, name in (("mask", "mask_row"), ("pose", "pose_row"),
                              ("pose", "pose_modes"), ("composition", "composition_row"),
                              ("vision", "vision_row")):
                set_grid_visible(getattr(self, name), refs[key])
            self.extra_button.configure(text="追加参照 ▾" if expanded else "追加参照 ▸",
                                        state="disabled" if is_video else "normal")
        if hasattr(self, "h3_duration_title"):
            self.h3_duration_title.configure(text="計画用区間長 (24fps)" if state["h3_long"] else "長さ (24fps)")
        if hasattr(self, "run_button"):
            self.run_button.configure(text=GENERATION_MODE_LABELS.get(generation_mode, "動画生成" if is_video else "画像生成"))
        if hasattr(self, "preview_button"):
            if not self.preview_button.winfo_manager():
                self.preview_button.pack(side="left", padx=(0, 6), before=self.cancel_button)
            self.preview_button.configure(text="新規計画" if generation_mode == "continuous" else "プロンプト確認")
        if hasattr(self, "long_actions_button"):
            if generation_mode == "continuous":
                if not self.long_actions_button.winfo_manager():
                    self.long_actions_button.pack(side="left", padx=(0, 6), before=self.cancel_button)
            else:
                self.long_actions_button.pack_forget()
        for widget in (self.width_entry, self.height_entry):
            widget.configure(state="normal" if state["resolution"] else "disabled")
        if hasattr(self, "resolution_box"):
            self.resolution_box.configure(state="readonly" if state["resolution"] else "disabled")
        self.denoise_entry.configure(state="normal" if state["denoise"] else "disabled")
        if hasattr(self, "strength_entry"):
            self.strength_entry.configure(state="normal" if state["strength"] else "disabled")
        if hasattr(self, "cfg_entry"):
            self.cfg_entry.configure(state="readonly" if hasattr(self, "checkpoint_model") and self._sdxl_turbo_active()
                                     else "normal" if state["cfg"] else "disabled")
        if hasattr(self, "checkpoint_box"):
            self._apply_generation_model_choices()
        if hasattr(self, "t2i_profile_box"):
            self.t2i_profile_box.configure(state="readonly" if state["t2i_profile"] else "disabled")
        if hasattr(self, "i2i_profile_box"):
            self.i2i_profile_box.configure(state="readonly" if state["i2i_profile"] else "disabled")
        if hasattr(self, "mask_button"):
            self.mask_button.configure(state="normal" if has("reference_image") and not is_video else "disabled")
        if hasattr(self, "vision_checkbox"):
            self.vision_checkbox.configure(state="normal" if refs["vision"] else "disabled")

    def _log(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _refresh_history(self, select_id: str | None = None, *, scan_legacy: bool = True) -> None:
        self.history_refresh.request(select_id, scan_legacy=scan_legacy, working=self.working,
                                     query=self.history_panel.query())

    def _finish_history_refresh(self, entries, select_id, error) -> None:
        self.history_refresh.complete(
            entries, select_id, error, working=self.working,
            on_entries=self.history_panel.apply_page,
            on_error=self._history_read_error,
        )

    def _history_read_error(self, text):
        self._log("履歴の読み込みに失敗: " + text)
        self.history_panel.history_details.set("履歴の読み込みに失敗しました。更新してください")

    def _change_history_flags(self, field):
        if self.working or self.character_analysis_running:
            return
        entries = self._selected_history()
        if not entries or field not in ("favorite", "archived"):
            return
        value = not all(getattr(entry, field) for entry in entries)
        if field == "archived" and value and not messagebox.askyesno(
                "履歴を非表示", f"{len(entries)}件を通常の履歴から非表示にします。ファイルは削除しません。"):
            return
        ids = tuple(entry.id for entry in entries)
        self._set_busy("履歴を更新中")
        self._launch_generation(lambda: self.history_store.set_flags(ids, **{field: value}),
                                done_event="history_flags_changed")

    def _on_history_flags_changed(self, _data):
        self.status.set("履歴を更新しました")
        self.history_panel._history_read_pending = True
        self.history_panel.history_table.selection_remove(*self.history_panel.history_table.selection())
        self._refresh_history(scan_legacy=False)

    def _selected_history(self) -> list[HistoryEntry]:
        return self.history_panel.selected_entries()

    def _one_history(self) -> HistoryEntry | None:
        selected = self._selected_history()
        return selected[0] if len(selected) == 1 else None

    def _output_tab_changed(self, _event=None) -> None:
        # Only a visible pane may own an active decoder.
        if self.tabs.select() != str(self.result_panel):
            self.result_panel.result_video.stop()
        if self.tabs.select() != str(self.history_panel):
            self.history_panel.history_video.stop()
        if hasattr(self, "project_workspace") and self.tabs.select() != str(self.project_workspace):
            self.project_workspace.stop_preview()
        self._history_selection_changed()

    def _history_selection_changed(self, _event=None) -> None:
        self.history_panel.refresh_selection(
            self.config["workflows"], working=self.working,
            visible=self.tabs.select() == str(self.history_panel),
        )

    def _restore_selected_character_traits(self) -> None:
        if self.working or self.character_analysis_running:
            return
        entry = self._one_history()
        if entry is None or not entry.character_traits:
            return
        try:
            self._open_character_references()
            if self.character_dialog is not None:
                self.character_dialog.load_history_traits(entry.character_traits)
        except (OSError, ValueError, RuntimeError) as exc:
            messagebox.showerror("キャラ特徴の復元", str(exc))

    def _restore_selected_history_request(self) -> None:
        """Replace only the editable request, without restoring generation settings."""
        if self.working:
            return
        text = history_request_text(self._one_history())
        if text is None:
            return
        # Keep this operation undoable as one edit. No generation, config
        # writes, workflow changes, reference-image changes or LLM calls.
        if self.prompt.get("1.0", "end-1c") != text:
            self.prompt.edit_separator()
            self.prompt.replace("1.0", "end-1c", text)
            self.prompt.edit_separator()
        self.prompt.mark_set("insert", "end-1c")
        self.prompt.see("insert")
        self.prompt.focus_set()
        self.form_canvas.yview_moveto(0)
        self.status.set("プロンプトを復元しました")

    def _restore_selected_history(self) -> None:
        if getattr(self, "working", False):
            return
        entry = self._one_history()
        if entry is None:
            messagebox.showinfo("履歴", "復元する履歴を1件選択してください")
            return
        restored_mode = workflow_generation_mode(self.config, entry.workflow_id)
        if entry.workflow_id == LONG_VIDEO_ID and hasattr(self, "project_workspace"):
            self._restore_long_project(entry)
            return
        if entry.workflow_id == LONG_VIDEO_ID:
            p = dict(entry.parameters)
            seconds = p.pop("long_seconds", 0)
            self._preferred_long_project_id = p.pop("long_run_id", None)
            p.pop("long_prompt_plan", None)
            p.pop("long_text_only", None)
            cuts = p.pop("long_cut_frames", None)
            p["frames"] = p.pop("long_segment_frames", 124)
            entry = replace(entry, workflow_id=core.H3_I2V_ID, parameters=p)
            if hasattr(self, "h3_long_target"):
                try:
                    restored_cuts = validate_cut_frames(cuts) if cuts is not None else None
                except core.OrchestratorError as exc:
                    messagebox.showerror("履歴復元", str(exc))
                    return
                if restored_cuts is not None:
                    self._custom_cut_frames = restored_cuts
                    self.h3_long_target.set(CUSTOM_CUTS)
                    self._sync_cut_summary()
                else:
                    self.h3_long_target.set(next((label for label in CONTINUOUS_TARGETS
                                                  if LONG_TARGETS[label] == seconds), "30秒"))
        if entry.legacy or entry.workflow_id not in self.config["workflows"]:
            messagebox.showinfo(
                "履歴", "この画像には生成設定が保存されていないため復元できません"
            )
            return
        # A missing old I2VA source must not silently turn into a new T2VA job.
        if entry.workflow_id == core.H3_I2V_ID:
            if entry.parameters.get("text_only_h3") is True:
                if entry.reference_image is not None:
                    messagebox.showerror("履歴復元", "保存されたH3参照なしモードが不正です")
                    return
            elif entry.reference_image is None or not entry.reference_image.is_file():
                messagebox.showerror("履歴復元", "保存されたH3参照画像が見つかりません")
                return
        if entry.workflow_id in camera_spec.IDS and hasattr(self, "camera_spec"):
            try:
                self.camera_spec = camera_spec.normalize(entry.parameters.get(camera_spec.KEY))
            except core.OrchestratorError as exc:
                messagebox.showerror("履歴復元", str(exc))
                return
            self._sync_camera_button()
        self.prompt.delete("1.0", "end")
        self.prompt.insert("1.0", entry.request_text)
        self._source_change_lock = True
        try:
            if hasattr(self, "generation_mode"):
                self.generation_mode.set(restored_mode)
            self.workflow.set(entry.workflow_id)
            reference = entry.reference_image
            self.reference_image.set(
                str(reference) if reference and reference.is_file() else ""
            )
            if hasattr(self, "mask_image"):
                self.mask_image.set(
                    str(entry.mask_image) if entry.mask_image and entry.mask_image.is_file() else ""
                )
            if hasattr(self, "pose_image"):
                self.pose_image.set(
                    str(entry.pose_image) if entry.pose_image and entry.pose_image.is_file() else ""
                )
            if hasattr(self, "composition_image"):
                self.composition_image.set(
                    str(entry.composition_image)
                    if entry.composition_image and entry.composition_image.is_file() else ""
                )
                if entry.composition_image and hasattr(self, "vision_composition"):
                    self.vision_composition.set(True)
            if hasattr(self, "pose_mode"):
                self.pose_mode.set("photo" if entry.workflow_id == "wai_pose_detect" else "skeleton")
            self._last_reference_image = self.reference_image.get()
        finally:
            self._source_change_lock = False
        video_entry = entry.kind in core.VIDEO_KINDS
        if entry.workflow_id in core.SDXL_WORKFLOW_IDS and hasattr(self, "checkpoint_model"):
            self.checkpoint_model.set(entry.parameters.get("checkpoint_model", core.DEFAULT_SDXL_CHECKPOINT))
        if entry.workflow_id == ANIMA_ID and hasattr(self, "anima_model"):
            self.anima_model.set(entry.parameters.get("checkpoint_model", ANIMA_BASE))
        if entry.workflow_id in core.QWEN_IDS and hasattr(self, "qwen_steps"):
            if entry.workflow_id == core.QWEN_T2I_ID:
                if hasattr(self, "qwen_model"):
                    self.qwen_model.set(entry.parameters.get("checkpoint_model", ""))
                self.qwen_steps.set(str(entry.parameters.get("steps", 50)))
                self.qwen_cfg.set(str(entry.parameters.get("cfg", 4)))
        if entry.workflow_id == core.H3_I2V_ID and hasattr(self, "h3_size"):
            p = entry.parameters
            if hasattr(self, "h3_model"):
                self.h3_model.set(core.h3_model_label(p.get("h3_model", "int8")))
                self.h3_turbo.set(core.H3_TURBO_LABELS.get(p.get("h3_turbo", "off"), "OFF"))
                if hasattr(self, "h3_performance"):
                    self.h3_performance.set(core.H3_PERFORMANCE_LABELS.get(
                        p.get("h3_performance", "standard"), core.H3_PERFORMANCE_LABELS["standard"]))
                if hasattr(self, "h3_encoder_cpu"):
                    self.h3_encoder_cpu.set(p.get("h3_encoder_device", "default") == "cpu")
                if hasattr(self, "h3_encoder_model"):
                    self.h3_encoder_model.set(core.H3_ENCODER_LABELS.get(p.get("h3_encoder_model", "nvfp4"), "NVFP4 AWQ"))
                if p.get("h3_turbo", "off") == "off" and "steps" in p:
                    variable = (self.h3_hybrid_steps if core.h3_hybrid_filename(p.get("h3_model")) is not None
                                and hasattr(self, "h3_hybrid_steps") else self.h3_steps)
                    variable.set(str(p["steps"]))
            if "width" in p and "height" in p:
                self.h3_size.set(f"{p['width']} × {p['height']}")
            if "frames" in p:
                self.h3_duration.set(next((label for label, count in H3_DURATIONS.items() if count == p["frames"]), f"{p['frames'] / 24:.2f}秒 ({p['frames']}f)"))
        elif entry.workflow_id == core.HUNYUAN_I2V_ID and hasattr(self, "hunyuan_size"):
            p = entry.parameters
            if "width" in p and "height" in p:
                self.hunyuan_size.set(f"{p['width']} × {p['height']}")
            if "frames" in p:
                self.hunyuan_frames.set(str(p["frames"]))
            if "steps" in p:
                self.hunyuan_steps.set(str(p["steps"]))
        elif video_entry and hasattr(self, "video_size"):
            p = entry.parameters
            if "width" in p and "height" in p:
                self.video_size.set(f"{p['width']} × {p['height']}")
            if "frames" in p:
                self.video_frames.set(str(p["frames"]))
            if "fps" in p:
                self.video_fps.set(str(p["fps"]))
        for key, variable in (
            ("width", self.width), ("height", self.height),
            ("steps", self.steps), ("cfg", self.cfg),
            ("denoise", self.denoise), ("seed", self.seed),
        ):
            if video_entry and key in ("width", "height"):
                continue
            if key in ("steps", "cfg") and (entry.workflow_id in core.QWEN_IDS or
                    core.sdxl_checkpoint_kind(entry.parameters.get("checkpoint_model", "")) == "turbo"):
                continue
            if key == "steps" and (
                (entry.workflow_id == core.H3_I2V_ID and hasattr(self, "h3_steps"))
                or (entry.workflow_id == core.HUNYUAN_I2V_ID and hasattr(self, "hunyuan_steps"))
            ):
                continue
            if key in entry.parameters:
                variable.set(str(entry.parameters[key]))
            elif key == "seed":
                variable.set("")
        if hasattr(self, "character_references"):
            self.character_references = entry.character_references
            self.character_traits = entry.character_traits or ""
            self.character_analysis = entry.character_analysis
            self.character_status.set(character_status_label(self.character_references, self.character_traits))
        if entry.kind == "t2i" and entry.prompt_profile in T2I_PROFILE_LABELS:
            self.t2i_profile.set(T2I_PROFILE_LABELS[entry.prompt_profile])
        elif (
            entry.kind in ("i2i", "inpaint")
            and entry.prompt_profile in I2I_PROFILE_LABELS
        ):
            self.i2i_profile.set(I2I_PROFILE_LABELS[entry.prompt_profile])
        elif entry.workflow_id == core.H3_I2V_ID:
            # Old H3 jobs had no preset. Restore the original general behavior,
            # without backfilling invented metadata into the saved history.
            self.h3_profile.set(H3_PROFILE_LABELS.get(
                entry.prompt_profile, H3_PROFILE_LABELS[H3_PROFILE_GENERAL]
            ))
        if hasattr(self, "parameter_widgets"):
            self._custom_size_editing = self.resolution_preset.get() == CUSTOM_RESOLUTION
        self._update_generation_controls()
        if hasattr(self, "h3_steps"):
            self._sync_h3_steps()
        if hasattr(self, "_image_choices"):
            self._refresh_image_picker()
        self.status.set("設定を復元しました")
        self._log(f"履歴の設定を復元: {entry.workflow_id} / Seed={entry.parameters.get('seed', '不明')}")
        self.prompt.focus_set()

    def _compare_selected_history(self) -> None:
        entries = self._selected_history()
        if len(entries) == 1 and getattr(entries[0], "comparison_group_id", None):
            self._open_model_comparison(group_id=entries[0].comparison_group_id)
            return
        if any(e.first_image is not None and is_video_output(e.first_image) for e in entries):
            messagebox.showinfo("画像比較", "動画は履歴の「開く」で再生してください")
            return
        if len(entries) == 2:
            left, right = (e.first_image for e in entries)
            titles = ("生成結果 A", "生成結果 B")
        elif len(entries) == 1 and entries[0].reference_image is not None:
            left, right = entries[0].reference_image, entries[0].first_image
            titles = ("元画像", "生成結果")
        else:
            messagebox.showinfo(
                "画像比較",
                "I2Iは履歴を1件選択、T2IはCtrl+クリックで2件選択して比較してください",
            )
            return
        if left is None or right is None or not left.is_file() or not right.is_file():
            messagebox.showerror("画像比較", "比較する画像ファイルが見つかりません")
            return
        try:
            ComparisonWindow(self.root, left, right, *titles)
        except (ValueError, OSError, tk.TclError) as exc:
            messagebox.showerror("画像比較", str(exc))

    def _sync_camera_button(self):
        if hasattr(self, "camera_button"):
            self.camera_button.configure(text="画角設定済…" if getattr(self, "camera_spec", {}) else "画角…")
            self.camera_button.configure(state="normal" if not self.working and self._active_workflow() in camera_spec.IDS else "disabled")

    def _edit_camera(self):
        if self.working or self._active_workflow() not in camera_spec.IDS:
            return
        result = choose_camera(self.root, self.camera_spec, self.width.get(), self.height.get())
        if result is not None:
            self.camera_spec = result
            self._sync_camera_button()
            self.status.set("カメラ設定: " + camera_spec.summary(result))

    def _open_model_comparison(self, group_id=None):
        if self.working or self.character_analysis_running or self.single_draft is not None:
            return
        existing = self.comparison_window
        if existing is None or not existing.winfo_exists():
            choices = tuple(getattr(self, "_image_choices", {}).values())
            self.comparison_window = ModelComparisonWindow(
                self.root, self.comparison_store, choices,
                width=self.width.get(), height=self.height.get(), seed=self.seed.get(),
                steps=self.steps.get(), cfg=self.cfg.get(), camera=getattr(self, "camera_spec", {}),
                on_start=self._start_model_comparison, on_cancel=self._request_cancel,
                on_adjust=lambda h, p: self._open_adjust(h, selected=p),
                on_open=self._open_path, on_close=self._close_model_comparison,
            )
        else:
            existing.lift()
        if group_id:
            self.comparison_window.open_group(group_id)

    def _close_model_comparison(self):
        if self.comparison_window is not None:
            self.comparison_window.destroy()
            self.comparison_window = None

    def _start_model_comparison(self, choices, **options):
        if self.working or self.character_analysis_running or self.single_draft is not None:
            return
        if self.generation_mode.get() != "image":
            raise core.OrchestratorError("画像生成タブで比較を開始してください")
        if any(v.get().strip() for v in (self.reference_image, self.mask_image, self.pose_image)):
            raise core.OrchestratorError("モデル比較はT2I専用です。実際の参照画像・マスク・ポーズを解除してください")
        prompt = self.prompt.get("1.0", "end").strip()
        if not prompt:
            raise core.OrchestratorError("メイン画面に生成内容を入力してください")
        if self.model.get().strip() in ("", "SELECT_IN_GUI"):
            raise core.OrchestratorError("LM Studioのモデルを選択してください")
        composition = Path(self.composition_image.get()).expanduser() if self.composition_image.get().strip() else None
        if composition is not None and not self.vision_composition.get():
            raise core.OrchestratorError("構図参考を使用するには画像をLLMで構図解析をONにしてください")
        if not self._save_settings():
            return
        cfg = copy.deepcopy(self.config)
        available = {(c.workflow_id, c.filename) for c in self._image_choices.values()}
        if any((c.workflow_id, c.filename) not in available for c in choices):
            raise core.OrchestratorError("モデル一覧が変わりました。比較対象を選び直してください")
        targets = prepare_targets(cfg["workflows"], choices, self._registered_models, **options)
        traits = self.character_traits or None
        refs = tuple(self.character_references) if traits else ()
        analysis = copy.deepcopy(self.character_analysis) if traits else None
        if traits:
            validate_character_selection(refs, analysis, traits)
        manifest = self.comparison_store.create(prompt, targets, options["policy"])
        controller = self._controller(cfg, self.prompt_cache if self.use_prompt_cache.get() else None)
        store, emit = self.comparison_store, self.messages.put
        self._comparison_active = manifest["id"]
        self._set_busy("比較生成を準備中")
        self.comparison_window.show_manifest(manifest, active=True)
        self._launch_generation(lambda: run_comparison(
            controller, store, manifest, composition_image=composition,
            character_references=refs, character_traits=traits, character_analysis=analysis,
            on_update=lambda value: emit(("model_comparison_progress", value)),
        ), done_event="model_comparison_done", cancel_as_progress=True,
            usage={"action": "image_compare", "mode": "image", "workflow": "model_comparison",
                   "group_id": manifest["id"]})

    def _on_model_comparison_progress(self, manifest):
        if manifest["id"] != self._comparison_active:
            return
        if self.comparison_window is not None:
            self.comparison_window.show_manifest(manifest, active=True)
        count = sum(t["status"] == "completed" for t in manifest["targets"])
        self.status.set(f"比較生成 {count}/{len(manifest['targets'])}件")

    def _on_model_comparison_done(self, manifest):
        if manifest["id"] != self._comparison_active:
            return
        if self.comparison_window is not None:
            self.comparison_window.show_manifest(manifest, active=False)
            self.comparison_window.refresh_groups()
        count = sum(t["status"] == "completed" for t in manifest["targets"])
        self.status.set(f"比較生成: {count}/{len(manifest['targets'])}件")
        self._log(f"比較グループ {manifest['id']}: {manifest['status']} / {count}件")
        self._refresh_history(scan_legacy=False)

    def _controller(self, cfg, cache=None):
        return GenerationController(
            cfg, CONFIG, OUTPUTS, self.history_store, self.job_journal,
            progress=lambda line: self.messages.put(("progress", line)),
            cancel_event=self.stop_event, prompt_cache=cache,
        )

    def _launch_generation(self, operation, *, done_event="done", long_video=False, cancel_as_progress=False,
                           usage=None):
        if usage is not None:
            original = operation
            metadata = dict(usage)
            metadata.setdefault("mode", self.generation_mode.get())
            metadata.setdefault("workflow", self._active_workflow() or "")
            store = self.llm_usage
            emit = self.messages.put
            operation = lambda: store.run(original, **metadata, notify=lambda line: emit(("llm_usage", line)))
        self.tasks.launch(operation, done_event=done_event, long_video=long_video,
                          cancel_as_progress=cancel_as_progress)

    def _record_completed_generation(
        self, result, images, request_text, source_image=None, mask_image=None,
        pose_image=None, composition_image=None, prompt_profile=None,
        character_references=(), character_traits=None, character_analysis=None,
    ):
        # Compatibility entry point; all history writes use the same service.
        return record_history(
            self.config, self.history_store, self.job_journal, result, images, request_text,
            source_image, mask_image, pose_image, composition_image, prompt_profile,
            character_references, character_traits, character_analysis,
            progress=lambda line: self.messages.put(("progress", line)),
        )

    def _set_busy(self, label: str) -> None:
        self.tasks.begin()
        self._sync_camera_button()
        comparison = getattr(self, "comparison_window", None)
        if comparison is not None and comparison.winfo_exists():
            comparison.set_busy(True, own_task=getattr(self, "_comparison_active", None) is not None)
        if hasattr(self, "timing_status"):
            self.timing_status.set("経過 00:00")
        if hasattr(self, "project_workspace"):
            self.project_workspace.set_enabled(False)
        self.result_panel.set_busy(True)
        self.history_panel.set_busy(True)
        if getattr(self, "adjust_window", None) is not None:
            self.adjust_window.set_busy(True, own_task=self._adjust_operation is not None)
        self.run_button.configure(state="disabled")
        self.preview_button.configure(state="disabled")
        self.cancel_button.configure(state="normal")
        if hasattr(self, "free_memory_button"):
            self.free_memory_button.configure(state="disabled")
        if hasattr(self, "recover_jobs_button"):
            self.recover_jobs_button.configure(state="disabled")
        self.progress_bar.start(12)
        self.status.set(label)

    def _regenerate_selected_history(self, *, new_seed: bool) -> None:
        if self.working or self.character_analysis_running:
            return
        entry = self._one_history()
        if (
            entry is None or entry.legacy
            or entry.workflow_id not in self.config["workflows"]
        ):
            messagebox.showwarning("再生成", "再生成可能な履歴を1件選択してください")
            return
        for name, source in (
            ("元画像", entry.reference_image),
            ("部分修正マスク", entry.mask_image),
            ("ポーズ参照", entry.pose_image),
        ):
            if source is not None and not source.is_file():
                messagebox.showerror("再生成", f"履歴に保存した{name}が見つかりません")
                return
        if not self._save_settings():
            return
        cfg = copy.deepcopy(self.config)
        self.review.begin(request_text=entry.request_text, profile=entry.prompt_profile,
                          character_traits=entry.character_traits, character_analysis=entry.character_analysis,
                          character_references=entry.character_references)
        self._set_busy("保存した設定を使って再生成中（LLMは呼び出しません）")
        self._log(
            f"再生成: {entry.workflow_id} / "
            + ("別Seed" if new_seed else "同じSeed")
        )

        controller = self._controller(cfg)
        self._launch_generation(lambda: controller.replay(entry, new_seed=new_seed),
                                usage={"action": "replay", "workflow": entry.workflow_id,
                                       "mode": workflow_generation_mode(cfg, entry.workflow_id),
                                       "frames": entry.parameters.get("frames")})

    def _collect_config(self) -> dict:
        config = copy.deepcopy(self.config)
        config["llm"]["provider"] = "lmstudio"
        config["llm"]["base_url"] = self.llm_url.get().strip()
        config["llm"]["model"] = self.model.get().strip() or "SELECT_IN_GUI"
        config["llm"]["unload_after_inference"] = self.unload_llm.get()
        if hasattr(self, "image_reasoning"):
            config["llm"]["image_reasoning"] = IMAGE_REASONING_BY_LABEL[self.image_reasoning.get()]
        config["llm"]["send_reference_to_llm"] = self.vision_composition.get()
        config["llm"]["t2i_prompt_profile"] = T2I_LABEL_TO_PROFILE[
            self.t2i_profile.get()
        ]
        config["llm"]["i2i_prompt_profile"] = I2I_LABEL_TO_PROFILE[
            self.i2i_profile.get()
        ]
        config["llm"]["h3_prompt_profile"] = H3_LABEL_TO_PROFILE[self.h3_profile.get()]
        config["comfyui"]["base_url"] = self.comfy_url.get().strip()
        config["comfyui"]["free_before_llm"] = self.free_comfy.get()
        opts = self._overrides()
        config["ui"] = {
            **config.get("ui", {}),
            **opts,
            "workflow": self.workflow.get(),
            "dark_mode": self.dark_mode.get(),
            "font_size": self.editor_font_size.get(),
        }
        if hasattr(self, "generation_mode"):
            config["ui"]["generation_mode"] = self.generation_mode.get()
            config["ui"]["mode_workflows"] = dict(self._mode_workflows)
            if hasattr(self, "_mode_settings"):
                config["ui"]["mode_settings"] = self._mode_settings.snapshot(self)
            config["ui"]["h3_long_target"] = self.h3_long_target.get()
            if hasattr(self, "h3_connection"):
                config["ui"]["h3_overlap_frames"] = preferred_connection_frames(
                    connection_frames(self.h3_connection.get()))
            if getattr(self, "_custom_cut_frames", None) is not None:
                config["ui"]["h3_cut_frames"] = list(self._custom_cut_frames)
        if hasattr(self, "camera_spec"):
            config["ui"][camera_spec.KEY] = camera_spec.normalize(self.camera_spec)
        if hasattr(self, "use_prompt_cache"):
            config["ui"]["use_prompt_cache"] = self.use_prompt_cache.get()
        config["ui"]["seed"] = self.seed.get().strip()
        config["ui"]["denoise"] = self.denoise.get().strip()
        config["ui"]["pose_mode"] = self.pose_mode.get()
        config["ui"]["control_strength"] = self.control_strength.get().strip()
        if hasattr(self, "h3_model"):
            config["ui"].update(self._h3_choices())
            config["ui"]["h3_steps"] = self.h3_steps.get()
            if hasattr(self, "h3_hybrid_steps"):
                config["ui"]["h3_hybrid_steps"] = self.h3_hybrid_steps.get()
            if hasattr(self, "h3_performance"):
                config["ui"]["h3_hybrid_performance"] = next(
                    key for key, label in core.H3_PERFORMANCE_LABELS.items() if label == self.h3_performance.get())
        for name in ("video_size", "video_frames", "video_fps", "h3_size", "h3_duration",
                     "hunyuan_size", "hunyuan_frames", "hunyuan_steps",
                     "checkpoint_model", "anima_model", "qwen_model", "qwen_steps", "qwen_cfg"):
            if hasattr(self, name):
                config["ui"][name] = getattr(self, name).get()
            elif name in self.config.get("ui", {}):
                config["ui"][name] = self.config["ui"][name]
        return config

    def _overrides(self) -> dict:
        workflow_id = self._active_workflow() if hasattr(self, "parameter_widgets") else None
        return common_overrides(
            getattr(self, "config", {}), workflow_id, width=self.width.get(), height=self.height.get(),
            steps=self.steps.get(), cfg=self.cfg.get(), seed=self.seed.get(),
            has_h3_steps=hasattr(self, "h3_steps"), has_hunyuan_steps=hasattr(self, "hunyuan_steps"),
        )

    def _video_overrides(self) -> dict:
        return wan_overrides(size=self.video_size.get(), frames=self.video_frames.get(),
                             fps=self.video_fps.get(), steps=self.steps.get(),
                             cfg=self.cfg.get(), seed=self.seed.get())

    def _qwen_overrides(self, workflow_id: str) -> dict:
        fast = workflow_id == core.QWEN_LIGHTNING_ID
        return qwen_overrides(workflow_id, width=self.width.get(), height=self.height.get(),
                              steps=4 if fast else self.qwen_steps.get(),
                              cfg=1 if fast else self.qwen_cfg.get(), seed=self.seed.get())

    def _hunyuan_overrides(self) -> dict:
        return hunyuan_overrides(size=self.hunyuan_size.get(), frames=self.hunyuan_frames.get(),
                                 steps=self.hunyuan_steps.get(), seed=self.seed.get())

    def _h3_overrides(self) -> dict:
        choices = self._h3_choices() if hasattr(self, "h3_model") else {}
        hybrid = core.h3_hybrid_filename(choices.get("h3_model")) is not None
        normal = self.h3_hybrid_steps if hybrid else getattr(self, "h3_steps", self.steps)
        return h3_overrides(size=self.h3_size.get(), duration=self.h3_duration.get(),
                            steps=normal.get(), seed=self.seed.get(), choices=choices)

    def _save_settings(self) -> bool:
        if self.working:
            return False
        try:
            config = self._collect_config()
            write_local_config(CONFIG, config)
            self.config = config
            self._log("設定保存: config.json")
            self.status.set("設定を保存しました")
            return True
        except (ValueError, OSError, core.OrchestratorError) as exc:
            messagebox.showerror("設定エラー", str(exc))
            return False

    def _browse_image(self) -> None:
        picked = filedialog.askopenfilename(
            filetypes=[("Images", "*.png *.jpg *.jpeg *.webp"), ("All files", "*.*")]
        )
        if picked:
            self.reference_image.set(picked)

    def _show_selected_history_prompt(self) -> None:
        """Inspect this selected history entry, never the last generated image."""
        selected = self._one_history()
        details = history_prompt_details(selected)
        if details is None:
            messagebox.showinfo(
                "履歴の生成タグ",
                "履歴を1件選択してください。旧画像など生成プロンプトが"
                "保存されていない項目は表示できません。",
            )
            return
        self._open_prompt_details(details, from_history=True)

    def _show_prompt_preview(self) -> None:
        """Inspect the last completed result/dry-run with its own metadata."""
        details = self.review.details()
        if details is None:
            messagebox.showinfo("生成タグ", "「解釈のみテスト」または画像生成を実行してください。")
            return
        self._open_prompt_details(details, from_history=False)

    def _open_prompt_details(self, details: dict, *, from_history: bool) -> None:
        show_prompt_details(self.root, details, from_history=from_history,
                            copy_text=self._copy_to_clipboard, show_character=self._show_saved_character_features)

    def _show_saved_character_features(self, details: dict) -> None:
        show_saved_character_features(self.root, details, copy_text=self._copy_to_clipboard)

    def _copy_to_clipboard(self, value: str) -> None:
        self.root.clipboard_clear()
        self.root.clipboard_append(value)
        self.root.update_idletasks()

    def _show_composition_report(self) -> None:
        show_composition_report(self.root, self.latest_composition_report)

    def _drop_character_files(self, files: tuple[str, ...]) -> None:
        if not files:
            return
        if self.working or self.character_analysis_running:
            messagebox.showwarning(
                "キャラ参照", "現在の処理が終了してから画像を追加してください"
            )
            return
        self._open_character_references()
        if self.character_dialog is not None and self.character_dialog.is_open():
            self.character_dialog._add_files(files)

    def _open_character_references(self) -> None:
        if self.character_dialog is not None and self.character_dialog.is_open():
            self.character_dialog.window.lift()
            self.character_dialog.window.focus_force()
            return
        self.character_dialog = CharacterReferenceWindow(
            self.root,
            images=self.character_references,
            analysis=self.character_analysis,
            approved=self.character_traits,
            on_analyze=self._request_character_analysis,
            on_confirm=self._approve_character_traits,
            on_clear=self._clear_character_traits,
            on_revise=self._request_character_revision,
            on_history=self._choose_character_history,
            feature_store=self.character_feature_store,
        )

    def _choose_character_history(self, dialog):
        if self.working or self.character_analysis_running:
            return
        try:
            entries = self.history_store.list_character_entries()
            traits = choose_history_traits(dialog.window, entries)
            if traits is not None:
                dialog.load_history_traits(traits)
        except (OSError, ValueError, RuntimeError, sqlite3.Error) as exc:
            messagebox.showerror("キャラ特徴の復元", str(exc), parent=dialog.window)

    def _request_character_analysis(
        self, paths: tuple[Path, ...], dialog: CharacterReferenceWindow,
    ) -> None:
        if self.working or self.character_analysis_running:
            dialog.finish(error="画像生成や別の特徴抽出が実行中です")
            return
        model = self.model.get().strip()
        if not model or model == "SELECT_IN_GUI":
            dialog.finish(error="先にLM Studioの画像対応モデルを選択してください")
            return
        self.character_analysis_running = True
        settings = copy.deepcopy(self.config["llm"])
        settings.update({
            "base_url": self.llm_url.get().strip(),
            "model": model,
            "unload_after_inference": self.unload_llm.get(),
        })

        comfy_settings = copy.deepcopy(self.config["comfyui"])
        comfy_settings.update(base_url=self.comfy_url.get().strip(),
                              free_before_llm=self.free_comfy.get())

        def task():
            try:
                def analyze():
                    release_comfy_before_llm(comfy_settings,
                                             progress=lambda line: self.messages.put(("progress", line)))
                    return LMStudio(settings).analyze_character_references(
                        paths, progress=lambda line: self.messages.put(("progress", line)),
                    )
                analysis = self.llm_usage.run(analyze, action="character_analysis", mode="character",
                    notify=lambda line: self.messages.put(("llm_usage", line)))
                self.messages.put(("character_analysis_done", (dialog, analysis)))
            except Exception as exc:
                self.messages.put(("character_analysis_error", (dialog, str(exc))))

        threading.Thread(target=task, daemon=True).start()

    def _request_character_revision(
        self, current: str, instruction: str, dialog: CharacterReferenceWindow,
    ) -> None:
        if self.working or self.character_analysis_running:
            dialog.finish_revision(error="他の画像生成・特徴抽出が実行中です")
            return
        model = self.model.get().strip()
        if not model or model == "SELECT_IN_GUI":
            dialog.finish_revision(error="先にLM Studioのモデルを選択してください")
            return
        self.character_analysis_running = True
        settings = copy.deepcopy(self.config["llm"])
        settings.update({
            "base_url": self.llm_url.get().strip(),
            "model": model,
            "unload_after_inference": self.unload_llm.get(),
        })

        comfy_settings = copy.deepcopy(self.config["comfyui"])
        comfy_settings.update(base_url=self.comfy_url.get().strip(),
                              free_before_llm=self.free_comfy.get())

        def task():
            try:
                def revise():
                    release_comfy_before_llm(comfy_settings,
                                             progress=lambda line: self.messages.put(("progress", line)))
                    return LMStudio(settings).revise_character_description(
                        current, instruction, progress=lambda line: self.messages.put(("progress", line)),
                    )
                revised = self.llm_usage.run(revise, action="character_revision", mode="character",
                    notify=lambda line: self.messages.put(("llm_usage", line)))
                self.messages.put(("character_revision_done", (dialog, revised)))
            except Exception as exc:
                self.messages.put(("character_revision_error", (dialog, str(exc))))

        threading.Thread(target=task, daemon=True).start()

    def _approve_character_traits(
        self, paths: tuple[Path, ...], analysis: dict | None, traits: str,
    ) -> None:
        if self.working or self.character_analysis_running:
            raise core.OrchestratorError("現在の処理が終了してからキャラ特徴を確定してください")
        paths, traits = validate_character_selection(paths, analysis, traits)
        # Persist first. If it fails, keep the previous accepted sheet intact.
        save_character_sheet(ROOT, paths, analysis, traits)
        self.character_references = paths
        self.character_analysis = copy.deepcopy(analysis)
        self.character_traits = traits
        self.character_status.set(character_status_label(paths, traits))
        self.status.set("キャラ特徴を確定しました。次のT2I/I2Iから反映します")
        self._log(f"キャラ特徴確定: {'文章のみ' if analysis is None else str(len(paths)) + '枚'}（生成プロンプトへ反映）")

    def _clear_character_traits(self) -> None:
        clear_character_sheet(ROOT)
        self.character_references = ()
        self.character_analysis = None
        self.character_traits = ""
        self.character_status.set("キャラ参照")
        self.status.set("キャラ特徴の使用を解除しました")

    def _browse_composition(self) -> None:
        picked = filedialog.askopenfilename(
            filetypes=[("Images", "*.png *.jpg *.jpeg *.webp"), ("All files", "*.*")]
        )
        if picked:
            self.composition_image.set(picked)
            self.vision_composition.set(True)
            self._update_generation_controls()
            self.status.set("画像をLLMに渡して構図を解析します。画像対応モデルを選択してください")

    def _browse_pose(self) -> None:
        picked = filedialog.askopenfilename(
            filetypes=[("Images", "*.png *.jpg *.jpeg *.webp"), ("All files", "*.*")]
        )
        if picked:
            self.pose_image.set(picked)

    def _edit_mask(self) -> None:
        source = self.reference_image.get().strip()
        if not source:
            messagebox.showwarning("部分修正", "先に修正する画像を指定してください")
            return
        result = edit_mask(self.root, Path(source), ROOT / "data" / "masks")
        if result is not None:
            self.mask_image.set(str(result))
            self._log(f"部分修正マスクを保存: {result.name}")
            self.status.set("修正範囲を指定しました。自然文を入力して生成してください")

    def _open_adjust_current(self):
        history_id = self._result_material_context.get("history_id")
        path = self.result_panel.selected_path()
        if not history_id or not image_file(path):
            messagebox.showinfo("画像調整", "生成設定の保存された画像を選択してください")
            return
        self._open_adjust(history_id, selected=path)

    def _open_adjust_history(self):
        entry = self._one_history()
        if can_adjust(entry, self.config["workflows"]):
            self._open_adjust(entry.id)

    def _open_adjust(self, history_id, *, selected=None):
        if self.adjust_window is not None:
            self.adjust_window.lift()
            self.adjust_window.focus_set()
            self.status.set("開いている画像調整を閉じてから別の画像を選択してください")
            return
        if self.working or self.character_analysis_running or self.single_draft is not None:
            return
        # Capture connection settings only. The current main-form generation
        # settings must not override the history's exact parameters.
        cfg = copy.deepcopy(self.config)
        cfg["llm"].update(base_url=self.llm_url.get().strip(), model=self.model.get().strip() or "SELECT_IN_GUI",
                          unload_after_inference=self.unload_llm.get(), send_reference_to_llm=False)
        if hasattr(self, "image_reasoning"):
            cfg["llm"]["image_reasoning"] = IMAGE_REASONING_BY_LABEL[self.image_reasoning.get()]
        cfg["comfyui"].update(base_url=self.comfy_url.get().strip(), free_before_llm=self.free_comfy.get())
        for name in ("llm", "comfyui"):
            try:
                parsed = urllib.parse.urlsplit(cfg[name]["base_url"])
                if parsed.scheme not in ("http", "https") or not parsed.netloc:
                    raise ValueError()
            except ValueError:
                messagebox.showerror("画像調整", f"{name}の接続先URLが不正です")
                return
        controller = self._controller(cfg)
        store = self.history_store
        def prepare():
            entry = store.get(history_id)
            return ImageAdjustDraft.from_history(controller, entry, selected)
        self._adjust_operation = "open"
        self._set_busy("画像調整を準備中")
        self._launch_generation(prepare, done_event="image_adjust_ready", cancel_as_progress=True)

    def _on_adjust_ready(self, draft):
        if self.stop_event.is_set():
            draft.close()
            return
        installed = core.installed_model_choices(self.generation_inventory, getattr(self, "_registered_models", ()))
        models = tuple(dict.fromkeys((*installed["sdxl"], *installed["anima"], *installed["qwen"],
                                      self.checkpoint_model.get(), self.anima_model.get(), self.qwen_model.get())))
        self.adjust_draft = draft
        try:
            self.adjust_window = ImageAdjustWindow(
                self.root, draft, self.project_workspace.translation_cache, models,
                on_action=self._adjust_action, on_close=self._close_adjust,
                on_cancel=self._request_cancel, status=self.status,
                registrations=getattr(self, "_registered_models", ()),
                reasoning_variable=getattr(self, "image_reasoning", None),
            )
            self.adjust_window.set_busy(True, own_task=True)
            self.status.set("画像調整")
        except Exception:
            draft.close()
            self.adjust_draft = None
            raise

    def _adjust_action(self, operation, **kwargs):
        if self.working or self.character_analysis_running or self.single_draft is not None:
            return
        draft = self.adjust_draft
        if draft is None or operation not in ("generate", "translate", "apply", "regenerate", "camera"):
            return
        if operation in ("regenerate", "camera") and hasattr(self, "image_reasoning"):
            draft.controller.config["llm"]["image_reasoning"] = IMAGE_REASONING_BY_LABEL[self.image_reasoning.get()]
        self._adjust_operation = operation
        self._set_busy("画像調整: 生成中" if operation == "generate" else "画像調整: プロンプト編集中")
        usage = {"action": "adjust_" + operation, "mode": "image",
                 "workflow": draft.workflow_id, "group_id": draft.group_id}
        if operation == "generate":
            self._launch_generation(lambda: draft.generate_variant(**kwargs),
                                    done_event="image_adjust_generated", usage=usage)
        else:
            cache = self.project_workspace.translation_cache
            def edit():
                if operation == "translate":
                    draft.translate(cache)
                elif operation == "camera":
                    draft.revise_camera(**kwargs)
                else:
                    draft.revise(operation, cache, **kwargs)
                return operation
            self._launch_generation(edit, done_event="image_adjust_changed",
                                    cancel_as_progress=True, usage=usage)

    def _on_adjust_generated(self, completed):
        if self.adjust_draft is None or self.adjust_window is None:
            return
        path, history_id = self.adjust_draft.accept_completed(completed)
        self.adjust_window.show_completed()
        self.status.set("画像調整完了" if history_id else "画像保存済み / 履歴未登録")
        self._log("画像調整完了: " + path.name)
        self._refresh_history(select_id=history_id, scan_legacy=False)

    def _on_adjust_changed(self, operation):
        if self.adjust_window is not None:
            self.adjust_window.show_prompt_change(operation)
            self.status.set("プロンプトを更新しました")

    def _close_adjust(self):
        if self.working and self._adjust_operation is not None:
            return
        window, self.adjust_window = self.adjust_window, None
        draft, self.adjust_draft = self.adjust_draft, None
        if window is not None:
            window.destroy()
        if draft is not None:
            draft.close()

    def _current_output_material(self):
        context = self._result_material_context
        self._choose_material(
            available_materials(self.result_panel.image_paths), context=context,
            preferred=self.result_panel.selected_path(), player=self.result_panel.result_video,
        )

    def _history_output_material(self):
        entry = self._one_history()
        if entry is None:
            return
        context = {"workflow": entry.workflow_id, "parameters": entry.parameters,
                   "profile": entry.prompt_profile, "request": history_request_text(entry),
                   "history_id": entry.id}
        self._choose_material(available_materials(entry.images, entry.reference_image),
                              context=context, preferred=entry.first_image,
                              player=self.history_panel.history_video)

    def _choose_material(self, materials, *, context, preferred=None, player=None):
        if self.working or self.character_analysis_running:
            return
        destinations = tuple(mode for mode, (_, workflow) in DESTINATIONS.items()
                             if workflow in self.config["workflows"])
        if not materials or not destinations:
            messagebox.showwarning("素材", "使用可能な素材・ワークフローがありません")
            return
        transfer = MaterialDialog(
            self.root, materials, destinations, workflow=context.get("workflow", ""),
            parameters=context.get("parameters"), profile=context.get("profile"),
            request=context.get("request"), preferred=preferred,
            mode=self.generation_mode.get(),
        ).result
        if transfer is None:
            return
        if transfer.mode == "continuous" and not self.project_workspace.confirm_replace():
            return
        source = transfer.material.path
        if is_video_output(source):
            ratio = 0.0
            if player is not None and player.source == source and player.session is not None:
                ratio = float(player.position.get())
                player.stop()
            picker = FramePicker(self.root, source, initial_ratio=ratio)
            picker.wait_visibility()
            picker.grab_set()
            self.root.wait_window(picker)
            if picker.result is None:
                return
            frame, stamp = picker.result
            self._pending_material_transfer = transfer
            self._set_busy("フレームを保存中")
            self._launch_generation(lambda: extract_material(
                self.history_store, source, frame, stamp=stamp,
                source_history_id=context.get("history_id"), cancel_event=self.stop_event,
            ), done_event="material_frame_ready", cancel_as_progress=True)
        else:
            self._apply_material_transfer(transfer, source)

    def _apply_material_transfer(self, transfer, source):
        if source is None or not source.is_file() or source.suffix.lower() not in IMAGE_EXTENSIONS:
            messagebox.showerror("素材", "静止画像が見つかりません")
            return
        mode = transfer.mode
        label, workflow = DESTINATIONS[mode]
        if workflow not in self.config["workflows"]:
            messagebox.showerror("素材", "使用先ワークフローが未登録です")
            return
        if mode == "continuous":
            # The user confirmed replacement before the optional extraction.
            # Invalidate older project list replies; detach, not delete, the plan.
            self._project_refresh_serial += 1
            self.project_workspace.clear_draft()
        self._source_change_lock = True
        try:
            for variable in (self.mask_image, self.pose_image, self.composition_image):
                variable.set("")
            self.reference_image.set(str(source))
            self._last_reference_image = str(source)
            self.generation_mode.set(mode)
            self.workflow.set(workflow)
            self._sync_workflow_choice()
            for name, value in transfer.settings.items():
                getattr(self, name).set(value)
            if transfer.request is not None:
                self.prompt.edit_separator()
                self.prompt.replace("1.0", "end-1c", transfer.request)
                self.prompt.edit_separator()
        finally:
            self._source_change_lock = False
        self._generation_ui_key = None
        self._update_generation_controls()
        self.tabs.select(self.project_workspace if mode == "continuous" else self.result_panel)
        self.prompt.focus_set()
        self.status.set(f"{label}の参照画像に設定しました")

    def _on_material_frame_ready(self, entry):
        self._refresh_history(select_id=entry.id, scan_legacy=False)
        transfer = self._pending_material_transfer
        self._pending_material_transfer = None
        if transfer is not None and not self.stop_event.is_set():
            # Execute the UI transfer only after the foreground worker goes idle.
            self._pending_material_transfer = (transfer, entry.first_image)

    def _open_history_output(self) -> None:
        entry = self._one_history()
        if entry and entry.first_image and entry.first_image.is_file():
            self._open_path(entry.first_image)
        else:
            messagebox.showinfo("履歴", "保存済みファイルを1件選択してください")

    def _open_model_manager(self):
        if self.working or self.character_analysis_running:
            messagebox.showwarning("生成モデル管理", "現在の処理が終了してからモデルを登録してください")
            return
        if self._registry_error:
            messagebox.showerror("生成モデル管理", "登録ファイルを読み込めません。上書きしません。\n" + self._registry_error)
            return
        if self.model_manager is not None and self.model_manager.winfo_exists():
            self.model_manager.lift()
            return
        self.model_manager = ModelManagerWindow(self.root, self._registered_models, self.generation_inventory,
                                                on_save=self._save_model_registry,
                                                on_refresh=self._refresh_generation_models)
        if self.generation_inventory is None:
            self._refresh_generation_models()

    def _save_model_registry(self, values):
        if self.working or self.character_analysis_running or self._registry_error:
            messagebox.showwarning("生成モデル管理", "現在は登録内容を変更できません")
            return False
        try:
            self._registered_models = save_registrations(self._registry_path, values)
        except (OSError, core.OrchestratorError) as exc:
            messagebox.showerror("生成モデル管理", str(exc))
            return False
        self._apply_generation_model_choices()
        self._log(f"生成モデル登録: {len(self._registered_models)}件")
        return True

    def _apply_generation_model_choices(self) -> None:
        self._sync_h3_model_picker()
        if hasattr(self, "_mode_boxes") and hasattr(self, "anima_model"):
            self._refresh_image_picker()
        if self.generation_inventory is None:
            return
        choices = core.installed_model_choices(self.generation_inventory, getattr(self, "_registered_models", ()))
        # Preserve selected values even when a model was removed.
        checkpoint = [name for name in choices["sdxl"]
                      if self._active_workflow() == "wai_t2i_basic" or core.sdxl_checkpoint_kind(name) != "turbo"]
        current = self.checkpoint_model.get()
        if current not in checkpoint:
            checkpoint.append(current)
        self.checkpoint_box.configure(values=checkpoint)

    def _refresh_generation_models(self) -> None:
        settings = copy.deepcopy(self.config["comfyui"])
        settings["base_url"] = self.comfy_url.get().strip()
        def task():
            try:
                inventory = core.ComfyUI(settings).list_generation_models()
                self.messages.put(("generation_models", (settings["base_url"], inventory)))
            except Exception as exc:
                self.messages.put(("generation_models_error", str(exc)))
        threading.Thread(target=task, daemon=True).start()

    def _refresh_models(self) -> None:
        if hasattr(self, "checkpoint_box"):
            self._refresh_generation_models()
        settings = copy.deepcopy(self.config["llm"])
        settings["base_url"] = self.llm_url.get().strip()
        def task():
            try:
                models = list_models(settings)
                self.messages.put(("models", models))
            except Exception as exc:
                self.messages.put(("error", f"モデル一覧を取得できません: {exc}"))
        threading.Thread(target=task, daemon=True).start()
        self._log("LM Studioのモデル一覧を取得中...")

    def _tick_timing(self, *, finished=False):
        if not hasattr(self, "timing_status"):
            return
        text = self.tasks.timing_text(finished=finished)
        if text is not None and self.timing_status.get() != text:
            self.timing_status.set(text)

    def _show_operations(self):
        if self._operations_window is None or not self._operations_window.is_open():
            self._operations_window = OperationsWindow(
                self.root, ROOT, on_refresh=self._refresh_operations, on_clear_cache=self._clear_operations_cache,
                on_export_usage=self._export_llm_usage,
            )
        self._operations_window.window.lift()
        self._refresh_operations()

    def _clear_operations_cache(self):
        if self.working or self.character_analysis_running:
            messagebox.showwarning("キャッシュ", "処理終了後に削除してください")
            return
        if messagebox.askyesno("キャッシュ削除", "解釈キャッシュを削除しますか？生成済みデータには影響しません。"):
            self._clear_prompt_cache()
            self._refresh_operations()

    def _refresh_operations(self):
        if self._operations_pending:
            return
        self._operations_pending = True

        def task():
            try:
                report = storage_report(ROOT)
                try:
                    cache = self.prompt_cache.stats()
                except CACHE_ERRORS:
                    cache = None
                try:
                    usage = self.llm_usage.report()
                except (sqlite3.Error, OSError, ValueError):
                    usage = None
                self.messages.put(("operations_report", (report, cache, memory_stats(), usage)))
            except Exception as exc:
                self.messages.put(("operations_error", str(exc)))

        threading.Thread(target=task, daemon=True).start()

    def _export_llm_usage(self):
        window = self._operations_window
        target = filedialog.asksaveasfilename(
            parent=window.window, title="LLM使用量をCSV出力",
            initialdir=str(self.history_store.data), initialfile="llm_usage.csv",
            defaultextension=".csv", filetypes=[("CSV", "*.csv")],
        )
        if not target:
            return

        def task():
            try:
                path = self.llm_usage.export_csv(target)
                self.messages.put(("llm_usage_exported", str(path)))
            except Exception as exc:
                self.messages.put(("llm_usage_export_error", str(exc)))
        threading.Thread(target=task, daemon=True).start()

    def _clear_prompt_cache(self) -> None:
        if self.working:
            self.status.set("生成終了後にキャッシュを削除してください")
            return
        try:
            count = self.prompt_cache.clear()
            self.status.set(f"解釈キャッシュを{count}件削除しました")
        except CACHE_ERRORS as exc:
            messagebox.showerror("キャッシュ削除", str(exc))

    def _release_comfy_memory(self) -> None:
        """Request memory release off the GUI thread, only with an empty queue."""
        if self.working or self.character_analysis_running:
            return
        settings = copy.deepcopy(self.config["comfyui"])
        settings["base_url"] = self.comfy_url.get().strip()
        self._set_busy("生成モデルの解放を要求中")
        self.cancel_button.configure(state="disabled")

        def task():
            core.ComfyUI(settings).free_if_idle()
            return "ComfyUI: メモリ解放要求を送信しました"

        self._launch_generation(task, done_event="progress")

    def _check_connections(self) -> None:
        llm = copy.deepcopy(self.config["llm"])
        llm["base_url"] = self.llm_url.get().strip()
        comfy = self.comfy_url.get().strip()
        def task():
            results = []
            for name, fn in (
                ("LM Studio", lambda: list_models(llm)),
                ("ComfyUI", lambda: core.http_json(comfy, "/queue", timeout=12)),
            ):
                try:
                    fn()
                    results.append(name + ": 接続OK")
                except Exception as exc:
                    results.append(name + ": 失敗 (" + str(exc) + ")")
            self.messages.put(("check", results))
        threading.Thread(target=task, daemon=True).start()
        self._log("接続を確認中...")

    def _sync_cut_summary(self, *_args):
        if self.h3_long_target.get() != CUSTOM_CUTS:
            self.h3_cut_summary.set("")
        elif self._custom_cut_frames is None:
            self.h3_cut_summary.set("未設定")
        else:
            self.h3_cut_summary.set(f"{len(self._custom_cut_frames)}カット / "
                                    f"{format_cut_seconds(sum(self._custom_cut_frames))}秒")

    def _set_custom_cuts(self, cuts):
        self._custom_cut_frames = validate_cut_frames(cuts)
        self.h3_long_target.set(CUSTOM_CUTS)
        self._sync_cut_summary()

    def _edit_cut_durations(self):
        if self.working or self.generation_mode.get() != "continuous":
            return None
        try:
            if self.h3_long_target.get() == CUSTOM_CUTS and self._custom_cut_frames is not None:
                initial = self._custom_cut_frames
            else:
                label = self.h3_duration.get()
                nominal = H3_DURATIONS.get(label)
                if nominal is None:
                    nominal = int(label.rsplit("(", 1)[1].removesuffix("f)"))
                initial = default_cut_frames(LONG_TARGETS.get(self.h3_long_target.get(), 30), nominal)
            cuts = edit_cut_durations(self.root, initial)
            if cuts is not None:
                if cuts != self._custom_cut_frames or self.h3_long_target.get() != CUSTOM_CUTS:
                    self._set_custom_cuts(cuts)
                self._save_settings()
                return list(cuts)
        except (IndexError, ValueError, core.OrchestratorError) as exc:
            messagebox.showerror("カット尺設定", str(exc))
        return None

    def _run_primary(self):
        if self.working:
            return
        if self.generation_mode.get() == "continuous" and self.project_workspace.draft is not None:
            self.project_workspace._accept("generate_join")
        else:
            # Without a plan, the first press creates one for review.
            self._start(False)

    def _run_secondary(self):
        self._start(self.generation_mode.get() != "continuous")

    def _project_actions_changed(self, available):
        for i, key in enumerate(self._long_menu_keys):
            self.long_actions_menu.entryconfigure(i, state="normal" if available[key] else "disabled")
        enabled = any(available[key] for key in self._long_menu_keys)
        self.long_actions_button.configure(state="normal" if enabled else "disabled")

    def _start(self, dry_run: bool) -> None:
        if self.working:
            return
        if self.character_analysis_running:
            messagebox.showwarning(
                "キャラ参照", "キャラ特徴抽出が終了してから画像を生成してください"
            )
            return
        if not self._save_settings():
            return
        prompt = self.prompt.get("1.0", "end").strip()
        source_text = self.reference_image.get().strip()
        image = Path(source_text).expanduser() if source_text else None
        composition = (
            Path(self.composition_image.get()).expanduser()
            if self.composition_image.get() else None
        )
        mask = Path(self.mask_image.get()).expanduser() if self.mask_image.get() else None
        pose = Path(self.pose_image.get()).expanduser() if self.pose_image.get() else None
        selected = self._active_workflow()
        if selected is None:
            messagebox.showerror("生成設定エラー", "画像・マスク・ポーズの指定に対応するワークフローがありません")
            return
        kind = self.config["workflows"][selected]["kind"]
        if selected in T2I_ONLY and any(value is not None for value in (image, mask, pose)):
            messagebox.showerror("生成設定エラー", "選択中のモデルはT2I専用です。参照画像・マスク・ポーズを解除してください。")
            return
        is_video = kind in core.VIDEO_KINDS
        mask, pose, composition = active_aux_inputs(kind, mask, pose, composition)
        continuous = self.generation_mode.get() == "continuous"
        text_only_h3 = selected == core.H3_I2V_ID and image is None
        text_only_long = continuous and text_only_h3
        if kind == "i2v" and not text_only_h3 and (image is None or image.suffix.lower() not in IMAGE_EXTENSIONS):
            messagebox.showerror("I2V", "参照画像を1枚指定してください")
            return
        if not prompt and not core.supports_empty_i2v_request(
            self.config, selected, image, mask, pose, composition,
        ):
            messagebox.showwarning("入力が必要です", "生成内容を入力してください。")
            return
        use_prompt_llm = core.needs_prompt_llm(
            self.config, prompt, self.character_traits, composition, workflow_id=selected,
        )
        if use_prompt_llm and self.model.get().strip() in ("", "SELECT_IN_GUI"):
            messagebox.showwarning("モデル未設定", "「モデル更新」からLM Studioのモデルを選択してください。")
            return
        try:
            overrides = (self._h3_overrides() if selected == core.H3_I2V_ID else
                         self._hunyuan_overrides() if selected == core.HUNYUAN_I2V_ID else
                         self._video_overrides() if selected == core.WAN_I2V_ID else
                         self._qwen_overrides(selected) if selected in core.QWEN_IDS else self._overrides())
            overrides = image_aware_overrides(
                self.config, selected, image is not None,
                overrides, self.denoise.get(), self.control_strength.get(),
            )
            if text_only_h3 and not continuous:
                overrides = core.h3_text_model_options(overrides)
            if selected == core.QWEN_T2I_ID and hasattr(self, "qwen_model") and self.qwen_model.get():
                overrides["checkpoint_model"] = self.qwen_model.get()
                core.split_checkpoint_option(overrides, {selected})
            if selected == ANIMA_ID:
                overrides["checkpoint_model"] = self.anima_model.get()
                core.split_checkpoint_option(overrides, {selected})
            if selected in core.SDXL_WORKFLOW_IDS and hasattr(self, "checkpoint_model"):
                overrides["checkpoint_model"] = self.checkpoint_model.get()
                core.split_checkpoint_option(overrides, {selected})
                if self._sdxl_turbo_active():
                    overrides.update(steps=4, cfg=1)
            if selected in camera_spec.IDS and getattr(self, "camera_spec", {}):
                overrides[camera_spec.KEY] = camera_spec.normalize(self.camera_spec)
        except (ValueError, core.OrchestratorError) as exc:
            messagebox.showerror("生成設定エラー", str(exc))
            return
        cfg = copy.deepcopy(self.config)
        prompt_cache = self.prompt_cache if self.use_prompt_cache.get() else None
        approved_traits = None if is_video else (self.character_traits or None)
        approved_images = tuple(self.character_references) if approved_traits else ()
        approved_analysis = (
            copy.deepcopy(self.character_analysis) if approved_traits else None
        )
        if approved_traits:
            try:
                validate_character_selection(approved_images, approved_analysis, approved_traits)
            except (OSError, ValueError, core.OrchestratorError) as exc:
                messagebox.showerror("キャラ参照", str(exc))
                return
        self.latest_composition_report = ""
        kind = cfg["workflows"][selected]["kind"]
        profile = (
            None if not use_prompt_llm else
            cfg["llm"].get("t2i_prompt_profile", DEFAULT_T2I_PROFILE)
            if selected in core.SDXL_WORKFLOW_IDS and kind == "t2i" else
            cfg["llm"].get("i2i_prompt_profile", DEFAULT_I2I_PROFILE)
            if kind in ("i2i", "inpaint") else
            cfg["llm"].get("h3_prompt_profile", DEFAULT_H3_PROFILE)
            if selected == core.H3_I2V_ID else None
        )
        continuous = self.generation_mode.get() == "continuous"
        if continuous:
            if hasattr(self, "project_workspace") and not self.project_workspace.confirm_replace():
                return
            if selected != core.H3_I2V_ID:
                messagebox.showerror("連続動画生成", "MiniMax H3を選択してください")
                return
            try:
                overrides = long_generation_model(overrides, text_only=text_only_long)
                overlap_frames = preferred_connection_frames(connection_frames(self.h3_connection.get()))
                self.h3_connection.set(connection_label(overlap_frames))
                cut_frames = None
                if self.h3_long_target.get() == CUSTOM_CUTS:
                    cut_frames = getattr(self, "_custom_cut_frames", None)
                    if cut_frames is None:
                        cut_frames = self._edit_cut_durations()
                        if cut_frames is None:
                            return
                    cut_frames = validate_cut_frames(cut_frames)
                    long_seconds = sum(cut_frames) / 24
                    frames = generation_frames_for_cuts(cut_frames)
                else:
                    long_seconds = LONG_TARGETS.get(self.h3_long_target.get(), 0)
                    frames = segment_plan(long_seconds, overrides["frames"])
                if image is not None:
                    if not image.is_file():
                        raise core.OrchestratorError("長尺生成の参照画像がありません")
                    if image.stat().st_size > 40 * 1024 * 1024:
                        raise core.OrchestratorError("参照画像は40MB以下にしてください")
                media = None  # Planning does not require FFmpeg or model preflight.
            except (OSError, core.OrchestratorError) as exc:
                messagebox.showerror("長尺生成", str(exc))
                return
            self._start_long_prompt_plan(
                cfg, prompt, image, overrides, long_seconds, frames, media,
                prompt_cache, dry_run, profile, cut_frames=cut_frames,
                overlap_frames=overlap_frames,
            )
            return
        if dry_run:
            controller = self._controller(cfg, prompt_cache)
            cache = self.project_workspace.translation_cache
            self._single_usage_group = uuid.uuid4().hex
            self._set_busy("プロンプト作成中")
            self._launch_generation(lambda: SinglePromptDraft.prepare(
                controller, prompt, selected, overrides, image=image, mask_image=mask,
                pose_image=pose, composition_image=composition, prompt_profile=profile,
                character_references=approved_images, character_traits=approved_traits,
                character_analysis=approved_analysis, cache=cache,
            ), done_event="single_prompt_ready", cancel_as_progress=True,
                usage={"action": "review", "workflow": selected, "frames": overrides.get("frames"),
                       "group_id": self._single_usage_group})
            return
        self.review.begin(request_text=prompt, profile=profile, character_traits=approved_traits,
                          character_analysis=approved_analysis, character_references=approved_images)
        self._set_busy("生成準備中...")
        self._log("開始: " + ("解釈のみテスト" if dry_run else "動画生成" if is_video else "画像生成")
                  + (f" / model={cfg['llm']['model']}" if use_prompt_llm else " / LLMなし"))

        controller = self._controller(cfg, prompt_cache)
        self._launch_generation(lambda: controller.generate(
            prompt, selected, overrides, image=image, dry_run=dry_run,
            mask_image=mask, pose_image=pose, composition_image=composition,
            prompt_profile=profile, character_references=approved_images,
            character_analysis=approved_analysis,
            **({"character_traits": approved_traits} if approved_traits else {}),
        ), usage={"action": "generate", "workflow": selected, "frames": overrides.get("frames")})

    def _sync_project_visibility(self, visible):
        if self._project_visible == visible:
            return
        self._project_visible = visible
        if visible:
            self.tabs.add(self.project_workspace, text="プロジェクト")
            self.tabs.select(self.project_workspace)
            self._refresh_projects()
        else:
            self.project_workspace.stop_preview()
            self.tabs.hide(self.project_workspace)

    def _refresh_projects(self, preferred=None, *, open_preferred=False):
        self._project_refresh_serial += 1
        serial = self._project_refresh_serial

        def task():
            try:
                projects = self.long_video_store.projects()
                self.messages.put(("projects_loaded", (serial, projects, preferred, open_preferred)))
            except Exception as exc:
                self.messages.put(("progress", "プロジェクト一覧の取得失敗: " + str(exc)))

        threading.Thread(target=task, daemon=True).start()

    def _project_config(self, manifest):
        # Generation inputs are captured separately from the left form.
        # The approved prompt plan retains its original interpretation profile.
        cfg = copy.deepcopy(self.config)
        cfg["comfyui"].update(base_url=self.comfy_url.get().strip(), free_before_llm=self.free_comfy.get())
        cfg["llm"].update(base_url=self.llm_url.get().strip(), model=self.model.get().strip() or "SELECT_IN_GUI",
                          unload_after_inference=self.unload_llm.get())
        if manifest.get("profile"):
            cfg["llm"]["h3_prompt_profile"] = manifest["profile"]
        return cfg

    def _restore_project_inputs(self, manifest):
        """Opening a project initializes the shared generation form once."""
        if self.generation_mode.get() != "continuous":
            return
        p = manifest["overrides"]
        self.prompt.delete("1.0", "end")
        self.prompt.insert("1.0", manifest["request"])
        self.prompt.edit_reset()
        source = self.long_video_store.source_asset(manifest)
        self.reference_image.set(str(source) if source is not None else "")
        self.h3_model.set(core.h3_model_label(p.get("h3_model", "int8")))
        self.h3_turbo.set(core.H3_TURBO_LABELS.get(p.get("h3_turbo", "off"), "OFF"))
        self.h3_performance.set(core.H3_PERFORMANCE_LABELS.get(
            p.get("h3_performance", "standard"), core.H3_PERFORMANCE_LABELS["standard"]))
        self.h3_encoder_cpu.set(p.get("h3_encoder_device", "default") == "cpu")
        self.h3_encoder_model.set(core.H3_ENCODER_LABELS.get(p.get("h3_encoder_model", "nvfp4"), "NVFP4 AWQ"))
        steps = self.h3_hybrid_steps if core.h3_hybrid_filename(p.get("h3_model")) is not None else self.h3_steps
        if "steps" in p:
            steps.set(str(p["steps"]))
        self.h3_size.set(f"{p['width']} × {p['height']}")
        self.h3_duration.set(next((label for label, n in H3_DURATIONS.items() if n == p["frames"]),
                                  f"{p['frames'] / 24:.2f}秒 ({p['frames']}f)"))
        self.seed.set(str(p["seed"]))
        self.h3_connection.set(connection_label(manifest.get("overlap_frames", 0)))
        self.h3_profile.set(H3_PROFILE_LABELS.get(manifest.get("profile"), H3_PROFILE_LABELS[H3_PROFILE_GENERAL]))
        if manifest.get("cut_frames") is not None:
            self._custom_cut_frames = list(manifest["cut_frames"])
            self.h3_long_target.set(CUSTOM_CUTS)
        else:
            label = next((name for name in CONTINUOUS_TARGETS if LONG_TARGETS[name] == manifest["seconds"]), "30秒")
            self.h3_long_target.set(label)
        self._sync_cut_summary()
        self._apply_generation_model_choices()
        self._sync_h3_steps()

    def _restore_long_project(self, entry):
        if not self.project_workspace.confirm_replace():
            return
        run_id = entry.parameters.get("long_run_id")
        try:
            manifest = self.long_video_store.load(self.long_video_store.folder(run_id) / "manifest.json")
        except (OSError, ValueError, KeyError, TypeError, core.OrchestratorError):
            text_only = entry.parameters.get("long_text_only") is True
            if (not entry.parameters.get("long_prompt_plan") or
                    (not text_only and (not entry.reference_image or not entry.reference_image.is_file()))):
                messagebox.showerror("履歴復元", "元の長尺プロジェクト記録と復元に必要な計画または参照画像がありません。")
                return
            if not messagebox.askyesno("履歴復元", "元のプロジェクト記録がありません。"
                                      "\n履歴から未生成の計画を復元しますか？"
                                      "\n旧形式では各カットのSeedを完全には復元できない場合があります。"):
                return
            try:
                manifest = restore_project_plan(self.long_video_store, entry, self.comfy_url.get().strip())
            except (OSError, ValueError, KeyError, TypeError, core.OrchestratorError) as exc:
                messagebox.showerror("履歴復元", str(exc))
                return
            run_id = manifest["run_id"]
        self.generation_mode.set("continuous")
        self.workflow.set(core.H3_I2V_ID)
        self._sync_workflow_choice()
        self._update_generation_controls()
        self._preferred_long_project_id = run_id
        self.project_workspace.load(manifest)
        self.tabs.select(self.project_workspace)
        self._refresh_projects(run_id)
        self.status.set("保存済みの長尺プロジェクトを復元しました")

    def _start_long_prompt_plan(self, cfg, prompt, image, overrides, seconds, frames,
                                media, cache, dry_run, profile, *, cut_frames=None,
                                overlap_frames=GUIDE_CONNECTION_FRAMES):
        text_only = image is None
        overrides = long_generation_model(overrides, text_only=text_only)
        reference_only = core.h3_ref2va_filename(overrides.get("h3_model")) is not None
        translation_cache = self.project_workspace.translation_cache
        self._set_busy("計画生成中")

        def task():
            with tempfile.TemporaryDirectory(prefix="asobiba-long-") as temporary:
                source = copy_frozen_asset(image, Path(temporary), "source") if image is not None else None
                plan = plan_long_prompts(
                    cfg, prompt, frames, seconds, reference_only, cut_frames=cut_frames,
                    overlap_frames=overlap_frames, image=source, text_only=text_only,
                    progress=lambda line: self.messages.put(("progress", line)),
                    cancel_event=self.stop_event, prompt_cache=cache, release_comfy=True,
                    translation_cache=translation_cache,
                )
                if self.stop_event.is_set():
                    raise JobCancellationRequested("長尺計画を中止しました")
                manifest = self.long_video_store.create(
                    cfg["comfyui"]["base_url"], prompt, source, overrides, seconds, profile,
                    prompt_plan=plan, cut_frames=cut_frames, draft=True,
                    overlap_frames=overlap_frames,
                )
            return manifest

        self._launch_generation(task, done_event="long_plan_ready", cancel_as_progress=True,
                                usage={"action": "long_plan", "workflow": core.H3_I2V_ID,
                                       "frames": round(seconds * 24), "cuts": len(frames)})

    def _finish_long_prompt_plan(self, manifest):
        self._preferred_long_project_id = manifest["run_id"]
        self.project_workspace.load(manifest)
        if self.generation_mode.get() == "continuous":
            self.tabs.select(self.project_workspace)
        self._refresh_projects(manifest["run_id"])
        missing = len(self.project_workspace.translation_cache.missing(manifest["prompt_plan"]))
        self.status.set(f"計画保存済み · 未翻訳 {missing}件" if missing else "計画保存済み")

    def _edit_project_prompt(self, manifest, plan, cuts, index, operation, japanese, instruction, cache,
                             *, selected_indices=None):
        """Capture the selected draft; translation/rewrite never creates a video job."""
        if self.working or self.character_analysis_running:
            raise core.OrchestratorError("現在の処理が終了してから操作してください")
        cfg = self._project_config(manifest)
        if cfg["llm"]["model"] in ("", "SELECT_IN_GUI"):
            raise core.OrchestratorError("LM Studioのモデルを選択してください")
        snapshot = copy.deepcopy(manifest)
        plan = copy.deepcopy(plan)
        cuts = list(cuts)
        self._set_busy("一括翻訳中" if operation == "translate_all" else
                       "プロンプト再生成中" if operation == "regenerate" else "プロンプト編集中")

        def task():
            try:
                result = edit_prompts(
                    cfg, snapshot, plan, cuts, index, operation, cache,
                    japanese=dict(japanese), instruction=instruction, selected_indices=selected_indices,
                    progress=lambda line: self.messages.put(("progress", line)),
                    cancel_event=self.stop_event,
                )
            except Exception:
                if operation in ("translate", "translate_all"):
                    # Individual successful translations are already cached.
                    # Refresh the same draft after partial failure/cancellation,
                    # without publishing an English edit or touching Tk here.
                    self.messages.put(("project_translation_cache_updated", (
                        snapshot["run_id"], cuts,
                        {"before": plan, "after": plan, "index": index},
                    )))
                raise
            return snapshot["run_id"], cuts, result

        self._launch_generation(task, done_event="project_prompt_edited",
                                usage={"action": "long_" + operation, "workflow": core.H3_I2V_ID,
                                       "mode": "continuous", "frames": sum(cuts), "cuts": len(cuts),
                                       "group_id": manifest["run_id"]})

    def _project_action(self, manifest, action):
        if self.working or self.character_analysis_running:
            raise core.OrchestratorError("現在の処理が終了してから操作してください")
        overrides = source = overlap_frames = None
        inputs_changed = False
        boundary = None
        if action.action in ("generate", "generate_join"):
            source_text = self.reference_image.get().strip()
            text_only = manifest["source"] is None
            if text_only != (not source_text):
                raise core.OrchestratorError("参照画像の有無を変える場合は新規計画を作成してください")
            overrides = long_generation_model(self._h3_overrides(), text_only=text_only)
            if "seed" not in overrides:
                overrides["seed"] = secrets.randbits(32)
            source = Path(source_text).expanduser() if source_text else None
            effective, source, inputs_changed = project_generation_inputs(
                self.long_video_store, manifest, overrides=overrides, source=source)
            overlap_frames = connection_frames(self.h3_connection.get())
            if "prompt_plan" not in manifest:
                if inputs_changed or overlap_frames != manifest.get("overlap_frames", 0):
                    raise core.OrchestratorError("計画のない旧プロジェクトは新規計画から作成してください")
            else:
                boundary = connection_changed_from(manifest, action.cut_frames, overlap_frames)
        changed = (first_changed_cut(manifest, action.prompt_plan, action.cut_frames)
                   if "prompt_plan" in manifest else None)
        affected = action.regenerate_from
        if changed is not None:
            affected = changed if affected is None else min(changed, affected)
        if boundary is not None:
            affected = boundary if affected is None else min(boundary, affected)
        if inputs_changed:
            affected = 0
        if affected is not None and affected < len(manifest["segments"]):
            reason = ("左側の生成設定または参照画像が変わりました。全カットを再生成します。"
                      if inputs_changed else
                      f"{'接続方式の変更を適用します。' if boundary is not None else ''}カット{affected+1}以降を再生成対象にします。")
            if not messagebox.askyesno("改訂版を作成", reason + "\n元のプロジェクトは保持します。続けますか？"):
                return
        if overrides is not None:
            self.seed.set(str(overrides["seed"]))
            if not self._save_settings():
                return
        cfg = self._project_config(manifest)
        cache = self.prompt_cache if self.use_prompt_cache.get() else None
        self._run_project_action(manifest, action, cfg, cache, overrides=overrides, source=source,
                                 overlap_frames=overlap_frames)

    def _run_project_action(self, manifest, action, cfg, cache, *, overrides=None, source=None,
                            overlap_frames=None):
        if action.action not in ("save", "generate", "generate_join", "join"):
            raise core.OrchestratorError("長尺プロジェクト操作が不正です")
        if action.action in ("generate", "generate_join") and manifest["backend"] != cfg["comfyui"]["base_url"].rstrip("/"):
            raise core.OrchestratorError("保存時と同じComfyUI接続先にしてください")
        if action.action in ("generate_join", "join"):
            self.review.begin(request_text=manifest["request"], profile=manifest.get("profile"))
        self._set_busy("長尺プロジェクト処理中")

        def task():
            if "prompt_plan" in manifest:
                updated = edit_project(
                    self.long_video_store, manifest, self.job_journal,
                    action.prompt_plan, action.cut_frames, regenerate_from=action.regenerate_from,
                    overrides=overrides, source=source, overlap_frames=overlap_frames,
                )
            else:
                if action.action not in ("generate_join", "join"):
                    raise core.OrchestratorError("旧形式は従来の再開・結合のみ対応します")
                updated = manifest
            self.messages.put(("long_project_saved", copy.deepcopy(updated)))
            if action.action == "save":
                return updated["run_id"]
            media = FFmpeg()
            if action.action != "join" and len(updated["segments"]) < len(updated["plan"]):
                guides = max((w.get("guide_frames", 0) for w in manifest_windows(updated)[len(updated["segments"]):]), default=0)
                preflight_long(cfg, CONFIG, updated["overrides"], updated["plan"], cancel_event=self.stop_event,
                               guide_frame_count=guides,
                               text_only_h3=updated["source"] is None and not updated["segments"])
            return self._complete_long_video(
                updated, cfg, media, cache, join_only=action.action == "join",
                auto_join=action.action != "generate",
            )

        event = "long_project_done" if action.action in ("save", "generate") else "done"
        self._launch_generation(task, done_event=event, long_video=True,
                                usage={"action": "long_" + action.action, "workflow": core.H3_I2V_ID,
                                       "mode": "continuous", "frames": sum(action.cut_frames),
                                       "cuts": len(action.cut_frames), "group_id": manifest["run_id"]})

    def _confirm_unknown_long_job(self, record):
        # Worker thread: dialog interaction stays on the Tk main thread.
        answered = threading.Event()
        decision = {"retry": False}
        self.messages.put(("confirm_unknown_long_job", (record, answered, decision)))
        while not answered.wait(0.2):
            if self.stop_event.is_set():
                return False
        return decision["retry"] and not self.stop_event.is_set()

    def _complete_long_video(self, manifest, cfg, media, prompt_cache, *, join_only=False, auto_join=True):
        return self._controller(cfg, prompt_cache).complete_long(
            self.long_video_store, manifest, media, confirm_unknown=self._confirm_unknown_long_job,
            join_only=join_only, auto_join=auto_join,
            on_checkpoint=lambda state: self.messages.put(("long_project_checkpoint", copy.deepcopy(state))),
        )

    def _request_cancel(self) -> None:
        self.tasks.cancel()
        self.status.set("停止要求中")
        self._log("現在の処理の停止を要求しました。送信済みジョブは対象IDのみ停止を試みます。")

    def _recover_jobs(self) -> None:
        """Recover completed outputs without resubmitting or changing the queue."""
        if self.working or self.character_analysis_running:
            return
        cfg = copy.deepcopy(self.config)
        cfg["comfyui"]["base_url"] = self.comfy_url.get().strip()
        self._set_busy("未回収ジョブを確認中")
        self.cancel_button.configure(state="disabled")
        self._launch_generation(self._controller(cfg).recover, done_event="jobs_recovered")

    def _build_event_router(self):
        return EventRouter({
            "progress": self._on_event_progress,
            "timing": self._on_event_timing,
            "operations_report": self._on_event_operations_report,
            "llm_usage": self._on_event_llm_usage,
            "llm_usage_exported": self._on_event_llm_usage_exported,
            "llm_usage_export_error": self._on_event_llm_usage_export_error,
            "operations_error": self._on_event_operations_error,
            "projects_loaded": self._on_event_projects_loaded,
            "long_plan_ready": self._finish_long_prompt_plan,
            "material_frame_ready": self._on_material_frame_ready,
            "model_comparison_progress": self._on_model_comparison_progress,
            "model_comparison_done": self._on_model_comparison_done,
            "image_adjust_ready": self._on_adjust_ready,
            "image_adjust_generated": self._on_adjust_generated,
            "image_adjust_changed": self._on_adjust_changed,
            "single_prompt_ready": self._on_single_prompt_ready,
            "single_prompt_changed": self._on_single_prompt_changed,
            "project_translation_cache_updated": self._on_event_project_translation_cache_updated,
            "project_prompt_edited": self._on_event_project_prompt_edited,
            "long_project_saved": self._on_event_long_project_saved,
            "long_project_checkpoint": self._on_event_long_project_checkpoint,
            "long_project_done": self._on_event_long_project_done,
            "confirm_unknown_long_job": self._on_event_confirm_unknown_long_job,
            "character_analysis_done": self._on_event_character_analysis_done,
            "character_analysis_error": self._on_event_character_analysis_error,
            "character_revision_done": self._on_event_character_revision_done,
            "character_revision_error": self._on_event_character_revision_error,
            "check": self._on_event_check,
            "generation_models": self._on_event_generation_models,
            "generation_models_error": self._on_event_generation_models_error,
            "models": self._on_event_models,
            "history_loaded": lambda data: self._finish_history_refresh(*data),
            "history_flags_changed": self._on_history_flags_changed,
            "cancel_requested": self._on_event_cancel_requested,
            "jobs_recovered": self._on_event_jobs_recovered,
            "done": self._on_event_done,
            "error": self._on_event_error,
            "idle": self._on_event_idle,
        })

    def _consume_messages(self) -> None:
        # A failed UI callback must not strand an already queued idle event.
        for kind, data in self.tasks.drain():
            try:
                if not self.event_router.dispatch(kind, data):
                    self._log("未登録のイベント: " + kind)
            except Exception as exc:
                self.root.report_callback_exception(type(exc), exc, exc.__traceback__)
        if self.root.winfo_exists():
            if self.working:
                self._tick_timing()
            self.root.after(15 if not self.messages.empty() else 100, self._consume_messages)

    def _on_single_prompt_ready(self, draft):
        if self.stop_event.is_set():
            draft.close()
            self.status.set("プロンプト作成を中止しました")
            return
        self.single_draft = draft
        self.status.set("プロンプト確認")

    def _on_single_prompt_changed(self, operation):
        self._single_refresh = True
        if self.single_window and operation == "translate":
            self.single_window._display_language = "日本語"
        self.status.set("プロンプト確認")

    def _close_single_prompt(self):
        if self.single_window is not None:
            self.single_window.destroy()
            self.single_window = None
        if self.single_draft is not None:
            self.single_draft.close()
            self.single_draft = None
        self._single_submit = self._single_success = self._single_refresh = False
        self._single_usage_group = None

    def _single_prompt_action(self, operation, **kwargs):
        if self.working or self.single_draft is None:
            return
        draft = self.single_draft
        cache = self.project_workspace.translation_cache
        if operation == "regenerate" and hasattr(self, "image_reasoning"):
            draft.controller.config["llm"]["image_reasoning"] = IMAGE_REASONING_BY_LABEL[self.image_reasoning.get()]
        if operation == "generate":
            context = draft.context
            self.review.begin(request_text=draft.request, profile=context["prompt_profile"],
                              character_traits=context["character_traits"],
                              character_analysis=context["character_analysis"])
            self._single_submit, self._single_success = True, False
            self._set_busy("確認済みプロンプトで生成中")
            self.single_window.set_busy(True)
            self._launch_generation(draft.generate,
                                    usage={"action": "review_generate", "workflow": draft.workflow_id,
                                           "mode": workflow_generation_mode(draft.controller.config, draft.workflow_id),
                                           "frames": draft.parameters.get("frames"),
                                           "group_id": self._single_usage_group})
        else:
            self._set_busy("プロンプト編集中")
            self.single_window.set_busy(True)
            def task():
                if operation == "translate":
                    draft.translate(cache)
                else:
                    draft.revise(operation, cache, **kwargs)
                return operation
            self._launch_generation(task, done_event="single_prompt_changed", cancel_as_progress=True,
                                    usage={"action": "review_" + operation, "workflow": draft.workflow_id,
                                           "mode": workflow_generation_mode(draft.controller.config, draft.workflow_id),
                                           "frames": draft.parameters.get("frames"),
                                           "group_id": self._single_usage_group})

    def _on_event_progress(self, data):
        if data.startswith("【構図認識結果】\n"):
            self.latest_composition_report = data.split("\n", 1)[1]
            self.status.set("構図認識が完了しました（認識結果...から確認可能）")
        else:
            self.status.set(data)
        self._log(data)

    def _on_event_timing(self, data):
        self.tasks.update_estimate(data)
        self._tick_timing()

    def _on_event_llm_usage(self, data):
        self._log(data)
        if self._operations_window is not None and self._operations_window.is_open():
            self._refresh_operations()

    def _on_event_llm_usage_exported(self, path):
        self._log("LLM使用量 CSV: " + path)
        if self._operations_window is not None and self._operations_window.is_open():
            self._operations_window.usage_status.set("CSV出力済み: " + path)

    def _on_event_llm_usage_export_error(self, error):
        self._log("LLM使用量 CSV出力失敗: " + error)
        if self._operations_window is not None and self._operations_window.is_open():
            messagebox.showerror("CSV出力", error, parent=self._operations_window.window)

    def _on_event_operations_report(self, data):
        self._operations_pending = False
        if self._operations_window is not None and self._operations_window.is_open():
            self._operations_window.update(*data)

    def _on_event_operations_error(self, data):
        self._operations_pending = False
        self._log("運用情報の取得失敗: " + data)
        if self._operations_window is not None and self._operations_window.is_open():
            self._operations_window.summary.set("取得失敗: " + data[:180])

    def _on_event_projects_loaded(self, data):
        serial, projects, preferred, open_preferred = data
        if serial == self._project_refresh_serial:
            self.project_workspace.set_projects(projects, preferred, open_preferred=open_preferred)

    def _on_event_project_translation_cache_updated(self, data):
        self.project_workspace.accept_prompt_result(*data)

    def _on_event_project_prompt_edited(self, data):
        run_id, cuts, result = data
        batch_review = "translated_count" in result
        if self.stop_event.is_set() and not batch_review:
            self.status.set("プロンプト編集を中止しました")
        elif self.project_workspace.accept_prompt_result(run_id, cuts, result):
            changed = result["before"] != result["after"]
            if batch_review:
                self.status.set(f"一括翻訳: {result['translated_count']}件完了（英語原文変更なし）")
            else:
                self.status.set("プロンプト編集完了（未保存・動画未生成）" if changed else "日本語訳を表示しました")
        else:
            self.status.set("計画が変わったため編集結果を適用しませんでした")

    def _on_event_long_project_saved(self, data):
        self._preferred_long_project_id = data["run_id"]
        self.project_workspace.load(data, preserve_selection=True, restore_inputs=False)
        self._refresh_projects(data["run_id"])
        self._log("長尺プロジェクト保存: " + data["run_id"])

    def _on_event_long_project_checkpoint(self, data):
        self.project_workspace.checkpoint(data)

    def _on_event_long_project_done(self, data):
        self._preferred_long_project_id = data
        self.status.set("長尺プロジェクト保存済み")

    def _on_event_confirm_unknown_long_job(self, data):
        record, answered, decision = data
        try:
            if not self.stop_event.is_set():
                decision["retry"] = messagebox.askyesno(
                    "状態不明の長尺ジョブ",
                    "前回ジョブの実行結果が確認できません。ComfyUI側に結果や待機・実行中のジョブがないことを確認してください。\n"
                    "この記録を失敗扱いにして同じ区間を再生成しますか？\n"
                    "以前に生成済みだった場合、再生成になる可能性があります。\n\nID: " + record["prompt_id"],
                )
        finally:
            answered.set()

    def _on_event_character_analysis_done(self, data):
        dialog, analysis = data
        self.character_analysis_running = False
        dialog.finish(analysis=analysis)
        self._log("キャラ参照画像の共通特徴を抽出。編集・確定待ち")
        self.status.set("キャラ特徴を編集して確定してください")

    def _on_event_character_analysis_error(self, data):
        dialog, error = data
        self.character_analysis_running = False
        dialog.finish(error=error)
        self._log("キャラ特徴抽出エラー: " + error)
        self.status.set("キャラ特徴抽出に失敗しました")

    def _on_event_character_revision_done(self, data):
        dialog, revised = data
        self.character_analysis_running = False
        dialog.finish_revision(revised_text=revised)
        self._log("自然文のキャラ説明修正案が完成（未確定）")
        self.status.set("キャラ説明の修正案を確認して確定してください")

    def _on_event_character_revision_error(self, data):
        dialog, error = data
        self.character_analysis_running = False
        dialog.finish_revision(error=error)
        self._log("自然文でのキャラ説明修正エラー: " + error)
        self.status.set("自然文による説明修正に失敗しました")

    def _on_event_check(self, data):
        for line in data:
            self._log(line)
        self.status.set("接続確認が完了しました")

    def _on_event_generation_models(self, data):
        url, inventory = data
        if url == self.comfy_url.get().strip():
            self.generation_inventory = inventory
            self._apply_generation_model_choices()
            choices = core.installed_model_choices(inventory, getattr(self, "_registered_models", ()))
            manager = getattr(self, "model_manager", None)
            if manager is not None and manager.winfo_exists():
                manager.update_inventory(inventory)
            self._log(f"ComfyUIモデル: SDXL {len(choices['sdxl'])}件 / Anima {len(choices['anima'])}件 / H3 {len(choices['h3'])}件")

    def _on_event_generation_models_error(self, data):
        self._log("ComfyUIモデル一覧を更新できません: " + data)
        manager = getattr(self, "model_manager", None)
        if manager is not None and manager.winfo_exists():
            manager.status.set("再検出失敗: " + data[:140])

    def _on_event_models(self, data):
        names = [item["key"] for item in data]
        self.model_box.configure(values=names)
        if self.model.get() not in names and names:
            self.model.set(names[0])
        self._log(f"LM Studioモデル: {len(names)}件。必要なモデルを選択して設定を保存してください。")
        self.status.set(f"モデル一覧を更新: {len(names)}件")

    def _on_event_cancel_requested(self, data):
        self.status.set("停止要求送信済み（終了未確認）")
        self._log(data)

    def _on_event_jobs_recovered(self, data):
        recovered, remaining = data
        self.status.set(f"回収 {recovered}件 / 未回収 {remaining}件")
        self._refresh_history(scan_legacy=False)
        comparison = getattr(self, "comparison_window", None)
        if comparison is not None and comparison.winfo_exists() and comparison.manifest:
            comparison.open_group(comparison.manifest["id"])

    def _on_event_done(self, data):
        result, images, history_id = data
        if self._single_submit:
            draft = self.single_draft
            context = draft.context
            self.review.begin(request_text=draft.request, profile=context["prompt_profile"],
                              character_traits=context["character_traits"],
                              character_analysis=context["character_analysis"],
                              character_references=draft.review_references)
        self.review.publish(result, self.config.get("workflows", {}))
        if self._single_submit and result["status"] != "dry_run":
            self._single_success = True
        self.result_panel.mark_prompt_available()
        if result["status"] == "dry_run":
            self._log("解釈結果:\n" + json.dumps(result, ensure_ascii=False, indent=2))
            self.status.set("解釈テスト完了（ComfyUI未実行）")
            self.tabs.select(0)
            self._show_prompt_preview()
        else:
            self.result_panel.show_outputs(images)
            review = self.review.details() or {}
            self._result_material_context = {
                "workflow": result.get("workflow_id", ""), "parameters": copy.deepcopy(result.get("parameters", {})),
                "profile": review.get("profile"), "request": review.get("request_text"), "history_id": history_id,
            }
            self.result_panel.set_adjustment_available(
                bool(history_id and supported_workflow(result.get("workflow_id"), self.config["workflows"])
                     and isinstance(result.get("parameters", {}).get("positive_prompt"), str)
                     and type(result.get("parameters", {}).get("seed")) is int))
            self._log("生成完了: " + json.dumps(result.get("parameters", {}), ensure_ascii=False))
            if history_id is None:
                self.status.set("出力保存済み / 履歴未登録（未回収結果または長尺再開で回収）")
            else:
                self.status.set("動画生成完了" if any(is_video_output(p) for p in images) else "画像生成完了")
            self.tabs.select(0)
            self._refresh_history(select_id=history_id, scan_legacy=False)

    def _on_event_error(self, data):
        self._log("ERROR: " + data)
        self.status.set("エラー: " + data[:110])
        parent = (self.adjust_window if getattr(self, "_adjust_operation", None) is not None
                  and getattr(self, "adjust_window", None) else self.single_window or self.root)
        messagebox.showerror("処理エラー", data, parent=parent)

    def _on_event_idle(self, data):
        self._tick_timing(finished=True)
        self.tasks.finish()
        self._sync_camera_button()
        self._comparison_active = None
        comparison = getattr(self, "comparison_window", None)
        if comparison is not None and comparison.winfo_exists():
            comparison.set_busy(False)
        self.review.finish()
        self._adjust_operation = None
        if getattr(self, "adjust_window", None) is not None:
            self.adjust_window.set_busy(False)
        if hasattr(self, "project_workspace"):
            self.project_workspace.set_enabled(True)
            if self._project_visible:
                self._refresh_projects()
        self.result_panel.set_busy(False)
        self.history_panel.set_busy(False)
        self.run_button.configure(state="normal")
        self.preview_button.configure(state="normal")
        self.cancel_button.configure(state="disabled")
        if hasattr(self, "free_memory_button"):
            self.free_memory_button.configure(state="normal")
        if hasattr(self, "recover_jobs_button"):
            self.recover_jobs_button.configure(state="normal")
        self.progress_bar.stop()
        self._history_selection_changed()
        if self._single_success:
            self._close_single_prompt()
        elif self.single_draft is not None:
            self._single_submit = False
            if self.single_window is None:
                self.single_window = SinglePromptWindow(
                    self.root, self.single_draft, self.project_workspace.translation_cache,
                    on_action=self._single_prompt_action, on_close=self._close_single_prompt,
                    on_cancel=self._request_cancel, status=self.status,
                    reasoning_variable=getattr(self, "image_reasoning", None),
                )
            else:
                self.single_window.set_busy(False)
                if self._single_refresh:
                    self.single_window.reload()
            self._single_refresh = False
        pending, self._pending_material_transfer = self._pending_material_transfer, None
        if isinstance(pending, tuple):
            self._apply_material_transfer(*pending)

    def _open_image(self) -> None:
        path = self.result_panel.selected_path()
        if path is not None:
            self._open_path(path)

    def _open_outputs(self) -> None:
        OUTPUTS.mkdir(parents=True, exist_ok=True)
        self._open_path(OUTPUTS)

    def _open_path(self, path: Path) -> None:
        try:
            if os.name == "nt":
                os.startfile(str(path))
            else:
                self._log("出力先: " + str(path))
        except OSError as exc:
            messagebox.showerror("ファイルを開けません", str(exc))

    def _on_close(self) -> None:
        if not self.working and hasattr(self, "project_workspace") and not self.project_workspace.confirm_replace():
            return
        if self.working and not messagebox.askokcancel(
            "実行中", "現在の操作の進捗表示は終了します。ComfyUI側の生成ジョブは停止しません。閉じますか？"
        ):
            return
        if not self.working:
            self._close_single_prompt()
            self._close_adjust()
        self.result_panel.result_video.stop()
        self.history_panel.history_video.stop()
        if hasattr(self, "project_workspace"):
            self.project_workspace.stop_preview()
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    # Native Explorer file drops require TkDnD, installed separately.
    # If unavailable, the existing file-picker and all generation modes work.
    root._native_dnd_enabled = enable_native_dnd(root)
    Application(root)
    root.mainloop()


if __name__ == "__main__":
    main()
