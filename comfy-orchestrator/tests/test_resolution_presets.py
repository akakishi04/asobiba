"""Resolution shortcuts must not replace the saved pixel dimensions."""
import json
from pathlib import Path
import tkinter as tk
import unittest
from unittest.mock import Mock

from comfy_orchestrator import core, gui


class ResolutionPresetTests(unittest.TestCase):
    def setUp(self):
        self.interpreter = tk.Tcl()
        self.app = gui.Application.__new__(gui.Application)
        app = self.app
        app.width = tk.StringVar(master=self.interpreter, value="768")
        app.height = tk.StringVar(master=self.interpreter, value="768")
        app.resolution_preset = tk.StringVar(
            master=self.interpreter,
            value=gui.resolution_preset_label(app.width.get(), app.height.get()),
        )
        app.width.trace_add("write", app._sync_resolution_preset)
        app.height.trace_add("write", app._sync_resolution_preset)
        app.width_entry = Mock()
        app.height_entry = Mock()
        app.steps = tk.StringVar(master=self.interpreter, value="20")
        app.cfg = tk.StringVar(master=self.interpreter, value="5.0")
        app.seed = tk.StringVar(master=self.interpreter, value="")

    def tearDown(self):
        # Explicitly remove the variable traces before releasing the Tcl interpreter.
        for var in (self.app.width, self.app.height):
            for modes, callback in var.trace_info():
                var.trace_remove(modes, callback)

    def test_presets_are_unique_and_valid(self):
        sizes = list(gui.RESOLUTION_PRESETS.values())
        self.assertEqual(len(sizes), 9)
        self.assertEqual(len(set(sizes)), len(sizes))
        for width, height in sizes:
            with self.subTest(width=width, height=height):
                core.check_param("width", width)
                core.check_param("height", height)

    def test_each_preset_updates_real_generation_overrides(self):
        for label, (width, height) in gui.RESOLUTION_PRESETS.items():
            with self.subTest(label=label):
                self.app.resolution_preset.set(label)
                self.app._apply_resolution_preset()
                values = self.app._overrides()
                self.assertEqual((values["width"], values["height"]), (width, height))
                self.assertEqual(self.app.resolution_preset.get(), label)

    def test_manual_input_and_history_dimension_updates_sync_label(self):
        app = self.app
        self.assertEqual(app.resolution_preset.get(), gui.resolution_preset_label("768", "768"))
        app.width.set("")
        self.assertEqual(app.resolution_preset.get(), gui.CUSTOM_RESOLUTION)
        app.width.set("1000")
        app.height.set("1104")
        self.assertEqual(app.resolution_preset.get(), gui.CUSTOM_RESOLUTION)
        app.width.set("1280")
        app.height.set("720")
        self.assertEqual(app.resolution_preset.get(), gui.resolution_preset_label("1280", "720"))
        self.assertNotEqual(app.resolution_preset.get(), gui.CUSTOM_RESOLUTION)

    def test_custom_selection_preserves_size(self):
        app = self.app
        app.resolution_preset.set(gui.CUSTOM_RESOLUTION)
        app._apply_resolution_preset()
        self.assertEqual((app.width.get(), app.height.get()), ("768", "768"))
        app.width_entry.focus_set.assert_called_once_with()

    def test_workflow_controls_follow_supported_output_dimensions(self):
        app = self.app
        config_path = Path(__file__).resolve().parents[1] / "config.example.json"
        app.config = json.loads(config_path.read_text(encoding="utf-8"))
        app.workflow = tk.StringVar(master=self.interpreter, value="自動")
        app.composition_image = tk.StringVar(master=self.interpreter, value="")
        app.size_hint = tk.StringVar(master=self.interpreter, value="")
        app.resolution_box = Mock()
        app.denoise_entry = Mock()
        for workflow, state in (
            ("wai_t2i_basic", "readonly"),
            ("wai_i2i_basic", "disabled"),
            ("wai_inpaint_basic", "disabled"),
            ("wai_pose_detect", "readonly"),
            ("wai_pose_skeleton", "readonly"),
            ("missing", "disabled"),
        ):
            with self.subTest(workflow=workflow):
                app._active_workflow = Mock(return_value=workflow)
                app._update_generation_controls()
                app.resolution_box.configure.assert_called_with(state=state)


if __name__ == "__main__":
    unittest.main()
