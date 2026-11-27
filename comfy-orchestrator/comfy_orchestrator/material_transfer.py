"""Reusable material selection and compatible settings transfer (no GUI)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tempfile
import uuid

from .generation_form import H3_DURATIONS
from .h3 import (h3_model_label, h3_hybrid_filename, split_h3_options, H3_TURBO_LABELS,
                 H3_ENCODER_LABELS, H3_PERFORMANCE_LABELS, H3_OPTION_KEYS)
from .long_video_plan import LONG_VIDEO_ID, continuation_model, check_cancel
from .output_collection import IMAGE_EXTENSIONS, VIDEO_EXTENSIONS
from .parameters import OrchestratorError, check_param
from .prompt_profiles import H3_PROFILE_LABELS, I2I_PROFILE_LABELS
from .video_media import FFmpeg
from .workflow_registry import (H3_I2V_ID, SDXL_WORKFLOW_IDS, sdxl_checkpoint_kind,
                                validate_h3_video_parameters)
from .asset_store import save_snapshot

DESTINATIONS = {"image": ("画像編集", "wai_i2i_basic"),
                "video": ("単発動画", H3_I2V_ID),
                "continuous": ("連続動画", H3_I2V_ID)}


@dataclass(frozen=True)
class Material:
    label: str
    path: Path


@dataclass(frozen=True)
class Transfer:
    material: Material
    mode: str
    request: str | None
    settings: dict


def available_materials(outputs, reference=None):
    rows, seen = [], set()
    for label, value in [*(("出力", p) for p in outputs), ("元の参照", reference)]:
        if value is None:
            continue
        path = Path(value).resolve()
        if path in seen or not path.is_file() or path.suffix.lower() not in IMAGE_EXTENSIONS | VIDEO_EXTENSIONS:
            continue
        seen.add(path)
        rows.append(Material(f"{label} · {path.name}", path))
    return tuple(rows)


def transfer_settings(workflow_id, parameters, profile, mode):
    """Copy only compatible settings, never prompts or a prior cut plan."""
    p = dict(parameters or {})
    result = {}
    if mode == "image" and workflow_id in SDXL_WORKFLOW_IDS:
        model = p.get("checkpoint_model")
        if model is not None and sdxl_checkpoint_kind(model) == "turbo":
            return {}
        if model is not None and sdxl_checkpoint_kind(model) is not None:
            result["checkpoint_model"] = model
        for name in ("steps", "cfg", "seed", "denoise"):
            if name in p:
                check_param(name, p[name])
                result[name] = str(p[name])
        if profile in I2I_PROFILE_LABELS:
            result["i2i_profile"] = I2I_PROFILE_LABELS[profile]
        return result
    if mode not in ("video", "continuous") or workflow_id not in (H3_I2V_ID, LONG_VIDEO_ID):
        return {}
    if workflow_id == LONG_VIDEO_ID:
        base = p.get("long_base_overrides")
        if isinstance(base, dict):
            p = dict(base)
        elif "long_segment_frames" in p:
            p["frames"] = p["long_segment_frames"]
        else:
            return {}
    _, options = split_h3_options({k: p[k] for k in H3_OPTION_KEYS if k in p}, enabled=True)
    if options:
        model = options["h3_model"]
        if mode == "continuous":
            try:
                continuation_model(model)
            except OrchestratorError:
                return {}
        result["h3_model"] = h3_model_label(model)
        result["h3_turbo"] = H3_TURBO_LABELS[options["h3_turbo"]]
        if h3_hybrid_filename(model) is not None:
            result["h3_performance"] = H3_PERFORMANCE_LABELS[options.get("h3_performance", "standard")]
        if "h3_encoder_device" in options:
            result["h3_encoder_cpu"] = options["h3_encoder_device"] == "cpu"
        if "h3_encoder_model" in options:
            result["h3_encoder_model"] = H3_ENCODER_LABELS[options["h3_encoder_model"]]
    if {"width", "height", "fps", "frames"} <= p.keys():
        validate_h3_video_parameters(p)
        result["h3_size"] = f"{p['width']} × {p['height']}"
        result["h3_duration"] = next((label for label, n in H3_DURATIONS.items() if n == p["frames"]),
                                     f"{p['frames'] / 24:.2f}秒 ({p['frames']}f)")
    if "steps" in p:
        check_param("steps", p["steps"])
        result["h3_hybrid_steps" if h3_hybrid_filename(options.get("h3_model")) is not None else "h3_steps"] = str(p["steps"])
    if "seed" in p:
        check_param("seed", p["seed"])
        result["seed"] = str(p["seed"])
    if profile in H3_PROFILE_LABELS:
        result["h3_profile"] = H3_PROFILE_LABELS[profile]
    return result


def source_stamp(path):
    info = Path(path).stat()
    return info.st_size, info.st_mtime_ns


def extract_material(store, source, frame, *, stamp, source_history_id=None, cancel_event=None, media=None):
    """Publish an exact decoded frame with its lineage, as a non-generation row."""
    source = Path(source).resolve()
    if not source.is_file() or source.suffix.lower() not in VIDEO_EXTENSIONS:
        raise OrchestratorError("動画ファイルを選択してください")
    if type(frame) is not int or frame < 1:
        raise OrchestratorError("フレーム番号が不正です")
    if source_stamp(source) != stamp:
        raise OrchestratorError("動画が変更されました。素材選択からやり直してください")
    store._relative_output(source)
    media = media or FFmpeg()
    with tempfile.TemporaryDirectory(prefix="asobiba-frame-") as temporary:
        target = Path(temporary) / "frame.png"
        media.extract_frame(source, frame, target, cancel_event)
        check_cancel(cancel_event)
        if source_stamp(source) != stamp:
            raise OrchestratorError("切り出し中に動画が変更されました")
        if not target.is_file() or not 0 < target.stat().st_size <= 40 * 1024 * 1024:
            raise OrchestratorError("フレーム画像が空または40MBを超えています")
        destination = store.outputs / "materials" / f"{uuid.uuid4().hex[:16]}_f{frame:06d}.png"
        save_snapshot(target, destination, store.data / "asset_pool")
        try:
            return store.record_frame(source=source, frame=frame, image=destination,
                                      source_history_id=source_history_id)
        except Exception:
            destination.unlink(missing_ok=True)
            raise
