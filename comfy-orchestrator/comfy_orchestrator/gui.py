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
from .lmstudio import list_models, LMStudio
from .character_ui import CharacterReferenceWindow
from .file_drop import enable_native_dnd, register_file_drop
from .character_refs import (
    validate_images as validate_character_images,
    normalize_approved as normalize_character_traits,
    save_character_sheet, load_character_sheet, clear_character_sheet,
    format_evidence,
)
from .prompt_profiles import (
    DEFAULT_T2I_PROFILE, T2I_PROFILE_LABELS, T2I_LABEL_TO_PROFILE,
    DEFAULT_I2I_PROFILE, I2I_PROFILE_LABELS, I2I_LABEL_TO_PROFILE,
    DEFAULT_H3_PROFILE, H3_PROFILE_GENERAL, H3_PROFILE_LABELS, H3_LABEL_TO_PROFILE,
)
from .ime_font import install_native_ime_font, sync_native_ime_font
from .ui_theme import apply_ttk_theme, style_text_widget
from .video_preview import VideoPreview


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config.json"
EXAMPLE = ROOT / "config.example.json"
OUTPUTS = ROOT / "outputs"

# Keep the pixel dimensions authoritative: presets are just a GUI shortcut.
CUSTOM_RESOLUTION = "カスタム"
VIDEO_RESOLUTIONS = ("832 × 480", "480 × 832", "640 × 640", "1280 × 704", "704 × 1280")
VIDEO_FRAME_COUNTS = ("49", "81", "121")
HUNYUAN_RESOLUTIONS = ("848 × 480", "480 × 848", "640 × 640")
H3_RESOLUTIONS = ("864 × 480", "480 × 864", "640 × 640", "1056 × 608", "608 × 1056", "1344 × 768", "768 × 1344", "768 × 768")
H3_DURATIONS = {"約5秒 (124f)": 124, "8秒 (192f)": 192, "約10秒 (243f)": 243, "約12秒 (294f)": 294, "約15秒 (362f)": 362}
VIDEO_EXTENSIONS = frozenset({".mp4", ".webm", ".mov", ".mkv"})
IMAGE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".webp"})


def is_video_output(path: Path) -> bool:
    return path.suffix.lower() in VIDEO_EXTENSIONS


RESOLUTION_PRESETS = {
    "512 × 512（軽量プレビュー）": (512, 512),
    "768 × 768（軽量・正方形）": (768, 768),
    "1024 × 1024（標準・正方形）": (1024, 1024),
    "832 × 1216（縦長イラスト）": (832, 1216),
    "1216 × 832（横長イラスト）": (1216, 832),
    "768 × 1024（縦長 3:4）": (768, 1024),
    "1024 × 768（横長 4:3）": (1024, 768),
    "720 × 1280（縦長 9:16）": (720, 1280),
    "1280 × 720（横長 16:9）": (1280, 720),
}


def resolution_preset_label(width: str, height: str) -> str:
    """Infer the preset from editable dimensions, including partial input."""
    try:
        dimensions = (int(width), int(height))
    except (TypeError, ValueError):
        return CUSTOM_RESOLUTION
    return next(
        (label for label, size in RESOLUTION_PRESETS.items() if size == dimensions),
        CUSTOM_RESOLUTION,
    )


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
    config["llm"].setdefault("t2i_prompt_profile", DEFAULT_T2I_PROFILE)
    config["llm"].setdefault("i2i_prompt_profile", DEFAULT_I2I_PROFILE)
    config["llm"].setdefault("h3_prompt_profile", DEFAULT_H3_PROFILE)
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


def output_media(result: dict) -> list[dict]:
    """Native SaveVideo uses images + animated; also support videos/gifs metadata."""
    media = []
    seen = set()
    outputs = result.get("outputs", {})
    if not isinstance(outputs, dict):
        return media
    for node_output in outputs.values():
        if not isinstance(node_output, dict):
            continue
        for key in ("images", "videos", "gifs"):
            entries = node_output.get(key, [])
            if not isinstance(entries, list):
                continue
            for entry in entries:
                if not isinstance(entry, dict) or not isinstance(entry.get("filename"), str):
                    continue
                name = entry["filename"]
                if Path(name).suffix.lower() not in IMAGE_EXTENSIONS | VIDEO_EXTENSIONS:
                    continue
                subfolder = str(entry.get("subfolder", ""))
                kind = str(entry.get("type", "output"))
                identity = (name, subfolder, kind)
                if identity in seen:
                    continue
                seen.add(identity)
                media.append({"filename": name, "subfolder": subfolder, "type": kind})
    return media


def output_images(result: dict) -> list[dict]:
    return [m for m in output_media(result) if Path(m["filename"]).suffix.lower() in IMAGE_EXTENSIONS]


def save_output_image(base_url: str, metadata: dict, prompt_id: str) -> Path:
    """Download a bounded image or video atomically into the local outputs directory."""
    parameters = {key: metadata[key] for key in ("filename", "subfolder", "type")}
    safe_name = Path(metadata["filename"].replace("\\", "/")).name
    suffix = Path(safe_name).suffix.lower()
    if suffix not in IMAGE_EXTENSIONS | VIDEO_EXTENSIONS:
        raise core.OrchestratorError("未対応の出力形式です")
    limit = (512 if suffix in VIDEO_EXTENSIONS else 40) * 1024 * 1024
    url = base_url.rstrip("/") + "/view?" + urllib.parse.urlencode(parameters)
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    prefix = "".join(c for c in prompt_id[:16] if c.isalnum() or c in "-_") or "output"
    destination = OUTPUTS / (prefix + "_" + safe_name)
    temporary = destination.with_suffix(destination.suffix + ".part")
    total = 0
    try:
        with urllib.request.urlopen(url, timeout=90) as response, temporary.open("wb") as out:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > limit:
                    raise core.OrchestratorError("出力ファイルがサイズ上限を超えました")
                out.write(chunk)
        if total == 0:
            raise core.OrchestratorError("出力ファイルが空です")
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return destination


def resolve_generation_workflow(
    config: dict, chosen: str, has_image: bool,
    has_mask: bool = False, has_pose: bool = False,
    pose_mode: str = "skeleton",
) -> str | None:
    """Route still images automatically; video requires an explicit selection."""
    registered = config.get("workflows", {})
    if registered.get(chosen, {}).get("kind") == "i2v":
        # Keep I2V selected while the user is still choosing the first frame.
        # _start validates required inputs before contacting the model.
        return chosen
    candidates = core.compatible_workflows(
        config.get("workflows", {}),
        image=True if has_image else None,
        mask=True if has_mask else None,
        pose=True if has_pose else None,
    )
    candidates = {key: entry for key, entry in candidates.items() if entry.get("kind") not in core.VIDEO_KINDS}
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


WORKFLOW_NAMES = {
    "wai_t2i_basic": "画像生成 · T2I",
    "wai_i2i_basic": "画像編集 · I2I",
    "wai_inpaint_basic": "部分修正",
    "wai_pose_skeleton": "ポーズ参照 · 骨格",
    "wai_pose_detect": "ポーズ参照 · 画像",
    core.H3_I2V_ID: "動画生成 · MiniMax H3",
    core.WAN_I2V_ID: "動画生成 · Wan 2.2",
    core.HUNYUAN_I2V_ID: "動画生成 · Hunyuan 1.5 (480p)",
    core.QWEN_T2I_ID: "画像生成 · Qwen-Image 2512",
    core.QWEN_LIGHTNING_ID: "画像生成 · Qwen-Image 2512 (4 Steps)",
}


def workflow_display_names(config: dict) -> dict[str, str]:
    """Stable IDs for execution; readable labels for the shared form."""
    labels = {"自動": "自動"}
    for key in config.get("workflows", {}):
        label = WORKFLOW_NAMES.get(key, key)
        if label in labels.values():
            label = f"{label} ({key})"
            while label in labels.values():
                label += " "
        labels[key] = label
    return labels


def parameter_visibility(config: dict, workflow_id: str | None, custom_size: bool = False) -> dict:
    """All workflows share the same grid. Only the individual fields vary."""
    entry = config.get("workflows", {}).get(workflow_id, {})
    bindings = entry.get("bindings", {})
    kind = entry.get("kind")
    video = kind in core.VIDEO_KINDS
    h3 = workflow_id == core.H3_I2V_ID
    hunyuan = workflow_id == core.HUNYUAN_I2V_ID
    qwen = workflow_id in core.QWEN_IDS
    still_size = not video and "image" not in bindings and {"width", "height"} <= bindings.keys()
    return {
        "resolution": still_size,
        "custom_size": still_size and custom_size,
        "source_size": not video and "image" in bindings and not still_size,
        "wan": video and not h3 and not hunyuan,
        "h3": h3,
        "h3_turbo": h3,
        "h3_performance": False,
        "hunyuan": hunyuan,
        "checkpoint": workflow_id in core.SDXL_WORKFLOW_IDS,
        "qwen_steps": workflow_id == core.QWEN_T2I_ID,
        "qwen_fixed": workflow_id == core.QWEN_LIGHTNING_ID,
        "steps": "steps" in bindings and not hunyuan and not qwen,
        "cfg": "cfg" in bindings and not qwen,
        "seed": "seed" in bindings,
        "denoise": "denoise" in bindings,
        "strength": "control_strength" in bindings,
        "t2i_profile": kind == "t2i" and not qwen,
        "i2i_profile": kind in ("i2i", "inpaint"),
        "h3_profile": h3,
    }


