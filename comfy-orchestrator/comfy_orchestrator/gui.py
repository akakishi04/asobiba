"""Windows desktop GUI for the fixed-workflow ComfyUI orchestrator.

Runs model inference in worker threads; Tk widgets are updated on the main thread.
No third-party GUI dependencies.
"""

from __future__ import annotations

import copy
import json
import os
import queue
import shutil
import sqlite3
import threading
import urllib.parse
import urllib.request
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

from . import core
from .comparison import ComparisonWindow
from .history import HistoryStore, HistoryEntry, HistoryError
from .mask_editor import edit_mask
from .lmstudio import list_models
from .ime_font import install_native_ime_font, sync_native_ime_font
from .ui_theme import apply_ttk_theme, style_text_widget


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config.json"
EXAMPLE = ROOT / "config.example.json"
OUTPUTS = ROOT / "outputs"


def bootstrap_config() -> dict:
    """Create the local settings file only if missing, preserving custom settings."""
    if not CONFIG.exists():
        shutil.copyfile(EXAMPLE, CONFIG)
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    example = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    if "llm" not in config:
        config["llm"] = copy.deepcopy(example["llm"])
    config["llm"]["provider"] = "lmstudio"
    # Backfill the new inference-only timeout without changing the user's
    # chosen model, endpoint, token limit, or older API-management timeout.
    config["llm"].setdefault(
        "inference_timeout_seconds", example["llm"]["inference_timeout_seconds"]
    )
    config["llm"].setdefault("send_reference_to_llm", False)
    config.setdefault("workflows", {})
    for workflow_id, entry in example.get("workflows", {}).items():
        config["workflows"].setdefault(workflow_id, copy.deepcopy(entry))
    config.setdefault("ui", copy.deepcopy(example.get("ui", {})))
    # One-time migration from the original 4096/2048 token presets.
    # Keep unrelated settings (including the user's chosen model and port).
    # A marker prevents a deliberate future choice of smaller limits from
    # being silently overwritten on the next startup.
    ui = config["ui"]
    if not ui.get("token_defaults_v2_applied", False):
        llm = config["llm"]
        defaults = example["llm"]
        if llm.get("context_length") == 4096:
            llm["context_length"] = defaults["context_length"]
        if llm.get("max_tokens", 2048) == 2048:
            llm["max_tokens"] = defaults["max_tokens"]
        ui["token_defaults_v2_applied"] = True
    return config


def output_images(result: dict) -> list[dict]:
    images: list[dict] = []
    outputs = result.get("outputs", {})
    if not isinstance(outputs, dict):
        return images
    for node_output in outputs.values():
        if not isinstance(node_output, dict):
            continue
        for entry in node_output.get("images", []):
            if isinstance(entry, dict) and isinstance(entry.get("filename"), str):
                images.append({
                    "filename": entry["filename"],
                    "subfolder": str(entry.get("subfolder", "")),
                    "type": str(entry.get("type", "output")),
                })
    return images


def save_output_image(base_url: str, metadata: dict, prompt_id: str) -> Path:
    """Download only a bounded image into the ignored local output directory."""
    parameters = {
        "filename": metadata["filename"],
        "subfolder": metadata["subfolder"],
        "type": metadata["type"],
    }
    url = base_url.rstrip("/") + "/view?" + urllib.parse.urlencode(parameters)
    with urllib.request.urlopen(url, timeout=45) as response:
        payload = response.read(40 * 1024 * 1024 + 1)
    if not payload or len(payload) > 40 * 1024 * 1024:
        raise core.OrchestratorError("画像の取得に失敗しました（40MB超過または空ファイル）")
    safe_name = Path(metadata["filename"].replace("\\", "/")).name
    if not safe_name.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
        raise core.OrchestratorError("未対応の出力画像形式です")
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    destination = OUTPUTS / (prompt_id[:16] + "_" + safe_name)
    destination.write_bytes(payload)
    return destination


def resolve_generation_workflow(
    config: dict, chosen: str, has_image: bool,
    has_mask: bool = False, has_pose: bool = False,
    pose_mode: str = "skeleton",
) -> str | None:
    """Route by available input type: no images always means plain T2I."""
    candidates = core.compatible_workflows(
        config.get("workflows", {}),
        image=True if has_image else None,
        mask=True if has_mask else None,
        pose=True if has_pose else None,
    )
    if not candidates:
        return None
    if has_pose:
        expected = "wai_pose_detect" if pose_mode == "photo" else "wai_pose_skeleton"
        if expected in candidates:
            return expected
    if chosen in candidates:
        return chosen
    preferred = (
        "wai_inpaint_basic" if has_mask else
        "wai_i2i_basic" if has_image else
        "wai_t2i_basic"
    )
    if preferred in candidates:
        return preferred
    return next(iter(candidates)) if len(candidates) == 1 else None


def image_aware_overrides(
    config: dict, workflow_id: str | None, has_image: bool,
    overrides: dict, denoise: str,
    control_strength: str = "0.85",
) -> dict:
    """Strip settings unsupported by a selected workflow."""
    candidates = (
        [config["workflows"][workflow_id]] if workflow_id in config["workflows"]
        else list(core.compatible_workflows(
            config.get("workflows", {}), image=True if has_image else None,
        ).values())
    )
    if not candidates:
        raise core.OrchestratorError("入力画像に対応するワークフローがありません")
    common = set(candidates[0]["bindings"])
    for entry in candidates[1:]:
        common.intersection_update(entry["bindings"])
    result = {key: value for key, value in overrides.items() if key in common}
    for field, raw in (("denoise", denoise), ("control_strength", control_strength)):
        if field in common:
            value = float(raw)
            core.check_param(field, value)
            result[field] = value
    return result

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


