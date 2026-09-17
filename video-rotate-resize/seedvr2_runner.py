from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

import cv2
from PIL import Image


PROGRESS_PREFIX = "APP_PROGRESS"


def _video_frame_count(path: Path) -> int:
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {path}")
    try:
        count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    finally:
        cap.release()
    if count <= 0:
        raise RuntimeError(f"Cannot determine frame count: {path}")
    return count


def _chunk_ranges(total: int, chunk_size: int, overlap: int) -> list[tuple[int, int]]:
    if chunk_size < 5:
        raise ValueError("chunk_size must be >= 5")
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


def _png_files(path: Path) -> list[Path]:
    files = sorted(path.glob("*.png"))
    if not files:
        raise RuntimeError(f"SeedVR2 produced no PNG frames: {path}")
    return files


def _copy_frame(source: Path, output_dir: Path, index: int) -> None:
    shutil.copy2(source, output_dir / f"frame{index:06d}.png")


def _blend_frames(a: Path, b: Path, output: Path, alpha: float) -> None:
    with Image.open(a) as ia, Image.open(b) as ib:
        left = ia.convert("RGB")
        right = ib.convert("RGB")
        if left.size != right.size:
            raise RuntimeError(
                f"SeedVR2 chunk geometry mismatch: {left.size} != {right.size}"
            )
        Image.blend(left, right, alpha).save(output, format="PNG", compress_level=1)


def _run_child(command: list[str], cwd: Path) -> None:
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    process = subprocess.Popen(
        command,
        cwd=str(cwd),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        creationflags=creationflags,
    )
    assert process.stdout is not None
    for line in process.stdout:
        if line.strip():
            print(line.rstrip(), flush=True)
    code = process.wait()
    if code:
        raise RuntimeError(f"SeedVR2 chunk process failed (code {code})")


def run(args: argparse.Namespace) -> None:
    video = args.video_path.resolve()
    repo = args.repo.resolve()
    output_dir = args.output_dir.resolve()
    cli = repo / "inference_cli.py"
    if not video.is_file():
        raise RuntimeError(f"Input video not found: {video}")
    if not cli.is_file():
        raise RuntimeError(f"SeedVR2 CLI not found: {cli}")

    total = _video_frame_count(video)
    ranges = _chunk_ranges(total, args.chunk_size, args.chunk_overlap)
    output_dir.mkdir(parents=True, exist_ok=True)
    for stale in output_dir.glob("*.png"):
        stale.unlink()

    work = output_dir / ".seed_chunks"
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True, exist_ok=True)

    print(
        f"SeedVR2 chunked runner: {total} frames / {len(ranges)} chunks / "
        f"chunk={args.chunk_size} overlap={args.chunk_overlap}",
        flush=True,
    )
    print(f"{PROGRESS_PREFIX}|SeedVR2|0|{len(ranges)}", flush=True)

    previous_tail: list[Path] = []
    previous_tail_start = 0

    try:
        for chunk_no, (start, end) in enumerate(ranges, start=1):
            chunk_dir = work / f"chunk_{chunk_no:04d}"
            chunk_dir.mkdir(parents=True, exist_ok=True)
            length = end - start
            print(
                f"SeedVR2: chunk {chunk_no}/{len(ranges)} frames {start}-{end - 1}",
                flush=True,
            )

            command = [
                sys.executable,
                str(cli),
                "--video_path",
                str(video),
                "--skip_first_frames",
                str(start),
                "--load_cap",
                str(length),
                "--resolution",
                str(args.resolution),
                "--batch_size",
                str(args.batch_size),
                "--model",
                args.model,
                "--output",
                str(chunk_dir),
                "--output_format",
                "png",
                "--color_correction",
                args.color_correction,
                "--blocks_to_swap",
                str(args.blocks_to_swap),
                "--temporal_overlap",
                str(args.temporal_overlap),
                "--preserve_vram",
                "--offload_io_components",
            ]
            if args.vae_tiling:
                command += [
                    "--vae_tiling_enabled",
                    "--vae_tile_size",
                    str(args.vae_tile_size),
                    "--vae_tile_overlap",
                    str(args.vae_tile_overlap),
                ]

            _run_child(command, repo)
            files = _png_files(chunk_dir)
            if len(files) != length:
                raise RuntimeError(
                    f"SeedVR2 chunk frame count mismatch: {len(files)} != {length} "
                    f"for frames {start}-{end - 1}"
                )

            is_last = chunk_no == len(ranges)
            if chunk_no == 1:
                keep_tail = min(args.chunk_overlap, len(files)) if not is_last else 0
                direct = len(files) - keep_tail
                for offset in range(direct):
                    _copy_frame(files[offset], output_dir, start + offset)
                if keep_tail:
                    previous_tail = files[-keep_tail:]
                    previous_tail_start = end - keep_tail
                else:
                    for offset in range(direct, len(files)):
                        _copy_frame(files[offset], output_dir, start + offset)
            else:
                actual_overlap = max(0, previous_tail_start + len(previous_tail) - start)
                actual_overlap = min(actual_overlap, len(previous_tail), len(files))
                if actual_overlap:
                    prev_offset = len(previous_tail) - actual_overlap
                    for j in range(actual_overlap):
                        alpha = (j + 1) / (actual_overlap + 1)
                        _blend_frames(
                            previous_tail[prev_offset + j],
                            files[j],
                            output_dir / f"frame{start + j:06d}.png",
                            alpha,
                        )

                current_pos = actual_overlap
                keep_tail = min(args.chunk_overlap, len(files) - current_pos) if not is_last else 0
                direct_end = len(files) - keep_tail
                for offset in range(current_pos, direct_end):
                    _copy_frame(files[offset], output_dir, start + offset)

                if keep_tail:
                    previous_tail = files[-keep_tail:]
                    previous_tail_start = end - keep_tail
                else:
                    previous_tail = []
                    previous_tail_start = end
                    for offset in range(direct_end, len(files)):
                        _copy_frame(files[offset], output_dir, start + offset)

            print(f"{PROGRESS_PREFIX}|SeedVR2|{chunk_no}|{len(ranges)}", flush=True)

        produced = len(list(output_dir.glob("frame*.png")))
        if produced != total:
            raise RuntimeError(f"SeedVR2 output frame count mismatch: {produced} != {total}")
        print(f"SeedVR2: completed {produced} frames", flush=True)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Memory-safe chunked SeedVR2 runner")
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--video-path", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--resolution", required=True, type=int)
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
    run(parser.parse_args())


if __name__ == "__main__":
    main()
