from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path

from video_tool import VideoToolError, find_executable


# Keep the source container so existing video/audio/subtitle codecs can be copied.
CONTAINERS = {
    ".mp4": "mp4",
    ".m4v": "mp4",
    ".mov": "mov",
    ".mkv": "matroska",
    ".avi": "avi",
    ".webm": "webm",
}
VIDEO_EXTENSIONS = frozenset(CONTAINERS)
_LAST_TIME_PART = re.compile(r"\d+(?:\.\d+)?\Z")


@dataclass(frozen=True)
class CutRange:
    start: Decimal
    end: Decimal


def parse_timecode(raw: str) -> Decimal:
    """Accept seconds, MM:SS[.mmm], or HH:MM:SS[.mmm]."""
    parts = raw.strip().split(":")
    if not 1 <= len(parts) <= 3:
        raise VideoToolError(f"時刻形式が不正です: {raw!r}")
    if not _LAST_TIME_PART.fullmatch(parts[-1]) or not all(
        p.isascii() and p.isdecimal() for p in parts[:-1]
    ):
        raise VideoToolError(f"時刻形式が不正です: {raw!r}")
    try:
        seconds = Decimal(parts[-1])
        if len(parts) >= 2:
            if seconds >= 60:
                raise VideoToolError(f"秒は60未満にしてください: {raw!r}")
            seconds += Decimal(int(parts[-2])) * 60
        if len(parts) == 3:
            if int(parts[-2]) >= 60:
                raise VideoToolError(f"分は60未満にしてください: {raw!r}")
            seconds += Decimal(int(parts[0])) * 3600
    except (ValueError, InvalidOperation) as exc:
        raise VideoToolError(f"時刻形式が不正です: {raw!r}") from exc
    if not seconds.is_finite() or seconds > Decimal("10000000"):
        raise VideoToolError("時刻が大きすぎます。")
    return seconds


def parse_cut_ranges(raw: str, duration: float | None = None) -> list[CutRange]:
    result = []
    for line_number, line in enumerate(raw.splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = re.split(r"\s*[-–〜～]\s*", line, maxsplit=1)
        if len(parts) != 2:
            raise VideoToolError(f"{line_number}行目: 開始 - 終了 の形式で入力してください。")
        try:
            start, end = (parse_timecode(part) for part in parts)
        except VideoToolError as exc:
            raise VideoToolError(f"{line_number}行目: {exc}") from exc
        if end <= start:
            raise VideoToolError(f"{line_number}行目: 終了は開始より後にしてください。")
        if duration is not None and duration > 0:
            if end > Decimal(str(duration)) + Decimal("0.5"):
                raise VideoToolError(f"{line_number}行目: 終了が元動画の長さを超えています。")
        result.append(CutRange(start, end))
        if len(result) > 1000:
            raise VideoToolError("指定範囲は1000件までです。")
    if not result:
        raise VideoToolError("切り出し範囲を1行以上入力してください。")
    return result


def validate_prefix(raw: str) -> str:
    value = raw.strip()
    if (
        not value
        or value in {".", ".."}
        or value.endswith(".")
        or any(ch in '<>:"/\\|?*' or ord(ch) < 32 for ch in value)
    ):
        raise VideoToolError("出力名には使用できない文字が含まれています。")
    return value


def _extension(path: str | Path) -> str:
    suffix = Path(path).suffix.lower()
    if suffix not in VIDEO_EXTENSIONS:
        raise VideoToolError(
            f"ストリームコピー対象外の拡張子です: {suffix or '(なし)'}"
        )
    return suffix


def _seconds(value: Decimal) -> str:
    return format(value, "f")


def build_copy_cut_command(
    source: str | Path,
    destination: str | Path,
    cut: CutRange,
    ffmpeg: str | None = None,
) -> list[str]:
    """Copy all streams for a requested interval; may start at an earlier keyframe."""
    src, dst = Path(source), Path(destination)
    if src.resolve() == dst.resolve():
        raise VideoToolError("入力動画を上書きすることはできません。")
    if _extension(src) != _extension(dst):
        raise VideoToolError("出力は入力と同じコンテナ拡張子にしてください。")
    if cut.start < 0 or cut.end <= cut.start:
        raise VideoToolError("切り出し範囲が不正です。")

    return [
        ffmpeg or find_executable("ffmpeg"),
        "-hide_banner", "-nostdin", "-n",
        "-ss", _seconds(cut.start),
        "-i", str(src),
        "-t", _seconds(cut.end - cut.start),
        "-map", "0",
        "-map_metadata", "0",
        "-map_chapters", "-1",
        "-c", "copy",
        "-avoid_negative_ts", "make_zero",
        "-progress", "pipe:1", "-nostats",
        str(dst),
    ]


def build_copy_segment_command(
    source: str | Path,
    output_pattern: str | Path,
    interval: Decimal,
    ffmpeg: str | None = None,
) -> list[str]:
    """Split into sequential parts without decoding or changing codecs."""
    src, dst = Path(source), Path(output_pattern)
    suffix = _extension(src)
    if _extension(dst) != suffix:
        raise VideoToolError("出力は入力と同じコンテナ拡張子にしてください。")
    if "%03d" not in dst.name:
        raise VideoToolError("自動分割の出力名には %03d が必要です。")
    if not interval.is_finite() or interval <= 0:
        raise VideoToolError("分割間隔は0より大きくしてください。")

    return [
        ffmpeg or find_executable("ffmpeg"),
        "-hide_banner", "-nostdin", "-n",
        "-i", str(src),
        "-map", "0",
        "-map_metadata", "0",
        "-c", "copy",
        "-f", "segment",
        "-segment_format", CONTAINERS[suffix],
        "-segment_time", _seconds(interval),
        "-segment_start_number", "1",
        "-reset_timestamps", "1",
        "-progress", "pipe:1", "-nostats",
        str(dst),
    ]
