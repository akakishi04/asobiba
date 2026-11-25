"""H3 Ref2VA uses a true reference node, not a resized first frame."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, Mock

from comfy_orchestrator import core, gui, lmstudio
from comfy_orchestrator.prompt_profiles import apply_h3_profile, DEFAULT_H3_PROFILE

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config.example.json"
FILENAME = "Sulphur/s3_ref2va_w4a8.safetensors"
MODEL = "ref2va:" + FILENAME


class Ref2VATests(unittest.TestCase):
    def setUp(self):
        self.config = core.load_config(CONFIG)
        self.entry = self.config["workflows"][core.H3_I2V_ID]
        self.graph = core.load_workflow(ROOT / self.entry["file"], self.entry["bindings"])
        self.options = {
            "h3_model": MODEL, "h3_turbo": "off",
            "h3_encoder_model": "clipproj4b", "h3_encoder_device": "default",
        }

    def test_discover_exact_filename_and_roundtrip(self):
        inventory = {"UNETLoader": [FILENAME, core.H3_MODELS["w4a8"],
                                    "ref2va_fl2va.safetensors", "s3_raw_w4a8.safetensors",
                                    "s3_ref2va.gguf", "../ref2va.safetensors"]}
        self.assertEqual(core.installed_model_choices(inventory)["h3"], ("w4a8", "s3_raw", MODEL))
        self.assertEqual(core.h3_model_from_label(core.h3_model_label(MODEL)), MODEL)
        for value in ("ref2va:../s3_ref2va.safetensors", "ref2va:s3_raw_w4a8.safetensors",
                      "ref2va:C:\\ref2va.safetensors", "ref2va:s3_ref2va.gguf"):
            with self.subTest(value=value), self.assertRaises(core.OrchestratorError):
                core.split_h3_options({"h3_model": value}, enabled=True)

    def test_ref_node_keeps_shared_bindings_and_clipproj(self):
        graph = core.prepare_h3_workflow(self.graph, self.options)
        self.assertEqual(graph["6"]["inputs"]["unet_name"], FILENAME)
        self.assertEqual(graph["104"]["class_type"], "MiniMaxH3ReferenceToVideo")
        inputs = graph["104"]["inputs"]
        self.assertNotIn("first_frame", inputs)
        self.assertEqual(inputs["ref_images.ref_image_0"], ["114", 0])
        self.assertEqual(inputs["ref_image_size"], "match")
        self.assertEqual(inputs["audio_vae"], ["24", 0])
        self.assertEqual(inputs["clip"], ["901", 0])
        self.assertEqual(graph["13"]["inputs"]["type"], "krea2")
        self.assertEqual(graph["9"]["inputs"]["scheduler"], "beta")
        self.assertEqual(graph["17"]["inputs"]["sampler_name"], "res_multistep")
        self.assertFalse(any(n["class_type"] == "LoraLoaderModelOnly" for n in graph.values()))
        self.assertEqual(self.graph["104"]["class_type"], "MiniMaxH3ImageToVideo")
        self.assertEqual(self.graph["104"]["inputs"]["first_frame"], ["114", 0])

    def test_ref_rejects_fl2va_turbo(self):
        with self.assertRaisesRegex(core.OrchestratorError, "FL2VA"):
            core.prepare_h3_workflow(self.graph, {**self.options, "h3_turbo": "turbo8"})

    def test_blank_reference_prompt_and_saved_replay(self):
        with tempfile.TemporaryDirectory() as folder:
            image = Path(folder) / "reference.png"
            image.write_bytes(b"image")
            with patch.object(lmstudio.LMStudio, "interpret") as llm, patch.object(core, "ComfyUI") as factory:
                comfy = factory.return_value
                comfy.upload_image.return_value = "ref.png"
                comfy.submit.return_value = "id"
                comfy.wait.return_value = {"outputs": {}}
                result = core.execute(self.config, CONFIG, "", image=image,
                                      selected_workflow=core.H3_I2V_ID,
                                      overrides={**self.options, "seed": 7, "width": 864, "height": 480})
                llm.assert_not_called()
                comfy.free_if_idle.assert_not_called()
                original = comfy.submit.call_args.args[0]
                self.assertEqual(original["104"]["inputs"]["prompt"], core.H3_REF2VA_DEFAULT_PROMPT)
                self.assertEqual(original["104"]["inputs"]["width"], 864)
                self.assertEqual(original["104"]["inputs"]["height"], 480)
                self.assertEqual(original["114"]["inputs"]["image"], "ref.png")
                self.assertEqual(result["parameters"]["h3_model"], MODEL)
                core.execute_saved(self.config, CONFIG, core.H3_I2V_ID,
                                   result["parameters"], reference_image=image)
                self.assertEqual(comfy.submit.call_args.args[0], original)

    def test_ref_prompt_policy_and_tag(self):
        prompt = "The character walks through a new scene."
        self.assertEqual(core.ensure_h3_reference_prompt(prompt).count("<Picture 1>"), 1)
        tagged = "The character in <Picture 1> walks."
        self.assertEqual(core.ensure_h3_reference_prompt(tagged), tagged)
        policy = apply_h3_profile("base", {core.H3_I2V_ID: self.entry},
                                  DEFAULT_H3_PROFILE, reference_only=True)
        self.assertIn("not an initial frame", policy)
        self.assertNotIn("Start from the actual first frame", policy)
        with tempfile.TemporaryDirectory() as folder:
            image = Path(folder) / "reference.png"
            image.write_bytes(b"image")
            with patch.object(lmstudio, "LMStudio") as factory:
                factory.return_value.interpret.return_value = {
                    "workflow_id": core.H3_I2V_ID,
                    "parameters": {"positive_prompt": prompt},
                }
                result = core.execute(self.config, CONFIG, "歩く", image=image, dry_run=True,
                                      selected_workflow=core.H3_I2V_ID, overrides=self.options)
                self.assertTrue(factory.call_args.args[0]["_h3_reference_only"])
                self.assertIsNone(factory.return_value.interpret.call_args.args[2])
                self.assertIn("<Picture 1>", result["parameters"]["positive_prompt"])

    def test_gui_selection_is_reference_only_and_does_not_change_encoder(self):
        var = lambda value: SimpleNamespace(get=lambda: value)
        app = SimpleNamespace(h3_model=var(core.h3_model_label(MODEL)), h3_turbo=var("8 Steps"),
                              h3_encoder_model=var("4B ClipProj (INT8)"), h3_encoder_cpu=var(False))
        self.assertEqual(gui.Application._h3_choices(app), self.options)

    def test_missing_reference_node_fails_preflight(self):
        graph = core.prepare_h3_workflow(self.graph, self.options)
        fields = {"UNETLoader": "unet_name", "CLIPLoader": "clip_name",
                  "VAELoader": "vae_name", "ClipProjApply": "projection"}
        def info(base, route, **kwargs):
            kind = route.rsplit("/", 1)[-1]
            if kind == "MiniMaxH3ReferenceToVideo":
                return {}
            if kind not in fields:
                return {kind: {}}
            field = fields[kind]
            return {kind: {"input": {"required": {field: [[n["inputs"][field] for n in graph.values() if n["class_type"] == kind]]}}}}
        with patch.object(core, "http_json", side_effect=info):
            with self.assertRaisesRegex(core.OrchestratorError, "MiniMaxH3ReferenceToVideo"):
                core.ComfyUI(self.config["comfyui"]).ensure_video_dependencies(graph)


if __name__ == "__main__":
    unittest.main()
