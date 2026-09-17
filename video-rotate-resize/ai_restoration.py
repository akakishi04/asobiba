from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Optional

from video_tool import VideoToolError, find_executable, probe_media


AI_MODES = {
    "off": "AIなし",
    "rvrt": "RVRT",
    "seedvr2": "SeedVR2",
    "rvrt_seedvr2": "RVRT → SeedVR2",
}


@dataclass(frozen=True)
class EngineConfig:
    rvrt_repo: Optional[Path] = None
    rvrt_python: Optional[Path] = None
    seedvr2_repo: Optional[Path] = None
    seedvr2_launcher: str = "torchrun"
    seedvr2_extra_args: tuple[str, ...] = ()
    seedvr2_custom_command: tuple[str, ...] = ()


@dataclass(frozen=True)
class RestorationConfig:
    mode: str
    rvrt_task: str = "005_RVRT_videodeblurring_GoPro_16frames"
    rvrt_tile: tuple[int, int, int] = (16, 192, 192)
    rvrt_overlap: tuple[int, int, int] = (2, 20, 20)
    seed: int = 42


@dataclass(frozen=True)
class PipelineStep:
    name: str
    command: tuple[str, ...]
    cwd: Path


def _read_optional_path(value: object) -> Optional[Path]:
    if not value:
        return None
    return Path(str(value)).expanduser()


def _read_string_list(payload: dict, key: str) -> tuple[str, ...]:
    value = payload.get(key, [])
    if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
        raise VideoToolError(f"{key} は文字列配列にしてください。")
    return tuple(value)


def load_engine_config(config_path: str | Path | None = None) -> EngineConfig:
    path = Path(config_path) if config_path else Path(__file__).with_name("ai_engines.json")
    if not path.exists():
        return EngineConfig()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise VideoToolError(f"AI設定を読み込めません: {path}\n{exc}") from exc

    return EngineConfig(
        rvrt_repo=_read_optional_path(payload.get("rvrt_repo")),
        rvrt_python=_read_optional_path(payload.get("rvrt_python")),
        seedvr2_repo=_read_optional_path(payload.get("seedvr2_repo")),
        seedvr2_launcher=str(payload.get("seedvr2_launcher", "torchrun")),
        seedvr2_extra_args=_read_string_list(payload, "seedvr2_extra_args"),
        seedvr2_custom_command=_read_string_list(payload, "seedvr2_custom_command"),
    )


def validate_restoration_config(config: RestorationConfig) -> None:
    if config.mode not in AI_MODES:
        raise VideoToolError(f"未対応のAIモードです: {config.mode}")
    if any(x <= 0 for x in config.rvrt_tile):
        raise VideoToolError("RVRT tile は正の整数にしてください。")
    if any(x < 0 for x in config.rvrt_overlap):
        raise VideoToolError("RVRT overlap は0以上にしてください。")


def _python_path(explicit: Optional[Path]) -> str:
    if explicit:
        if not explicit.is_file():
            raise VideoToolError(f"Python実行ファイルが見つかりません: {explicit}")
        return str(explicit)
    return find_executable("python")


def _require_repo(path: Optional[Path], marker: str, engine_name: str) -> Path:
    if path is None:
        raise VideoToolError(
            f"{engine_name} の場所が未設定です。ai_engines.json を作成して {engine_name} のrepoを指定してください。"
        )
    path = path.resolve()
    if not (path / marker).is_file():
        raise VideoToolError(f"{engine_name} repoが不正です: {path} ({marker} がありません)")
    return path


def build_rvrt_step(engine: EngineConfig, config: RestorationConfig, frames_root: Path) -> PipelineStep:
    repo = _require_repo(engine.rvrt_repo, "main_test_rvrt.py", "RVRT")
    python = _python_path(engine.rvrt_python)
    command = (
        python,
        "main_test_rvrt.py",
        "--task",
        config.rvrt_task,
        "--folder_lq",
        str(frames_root),
        "--tile",
        *(str(x) for x in config.rvrt_tile),
        "--tile_overlap",
        *(str(x) for x in config.rvrt_overlap),
        "--save_result",
    )
    return PipelineStep("RVRT", tuple(command), repo)


