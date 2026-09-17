from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Optional


class VideoToolError(RuntimeError):
    pass


@dataclass(frozen=True)
class ProbeInfo:
    width: int
    height: int
    duration_seconds: Optional[float]
    fps: Optional[float]
    codec: str
    rotation: int


def find_executable(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise VideoToolError(
            f"{name} が見つかりません。FFmpeg をインストールし、PATH を通してください。"
        )
    return path


def _ratio_to_float(value: str | None) -> Optional[float]:
    if not value or value in {"0/0", "N/A"}:
        return None
    try:
        return float(Fraction(value))
    except (ValueError, ZeroDivisionError):
        return None


def _extract_rotation(stream: dict) -> int:
    for item in stream.get("side_data_list", []):
        if "rotation" in item:
            try:
                return int(round(float(item["rotation"])))
            except (TypeError, ValueError):
                pass

    tags = stream.get("tags", {})
    if "rotate" in tags:
        try:
            return int(round(float(tags["rotate"])))
        except (TypeError, ValueError):
            pass

    return 0


def probe_media(path: str | Path, ffprobe: str | None = None) -> ProbeInfo:
    source = Path(path)
    if not source.is_file():
        raise VideoToolError(f"入力ファイルが見つかりません: {source}")

    ffprobe_bin = ffprobe or find_executable("ffprobe")
    command = [
        ffprobe_bin,
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_streams",
        "-show_format",
        str(source),
    ]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "ffprobe failed").strip()
        raise VideoToolError(detail) from exc

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise VideoToolError("ffprobe の出力を解析できませんでした。") from exc

    video_stream = next(
        (stream for stream in payload.get("streams", []) if stream.get("codec_type") == "video"),
        None,
    )
    if video_stream is None:
        raise VideoToolError("動画ストリームが見つかりません。")

    duration = None
    for raw in (video_stream.get("duration"), payload.get("format", {}).get("duration")):
        try:
            duration = float(raw)
            break
        except (TypeError, ValueError):
            continue

    return ProbeInfo(
        width=int(video_stream.get("width", 0)),
        height=int(video_stream.get("height", 0)),
        duration_seconds=duration,
        fps=_ratio_to_float(video_stream.get("avg_frame_rate")),
        codec=str(video_stream.get("codec_name", "unknown")),
        rotation=_extract_rotation(video_stream),
    )


def nvenc_available(ffmpeg: str | None = None) -> bool:
    ffmpeg_bin = ffmpeg or find_executable("ffmpeg")
    try:
        result = subprocess.run(
            [ffmpeg_bin, "-hide_banner", "-encoders"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except OSError:
        return False
    return "h264_nvenc" in (result.stdout + result.stderr)


def validate_target_resolution(target: tuple[int, int] | None) -> None:
    if target is None:
        return
    width, height = target
    if width <= 0 or height <= 0:
        raise VideoToolError("出力解像度は正の整数にしてください。")
    if width % 2 or height % 2:
        raise VideoToolError("H.264互換性のため、幅と高さは偶数にしてください。")


def build_video_filter(rotation: str, target: tuple[int, int] | None) -> str:
    filters: list[str] = []
    rotation_filters = {
        "none": None,
        "cw90": "transpose=1",
        "ccw90": "transpose=2",
        "180": "hflip,vflip",
    }
    if rotation not in rotation_filters:
        raise VideoToolError(f"未対応の回転指定です: {rotation}")

    rotate_filter = rotation_filters[rotation]
    if rotate_filter:
        filters.extend(rotate_filter.split(","))

    validate_target_resolution(target)
    if target is not None:
        width, height = target
        filters.append(
            f"scale={width}:{height}:force_original_aspect_ratio=decrease:flags=lanczos"
        )
        filters.append(f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black")

    if filters:
        filters.append("setsar=1")
    return ",".join(filters)


def build_ffmpeg_command(
    input_path: str | Path,
    output_path: str | Path,
    rotation: str,
    target: tuple[int, int] | None,
    encoder: str,
    ffmpeg: str | None = None,
) -> list[str]:
    source = Path(input_path)
    destination = Path(output_path)
    if source.resolve() == destination.resolve():
        raise VideoToolError("入力ファイルと出力ファイルは別の名前にしてください。")
    if encoder not in {"nvenc", "libx264"}:
        raise VideoToolError(f"未対応のエンコーダーです: {encoder}")

    ffmpeg_bin = ffmpeg or find_executable("ffmpeg")
    vf = build_video_filter(rotation, target)

    command = [
        ffmpeg_bin,
        "-y",
        "-hide_banner",
        "-i",
        str(source),
        "-map",
        "0:v:0",
        "-map",
        "0:a?",
        "-map_metadata",
        "0",
    ]

    if vf:
        command += ["-vf", vf]

    if encoder == "nvenc":
        command += [
            "-c:v",
            "h264_nvenc",
            "-preset",
            "p6",
            "-tune",
            "hq",
            "-rc",
            "vbr",
            "-cq",
            "18",
            "-b:v",
            "0",
        ]
    else:
        command += ["-c:v", "libx264", "-preset", "medium", "-crf", "18"]

    command += [
        "-pix_fmt",
        "yuv420p",
        "-metadata:s:v:0",
        "rotate=0",
        "-c:a",
        "copy",
        "-movflags",
        "+faststart",
        "-progress",
        "pipe:1",
        "-nostats",
        str(destination),
    ]
    return command
