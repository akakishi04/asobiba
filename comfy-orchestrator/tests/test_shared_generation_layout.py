"""Offline regression tests for a single shared image/video work surface."""
import inspect
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from comfy_orchestrator import core, gui

ROOT = Path(__file__).resolve().parents[1]


class Var:
    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class SharedLayoutTests(unittest.TestCase):
    def setUp(self):
        self.config = core.load_config(ROOT / "config.example.json")

    def test_only_contextual_fields_change_in_shared_grid(self):
        visibility = lambda key, custom=False: gui.parameter_visibility(self.config, key, custom)
        t2i = visibility("wai_t2i_basic")
        self.assertTrue(t2i["resolution"] and t2i["t2i_profile"])
        self.assertFalse(t2i["custom_size"] or t2i["denoise"] or t2i["h3"])
        self.assertTrue(visibility("wai_t2i_basic", True)["custom_size"])
        edit = visibility("wai_i2i_basic")
        self.assertTrue(edit["source_size"] and edit["denoise"] and edit["i2i_profile"])
        self.assertFalse(edit["resolution"] or edit["h3_profile"])
        self.assertTrue(visibility("wai_inpaint_basic")["denoise"])
        self.assertTrue(visibility("wai_pose_detect")["strength"])
        h3 = visibility(core.H3_I2V_ID, True)
        self.assertTrue(h3["h3"] and h3["steps"] and h3["seed"] and h3["h3_profile"])
        self.assertFalse(h3["resolution"] or h3["custom_size"] or h3["cfg"] or h3["denoise"] or h3["wan"])
        wan = visibility(core.WAN_I2V_ID)
        self.assertTrue(wan["wan"] and wan["cfg"] and wan["seed"])
        self.assertFalse(wan["h3"] or wan["h3_profile"] or wan["resolution"])

    def test_collapsed_references_keep_existing_inputs_visible(self):
        flags = dict(video=False, expanded=False, reference=False, mask=False, pose=False, composition=False)
        self.assertFalse(any(gui.reference_visibility(**flags).values()))
        self.assertTrue(gui.reference_visibility(**dict(flags, expanded=True))["pose"])
        self.assertTrue(gui.reference_visibility(**dict(flags, reference=True))["mask"])
        state = gui.reference_visibility(**dict(flags, video=True, mask=True, pose=True, composition=True))
        self.assertTrue(all(state.values()))

    def test_display_labels_round_trip_internal_workflow_id(self):
        names = gui.workflow_display_names(self.config)
        self.assertEqual(set(names), {"自動", *self.config["workflows"]})
        self.assertEqual(len(set(names.values())), len(names))
        self.assertIn("MiniMax H3", names[core.H3_I2V_ID])
        fake = SimpleNamespace(workflow_names=names, workflow_choice=Var(names[core.H3_I2V_ID]),
                               workflow=Var("自動"), _update_generation_controls=Mock())
        gui.Application._on_workflow_choice(fake)
        self.assertEqual(fake.workflow.get(), core.H3_I2V_ID)
        fake.workflow.set("wai_i2i_basic")
        gui.Application._sync_workflow_choice(fake)
        self.assertEqual(fake.workflow_choice.get(), names["wai_i2i_basic"])

    def test_hidden_dimensions_and_cfg_do_not_block_h3(self):
        fake = SimpleNamespace(config=self.config, parameter_widgets={},
                               _active_workflow=lambda: core.H3_I2V_ID,
                               width=Var(""), height=Var("bad"), cfg=Var("bad"),
                               steps=Var("20"), seed=Var(""))
        result = gui.Application._overrides(fake)
        self.assertEqual((result["width"], result["height"], result["cfg"]), (768, 768, 5))
        fake._active_workflow = lambda: "wai_t2i_basic"
        with self.assertRaises(ValueError):
            gui.Application._overrides(fake)

    def test_same_prompt_reference_and_result_widgets_for_all_workflows(self):
        source = inspect.getsource(gui.Application._build)
        self.assertEqual(source.count("self.prompt = scrolledtext.ScrolledText("), 1)
        self.assertEqual(source.count("self.reference_row, _ = input_row"), 1)
        self.assertLess(source.index("self.prompt ="), source.index("self.reference_row,"))
        self.assertEqual(source.count("self.tabs = ttk.Notebook("), 1)
        self.assertNotIn("日本語で指示を入力。", source)
        self.assertNotIn("T2Iは構図と光", source)
        self.assertNotIn("Seed空欄＝ランダム", source)
        self.assertNotIn("下へスクロール可能", source)


if __name__ == "__main__":
    unittest.main()