def _expand_seedvr2_custom_command(
    template: tuple[str, ...],
    *,
    input_dir: Path,
    output_dir: Path,
    width: int,
    height: int,
    seed: int,
) -> tuple[str, ...]:
    values = {
        "input_dir": str(input_dir),
        "output_dir": str(output_dir),
        "width": str(width),
        "height": str(height),
        "seed": str(seed),
    }
    try:
        return tuple(part.format(**values) for part in template)
    except KeyError as exc:
        raise VideoToolError(f"seedvr2_custom_command に未知のプレースホルダーがあります: {exc}") from exc


def build_seedvr2_step(
    engine: EngineConfig,
    config: RestorationConfig,
    input_dir: Path,
    output_dir: Path,
    width: int,
    height: int,
) -> PipelineStep:
    if engine.seedvr2_custom_command:
        command = _expand_seedvr2_custom_command(
            engine.seedvr2_custom_command,
            input_dir=input_dir,
            output_dir=output_dir,
            width=width,
            height=height,
            seed=config.seed,
        )
        cwd = engine.seedvr2_repo.resolve() if engine.seedvr2_repo else Path.cwd()
        return PipelineStep("SeedVR2(custom)", command, cwd)

    repo = _require_repo(engine.seedvr2_repo, "projects/inference_seedvr2_3b.py", "SeedVR2")
    launcher = engine.seedvr2_launcher.strip() or "torchrun"
    launcher_bin = launcher if Path(launcher).is_absolute() else find_executable(launcher)
    command = (
        launcher_bin,
        "--nproc-per-node=1",
        "projects/inference_seedvr2_3b.py",
        "--video_path",
        str(input_dir),
        "--output_dir",
        str(output_dir),
        "--seed",
        str(config.seed),
        "--res_h",
        str(height),
        "--res_w",
        str(width),
        "--sp_size",
        "1",
        *engine.seedvr2_extra_args,
    )
    return PipelineStep("SeedVR2", tuple(command), repo)


def format_command(command: Iterable[str]) -> str:
    if os.name == "nt":
        return subprocess.list2cmdline(list(command))
    return shlex.join(command)


def run_step(
    step: PipelineStep,
    *,
    on_line: Callable[[str], None],
    register_process: Callable[[Optional[subprocess.Popen[str]]], None],
) -> None:
    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    on_line(f"[{step.name}] {format_command(step.command)}")
    process = subprocess.Popen(
        list(step.command),
        cwd=step.cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        creationflags=creationflags,
    )
    register_process(process)
    try:
        assert process.stdout is not None
        for line in process.stdout:
            text = line.rstrip()
            if text:
                on_line(text)
        code = process.wait()
        if code != 0:
            raise VideoToolError(f"{step.name} が失敗しました (exit code {code})")
    finally:
        register_process(None)


def extract_frames(
    input_path: Path,
    frames_root: Path,
    *,
    ffmpeg: str,
    on_line: Callable[[str], None],
    register_process: Callable[[Optional[subprocess.Popen[str]]], None],
) -> Path:
    clip = frames_root / "clip"
    clip.mkdir(parents=True, exist_ok=True)
    command = [ffmpeg, "-y", "-hide_banner", "-i", str(input_path), "-vsync", "0", str(clip / "%08d.png")]
    run_step(PipelineStep("Frame extract", tuple(command), frames_root), on_line=on_line, register_process=register_process)
    return clip


def encode_frames(
    frames_dir: Path,
    source_video: Path,
    output_path: Path,
    *,
    fps: float,
    encoder: str,
    ffmpeg: str,
    on_line: Callable[[str], None],
    register_process: Callable[[Optional[subprocess.Popen[str]]], None],
) -> None:
    command = [
        ffmpeg,
        "-y",
        "-hide_banner",
        "-framerate",
        f"{fps:.8f}",
        "-i",
        str(frames_dir / "%08d.png"),
        "-i",
        str(source_video),
        "-map",
        "0:v:0",
        "-map",
        "1:a?",
    ]
    if encoder == "nvenc":
        command += ["-c:v", "h264_nvenc", "-preset", "p6", "-tune", "hq", "-rc", "vbr", "-cq", "18", "-b:v", "0"]
    else:
        command += ["-c:v", "libx264", "-preset", "medium", "-crf", "18"]
    command += ["-pix_fmt", "yuv420p", "-c:a", "copy", "-shortest", "-movflags", "+faststart", str(output_path)]
    run_step(PipelineStep("Encode", tuple(command), output_path.parent), on_line=on_line, register_process=register_process)


