"""Offline checks for optional Explorer file D&D in character references."""

from __future__ import annotations

import sys
import tempfile
import tkinter as tk
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from comfy_orchestrator import character_refs, file_drop
from comfy_orchestrator.character_ui import CharacterReferenceWindow


class FileDropParsingTests(unittest.TestCase):
    def test_tcl_path_list_preserves_spaces_and_unicode_in_batch(self):
        interp = tk.Tcl()  # A display server is NOT needed.
        raw = "{C:/Art Files/正面 画像.png} {C:/Art Files/横 顔.webp} C:/tmp/third.jpg"
        paths = file_drop.split_dropped_paths(interp, raw)
        self.assertEqual(paths, (
            "C:/Art Files/正面 画像.png",
            "C:/Art Files/横 顔.webp",
            "C:/tmp/third.jpg",
        ))

    def test_empty_or_invalid_drop_event_is_ignored(self):
        interp = tk.Tcl()
        self.assertEqual(file_drop.split_dropped_paths(interp, " "), ())
        self.assertEqual(file_drop.split_dropped_paths(interp, ""), ())
        self.assertEqual(file_drop.split_dropped_paths(interp, None), ())

    def test_native_drop_callback_uses_tcl_list_not_whitespace_split(self):
        interp = tk.Tcl()
        captured = []
        class FakeTarget:
            tk = interp
            def drop_target_register(self, *types):
                self.types = types
            def dnd_bind(self, name, callback):
                self.event_name = name
                self.callback = callback
        target = FakeTarget()
        fake_package = types.ModuleType("tkinterdnd2")
        fake_package.DND_FILES = "DND_Files"
        with patch.dict(sys.modules, {"tkinterdnd2": fake_package}):
            self.assertTrue(file_drop.register_file_drop(target, captured.append))
        self.assertEqual(target.types, ("DND_Files",))
        self.assertEqual(target.event_name, "<<Drop>>")
        action = target.callback(SimpleNamespace(
            data="{C:/Images/abc def.png} {C:/Images/あ い.jpg}",
        ))
        self.assertEqual(action, "copy")
        self.assertEqual(captured, [(
            "C:/Images/abc def.png", "C:/Images/あ い.jpg",
        )])

    def test_missing_optional_dependency_keeps_file_picker_fallback(self):
        class Widget:
            def drop_target_register(self, *args):
                raise AssertionError("missing dependency should prevent registration")
            def dnd_bind(self, *args):
                raise AssertionError("missing dependency should prevent registration")
        with patch.dict(sys.modules, {"tkinterdnd2": None}):
            self.assertFalse(file_drop.register_file_drop(Widget(), lambda _v: None))
            self.assertFalse(file_drop.enable_native_dnd(object()))

    def test_can_enable_native_drop_in_existing_tk_root(self):
        fake_package = types.ModuleType("tkinterdnd2")
        calls = []
        fake_package.TkinterDnD = SimpleNamespace(
            require=lambda root: calls.append(root),
        )
        root = object()
        with patch.dict(sys.modules, {"tkinterdnd2": fake_package}):
            self.assertTrue(file_drop.enable_native_dnd(root))
        self.assertEqual(calls, [root])


class CharacterImageBatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name).resolve()
        self.images = []
        for i, suffix in enumerate((".png", ".jpg", ".webp", ".PNG", ".png")):
            p = root / f"人物 画像 {i}{suffix}"
            p.write_bytes(b"fake-image-content")
            self.images.append(p)

    def test_multi_drop_appends_without_duplicates(self):
        result = character_refs.add_character_image_files(
            [self.images[0]], [str(self.images[0]), str(self.images[1]), str(self.images[2])]
        )
        self.assertEqual(result, tuple(self.images[:3]))

    def test_four_images_allowed_then_extra_rejected_atomically(self):
        existing = tuple(self.images[:2])
        self.assertEqual(len(character_refs.add_character_image_files(
            existing, [str(self.images[2]), str(self.images[3])],
        )), 4)
        with self.assertRaisesRegex(RuntimeError, "最大4枚"):
            character_refs.add_character_image_files(existing, [
                str(self.images[2]), str(self.images[3]), str(self.images[4]),
            ])
        self.assertEqual(existing, tuple(self.images[:2]))

    def test_invalid_extension_or_directory_rejects_whole_drop(self):
        bad_file = Path(self.tmp.name) / "wrong.txt"
        bad_file.write_text("not image")
        for invalid in (bad_file, Path(self.tmp.name)):
            with self.subTest(invalid=invalid):
                with self.assertRaises(RuntimeError):
                    character_refs.add_character_image_files(
                        [self.images[0]], [self.images[1], invalid]
                    )

    def test_batched_drop_reuses_same_gui_add_logic(self):
        class State:
            def __init__(self):
                self.value = ""
            def set(self, value):
                self.value = value
        log = []
        fake = SimpleNamespace(
            images=[self.images[0]],
            busy=False,
            text_only=False,
            status=State(),
            window=None,
            _refresh=lambda: log.append("refresh"),
            _invalidate=lambda: log.append("invalidate"),
        )
        CharacterReferenceWindow._add_files(
            fake, (str(self.images[1]), str(self.images[2])),
        )
        self.assertEqual(fake.images, self.images[:3])
        self.assertEqual(log, ["refresh", "invalidate"])
        self.assertIn("3枚を登録", fake.status.value)

    def test_busy_gui_does_not_change_references(self):
        fake = SimpleNamespace(images=[self.images[0]], busy=True)
        CharacterReferenceWindow._add_files(fake, (str(self.images[1]),))
        self.assertEqual(fake.images, self.images[:1])


if __name__ == "__main__":
    unittest.main()
