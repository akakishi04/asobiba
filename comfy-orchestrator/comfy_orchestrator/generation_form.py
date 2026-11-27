"""Workflow selection, generation form policies and raw-value validation.

These functions depend on configuration and values, not the Tk event loop.
"""
from __future__ import annotations

from .parameters import OrchestratorError, check_param
from .workflow_registry import (
    compatible_workflows,
    VIDEO_KINDS,
    H3_I2V_ID,
    WAN_I2V_ID,
    HUNYUAN_I2V_ID,
    QWEN_T2I_ID,
    QWEN_LIGHTNING_ID,
    QWEN_IDS,
    SDXL_WORKFLOW_IDS,
    validate_wan_video_parameters,
    validate_hunyuan_video_parameters,
    validate_h3_video_parameters,
)
from .h3 import H3_OPTION_KEYS, H3_TURBOS, h3_hybrid_filename, validate_h3_hybrid_steps
from .long_video_plan import LONG_VIDEO_ID, LONG_TARGETS
from .timeline import CONTINUATION_OVERLAP_FRAMES, GUIDE_CONNECTION_FRAMES


# Keep the pixel dimensions authoritative: presets are just a GUI shortcut.
CUSTOM_RESOLUTION = "カスタム"
VIDEO_RESOLUTIONS = ("832 × 480", "480 × 832", "640 × 640", "1280 × 704", "704 × 1280")
VIDEO_FRAME_COUNTS = ("49", "81", "121")
HUNYUAN_RESOLUTIONS = ("848 × 480", "480 × 848", "640 × 640")
H3_RESOLUTIONS = ("864 × 480", "480 × 864", "640 × 640", "1056 × 608", "608 × 1056", "1344 × 768", "768 × 1344", "768 × 768")
H3_DURATIONS = {"約5秒 (124f)": 124, "8秒 (192f)": 192, "約10秒 (243f)": 243, "約12秒 (294f)": 294, "約15秒 (362f)": 362}
# Only the adopted guide policy and the conventional comparison are selectable.
H3_CONNECTION_LABELS = {GUIDE_CONNECTION_FRAMES: "ガイド接続（22f）", 0: "従来接続"}
# A loaded old manifest may display its retired policy without making it a
# selectable option. This permits exact resume, including in-flight jobs.
LEGACY_CONNECTION_LABELS = {
    frames: f"旧助走接続（最大{frames}f）"
    for frames in range(1, CONTINUATION_OVERLAP_FRAMES + 1)
}


def preferred_connection_frames(frames):
    """Migrate old UI preferences; do not alter any saved project."""
    return frames if type(frames) is int and frames in H3_CONNECTION_LABELS else GUIDE_CONNECTION_FRAMES


def connection_label(frames):
    if type(frames) is int and frames in LEGACY_CONNECTION_LABELS:
        return LEGACY_CONNECTION_LABELS[frames]
    return H3_CONNECTION_LABELS[preferred_connection_frames(frames)]


def connection_frames(label):
    for frames, name in {**H3_CONNECTION_LABELS, **LEGACY_CONNECTION_LABELS}.items():
        if name == label:
            return frames
    raise OrchestratorError("接続方式の設定が不正です")


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
    candidates = compatible_workflows(
        config.get("workflows", {}),
        image=True if has_image else None,
        mask=True if has_mask else None,
        pose=True if has_pose else None,
    )
    candidates = {key: entry for key, entry in candidates.items() if entry.get("kind") not in VIDEO_KINDS}
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
    H3_I2V_ID: "動画生成 · MiniMax H3",
    LONG_VIDEO_ID: "動画生成 · H3 長尺",
    WAN_I2V_ID: "動画生成 · Wan 2.2",
    HUNYUAN_I2V_ID: "動画生成 · Hunyuan 1.5 (480p)",
    QWEN_T2I_ID: "画像生成 · Qwen-Image 2512",
    QWEN_LIGHTNING_ID: "画像生成 · Qwen-Image 2512 (4 Steps)",
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


GENERATION_MODE_LABELS = {"image": "画像生成", "video": "動画生成", "continuous": "連続動画生成"}
CONTINUOUS_TARGETS = tuple(label for label, seconds in LONG_TARGETS.items() if seconds > 0)


def workflow_generation_mode(config: dict, workflow_id: str) -> str:
    if workflow_id == LONG_VIDEO_ID:
        return "continuous"
    entry = config.get("workflows", {}).get(workflow_id, {})
    return "video" if entry.get("kind") in VIDEO_KINDS else "image"


def mode_workflow_ids(config: dict, mode: str) -> tuple[str, ...]:
    workflows = config.get("workflows", {})
    if mode == "continuous":
        return (H3_I2V_ID,) if workflows.get(H3_I2V_ID, {}).get("kind") == "i2v" else ()
    if mode == "video":
        return tuple(key for key, entry in workflows.items() if entry.get("kind") in VIDEO_KINDS)
    return ("自動", *(key for key, entry in workflows.items() if entry.get("kind") not in VIDEO_KINDS))


def choose_mode_workflow(config: dict, mode: str, preferred: str | None = None) -> str:
    choices = mode_workflow_ids(config, mode)
    if preferred in choices:
        return preferred
    if H3_I2V_ID in choices:
        return H3_I2V_ID
    return choices[0] if choices else ""


