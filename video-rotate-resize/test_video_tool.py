import unittest

from video_tool import VideoToolError, build_ffmpeg_command, build_video_filter


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


if __name__ == "__main__":
    unittest.main()
