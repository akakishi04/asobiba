"""Thumbnail decoding is bounded, independent of Tk, and safe to cancel."""
import io
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import Mock

from comfy_orchestrator.history_thumbnails import SIZE, ThumbnailLoader, thumbnail_png
from comfy_orchestrator.video_media import FFmpeg
from comfy_orchestrator.parameters import OrchestratorError


class ThumbnailTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)

    def wait(self, loader):
        result = []
        until = time.monotonic() + 5
        while time.monotonic() < until:
            result.extend(loader.drain())
            if (None, None) in result:
                return result
            time.sleep(0.01)
        self.fail("thumbnail worker did not finish")

    def test_image_is_downscaled_without_altering_original(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow unavailable")
        path = self.root / "picture.png"
        Image.new("RGB", (320, 160), "red").save(path)
        original = path.read_bytes()
        raw = thumbnail_png(path)
        with Image.open(io.BytesIO(raw)) as image:
            self.assertEqual(image.size, (80, 40))
        self.assertEqual(path.read_bytes(), original)

    def test_video_thumbnail_is_a_small_first_frame(self):
        try:
            from PIL import Image
            media = FFmpeg()
        except (ImportError, OrchestratorError) as exc:
            self.skipTest(str(exc))
        path = self.root / "clip.mp4"
        media._run([media.ffmpeg, "-v", "error", "-y", "-f", "lavfi", "-i",
                    "testsrc2=s=160x96:r=24", "-frames:v", "4", "-c:v", "libx264",
                    "-pix_fmt", "yuv420p", path])
        with Image.open(io.BytesIO(thumbnail_png(path))) as image:
            self.assertEqual(image.size, SIZE)

    def test_cache_reuses_exact_file_and_reloads_after_change(self):
        path = self.root / "x.png"
        path.write_bytes(b"first")
        load = Mock(return_value=b"png")
        loader = ThumbnailLoader(load=load, limit=2)
        loader.request((("a", path),))
        self.assertEqual(self.wait(loader), [("a", b"png"), (None, None)])
        loader.request((("b", path),))
        self.assertEqual(self.wait(loader), [("b", b"png"), (None, None)])
        load.assert_called_once()
        path.write_bytes(b"changed")
        loader.request((("c", path),))
        self.wait(loader)
        self.assertEqual(load.call_count, 2)

    def test_cancelled_worker_never_returns_old_page(self):
        a, b = self.root / "a.png", self.root / "b.png"
        a.write_bytes(b"a")
        b.write_bytes(b"b")
        started = threading.Event()
        gate = threading.Event()
        def load(path, event):
            if path == a:
                started.set()
                gate.wait(3)
            return path.read_bytes()
        loader = ThumbnailLoader(load=load)
        loader.request((("old", a),))
        self.assertTrue(started.wait(3))
        loader.request((("new", b),))
        gate.set()
        self.assertEqual(self.wait(loader), [("new", b"b"), (None, None)])


if __name__ == "__main__":
    unittest.main()
