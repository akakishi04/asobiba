import tempfile
import threading
import time
import unittest
from pathlib import Path

from pause_control import wait_if_paused


class PauseControlTests(unittest.TestCase):
    def test_wait_if_paused_runs_offload_and_restore_callbacks(self):
        with tempfile.TemporaryDirectory() as temp_name:
            marker = Path(temp_name) / "pause.flag"
            marker.touch()
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
                poll_seconds=0.02,
            )
            thread.join(timeout=1)

            self.assertTrue(paused)
            self.assertEqual(calls, ["offload", "restore"])

    def test_wait_returns_immediately_without_marker(self):
        with tempfile.TemporaryDirectory() as temp_name:
            marker = Path(temp_name) / "pause.flag"
            self.assertFalse(wait_if_paused(marker, "test"))


if __name__ == "__main__":
    unittest.main()
