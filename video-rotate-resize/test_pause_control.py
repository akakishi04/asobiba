import tempfile
import threading
import time
import unittest
from pathlib import Path

from pause_control import (
    PAUSE_DEEP,
    PAUSE_SOFT,
    get_pause_mode,
    wait_if_paused,
)


class PauseControlTests(unittest.TestCase):
    def test_wait_if_paused_runs_offload_and_restore_callbacks(self):
        with tempfile.TemporaryDirectory() as temp_name:
            marker = Path(temp_name) / "pause.flag"
            marker.write_text(PAUSE_SOFT, encoding="utf-8")
            calls = []

            def release():
                calls.append("offload")

            def restore():
                calls.append("restore")

            def resume_later():
                time.sleep(0.1)
                marker.unlink(missing_ok=True)

            thread = threading.Thread(target=resume_later, daemon=True)
            thread.start()
            paused = wait_if_paused(
                marker,
                "test",
                before_wait=release,
                after_wait=restore,
                accepted_modes={PAUSE_SOFT},
                poll_seconds=0.02,
            )
            thread.join(timeout=1)

            self.assertTrue(paused)
            self.assertEqual(calls, ["offload", "restore"])

    def test_deep_pause_mode_is_detected(self):
        with tempfile.TemporaryDirectory() as temp_name:
            marker = Path(temp_name) / "pause.flag"
            marker.write_text(PAUSE_DEEP, encoding="utf-8")
            self.assertEqual(get_pause_mode(marker), PAUSE_DEEP)
            self.assertFalse(
                wait_if_paused(
                    marker,
                    "test",
                    accepted_modes={PAUSE_SOFT},
                    poll_seconds=0.01,
                )
            )

    def test_empty_legacy_marker_defaults_to_soft(self):
        with tempfile.TemporaryDirectory() as temp_name:
            marker = Path(temp_name) / "pause.flag"
            marker.touch()
            self.assertEqual(get_pause_mode(marker), PAUSE_SOFT)

    def test_wait_returns_immediately_without_marker(self):
        with tempfile.TemporaryDirectory() as temp_name:
            marker = Path(temp_name) / "pause.flag"
            self.assertIsNone(get_pause_mode(marker))
            self.assertFalse(wait_if_paused(marker, "test"))


if __name__ == "__main__":
    unittest.main()
