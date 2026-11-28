"""Anima profile, model picker and graph contracts without GPU access."""
import unittest
from pathlib import Path
from unittest.mock import patch

from comfy_orchestrator import core, image_prompts
from comfy_orchestrator.model_profiles import (
    ANIMA_ID, ANIMA_BASE, anima_model_name, anima_models,
    image_model_choices, selected_label, defaults_for,
)
from comfy_orchestrator.generation_form import resolve_generation_workflow

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config.example.json"
MODEL = "anima/AnimaIka_v52.safetensors"


class ImageModelProfileTests(unittest.TestCase):
    def setUp(self):
        self.config = core.load_config(CONFIG)

    def test_anima_discovery_and_path_safety(self):
        names = [MODEL, ANIMA_BASE, "animagineXL.safetensors", "../AnimaIka.safetensors",
                 "unrelated.safetensors", "anima.gguf"]
        self.assertEqual(anima_models({"UNETLoader": names}), (MODEL, ANIMA_BASE))
        self.assertTrue(anima_model_name("anima/AnimaIka_v52.safetensors"))
        self.assertFalse(anima_model_name("C:/AnimaIka.safetensors"))

    def test_model_picker_maps_to_graph_and_defaults(self):
        choices = image_model_choices(self.config["workflows"], {"UNETLoader": [MODEL]},
                                     ("waiIllustriousSDXL_v170.safetensors",),
                                     "waiIllustriousSDXL_v170.safetensors", MODEL)
        item = next(c for c in choices if c.filename == MODEL)
        self.assertEqual(item.workflow_id, ANIMA_ID)
        self.assertEqual(defaults_for(self.config["workflows"], item)["steps"], 28)
        self.assertEqual(selected_label(choices, ANIMA_ID, "", MODEL), item.label)
        self.assertEqual(resolve_generation_workflow(self.config, ANIMA_ID, False), ANIMA_ID)
        self.assertEqual(resolve_generation_workflow(self.config, ANIMA_ID, True), ANIMA_ID)
        self.assertEqual(resolve_generation_workflow(self.config, "wai_t2i_basic", True), "wai_i2i_basic")
        self.assertEqual(image_prompts.prompt_format(ANIMA_ID), "tags")

    def test_anima_checkpoint_saved_and_preflighted(self):
        params = {**self.config["workflows"][ANIMA_ID]["defaults"],
                  "positive_prompt": "tree", "seed": 19, "checkpoint_model": MODEL}
        with patch.object(core, "ComfyUI") as factory:
            comfy = factory.return_value
            comfy.submit.return_value = "test"
            comfy.wait.return_value = {"outputs": {}}
            result = core.execute_saved(self.config, CONFIG, ANIMA_ID, params)
            graph = comfy.submit.call_args.args[0]
            self.assertEqual(graph["2"]["inputs"]["unet_name"], MODEL)
            self.assertEqual(graph["3"]["inputs"]["clip_name"], "qwen_3_06b_base.safetensors")
            self.assertEqual(graph["3"]["inputs"]["type"], "stable_diffusion")
            self.assertEqual(graph["4"]["inputs"]["vae_name"], "qwen_image_vae.safetensors")
            self.assertEqual(graph["5"]["inputs"]["shift"], 3)
            self.assertEqual(graph["8"]["class_type"], "EmptyLatentImage")
            self.assertEqual(result["parameters"], params)
            comfy.ensure_video_dependencies.assert_called_once()

    def test_anima_cannot_use_sdxl_or_arbitrary_unet(self):
        for workflow, model in [(ANIMA_ID, "other.safetensors"),
                                ("wai_t2i_basic", MODEL),
                                (ANIMA_ID, "../AnimaIka.safetensors")]:
            with self.assertRaises(core.OrchestratorError):
                core.split_checkpoint_option({"checkpoint_model": model}, {workflow})


if __name__ == "__main__":
    unittest.main()
