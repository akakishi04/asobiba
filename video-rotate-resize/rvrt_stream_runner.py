from __future__ import annotations

import argparse
import gc
import json
import math
import subprocess
from fractions import Fraction
from pathlib import Path

import numpy as np
import torch
from vsrvrt.model_configs import get_config
from vsrvrt.rvrt_core import RVRTInference

from pause_control import PAUSE_DEEP, PAUSE_SOFT, get_pause_mode, wait_if_paused
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
    tile_size: tuple[int, int, int] | None = None,
) -> torch.Tensor:
    padded, original = _pad_temporal(clip)
    with torch.no_grad():
        output = inference.inference(
            padded,
            tile_size=tile_size,
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
    # RVRT is FP16 on CUDA; keeping the CPU staging tensor in FP16 halves RAM
    # and host-to-device transfer volume without discarding model precision.
    clip = torch.empty((1, chunk_size, 3, height, width), dtype=torch.float16)
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
    pause_file: Path | None,
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

    # One model load for the whole video unless a full-memory pause explicitly
    # unloads it. Full pause reloads the same weights from disk on resume.
    cached_tile_size: tuple[int, int, int] | None = None
    inference: RVRTInference | None = RVRTInference(
        config, use_fp16=True, device=torch.device("cuda")
    )

    def offload_model() -> None:
        if inference is None or inference.model is None:
            return
        inference.model = inference.model.to("cpu")
        torch.cuda.empty_cache()

    def restore_model() -> None:
        if inference is None or inference.model is None:
            return
        inference.model = inference.model.to(inference.device)

    def deep_unload_model() -> None:
        nonlocal inference, cached_tile_size
        if torch.cuda.is_available():
            torch.cuda.synchronize()
        # vsrvrt also keeps a class-level model cache. Remove that reference or
        # the weight tensors remain alive in process RAM after deleting inference.
        try:
            RVRTInference._model_cache.pop(config.task, None)
        except Exception:
            pass
        if inference is not None:
            inference.model = None
        inference = None
        cached_tile_size = None
        gc.collect()
        torch.cuda.empty_cache()
        # Hint Windows to trim the process working set after the large model
        # tensors have been freed, matching SeedVR2's deep cleanup behavior.
        try:
            import ctypes
            import sys

            if sys.platform == "win32":
                kernel32 = ctypes.windll.kernel32
                handle = kernel32.GetCurrentProcess()
                kernel32.SetProcessWorkingSetSize(handle, -1, -1)
        except Exception:
            pass
        print("RVRT: model fully unloaded from GPU/CPU memory", flush=True)

    def deep_reload_model() -> None:
        nonlocal inference
        print("RVRT: reloading model after full pause...", flush=True)
        inference = RVRTInference(
            config, use_fp16=True, device=torch.device("cuda")
        )

    def handle_pause() -> bool:
        mode = get_pause_mode(pause_file)
        if mode == PAUSE_DEEP:
            return wait_if_paused(
                pause_file,
                "RVRT",
                before_wait=deep_unload_model,
                after_wait=deep_reload_model,
                accepted_modes={PAUSE_DEEP},
            )
        if mode == PAUSE_SOFT:
            return wait_if_paused(
                pause_file,
                "RVRT",
                before_wait=offload_model,
                after_wait=restore_model,
                accepted_modes={PAUSE_SOFT},
            )
        return False

    # Honor a pause request made immediately after the stage started.
    handle_pause()

    reader = RawVideoPipeReader(video_path, ffmpeg, width, height, vf)
    writer = LosslessVideoWriter(output_video, ffmpeg, fps, width, height)
    pacer = DutyPacer(gpu_duty)

    print(f"{PROGRESS_PREFIX}|RVRT|0|{estimated_chunks}", flush=True)

    input_tail: torch.Tensor | None = None
    output_tail: torch.Tensor | None = None
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

            # Maximum-speed mode can reuse the first auto-tile decision.
            # Lower-duty profiles stay adaptive so another application taking
            # VRAM can cause RVRT to choose a smaller temporal tile later.
            if inference is None:
                raise RuntimeError("RVRT model is not loaded")
            if gpu_duty >= 100:
                if cached_tile_size is None:
                    cached_tile_size = inference._get_auto_tile_size(clip)
                    print(
                        f"RVRT: cached auto tile {cached_tile_size} for max-speed mode",
                        flush=True,
                    )
                active_tile_size = cached_tile_size
            else:
                active_tile_size = None

            pacer.begin()
            current = _infer_chunk(
                inference,
                clip,
                (height, width),
                tile_size=active_tile_size,
            )

            pause_requested = get_pause_mode(pause_file) is not None
            if pause_requested:
                paused = handle_pause()
                if paused:
                    pacer.begin()
                delay = 0.0
            else:
                delay = pacer.pace()
                if delay >= 0.5:
                    print(
                        f"RVRT: resource pacing {delay:.1f}s idle "
                        f"(target duty {gpu_duty}%)",
                        flush=True,
                    )

            input_tail = next_tail
            del clip
            if gpu_duty < 100:
                # In coexistence modes return allocator cache to other apps.
                torch.cuda.empty_cache()

            wanted_new = chunk_size if chunk_no == 1 else chunk_size - overlap
            is_final_short = new_count < wanted_new

            # Write everything except the outer overlap immediately. Only the
            # boundary tail stays in RAM for blending with the next chunk.
            if output_tail is None:
                if is_final_short or overlap == 0:
                    writer.write(current)
                    output_tail = None
                else:
                    keep = min(overlap, current.shape[1])
                    direct = current.shape[1] - keep
                    if direct:
                        writer.write(current[:, :direct])
                    output_tail = current[:, direct:].contiguous()
            else:
                actual_overlap = min(
                    output_tail.shape[1], current.shape[1], overlap
                )
                if actual_overlap:
                    blended = []
                    tail_offset = output_tail.shape[1] - actual_overlap
                    for j in range(actual_overlap):
                        alpha = (j + 1) / (actual_overlap + 1)
                        blended.append(
                            output_tail[0, tail_offset + j] * (1.0 - alpha)
                            + current[0, j] * alpha
                        )
                    writer.write(torch.stack(blended, dim=0).unsqueeze(0))
                else:
                    writer.write(output_tail)

                remainder = current[:, actual_overlap:]
                if is_final_short or overlap == 0:
                    if remainder.shape[1]:
                        writer.write(remainder)
                    output_tail = None
                else:
                    keep = min(overlap, remainder.shape[1])
                    direct = remainder.shape[1] - keep
                    if direct:
                        writer.write(remainder[:, :direct])
                    output_tail = (
                        remainder[:, direct:].contiguous() if keep else None
                    )

            shown_total = max(estimated_chunks, chunk_no)
            print(f"{PROGRESS_PREFIX}|RVRT|{chunk_no}|{shown_total}", flush=True)

            # A short final chunk means the decoder reached EOF.
            if is_final_short:
                break

        if output_tail is not None:
            writer.write(output_tail)

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
    parser.add_argument("--pause-file", type=Path, default=None)
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
        args.pause_file,
    )


if __name__ == "__main__":
    main()
