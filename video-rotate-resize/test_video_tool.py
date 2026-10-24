import unittest

from video_tool import (
    ProbeInfo,
    VideoToolError,
    build_extract_png_command,
    build_ffmpeg_command,
    build_frames_to_lossless_video_command,
    build_frames_to_video_command,
    build_lossless_transform_command,
    build_video_filter,
    transformed_dimensions,
)


class VideoToolTests(unittest.TestCase):
    def test_clockwise_1080p_filter(self):
        vf = build_video_filter("cw90", (1920, 1080))
        self.assertEqual(
            vf,
            "transpose=1,scale=1920:1080:force_original_aspect_ratio=decrease:flags=lanczos,"
            "pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black,setsar=1",
        )

    def test_rotation_only_filter(self):
        self.assertEqual(build_video_filter("ccw90", None), "transpose=2,setsar=1")

    def test_180_filter(self):
        self.assertEqual(build_video_filter("180", None), "hflip,vflip,setsar=1")

    def test_odd_target_is_rejected(self):
        with self.assertRaises(VideoToolError):
            build_video_filter("none", (1919, 1080))

    def test_nvenc_command(self):
        cmd = build_ffmpeg_command(
            "input.mp4",
            "output.mp4",
            "cw90",
            (1920, 1080),
            "nvenc",
            ffmpeg="ffmpeg",
        )
        self.assertIn("h264_nvenc", cmd)
        self.assertIn("-progress", cmd)
        self.assertIn("pipe:1", cmd)

    def test_cpu_command(self):
        cmd = build_ffmpeg_command(
            "input.mp4",
            "output.mp4",
            "none",
            (1280, 720),
            "libx264",
            ffmpeg="ffmpeg",
        )
        self.assertIn("libx264", cmd)
        self.assertIn("-crf", cmd)

    def test_lossless_intermediate_uses_ffv1(self):
        cmd = build_lossless_transform_command(
            "input.mp4",
            "intermediate.mkv",
            "cw90",
            None,
            ffmpeg="ffmpeg",
        )
        self.assertIn("ffv1", cmd)
        self.assertIn("transpose=1,setsar=1", cmd)

    def test_extract_png_command_can_apply_transform(self):
        cmd = build_extract_png_command(
            "input.mp4",
            "frame%06d.png",
            "ccw90",
            (1920, 1080),
            ffmpeg="ffmpeg",
        )
        self.assertIn("-fps_mode", cmd)
        self.assertIn("frame%06d.png", cmd)
        self.assertTrue(any("transpose=2" in part for part in cmd))

    def test_frames_to_lossless_video(self):
        cmd = build_frames_to_lossless_video_command(
            "frame%06d.png",
            59.94,
            "restored.mkv",
            ffmpeg="ffmpeg",
        )
        self.assertIn("ffv1", cmd)
        self.assertIn("59.94000000", cmd)

    def test_frames_to_final_video_restores_audio(self):
        cmd = build_frames_to_video_command(
            "frame%06d.png",
            30.0,
            "source.mp4",
            "output.mp4",
            "nvenc",
            exact_resolution=(1920, 1080),
            ffmpeg="ffmpeg",
        )
        self.assertIn("h264_nvenc", cmd)
        self.assertIn("1:a?", cmd)
        self.assertIn("copy", cmd)
        self.assertTrue(any("scale=1920:1080" in part for part in cmd))

    def test_transformed_dimensions_honors_display_rotation(self):
        info = ProbeInfo(
            width=2160,
            height=3840,
            duration_seconds=1.0,
            fps=30.0,
            codec="h264",
            rotation=90,
        )
        self.assertEqual(transformed_dimensions(info, "none", None), (3840, 2160))
        self.assertEqual(transformed_dimensions(info, "cw90", None), (2160, 3840))


if __name__ == "__main__":
    unittest.main()
