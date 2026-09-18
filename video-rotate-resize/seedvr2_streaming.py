from __future__ import annotations

import tempfile
from pathlib import Path

from ai_backends import AI_SEEDVR2, build_seedvr2_command
from rvrt_streaming import _final_from_lossless_command
from video_tool import build_lossless_transform_command


def enable_seedvr2_streaming(app_ai) -> None:
    """Use persistent SeedVR2 + FFV1 output for SeedVR2-only runs."""
    original_ai_worker = app_ai.App._ai_worker

    def ai_worker_seed_streaming(
        self,
        src,
        dst,
        rot,
        target,
        mode,
        enc,
        fps,
        dims,
        ffmpeg,
    ):
        if mode != AI_SEEDVR2:
            return original_ai_worker(
                self, src, dst, rot, target, mode, enc, fps, dims, ffmpeg
            )

        try:
            with tempfile.TemporaryDirectory(
                prefix=".video_ai_", dir=dst.parent
            ) as td:
                t = Path(td)
                seed_in = src

                if rot != "none" or target is not None:
                    self._stage(8, "SeedVR2用ロスレス中間映像作成中...")
                    seed_in = t / "seed_input.mkv"
                    self._run(
                        build_lossless_transform_command(
                            src,
                            seed_in,
                            rot,
                            target,
                            ffmpeg,
                        ),
                        "Lossless transform",
                    )

                seed_video = t / "seedvr2_restored.mkv"
                self._stage(20, "SeedVR2復元中...")
                cmd, cwd = build_seedvr2_command(
                    self.config,
                    seed_in,
                    seed_video,
                    min(dims),
                    fps,
                    getattr(self, "_pause_file", None),
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

    app_ai.App._ai_worker = ai_worker_seed_streaming
