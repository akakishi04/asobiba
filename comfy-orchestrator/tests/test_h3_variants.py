"""Host-only H3 model selection and Turbo LoRA regressions."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from comfy_orchestrator import core, gui, lmstudio

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config.example.json"


class Var:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class H3VariantTests(unittest.TestCase):
    def setUp(self):
        self.config = core.load_config(CONFIG)
        self.entry = self.config["workflows"][core.H3_I2V_ID]
        self.graph = core.load_workflow(ROOT / self.entry["file"], self.entry["bindings"])

    def test_all_six_model_turbo_combinations(self):
        for model in core.H3_MODELS:
            for turbo, (filename, steps) in core.H3_TURBOS.items():
                with self.subTest(model=model, turbo=turbo):
                    opts = {"h3_model": model, "h3_turbo": turbo}
                    graph = core.prepare_h3_workflow(self.graph, opts, {"steps": steps or 20})
                    self.assertEqual(graph["6"]["inputs"]["unet_name"], core.H3_MODELS[model])
                    loras = [(key, n) for key, n in graph.items() if n["class_type"] == "LoraLoaderModelOnly"]
                    if filename:
                        self.assertEqual(len(loras), 1)
                        node, lora = loras[0]
                        self.assertEqual(lora["inputs"], {"model": ["6", 0], "lora_name": filename, "strength_model": 1.0})
                        self.assertEqual(graph["9"]["inputs"]["model"], [node, 0])
                        self.assertEqual(graph["16"]["inputs"]["model"], [node, 0])
                        self.assertEqual(graph["9"]["inputs"]["steps"], steps)
                        self.assertEqual(graph["17"]["inputs"]["sampler_name"], "res_multistep")
                    else:
                        self.assertFalse(loras)
        self.assertEqual(self.graph["6"]["inputs"]["unet_name"], core.H3_MODELS["int8"])
        self.assertEqual(self.graph["9"]["inputs"]["model"], ["6", 0])
        self.assertIs(core.prepare_h3_workflow(self.graph, {}), self.graph)

    def test_invalid_options_and_turbo_steps(self):
        for bad in ({"h3_model": "../arbitrary.safetensors"}, {"h3_turbo": ["turbo8"]}):
            with self.assertRaises(core.OrchestratorError):
                core.split_h3_options(bad, enabled=True)
        with self.assertRaises(core.OrchestratorError):
            core.split_h3_options({"h3_model": "w4a8"}, enabled=False)
        with self.assertRaises(core.OrchestratorError):
            core.prepare_h3_workflow(self.graph, {"h3_model": "w4a8", "h3_turbo": "turbo8"}, {"steps": 4})

    def test_gui_choices_are_retained_and_steps_are_independent(self):
        fake = SimpleNamespace(h3_size=Var("864 × 480"), h3_duration=Var("約5秒 (124f)"),
                               steps=Var("20"), h3_steps=Var("17"), seed=Var("7"),
                               h3_model=Var("W4A8 Mixed"), h3_turbo=Var("8 Steps"))
        fake._h3_choices = lambda: gui.Application._h3_choices(fake)
        params = gui.Application._h3_overrides(fake)
        self.assertEqual(params["steps"], 8)
        self.assertEqual(params["h3_model"], "w4a8")
        self.assertEqual(gui.image_aware_overrides(self.config, core.H3_I2V_ID, True, params, "0.53"), params)
        fake.h3_turbo.set("OFF")
        self.assertEqual(gui.Application._h3_overrides(fake)["steps"], 17)
        self.assertEqual(fake.steps.get(), "20")

    def test_dry_run_host_options_are_not_llm_fields(self):
        schema = core.plan_schema({core.H3_I2V_ID: self.entry})
        self.assertEqual(set(schema["properties"]["parameters"]["properties"]), {"positive_prompt"})
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "first.png"
            image.write_bytes(b"image")
            with patch.object(lmstudio.LMStudio, "interpret", return_value={
                "workflow_id": core.H3_I2V_ID,
                "parameters": {"positive_prompt": "Hair moves.", "h3_model": "int8", "steps": 150},
            }):
                result = core.execute(self.config, CONFIG, "動かす", image=image, dry_run=True,
                                      selected_workflow=core.H3_I2V_ID,
                                      overrides={"h3_model": "w4a8", "h3_turbo": "turbo8", "steps": 20, "seed": 7})
        self.assertEqual(result["parameters"]["h3_model"], "w4a8")
        self.assertEqual(result["parameters"]["h3_turbo"], "turbo8")
        self.assertEqual(result["parameters"]["steps"], 8)

    def test_missing_lora_is_detected(self):
        graph = core.prepare_h3_workflow(self.graph, {"h3_model": "w4a8", "h3_turbo": "turbo4"})
        loaders = {"UNETLoader": "unet_name", "CLIPLoader": "clip_name", "VAELoader": "vae_name",
                   "LoraLoaderModelOnly": "lora_name"}
        def info(base, route, **kwargs):
            node = route.rsplit("/", 1)[-1]
            if node not in loaders:
                return {node: {}}
            field = loaders[node]
            choices = [] if node == "LoraLoaderModelOnly" else [n["inputs"][field] for n in graph.values() if n["class_type"] == node]
            return {node: {"input": {"required": {field: [choices]}}}}
        with patch.object(core, "http_json", side_effect=info):
            with self.assertRaisesRegex(core.OrchestratorError, "turbo_4step_v1.3"):
                core.ComfyUI(self.config["comfyui"]).ensure_video_dependencies(graph)

    def test_replay_restores_saved_variant_not_current_gui(self):
        params = dict(self.entry["defaults"], positive_prompt="Hair moves.", seed=7, steps=4,
                      h3_model="w4a8", h3_turbo="turbo4")
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "first.png"
            image.write_bytes(b"image")
            with patch.object(core, "ComfyUI") as factory:
                comfy = factory.return_value
                comfy.upload_image.return_value = "first.png"
                comfy.submit.return_value = "id"
                comfy.wait.return_value = {"outputs": {}}
                result = core.execute_saved(self.config, CONFIG, core.H3_I2V_ID, params, reference_image=image)
                rendered = comfy.submit.call_args.args[0]
                checked = comfy.ensure_video_dependencies.call_args.args[0]
                self.assertEqual(checked["6"]["inputs"]["unet_name"], core.H3_MODELS["w4a8"])
                self.assertEqual(rendered["9"]["inputs"]["steps"], 4)
                self.assertEqual(rendered["900"]["inputs"]["lora_name"], core.H3_TURBOS["turbo4"][0])
                self.assertEqual(result["parameters"], params)
                self.assertEqual(rendered["15"]["inputs"]["noise_seed"], 7)


if __name__ == "__main__":
    unittest.main()
