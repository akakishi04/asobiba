import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from ai_backends import AIConfig
from rvrt_streaming import _build_rvrt_stream_command, _final_from_lossless_command
from video_tool import VideoToolError


class RVRTStreamingTests(unittest.TestCase):
    def test_stream_command_uses_video_not_full_png_directory(self):
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            python = root / "python.exe"
            python.write_text("", encoding="utf-8")
            config = AIConfig(
                rvrt_python=str(python),
                rvrt_chunk_size=16,
                rvrt_chunk_overlap=4,
            )
            fake_app = SimpleNamespace(
                VideoToolError=VideoToolError,
                find_executable=lambda name: "ffprobe" if name == "ffprobe" else name,
            )
            cmd, cwd = _build_rvrt_stream_command(
                fake_app,
                config,
                Path("input.mp4"),
                Path("restored.mkv"),
                "none",
                None,
                30.0,
                (1920, 1080),
                "ffmpeg",
            )
            self.assertEqual(cwd.name, "video-rotate-resize")
            self.assertIn("--video-path", cmd)
            self.assertIn("--output-video", cmd)
            self.assertIn("--chunk-size", cmd)
            self.assertEqual(cmd[cmd.index("--chunk-size") + 1], "16")
            self.assertEqual(cmd[cmd.index("--chunk-overlap") + 1], "4")
            self.assertEqual(cmd[cmd.index("--width") + 1], "1920")
            self.assertEqual(cmd[cmd.index("--height") + 1], "1080")
            self.assertEqual(cmd[cmd.index("--gpu-duty") + 1], "100")
            self.assertNotIn("--input-dir", cmd)

    def test_final_encode_reads_single_lossless_video_and_original_audio(self):
        cmd = _final_from_lossless_command(
            "ffmpeg",
            Path("restored.mkv"),
            Path("source.mp4"),
            Path("output.mp4"),
            "nvenc",
            (1920, 1080),
        )
        self.assertIn("restored.mkv", cmd)
        self.assertIn("source.mp4", cmd)
        self.assertIn("h264_nvenc", cmd)
        self.assertIn("-progress", cmd)
        self.assertNotIn("frame%06d.png", cmd)


if __name__ == "__main__":
    unittest.main()
