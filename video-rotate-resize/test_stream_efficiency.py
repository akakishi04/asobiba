import unittest
from pathlib import Path


BASE = Path(__file__).resolve().parent


class StreamingEfficiencyTests(unittest.TestCase):
    def test_rvrt_uses_one_rawvideo_pipe_without_png_chunks(self):
        source = (BASE / "rvrt_stream_runner.py").read_text(encoding="utf-8")
        self.assertIn("class RawVideoPipeReader", source)
        self.assertIn('"rawvideo"', source)
        self.assertNotIn("frame%06d.png", source)
        self.assertNotIn("TemporaryDirectory", source)

    def test_seedvr2_keeps_model_loaded_and_does_not_rescan_cli_chunks(self):
        source = (BASE / "seedvr2_runner.py").read_text(encoding="utf-8")
        self.assertIn('cache_model=True', source)
        self.assertIn('modules["prepare_runner"]', source)
        self.assertIn("class SequentialVideoReader", source)
        self.assertNotIn("--skip_first_frames", source)
        self.assertNotIn("--load_cap", source)
        self.assertNotIn("shutil.copy2", source)

    def test_streaming_modules_compile(self):
        for name in (
            "resource_policy.py",
            "rvrt_stream_runner.py",
            "seedvr2_runner.py",
            "seedvr2_streaming.py",
            "rvrt_streaming.py",
        ):
            path = BASE / name
            compile(path.read_text(encoding="utf-8"), str(path), "exec")


if __name__ == "__main__":
    unittest.main()