def set_grid_visible(widget, visible: bool) -> None:
    """Avoid no-op geometry requests (including while parent is unmapped)."""
    if (widget.winfo_manager() == "grid") != visible:
        widget.grid() if visible else widget.grid_remove()


def reference_visibility(*, video: bool, expanded: bool, reference: bool,
                         mask: bool, pose: bool, composition: bool) -> dict:
    """Never hide selected references, so incompatible inputs can be cleared."""
    return {
        "mask": mask or (reference and not video),
        "pose": pose or (expanded and not video),
        "composition": not video and (composition or expanded),
        "vision": not video and (reference or pose or composition),
    }


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
    if workflow_id == core.H3_I2V_ID:
        result.update({key: overrides[key] for key in core.H3_OPTION_KEYS if key in overrides})
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


def history_request_text(entry: HistoryEntry | None) -> str | None:
    """Return the original editable request, never invented text or generated tags."""
    if entry is None or entry.legacy:
        return None
    text = entry.request_text
    return text if isinstance(text, str) and text.strip() else None


def history_prompt_details(entry: HistoryEntry | None) -> dict | None:
    """Expose only the literal prompts and metadata stored for this exact run.

    Never call an LLM, infer a missing negative prompt or consult the latest run.
    Pre-history imported images have no known generation parameters.
    """
    if entry is None or entry.legacy or not isinstance(entry.parameters, dict):
        return None
    positive = entry.parameters.get("positive_prompt")
    if not isinstance(positive, str) or not positive.strip():
        return None
    negative = entry.parameters.get("negative_prompt")
    return {
        "workflow_id": entry.workflow_id,
        "kind": entry.kind,
        "profile": entry.prompt_profile,
        "request_text": entry.request_text,
        "positive_prompt": positive,
        "negative_prompt": negative if isinstance(negative, str) else None,
        "seed": entry.parameters.get("seed"),
        "steps": entry.parameters.get("steps"),
        "cfg": entry.parameters.get("cfg"),
        "denoise": entry.parameters.get("denoise"),
        "character_traits": entry.character_traits,
        "character_analysis": entry.character_analysis,
        "character_references": entry.character_references,
    }


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
        self._history_refresh_running = False
        self._history_refresh_pending: tuple[str | None, bool] | None = None
        self._history_selection_key = None
        self._history_preview_key = None
        self._generation_ui_key = None
        self._form_width = None
        self._form_bounds = None
        self.history_preview_photo: tk.PhotoImage | None = None
        self.latest_composition_report = ""
        self.latest_prompt_plan: dict | None = None
        self.latest_prompt_profile: str | None = None
        self.latest_request_text: str | None = None
        self.latest_character_traits: str | None = None
        self.latest_character_analysis: dict | None = None
        self.latest_character_references: tuple[Path, ...] = ()
        self.character_references, self.character_analysis, self.character_traits = (
            load_character_sheet(ROOT)
        )
        self.character_analysis_running = False
        self.character_dialog: CharacterReferenceWindow | None = None
        self._variables()
        self._build()
        self._refresh_generation_models()
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
        self.workflow_names = workflow_display_names(self.config)
        self.workflow_choice = tk.StringVar(value=self.workflow_names.get(self.workflow.get(), "自動"))
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
        model_key = options.get("h3_model", "int8")
        turbo_key = options.get("h3_turbo", "off")
        self.h3_model = tk.StringVar(value=core.h3_model_label(model_key))
        self.generation_inventory = None
        self.checkpoint_model = tk.StringVar(value=options.get("checkpoint_model", core.DEFAULT_SDXL_CHECKPOINT))
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
        self.status = tk.StringVar(value="準備完了")
        self.result_info = tk.StringVar(value="")
        self.character_status = tk.StringVar(
            value=f"キャラ参照 · {len(self.character_references)}枚"
            if self.character_traits else "キャラ参照"
        )

    def _build(self) -> None:
        colors = apply_ttk_theme(self.root, self.dark_mode.get())

        layout = ttk.Frame(self.root, padding=10)
        layout.pack(fill="both", expand=True)
        self.topbar = ttk.Frame(layout)
        self.topbar.pack(fill="x")
        ttk.Label(self.topbar, text="LLM").pack(side="left", padx=(0, 6))
        self.model_box = ttk.Combobox(self.topbar, textvariable=self.model, state="normal", width=18)
        self.model_box.pack(side="left", fill="x", expand=True)
        ttk.Button(self.topbar, text="モデル更新", command=self._refresh_models).pack(side="left", padx=(6, 0))
        self.connection_toggle = ttk.Button(self.topbar, text="設定 ▸", command=self._toggle_connection_settings)
        self.connection_toggle.pack(side="left", padx=(6, 0))

        self.connection_visible = False
        self.connection_panel = connection = ttk.Frame(layout, padding=(0, 6, 0, 0))
        connection.columnconfigure(1, weight=1)
        ttk.Label(connection, text="LM Studio").grid(row=0, column=0, sticky="w", padx=(0, 7), pady=3)
        ttk.Entry(connection, textvariable=self.llm_url).grid(row=0, column=1, sticky="ew", pady=3)
        ttk.Label(connection, text="ComfyUI").grid(row=1, column=0, sticky="w", padx=(0, 7), pady=3)
        ttk.Entry(connection, textvariable=self.comfy_url).grid(row=1, column=1, sticky="ew", pady=3)
        options_frame = ttk.Frame(connection)
        options_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(4, 2))
        ttk.Checkbutton(options_frame, text="解釈後にLLMを解放",
                        variable=self.unload_llm).grid(row=0, column=0, sticky="w", padx=(0, 12))
        ttk.Checkbutton(options_frame, text="解釈前にComfyUIを解放",
                        variable=self.free_comfy).grid(row=0, column=1, sticky="w")
        encoder_row = ttk.Frame(connection)
        encoder_row.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(2, 2))
        ttk.Label(encoder_row, text="H3エンコーダー").pack(side="left", padx=(0, 6))
        ttk.Combobox(encoder_row, textvariable=self.h3_encoder_model,
                     values=tuple(core.H3_ENCODER_LABELS.values()), state="readonly", width=18).pack(side="left")
        ttk.Checkbutton(encoder_row, text="CPU実行", variable=self.h3_encoder_cpu).pack(side="left", padx=(10, 0))
        settings_actions = ttk.Frame(connection)
        settings_actions.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(4, 0))
        ttk.Checkbutton(settings_actions, text="ダーク表示", variable=self.dark_mode,
                        command=self._switch_theme).pack(side="left")
        ttk.Button(settings_actions, text="保存", command=self._save_settings).pack(side="right")
        ttk.Button(settings_actions, text="接続確認", command=self._check_connections).pack(side="right", padx=(0, 6))
        self.free_memory_button = ttk.Button(settings_actions, text="生成モデル解放", command=self._release_comfy_memory)
        self.free_memory_button.pack(side="right", padx=(0, 6))

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

        prompt_panel = ttk.LabelFrame(left, text="生成", padding=8, style="Section.TLabelframe")
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

        # One shared work surface: mode, prompt, references, parameters, actions.
        workflow_row = ttk.Frame(self.options_form)
        workflow_row.pack(fill="x", pady=(0, 8))
        ttk.Label(workflow_row, text="ワークフロー").pack(side="left", padx=(0, 6))
        self.workflow_box = ttk.Combobox(
            workflow_row, textvariable=self.workflow_choice,
            values=tuple(self.workflow_names.values()), state="readonly", width=18,
        )
        self.workflow_box.pack(side="left", fill="x", expand=True)
        self.workflow_box.bind("<<ComboboxSelected>>", self._on_workflow_choice)

        editor_toolbar = ttk.Frame(self.options_form)
        editor_toolbar.pack(fill="x", pady=(0, 4))
        ttk.Label(editor_toolbar, text="プロンプト", style="FieldHeading.TLabel").pack(side="left")
        ttk.Button(editor_toolbar, text="A+", width=3, command=lambda: self._change_editor_font(1),
                   style="Compact.TButton").pack(side="right", padx=(4, 0))
        ttk.Button(editor_toolbar, text="A−", width=3, command=lambda: self._change_editor_font(-1),
                   style="Compact.TButton").pack(side="right")
        self.prompt = scrolledtext.ScrolledText(
            self.options_form, height=6, wrap="word",
            font=("Meiryo UI", self.editor_font_size.get()),
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

        self.reference_row, _ = input_row(0, "参照画像", self.reference_image, self._browse_image, editable=True)
        self.mask_row, self.mask_button = input_row(1, "修正範囲", self.mask_image, self._edit_mask, button_text="範囲を塗る")

        self.reference_tools = reference_tools = ttk.Frame(inputs)
        reference_tools.grid(row=2, column=0, sticky="ew", pady=(0, 4))
        self.extra_button = ttk.Button(reference_tools, text="追加参照 ▸",
                                       command=self._toggle_extra_references, style="Compact.TButton")
        self.extra_button.pack(side="left")
        self.character_button = ttk.Button(reference_tools, textvariable=self.character_status,
                                           command=self._open_character_references, style="Compact.TButton")
        self.character_button.pack(side="left", padx=(6, 0))
        for target in (reference_tools, self.character_button):
            register_file_drop(target, self._drop_character_files)
        self.composition_row, _ = input_row(3, "構図参考", self.composition_image, self._browse_composition)
        self.pose_row, _ = input_row(4, "ポーズ画像", self.pose_image, self._browse_pose)
        self.pose_modes = ttk.Frame(inputs)
        self.pose_modes.grid(row=5, column=0, sticky="ew", pady=(0, 5))
        ttk.Radiobutton(self.pose_modes, text="骨格PNG", variable=self.pose_mode,
                        value="skeleton", command=self._on_pose_image_changed).pack(side="left", padx=(0, 14))
        ttk.Radiobutton(self.pose_modes, text="画像から骨格検出", variable=self.pose_mode,
                        value="photo", command=self._on_pose_image_changed).pack(side="left")
        self.vision_row = ttk.Frame(inputs)
        self.vision_row.grid(row=6, column=0, sticky="ew", pady=(0, 4))
        self.vision_checkbox = ttk.Checkbutton(self.vision_row, text="LLMで画像を解析",
                                              variable=self.vision_composition)
        self.vision_checkbox.pack(side="left")
        ttk.Button(self.vision_row, text="認識結果", command=self._show_composition_report,
                   style="Compact.TButton").pack(side="right")
        self.reference_image.trace_add("write", lambda *_args: self._on_reference_image_changed())
        self.mask_image.trace_add("write", lambda *_args: self._on_mask_image_changed())
        self.pose_image.trace_add("write", lambda *_args: self._on_pose_image_changed())
        self.composition_image.trace_add("write", self._on_composition_image_changed)

        settings = ttk.Frame(self.options_form)
        settings.pack(fill="x", pady=(0, 4))
        for col in (1, 3):
            settings.columnconfigure(col, weight=1)
        ttk.Separator(settings).grid(row=0, column=0, columnspan=4, sticky="ew", pady=(0, 8))
        ttk.Label(settings, text="生成設定", style="FieldHeading.TLabel").grid(
            row=1, column=0, columnspan=4, sticky="w", pady=(0, 6),
        )
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
        self.resolution_box = field(2, 0, "解像度", self.resolution_preset, "resolution",
                                    choices=(*RESOLUTION_PRESETS, CUSTOM_RESOLUTION), span=3, width=18)
        self.resolution_box.bind("<<ComboboxSelected>>", self._apply_resolution_preset)
        self.width_entry = field(3, 0, "幅", self.width, "custom_size")
        self.height_entry = field(3, 2, "高さ", self.height, "custom_size")
        source_title = ttk.Label(settings, text="解像度")
        source_title.grid(row=2, column=0, sticky="w", padx=(0, 6), pady=3)
        source_value = ttk.Label(settings, text="元画像サイズ")
        source_value.grid(row=2, column=1, columnspan=3, sticky="w", pady=3)
        self.parameter_widgets["source_size"] = [source_title, source_value]

        field(2, 0, "解像度", self.video_size, "wan", choices=VIDEO_RESOLUTIONS, span=3, width=18)
        field(3, 0, "フレーム数", self.video_frames, "wan", choices=VIDEO_FRAME_COUNTS)
        field(3, 2, "FPS", self.video_fps, "wan", choices=("16", "24", "30"), width=5)
        field(2, 0, "解像度", self.h3_size, "h3", choices=H3_RESOLUTIONS, span=3, width=18)
        field(3, 0, "長さ (24fps)", self.h3_duration, "h3", choices=tuple(H3_DURATIONS), span=3, width=18)

        field(2, 0, "解像度", self.hunyuan_size, "hunyuan", choices=HUNYUAN_RESOLUTIONS, span=3, width=18)
        field(3, 0, "フレーム数 (24fps)", self.hunyuan_frames, "hunyuan",
              choices=VIDEO_FRAME_COUNTS, span=3)
        field(4, 0, "Steps", self.hunyuan_steps, "hunyuan", choices=("8", "12"), span=3)
        self.steps_entry = field(4, 0, "Steps", self.steps, "steps")
        self.cfg_entry = field(4, 2, "CFG", self.cfg, "cfg")
        field(4, 0, "Steps", self.qwen_steps, "qwen_steps")
        field(4, 2, "CFG", self.qwen_cfg, "qwen_steps")
        field(4, 0, "Steps", self.qwen_fixed_steps, "qwen_fixed").configure(state="readonly")
        field(4, 2, "CFG", self.qwen_fixed_cfg, "qwen_fixed").configure(state="readonly")
        self.seed_entry = field(5, 0, "Seed", self.seed, "seed", span=2)
        self.random_seed_button = ttk.Button(settings, text="ランダム", style="Compact.TButton",
                                             command=lambda: self.seed.set(""))
        self.random_seed_button.grid(row=5, column=3, sticky="ew", pady=3)
        self.parameter_widgets["seed"].append(self.random_seed_button)
        self.denoise_entry = field(6, 0, "Denoise", self.denoise, "denoise", span=3)
        self.strength_entry = field(6, 0, "ポーズ強度", self.control_strength, "strength", span=3)
        self.t2i_profile_box = field(7, 0, "プロンプト方式", self.t2i_profile, "t2i_profile",
                                     choices=tuple(T2I_PROFILE_LABELS.values()), span=3, width=18)
        self.i2i_profile_box = field(7, 0, "プロンプト方式", self.i2i_profile, "i2i_profile",
                                     choices=tuple(I2I_PROFILE_LABELS.values()), span=3, width=18)
        self.h3_profile_box = field(7, 0, "プロンプト方式", self.h3_profile, "h3_profile",
                                    choices=tuple(H3_PROFILE_LABELS.values()), span=3, width=18)
        self.checkpoint_box = field(8, 0, "モデル", self.checkpoint_model, "checkpoint",
                                    choices=(self.checkpoint_model.get(),), span=3, width=18)
        self.checkpoint_box.bind("<<ComboboxSelected>>", self._sync_h3_steps)
        self.h3_model_box = field(8, 0, "モデル", self.h3_model, "h3",
                                  choices=tuple(dict.fromkeys((*core.H3_MODEL_LABELS.values(), self.h3_model.get()))),
                                  span=3, width=18)
        self.h3_turbo_box = field(9, 0, "追加Turbo", self.h3_turbo, "h3_turbo",
                                  choices=tuple(core.H3_TURBO_LABELS.values()), span=3, width=18)
        self.h3_performance_box = field(9, 0, "高速化", self.h3_performance, "h3_performance",
                                        choices=tuple(core.H3_PERFORMANCE_LABELS.values()), span=3, width=18)
        self.h3_performance_box.bind("<<ComboboxSelected>>", self._on_h3_performance_choice)
        self.h3_model_box.bind("<<ComboboxSelected>>", self._on_h3_model_choice)
        self.h3_turbo_box.bind("<<ComboboxSelected>>", self._sync_h3_steps)
        for widgets in self.parameter_widgets.values():
            for widget in widgets:
                widget.grid_remove()

        self.run_button = ttk.Button(
            action_row, text="画像生成", style="Run.TButton", command=lambda: self._start(False)
        )
        self.run_button.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.preview_button = ttk.Button(action_row, text="解釈テスト", command=lambda: self._start(True))
        self.preview_button.pack(side="left", padx=(0, 6))
        self.cancel_button = ttk.Button(
            action_row, text="待機中止", command=self._request_cancel, state="disabled"
        )
        self.cancel_button.pack(side="left")

        self.tabs = ttk.Notebook(right)
        self.tabs.pack(fill="both", expand=True)
        preview_panel = ttk.Frame(self.tabs, padding=8)
        self.tabs.add(preview_panel, text="結果")
        self.result_panel = preview_panel
        history_panel = ttk.Frame(self.tabs, padding=8)
        self.tabs.add(history_panel, text="履歴")
        self.history_panel = history_panel

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
        self.image_label = ttk.Label(preview_panel, text="生成結果なし", anchor="center")
        self.image_label.pack(fill="both", expand=True)
        self.result_video = VideoPreview(preview_panel, height=240)
        ttk.Label(preview_meta, textvariable=self.result_info, wraplength=350).pack(anchor="w", pady=(3, 4))
        self.images_list = tk.Listbox(
            preview_meta, height=2, exportselection=False, font=("Meiryo UI", 9),
        )
        # Show a file chooser only when multiple outputs exist.
        self.images_list.bind("<<ListboxSelect>>", self._show_selected_image)
        row = ttk.Frame(preview_actions)
        row.pack(fill="x")
        for col in range(3):
            row.columnconfigure(col, weight=1)
        self.open_button = ttk.Button(row, text="開く", command=self._open_image, state="disabled")
        self.open_button.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(row, text="保存先", command=self._open_outputs).grid(row=0, column=1, sticky="ew", padx=(0, 4))
        self.result_prompt_button = ttk.Button(row, text="プロンプト", command=self._show_prompt_preview, state="disabled")
        self.result_prompt_button.grid(row=0, column=2, sticky="ew")
        self.result_tools = ttk.Frame(preview_actions)
        self.result_tools.columnconfigure(0, weight=1)
        self.result_tools.columnconfigure(1, weight=1)
        ttk.Button(self.result_tools, text="I2Iに使用", command=self._current_output_to_i2i).grid(
            row=0, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(self.result_tools, text="I2Vに使用", command=self._current_output_to_i2v).grid(
            row=0, column=1, sticky="ew")

        history_columns = ("date", "workflow", "seed")
        table_holder = ttk.Frame(history_panel)
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
        self.history_table.bind("<<TreeviewSelect>>", self._history_selection_changed)
        self.history_table.bind("<Double-1>", lambda _e: self._restore_selected_history())

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
        self.history_open_button = ttk.Button(first_row, text="開く", command=self._open_history_output, style="Compact.TButton")
        self.history_open_button.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self.history_request_button = ttk.Button(first_row, text="プロンプト復元",
            command=self._restore_selected_history_request, state="disabled", style="Compact.TButton")
        self.history_request_button.grid(row=0, column=1, sticky="ew", padx=(0, 4))
        self.history_restore_button = ttk.Button(first_row, text="設定復元", command=self._restore_selected_history, style="Compact.TButton")
        self.history_restore_button.grid(row=0, column=2, sticky="ew", padx=(0, 4))
        self.history_compare_button = ttk.Button(first_row, text="比較", command=self._compare_selected_history, style="Compact.TButton")
        self.history_compare_button.grid(row=0, column=3, sticky="ew")
        second_row = ttk.Frame(history_actions)
        second_row.pack(fill="x")
        for col in range(4):
            second_row.columnconfigure(col, weight=1)
        self.same_seed_button = ttk.Button(second_row, text="同Seed再生成",
            command=lambda: self._regenerate_selected_history(new_seed=False), state="disabled", style="Compact.TButton")
        self.same_seed_button.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self.new_seed_button = ttk.Button(second_row, text="別Seed再生成",
            command=lambda: self._regenerate_selected_history(new_seed=True), state="disabled", style="Compact.TButton")
        self.new_seed_button.grid(row=0, column=1, sticky="ew", padx=(0, 4))
        self.history_prompt_button = ttk.Button(second_row, text="詳細", command=self._show_selected_history_prompt, style="Compact.TButton")
        self.history_prompt_button.grid(row=0, column=2, sticky="ew", padx=(0, 4))
        ttk.Button(second_row, text="更新", command=self._refresh_history, style="Compact.TButton").grid(row=0, column=3, sticky="ew")
        self.history_tools = ttk.Frame(history_actions)
        self.history_tools.columnconfigure(0, weight=1)
        self.history_tools.columnconfigure(1, weight=1)
        ttk.Button(self.history_tools, text="I2Iに使用", command=self._history_output_to_i2i, style="Compact.TButton").grid(
            row=0, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(self.history_tools, text="I2Vに使用", command=self._history_output_to_i2v, style="Compact.TButton").grid(
            row=0, column=1, sticky="ew")

        self.tabs.bind("<<NotebookTabChanged>>", self._output_tab_changed)
        self._switch_theme()
        self._update_generation_controls()
        install_native_ime_font(self.prompt)
        self._log("GUI起動。LM StudioのDeveloper画面でLocal Serverを起動してください。")
        self._log("設定は comfy-orchestrator/config.json に保存され、Gitには含まれません。")

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

    def _toggle_connection_settings(self) -> None:
        if self.connection_visible:
            self.connection_panel.pack_forget()
        else:
            self.connection_panel.pack(fill="x", after=self.topbar)
        self.connection_visible = not self.connection_visible
        self.connection_toggle.configure(text="設定 ▾" if self.connection_visible else "設定 ▸")

    def _toggle_extra_references(self) -> None:
        self._extra_references = not self._extra_references
        self._update_generation_controls()

    def _sync_workflow_choice(self, *_args) -> None:
        label = self.workflow_names.get(self.workflow.get(), self.workflow.get())
        if self.workflow_choice.get() != label:
            self.workflow_choice.set(label)

    def _on_workflow_choice(self, _event=None) -> None:
        by_label = {label: key for key, label in self.workflow_names.items()}
        self.workflow.set(by_label.get(self.workflow_choice.get(), "自動"))
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
        if core.h3_hybrid_filename(model) is not None and hasattr(self, "h3_performance"):
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

    def _on_h3_model_choice(self, _event=None) -> None:
        # Different merged/quantized weights have not been validated with Turbo.
        # Start their comparison without an additional LoRA; user may opt in.
        if self._h3_choices()["h3_model"] not in ("int8", "w4a8"):
            self.h3_turbo.set("OFF")
        self._sync_h3_steps()

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
        if hasattr(self, "parameter_widgets"):
            for widget in self.parameter_widgets.get("h3_turbo", ()):
                set_grid_visible(widget, is_h3 and not hybrid)
            for widget in self.parameter_widgets.get("h3_performance", ()):
                set_grid_visible(widget, hybrid)
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
        if workflow_id and self.workflow.get() not in ("自動", workflow_id):
            self.workflow.set(workflow_id)
        entry = self.config["workflows"].get(workflow_id, {})
        is_video = entry.get("kind") in core.VIDEO_KINDS
        state = parameter_visibility(
            self.config, workflow_id,
            getattr(self, "_custom_size_editing", False)
            or (hasattr(self, "resolution_preset") and self.resolution_preset.get() == CUSTOM_RESOLUTION),
        )
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
        ui_key = (workflow_id, tuple(state.items()), tuple(refs.items()), expanded,
                  reference, pose, composition)
        if getattr(self, "_generation_ui_key", None) == ui_key:
            return
        self._generation_ui_key = ui_key
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
        if hasattr(self, "run_button"):
            self.run_button.configure(text="動画生成" if is_video else "画像生成")
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
        """Read SQLite and enumerate files off the Tk event loop."""
        scan_legacy = scan_legacy and not self.working
        if self._history_refresh_running:
            previous = self._history_refresh_pending
            self._history_refresh_pending = (
                select_id if select_id is not None else (previous[0] if previous else None),
                scan_legacy or bool(previous and previous[1]),
            )
            return
        self._history_refresh_running = True
        store = self.history_store
        messages = self.messages

        def task():
            try:
                if scan_legacy:
                    store.import_legacy_outputs(limit=500)
                entries = store.list_entries(limit=500)
                messages.put(("history_loaded", (entries, select_id, None)))
            except Exception as exc:
                messages.put(("history_loaded", (None, select_id, str(exc))))

        threading.Thread(target=task, daemon=True).start()

    def _finish_history_refresh(self, entries, select_id, error) -> None:
        self._history_refresh_running = False
        if error is not None:
            self._log("履歴の読み込みに失敗: " + error)
        pending = self._history_refresh_pending
        self._history_refresh_pending = None
        if pending is not None:
            # A completion/refresh arrived during the read. Fetch the newer
            # snapshot rather than rendering two consecutive full snapshots.
            self._refresh_history(
                select_id=pending[0] if pending[0] is not None else select_id,
                scan_legacy=pending[1],
            )
        elif entries is not None:
            self._apply_history_entries(entries, select_id)

    @staticmethod
    def _history_row(entry: HistoryEntry) -> tuple:
        short = entry.request_text.replace("\n", " ").strip()[:80]
        timestamp = entry.created_at
        try:
            from datetime import datetime
            timestamp = datetime.fromisoformat(timestamp).astimezone().strftime("%m/%d %H:%M")
        except (ValueError, OverflowError):
            timestamp = timestamp[:16]
        return (short or "(プロンプトなし)",
                (timestamp, entry.kind.upper(), str(entry.parameters.get("seed", "—"))))

    def _apply_history_entries(self, entries, select_id: str | None = None) -> None:
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
            title, values = self._history_row(entry)
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

    def _output_tab_changed(self, _event=None) -> None:
        # Only a visible pane may own an active decoder.
        if self.tabs.select() != str(self.result_panel):
            self.result_video.stop()
        if self.tabs.select() != str(self.history_panel):
            self.history_video.stop()
        self._history_selection_changed()

    def _set_result_video(self, path: Path | None) -> None:
        if not hasattr(self, "result_video"):
            return
        self.result_video.set_source(path)
        if path is not None:
            self.image_label.pack_forget()
            self.result_video.pack(fill="both", expand=True)
        else:
            self.result_video.pack_forget()
            if not self.image_label.winfo_manager():
                self.image_label.pack(fill="both", expand=True)

    def _set_history_video(self, path: Path | None) -> None:
        if not hasattr(self, "history_video"):
            return
        self.history_video.set_source(path)
        if path is not None:
            self.history_image.pack_forget()
            self.history_video.pack(fill="x", pady=(0, 4))
        else:
            self.history_video.pack_forget()
            if not self.history_image.winfo_manager():
                self.history_image.pack(fill="x", pady=(0, 4))

    def _history_selection_changed(self, _event=None) -> None:
        # The Result tab does not need hidden history thumbnails or file checks.
        if hasattr(self, "history_panel") and self.tabs.select() != str(self.history_panel):
            return
        selected = self._selected_history()
        selection_key = (tuple(entry.id for entry in selected), self.working)
        if getattr(self, "_history_selection_key", None) == selection_key:
            return
        self._history_selection_key = selection_key
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

        if hasattr(self, "history_open_button"):
            single = selected[0] if len(selected) == 1 else None
            output = single.first_image if single else None
            exists = bool(output and output.is_file())
            still = exists and not is_video_output(output)
            restorable = bool(single and not single.legacy and single.workflow_id in self.config["workflows"] and not self.working)
            comparable = ((len(selected) == 2 and all(e.first_image and e.first_image.is_file() and not is_video_output(e.first_image) for e in selected))
                          or bool(still and single.reference_image and single.reference_image.is_file()))
            for button, enabled in (
                (self.history_open_button, exists), (self.history_restore_button, restorable),
                (self.history_compare_button, comparable),
                (self.history_prompt_button, bool(single and history_prompt_details(single))),
            ):
                button.configure(state="normal" if enabled else "disabled")
            if hasattr(self, "history_request_button"):
                self.history_request_button.configure(
                    state="normal" if history_request_text(single) is not None and not self.working else "disabled"
                )
            if still and not self.working:
                self.history_tools.pack(fill="x", pady=(4, 0))
            else:
                self.history_tools.pack_forget()
        if not selected:
            if hasattr(self, "history_video"):
                self._set_history_video(None)
            self._history_preview_key = None
            self.history_details.set("")
            self.history_image.configure(image="", text="")
            self.history_preview_photo = None
            return
        if len(selected) > 1:
            if hasattr(self, "history_video"):
                self._set_history_video(None)
            self._history_preview_key = None
            self.history_details.set(f"{len(selected)}件選択中")
            self.history_image.configure(image="", text="")
            self.history_preview_photo = None
            return

        entry = selected[0]
        p = entry.parameters
        if entry.kind == "t2i":
            policy_label = T2I_PROFILE_LABELS.get(
                entry.prompt_profile, entry.prompt_profile or "記録なし"
            )
        elif entry.kind in ("i2i", "inpaint"):
            policy_label = I2I_PROFILE_LABELS.get(
                entry.prompt_profile, entry.prompt_profile or "記録なし"
            )
        elif entry.workflow_id == core.H3_I2V_ID:
            policy_label = H3_PROFILE_LABELS.get(
                entry.prompt_profile, entry.prompt_profile or "記録なし"
            )
        else:
            policy_label = None
        details = [WORKFLOW_NAMES.get(entry.workflow_id, entry.workflow_id)]
        if "width" in p and "height" in p:
            details.append(f"{p['width']}×{p['height']}")
        if entry.kind in core.VIDEO_KINDS and isinstance(p.get("fps"), (int, float)) and p["fps"] > 0 and isinstance(p.get("frames"), int):
            details.append(f"{p['frames'] / p['fps']:.1f}秒")
        if "steps" in p:
            details.append(f"{p['steps']} steps")
        if "checkpoint_model" in p:
            details.append(Path(p["checkpoint_model"].replace("\\", "/")).stem)
        if entry.workflow_id == core.H3_I2V_ID and "h3_model" in p:
            details.append(core.h3_model_label(p["h3_model"]))
            turbo = core.H3_TURBO_LABELS.get(p.get("h3_turbo", "off"), "")
            if turbo and turbo != "OFF":
                details.append("Turbo " + turbo)
        if policy_label:
            details.append(policy_label)
        if entry.legacy:
            details = ["旧履歴"]
        self.history_details.set("  ·  ".join(details))
        image = entry.first_image
        exists = image is not None and image.is_file()
        preview_key = (entry.id, image, exists)
        if getattr(self, "_history_preview_key", None) == preview_key:
            return
        self._history_preview_key = preview_key
        if hasattr(self, "history_video"):
            self._set_history_video(image if exists and is_video_output(image) else None)
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
        video_entry = entry.kind in core.VIDEO_KINDS
        if entry.workflow_id in core.SDXL_WORKFLOW_IDS and hasattr(self, "checkpoint_model"):
            self.checkpoint_model.set(entry.parameters.get("checkpoint_model", core.DEFAULT_SDXL_CHECKPOINT))
        if entry.workflow_id in core.QWEN_IDS and hasattr(self, "qwen_steps"):
            if entry.workflow_id == core.QWEN_T2I_ID:
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
            self.character_status.set(
                f"確定: {len(entry.character_references)}枚"
                if self.character_traits else "キャラ参照"
            )
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
        self.status.set("設定を復元しました")
        self._log(f"履歴の設定を復元: {entry.workflow_id} / Seed={entry.parameters.get('seed', '不明')}")
        self.prompt.focus_set()

    def _compare_selected_history(self) -> None:
        entries = self._selected_history()
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

    def _record_completed_generation(
        self, result: dict, images: list[Path], request_text: str,
        source_image: Path | None, mask_image: Path | None = None,
        pose_image: Path | None = None,
        composition_image: Path | None = None,
        prompt_profile: str | None = None,
        character_references: tuple[Path, ...] = (),
        character_traits: str | None = None,
        character_analysis: dict | None = None,
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
                prompt_profile=prompt_profile,
                character_references=character_references,
                character_traits=character_traits,
                character_analysis=character_analysis,
            )
            return entry.id
        except (HistoryError, OSError, ValueError, sqlite3.Error) as exc:
            self.messages.put(("progress", f"履歴保存に失敗しました（画像は保持）: {exc}"))
            return None

    def _set_busy(self, label: str) -> None:
        self.stop_event.clear()
        self.working = True
        for name in ("result_video", "history_video"):
            if hasattr(self, name):
                getattr(self, name).set_enabled(False)
        self.run_button.configure(state="disabled")
        self.preview_button.configure(state="disabled")
        self.cancel_button.configure(state="normal")
        if hasattr(self, "free_memory_button"):
            self.free_memory_button.configure(state="disabled")
        self.same_seed_button.configure(state="disabled")
        self.new_seed_button.configure(state="disabled")
        if hasattr(self, "history_request_button"):
            self.history_request_button.configure(state="disabled")
        if hasattr(self, "history_restore_button"):
            self.history_restore_button.configure(state="disabled")
            self.history_tools.pack_forget()
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
        self.latest_prompt_profile = entry.prompt_profile
        self.latest_request_text = entry.request_text
        self.latest_character_traits = entry.character_traits
        self.latest_character_analysis = entry.character_analysis
        self.latest_character_references = entry.character_references
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
                for item in output_media(result):
                    try:
                        images.append(
                            save_output_image(
                                cfg["comfyui"]["base_url"], item, result["prompt_id"]
                            )
                        )
                    except Exception as exc:
                        self.messages.put(("progress", f"出力取得エラー: {exc}"))
                if entry.kind in core.VIDEO_KINDS and not any(is_video_output(p) for p in images):
                    raise core.OrchestratorError("動画を取得できません。ComfyUIのoutput/videoを確認してください")
                history_id = self._record_completed_generation(
                    result, images, entry.request_text, entry.reference_image,
                    entry.mask_image, entry.pose_image,
                    entry.composition_image if entry.composition_image
                    and entry.composition_image.is_file() else None,
                    entry.prompt_profile,
                    character_references=entry.character_references
                    if all(p.is_file() for p in entry.character_references) else (),
                    character_traits=entry.character_traits
                    if all(p.is_file() for p in entry.character_references) else None,
                    character_analysis=entry.character_analysis
                    if all(p.is_file() for p in entry.character_references) else None,
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
            **opts,
            "workflow": self.workflow.get(),
            "dark_mode": self.dark_mode.get(),
            "font_size": self.editor_font_size.get(),
        }
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
                     "checkpoint_model", "qwen_steps", "qwen_cfg"):
            if hasattr(self, name):
                config["ui"][name] = getattr(self, name).get()
            elif name in self.config.get("ui", {}):
                config["ui"][name] = self.config["ui"][name]
        return config

    def _overrides(self) -> dict:
        # Still-image dimensions and H3's unused CFG should not block a job
        # merely because an earlier edit left a hidden entry unfinished.
        entry = {}
        if hasattr(self, "parameter_widgets"):
            entry = self.config.get("workflows", {}).get(self._active_workflow(), {})
        bindings = entry.get("bindings", {})
        video = entry.get("kind") in core.VIDEO_KINDS
        previous = self.config.get("ui", {}) if entry else {}
        values = {}
        for name, variable, parse, default in (
            ("width", self.width, int, 768),
            ("height", self.height, int, 768),
            ("steps", self.steps, int, 20),
            ("cfg", self.cfg, float, 5.0),
        ):
            try:
                value = parse(variable.get())
                core.check_param(name, value)
            except (ValueError, core.OrchestratorError):
                separate_qwen = entry.get("kind") == "t2i" and self._active_workflow() in core.QWEN_IDS and name in ("steps", "cfg")
                separate_video_steps = name == "steps" and (
                    (hasattr(self, "h3_steps") and self._active_workflow() == core.H3_I2V_ID)
                    or (hasattr(self, "hunyuan_steps") and self._active_workflow() == core.HUNYUAN_I2V_ID)
                )
                if not entry or (name in bindings and not (video and name in ("width", "height")) and not separate_video_steps and not separate_qwen):
                    raise
                value = previous.get(name, default)
                try:
                    core.check_param(name, value)
                except core.OrchestratorError:
                    value = default
            values[name] = value
        if self.seed.get().strip():
            values["seed"] = int(self.seed.get().strip())
            core.check_param("seed", values["seed"])
        return values

    def _video_overrides(self) -> dict:
        width, height = (int(part.strip()) for part in self.video_size.get().split("×"))
        values = {
            "width": width, "height": height,
            "frames": int(self.video_frames.get()), "fps": int(self.video_fps.get()),
            "steps": int(self.steps.get()), "cfg": float(self.cfg.get()),
        }
        if self.seed.get().strip():
            values["seed"] = int(self.seed.get().strip())
        for name, value in values.items():
            core.check_param(name, value)
        core.validate_wan_video_parameters(values)
        return values

    def _qwen_overrides(self, workflow_id: str) -> dict:
        fast = workflow_id == core.QWEN_LIGHTNING_ID
        values = {"width": int(self.width.get()), "height": int(self.height.get()),
                  "steps": 4 if fast else int(self.qwen_steps.get()),
                  "cfg": 1 if fast else float(self.qwen_cfg.get())}
        if self.seed.get().strip():
            values["seed"] = int(self.seed.get().strip())
        for name, value in values.items():
            core.check_param(name, value)
        if values["width"] % 16 or values["height"] % 16:
            raise core.OrchestratorError("Qwen-Imageの幅・高さは16の倍数にしてください")
        return values

    def _hunyuan_overrides(self) -> dict:
        width, height = (int(part.strip()) for part in self.hunyuan_size.get().split("×"))
        values = {"width": width, "height": height, "frames": int(self.hunyuan_frames.get()),
                  "fps": 24, "steps": int(self.hunyuan_steps.get())}
        if self.seed.get().strip():
            values["seed"] = int(self.seed.get().strip())
        for name, value in values.items():
            core.check_param(name, value)
        core.validate_hunyuan_video_parameters(values)
        return values

    def _h3_overrides(self) -> dict:
        width, height = (int(part.strip()) for part in self.h3_size.get().split("×"))
        label = self.h3_duration.get()
        frames = H3_DURATIONS.get(label)
        if frames is None:
            # Restore a valid duration from a history entry made outside the GUI.
            frames = int(label.rsplit("(", 1)[1].removesuffix("f)"))
        choices = self._h3_choices() if hasattr(self, "h3_model") else {}
        fixed = core.H3_TURBOS[choices.get("h3_turbo", "off")][1]
        hybrid = core.h3_hybrid_filename(choices.get("h3_model")) is not None
        if hybrid and choices.get("h3_performance") in ("euler_dense", "kitchen_int8"):
            fixed = 8
        normal = self.h3_hybrid_steps if hybrid else getattr(self, "h3_steps", self.steps)
        values = {
            "width": width, "height": height, "frames": frames,
            "fps": 24, "steps": fixed if fixed is not None else int(normal.get()),
        }
        if self.seed.get().strip():
            values["seed"] = int(self.seed.get().strip())
        for name, value in values.items():
            core.check_param(name, value)
        core.validate_h3_video_parameters(values)
        if hybrid:
            core.validate_h3_hybrid_steps(values["steps"], choices.get("h3_performance", "standard"))
        return {**values, **choices}

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
        """Inspect the most recent result/dry-run without changing history."""
        result = self.latest_prompt_plan
        if not result or not isinstance(result.get("parameters"), dict):
            messagebox.showinfo(
                "生成タグ", "「解釈のみテスト」または画像生成を実行してください。",
            )
            return
        params = result["parameters"]
        workflow_id = result.get("workflow_id", "")
        kind = self.config.get("workflows", {}).get(workflow_id, {}).get("kind")
        self._open_prompt_details({
            "workflow_id": workflow_id,
            "kind": kind,
            "profile": self.latest_prompt_profile,
            "request_text": self.latest_request_text,
            "positive_prompt": params.get("positive_prompt", ""),
            "negative_prompt": params.get("negative_prompt"),
            "seed": params.get("seed"),
            "steps": params.get("steps"),
            "cfg": params.get("cfg"),
            "denoise": params.get("denoise"),
            "character_traits": self.latest_character_traits,
            "character_analysis": self.latest_character_analysis,
            "character_references": self.latest_character_references,
        }, from_history=False)

    def _open_prompt_details(self, details: dict, *, from_history: bool) -> None:
        """Shared read-only viewer for current and historic literal prompts."""
        kind = details.get("kind")
        version = details.get("profile")
        if kind == "t2i":
            version_text = T2I_PROFILE_LABELS.get(version, version or "記録なし")
        elif kind in ("i2i", "inpaint"):
            version_text = I2I_PROFILE_LABELS.get(version, version or "記録なし")
        elif details.get("workflow_id") == core.H3_I2V_ID:
            version_text = H3_PROFILE_LABELS.get(version, version or "記録なし")
        else:
            version_text = version or "対象外"
        positive = str(details.get("positive_prompt") or "")
        negative = details.get("negative_prompt")
        negative_saved = isinstance(negative, str)
        negative_text = negative if negative_saved else "（履歴に記録なし）"
        original_request = details.get("request_text")
        popup = tk.Toplevel(self.root)
        popup.title(("履歴" if from_history else "今回") + "の生成タグ")
        popup.geometry("780x650")
        popup.minsize(480, 390)
        popup.transient(self.root)
        ttk.Label(
            popup,
            text=f"ワークフロー: {details.get('workflow_id', '?')} / "
                 f"方式: {version_text}",
            style="Muted.TLabel", wraplength=740,
        ).pack(anchor="w", padx=12, pady=(10, 3))
        values = [
            f"{label}: {details.get(key)}"
            for key, label in (
                ("seed", "Seed"), ("steps", "Steps"),
                ("cfg", "CFG"), ("denoise", "Denoise"),
            )
            if details.get(key) is not None
        ]
        if values:
            ttk.Label(
                popup, text="  /  ".join(values),
                style="Muted.TLabel", wraplength=740,
            ).pack(anchor="w", padx=12, pady=(0, 5))

        # Pack the action bar before expanding editors, so copy/close is
        # reachable even if the window is resized smaller than its content.
        buttons = ttk.Frame(popup, padding=(12, 0, 12, 12))
        buttons.pack(side="bottom", fill="x")

        def add_readonly(label: str, value: str, *, rows: int, grow: bool) -> None:
            frame = ttk.LabelFrame(popup, text=label, padding=7)
            frame.pack(fill="both" if grow else "x",
                       expand=grow, padx=12, pady=(0, 7))
            widget = scrolledtext.ScrolledText(
                frame, height=rows, wrap="word",
                font=("Meiryo UI", 10), padx=8, pady=6,
            )
            widget.insert("1.0", value)
            widget.configure(state="disabled")
            widget.pack(fill="both", expand=True)

        if original_request is not None:
            add_readonly("元の自然文", str(original_request), rows=3, grow=False)
        add_readonly("Positive", positive, rows=7, grow=True)
        add_readonly("Negative", negative_text, rows=4, grow=True)

        ttk.Button(
            buttons, text="Positiveをコピー",
            command=lambda: self._copy_to_clipboard(positive),
        ).pack(side="left", padx=(0, 6))
        ttk.Button(
            buttons, text="Negativeをコピー",
            command=lambda: self._copy_to_clipboard(negative),
            state="normal" if negative_saved else "disabled",
        ).pack(side="left")
        if details.get("character_traits"):
            ttk.Button(
                buttons, text="キャラ特徴",
                command=lambda: self._show_saved_character_features(details),
            ).pack(side="left", padx=(6, 0))
        ttk.Button(
            buttons, text="閉じる", command=popup.destroy,
        ).pack(side="right")

    def _show_saved_character_features(self, details: dict) -> None:
        """Review the exact approved sheet and observed reference evidence."""
        traits = details.get("character_traits")
        if not traits:
            return
        popup = tk.Toplevel(self.root)
        popup.title("キャラ参照・確定特徴")
        popup.geometry("760x570")
        popup.minsize(450, 300)
        popup.transient(self.root)
        bottom = ttk.Frame(popup, padding=(10, 3, 10, 10))
        bottom.pack(side="bottom", fill="x")
        ttk.Button(
            bottom, text="確定特徴をコピー",
            command=lambda: self._copy_to_clipboard(traits),
        ).pack(side="left")
        ttk.Button(bottom, text="閉じる", command=popup.destroy).pack(side="right")
        num = len(details.get("character_references") or ())
        ttk.Label(
            popup, text=f"生成に採用した特徴 / 参照画像 {num}枚",
            style="Muted.TLabel",
        ).pack(anchor="w", padx=10, pady=(8, 4))
        content = ttk.Panedwindow(popup, orient="vertical")
        content.pack(fill="both", expand=True, padx=10, pady=(0, 8))
        approved_frame = ttk.LabelFrame(content, text="ユーザー確定値")
        content.add(approved_frame, weight=2)
        report_frame = ttk.LabelFrame(content, text="抽出根拠（LLM推定）")
        content.add(report_frame, weight=3)
        for frame, value in (
            (approved_frame, traits),
            (report_frame, (
                format_evidence(details["character_analysis"])
                if details.get("character_analysis") else "記録なし"
            )),
        ):
            view = scrolledtext.ScrolledText(
                frame, wrap="word", height=7, font=("Meiryo UI", 10),
            )
            view.insert("1.0", value)
            view.configure(state="disabled")
            view.pack(fill="both", expand=True, padx=6, pady=6)

    def _copy_to_clipboard(self, value: str) -> None:
        self.root.clipboard_clear()
        self.root.clipboard_append(value)
        self.root.update_idletasks()

    def _show_composition_report(self) -> None:
        """Show exactly what the selected local VLM thought it saw."""
        report = self.latest_composition_report
        if not report:
            messagebox.showinfo(
                "画像の構図認識",
                "まず参照画像を選び、「解釈のみテスト」を実行してください。"
                "画像対応モデルと構図解析ONが必要です。",
            )
            return
        window = tk.Toplevel(self.root)
        window.title("画像の構図認識結果（VLM推定）")
        window.geometry("700x480")
        window.minsize(440, 300)
        window.transient(self.root)
        ttk.Label(
            window,
            text="以下は画像対応LLMの観察結果です。誤認識があれば、生成指示を具体化するか"
                 "ポーズControlNetの併用を検討してください。",
            style="Muted.TLabel", wraplength=650,
        ).pack(anchor="w", fill="x", padx=12, pady=(12, 7))
        view = scrolledtext.ScrolledText(
            window, wrap="word", font=("Meiryo UI", 11), padx=10,
            pady=8, height=14,
        )
        view.insert("1.0", report)
        view.configure(state="disabled")
        view.pack(fill="both", expand=True, padx=12, pady=(0, 8))
        footer = ttk.Frame(window, padding=(12, 0, 12, 12))
        footer.pack(fill="x")
        ttk.Button(
            footer, text="閉じる", command=window.destroy,
        ).pack(side="right")

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
        )

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

        def task():
            try:
                analysis = LMStudio(settings).analyze_character_references(
                    paths, progress=lambda line: self.messages.put(("progress", line)),
                )
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

        def task():
            try:
                revised = LMStudio(settings).revise_character_description(
                    current, instruction,
                    progress=lambda line: self.messages.put(("progress", line)),
                )
                self.messages.put(("character_revision_done", (dialog, revised)))
            except Exception as exc:
                self.messages.put(("character_revision_error", (dialog, str(exc))))

        threading.Thread(target=task, daemon=True).start()

    def _approve_character_traits(
        self, paths: tuple[Path, ...], analysis: dict, traits: str,
    ) -> None:
        paths = validate_character_images(paths)
        traits = normalize_character_traits(traits)
        # Persist first. If it fails, keep the previous accepted sheet intact.
        save_character_sheet(ROOT, paths, analysis, traits)
        self.character_references = paths
        self.character_analysis = copy.deepcopy(analysis)
        self.character_traits = traits
        self.character_status.set(f"キャラ参照 · {len(paths)}枚")
        self.status.set("キャラ特徴を確定しました。次のT2I/I2Iから反映します")
        self._log(f"キャラ特徴確定: {len(paths)}枚（生成プロンプトへ反映）")

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

    def _use_as_i2i_source(self, path: Path | None, workflow_id: str = "wai_i2i_basic") -> None:
        label = "I2V" if workflow_id in core.HOST_VIDEO_IDS else "I2I"
        if self.working:
            messagebox.showwarning(label, "現在の処理が終了してから画像を指定してください")
            return
        if path is None or not path.is_file() or path.suffix.lower() not in IMAGE_EXTENSIONS:
            messagebox.showerror(label, "静止画像を選択してください")
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
        self.workflow.set(workflow_id)
        self._update_generation_controls()
        self.tabs.select(0)
        self.prompt.focus_set()
        self.status.set(f"生成結果を{label}の参照画像に設定しました")

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

    def _current_output_to_i2v(self) -> None:
        selected = self.images_list.curselection()
        index = selected[0] if selected else 0
        self._use_as_i2i_source(
            self.image_paths[index] if index < len(self.image_paths) else None,
            core.H3_I2V_ID,
        )

    def _history_output_to_i2v(self) -> None:
        entry = self._one_history()
        self._use_as_i2i_source(entry.first_image if entry else None, core.H3_I2V_ID)

    def _open_history_output(self) -> None:
        entry = self._one_history()
        if entry and entry.first_image and entry.first_image.is_file():
            self._open_path(entry.first_image)
        else:
            messagebox.showinfo("履歴", "保存済みファイルを1件選択してください")

    def _apply_generation_model_choices(self) -> None:
        if self.generation_inventory is None:
            return
        choices = core.installed_model_choices(self.generation_inventory)
        # Preserve selected values even when a model was removed: never silently
        # change the actual generation weights on refresh or history restore.
        h3 = [core.h3_model_label(key) for key in choices["h3"]]
        current = self.h3_model.get()
        if current not in h3:
            h3.append(current)
        self.h3_model_box.configure(values=h3)
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

    def _release_comfy_memory(self) -> None:
        """Request memory release off the GUI thread, only with an empty queue."""
        if self.working:
            return
        settings = copy.deepcopy(self.config["comfyui"])
        settings["base_url"] = self.comfy_url.get().strip()
        self._set_busy("生成モデルの解放を要求中")
        self.cancel_button.configure(state="disabled")

        def task():
            try:
                core.ComfyUI(settings).free_if_idle()
                self.messages.put(("progress", "ComfyUI: メモリ解放要求を送信しました"))
            except Exception as exc:
                self.messages.put(("error", str(exc)))
            finally:
                self.messages.put(("idle", None))

        threading.Thread(target=task, daemon=True).start()

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
        if self.character_analysis_running:
            messagebox.showwarning(
                "キャラ参照", "キャラ特徴抽出が終了してから画像を生成してください"
            )
            return
        if not self._save_settings():
            return
        prompt = self.prompt.get("1.0", "end").strip()
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
        is_video = self.config["workflows"][selected]["kind"] == "i2v"
        if is_video:
            # Keep still-image composition and character selections intact,
            # without letting them trigger a VLM or block video generation.
            composition = None
        if is_video and (image is None or image.suffix.lower() not in IMAGE_EXTENSIONS
                         or mask is not None or pose is not None):
            messagebox.showerror("I2V", "参照画像を1枚指定し、マスク・ポーズ画像は空欄にしてください")
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
            if selected in core.SDXL_WORKFLOW_IDS and hasattr(self, "checkpoint_model"):
                overrides["checkpoint_model"] = self.checkpoint_model.get()
                core.split_checkpoint_option(overrides, {selected})
                if self._sdxl_turbo_active():
                    overrides.update(steps=4, cfg=1)
        except (ValueError, core.OrchestratorError) as exc:
            messagebox.showerror("生成設定エラー", str(exc))
            return
        cfg = copy.deepcopy(self.config)
        approved_traits = None if is_video else (self.character_traits or None)
        approved_images = tuple(self.character_references) if approved_traits else ()
        approved_analysis = (
            copy.deepcopy(self.character_analysis) if approved_traits else None
        )
        if approved_traits:
            try:
                validate_character_images(approved_images)
                normalize_character_traits(approved_traits)
                if not isinstance(approved_analysis, dict):
                    raise core.OrchestratorError("キャラ参照の承認情報がありません")
            except (OSError, ValueError, core.OrchestratorError) as exc:
                messagebox.showerror("キャラ参照", str(exc))
                return
        self.latest_character_traits = approved_traits
        self.latest_character_references = approved_images
        self.latest_character_analysis = approved_analysis
        self.latest_composition_report = ""
        kind = cfg["workflows"][selected]["kind"]
        self.latest_prompt_profile = (
            None if not use_prompt_llm else
            cfg["llm"].get("t2i_prompt_profile", DEFAULT_T2I_PROFILE)
            if kind == "t2i" else
            cfg["llm"].get("i2i_prompt_profile", DEFAULT_I2I_PROFILE)
            if kind in ("i2i", "inpaint") else
            cfg["llm"].get("h3_prompt_profile", DEFAULT_H3_PROFILE)
            if selected == core.H3_I2V_ID else None
        )
        self.latest_request_text = prompt
        self._set_busy("解釈テスト中..." if dry_run else "生成準備中...")
        self._log("開始: " + ("解釈のみテスト" if dry_run else "動画生成" if is_video else "画像生成")
                  + (f" / model={cfg['llm']['model']}" if use_prompt_llm else " / LLMなし"))

        def task():
            try:
                result = core.execute(
                    cfg, CONFIG, prompt, image=image, dry_run=dry_run,
                    selected_workflow=selected, overrides=overrides,
                    progress=lambda line: self.messages.put(("progress", line)),
                    cancel_event=self.stop_event, mask_image=mask, pose_image=pose,
                    composition_image=composition,
                    **({"character_traits": approved_traits}
                       if approved_traits else {}),
                )
                images = []
                if not dry_run:
                    for item in output_media(result):
                        try:
                            path = save_output_image(cfg["comfyui"]["base_url"], item, result["prompt_id"])
                            images.append(path)
                        except Exception as exc:
                            self.messages.put(("progress", f"出力取得エラー: {exc}"))
                if not dry_run and is_video and not any(is_video_output(p) for p in images):
                    raise core.OrchestratorError("動画を取得できません。ComfyUIのoutput/videoを確認してください")
                history_id = (
                    self._record_completed_generation(
                        result, images, prompt, image, mask, pose, composition,
                        self.latest_prompt_profile,
                        character_references=approved_images,
                        character_traits=approved_traits,
                        character_analysis=approved_analysis,
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
            # Yield between bursts of worker events instead of monopolizing Tk.
            for _ in range(24):
                kind, data = self.messages.get_nowait()
                if kind == "progress":
                    if data.startswith("【構図認識結果】\n"):
                        self.latest_composition_report = data.split("\n", 1)[1]
                        self.status.set("構図認識が完了しました（認識結果...から確認可能）")
                    else:
                        self.status.set(data)
                    self._log(data)
                elif kind == "character_analysis_done":
                    dialog, analysis = data
                    self.character_analysis_running = False
                    dialog.finish(analysis=analysis)
                    self._log("キャラ参照画像の共通特徴を抽出。編集・確定待ち")
                    self.status.set("キャラ特徴を編集して確定してください")
                elif kind == "character_analysis_error":
                    dialog, error = data
                    self.character_analysis_running = False
                    dialog.finish(error=error)
                    self._log("キャラ特徴抽出エラー: " + error)
                    self.status.set("キャラ特徴抽出に失敗しました")
                elif kind == "character_revision_done":
                    dialog, revised = data
                    self.character_analysis_running = False
                    dialog.finish_revision(revised_text=revised)
                    self._log("自然文のキャラ説明修正案が完成（未確定）")
                    self.status.set("キャラ説明の修正案を確認して確定してください")
                elif kind == "character_revision_error":
                    dialog, error = data
                    self.character_analysis_running = False
                    dialog.finish_revision(error=error)
                    self._log("自然文でのキャラ説明修正エラー: " + error)
                    self.status.set("自然文による説明修正に失敗しました")
                elif kind == "check":
                    for line in data:
                        self._log(line)
                    self.status.set("接続確認が完了しました")
                elif kind == "generation_models":
                    url, inventory = data
                    if url == self.comfy_url.get().strip():
                        self.generation_inventory = inventory
                        self._apply_generation_model_choices()
                        choices = core.installed_model_choices(inventory)
                        self._log(f"ComfyUIモデル: SDXL {len(choices['sdxl'])}件 / H3 {len(choices['h3'])}件")
                elif kind == "generation_models_error":
                    self._log("ComfyUIモデル一覧を更新できません: " + data)
                elif kind == "models":
                    names = [item["key"] for item in data]
                    self.model_box.configure(values=names)
                    if self.model.get() not in names and names:
                        self.model.set(names[0])
                    self._log(f"LM Studioモデル: {len(names)}件。必要なモデルを選択して設定を保存してください。")
                    self.status.set(f"モデル一覧を更新: {len(names)}件")
                elif kind == "history_loaded":
                    self._finish_history_refresh(*data)
                elif kind == "done":
                    result, images, history_id = data
                    self.latest_prompt_plan = result
                    self.result_prompt_button.configure(state="normal")
                    if result["status"] == "dry_run":
                        self._log("解釈結果:\n" + json.dumps(result, ensure_ascii=False, indent=2))
                        self.status.set("解釈テスト完了（ComfyUI未実行）")
                        self.tabs.select(0)
                        self._show_prompt_preview()
                    else:
                        self.image_paths = images
                        self.images_list.delete(0, "end")
                        for file in images:
                            self.images_list.insert("end", file.name)
                        if len(images) > 1:
                            self.images_list.pack(fill="x", pady=(0, 5))
                        else:
                            self.images_list.pack_forget()
                        if images:
                            self.images_list.selection_set(0)
                            self._display_image(images[0])
                            self.open_button.configure(state="normal")
                        else:
                            self._set_result_video(None)
                            self.preview_photo = None
                            self.image_label.configure(image="", text="出力なし")
                            self.result_info.set("")
                            self.result_tools.pack_forget()
                            self.open_button.configure(state="disabled")
                        self._log("生成完了: " + json.dumps(result.get("parameters", {}), ensure_ascii=False))
                        self.status.set("動画生成完了" if any(is_video_output(p) for p in images) else "画像生成完了")
                        self.tabs.select(0)
                        self._refresh_history(select_id=history_id, scan_legacy=False)
                elif kind == "error":
                    self._log("ERROR: " + data)
                    self.status.set("エラー: " + data[:110])
                    messagebox.showerror("処理エラー", data)
                elif kind == "idle":
                    self.working = False
                    for name in ("result_video", "history_video"):
                        if hasattr(self, name):
                            getattr(self, name).set_enabled(True)
                    self.run_button.configure(state="normal")
                    self.preview_button.configure(state="normal")
                    self.cancel_button.configure(state="disabled")
                    if hasattr(self, "free_memory_button"):
                        self.free_memory_button.configure(state="normal")
                    self.progress_bar.stop()
                    self._history_selection_changed()
        except queue.Empty:
            pass
        if self.root.winfo_exists():
            self.root.after(15 if not self.messages.empty() else 100, self._consume_messages)

    def _show_selected_image(self, _event=None) -> None:
        selected = self.images_list.curselection()
        if selected and selected[0] < len(self.image_paths):
            self._display_image(self.image_paths[selected[0]])

    def _display_image(self, path: Path) -> None:
        if hasattr(self, "result_video"):
            self._set_result_video(path if is_video_output(path) else None)
        if path.suffix.lower() in IMAGE_EXTENSIONS:
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

    def _open_image(self) -> None:
        selected = self.images_list.curselection()
        index = selected[0] if selected else 0
        if index < len(self.image_paths):
            self._open_path(self.image_paths[index])

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
        for name in ("result_video", "history_video"):
            if hasattr(self, name):
                getattr(self, name).stop()
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
