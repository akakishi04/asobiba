import json
import tempfile
import unittest
from pathlib import Path

from ai_restoration import (
    EngineConfig,
    RestorationConfig,
    build_rvrt_step,
    build_seedvr2_step,
    load_engine_config,
)


class AIRestorationTests(unittest.TestCase):
    def test_load_engine_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ai_engines.json"
            path.write_text(
                json.dumps(
                    {
                        "rvrt_repo": "C:/rvrt",
                        "seedvr2_custom_command": [
                            "python",
                            "runner.py",
                            "--input",
                            "{input_dir}",
                            "--output",
                            "{output_dir}",
                        ],
                    }
                ),
                encoding="utf-8",
            )
            cfg = load_engine_config(path)
            self.assertEqual(str(cfg.rvrt_repo), "C:/rvrt")
            self.assertIn("{input_dir}", cfg.seedvr2_custom_command)

    def test_build_rvrt_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "RVRT"
            repo.mkdir()
            (repo / "main_test_rvrt.py").write_text("", encoding="utf-8")
            fake_python = Path(tmp) / "python.exe"
            fake_python.write_text("", encoding="utf-8")
            frames = Path(tmp) / "frames"
            frames.mkdir()
            step = build_rvrt_step(
                EngineConfig(rvrt_repo=repo, rvrt_python=fake_python),
                RestorationConfig(mode="rvrt"),
                frames,
            )
            self.assertEqual(step.name, "RVRT")
            self.assertIn("--folder_lq", step.command)
            self.assertIn(str(frames), step.command)
            self.assertIn("--save_result", step.command)

    def test_seedvr2_custom_command_expands_placeholders(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            input_dir = base / "in"
            output_dir = base / "out"
            command = (
                "runner.exe",
                "--in",
                "{input_dir}",
                "--out",
                "{output_dir}",
                "--size",
                "{width}x{height}",
                "--seed",
                "{seed}",
            )
            step = build_seedvr2_step(
                EngineConfig(seedvr2_custom_command=command),
                RestorationConfig(mode="seedvr2", seed=123),
                input_dir,
                output_dir,
                1920,
                1080,
            )
            self.assertEqual(step.name, "SeedVR2(custom)")
            self.assertIn(str(input_dir), step.command)
            self.assertIn(str(output_dir), step.command)
            self.assertIn("1920x1080", step.command)
            self.assertIn("123", step.command)


if __name__ == "__main__":
    unittest.main()
