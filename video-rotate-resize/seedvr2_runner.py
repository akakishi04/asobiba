from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

# Must be set before torch is imported so cudaMallocAsync is actually selected.
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "backend:cudaMallocAsync")

import cv2
import numpy as np
import torch

from pause_control import wait_if_paused
from resource_policy import DutyPacer, PROFILE_BACKGROUND, PROFILE_BALANCED


PROGRESS_PREFIX = "APP_PROGRESS"


def _chunk_count(total: int, chunk_size: int, overlap: int) -> int:
    if total <= chunk_size:
        return 1
    stride = chunk_size - overlap
    return 1 + (max(0, total - chunk_size) + stride - 1) // stride


def _apply_temporal_overlap_blending(
    frames_tensor: torch.Tensor,
    batch_size: int,
    overlap: int,
) -> torch.Tensor:
    """Equivalent to the pinned upstream CLI post-pass, kept local for stability."""
    total = frames_tensor.shape[0]
    if overlap <= 0 or batch_size <= overlap or total <= batch_size:
        return frames_tensor

    output = frames_tensor[:batch_size]
    input_pos = batch_size
    while input_pos < total:
        remaining = total - input_pos
        current_size = min(batch_size, remaining)
        if current_size <= overlap:
            break
        current = frames_tensor[input_pos : input_pos + current_size]
        prev_tail = output[-overlap:]
        cur_head = current[:overlap]

        if overlap >= 3:
            t = torch.linspace(
                0.0, 1.0, steps=overlap, dtype=frames_tensor.dtype
            )
            u = ((t - 1.0 / 3.0) / (1.0 / 3.0)).clamp(0.0, 1.0)
            w_prev = (0.5 + 0.5 * torch.cos(torch.pi * u)).view(
                overlap, 1, 1, 1
            )
        else:
            w_prev = torch.linspace(
                1.0, 0.0, steps=overlap, dtype=frames_tensor.dtype
            ).view(overlap, 1, 1, 1)
        blended = prev_tail * w_prev + cur_head * (1.0 - w_prev)
        output = torch.cat([output[:-overlap], blended], dim=0)
        if overlap < current_size:
            output = torch.cat([output, current[overlap:]], dim=0)
        input_pos += current_size
    return output


class SequentialVideoReader:
    """Read the source once; never re-scan earlier frames for later chunks."""

    def __init__(self, path: Path):
        self.cap = cv2.VideoCapture(str(path))
        if not self.cap.isOpened():
            raise RuntimeError(f"Cannot open video: {path}")
        self.total = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.fps = float(self.cap.get(cv2.CAP_PROP_FPS) or 0.0)
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if self.total <= 0 or self.width <= 0 or self.height <= 0:
            self.cap.release()
            raise RuntimeError(f"Cannot determine video geometry/frame count: {path}")

    def read_chunk(
        self,
        tail: torch.Tensor | None,
        chunk_size: int,
        overlap: int,
    ) -> tuple[torch.Tensor | None, torch.Tensor | None, int]:
        tail_len = 0 if tail is None else int(tail.shape[0])
        wanted_new = chunk_size - tail_len
        frames = torch.empty(
            (chunk_size, self.height, self.width, 3),
            dtype=torch.float16,
        )
        if tail is not None and tail_len:
            frames[:tail_len].copy_(tail)

        new_count = 0
        for i in range(wanted_new):
            ok, frame = self.cap.read()
            if not ok:
                break
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            target = frames[tail_len + i]
            target.copy_(torch.from_numpy(rgb))
            target.mul_(1.0 / 255.0)
            new_count += 1

        if new_count == 0:
            return None, None, 0

        actual = tail_len + new_count
        frames = frames[:actual].contiguous()
        keep = min(overlap, actual)
        next_tail = frames[actual - keep : actual].clone() if keep else None
        return frames, next_tail, new_count

    def close(self) -> None:
        self.cap.release()


class LosslessVideoWriter:
    def __init__(self, path: Path, fps: float, width: int, height: int):
        self.path = path
        self.count = 0
        self.closed = False
        ffmpeg = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
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
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        self.proc = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            creationflags=flags,
        )

    def write(self, frames: torch.Tensor) -> None:
        if self.proc.stdin is None:
            raise RuntimeError("FFV1 writer stdin is unavailable")
        array = (
            frames.detach()
            .float()
            .clamp_(0.0, 1.0)
            .mul_(255.0)
            .round_()
            .to(torch.uint8)
            .cpu()
            .numpy()
        )
        for frame in array:
            self.proc.stdin.write(frame.tobytes())
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


