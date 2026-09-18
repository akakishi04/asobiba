from __future__ import annotations

import argparse
import json
import math
import subprocess
from fractions import Fraction
from pathlib import Path

import numpy as np
import torch
from vsrvrt.model_configs import get_config
from vsrvrt.rvrt_core import RVRTInference

from resource_policy import DutyPacer


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
    payload = json.loads(result.stdout)
    stream = next(iter(payload.get("streams", [])), {})
    fps = _ratio(stream.get("avg_frame_rate")) or fallback_fps
    if fps <= 0:
        raise RuntimeError("RVRT streaming requires a positive FPS")

    try:
        count = int(stream.get("nb_frames"))
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


class RawVideoPipeReader:
    """Decode the source once and stream transformed RGB24 frames over stdout."""

    def __init__(
        self,
        video_path: Path,
        ffmpeg: str,
        width: int,
        height: int,
        vf: str,
    ):
        self.width = width
        self.height = height
        self.frame_bytes = width * height * 3
        self.closed = False
        command = [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(video_path),
            "-map",
            "0:v:0",
            "-an",
            "-sn",
            "-dn",
        ]
        if vf:
            command += ["-vf", vf]
        command += [
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "pipe:1",
        ]
        self.proc = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
        )

    def read_frame(self) -> bytes | None:
        if self.proc.stdout is None:
            raise RuntimeError("FFmpeg rawvideo stdout is unavailable")
        remaining = self.frame_bytes
        chunks: list[bytes] = []
        while remaining > 0:
            data = self.proc.stdout.read(remaining)
            if not data:
                if not chunks:
                    return None
                raise RuntimeError("FFmpeg rawvideo ended in the middle of a frame")
            chunks.append(data)
            remaining -= len(data)
        return b"".join(chunks)

    def close(self, check: bool) -> None:
        if self.closed:
            return
        self.closed = True
        if self.proc.stdout is not None:
            try:
                self.proc.stdout.close()
            except OSError:
                pass
        if self.proc.poll() is None:
            if check:
                try:
                    self.proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    self.proc.terminate()
                    self.proc.wait(timeout=5)
            else:
                self.proc.terminate()
                try:
                    self.proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
                    self.proc.wait()
        stderr = b""
        if self.proc.stderr is not None:
            stderr = self.proc.stderr.read()
            self.proc.stderr.close()
        if check and self.proc.returncode not in {0, None}:
            detail = stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(detail or f"FFmpeg decoder failed ({self.proc.returncode})")


class LosslessVideoWriter:
    def __init__(self, path: Path, ffmpeg: str, fps: float, width: int, height: int):
        self.path = path
        self.count = 0
        self.closed = False
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
            array = (
                frames[0, i]
                .detach()
                .float()
                .clamp_(0.0, 1.0)
                .permute(1, 2, 0)
                .cpu()
                .numpy()
            )
            self.proc.stdin.write(np.rint(array * 255.0).astype(np.uint8).tobytes())
            self.count += 1

    def close(self, check: bool = True) -> None:
        if self.closed:
            return
        self.closed = True
        if self.proc.stdin is not None and not self.proc.stdin.closed:
            self.proc.stdin.close()
        stderr = b""
        if self.proc.stderr is not None:
            stderr = self.proc.stderr.read()
        code = self.proc.wait()
        if check and code:
            detail = stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(detail or f"FFV1 writer failed (code {code})")


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


