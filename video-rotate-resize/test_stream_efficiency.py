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

    def test_ai_runners_use_cooperative_pause_not_process_suspend(self):
        rvrt = (BASE / "rvrt_stream_runner.py").read_text(encoding="utf-8")
        seed = (BASE / "seedvr2_runner.py").read_text(encoding="utf-8")
        pause_ui = (BASE / "pause_support.py").read_text(encoding="utf-8")
        self.assertIn("wait_if_paused", rvrt)
        self.assertIn("wait_if_paused", seed)
        self.assertIn("一時停止", pause_ui)
        self.assertNotIn("SuspendThread", rvrt + seed + pause_ui)

    def test_full_pause_releases_model_ram_and_can_reload(self):
        rvrt = (BASE / "rvrt_stream_runner.py").read_text(encoding="utf-8")
        seed = (BASE / "seedvr2_runner.py").read_text(encoding="utf-8")
        self.assertIn("_model_cache.pop", rvrt)
        self.assertIn("model fully unloaded from GPU/CPU memory", rvrt)
        self.assertIn('keep_models_in_ram=False', seed)
        self.assertIn("deep_reload_runner", seed)
        self.assertIn("create_runner()", seed)

    def test_streaming_modules_compile(self):
        for name in (
            "resource_policy.py",
            "pause_control.py",
            "pause_support.py",
            "ai_backends.py",
            "app_ai.py",
            "eta_support.py",
            "settings_extension.py",
            "launcher.py",
            "rvrt_stream_runner.py",
            "seedvr2_runner.py",
            "seedvr2_streaming.py",
            "rvrt_streaming.py",
        ):
            path = BASE / name
            compile(path.read_text(encoding="utf-8"), str(path), "exec")


if __name__ == "__main__":
    unittest.main()
