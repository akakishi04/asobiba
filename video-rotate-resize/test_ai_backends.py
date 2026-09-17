import tempfile
import unittest
from pathlib import Path

from ai_backends import (
    AIConfig,
    AI_RVRT,
    AI_SEEDVR2,
    build_rvrt_command,
    build_seedvr2_command,
    normalize_png_sequence,
    validate_for_mode,
)


class AIBackendTests(unittest.TestCase):
    def _fake_engine(self, root: Path, name: str, marker: str) -> tuple[Path, Path]:
        repo = root / name
        repo.mkdir()
        (repo / marker).write_text("# stub\n", encoding="utf-8")
        python = root / f"{name}_python.exe"
        python.write_text("", encoding="utf-8")
        return repo, python

    def test_seedvr2_command_defaults_to_native_short_side(self):
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            repo, python = self._fake_engine(root, "seed", "inference_cli.py")
            cfg = AIConfig(
                seedvr2_repo=str(repo),
                seedvr2_python=str(python),
                seedvr2_batch_size=5,
                seedvr2_blocks_to_swap=20,
            )
            validate_for_mode(cfg, AI_SEEDVR2)
            cmd, cwd = build_seedvr2_command(cfg, "input.mp4", "out", 1080)
            self.assertEqual(cwd, repo)
            self.assertIn("--resolution", cmd)
            self.assertEqual(cmd[cmd.index("--resolution") + 1], "1080")
            self.assertEqual(cmd[cmd.index("--batch_size") + 1], "5")
            self.assertIn("--vae_tiling_enabled", cmd)

    def test_seedvr2_resolution_override(self):
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            repo, python = self._fake_engine(root, "seed", "inference_cli.py")
            cfg = AIConfig(
                seedvr2_repo=str(repo),
                seedvr2_python=str(python),
                seedvr2_resolution_override=1072,
            )
            cmd, _ = build_seedvr2_command(cfg, "input.mp4", "out", 2160)
            self.assertEqual(cmd[cmd.index("--resolution") + 1], "1072")

    def test_rvrt_command_uses_one_x_deblur_task(self):
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            repo, python = self._fake_engine(root, "rvrt", "main_test_rvrt.py")
            cfg = AIConfig(rvrt_repo=str(repo), rvrt_python=str(python))
            validate_for_mode(cfg, AI_RVRT)
            cmd, cwd = build_rvrt_command(cfg, "frames")
            self.assertEqual(cwd, repo)
            self.assertIn("005_RVRT_videodeblurring_GoPro_16frames", cmd)
            self.assertIn("--save_result", cmd)
            self.assertIn("--num_workers", cmd)

    def test_config_round_trip(self):
        with tempfile.TemporaryDirectory() as temp_name:
            path = Path(temp_name) / "ai_config.json"
            cfg = AIConfig(seedvr2_batch_size=7, seedvr2_resolution_override=1440)
            cfg.save(path)
            restored = AIConfig.load(path)
            self.assertEqual(restored.seedvr2_batch_size, 7)
            self.assertEqual(restored.seedvr2_resolution_override, 1440)

    def test_normalize_png_sequence(self):
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            source = root / "source"
            destination = root / "dest"
            source.mkdir()
            (source / "clip_upscaled_00001.png").write_bytes(b"b")
            (source / "clip_upscaled_00000.png").write_bytes(b"a")
            count = normalize_png_sequence(source, destination)
            self.assertEqual(count, 2)
            self.assertEqual((destination / "frame000000.png").read_bytes(), b"a")
            self.assertEqual((destination / "frame000001.png").read_bytes(), b"b")


if __name__ == "__main__":
    unittest.main()