def _configure_cpu_threads(profile: str) -> None:
    if profile == PROFILE_BACKGROUND:
        torch.set_num_threads(2)
    elif profile == PROFILE_BALANCED:
        torch.set_num_threads(min(4, max(1, os.cpu_count() or 1)))


def _load_seed_modules(repo: Path):
    repo_text = str(repo)
    if repo_text not in sys.path:
        sys.path.insert(0, repo_text)

    from src.core.generation import (
        decode_all_batches,
        encode_all_batches,
        prepare_generation_context,
        prepare_runner,
        setup_device_environment,
        upscale_all_batches,
    )
    from src.optimization.memory_manager import complete_cleanup, manage_model_device
    from src.utils.debug import Debug
    from src.utils.downloads import download_weight

    return {
        "decode": decode_all_batches,
        "encode": encode_all_batches,
        "prepare_context": prepare_generation_context,
        "prepare_runner": prepare_runner,
        "setup_device": setup_device_environment,
        "upscale": upscale_all_batches,
        "cleanup": complete_cleanup,
        "manage_model_device": manage_model_device,
        "Debug": Debug,
        "download_weight": download_weight,
    }


def run(args: argparse.Namespace) -> None:
    video = args.video_path.resolve()
    repo = args.repo.resolve()
    output_video = args.output_video.resolve()
    if not video.is_file():
        raise RuntimeError(f"Input video not found: {video}")
    if not (repo / "inference_cli.py").is_file():
        raise RuntimeError(f"SeedVR2 repo is invalid: {repo}")
    if args.chunk_size < 5 or args.chunk_overlap < 0:
        raise ValueError("Invalid SeedVR2 chunk settings")
    if args.chunk_overlap >= args.chunk_size:
        raise ValueError("chunk overlap must be smaller than chunk size")

    os.environ["PYTHONUTF8"] = "1"
    os.environ["PYTHONIOENCODING"] = "utf-8"
    os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "backend:cudaMallocAsync")
    _configure_cpu_threads(args.resource_profile)

    modules = _load_seed_modules(repo)
    debug = modules["Debug"](enabled=False)
    model_dir = repo / "seedvr2_models"
    model_dir.mkdir(parents=True, exist_ok=True)

    reader = SequentialVideoReader(video)
    total = reader.total
    fps = reader.fps if reader.fps > 0 else args.fps
    if fps <= 0:
        reader.close()
        raise RuntimeError("SeedVR2 requires a positive FPS")
    chunks = _chunk_count(total, args.chunk_size, args.chunk_overlap)

    print(
        f"SeedVR2 persistent runner: {total} frames / {chunks} chunks / "
        f"chunk={args.chunk_size} overlap={args.chunk_overlap} / "
        f"batch={args.batch_size} / BlockSwap={args.blocks_to_swap} / "
        f"duty={args.gpu_duty}% / profile={args.resource_profile}",
        flush=True,
    )
    print(f"{PROGRESS_PREFIX}|SeedVR2|0|{chunks}", flush=True)

    # Download once, load once, reuse the same runner for every outer chunk.
    modules["download_weight"](args.model, str(model_dir))
    device = modules["setup_device"]("cuda:0", debug)
    runner, _ = modules["prepare_runner"](
        args.model,
        str(model_dir),
        True,
        debug,
        cache_model=True,
        block_swap_config={
            "blocks_to_swap": args.blocks_to_swap,
            "use_none_blocking": False,
            "offload_io_components": True,
            "cache_model": True,
        },
        vae_tiling_enabled=args.vae_tiling,
        vae_tile_size=(args.vae_tile_size, args.vae_tile_size),
        vae_tile_overlap=(args.vae_tile_overlap, args.vae_tile_overlap),
        cached_runner=None,
    )

    def offload_all_models() -> None:
        for model, name in ((runner.vae, "VAE"), (runner.dit, "DiT")):
            modules["manage_model_device"](
                model=model,
                target_device="cpu",
                model_name=name,
                preserve_vram=True,
                debug=debug,
                runner=runner,
            )
        torch.cuda.empty_cache()

    # If pause was requested while the model was loading, stop before decoding
    # any video frames and release model VRAM first.
    wait_if_paused(
        args.pause_file,
        "SeedVR2",
        before_wait=offload_all_models,
    )

    pacer = DutyPacer(args.gpu_duty)
    writer: LosslessVideoWriter | None = None
    input_tail: torch.Tensor | None = None
    output_tail: torch.Tensor | None = None
    unique_read = 0
    chunk_no = 0

    def pace_callback(current: int, total_batches: int, frames: int, phase: str):
        if "Upscaling" in phase:
            active_model, model_name = runner.dit, "DiT"
        else:
            active_model, model_name = runner.vae, "VAE"

        def offload_active() -> None:
            modules["manage_model_device"](
                model=active_model,
                target_device="cpu",
                model_name=model_name,
                preserve_vram=True,
                debug=debug,
                runner=runner,
            )
            torch.cuda.empty_cache()

        def restore_active() -> None:
            modules["manage_model_device"](
                model=active_model,
                target_device=str(device),
                model_name=model_name,
                preserve_vram=False,
                debug=debug,
                runner=runner,
            )

        pause_requested = bool(
            args.pause_file and Path(args.pause_file).exists()
        )
        if pause_requested:
            paused = wait_if_paused(
                args.pause_file,
                "SeedVR2",
                before_wait=offload_active,
                after_wait=restore_active,
            )
            if paused:
                pacer.begin()
            return

        delay = pacer.pace()
        if delay >= 0.5:
            print(
                f"SeedVR2: resource pacing {delay:.1f}s idle after "
                f"{phase} {current}/{total_batches} (target duty {args.gpu_duty}%)",
                flush=True,
            )

        # Catch a pause request that arrived while the duty-cycle sleep ran.
        paused = wait_if_paused(
            args.pause_file,
            "SeedVR2",
            before_wait=offload_active,
            after_wait=restore_active,
        )
        if paused:
            pacer.begin()

    try:
        while True:
            tail_len = 0 if input_tail is None else int(input_tail.shape[0])
            start = unique_read - tail_len
            frames, next_tail, new_count = reader.read_chunk(
                input_tail,
                args.chunk_size,
                args.chunk_overlap,
            )
            if frames is None or new_count <= 0:
                break
            unique_read += new_count
            chunk_no += 1

            print(
                f"SeedVR2: chunk {chunk_no}/{max(chunks, chunk_no)} "
                f"frames {start}-{start + frames.shape[0] - 1}",
                flush=True,
            )

            ctx = modules["prepare_context"](device=device, debug=debug)

            pacer.begin()
            ctx = modules["encode"](
                runner,
                ctx=ctx,
                images=frames,
                batch_size=args.batch_size,
                preserve_vram=True,
                debug=debug,
                progress_callback=pace_callback,
                temporal_overlap=args.temporal_overlap,
                res_w=args.resolution,
                input_noise_scale=0.0,
                color_correction=args.color_correction,
            )

            wait_if_paused(args.pause_file, "SeedVR2")
            pacer.begin()
            ctx = modules["upscale"](
                runner,
                ctx=ctx,
                preserve_vram=True,
                debug=debug,
                progress_callback=pace_callback,
                cfg_scale=1.0,
                seed=100,
                latent_noise_scale=0.0,
            )

            wait_if_paused(args.pause_file, "SeedVR2")
            pacer.begin()
            ctx = modules["decode"](
                runner,
                ctx=ctx,
                preserve_vram=True,
                debug=debug,
                progress_callback=pace_callback,
                color_correction=args.color_correction,
            )

            current = ctx["final_video"]
            current = _apply_temporal_overlap_blending(
                current,
                args.batch_size,
                args.temporal_overlap,
            )
            if current.shape[0] < frames.shape[0]:
                raise RuntimeError(
                    f"SeedVR2 returned too few frames: {current.shape[0]} < {frames.shape[0]}"
                )
            if current.shape[0] > frames.shape[0]:
                current = current[: frames.shape[0]].contiguous()

            input_tail = next_tail
            del frames, ctx
            torch.cuda.empty_cache()

            if writer is None:
                h, w = int(current.shape[1]), int(current.shape[2])
                writer = LosslessVideoWriter(output_video, fps, w, h)

            wanted_new = (
                args.chunk_size
                if chunk_no == 1
                else args.chunk_size - args.chunk_overlap
            )
            is_final_short = new_count < wanted_new

            # Keep only the outer overlap in RAM; stream all finalized frames
            # directly into FFV1 as soon as they are available.
            if output_tail is None:
                if is_final_short or args.chunk_overlap == 0:
                    writer.write(current)
                    output_tail = None
                else:
                    keep = min(args.chunk_overlap, current.shape[0])
                    direct = current.shape[0] - keep
                    if direct:
                        writer.write(current[:direct])
                    output_tail = current[direct:].contiguous()
            else:
                actual_overlap = min(
                    output_tail.shape[0],
                    current.shape[0],
                    args.chunk_overlap,
                )
                if actual_overlap:
                    tail = output_tail[-actual_overlap:]
                    head = current[:actual_overlap]
                    alpha = torch.linspace(
                        1.0 / (actual_overlap + 1),
                        actual_overlap / (actual_overlap + 1),
                        steps=actual_overlap,
                        dtype=current.dtype,
                    ).view(actual_overlap, 1, 1, 1)
                    writer.write(tail * (1.0 - alpha) + head * alpha)
                else:
                    writer.write(output_tail)

                remainder = current[actual_overlap:]
                if is_final_short or args.chunk_overlap == 0:
                    if remainder.shape[0]:
                        writer.write(remainder)
                    output_tail = None
                else:
                    keep = min(args.chunk_overlap, remainder.shape[0])
                    direct = remainder.shape[0] - keep
                    if direct:
                        writer.write(remainder[:direct])
                    output_tail = (
                        remainder[direct:].contiguous() if keep else None
                    )

            print(
                f"{PROGRESS_PREFIX}|SeedVR2|{chunk_no}|{max(chunks, chunk_no)}",
                flush=True,
            )

            # At an outer-chunk boundary preserve_vram has already moved the
            # phase models back to CPU, so this pause consumes minimal VRAM.
            wait_if_paused(args.pause_file, "SeedVR2")

            if is_final_short:
                break

        if writer is None:
            raise RuntimeError("SeedVR2 produced no output")
        if output_tail is not None:
            writer.write(output_tail)
        writer.close(check=True)
        produced = writer.count
        writer = None

        if produced != unique_read:
            raise RuntimeError(
                f"SeedVR2 output frame count mismatch: {produced} != {unique_read}"
            )
        if unique_read != total:
            print(
                f"SeedVR2: container frame count was {total}, decoded {unique_read}; "
                "using decoded count as authoritative",
                flush=True,
            )
        print(
            f"SeedVR2 persistent streaming completed: {produced} frames -> {output_video}",
            flush=True,
        )
    finally:
        reader.close()
        if writer is not None:
            try:
                writer.close(check=False)
            except Exception:
                pass
        try:
            modules["cleanup"](
                runner=runner,
                debug=debug,
                keep_models_in_ram=False,
            )
        except Exception:
            pass


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Persistent, bounded-memory SeedVR2 video restoration runner"
    )
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--video-path", required=True, type=Path)
    parser.add_argument("--output-video", required=True, type=Path)
    parser.add_argument("--resolution", required=True, type=int)
    parser.add_argument("--fps", required=True, type=float)
    parser.add_argument("--batch-size", type=int, default=5)
    parser.add_argument("--model", required=True)
    parser.add_argument("--blocks-to-swap", type=int, default=20)
    parser.add_argument("--temporal-overlap", type=int, default=2)
    parser.add_argument("--chunk-size", type=int, default=45)
    parser.add_argument("--chunk-overlap", type=int, default=5)
    parser.add_argument("--color-correction", default="wavelet")
    parser.add_argument("--vae-tiling", action="store_true")
    parser.add_argument("--vae-tile-size", type=int, default=512)
    parser.add_argument("--vae-tile-overlap", type=int, default=128)
    parser.add_argument("--gpu-duty", type=int, default=100)
    parser.add_argument("--resource-profile", default="max")
    parser.add_argument("--pause-file", type=Path, default=None)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
