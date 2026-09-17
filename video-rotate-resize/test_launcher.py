import os
import unittest

import launcher


class LauncherTests(unittest.TestCase):
    def test_drag_and_drop_video_extensions(self):
        for suffix in (".mp4", ".mov", ".mkv", ".m4v", ".avi", ".webm"):
            self.assertIn(suffix, launcher.VIDEO_EXTENSIONS)

    def test_gui_dependency_directory_is_local(self):
        self.assertEqual(launcher.LOCAL_DEPS.parent, launcher.BASE)
        self.assertEqual(launcher.LOCAL_DEPS.name, ".app_deps")

    def test_tkinterdnd_version_is_pinned(self):
        self.assertEqual(launcher.TKINTERDND_VERSION, "0.6.3")

    def test_child_python_processes_are_forced_to_utf8(self):
        self.assertEqual(os.environ.get("PYTHONUTF8"), "1")
        self.assertEqual(os.environ.get("PYTHONIOENCODING"), "utf-8")


if __name__ == "__main__":
    unittest.main()