def rvrt_output_dir(repo: Path, task: str, clip_name: str = "clip") -> Path:
    return repo / "results" / task / clip_name


def find_rvrt_output(repo: Path, task: str, clip_name: str = "clip") -> Path:
    candidate = rvrt_output_dir(repo, task, clip_name)
    if candidate.is_dir() and any(candidate.glob("*.png")):
        return candidate
    raise VideoToolError(f"RVRT出力が見つかりません: {candidate}")


def find_seedvr2_video(output_dir: Path) -> Path:
    videos = sorted(
        [p for p in output_dir.rglob("*") if p.is_file() and p.suffix.lower() in {".mp4", ".mov", ".mkv", ".webm"}],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not videos:
        raise VideoToolError(f"SeedVR2出力動画が見つかりません: {output_dir}")
    return videos[0]


def run_restoration_pipeline(
    input_path: str | Path,
    output_path: str | Path,
    config: RestorationConfig,
    engine: EngineConfig,
    *,
    encoder: str,
    ffmpeg: str | None = None,
    on_line: Callable[[str], None] = print,
    register_process: Callable[[Optional[subprocess.Popen[str]]], None] = lambda _p: None,
) -> None:
    validate_restoration_config(config)
    if config.mode == "off":
        raise VideoToolError("AIモードがoffです。")

    source = Path(input_path).resolve()
    destination = Path(output_path).resolve()
    if source == destination:
        raise VideoToolError("入力と出力は別ファイルにしてください。")
    if not source.is_file():
        raise VideoToolError(f"入力動画がありません: {source}")

    ffmpeg_bin = ffmpeg or find_executable("ffmpeg")
    info = probe_media(source)
    if not info.fps or info.fps <= 0:
        raise VideoToolError("FPSを取得できないためAI復元できません。")

    with tempfile.TemporaryDirectory(prefix="video_ai_restore_") as tmp_raw:
        tmp = Path(tmp_raw)
        current_video = source

        if config.mode in {"rvrt", "rvrt_seedvr2"}:
            frames_root = tmp / "rvrt_input"
            extract_frames(
                current_video,
                frames_root,
                ffmpeg=ffmpeg_bin,
                on_line=on_line,
                register_process=register_process,
            )
            step = build_rvrt_step(engine, config, frames_root)
            output_dir = rvrt_output_dir(step.cwd, config.rvrt_task)
            if output_dir.exists():
                shutil.rmtree(output_dir)
            run_step(step, on_line=on_line, register_process=register_process)
            rvrt_frames = find_rvrt_output(step.cwd, config.rvrt_task)
            rvrt_video = tmp / "rvrt.mp4"
            encode_frames(
                rvrt_frames,
                current_video,
                rvrt_video,
                fps=info.fps,
                encoder=encoder,
                ffmpeg=ffmpeg_bin,
                on_line=on_line,
                register_process=register_process,
            )
            current_video = rvrt_video

        if config.mode in {"seedvr2", "rvrt_seedvr2"}:
            current_info = probe_media(current_video)
            seed_input = tmp / "seedvr2_input"
            seed_output = tmp / "seedvr2_output"
            seed_input.mkdir(parents=True, exist_ok=True)
            seed_output.mkdir(parents=True, exist_ok=True)
            staged = seed_input / current_video.name
            shutil.copy2(current_video, staged)
            step = build_seedvr2_step(
                engine,
                config,
                seed_input,
                seed_output,
                current_info.width,
                current_info.height,
            )
            run_step(step, on_line=on_line, register_process=register_process)
            current_video = find_seedvr2_video(seed_output)

        destination.parent.mkdir(parents=True, exist_ok=True)
        if current_video.resolve() != destination:
            shutil.copy2(current_video, destination)
