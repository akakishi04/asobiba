"""Tests for Windows Japanese IME conversion font, without a GUI or Windows."""

from __future__ import annotations

import ctypes
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from comfy_orchestrator import ime_font


class Editor:
    def __init__(self):
        self.bindings = {}
        self.focused = True
        self.pending = []

    def focus_get(self):
        return self if self.focused else None

    def cget(self, name):
        assert name == "font"
        return ("Meiryo UI", 12)

    def winfo_id(self):
        return 1234

    def winfo_toplevel(self):
        return self

    def after_idle(self, callback):
        self.pending.append(callback)

    def bind(self, sequence, callback, add=None):
        self.bindings[sequence] = (callback, add)


class TestNativeIMEFont(unittest.TestCase):
    def test_logfont_point_to_pixel_scaling(self):
        self.assertEqual(ime_font.logical_font("Meiryo UI", 12, 96).lfHeight, -16)
        self.assertEqual(ime_font.logical_font("Meiryo UI", 12, 144).lfHeight, -24)
        self.assertEqual(ime_font.logical_font("Meiryo UI", -16, 144).lfHeight, -16)
        self.assertEqual(ime_font.logical_font("Meiryo UI", 12, 96).lfFaceName, "Meiryo UI")
        self.assertEqual(ime_font.logical_font("Meiryo UI", 12, 96, bold=True).lfWeight, 700)

    def test_nothing_on_non_windows(self):
        editor = Editor()
        with patch.object(ime_font, "_is_windows", return_value=False):
            self.assertFalse(ime_font.sync_native_ime_font(editor))
            ime_font.install_native_ime_font(editor)
        self.assertFalse(editor.bindings)

    def test_unsafe_font_arguments_rejected(self):
        for size, dpi in ((0, 96), (12, 0), (12, -1)):
            with self.subTest(size=size, dpi=dpi):
                with self.assertRaises(ValueError):
                    ime_font.logical_font("Meiryo UI", size, dpi)

    def test_set_font_and_release_native_handles(self):
        editor = Editor()
        actions = []

        class User32:
            def GetFocus(self):
                return 1234
            def GetDC(self, hwnd):
                return 111
            def ReleaseDC(self, hwnd, dc):
                actions.append(("release_dc", hwnd, dc))

        class Gdi32:
            def GetDeviceCaps(self, dc, index):
                self_test.assertEqual(index, ime_font.LOGPIXELSY)
                return 144

        class Imm32:
            def ImmGetContext(self, hwnd):
                return 222
            def ImmSetCompositionFontW(self, himc, pointer):
                font = ctypes.cast(pointer, ctypes.POINTER(ime_font.LOGFONTW)).contents
                actions.append(("set_font", himc, font.lfHeight, font.lfFaceName))
                return True
            def ImmReleaseContext(self, hwnd, himc):
                actions.append(("release_ime", hwnd, himc))

        class Font:
            def __init__(self, *, root, font):
                self_test.assertIs(root, editor)
                self_test.assertEqual(font, ("Meiryo UI", 12))
            def actual(self):
                return {"family": "Meiryo UI", "size": 12, "weight": "normal"}

        self_test = self
        with patch.object(ime_font, "_is_windows", return_value=True), \
             patch.object(ime_font, "_native_api", return_value=(User32(), Imm32(), Gdi32())), \
             patch.object(ime_font.tkfont, "Font", Font):
            self.assertTrue(ime_font.sync_native_ime_font(editor))
        self.assertEqual(actions, [
            ("release_dc", 1234, 111),
            ("set_font", 222, -24, "Meiryo UI"),
            ("release_ime", 1234, 222),
        ])

    def test_not_applied_if_editor_is_not_focused(self):
        editor = Editor()
        editor.focused = False
        with patch.object(ime_font, "_is_windows", return_value=True), \
             patch.object(ime_font, "_native_api", side_effect=AssertionError("must not call Win32")):
            self.assertFalse(ime_font.sync_native_ime_font(editor))

    def test_event_bindings_preserve_regular_typing(self):
        editor = Editor()
        with patch.object(ime_font, "_is_windows", return_value=True), \
             patch.object(ime_font, "sync_native_ime_font", return_value=True) as sync:
            ime_font.install_native_ime_font(editor)
            self.assertEqual(set(editor.bindings), {"<FocusIn>", "<KeyPress>"})
            self.assertTrue(all(add == "+" for _, add in editor.bindings.values()))
            editor.bindings["<FocusIn>"][0](SimpleNamespace())
            self.assertEqual(sync.call_count, 0)
            editor.pending[0]()
            editor.bindings["<KeyPress>"][0](SimpleNamespace(keycode=ime_font.IME_KEYCODE))
            editor.bindings["<KeyPress>"][0](SimpleNamespace(keycode=65))
            self.assertEqual(sync.call_count, 2)


if __name__ == "__main__":
    unittest.main()
