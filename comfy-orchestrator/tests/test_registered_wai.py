"""Offline regression for the shipped waiIllustrious API workflow and bindings."""

from __future__ import annotations

import unittest
from pathlib import Path

from comfy_orchestrator.core import load_config, load_workflow, render_workflow, validate_plan


ROOT = Path(__file__).resolve().parents[1]


class RegisteredWaiWorkflowTests(unittest.TestCase):
    def test_shipped_wai_t2i_can_be_loaded_and_rendered(self):
        config_path = ROOT / "config.example.json"
        config = load_config(config_path)
        self.assertIn("wai_t2i_basic", config["workflows"])
        selected = config["workflows"]["wai_t2i_basic"]
        self.assertEqual(selected["kind"], "t2i")
        self.assertNotIn("image", selected["bindings"])

        template = load_workflow(ROOT / selected["file"], selected["bindings"])
        self.assertEqual(template["2"]["inputs"]["ckpt_name"], "waiIllustriousSDXL_v170.safetensors")
        self.assertEqual(template["13"]["class_type"], "SaveImage")

        plan = {
            "workflow_id": "wai_t2i_basic",
            "parameters": {
                "positive_prompt": "1girl, silver hair, beach at sunset, anime style",
                "width": 768,
                "height": 768,
                "steps": 20,
                "cfg": 5.0,
                "seed": 12345,
            },
        }
        workflow_id, params = validate_plan(plan, config["workflows"], has_image=False)
        self.assertEqual(workflow_id, "wai_t2i_basic")
        self.assertEqual(params["negative_prompt"], "low quality, blurry, bad anatomy, extra fingers")

        rendered = render_workflow(template, selected["bindings"], params, image_name=None)
        self.assertEqual(rendered["8"]["inputs"]["text"], plan["parameters"]["positive_prompt"])
        self.assertEqual(rendered["5"]["inputs"]["text"], params["negative_prompt"])
        self.assertEqual(rendered["10"]["inputs"]["width"], 768)
        self.assertEqual(rendered["10"]["inputs"]["height"], 768)
        self.assertEqual(rendered["11"]["inputs"]["steps"], 20)
        self.assertEqual(rendered["11"]["inputs"]["cfg"], 5.0)
        self.assertEqual(rendered["11"]["inputs"]["seed"], 12345)

        # Editing a planned prompt cannot mutate the checked-in API template.
        self.assertEqual(template["10"]["inputs"]["width"], 1024)
        self.assertEqual(template["11"]["inputs"]["steps"], 28)


if __name__ == "__main__":
    unittest.main()
