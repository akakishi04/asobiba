"""Generation categories must not conflate single H3 runs and long series."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from comfy_orchestrator import core, gui
from comfy_orchestrator.long_video import LONG_VIDEO_ID

class Var:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class GenerationModeTests(unittest.TestCase):
    def setUp(self):
        self.config = {"workflows": {
            "wai_t2i_basic": {"kind": "t2i", "bindings": {}},
            "wai_i2i_basic": {"kind": "i2i", "bindings": {"image": {}}},
            core.H3_I2V_ID: {"kind": "i2v", "bindings": {"image": {}}},
            core.WAN_I2V_ID: {"kind": "i2v", "bindings": {"image": {}}},
        }}

    def test_categories_are_disjoint_except_shared_h3_backend(self):
        self.assertEqual(gui.mode_workflow_ids(self.config, "image"),
                         ("自動", "wai_t2i_basic", "wai_i2i_basic"))
        self.assertEqual(gui.mode_workflow_ids(self.config, "video"),
                         (core.H3_I2V_ID, core.WAN_I2V_ID))
        self.assertEqual(gui.mode_workflow_ids(self.config, "continuous"),
                         (core.H3_I2V_ID,))
        self.assertEqual(gui.workflow_generation_mode(self.config, LONG_VIDEO_ID), "continuous")
        self.assertEqual(gui.workflow_generation_mode(self.config, core.H3_I2V_ID), "video")

    def test_stale_workflow_never_crosses_category(self):
        self.assertEqual(gui.choose_mode_workflow(self.config, "image", core.H3_I2V_ID), "自動")
        self.assertEqual(gui.choose_mode_workflow(self.config, "video", "wai_t2i_basic"), core.H3_I2V_ID)
        self.assertEqual(gui.choose_mode_workflow(self.config, "continuous", core.WAN_I2V_ID), core.H3_I2V_ID)

    def test_only_continuous_mode_exposes_long_controls(self):
        for mode in ("video", "continuous"):
            visibility = gui.parameter_visibility(self.config, core.H3_I2V_ID, generation_mode=mode)
            self.assertTrue(visibility["h3"])
            self.assertEqual(visibility["h3_long"], mode == "continuous")
        self.assertNotIn("単発", gui.CONTINUOUS_TARGETS)

    def test_switch_preserves_mode_specific_workflow_and_inputs(self):
        names = gui.workflow_display_names(self.config)
        app = SimpleNamespace(
            config=self.config, generation_mode=Var("video"),
            workflow=Var("wai_i2i_basic"), workflow_choice=Var(""), workflow_names=names,
            _mode_workflows={"image": "wai_i2i_basic", "video": core.WAN_I2V_ID,
                             "continuous": core.H3_I2V_ID},
            workflow_box=Mock(), reference_image=Var("ref.png"), prompt=Mock(),
            _update_generation_controls=Mock(),
        )
        app._sync_workflow_choice = lambda: gui.Application._sync_workflow_choice(app)
        gui.Application._on_generation_mode_choice(app)
        self.assertEqual(app.workflow.get(), core.WAN_I2V_ID)
        app.generation_mode.set("continuous")
        gui.Application._on_generation_mode_choice(app)
        self.assertEqual(app.workflow.get(), core.H3_I2V_ID)
        app.generation_mode.set("image")
        gui.Application._on_generation_mode_choice(app)
        self.assertEqual(app.workflow.get(), "wai_i2i_basic")
        self.assertEqual(app.reference_image.get(), "ref.png")
        app.prompt.delete.assert_not_called()
        app.prompt.insert.assert_not_called()

    def test_active_workflow_cannot_route_continuous_to_image(self):
        app = SimpleNamespace(config=self.config, generation_mode=Var("continuous"),
                              workflow=Var("wai_t2i_basic"), reference_image=Var(""))
        self.assertEqual(gui.Application._active_workflow(app), core.H3_I2V_ID)
        app.generation_mode.set("image")
        app.workflow.set(core.H3_I2V_ID)
        app.reference_image.set("ref.png")
        self.assertEqual(gui.Application._active_workflow(app), "wai_i2i_basic")


if __name__ == "__main__":
    unittest.main()
