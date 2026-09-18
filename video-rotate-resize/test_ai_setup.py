import os
import tempfile
import unittest
from pathlib import Path

from ai_setup import (
    AISetupPaths,
    RVRT_TORCH_INDEX,
    RVRT_TORCH_PACKAGES,
    SEEDVR2_REPO_URL,
    SEEDVR2_REVISION,
    SEEDVR2_TORCH_INDEX,
    SEEDVR2_TORCH_PACKAGES,
    VSRVRT_VERSION,
)


class AISetupTests(unittest.TestCase):
    def test_managed_paths_stay_under_video_tool_directory(self):
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name).resolve()
            paths = AISetupPaths.for_base(root)
            self.assertEqual(paths.engines, root / "ai_engines")
            self.assertEqual(paths.seedvr2_repo, root / "ai_engines" / "SeedVR2")
            self.assertEqual(paths.rvrt_venv, root / ".venv-rvrt")
            self.assertEqual(paths.seedvr2_venv, root / ".venv-seedvr2")

    def test_venv_python_layout(self):
        root = Path("example")
        python = AISetupPaths.venv_python(root)
        if os.name == "nt":
            self.assertEqual(python, root / "Scripts" / "python.exe")
        else:
            self.assertEqual(python, root / "bin" / "python")

    def test_backend_versions_are_pinned(self):
        self.assertEqual(VSRVRT_VERSION, "1.1.3")
        self.assertEqual(len(SEEDVR2_REVISION), 40)
        self.assertTrue(SEEDVR2_REPO_URL.endswith("comfyui_seedvr2.git"))
        self.assertIn("torch==2.7.1", RVRT_TORCH_PACKAGES)
        self.assertIn("cu128", RVRT_TORCH_INDEX)
        self.assertIn("torch==2.6.0", SEEDVR2_TORCH_PACKAGES)
        self.assertIn("cu126", SEEDVR2_TORCH_INDEX)


if __name__ == "__main__":
    unittest.main()
