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

    def test_cpu_encoder_is_scoped_to_h3_and_preserves_old_jobs(self):
        options = {"h3_model": "w4a8", "h3_turbo": "turbo8", "h3_encoder_device": "cpu"}
        graph = core.prepare_h3_workflow(self.graph, options, {"steps": 8})
        self.assertEqual(graph["13"]["inputs"]["device"], "cpu")
        self.assertEqual(graph["6"]["inputs"]["unet_name"], core.H3_MODELS["w4a8"])
        alternative = core.prepare_h3_workflow(self.graph, {
            **options, "h3_encoder_model": "int4", "h3_encoder_device": "default",
        }, {"steps": 8})
        self.assertEqual(alternative["13"]["inputs"]["clip_name"], core.H3_ENCODERS["int4"])
        self.assertEqual(alternative["13"]["inputs"]["device"], "default")
        self.assertEqual(self.graph["13"]["inputs"]["clip_name"], core.H3_ENCODERS["nvfp4"])
        with self.assertRaises(core.OrchestratorError):
            core.split_h3_options({"h3_encoder_model": "../unknown.safetensors"}, enabled=True)
        self.assertEqual(graph["9"]["inputs"]["steps"], 8)
        self.assertEqual(self.graph["13"]["inputs"]["device"], "default")
        self.assertEqual(core.prepare_h3_workflow(self.graph, {"h3_model": "int8"})["13"]["inputs"]["device"], "default")
        self.assertEqual(core.prepare_h3_workflow(self.graph, {**options, "h3_encoder_device": "default"})["13"]["inputs"]["device"], "default")
        with self.assertRaises(core.OrchestratorError):
            core.split_h3_options({"h3_encoder_device": "cuda:1"}, enabled=True)
        with self.assertRaises(core.OrchestratorError):
            core.split_h3_options({"h3_encoder_device": "cpu"}, enabled=False)

    def test_clipproj4b_uses_stock_loader_and_projection(self):
        options = {"h3_model": "w4a8", "h3_turbo": "turbo8",
                   "h3_encoder_model": "clipproj4b", "h3_encoder_device": "default"}
        graph = core.prepare_h3_workflow(self.graph, options, {"steps": 8})
        self.assertEqual(graph["13"]["inputs"], {
            "clip_name": "qwen3vl_4b_int8_convrot.safetensors",
            "type": "krea2", "device": "default",
        })
        self.assertEqual(graph["901"], {"class_type": "ClipProjApply", "inputs": {
            "clip": ["13", 0], "projection": core.H3_CLIPPROJ_MATRIX,
        }})
        self.assertEqual(graph["104"]["inputs"]["clip"], ["901", 0])
        self.assertEqual(graph["9"]["inputs"]["steps"], 8)
        self.assertEqual(graph["900"]["inputs"]["lora_name"], core.H3_TURBOS["turbo8"][0])
        self.assertEqual(self.graph["13"]["inputs"]["type"], "minimax")
        self.assertEqual(self.graph["104"]["inputs"]["clip"], ["13", 0])
        ordinary = core.prepare_h3_workflow(self.graph, {**options, "h3_encoder_model": "nvfp4"})
        self.assertNotIn("901", ordinary)
        self.assertEqual(ordinary["13"]["inputs"]["type"], "minimax")

    def test_clipproj_dependency_validation(self):
        graph = core.prepare_h3_workflow(self.graph, {
            "h3_model": "w4a8", "h3_turbo": "off",
            "h3_encoder_model": "clipproj4b",
        })
        loader_fields = {"UNETLoader": "unet_name", "CLIPLoader": "clip_name",
                         "VAELoader": "vae_name", "ClipProjApply": "projection"}
        def mock_info(missing):
            def info(base, route, **kwargs):
                node = route.rsplit("/", 1)[-1]
                if node == "ClipProjApply" and missing == "node":
                    return {}
                if node not in loader_fields:
                    return {node: {}}
                field = loader_fields[node]
                choices = [n["inputs"][field] for n in graph.values() if n["class_type"] == node]
                if node == "ClipProjApply" and missing == "matrix":
                    choices = []
                return {node: {"input": {"required": {field: [choices]}}}}
            return info
        comfy = core.ComfyUI(self.config["comfyui"])
        with patch.object(core, "http_json", side_effect=mock_info(None)):
            comfy.ensure_video_dependencies(graph)
        with patch.object(core, "http_json", side_effect=mock_info("node")):
            with self.assertRaisesRegex(core.OrchestratorError, "ClipProj Apply"):
                comfy.ensure_video_dependencies(graph)
        with patch.object(core, "http_json", side_effect=mock_info("matrix")):
            with self.assertRaisesRegex(core.OrchestratorError, "clip_projections"):
                comfy.ensure_video_dependencies(graph)

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
                               h3_model=Var("W4A8 Mixed"), h3_turbo=Var("8 Steps"),
                               h3_encoder_cpu=Var(True), h3_encoder_model=Var("INT4 ConvRot"))
        fake._h3_choices = lambda: gui.Application._h3_choices(fake)
        params = gui.Application._h3_overrides(fake)
        self.assertEqual(params["steps"], 8)
        self.assertEqual(params["h3_model"], "w4a8")
        self.assertEqual(params["h3_encoder_device"], "cpu")
        self.assertEqual(params["h3_encoder_model"], "int4")
        fake.h3_encoder_model.set("4B ClipProj (INT8)")
        self.assertEqual(gui.Application._h3_choices(fake)["h3_encoder_model"], "clipproj4b")
        fake.h3_encoder_model.set("INT4 ConvRot")
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
                      h3_model="w4a8", h3_turbo="turbo4", h3_encoder_device="cpu", h3_encoder_model="int4")
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
                self.assertEqual(rendered["13"]["inputs"]["device"], "cpu")
                self.assertEqual(rendered["13"]["inputs"]["clip_name"], core.H3_ENCODERS["int4"])
                self.assertEqual(rendered["900"]["inputs"]["lora_name"], core.H3_TURBOS["turbo4"][0])
                self.assertEqual(result["parameters"], params)
                self.assertEqual(rendered["15"]["inputs"]["noise_seed"], 7)


if __name__ == "__main__":
    unittest.main()
