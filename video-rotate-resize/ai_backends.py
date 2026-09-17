from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path

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
    rvrt_repo: str = ""
    rvrt_python: str = ""
    rvrt_task: str = "005_RVRT_videodeblurring_GoPro_16frames"
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
    if mode in {AI_RVRT, AI_RVRT_SEEDVR2}:
        _require_repo(config.rvrt_repo, "main_test_rvrt.py", "RVRT")
        resolve_python(config.rvrt_python)
        if config.rvrt_task not in set(RVRT_TASKS.values()):
            raise VideoToolError(f"未対応のRVRTタスクです: {config.rvrt_task}")

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


def build_rvrt_command(
    config: AIConfig,
    folder_lq_root: str | Path,
) -> tuple[list[str], Path]:
    repo = _require_repo(config.rvrt_repo, "main_test_rvrt.py", "RVRT")
    python_bin = resolve_python(config.rvrt_python)
    command = [
        python_bin,
        str(repo / "main_test_rvrt.py"),
        "--task",
        config.rvrt_task,
        "--folder_lq",
        str(folder_lq_root),
        "--tile",
        "0",
        "256",
        "256",
        "--tile_overlap",
        "2",
        "20",
        "20",
        "--num_workers",
        "0",
        "--save_result",
    ]
    return command, repo


def build_seedvr2_command(
    config: AIConfig,
    input_video: str | Path,
    output_dir: str | Path,
    native_short_side: int,
) -> tuple[list[str], Path]:
    repo = _require_repo(config.seedvr2_repo, "inference_cli.py", "SeedVR2")
    python_bin = resolve_python(config.seedvr2_python)
    resolution = config.seedvr2_resolution_override or native_short_side
    if resolution <= 0:
        raise VideoToolError("SeedVR2の処理解像度を決定できません。")

    command = [
        python_bin,
        str(repo / "inference_cli.py"),
        "--video_path",
        str(input_video),
        "--resolution",
        str(resolution),
        "--batch_size",
        str(config.seedvr2_batch_size),
        "--model",
        config.seedvr2_model,
        "--output",
        str(output_dir),
        "--output_format",
        "png",
        "--color_correction",
        "wavelet",
        "--blocks_to_swap",
        str(config.seedvr2_blocks_to_swap),
        "--temporal_overlap",
        str(config.seedvr2_temporal_overlap),
        "--preserve_vram",
        "--offload_io_components",
    ]
    if config.seedvr2_vae_tiling:
        command += [
            "--vae_tiling_enabled",
            "--vae_tile_size",
            str(config.seedvr2_vae_tile_size),
            "--vae_tile_overlap",
            str(config.seedvr2_vae_tile_overlap),
        ]
    return command, repo


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


def rvrt_result_dir(config: AIConfig, clip_name: str) -> Path:
    repo = Path(config.rvrt_repo)
    return repo / "results" / config.rvrt_task / clip_name
