import json
import shutil
import subprocess
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from video_split import (
    CutRange,
    build_copy_cut_command,
    build_copy_segment_command,
    parse_cut_ranges,
    parse_timecode,
    validate_prefix,
)
from video_tool import VideoToolError


class StreamCopyCommandTests(unittest.TestCase):
    def test_timecode_formats(self):
        self.assertEqual(parse_timecode("90"), Decimal("90"))
        self.assertEqual(parse_timecode("01:30.25"), Decimal("90.25"))
        self.assertEqual(parse_timecode("01:02:03.5"), Decimal("3723.5"))

    def test_bad_timecodes(self):
        for value in ("", "-1", "00:60", "01:60:00", "1:2:3:4", "NaN", "inf"):
            with self.subTest(value=value), self.assertRaises(VideoToolError):
                parse_timecode(value)

    def test_multiple_cuts_and_duration(self):
        cuts = parse_cut_ranges(
            "# comment\n00:00:00 - 00:00:15.5\n00:01:00 - 90",
            duration=100,
        )
        self.assertEqual(cuts, [
            CutRange(Decimal("0"), Decimal("15.5")),
            CutRange(Decimal("60"), Decimal("90")),
        ])
        with self.assertRaises(VideoToolError):
            parse_cut_ranges("1 - 8", duration=5)
        with self.assertRaises(VideoToolError):
            parse_cut_ranges("3 - 1")
        with self.assertRaises(VideoToolError):
            parse_cut_ranges("15")

    def test_safe_prefix(self):
        self.assertEqual(validate_prefix("録画 01"), "録画 01")
        for value in ("", "../other", "bad:name", "trailing."):
            with self.subTest(value=value), self.assertRaises(VideoToolError):
                validate_prefix(value)

    def test_manual_cut_keeps_streams(self):
        cmd = build_copy_cut_command(
            "in.mkv", "out.mkv",
            CutRange(Decimal("12.5"), Decimal("31")), ffmpeg="ffmpeg",
        )
        self.assertEqual(cmd[cmd.index("-c") + 1], "copy")
        self.assertEqual(cmd[cmd.index("-map") + 1], "0")
        self.assertEqual(cmd[cmd.index("-ss") + 1], "12.5")
        self.assertEqual(cmd[cmd.index("-t") + 1], "18.5")
        self.assertIn("-n", cmd)
        self.assertNotIn("-vf", cmd)
        self.assertNotIn("libx264", cmd)

    def test_auto_segment_preserves_container(self):
        cmd = build_copy_segment_command(
            "source.m4v", "part_%03d.m4v", Decimal("60"), ffmpeg="ffmpeg",
        )
        self.assertEqual(cmd[cmd.index("-c") + 1], "copy")
        self.assertEqual(cmd[cmd.index("-segment_format") + 1], "mp4")
        self.assertEqual(cmd[cmd.index("-segment_time") + 1], "60")
        self.assertIn("-reset_timestamps", cmd)

    def test_invalid_commands(self):
        with self.assertRaises(VideoToolError):
            build_copy_cut_command(
                "source.mp4", "source.mp4",
                CutRange(Decimal("0"), Decimal("1")), ffmpeg="ffmpeg",
            )
        with self.assertRaises(VideoToolError):
            build_copy_cut_command(
                "source.mp4", "other.mkv",
                CutRange(Decimal("0"), Decimal("1")), ffmpeg="ffmpeg",
            )
        with self.assertRaises(VideoToolError):
            build_copy_segment_command(
                "source.mp4", "part_%03d.mp4", Decimal("0"), ffmpeg="ffmpeg",
            )


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg not installed")
class StreamCopyIntegrationTests(unittest.TestCase):
    def test_real_cut_and_split_retain_codecs(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "source.mkv"
            subprocess.run(
                [
                    "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "lavfi", "-i", "testsrc2=size=96x64:rate=4",
                    "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=44100",
                    "-t", "5", "-c:v", "mpeg4", "-g", "4", "-q:v", "5",
                    "-c:a", "aac", "-shortest", str(source),
                ],
                check=True, capture_output=True,
            )

            cut_path = root / "cut.mkv"
            subprocess.run(
                build_copy_cut_command(
                    source, cut_path, CutRange(Decimal("1"), Decimal("3")),
                    ffmpeg="ffmpeg",
                ),
                check=True, capture_output=True,
            )

            segment_pattern = root / "part_%03d.mkv"
            subprocess.run(
                build_copy_segment_command(
                    source, segment_pattern, Decimal("2"), ffmpeg="ffmpeg",
                ),
                check=True, capture_output=True,
            )
            parts = sorted(root.glob("part_*.mkv"))
            self.assertGreaterEqual(len(parts), 2)

            def codecs(path):
                result = subprocess.run(
                    ["ffprobe", "-v", "error", "-show_entries",
                     "stream=codec_type,codec_name", "-of", "json", str(path)],
                    check=True, capture_output=True, text=True,
                )
                return sorted(
                    (stream["codec_type"], stream["codec_name"])
                    for stream in json.loads(result.stdout)["streams"]
                )

            expected = codecs(source)
            self.assertEqual(codecs(cut_path), expected)
            for part in parts:
                self.assertEqual(codecs(part), expected)


if __name__ == "__main__":
    unittest.main()
