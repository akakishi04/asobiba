from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path

from resource_policy import (
    PROFILE_CUSTOM,
    effective_gpu_duty_percent,
    effective_seedvr2_blocks_to_swap,
    validate_resource_profile,
)
from video_tool import VideoToolError


AI_NONE = "none"
AI_RVRT = "rvrt"
AI_SEEDVR2 = "seedvr2"
AI_RVRT_SEEDVR2 = "rvrt_seedvr2"

AI_CHOICES = {
    "なし": AI_NONE,
    "RVRT（忠実復元 / デブラー）": AI_RVRT,
    "SeedVR2（AI復元）": AI_SEEDVR2,
    "RVRT → SeedVR2（高品質）": AI_RVRT_SEEDVR2,
}

RVRT_TASKS = {
    "GoPro Deblur（推奨）": "005_RVRT_videodeblurring_GoPro_16frames",
    "DVD Deblur": "004_RVRT_videodeblurring_DVD_16frames",
}

DEFAULT_SEEDVR2_MODEL = "seedvr2_ema_3b_fp8_e4m3fn.safetensors"


@dataclass
class AIConfig:
    # rvrt_repo is kept only so older ai_config.json files continue loading. The
    # managed backend uses the PyPI vsrvrt package and rvrt_runner.py instead.
    rvrt_repo: str = ""
    rvrt_python: str = ""
    rvrt_task: str = "005_RVRT_videodeblurring_GoPro_16frames"
    rvrt_chunk_size: int = 16
    rvrt_chunk_overlap: int = 4
    seedvr2_repo: str = ""
    seedvr2_python: str = ""
    seedvr2_model: str = DEFAULT_SEEDVR2_MODEL
    seedvr2_batch_size: int = 5
    seedvr2_blocks_to_swap: int = 20
    seedvr2_temporal_overlap: int = 2
    seedvr2_resolution_override: int = 0
    seedvr2_vae_tiling: bool = True
    seedvr2_vae_tile_size: int = 512
    seedvr2_vae_tile_overlap: int = 128
    # The upstream standalone CLI materializes all selected frames in system RAM
    # before inference. Keep each invocation bounded and blend neighboring chunks.
    seedvr2_chunk_size: int = 45
    seedvr2_chunk_overlap: int = 5
    # Resource policy. Presets do not lower image resolution or quality settings.
    resource_profile: str = "max"
    gpu_duty_cycle_percent: int = 100

    @classmethod
    def load(cls, config_path: str | Path) -> "AIConfig":
        path = Path(config_path)
        if not path.is_file():
            return cls()
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise VideoToolError(f"AI設定を読み込めません: {path}") from exc

        known = {field_name for field_name in cls.__dataclass_fields__}
        values = {key: value for key, value in payload.items() if key in known}
        return cls(**values)

    def save(self, config_path: str | Path) -> None:
        path = Path(config_path)
        path.write_text(
            json.dumps(asdict(self), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


def resolve_python(value: str) -> str:
    raw = value.strip()
    if not raw:
        raise VideoToolError("AI用Pythonが設定されていません。")
    candidate = Path(raw)
    if candidate.is_file():
        return str(candidate)
    found = shutil.which(raw)
    if found:
        return found
    raise VideoToolError(f"AI用Pythonが見つかりません: {raw}")


def _require_repo(repo_value: str, marker: str, engine_name: str) -> Path:
    raw = repo_value.strip()
    if not raw:
        raise VideoToolError(f"{engine_name} のフォルダが設定されていません。")
    repo = Path(raw)
    marker_path = repo / marker
    if not marker_path.is_file():
        raise VideoToolError(
            f"{engine_name} の実行ファイルが見つかりません: {marker_path}"
        )
    return repo


def validate_for_mode(config: AIConfig, mode: str) -> None:
    try:
        validate_resource_profile(
            config.resource_profile,
            config.gpu_duty_cycle_percent,
        )
    except ValueError as exc:
        raise VideoToolError(str(exc)) from exc
    if mode in {AI_RVRT, AI_RVRT_SEEDVR2}:
        resolve_python(config.rvrt_python)
        if config.rvrt_task not in set(RVRT_TASKS.values()):
            raise VideoToolError(f"未対応のRVRTタスクです: {config.rvrt_task}")
        if config.rvrt_chunk_size < 4:
            raise VideoToolError("RVRT chunk size は4以上にしてください。")
        if config.rvrt_chunk_overlap < 0 or config.rvrt_chunk_overlap >= config.rvrt_chunk_size:
            raise VideoToolError("RVRT chunk overlap は0以上かつ chunk size 未満にしてください。")

    if mode in {AI_SEEDVR2, AI_RVRT_SEEDVR2}:
        _require_repo(config.seedvr2_repo, "inference_cli.py", "SeedVR2")
        resolve_python(config.seedvr2_python)
        if not config.seedvr2_model.strip():
            raise VideoToolError("SeedVR2 model が設定されていません。")
        if config.seedvr2_batch_size <= 0:
            raise VideoToolError("SeedVR2 batch size は1以上にしてください。")
        if config.seedvr2_temporal_overlap >= config.seedvr2_batch_size:
            raise VideoToolError("SeedVR2 temporal overlap は batch size より小さくしてください。")
        if config.seedvr2_blocks_to_swap < 0:
            raise VideoToolError("SeedVR2 blocks_to_swap は0以上にしてください。")
        if config.seedvr2_temporal_overlap < 0:
            raise VideoToolError("SeedVR2 temporal overlap は0以上にしてください。")
        if config.seedvr2_resolution_override < 0:
            raise VideoToolError("SeedVR2 resolution override は0以上にしてください。")
        if config.seedvr2_vae_tile_overlap >= config.seedvr2_vae_tile_size:
            raise VideoToolError("SeedVR2 VAE tile overlap は tile size より小さくしてください。")
        if config.seedvr2_chunk_size < 5:
            raise VideoToolError("SeedVR2 chunk size は5以上にしてください。")
        if config.seedvr2_chunk_overlap < 0 or config.seedvr2_chunk_overlap >= config.seedvr2_chunk_size:
            raise VideoToolError("SeedVR2 chunk overlap は0以上かつ chunk size 未満にしてください。")


def build_rvrt_command(
    config: AIConfig,
    input_dir: str | Path,
    output_dir: str | Path,
    runner_script: str | Path,
) -> tuple[list[str], Path]:
    python_bin = resolve_python(config.rvrt_python)
    runner = Path(runner_script).resolve()
    if not runner.is_file():
        raise VideoToolError(f"RVRT runner が見つかりません: {runner}")
    command = [
        python_bin,
        str(runner),
        "--input-dir",
        str(input_dir),
        "--output-video",
        str(output_video),
        "--task",
        config.rvrt_task,
        "--chunk-size",
        str(config.rvrt_chunk_size),
        "--chunk-overlap",
        str(config.rvrt_chunk_overlap),
    ]
    return command, runner.parent


def build_seedvr2_command(
    config: AIConfig,
    input_video: str | Path,
    output_video: str | Path,
    native_short_side: int,
) -> tuple[list[str], Path]:
    repo = _require_repo(config.seedvr2_repo, "inference_cli.py", "SeedVR2")
    python_bin = resolve_python(config.seedvr2_python)
    resolution = config.seedvr2_resolution_override or native_short_side
    if resolution <= 0:
        raise VideoToolError("SeedVR2の処理解像度を決定できません。")

    runner = Path(__file__).with_name("seedvr2_runner.py").resolve()
    if not runner.is_file():
        raise VideoToolError(f"SeedVR2 runner が見つかりません: {runner}")

    command = [
        python_bin,
        str(runner),
        "--repo",
        str(repo),
        "--video-path",
        str(input_video),
        "--output-dir",
        str(output_dir),
        "--resolution",
        str(resolution),
        "--batch-size",
        str(config.seedvr2_batch_size),
        "--model",
        config.seedvr2_model,
        "--blocks-to-swap",
        str(effective_seedvr2_blocks_to_swap(config)),
        "--temporal-overlap",
        str(config.seedvr2_temporal_overlap),
        "--chunk-size",
        str(config.seedvr2_chunk_size),
        "--chunk-overlap",
        str(config.seedvr2_chunk_overlap),
        "--color-correction",
        "wavelet",
        "--gpu-duty",
        str(effective_gpu_duty_percent(config)),
        "--resource-profile",
        config.resource_profile,
    ]
    if config.seedvr2_vae_tiling:
        command += [
            "--vae-tiling",
            "--vae-tile-size",
            str(config.seedvr2_vae_tile_size),
            "--vae-tile-overlap",
            str(config.seedvr2_vae_tile_overlap),
        ]
    return command, runner.parent


def normalize_png_sequence(
    source_dir: str | Path,
    destination_dir: str | Path,
) -> int:
    """Copy/rename PNGs to frame000000.png... for deterministic FFmpeg input."""
    source = Path(source_dir)
    destination = Path(destination_dir)
    files = sorted(source.glob("*.png"))
    if not files:
        raise VideoToolError(f"AI処理結果のPNGが見つかりません: {source}")

    destination.mkdir(parents=True, exist_ok=True)
    for index, item in enumerate(files):
        target = destination / f"frame{index:06d}.png"
        shutil.copy2(item, target)
    return len(files)
