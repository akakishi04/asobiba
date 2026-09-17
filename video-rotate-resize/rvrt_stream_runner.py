from __future__ import annotations

import argparse
import json
import math
import subprocess
import tempfile
from fractions import Fraction
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from vsrvrt.model_configs import get_config
from vsrvrt.rvrt_core import RVRTInference


PROGRESS_PREFIX = "APP_PROGRESS"


def _ratio(value: str | None) -> float | None:
    if not value or value in {"0/0", "N/A"}:
        return None
    try:
        return float(Fraction(value))
    except (ValueError, ZeroDivisionError):
        return None


def _probe_frame_count(
    video_path: Path,
    ffprobe: str,
    fallback_fps: float,
) -> tuple[int, float, bool]:
    command = [
        ffprobe,
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=nb_frames,duration,avg_frame_rate:format=duration",
        "-of",
        "json",
        str(video_path),
    ]
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode:
        raise RuntimeError((result.stderr or result.stdout or "ffprobe failed").strip())
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("ffprobe output could not be parsed") from exc

    stream = next(iter(payload.get("streams", [])), {})
    fps = _ratio(stream.get("avg_frame_rate")) or fallback_fps
    if fps <= 0:
        raise RuntimeError("RVRT streaming requires a positive FPS")

    raw_count = stream.get("nb_frames")
    try:
        count = int(raw_count)
        if count > 0:
            return count, fps, True
    except (TypeError, ValueError):
        pass

    duration = None
    for raw in (stream.get("duration"), payload.get("format", {}).get("duration")):
        try:
            duration = float(raw)
            if duration > 0:
                break
        except (TypeError, ValueError):
            duration = None
    if not duration:
        raise RuntimeError("Could not determine video frame count or duration")
    return max(1, int(round(duration * fps))), fps, False


def _chunk_count(total_frames: int, chunk_size: int, overlap: int) -> int:
    if total_frames <= chunk_size:
        return 1
    stride = chunk_size - overlap
    return 1 + int(math.ceil((total_frames - chunk_size) / stride))


def _extract_chunk(
    video_path: Path,
    output_dir: Path,
    start_frame: int,
    frame_count: int,
    fps: float,
    ffmpeg: str,
    vf: str,
) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    start_seconds = start_frame / fps
    command = [
        ffmpeg,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        f"{start_seconds:.9f}",
        "-i",
        str(video_path),
        "-map",
        "0:v:0",
        "-an",
        "-sn",
        "-dn",
        "-frames:v",
        str(frame_count),
    ]
    if vf:
        command += ["-vf", vf]
    command += [
        "-fps_mode",
        "passthrough",
        "-start_number",
        "0",
        str(output_dir / "frame%06d.png"),
    ]
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode:
        raise RuntimeError((result.stderr or result.stdout or "FFmpeg chunk extract failed").strip())
    return sorted(output_dir.glob("*.png"))


def _load_frames(paths: list[Path]) -> torch.Tensor:
    frames: list[torch.Tensor] = []
    expected: tuple[int, int] | None = None
    for path in paths:
        with Image.open(path) as image:
            rgb = image.convert("RGB")
            if expected is None:
                expected = rgb.size
            elif rgb.size != expected:
                raise RuntimeError(
                    f"Frame size mismatch: {path} is {rgb.size}, expected {expected}"
                )
            array = np.asarray(rgb, dtype=np.float32) / 255.0
        frames.append(torch.from_numpy(array).permute(2, 0, 1).contiguous())
    if not frames:
        raise RuntimeError("No frames were extracted for RVRT chunk")
    return torch.stack(frames, dim=0).unsqueeze(0)


def _pad_temporal(clip: torch.Tensor, minimum: int = 4) -> tuple[torch.Tensor, int]:
    original = clip.shape[1]
    target = max(minimum, int(math.ceil(original / 2.0) * 2))
    if target == original:
        return clip, original
    last = clip[:, -1:, ...]
    return torch.cat([clip, last.repeat(1, target - original, 1, 1, 1)], dim=1), original