def _read_chunk(
    reader: RawVideoPipeReader,
    tail: torch.Tensor | None,
    chunk_size: int,
    overlap: int,
    width: int,
    height: int,
) -> tuple[torch.Tensor | None, torch.Tensor | None, int]:
    tail_len = 0 if tail is None else int(tail.shape[1])
    wanted_new = chunk_size - tail_len
    clip = torch.empty((1, chunk_size, 3, height, width), dtype=torch.float32)
    if tail is not None and tail_len:
        clip[:, :tail_len].copy_(tail)

    new_count = 0
    for offset in range(wanted_new):
        data = reader.read_frame()
        if data is None:
            break
        array = np.frombuffer(data, dtype=np.uint8).reshape(height, width, 3)
        source = torch.from_numpy(array.copy()).permute(2, 0, 1)
        target = clip[0, tail_len + offset]
        target.copy_(source)
        target.mul_(1.0 / 255.0)
        new_count += 1

    if new_count == 0:
        return None, None, 0

    actual = tail_len + new_count
    clip = clip[:, :actual].contiguous()
    keep = min(overlap, actual)
    next_tail = clip[:, actual - keep : actual].clone() if keep else None
    return clip, next_tail, new_count


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
    width: int,
    height: int,
    gpu_duty: int,
) -> None:
    if chunk_size < 4:
        raise ValueError("chunk_size must be >= 4")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must satisfy 0 <= overlap < chunk_size")
    if width <= 0 or height <= 0:
        raise ValueError("width/height must be positive")
    if not video_path.is_file():
        raise RuntimeError(f"Input video not found: {video_path}")

    total_frames, fps, count_is_exact = _probe_frame_count(
        video_path, ffprobe, fallback_fps
    )
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
        f"RVRT pipe streaming: {task} / "
        f"{'exact' if count_is_exact else 'estimated'} {total_frames} frames / "
        f"chunk={chunk_size} overlap={overlap} / duty={gpu_duty}% / "
        f"GPU={torch.cuda.get_device_name(0)} / fp16",
        flush=True,
    )

    # One model load and one decoder process for the entire video.
    inference = RVRTInference(config, use_fp16=True, device=torch.device("cuda"))
    reader = RawVideoPipeReader(video_path, ffmpeg, width, height, vf)
    writer = LosslessVideoWriter(output_video, ffmpeg, fps, width, height)
    pacer = DutyPacer(gpu_duty)

    print(f"{PROGRESS_PREFIX}|RVRT|0|{estimated_chunks}", flush=True)

    input_tail: torch.Tensor | None = None
    pending_start: int | None = None
    pending: torch.Tensor | None = None
    unique_read = 0
    chunk_no = 0
    normal_reader_close = False

    try:
        while True:
            start = unique_read - (0 if input_tail is None else input_tail.shape[1])
            clip, next_tail, new_count = _read_chunk(
                reader,
                input_tail,
                chunk_size,
                overlap,
                width,
                height,
            )
            if clip is None or new_count <= 0:
                break

            unique_read += new_count
            chunk_no += 1
            print(
                f"RVRT: chunk {chunk_no}/{max(estimated_chunks, chunk_no)} "
                f"frames {start}-{start + clip.shape[1] - 1}",
                flush=True,
            )

            pacer.begin()
            current = _infer_chunk(inference, clip, (height, width))
            delay = pacer.pace()
            if delay >= 0.5:
                print(
                    f"RVRT: resource pacing {delay:.1f}s idle "
                    f"(target duty {gpu_duty}%)",
                    flush=True,
                )

            input_tail = next_tail
            del clip
            torch.cuda.empty_cache()

            if pending is None or pending_start is None:
                pending_start = int(start)
                pending = current
            else:
                pending_end = pending_start + pending.shape[1]
                actual_overlap = max(0, pending_end - int(start))
                actual_overlap = min(
                    actual_overlap, pending.shape[1], current.shape[1]
                )

                if actual_overlap == 0:
                    writer.write(pending)
                    pending_start = int(start)
                    pending = current
                else:
                    direct_count = pending.shape[1] - actual_overlap
                    if direct_count:
                        writer.write(pending[:, :direct_count])

                    blended = []
                    for j in range(actual_overlap):
                        alpha = (j + 1) / (actual_overlap + 1)
                        blended.append(
                            pending[0, direct_count + j] * (1.0 - alpha)
                            + current[0, j] * alpha
                        )
                    if blended:
                        writer.write(torch.stack(blended, dim=0).unsqueeze(0))
                    pending_start = int(start) + actual_overlap
                    pending = current[:, actual_overlap:].contiguous()
                    del current

            shown_total = max(estimated_chunks, chunk_no)
            print(f"{PROGRESS_PREFIX}|RVRT|{chunk_no}|{shown_total}", flush=True)

            # A short final chunk means the decoder reached EOF.
            wanted_new = chunk_size if chunk_no == 1 else chunk_size - overlap
            if new_count < wanted_new:
                break

        if pending is not None:
            writer.write(pending)

        reader.close(check=True)
        normal_reader_close = True
        writer.close(check=True)

        produced = writer.count
        if count_is_exact and produced != total_frames:
            raise RuntimeError(
                f"RVRT output frame count mismatch: {produced} != {total_frames}"
            )
        print(
            f"RVRT pipe streaming completed: {produced} frames -> {output_video}",
            flush=True,
        )
    finally:
        if not normal_reader_close:
            try:
                reader.close(check=False)
            except Exception:
                pass
        try:
            writer.close(check=False)
        except Exception:
            pass


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Pipe-streamed RVRT 1x video restoration runner"
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
    parser.add_argument("--width", required=True, type=int)
    parser.add_argument("--height", required=True, type=int)
    parser.add_argument("--gpu-duty", type=int, default=100)
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
        args.width,
        args.height,
        args.gpu_duty,
    )


if __name__ == "__main__":
    main()
