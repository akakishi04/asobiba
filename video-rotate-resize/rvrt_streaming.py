from __future__ import annotations

import tempfile
from pathlib import Path

from ai_backends import (
    AI_RVRT,
    AI_RVRT_SEEDVR2,
    build_seedvr2_command,
    resolve_python,
)
from resource_policy import effective_gpu_duty_percent
from video_tool import build_video_filter


def _append_encoder(command: list[str], encoder: str) -> None:
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
    elif encoder == "libx264":
        command += ["-c:v", "libx264", "-preset", "medium", "-crf", "18"]
    else:
        raise RuntimeError(f"Unsupported encoder: {encoder}")


def _final_from_lossless_command(
    ffmpeg: str,
    restored_video: Path,
    audio_source: Path,
    output_path: Path,
    encoder: str,
    exact_resolution: tuple[int, int],
    scale_output: bool = True,
) -> list[str]:
    width, height = exact_resolution
    command = [
        ffmpeg,
        "-y",
        "-hide_banner",
        "-i",
        str(restored_video),
        "-i",
        str(audio_source),
        "-map",
        "0:v:0",
        "-map",
        "1:a?",
        "-map_metadata",
        "1",
    ]
    if scale_output:
        command += ["-vf", f"scale={width}:{height}:flags=lanczos,setsar=1"]
    else:
        command += ["-vf", "setsar=1"]
    _append_encoder(command, encoder)
    command += [
        "-pix_fmt",
        "yuv420p",
        "-metadata:s:v:0",
        "rotate=0",
        "-c:a",
        "copy",
        "-shortest",
        "-movflags",
        "+faststart",
        "-progress",
        "pipe:1",
        "-nostats",
        str(output_path),
    ]
    return command


def _build_rvrt_stream_command(
    app_ai,
    config,
    src: Path,
    output_video: Path,
    rot: str,
    target: tuple[int, int] | None,
    fps: float,
    dims: tuple[int, int],
    ffmpeg: str,
) -> tuple[list[str], Path]:
    runner = Path(__file__).with_name("rvrt_stream_runner.py").resolve()
    if not runner.is_file():
        raise app_ai.VideoToolError(
            f"RVRT streaming runner が見つかりません: {runner}"
        )
    ffprobe = app_ai.find_executable("ffprobe")
    vf = build_video_filter(rot, target)
    width, height = dims
    command = [
        resolve_python(config.rvrt_python),
        str(runner),
        "--video-path",
        str(src),
        "--output-video",
        str(output_video),
        "--task",
        config.rvrt_task,
        "--chunk-size",
        str(config.rvrt_chunk_size),
        "--chunk-overlap",
        str(config.rvrt_chunk_overlap),
        "--ffmpeg",
        ffmpeg,
        "--ffprobe",
        ffprobe,
        "--fps",
        f"{fps:.8f}",
        "--width",
        str(width),
        "--height",
        str(height),
        "--gpu-duty",
        str(effective_gpu_duty_percent(config)),
    ]
    if vf:
        command += ["--vf", vf]
    return command, runner.parent


def enable_rvrt_streaming(app_ai) -> None:
    """Use pipe-streamed RVRT and lossless-video handoff instead of PNG sequences."""
    original_ai_worker = app_ai.App._ai_worker

    def ai_worker_streaming(self, src, dst, rot, target, mode, enc, fps, dims, ffmpeg):
        if mode not in {AI_RVRT, AI_RVRT_SEEDVR2}:
            return original_ai_worker(
                self, src, dst, rot, target, mode, enc, fps, dims, ffmpeg
            )

        try:
            with tempfile.TemporaryDirectory(
                prefix=".video_ai_", dir=dst.parent
            ) as td:
                t = Path(td)
                rvrt_video = t / "rvrt_restored.mkv"

                self._stage(20, "RVRT復元中...")
                cmd, cwd = _build_rvrt_stream_command(
                    app_ai,
                    self.config,
                    src,
                    rvrt_video,
                    rot,
                    target,
                    fps,
                    dims,
                    ffmpeg,
                )
                self._run(cmd, "RVRT", cwd)

                if mode == AI_RVRT:
                    self._stage(92, "最終MP4作成中...")
                    self._run(
                        _final_from_lossless_command(
                            ffmpeg,
                            rvrt_video,
                            src,
                            dst,
                            enc,
                            dims,
                            scale_output=False,
                        ),
                        "FFmpeg",
                    )
                    self._done(dst)
                    return

                seed_video = t / "seedvr2_restored.mkv"
                self._stage(62, "SeedVR2復元中...")
                cmd, cwd = build_seedvr2_command(
                    self.config,
                    rvrt_video,
                    seed_video,
                    min(dims),
                    fps,
                )
                self._run(cmd, "SeedVR2", cwd)

                self._stage(92, "最終MP4作成中...")
                self._run(
                    _final_from_lossless_command(
                        ffmpeg,
                        seed_video,
                        src,
                        dst,
                        enc,
                        dims,
                    ),
                    "FFmpeg",
                )
                self._done(dst)
        except app_ai.Cancelled:
            self._cancelled()
        except Exception as exc:
            self._failed(exc)
        finally:
            self._idle()

    app_ai.App._ai_worker = ai_worker_streaming
