import inspect
import os
import unittest

import launcher
import settings_extension


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

    def test_dnd_does_not_replace_global_tk_constructor(self):
        source = inspect.getsource(launcher._enable_drag_and_drop)
        self.assertNotIn("app_ai.tk.Tk =", source)
        self.assertIn("TkinterDnD.Tk()", source)

    def test_seedvr2_chunk_controls_are_exposed(self):
        source = inspect.getsource(settings_extension.enable_seedvr2_chunk_settings)
        self.assertIn("seedvr2_chunk_size", source)
        self.assertIn("seedvr2_chunk_overlap", source)
        self.assertIn("長尺動画 / RAM", source)
        self.assertIn("実行負荷", source)
        self.assertIn("GPUデューティ目標", source)


if __name__ == "__main__":
    unittest.main()