def _infer_chunk(
    inference: RVRTInference,
    clip: torch.Tensor,
    input_hw: tuple[int, int],
) -> torch.Tensor:
    padded, original = _pad_temporal(clip)
    with torch.no_grad():
        output = inference.inference(
            padded,
            tile_size=None,
            tile_overlap=(2, 20, 20),
        )
    output = output[:, :original, ...].float().cpu()
    height, width = input_hw
    if output.shape[-2] != height or output.shape[-1] != width:
        print(
            f"RVRT: crop padded output {output.shape[-1]}x{output.shape[-2]} -> {width}x{height}",
            flush=True,
        )
        output = output[..., :height, :width]
    return output


def _tensor_to_rgb24(frame: torch.Tensor) -> bytes:
    array = (
        frame.detach()
        .float()
        .clamp_(0.0, 1.0)
        .permute(1, 2, 0)
        .cpu()
        .numpy()
    )
    return np.rint(array * 255.0).astype(np.uint8).tobytes()


class LosslessVideoWriter:
    def __init__(self, path: Path, ffmpeg: str, fps: float, width: int, height: int):
        self.path = path
        self.count = 0
        command = [
            ffmpeg,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-s",
            f"{width}x{height}",
            "-r",
            f"{fps:.8f}",
            "-i",
            "pipe:0",
            "-an",
            "-c:v",
            "ffv1",
            "-level",
            "3",
            "-pix_fmt",
            "yuv444p",
            str(path),
        ]
        self.proc = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )

    def write(self, frames: torch.Tensor) -> None:
        if self.proc.stdin is None:
            raise RuntimeError("FFV1 writer stdin is unavailable")
        for i in range(frames.shape[1]):
            self.proc.stdin.write(_tensor_to_rgb24(frames[0, i]))
            self.count += 1

    def close(self) -> None:
        if self.proc.stdin is not None and not self.proc.stdin.closed:
            self.proc.stdin.close()
        stderr = b""
        if self.proc.stderr is not None:
            stderr = self.proc.stderr.read()
        code = self.proc.wait()
        if code:
            detail = stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(detail or f"FFV1 writer failed (code {code})")


