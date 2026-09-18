from __future__ import annotations

import argparse
import math
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from vsrvrt.model_configs import get_config
from vsrvrt.rvrt_core import RVRTInference


PROGRESS_PREFIX = "APP_PROGRESS"


def _frame_files(input_dir: Path) -> list[Path]:
    files = sorted(input_dir.glob("*.png"))
    if not files:
        raise RuntimeError(f"PNG frames not found: {input_dir}")
    return files


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
    return torch.stack(frames, dim=0).unsqueeze(0)


def _save_frame(tensor: torch.Tensor, path: Path) -> None:
    array = (
        tensor.detach()
        .float()
        .clamp_(0.0, 1.0)
        .permute(1, 2, 0)
        .cpu()
        .numpy()
    )
    image = Image.fromarray(np.rint(array * 255.0).astype(np.uint8), mode="RGB")
    image.save(path, format="PNG", compress_level=1)


def _chunk_ranges(total: int, chunk_size: int, overlap: int) -> list[tuple[int, int]]:
    if total <= 0:
        return []
    if chunk_size < 4:
        raise ValueError("chunk_size must be >= 4")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must satisfy 0 <= overlap < chunk_size")
    if total <= chunk_size:
        return [(0, total)]

    stride = chunk_size - overlap
    ranges: list[tuple[int, int]] = []
    start = 0
    while start < total:
        end = min(total, start + chunk_size)
        ranges.append((start, end))
        if end >= total:
            break
        start += stride
    return ranges


def _pad_temporal(clip: torch.Tensor, minimum: int = 4) -> tuple[torch.Tensor, int]:
    original = clip.shape[1]
    target = max(minimum, int(math.ceil(original / 2.0) * 2))
    if target == original:
        return clip, original
    last = clip[:, -1:, ...]
    clip = torch.cat([clip, last.repeat(1, target - original, 1, 1, 1)], dim=1)
    return clip, original


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


def _write_pending(
    output_dir: Path,
    start_index: int,
    frames: torch.Tensor,
) -> None:
    for offset in range(frames.shape[1]):
        index = start_index + offset
        _save_frame(frames[0, offset], output_dir / f"frame{index:06d}.png")


def run(
    input_dir: Path,
    output_dir: Path,
    task: str,
    chunk_size: int,
    overlap: int,
) -> None:
    files = _frame_files(input_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    for stale in output_dir.glob("*.png"):
        stale.unlink()

    if not torch.cuda.is_available():
        raise RuntimeError("RVRT requires CUDA, but torch.cuda.is_available() is False")

    config = get_config(task)
    if config.upscale != 1:
        raise RuntimeError("This runner is restricted to RVRT 1x restoration tasks")

    print(
        f"RVRT: {task} / {len(files)} frames / GPU={torch.cuda.get_device_name(0)} / fp16",
        flush=True,
    )
    inference = RVRTInference(config, use_fp16=True, device=torch.device("cuda"))
    chunks = _chunk_ranges(len(files), chunk_size, overlap)
    print(f"{PROGRESS_PREFIX}|RVRT|0|{len(chunks)}", flush=True)

    pending_start: int | None = None
    pending: torch.Tensor | None = None
    input_hw: tuple[int, int] | None = None

    for chunk_no, (start, end) in enumerate(chunks, start=1):
        print(f"RVRT: chunk {chunk_no}/{len(chunks)} frames {start}-{end - 1}", flush=True)
        clip = _load_frames(files[start:end])
        if input_hw is None:
            input_hw = (clip.shape[-2], clip.shape[-1])
        current = _infer_chunk(inference, clip, input_hw)
        del clip
        torch.cuda.empty_cache()

        if pending is None or pending_start is None:
            pending_start = start
            pending = current
            print(f"{PROGRESS_PREFIX}|RVRT|{chunk_no}|{len(chunks)}", flush=True)
            continue

        pending_end = pending_start + pending.shape[1]
        actual_overlap = max(0, pending_end - start)
        actual_overlap = min(actual_overlap, pending.shape[1], current.shape[1])

        if actual_overlap == 0:
            _write_pending(output_dir, pending_start, pending)
            pending_start = start
            pending = current
            print(f"{PROGRESS_PREFIX}|RVRT|{chunk_no}|{len(chunks)}", flush=True)
            continue

        direct_count = pending.shape[1] - actual_overlap
        if direct_count:
            _write_pending(output_dir, pending_start, pending[:, :direct_count])

        blend_start = start
        for j in range(actual_overlap):
            alpha = (j + 1) / (actual_overlap + 1)
            blended = pending[0, direct_count + j] * (1.0 - alpha) + current[0, j] * alpha
            _save_frame(blended, output_dir / f"frame{blend_start + j:06d}.png")

        pending_start = start + actual_overlap
        pending = current[:, actual_overlap:].contiguous()
        del current
        print(f"{PROGRESS_PREFIX}|RVRT|{chunk_no}|{len(chunks)}", flush=True)

    if pending is not None and pending_start is not None:
        _write_pending(output_dir, pending_start, pending)

    produced = len(list(output_dir.glob("*.png")))
    if produced != len(files):
        raise RuntimeError(f"RVRT output frame count mismatch: {produced} != {len(files)}")
    print(f"RVRT: completed {produced} frames", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="RVRT 1x restoration runner for video-rotate-resize")
    parser.add_argument("--input-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--task", required=True)
    parser.add_argument("--chunk-size", type=int, default=16)
    parser.add_argument("--chunk-overlap", type=int, default=4)
    args = parser.parse_args()
    run(args.input_dir, args.output_dir, args.task, args.chunk_size, args.chunk_overlap)


if __name__ == "__main__":
    main()
