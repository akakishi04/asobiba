"""Bounded, cancellable thumbnail reads; never create Tk objects in workers."""
from __future__ import annotations

from collections import OrderedDict
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
import queue
import threading

from .output_collection import IMAGE_EXTENSIONS, VIDEO_EXTENSIONS
from .video_media import FFmpeg

SIZE = (80, 48)


def thumbnail_png(path, cancel_event=None):
    """Use optional Pillow and FFmpeg. Unsupported/missing assets have no thumbnail."""
    from PIL import Image
    path = Path(path)
    if cancel_event is not None and cancel_event.is_set():
        return None
    if not path.is_file():
        return None

    def resize(source):
        with Image.open(source) as image:
            image.thumbnail(SIZE)
            rgba = image.convert("RGBA")
            buffer = BytesIO()
            rgba.save(buffer, format="PNG")
            return buffer.getvalue()

    suffix = path.suffix.lower()
    if suffix in IMAGE_EXTENSIONS:
        return resize(path)
    if suffix in VIDEO_EXTENSIONS:
        media = FFmpeg()
        with TemporaryDirectory(prefix="asobiba-thumb-") as folder:
            target = Path(folder) / "thumbnail.png"
            # Only decode the first frame; no full-video frame count or seek.
            media._run([media.ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
                        "-threads", "2", "-i", path, "-map", "0:v:0", "-frames:v", "1",
                        "-vf", "scale=80:48:force_original_aspect_ratio=decrease",
                        "-threads", "2", target], cancel_event, timeout=30)
            return resize(target)
    return None


class ThumbnailLoader:
    """One current request and bounded cache; stale results are never published."""
    def __init__(self, *, load=thumbnail_png, limit=256):
        self.load = load
        self.limit = limit
        self.cache = OrderedDict()
        self.lock = threading.Lock()
        self.messages = queue.Queue()
        self.generation = 0
        self.event = None

    def cancel(self):
        if self.event is not None:
            self.event.set()
        self.generation += 1
        self.event = None
        # Old worker output can still arrive; consumers discard by generation.
        self.drain()

    def request(self, items):
        self.cancel()
        generation = self.generation
        event = self.event = threading.Event()

        def task():
            try:
                for row_id, path in items:
                    if event.is_set():
                        break
                    data = None
                    try:
                        path = Path(path)
                        stat = path.stat()
                        key = (path.resolve(), stat.st_size, stat.st_mtime_ns)
                        with self.lock:
                            data = self.cache.get(key)
                            if data is not None:
                                self.cache.move_to_end(key)
                        if data is None:
                            data = self.load(path, event)
                            if data is not None and not event.is_set():
                                with self.lock:
                                    self.cache[key] = data
                                    self.cache.move_to_end(key)
                                    while len(self.cache) > self.limit:
                                        self.cache.popitem(last=False)
                    except Exception:
                        # A bad file or missing optional dependency must not
                        # prevent the other history rows from being shown.
                        pass
                    if not event.is_set():
                        self.messages.put((generation, row_id, data))
            finally:
                if not event.is_set():
                    self.messages.put((generation, None, None))
        threading.Thread(target=task, daemon=True).start()

    def drain(self):
        rows = []
        while True:
            try:
                generation, row_id, data = self.messages.get_nowait()
            except queue.Empty:
                break
            if generation == self.generation:
                rows.append((row_id, data))
        return rows