def run(
    video_path: Path,
    output_video: Path,
    task: str,
    chunk_size: int,
    overlap: int,
    ffmpeg: str,
    ffprobe: str,
    fallback_fps: float,
    vf: str,
) -> None:
    if chunk_size < 4:
        raise ValueError("chunk_size must be >= 4")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must satisfy 0 <= overlap < chunk_size")
    if not video_path.is_file():
        raise RuntimeError(f"Input video not found: {video_path}")

    total_frames, fps, count_is_exact = _probe_frame_count(video_path, ffprobe, fallback_fps)
    estimated_chunks = _chunk_count(total_frames, chunk_size, overlap)

    if not torch.cuda.is_available():
        raise RuntimeError("RVRT requires CUDA, but torch.cuda.is_available() is False")
    config = get_config(task)
    if config.upscale != 1:
        raise RuntimeError("This runner is restricted to RVRT 1x restoration tasks")

    output_video.parent.mkdir(parents=True, exist_ok=True)
    if output_video.exists():
        output_video.unlink()

    print(
        f"RVRT streaming: {task} / {'exact' if count_is_exact else 'estimated'} {total_frames} frames / "
        f"chunk={chunk_size} overlap={overlap} / GPU={torch.cuda.get_device_name(0)} / fp16",
        flush=True,
    )
    inference = RVRTInference(config, use_fp16=True, device=torch.device("cuda"))
    print(f"{PROGRESS_PREFIX}|RVRT|0|{estimated_chunks}", flush=True)

    writer: LosslessVideoWriter | None = None
    pending_start: int | None = None
    pending: torch.Tensor | None = None
    input_hw: tuple[int, int] | None = None
    stride = chunk_size - overlap
    start = 0
    chunk_no = 0
    last_extracted = False

    try:
        while True:
            if count_is_exact and start >= total_frames:
                break
            requested = chunk_size
            if count_is_exact:
                requested = min(requested, total_frames - start)
            if requested <= 0:
                break

            chunk_no += 1
            print(
                f"RVRT: extract chunk {chunk_no}/{estimated_chunks} frames {start}-{start + requested - 1}",
                flush=True,
            )
            with tempfile.TemporaryDirectory(prefix=".rvrt_chunk_", dir=output_video.parent) as td:
                paths = _extract_chunk(
                    video_path,
                    Path(td),
                    start,
                    requested,
                    fps,
                    ffmpeg,
                    vf,
                )
                if not paths:
                    break
                actual = len(paths)
                clip = _load_frames(paths)

            if input_hw is None:
                input_hw = (clip.shape[-2], clip.shape[-1])
                writer = LosslessVideoWriter(
                    output_video,
                    ffmpeg,
                    fps,
                    input_hw[1],
                    input_hw[0],
                )
            current = _infer_chunk(inference, clip, input_hw)
            del clip
            torch.cuda.empty_cache()

            if pending is None or pending_start is None:
                pending_start = start
                pending = current
            else:
                if writer is None:
                    raise RuntimeError("RVRT output writer was not initialized")
                pending_end = pending_start + pending.shape[1]
                actual_overlap = max(0, pending_end - start)
                actual_overlap = min(actual_overlap, pending.shape[1], current.shape[1])

                if actual_overlap == 0:
                    writer.write(pending)
                    pending_start = start
                    pending = current
                else:
                    direct_count = pending.shape[1] - actual_overlap
                    if direct_count:
                        writer.write(pending[:, :direct_count])
                    blends = []
                    for j in range(actual_overlap):
                        alpha = (j + 1) / (actual_overlap + 1)
                        blends.append(
                            pending[0, direct_count + j] * (1.0 - alpha)
                            + current[0, j] * alpha
                        )
                    if blends:
                        writer.write(torch.stack(blends, dim=0).unsqueeze(0))
                    pending_start = start + actual_overlap
                    pending = current[:, actual_overlap:].contiguous()
                    del current

            shown_total = max(estimated_chunks, chunk_no)
            print(f"{PROGRESS_PREFIX}|RVRT|{chunk_no}|{shown_total}", flush=True)

            if actual < requested:
                last_extracted = True
                break
            if count_is_exact and start + actual >= total_frames:
                break
            start += stride

        if pending is not None:
            if writer is None:
                raise RuntimeError("RVRT output writer was not initialized")
            writer.write(pending)

        if writer is None:
            raise RuntimeError("RVRT produced no output frames")
        writer.close()
        produced = writer.count
        writer = None

        if count_is_exact and produced != total_frames:
            raise RuntimeError(f"RVRT output frame count mismatch: {produced} != {total_frames}")
        print(
            f"RVRT streaming completed: {produced} frames -> {output_video}"
            + ("" if count_is_exact or last_extracted else " (frame count was estimated)"),
            flush=True,
        )
    finally:
        if writer is not None:
            try:
                writer.close()
            except Exception:
                pass


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Memory/disk-bounded RVRT 1x video restoration runner"
    )
    parser.add_argument("--video-path", required=True, type=Path)
    parser.add_argument("--output-video", required=True, type=Path)
    parser.add_argument("--task", required=True)
    parser.add_argument("--chunk-size", type=int, default=16)
    parser.add_argument("--chunk-overlap", type=int, default=4)
    parser.add_argument("--ffmpeg", required=True)
    parser.add_argument("--ffprobe", required=True)
    parser.add_argument("--fps", required=True, type=float)
    parser.add_argument("--vf", default="")
    args = parser.parse_args()
    run(
        args.video_path,
        args.output_video,
        args.task,
        args.chunk_size,
        args.chunk_overlap,
        args.ffmpeg,
        args.ffprobe,
        args.fps,
        args.vf,
    )


if __name__ == "__main__":
    main()
