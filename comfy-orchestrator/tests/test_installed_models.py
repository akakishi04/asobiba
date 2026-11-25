"""Installed-model routing and Qwen/SDXL host selections."""
import unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

from comfy_orchestrator import core, gui, lmstudio

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config.example.json"


class InstalledModelsTests(unittest.TestCase):
    def setUp(self):
        self.config = core.load_config(CONFIG)

    def test_choices_use_matching_loader_and_family(self):
        result = core.installed_model_choices({
            "UNETLoader": [core.H3_MODELS["w4a8"], core.H3_MODELS["gguf_u16g"],
                           core.H3_MODELS["s3_raw"], "unrelated.safetensors"],
            "UnetLoaderGGUF": [core.H3_MODELS["gguf_u16g"]],
            "CheckpointLoaderSimple": ["Illustrious-XL-v2.0.safetensors",
                                       "Stable Diffusion XL Turbo.safetensors",
                                       "other_model.safetensors", "../Illustrious.safetensors"],
        })
        self.assertEqual(result["h3"], ("w4a8", "gguf_u16g", "s3_raw"))
        self.assertEqual(result["sdxl"], ("Illustrious-XL-v2.0.safetensors",
                                         "Stable Diffusion XL Turbo.safetensors"))

    def test_inventory_uses_no_generation_and_missing_optional_gguf(self):
        def info(base, route, **kwargs):
            kind = route.rsplit("/", 1)[-1]
            if kind == "UnetLoaderGGUF":
                return {}
            field = "ckpt_name" if kind == "CheckpointLoaderSimple" else "unet_name"
            return {kind: {"input": {"required": {field: [["example.safetensors"]]}}}}
        with patch.object(core, "http_json", side_effect=info) as api:
            inventory = core.ComfyUI(self.config["comfyui"]).list_generation_models()
        self.assertEqual(inventory["UnetLoaderGGUF"], ())
        self.assertEqual(api.call_count, 3)
        self.assertTrue(all(call.args[1].startswith("/object_info/") for call in api.call_args_list))

    def test_checkpoint_replay_preserves_saved_file_and_turbo_sampler(self):
        key = "wai_t2i_basic"
        params = dict(self.config["workflows"][key]["defaults"], positive_prompt="Landscape", seed=7,
                      checkpoint_model="Stable Diffusion XL Turbo.safetensors", steps=4, cfg=1)
        with patch.object(core, "ComfyUI") as factory:
            comfy = factory.return_value
            comfy.submit.return_value = "id"
            comfy.wait.return_value = {"outputs": {}}
            result = core.execute_saved(self.config, CONFIG, key, params)
            rendered = comfy.submit.call_args.args[0]
            self.assertEqual(rendered["2"]["inputs"]["ckpt_name"], params["checkpoint_model"])
            self.assertEqual(rendered["11"]["inputs"]["sampler_name"], "euler_ancestral")
            self.assertEqual(result["parameters"], params)

    def test_checkpoint_rejects_wrong_workflow_and_path(self):
        for name, key in (("../Illustrious.safetensors", "wai_t2i_basic"),
                          ("sd_xl_turbo_1.0.safetensors", "wai_i2i_basic"),
                          ("Illustrious-XL-v2.0.safetensors", core.H3_I2V_ID)):
            with self.subTest(name=name, key=key), self.assertRaises(core.OrchestratorError):
                core.split_checkpoint_option({"checkpoint_model": name}, {key})

    def test_qwen_lightning_fixed_host_parameters_and_replay(self):
        key = core.QWEN_LIGHTNING_ID
        with patch.object(lmstudio.LMStudio, "interpret", return_value={
            "workflow_id": key, "parameters": {"positive_prompt": "A blue sky.", "steps": 50, "cfg": 6},
        }), patch.object(core, "ComfyUI") as factory:
            comfy = factory.return_value
            comfy.submit.return_value = "id"
            comfy.wait.return_value = {"outputs": {}}
            result = core.execute(self.config, CONFIG, "青い空", selected_workflow=key,
                                  overrides={"width": 1024, "height": 1024, "seed": 7, "steps": 20})
            self.assertEqual(result["parameters"]["steps"], 4)
            self.assertEqual(result["parameters"]["cfg"], 1)
            graph = comfy.submit.call_args.args[0]
            self.assertEqual(graph["222"]["inputs"]["model"], ["221", 0])
            self.assertEqual(graph["230"]["inputs"]["steps"], 4)
            self.assertEqual(graph["232"]["class_type"], "EmptySD3LatentImage")
            core.execute_saved(self.config, CONFIG, key, result["parameters"])
            self.assertEqual(comfy.submit.call_args.args[0], graph)

    def test_qwen_visibility_and_auto_still_routing(self):
        v = gui.parameter_visibility(self.config, core.QWEN_T2I_ID)
        self.assertTrue(v["qwen_steps"])
        self.assertFalse(v["checkpoint"] or v["t2i_profile"] or v["h3"])
        self.assertEqual(gui.resolve_generation_workflow(self.config, "自動", False),
                         "wai_t2i_basic")
        self.assertEqual(gui.resolve_generation_workflow(self.config, core.QWEN_T2I_ID, False),
                         core.QWEN_T2I_ID)


if __name__ == "__main__":
    unittest.main()