def preview_subsample(
    image_width: int, image_height: int, viewport_width: int,
    viewport_height: int, maximum: int,
) -> int:
    """Integer downscale factor fitting an image into its available viewport.

    Tk PhotoImage uses integer subsampling. Small or still-unmapped viewports
    fall back to a conservative capped preview size.
    """
    safe_width = max(80, min(maximum, viewport_width if viewport_width >= 40 else maximum))
    safe_height = max(80, min(maximum, viewport_height if viewport_height >= 40 else maximum))
    return max(
        1,
        (image_width + safe_width - 1) // safe_width,
        (image_height + safe_height - 1) // safe_height,
    )


class Application:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Asobiba | Comfy Orchestrator")
        width, height, x, y, min_width, min_height = initial_window_bounds(
            self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        )
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        self.root.minsize(min_width, min_height)
        self.messages: queue.Queue = queue.Queue()
        self.working = False
        self.stop_event = threading.Event()
        self.image_paths: list[Path] = []
        self.preview_photo: tk.PhotoImage | None = None
        self.config = bootstrap_config()
        self.history_store = HistoryStore(ROOT)
        self.history_entries: dict[str, HistoryEntry] = {}
        self.history_preview_photo: tk.PhotoImage | None = None
        self._variables()
        self._build()
        self._refresh_history()
        self.root.after(100, self._consume_messages)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _variables(self) -> None:
        llm = self.config["llm"]
        comfy = self.config["comfyui"]
        options = self.config.get("ui", {})
        self.llm_url = tk.StringVar(value=llm.get("base_url", "http://127.0.0.1:1234"))
        self.comfy_url = tk.StringVar(value=comfy.get("base_url", "http://127.0.0.1:8188"))
        self.model = tk.StringVar(value="" if llm.get("model") == "SELECT_IN_GUI" else llm.get("model", ""))
        workflows = list(self.config.get("workflows", {}))
        preferred = options.get("workflow", workflows[0] if workflows else "自動")
        self.workflow = tk.StringVar(value=preferred if preferred in workflows else "自動")
        self.width = tk.StringVar(value=str(options.get("width", 768)))
        self.height = tk.StringVar(value=str(options.get("height", 768)))
        self.steps = tk.StringVar(value=str(options.get("steps", 20)))
        self.cfg = tk.StringVar(value=str(options.get("cfg", 5.0)))
        self.seed = tk.StringVar(value=str(options.get("seed", "")))
        self.denoise = tk.StringVar(value=str(options.get("denoise", 0.53)))
        self.size_hint = tk.StringVar(value="")
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
        self.free_comfy = tk.BooleanVar(value=comfy.get("free_before_llm", True))
        self.status = tk.StringVar(value="準備完了 — LM Studioのサーバーを起動してください")
        self.result_info = tk.StringVar(value="生成画像はここに表示されます")

    def _build(self) -> None:
        colors = apply_ttk_theme(self.root, self.dark_mode.get())

        layout = ttk.Frame(self.root, padding=10)
        layout.pack(fill="both", expand=True)
        title_row = ttk.Frame(layout)
        title_row.pack(fill="x")
        ttk.Label(title_row, text="Comfy Orchestrator", style="Heading.TLabel").pack(side="left")
        ttk.Checkbutton(
            title_row, text="ダーク表示", variable=self.dark_mode,
            command=self._switch_theme,
        ).pack(side="right", padx=(10, 0))
        ttk.Label(
            layout,
            text="自然文 → LM Studioで解釈 → LLMアンロード → ComfyUI画像生成",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(1, 6))

        connection = ttk.LabelFrame(layout, text="接続・モデル", padding=10, style="Section.TLabelframe")
        connection.pack(fill="x")
        connection.columnconfigure(1, weight=1)
        connection.columnconfigure(3, weight=1)
        ttk.Label(connection, text="LM Studio").grid(row=0, column=0, sticky="w", padx=(0, 7), pady=3)
        ttk.Entry(connection, textvariable=self.llm_url).grid(row=0, column=1, sticky="ew", padx=(0, 12))
        ttk.Label(connection, text="ComfyUI").grid(row=0, column=2, sticky="w", padx=(0, 7))
        ttk.Entry(connection, textvariable=self.comfy_url).grid(row=0, column=3, sticky="ew")
        ttk.Label(connection, text="解釈用モデル").grid(row=1, column=0, sticky="w", pady=(6, 3))
        self.model_box = ttk.Combobox(connection, textvariable=self.model, state="normal")
        self.model_box.grid(row=1, column=1, sticky="ew", pady=(6, 3), padx=(0, 12))
        ttk.Button(connection, text="モデルを更新", command=self._refresh_models).grid(
            row=1, column=2, sticky="ew", padx=(0, 7), pady=(6, 3)
        )
        ttk.Button(connection, text="接続確認", command=self._check_connections).grid(
            row=1, column=3, sticky="w", pady=(6, 3)
        )

        options_frame = ttk.Frame(connection)
        options_frame.grid(row=2, column=0, columnspan=4, sticky="ew", pady=(6, 0))
        ttk.Checkbutton(
            options_frame, text="解釈後にLLMを解放（推奨）",
            variable=self.unload_llm
        ).pack(side="left", padx=(0, 22))
        ttk.Checkbutton(
            options_frame, text="解釈前にComfyUIを解放",
            variable=self.free_comfy
        ).pack(side="left")
        ttk.Button(options_frame, text="設定を保存", command=self._save_settings).pack(side="right")

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

        prompt_panel = ttk.LabelFrame(left, text="自然文・生成設定（下へスクロール可能）", padding=8, style="Section.TLabelframe")
        prompt_panel.pack(fill="both", expand=True, padx=(0, 6))

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
        self.root.bind("<MouseWheel>", self._on_form_mousewheel, add="+")
        self.root.bind("<Button-4>", self._on_form_mousewheel, add="+")
        self.root.bind("<Button-5>", self._on_form_mousewheel, add="+")

        editor_toolbar = ttk.Frame(self.options_form)
        editor_toolbar.pack(fill="x", pady=(0, 7))
        ttk.Label(
            editor_toolbar,
            text="日本語で指示を入力。LLMが生成向けのプロンプトに変換します。",
            style="Muted.TLabel",
        ).pack(side="left", fill="x", expand=True)
        ttk.Button(
            editor_toolbar, text="A+", width=4, command=lambda: self._change_editor_font(1),
        ).pack(side="right", padx=(4, 0))
        ttk.Button(
            editor_toolbar, text="A−", width=4, command=lambda: self._change_editor_font(-1),
        ).pack(side="right", padx=(4, 0))
        self.prompt = scrolledtext.ScrolledText(
            self.options_form, height=6, wrap="word",
            font=("Meiryo UI", self.editor_font_size.get()),
            undo=True, autoseparators=True, maxundo=100,
            padx=14, pady=12, spacing1=3, spacing3=3,
        )
        self.prompt.insert("1.0", "夕暮れの海辺に立つ銀髪の少女。アニメ調で、風になびく髪を自然に描いて。")
        # Never stretch the editor into a huge empty white area. It remains
        # scrollable for longer prompts; IME composition is handled natively.
        self.prompt.pack(fill="x", expand=False, pady=(0, 10))

        settings = ttk.LabelFrame(
            self.options_form, text="生成パラメータ", padding=8,
        )
        settings.pack(fill="x", pady=(0, 8))
        # Two setting pairs per row fit narrow split panes much better than six columns.
        for col in (1, 3):
            settings.columnconfigure(col, weight=1)

        ttk.Label(settings, text="ワークフロー").grid(
            row=0, column=0, sticky="w", padx=(0, 6)
        )
        self.workflow_box = ttk.Combobox(
            settings, textvariable=self.workflow,
            values=["自動", *self.config.get("workflows", {}).keys()],
            state="readonly",
        )
        self.workflow_box.grid(
            row=0, column=1, columnspan=3, sticky="ew", pady=4,
        )
        self.workflow_box.bind(
            "<<ComboboxSelected>>", lambda _e: self._update_generation_controls()
        )
        ttk.Label(settings, text="幅").grid(row=1, column=0, sticky="w", padx=(0, 5))
        self.width_entry = ttk.Entry(settings, textvariable=self.width, width=8)
        self.width_entry.grid(row=1, column=1, sticky="ew", padx=(0, 8))
        ttk.Label(settings, text="高さ").grid(row=1, column=2, sticky="w", padx=(0, 5))
        self.height_entry = ttk.Entry(settings, textvariable=self.height, width=8)
        self.height_entry.grid(row=1, column=3, sticky="ew")

        ttk.Label(settings, text="Steps").grid(row=2, column=0, sticky="w")
        ttk.Entry(settings, textvariable=self.steps, width=8).grid(
            row=2, column=1, sticky="ew", padx=(0, 8),
        )
        ttk.Label(settings, text="CFG").grid(row=2, column=2, sticky="w")
        ttk.Entry(settings, textvariable=self.cfg, width=8).grid(
            row=2, column=3, sticky="ew",
        )
        ttk.Label(settings, text="Seed").grid(row=3, column=0, sticky="w")
        ttk.Entry(settings, textvariable=self.seed).grid(
            row=3, column=1, columnspan=3, sticky="ew",
        )
        ttk.Label(settings, text="Denoise (I2I)").grid(row=4, column=0, sticky="w")
        self.denoise_entry = ttk.Entry(settings, textvariable=self.denoise, width=8)
        self.denoise_entry.grid(row=4, column=1, sticky="ew", padx=(0, 8))
        ttk.Label(settings, text="ポーズ強度").grid(row=4, column=2, sticky="w")
        self.strength_entry = ttk.Entry(
            settings, textvariable=self.control_strength, width=8,
        )
        self.strength_entry.grid(row=4, column=3, sticky="ew")
        ttk.Label(
            settings, textvariable=self.size_hint, style="Muted.TLabel",
        ).grid(row=5, column=0, columnspan=4, sticky="w", pady=(4, 0))
        ttk.Label(
            settings, text="Seed空欄＝ランダム。画像なしはT2I／マスク指定は部分修正。",
            style="Muted.TLabel",
        ).grid(row=6, column=0, columnspan=4, sticky="w", pady=(3, 0))

        image_row = ttk.Frame(self.options_form)
        image_row.pack(fill="x", pady=(0, 12))
        ttk.Label(image_row, text="参照画像").pack(side="left", padx=(0, 8))
        ttk.Entry(image_row, textvariable=self.reference_image, width=8).pack(side="left", fill="x", expand=True)
        ttk.Button(image_row, text="参照...", command=self._browse_image).pack(side="left", padx=(5, 0))
        ttk.Button(image_row, text="消去", command=lambda: self.reference_image.set("")).pack(side="left", padx=(5, 0))
        ttk.Label(
            self.options_form,
            text="I2Iでは参照画像が必要です。画像はComfyUIに送ります。LLMの画像認識は初期設定でOFF。",
            wraplength=460, style="Muted.TLabel",
        ).pack(anchor="w", pady=(0, 10))
        self.reference_image.trace_add(
            "write", lambda *_args: self._on_reference_image_changed()
        )
        composition_row = ttk.Frame(self.options_form)
        composition_row.pack(fill="x", pady=(0, 5))
        ttk.Label(composition_row, text="構図参考（LLMのみ）").pack(
            side="left", padx=(0, 6),
        )
        ttk.Entry(
            composition_row, textvariable=self.composition_image,
            state="readonly", width=8,
        ).pack(side="left", fill="x", expand=True)
        ttk.Button(
            composition_row, text="参照...", command=self._browse_composition,
        ).pack(side="left", padx=(5, 0))
        ttk.Button(
            composition_row, text="消去",
            command=lambda: self.composition_image.set(""),
        ).pack(side="left", padx=(5, 0))
        self.composition_image.trace_add(
            "write", lambda *_args: self._update_generation_controls(),
        )
        ttk.Label(
            self.options_form,
            text="この画像はComfyUIへ送らず、LLMの構図説明だけに使います。"
                 "他の参照画像がなければT2Iで生成します。",
            style="Muted.TLabel", wraplength=470,
        ).pack(anchor="w", pady=(0, 8))

        mask_row = ttk.Frame(self.options_form)
        mask_row.pack(fill="x", pady=(0, 5))
        ttk.Label(mask_row, text="部分修正").pack(side="left", padx=(0, 9))
        ttk.Entry(mask_row, textvariable=self.mask_image, state="readonly", width=8).pack(
            side="left", fill="x", expand=True
        )
        self.mask_button = ttk.Button(
            mask_row, text="範囲を塗る...", command=self._edit_mask,
        )
        self.mask_button.pack(side="left", padx=(5, 0))
        ttk.Button(
            mask_row, text="消去", command=lambda: self.mask_image.set(""),
        ).pack(side="left", padx=(5, 0))
        self.mask_image.trace_add(
            "write", lambda *_args: self._on_mask_image_changed()
        )

        pose_row = ttk.Frame(self.options_form)
        pose_row.pack(fill="x", pady=(0, 5))
        ttk.Label(pose_row, text="ポーズ参照").pack(side="left", padx=(0, 5))
        ttk.Entry(pose_row, textvariable=self.pose_image, state="readonly", width=8).pack(
            side="left", fill="x", expand=True
        )
        ttk.Button(pose_row, text="参照...", command=self._browse_pose).pack(
            side="left", padx=(5, 0)
        )
        ttk.Button(
            pose_row, text="消去", command=lambda: self.pose_image.set(""),
        ).pack(side="left", padx=(5, 0))
        self.pose_image.trace_add(
            "write", lambda *_args: self._on_pose_image_changed()
        )
        pose_modes = ttk.Frame(self.options_form)
        pose_modes.pack(fill="x", pady=(0, 6))
        ttk.Radiobutton(
            pose_modes, text="骨格PNGを直接利用", variable=self.pose_mode,
            value="skeleton", command=self._on_pose_image_changed,
        ).pack(anchor="w")
        ttk.Radiobutton(
            pose_modes, text="通常画像から骨格検出（DWPose）", variable=self.pose_mode,
            value="photo", command=self._on_pose_image_changed,
        ).pack(anchor="w", pady=(2, 0))
        ttk.Label(
            self.options_form, text="ポーズ参照はT2Iと別の入力です。通常画像モードは追加ControlNet・DWPoseが必要。",
            style="Muted.TLabel", wraplength=470,
        ).pack(anchor="w", pady=(0, 6))
        self.vision_checkbox = ttk.Checkbutton(
            self.options_form,
            text="画像をLLMで構図解析し、プロンプトに反映",
            variable=self.vision_composition,
        )
        self.vision_checkbox.pack(anchor="w", pady=(2, 2))
        ttk.Label(
            self.options_form,
            text="画像対応VLMが必要。人物の位置・視点・ポーズを英文タグに変換します。"
                 "厳密な構図固定はControlNetを利用。",
            style="Muted.TLabel", wraplength=470,
        ).pack(anchor="w", pady=(0, 8))

        self.preview_button = ttk.Button(action_row, text="解釈のみテスト", command=lambda: self._start(True))
        self.preview_button.pack(side="left", padx=(0, 8))
        self.run_button = ttk.Button(
            action_row, text="画像生成を開始", style="Run.TButton", command=lambda: self._start(False)
        )
        self.run_button.pack(side="left", padx=(0, 8))
        self.cancel_button = ttk.Button(
            action_row, text="待機を中止", command=self._request_cancel, state="disabled"
        )
        self.cancel_button.pack(side="left")

        self.tabs = ttk.Notebook(right)
        self.tabs.pack(fill="both", expand=True)
        preview_panel = ttk.Frame(self.tabs, padding=8)
        self.tabs.add(preview_panel, text="今回の結果")
        history_panel = ttk.Frame(self.tabs, padding=8)
        self.tabs.add(history_panel, text="生成履歴")

        # Output and history actions are packed before expanding previews/lists.
        # They remain visible even when the window is shorter than requested.
        preview_actions = ttk.Frame(preview_panel)
        preview_actions.pack(side="bottom", fill="x", pady=(5, 0))
        preview_meta = ttk.Frame(preview_panel)
        preview_meta.pack(side="bottom", fill="x")
        history_actions = ttk.Frame(history_panel)
        history_actions.pack(side="bottom", fill="x", pady=(5, 0))
        history_meta = ttk.Frame(history_panel)
        history_meta.pack(side="bottom", fill="x", pady=(5, 0))
        self.image_label = ttk.Label(preview_panel, text="生成画像のプレビュー", anchor="center")
        self.image_label.pack(fill="both", expand=True)
        ttk.Label(preview_meta, textvariable=self.result_info, wraplength=350).pack(anchor="w", pady=(3, 4))
        self.images_list = tk.Listbox(
            preview_meta, height=3, exportselection=False, font=("Meiryo UI", 9),
        )
        self.images_list.pack(fill="x", pady=(0, 5))
        self.images_list.bind("<<ListboxSelect>>", self._show_selected_image)
        row = ttk.Frame(preview_actions)
        row.pack(fill="x")
        self.open_button = ttk.Button(row, text="画像を開く", command=self._open_image, state="disabled")
        self.open_button.pack(side="left", padx=(0, 6))
        ttk.Button(row, text="保存先を開く", command=self._open_outputs).pack(side="left")
        ttk.Button(
            preview_actions, text="この画像からI2I", command=self._current_output_to_i2i,
        ).pack(fill="x", pady=(5, 0))

        ttk.Label(
            history_panel,
            text="履歴を選択して設定を復元。Ctrl+クリックで2件選択すると比較できます。",
            style="Muted.TLabel", wraplength=410,
        ).pack(anchor="w", pady=(1, 7))
        history_columns = ("date", "workflow", "seed")
        table_holder = ttk.Frame(history_panel)
        table_holder.pack(fill="both", expand=True)
        self.history_table = ttk.Treeview(
            table_holder, columns=history_columns, show="tree headings",
            selectmode="extended", height=6,
        )
        self.history_table.heading("#0", text="指示 / 生成内容")
        self.history_table.column("#0", width=230, minwidth=130, stretch=True)
        self.history_table.heading("date", text="日時")
        self.history_table.column("date", width=126, minwidth=105, stretch=False)
        self.history_table.heading("workflow", text="種別")
        self.history_table.column("workflow", width=85, minwidth=70, stretch=False)
        self.history_table.heading("seed", text="Seed")
        self.history_table.column("seed", width=93, minwidth=70, stretch=False)
        history_y = ttk.Scrollbar(table_holder, orient="vertical", command=self.history_table.yview)
        history_x = ttk.Scrollbar(table_holder, orient="horizontal", command=self.history_table.xview)
        self.history_table.configure(yscrollcommand=history_y.set, xscrollcommand=history_x.set)
        self.history_table.grid(row=0, column=0, sticky="nsew")
        history_y.grid(row=0, column=1, sticky="ns")
        history_x.grid(row=1, column=0, sticky="ew")
        table_holder.columnconfigure(0, weight=1)
        table_holder.rowconfigure(0, weight=1)
        self.history_table.bind("<<TreeviewSelect>>", self._history_selection_changed)
        self.history_table.bind("<Double-1>", lambda _e: self._restore_selected_history())

        self.history_details = tk.StringVar(value="履歴を選択してください")
        ttk.Label(
            history_meta, textvariable=self.history_details,
            wraplength=420, style="Muted.TLabel",
        ).pack(anchor="w", fill="x", pady=(8, 5))
        self.history_image = ttk.Label(
            history_meta, text="履歴画像", anchor="center",
        )
        self.history_image.pack(fill="x", pady=(0, 4))
        first_row = ttk.Frame(history_actions)
        first_row.pack(fill="x", pady=(2, 4))
        ttk.Button(
            first_row, text="設定を復元", command=self._restore_selected_history,
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            first_row, text="比較", command=self._compare_selected_history,
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            first_row, text="履歴更新", command=self._refresh_history,
        ).pack(side="left")
        second_row = ttk.Frame(history_actions)
        second_row.pack(fill="x")
        self.same_seed_button = ttk.Button(
            second_row, text="同じSeedで再生成",
            command=lambda: self._regenerate_selected_history(new_seed=False),
            state="disabled",
        )
        self.same_seed_button.pack(side="left", padx=(0, 6))
        self.new_seed_button = ttk.Button(
            second_row, text="別Seedで再生成",
            command=lambda: self._regenerate_selected_history(new_seed=True),
            state="disabled",
        )
        self.new_seed_button.pack(side="left")
        ttk.Button(
            history_actions, text="選択した画像をI2Iの元画像にする",
            command=self._history_output_to_i2i,
        ).pack(fill="x", pady=(6, 0))

        self._switch_theme()
        self._update_generation_controls()
        install_native_ime_font(self.prompt)
        self._log("GUI起動。LM StudioのDeveloper画面でLocal Serverを起動してください。")
        self._log("設定は comfy-orchestrator/config.json に保存され、Gitには含まれません。")

    def _size_form_to_canvas(self, width: int) -> None:
        """Match the scrollable form to its viewport without growing the window."""
        self.form_canvas.itemconfigure(self.form_window, width=max(1, width))
        self._sync_form_scrollregion()

    def _sync_form_scrollregion(self) -> None:
        bounds = self.form_canvas.bbox("all")
        if bounds:
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
        style_text_widget(self.images_list, colors)
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
        get = lambda name: bool(getattr(self, name, None) and getattr(self, name).get().strip())
        pose_mode = getattr(self, "pose_mode", None)
        return resolve_generation_workflow(
            self.config, self.workflow.get(),
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
            if hasattr(self, "mask_image") and source != previous:
                self.mask_image.set("")
            if source and hasattr(self, "pose_image"):
                self.pose_image.set("")
        finally:
            self._source_change_lock = False
        chosen = self._active_workflow()
        if chosen:
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
        if chosen:
            self.workflow.set(chosen)
        self._update_generation_controls()

    def _on_mask_image_changed(self) -> None:
        if self._source_change_lock:
            return
        chosen = self._active_workflow()
        if chosen:
            self.workflow.set(chosen)
        self._update_generation_controls()

    def _update_generation_controls(self) -> None:
        """Disable only the settings that are unsupported by the active mode."""
        workflow_id = self._active_workflow()
        # Keep the combobox honest: a missing reference always shows plain T2I.
        if workflow_id and self.workflow.get() not in ("自動", workflow_id):
            self.workflow.set(workflow_id)
        bindings = self.config["workflows"].get(workflow_id, {}).get("bindings", {})
        uses_source_image = "image" in bindings
        for entry in (self.width_entry, self.height_entry):
            entry.configure(state="disabled" if uses_source_image else "normal")
        self.denoise_entry.configure(
            state="normal" if "denoise" in bindings else "disabled"
        )
        if hasattr(self, "strength_entry"):
            self.strength_entry.configure(
                state="normal" if "control_strength" in bindings else "disabled"
            )
        if hasattr(self, "mask_button"):
            self.mask_button.configure(
                state="normal" if self.reference_image.get().strip() else "disabled"
            )
        if hasattr(self, "vision_checkbox"):
            has_visual_reference = bool(
                self.reference_image.get().strip()
                or self.pose_image.get().strip()
                or self.composition_image.get().strip()
            )
            self.vision_checkbox.configure(
                state="normal" if has_visual_reference else "disabled"
            )
        hint = (
            "ポーズを参照して生成" if "pose" in bindings else
            "マスクの白い部分だけ変更" if "mask" in bindings else
            "I2Iは元画像サイズ" if uses_source_image else
            "構図画像をLLMで解析→T2I" if self.composition_image.get().strip() else
            "参照画像なし：自動でT2I"
        )
        self.size_hint.set(hint)


    def _log(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _refresh_history(self, select_id: str | None = None) -> None:
        """Show latest saved images, including older outputs with unknown parameters."""
        try:
            self.history_store.import_legacy_outputs(limit=500)
            entries = self.history_store.list_entries(limit=500)
        except (HistoryError, OSError, ValueError, sqlite3.Error) as exc:
            self._log(f"履歴の読み込みに失敗: {exc}")
            return
        old_selected = set(self.history_table.selection())
        self.history_entries = {entry.id: entry for entry in entries}
        for item in self.history_table.get_children():
            self.history_table.delete(item)
        for entry in entries:
            short = entry.request_text.replace("\n", " ").strip()[:80]
            title = short or "(プロンプトなし)"
            timestamp = entry.created_at
            try:
                from datetime import datetime
                timestamp = datetime.fromisoformat(entry.created_at).astimezone().strftime("%m/%d %H:%M")
            except (ValueError, OverflowError):
                timestamp = entry.created_at[:16]
            seed = str(entry.parameters.get("seed", "—"))
            self.history_table.insert(
                "", "end", iid=entry.id, text=title,
                values=(timestamp, entry.kind.upper(), seed),
            )
        requested = {select_id} if select_id else old_selected
        available = [entry_id for entry_id in requested if entry_id in self.history_entries]
        if available:
            self.history_table.selection_set(*available)
            self.history_table.see(available[0])
        self._history_selection_changed()
        if not entries:
            self.history_details.set("まだ保存された生成結果がありません")

    def _selected_history(self) -> list[HistoryEntry]:
        return [
            self.history_entries[entry_id]
            for entry_id in self.history_table.selection()
            if entry_id in self.history_entries
        ]

    def _one_history(self) -> HistoryEntry | None:
        selected = self._selected_history()
        return selected[0] if len(selected) == 1 else None

    def _history_selection_changed(self, _event=None) -> None:
        selected = self._selected_history()
        can_replay = (
            len(selected) == 1
            and not selected[0].legacy
            and selected[0].workflow_id in self.config["workflows"]
            and selected[0].first_image is not None
            and (selected[0].reference_image is None or selected[0].reference_image.is_file())
            and (selected[0].mask_image is None or selected[0].mask_image.is_file())
            and (selected[0].pose_image is None or selected[0].pose_image.is_file())
            and not self.working
        )
        state = "normal" if can_replay else "disabled"
        self.same_seed_button.configure(state=state)
        self.new_seed_button.configure(state=state)

        if not selected:
            self.history_details.set("履歴を選択してください")
            self.history_image.configure(image="", text="履歴画像")
            self.history_preview_photo = None
            return
        if len(selected) > 1:
            self.history_details.set(
                f"{len(selected)}件選択中。2件を比較するには「比較」を押してください。"
            )
            self.history_image.configure(image="", text="2件選択中")
            self.history_preview_photo = None
            return

        entry = selected[0]
        p = entry.parameters
        self.history_details.set(
            f"ワークフロー: {entry.workflow_id} / "
            f"Seed: {p.get('seed', '不明')} / "
            f"Steps: {p.get('steps', '不明')} / "
            f"CFG: {p.get('cfg', '不明')} / "
            f"画像: {len(entry.images)}枚"
            + (" / 旧画像（再生成用設定なし）" if entry.legacy else "")
        )
        image = entry.first_image
        if image is None or not image.is_file():
            self.history_preview_photo = None
            self.history_image.configure(image="", text="画像ファイルが見つかりません")
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
                image="", text="プレビューできない形式です。比較画面で確認してください"
            )

    def _restore_selected_history(self) -> None:
        entry = self._one_history()
        if entry is None:
            messagebox.showinfo("履歴", "復元する履歴を1件選択してください")
            return
        if entry.legacy or entry.workflow_id not in self.config["workflows"]:
            messagebox.showinfo(
                "履歴", "この画像には生成設定が保存されていないため復元できません"
            )
            return
        self.prompt.delete("1.0", "end")
        self.prompt.insert("1.0", entry.request_text)
        self._source_change_lock = True
        try:
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
        for key, variable in (
            ("width", self.width), ("height", self.height),
            ("steps", self.steps), ("cfg", self.cfg),
            ("denoise", self.denoise), ("seed", self.seed),
        ):
            if key in entry.parameters:
                variable.set(str(entry.parameters[key]))
            elif key == "seed":
                variable.set("")
        self._update_generation_controls()
        self.status.set("履歴から設定を復元しました。自然文を編集して生成できます")
        self._log(f"履歴の設定を復元: {entry.workflow_id} / Seed={entry.parameters.get('seed', '不明')}")
        self.prompt.focus_set()

    def _compare_selected_history(self) -> None:
        entries = self._selected_history()
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

    def _record_completed_generation(
        self, result: dict, images: list[Path], request_text: str,
        source_image: Path | None, mask_image: Path | None = None,
        pose_image: Path | None = None,
        composition_image: Path | None = None,
    ) -> str | None:
        if not images:
            return None
        try:
            workflow_id = result["workflow_id"]
            entry = self.history_store.record(
                prompt_id=result["prompt_id"],
                workflow_id=workflow_id,
                kind=self.config["workflows"][workflow_id]["kind"],
                request_text=request_text,
                parameters=result["parameters"],
                images=images,
                reference_image=source_image,
                mask_image=mask_image,
                pose_image=pose_image,
                composition_image=composition_image,
            )
            return entry.id
        except (HistoryError, OSError, ValueError, sqlite3.Error) as exc:
            self.messages.put(("progress", f"履歴保存に失敗しました（画像は保持）: {exc}"))
            return None

    def _set_busy(self, label: str) -> None:
        self.stop_event.clear()
        self.working = True
        self.run_button.configure(state="disabled")
        self.preview_button.configure(state="disabled")
        self.cancel_button.configure(state="normal")
        self.same_seed_button.configure(state="disabled")
        self.new_seed_button.configure(state="disabled")
        self.progress_bar.start(12)
        self.status.set(label)

    def _regenerate_selected_history(self, *, new_seed: bool) -> None:
        if self.working:
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
        self._set_busy("保存した設定を使って再生成中（LLMは呼び出しません）")
        self._log(
            f"再生成: {entry.workflow_id} / "
            + ("別Seed" if new_seed else "同じSeed")
        )

        def task():
            try:
                result = core.execute_saved(
                    cfg, CONFIG, entry.workflow_id, entry.parameters,
                    reference_image=entry.reference_image,
                    new_seed=new_seed,
                    progress=lambda line: self.messages.put(("progress", line)),
                    cancel_event=self.stop_event,
                    mask_image=entry.mask_image, pose_image=entry.pose_image,
                )
                images = []
                for item in output_images(result):
                    try:
                        images.append(
                            save_output_image(
                                cfg["comfyui"]["base_url"], item, result["prompt_id"]
                            )
                        )
                    except Exception as exc:
                        self.messages.put(("progress", f"画像取得エラー: {exc}"))
                history_id = self._record_completed_generation(
                    result, images, entry.request_text, entry.reference_image,
                    entry.mask_image, entry.pose_image,
                    entry.composition_image if entry.composition_image
                    and entry.composition_image.is_file() else None,
                )
                self.messages.put(("done", (result, images, history_id)))
            except Exception as exc:
                self.messages.put(("error", str(exc)))
            finally:
                self.messages.put(("idle", None))
        threading.Thread(target=task, daemon=True).start()

    def _collect_config(self) -> dict:
        config = copy.deepcopy(self.config)
        config["llm"]["provider"] = "lmstudio"
        config["llm"]["base_url"] = self.llm_url.get().strip()
        config["llm"]["model"] = self.model.get().strip() or "SELECT_IN_GUI"
        config["llm"]["unload_after_inference"] = self.unload_llm.get()
        config["llm"]["send_reference_to_llm"] = self.vision_composition.get()
        config["comfyui"]["base_url"] = self.comfy_url.get().strip()
        config["comfyui"]["free_before_llm"] = self.free_comfy.get()
        opts = self._overrides()
        config["ui"] = {
            **opts,
            "workflow": self.workflow.get(),
            "dark_mode": self.dark_mode.get(),
            "font_size": self.editor_font_size.get(),
        }
        config["ui"]["seed"] = self.seed.get().strip()
        config["ui"]["denoise"] = self.denoise.get().strip()
        config["ui"]["pose_mode"] = self.pose_mode.get()
        config["ui"]["control_strength"] = self.control_strength.get().strip()
        return config

    def _overrides(self) -> dict:
        values = {
            "width": int(self.width.get()),
            "height": int(self.height.get()),
            "steps": int(self.steps.get()),
            "cfg": float(self.cfg.get()),
        }
        if self.seed.get().strip():
            values["seed"] = int(self.seed.get().strip())
        for name, value in values.items():
            core.check_param(name, value)
        return values

    def _save_settings(self) -> bool:
        if self.working:
            return False
        try:
            config = self._collect_config()
            backup_path = CONFIG.with_suffix(".json.tmp")
            backup_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            core.load_config(backup_path)
            backup_path.replace(CONFIG)
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

    def _use_as_i2i_source(self, path: Path | None) -> None:
        if self.working:
            messagebox.showwarning("I2I", "現在の処理が終了してから画像を指定してください")
            return
        if path is None or not path.is_file():
            messagebox.showerror("I2I", "使用する画像ファイルが見つかりません")
            return
        self._source_change_lock = True
        try:
            self.mask_image.set("")
            self.pose_image.set("")
            self._last_reference_image = ""
            self.reference_image.set(str(path))
        finally:
            self._source_change_lock = False
        self._on_reference_image_changed()
        self.workflow.set("wai_i2i_basic")
        self._update_generation_controls()
        self.tabs.select(0)
        self.prompt.focus_set()
        self.status.set("生成結果をI2Iの参照画像に設定しました")

    def _current_output_to_i2i(self) -> None:
        selected = self.images_list.curselection()
        index = selected[0] if selected else 0
        self._use_as_i2i_source(
            self.image_paths[index] if index < len(self.image_paths) else None
        )

    def _history_output_to_i2i(self) -> None:
        entry = self._one_history()
        if entry is None:
            messagebox.showinfo("I2I", "画像を1件選択してください")
            return
        self._use_as_i2i_source(entry.first_image)

    def _refresh_models(self) -> None:
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

    def _start(self, dry_run: bool) -> None:
        if self.working:
            return
        if not self._save_settings():
            return
        prompt = self.prompt.get("1.0", "end").strip()
        if not prompt:
            messagebox.showwarning("入力が必要です", "生成内容を入力してください。")
            return
        if self.model.get().strip() in ("", "SELECT_IN_GUI"):
            messagebox.showwarning("モデル未設定", "「モデルを更新」からLM Studioのモデルを選択してください。")
            return
        image = Path(self.reference_image.get()).expanduser() if self.reference_image.get() else None
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
        try:
            overrides = self._overrides()
            overrides = image_aware_overrides(
                self.config, selected, image is not None,
                overrides, self.denoise.get(), self.control_strength.get(),
            )
        except (ValueError, core.OrchestratorError) as exc:
            messagebox.showerror("生成設定エラー", str(exc))
            return
        cfg = copy.deepcopy(self.config)
        self._set_busy("解釈テスト中..." if dry_run else "生成準備中...")
        self._log("開始: " + ("解釈のみテスト" if dry_run else "画像生成") + f" / model={cfg['llm']['model']}")

        def task():
            try:
                result = core.execute(
                    cfg, CONFIG, prompt, image=image, dry_run=dry_run,
                    selected_workflow=selected, overrides=overrides,
                    progress=lambda line: self.messages.put(("progress", line)),
                    cancel_event=self.stop_event, mask_image=mask, pose_image=pose,
                    composition_image=composition,
                )
                images = []
                if not dry_run:
                    for item in output_images(result):
                        try:
                            path = save_output_image(cfg["comfyui"]["base_url"], item, result["prompt_id"])
                            images.append(path)
                        except Exception as exc:
                            self.messages.put(("progress", f"画像取得エラー: {exc}"))
                history_id = (
                    self._record_completed_generation(
                        result, images, prompt, image, mask, pose, composition,
                    )
                    if not dry_run else None
                )
                self.messages.put(("done", (result, images, history_id)))
            except Exception as exc:
                self.messages.put(("error", str(exc)))
            finally:
                self.messages.put(("idle", None))
        threading.Thread(target=task, daemon=True).start()

    def _request_cancel(self) -> None:
        self.stop_event.set()
        self.status.set("停止要求済み（ComfyUI側のジョブは中断しません）")
        self._log("処理の待機終了を要求しました。すでに投入された生成ジョブは続行します。")

    def _consume_messages(self) -> None:
        try:
            while True:
                kind, data = self.messages.get_nowait()
                if kind == "progress":
                    self._log(data)
                    self.status.set(data)
                elif kind == "check":
                    for line in data:
                        self._log(line)
                    self.status.set("接続確認が完了しました")
                elif kind == "models":
                    names = [item["key"] for item in data]
                    self.model_box.configure(values=names)
                    if self.model.get() not in names and names:
                        self.model.set(names[0])
                    self._log(f"LM Studioモデル: {len(names)}件。必要なモデルを選択して設定を保存してください。")
                    self.status.set(f"モデル一覧を更新: {len(names)}件")
                elif kind == "done":
                    result, images, history_id = data
                    if result["status"] == "dry_run":
                        self._log("解釈結果:\n" + json.dumps(result, ensure_ascii=False, indent=2))
                        self.status.set("解釈テスト完了（ComfyUI未実行）")
                    else:
                        self.image_paths = images
                        self.images_list.delete(0, "end")
                        for file in images:
                            self.images_list.insert("end", file.name)
                        if images:
                            self.images_list.selection_set(0)
                            self._display_image(images[0])
                            self.open_button.configure(state="normal")
                        self.result_info.set(
                            f"生成完了: {len(images)}画像保存 / prompt_id={result['prompt_id']}"
                        )
                        self._log("生成完了: " + json.dumps(result.get("parameters", {}), ensure_ascii=False))
                        self.status.set("画像生成完了")
                        self._refresh_history(select_id=history_id)
                        self.tabs.select(0)
                elif kind == "error":
                    self._log("ERROR: " + data)
                    self.status.set("エラー: " + data[:110])
                    messagebox.showerror("処理エラー", data)
                elif kind == "idle":
                    self.working = False
                    self.run_button.configure(state="normal")
                    self.preview_button.configure(state="normal")
                    self.cancel_button.configure(state="disabled")
                    self.progress_bar.stop()
                    self._history_selection_changed()
        except queue.Empty:
            pass
        if self.root.winfo_exists():
            self.root.after(100, self._consume_messages)

    def _show_selected_image(self, _event=None) -> None:
        selected = self.images_list.curselection()
        if selected and selected[0] < len(self.image_paths):
            self._display_image(self.image_paths[selected[0]])

    def _display_image(self, path: Path) -> None:
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
            self.image_label.configure(image="", text="プレビュー非対応の画像です。ファイルを開いてください。")
        self.result_info.set(path.name)

    def _open_image(self) -> None:
        selected = self.images_list.curselection()
        if selected and selected[0] < len(self.image_paths):
            self._open_path(self.image_paths[selected[0]])

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
        if self.working and not messagebox.askokcancel(
            "実行中", "現在の操作の進捗表示は終了します。ComfyUI側の生成ジョブは停止しません。閉じますか？"
        ):
            return
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    Application(root)
    root.mainloop()


if __name__ == "__main__":
    main()