def parameter_visibility(config: dict, workflow_id: str | None, custom_size: bool = False,
                         *, generation_mode: str | None = None) -> dict:
    """All workflows share the same grid. Only the individual fields vary."""
    entry = config.get("workflows", {}).get(workflow_id, {})
    bindings = entry.get("bindings", {})
    kind = entry.get("kind")
    video = kind in VIDEO_KINDS
    h3 = workflow_id == H3_I2V_ID
    hunyuan = workflow_id == HUNYUAN_I2V_ID
    qwen = workflow_id in QWEN_IDS
    still_size = not video and "image" not in bindings and {"width", "height"} <= bindings.keys()
    return {
        "resolution": still_size,
        "custom_size": still_size and custom_size,
        "source_size": not video and "image" in bindings and not still_size,
        "wan": video and not h3 and not hunyuan,
        "h3": h3,
        "h3_long": h3 and generation_mode == "continuous",
        "h3_turbo": h3,
        "h3_performance": False,
        "hunyuan": hunyuan,
        "checkpoint": workflow_id in SDXL_WORKFLOW_IDS,
        "qwen_steps": workflow_id == QWEN_T2I_ID,
        "qwen_fixed": workflow_id == QWEN_LIGHTNING_ID,
        "steps": "steps" in bindings and not hunyuan and not qwen,
        "cfg": "cfg" in bindings and not qwen,
        "seed": "seed" in bindings,
        "denoise": "denoise" in bindings,
        "strength": "control_strength" in bindings,
        "t2i_profile": kind == "t2i" and not qwen,
        "i2i_profile": kind in ("i2i", "inpaint"),
        "h3_profile": h3,
    }


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
        else list(compatible_workflows(
            config.get("workflows", {}), image=True if has_image else None,
        ).values())
    )
    if not candidates:
        raise OrchestratorError("入力画像に対応するワークフローがありません")
    common = set(candidates[0]["bindings"])
    for entry in candidates[1:]:
        common.intersection_update(entry["bindings"])
    result = {key: value for key, value in overrides.items() if key in common}
    if workflow_id == H3_I2V_ID:
        result.update({key: overrides[key] for key in H3_OPTION_KEYS if key in overrides})
    for field, raw in (("denoise", denoise), ("control_strength", control_strength)):
        if field in common:
            value = float(raw)
            check_param(field, value)
            result[field] = value
    return result


def common_overrides(config, workflow_id, *, width, height, steps, cfg, seed,
                     has_h3_steps=False, has_hunyuan_steps=False) -> dict:
    """Validate active fields; hidden stale edits must not block other modes."""
    entry = config.get("workflows", {}).get(workflow_id, {})
    bindings = entry.get("bindings", {})
    video = entry.get("kind") in VIDEO_KINDS
    previous = config.get("ui", {}) if entry else {}
    values = {}
    for name, raw, parse, default in (
        ("width", width, int, 768),
        ("height", height, int, 768),
        ("steps", steps, int, 20),
        ("cfg", cfg, float, 5.0),
    ):
        try:
            value = parse(raw)
            check_param(name, value)
        except (ValueError, OrchestratorError):
            separate_qwen = entry.get("kind") == "t2i" and workflow_id in QWEN_IDS and name in ("steps", "cfg")
            separate_video_steps = name == "steps" and (
                (has_h3_steps and workflow_id == H3_I2V_ID)
                or (has_hunyuan_steps and workflow_id == HUNYUAN_I2V_ID)
            )
            if not entry or (name in bindings and not (video and name in ("width", "height"))
                             and not separate_video_steps and not separate_qwen):
                raise
            value = previous.get(name, default)
            try:
                check_param(name, value)
            except OrchestratorError:
                value = default
        values[name] = value
    if seed.strip():
        values["seed"] = int(seed.strip())
        check_param("seed", values["seed"])
    return values


def wan_overrides(*, size, frames, fps, steps, cfg, seed):
    width, height = (int(part.strip()) for part in size.split("×"))
    values = {"width": width, "height": height, "frames": int(frames), "fps": int(fps),
              "steps": int(steps), "cfg": float(cfg)}
    if seed.strip():
        values["seed"] = int(seed.strip())
    for name, value in values.items():
        check_param(name, value)
    validate_wan_video_parameters(values)
    return values


def qwen_overrides(workflow_id, *, width, height, steps, cfg, seed):
    fast = workflow_id == QWEN_LIGHTNING_ID
    values = {"width": int(width), "height": int(height),
              "steps": 4 if fast else int(steps), "cfg": 1 if fast else float(cfg)}
    if seed.strip():
        values["seed"] = int(seed.strip())
    for name, value in values.items():
        check_param(name, value)
    if values["width"] % 16 or values["height"] % 16:
        raise OrchestratorError("Qwen-Imageの幅・高さは16の倍数にしてください")
    return values


def hunyuan_overrides(*, size, frames, steps, seed):
    width, height = (int(part.strip()) for part in size.split("×"))
    values = {"width": width, "height": height, "frames": int(frames), "fps": 24, "steps": int(steps)}
    if seed.strip():
        values["seed"] = int(seed.strip())
    for name, value in values.items():
        check_param(name, value)
    validate_hunyuan_video_parameters(values)
    return values


def h3_overrides(*, size, duration, steps, seed, choices):
    width, height = (int(part.strip()) for part in size.split("×"))
    frames = H3_DURATIONS.get(duration)
    if frames is None:
        frames = int(duration.rsplit("(", 1)[1].removesuffix("f)"))
    fixed = H3_TURBOS[choices.get("h3_turbo", "off")][1]
    hybrid = h3_hybrid_filename(choices.get("h3_model")) is not None
    if hybrid and choices.get("h3_performance") in ("euler_dense", "kitchen_int8"):
        fixed = 8
    values = {"width": width, "height": height, "frames": frames, "fps": 24,
              "steps": fixed if fixed is not None else int(steps)}
    if seed.strip():
        values["seed"] = int(seed.strip())
    for name, value in values.items():
        check_param(name, value)
    validate_h3_video_parameters(values)
    if hybrid:
        validate_h3_hybrid_steps(values["steps"], choices.get("h3_performance", "standard"))
    return {**values, **choices}
