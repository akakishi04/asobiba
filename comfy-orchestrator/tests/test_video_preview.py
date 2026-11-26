import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from comfy_orchestrator import video_preview as vp, gui


class VideoPreviewTests(unittest.TestCase):
    def test_time_format(self):
        self.assertEqual(vp.format_time(-1), "0:00")
        self.assertEqual(vp.format_time(61234), "1:01")

    def test_preview_missing_binding_reports_actual_python_and_native_errors_are_distinct(self):
        with patch.object(vp.sys, "executable", r"C:\Python314\python.exe"):
            message = vp.preview_error_message(ModuleNotFoundError("No module named 'vlc'", name="vlc"))
            self.assertIn("python-vlc", message)
            self.assertIn("run_gui.bat", message)
            self.assertIn(r"C:\Python314\python.exe", message)
            native = vp.preview_error_message(OSError("libvlc.dll"))
            self.assertIn("64bit VLC", native)
            self.assertIn("libvlc.dll", native)
            self.assertNotIn("現在のPythonに python-vlc がありません", native)

    def test_session_initialization_and_idempotent_cleanup(self):
        instance, player, media = Mock(), Mock(), Mock()
        instance.media_player_new.return_value = player
        instance.media_new_path.return_value = media
        vlc = SimpleNamespace(Instance=Mock(return_value=instance))
        with patch.object(vp.sys, "platform", "win32"), patch.object(vp.importlib, "import_module", return_value=vlc), patch.object(vp, "attach_windows") as attach:
            session = vp.VLCSession(Path("test.mp4"), 17)
            attach.assert_called_once_with(player, 17)
            player.set_media.assert_called_once_with(media)
            player.play.assert_not_called()
            session.close()
            session.close()
            player.stop.assert_called_once()
            player.release.assert_called_once()
            media.release.assert_called_once()
            instance.release.assert_called_once()

    def test_partial_open_failure_releases_all_objects(self):
        instance, player, media = Mock(), Mock(), Mock()
        instance.media_player_new.return_value = player
        instance.media_new_path.return_value = media
        vlc = SimpleNamespace(Instance=Mock(return_value=instance))
        with patch.object(vp.sys, "platform", "win32"), patch.object(vp.importlib, "import_module", return_value=vlc), patch.object(vp, "attach_windows", side_effect=RuntimeError("bad hwnd")):
            with self.assertRaisesRegex(RuntimeError, "bad hwnd"):
                vp.VLCSession(Path("test.mp4"), 17)
        player.stop.assert_called_once()
        player.release.assert_called_once()
        media.release.assert_called_once()
        instance.release.assert_called_once()

    def test_tab_switch_stops_hidden_player(self):
        app = SimpleNamespace(tabs=Mock(), result_panel=".result", history_panel=".history",
                              result_video=Mock(), history_video=Mock(), _history_selection_changed=Mock())
        app.tabs.select.return_value = ".history"
        gui.Application._output_tab_changed(app)
        app.result_video.stop.assert_called_once()
        app.history_video.stop.assert_not_called()
        app._history_selection_changed.assert_called_once()


if __name__ == "__main__":
    unittest.main()
