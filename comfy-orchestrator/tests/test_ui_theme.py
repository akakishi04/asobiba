"""Readability and persistent-setting regressions for the Windows Tk GUI.

No Tk window or display server required for these tests.
"""

from __future__ import annotations

import unittest

from comfy_orchestrator import gui
from comfy_orchestrator.ui_theme import palette


def _luminance(hex_color: str) -> float:
    values = [int(hex_color[i : i + 2], 16) / 255.0 for i in (1, 3, 5)]
    linear = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in values]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast(a: str, b: str) -> float:
    x, y = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (x + 0.05) / (y + 0.05)


class TestTheme(unittest.TestCase):
    def test_light_and_dark_input_contrast(self):
        for dark in (False, True):
            with self.subTest(dark=dark):
                p = palette(dark)
                self.assertGreaterEqual(_contrast(p["text"], p["input"]), 7.0)
                self.assertGreaterEqual(_contrast(p["text"], p["surface"]), 7.0)

    def test_primary_button_contrast(self):
        for dark in (False, True):
            with self.subTest(dark=dark):
                p = palette(dark)
                self.assertGreaterEqual(_contrast("#FFFFFF", p["accent"]), 4.5)
                self.assertGreaterEqual(_contrast("#FFFFFF", p["accent_hover"]), 4.5)

    def test_palette_returns_copy(self):
        first = palette(True)
        first["text"] = "#000000"
        self.assertNotEqual(first["text"], palette(True)["text"])

    def test_gui_preserves_text_on_theme_switch(self):
        source = gui.Application._switch_theme.__code__.co_names
        self.assertIn("apply_ttk_theme", source)
        self.assertNotIn("delete", source)
        self.assertNotIn("insert", source)

    def test_theme_and_editor_font_are_persisted_with_other_settings(self):
        class Field:
            def __init__(self, value):
                self.value = value

            def get(self):
                return self.value

        from types import SimpleNamespace
        fake = SimpleNamespace(
            config={
                "llm": {"provider": "lmstudio", "base_url": "http://127.0.0.1:1234", "model": "a"},
                "comfyui": {"base_url": "http://127.0.0.1:8188"},
                "workflows": {},
            },
            llm_url=Field("http://127.0.0.1:57317"),
            comfy_url=Field("http://127.0.0.1:8188"),
            model=Field("gemma"),
            unload_llm=Field(True),
            free_comfy=Field(True),
            workflow=Field("自動"),
            dark_mode=Field(True),
            editor_font_size=Field(15),
            seed=Field(""),
            denoise=Field("0.53"),
            pose_mode=Field("skeleton"),
            control_strength=Field("0.85"),
            _overrides=lambda: {"width": 768, "height": 768, "steps": 20, "cfg": 5.0},
        )
        saved = gui.Application._collect_config(fake)
        self.assertEqual(saved["ui"]["font_size"], 15)
        self.assertTrue(saved["ui"]["dark_mode"])
        self.assertEqual(saved["ui"]["denoise"], "0.53")
        self.assertEqual(saved["llm"]["base_url"], "http://127.0.0.1:57317")

    def test_editor_font_size_has_safe_range(self):
        class State:
            def __init__(self, number):
                self.number = number

            def get(self):
                return self.number

            def set(self, number):
                self.number = number

        class FakeEditor:
            def __init__(self):
                self.font = None

            def configure(self, **kw):
                self.font = kw["font"]

        class FakeApp:
            editor_font_size = State(20)
            prompt = FakeEditor()

        obj = FakeApp()
        gui.Application._change_editor_font(obj, 3)
        self.assertEqual(obj.editor_font_size.get(), 20)
        gui.Application._change_editor_font(obj, -50)
        self.assertEqual(obj.editor_font_size.get(), 10)
        self.assertEqual(obj.prompt.font, ("Meiryo UI", 10))


if __name__ == "__main__":
    unittest.main()
