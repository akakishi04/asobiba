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
    def _fake_python(self, root: Path, name: str) -> Path:
        python = root / f"{name}_python.exe"
        python.write_text("", encoding="utf-8")
        return python

    def _fake_seed_engine(self, root: Path) -> tuple[Path, Path]:
        repo = root / "seed"
        repo.mkdir()
        (repo / "inference_cli.py").write_text("# stub\n", encoding="utf-8")
        return repo, self._fake_python(root, "seed")

    def test_seedvr2_command_uses_memory_safe_chunk_runner(self):
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            repo, python = self._fake_seed_engine(root)
            cfg = AIConfig(
                seedvr2_repo=str(repo),
                seedvr2_python=str(python),
                seedvr2_batch_size=5,
                seedvr2_blocks_to_swap=20,
                seedvr2_chunk_size=45,
                seedvr2_chunk_overlap=5,
            )
            validate_for_mode(cfg, AI_SEEDVR2)
            pause = root / "pause.flag"
            cmd, cwd = build_seedvr2_command(
                cfg, "input.mp4", "out.mkv", 1080, 30.0, pause
            )
            self.assertEqual(cmd[0], str(python))
            self.assertTrue(cmd[1].endswith("seedvr2_runner.py"))
            self.assertEqual(cwd, Path(cmd[1]).parent)
            self.assertEqual(cmd[cmd.index("--resolution") + 1], "1080")
            self.assertEqual(cmd[cmd.index("--batch-size") + 1], "5")
            self.assertEqual(cmd[cmd.index("--blocks-to-swap") + 1], "20")
            self.assertEqual(cmd[cmd.index("--chunk-size") + 1], "45")
            self.assertEqual(cmd[cmd.index("--chunk-overlap") + 1], "5")
            self.assertEqual(cmd[cmd.index("--output-video") + 1], "out.mkv")
            self.assertEqual(cmd[cmd.index("--fps") + 1], "30.00000000")
            self.assertEqual(cmd[cmd.index("--pause-file") + 1], str(pause))
            self.assertIn("--vae-tiling", cmd)

    def test_seedvr2_resolution_override(self):
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            repo, python = self._fake_seed_engine(root)
            cfg = AIConfig(
                seedvr2_repo=str(repo),
                seedvr2_python=str(python),
                seedvr2_resolution_override=1072,
            )
            cmd, _ = build_seedvr2_command(cfg, "input.mp4", "out.mkv", 2160, 30.0)
            self.assertEqual(cmd[cmd.index("--resolution") + 1], "1072")

    def test_seedvr2_invalid_chunk_overlap_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            repo, python = self._fake_seed_engine(root)
            cfg = AIConfig(
                seedvr2_repo=str(repo),
                seedvr2_python=str(python),
                seedvr2_chunk_size=45,
                seedvr2_chunk_overlap=45,
            )
            with self.assertRaises(Exception):
                validate_for_mode(cfg, AI_SEEDVR2)


    def test_background_profile_increases_seed_offload_and_sets_duty(self):
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            repo, python = self._fake_seed_engine(root)
            cfg = AIConfig(
                seedvr2_repo=str(repo),
                seedvr2_python=str(python),
                seedvr2_blocks_to_swap=20,
                resource_profile="background",
            )
            cmd, _ = build_seedvr2_command(
                cfg, "input.mp4", "out.mkv", 1080, 30.0
            )
            self.assertEqual(cmd[cmd.index("--blocks-to-swap") + 1], "28")
            self.assertEqual(cmd[cmd.index("--gpu-duty") + 1], "50")
            self.assertEqual(
                cmd[cmd.index("--resource-profile") + 1], "background"
            )

    def test_rvrt_command_uses_managed_runner_and_one_x_task(self):
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            python = self._fake_python(root, "rvrt")
            runner = root / "rvrt_runner.py"
            runner.write_text("# stub\n", encoding="utf-8")
            cfg = AIConfig(
                rvrt_python=str(python),
                rvrt_chunk_size=16,
                rvrt_chunk_overlap=4,
            )
            validate_for_mode(cfg, AI_RVRT)
            cmd, cwd = build_rvrt_command(cfg, "frames_in", "frames_out", runner)
            self.assertEqual(cwd, runner.resolve().parent)
            self.assertEqual(cmd[0], str(python))
            self.assertEqual(cmd[1], str(runner.resolve()))
            self.assertEqual(
                cmd[cmd.index("--task") + 1],
                "005_RVRT_videodeblurring_GoPro_16frames",
            )
            self.assertEqual(cmd[cmd.index("--chunk-size") + 1], "16")
            self.assertEqual(cmd[cmd.index("--chunk-overlap") + 1], "4")
            self.assertEqual(cmd[cmd.index("--input-dir") + 1], "frames_in")
            self.assertEqual(cmd[cmd.index("--output-dir") + 1], "frames_out")

    def test_rvrt_does_not_require_external_repo(self):
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            python = self._fake_python(root, "rvrt")
            cfg = AIConfig(rvrt_python=str(python), rvrt_repo="")
            validate_for_mode(cfg, AI_RVRT)

    def test_rvrt_invalid_overlap_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            python = self._fake_python(root, "rvrt")
            cfg = AIConfig(
                rvrt_python=str(python),
                rvrt_chunk_size=16,
                rvrt_chunk_overlap=16,
            )
            with self.assertRaises(Exception):
                validate_for_mode(cfg, AI_RVRT)

    def test_config_round_trip(self):
        with tempfile.TemporaryDirectory() as temp_name:
            path = Path(temp_name) / "ai_config.json"
            cfg = AIConfig(
                rvrt_chunk_size=12,
                seedvr2_batch_size=7,
                seedvr2_resolution_override=1440,
                seedvr2_chunk_size=37,
                seedvr2_chunk_overlap=5,
                resource_profile="background",
                gpu_duty_cycle_percent=55,
            )
            cfg.save(path)
            restored = AIConfig.load(path)
            self.assertEqual(restored.rvrt_chunk_size, 12)
            self.assertEqual(restored.seedvr2_batch_size, 7)
            self.assertEqual(restored.seedvr2_resolution_override, 1440)
            self.assertEqual(restored.seedvr2_chunk_size, 37)
            self.assertEqual(restored.seedvr2_chunk_overlap, 5)
            self.assertEqual(restored.resource_profile, "background")
            self.assertEqual(restored.gpu_duty_cycle_percent, 55)

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
