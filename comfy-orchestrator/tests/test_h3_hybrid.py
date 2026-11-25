"""Native H3 hybrid model detection, conditioning, sampling and replay."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from comfy_orchestrator import core, gui, lmstudio

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config.example.json"
FILE = "Eros/10Eros_Max_8stepTurbo_v1.0_hybrid_activation_learned_compact_w4w6int8_14.50gb.safetensors"


class HybridTests(unittest.TestCase):
    def setUp(self):
        self.config = core.load_config(CONFIG)
        entry = self.config["workflows"][core.H3_I2V_ID]
        self.graph = core.load_workflow(ROOT / entry["file"], entry["bindings"])

    def options(self, reference_only):
        return {"h3_model": core.h3_hybrid_model_key(FILE, reference_only=reference_only),
                "h3_turbo": "off", "h3_encoder_model": "clipproj4b",
                "h3_encoder_device": "default"}

    def test_discovery_and_roundtrip(self):
        choices = core.installed_model_choices({"UNETLoader": [FILE, "unknown_hybrid.safetensors", "../" + FILE]})
        self.assertEqual(len(choices["h3"]), 2)
        for reference_only in (False, True):
            key = self.options(reference_only)["h3_model"]
            self.assertIn(key, choices["h3"])
            self.assertEqual(core.h3_hybrid_filename(key), FILE)
            self.assertEqual(core.h3_model_from_label(core.h3_model_label(key)), key)
            self.assertEqual(core.h3_ref2va_filename(key), FILE if reference_only else None)

    def test_both_conditioning_paths_and_sampler(self):
        for reference_only in (False, True):
            with self.subTest(reference_only=reference_only):
                graph = core.prepare_h3_workflow(self.graph, self.options(reference_only), {"steps": 12})
                self.assertEqual(graph["6"]["inputs"]["unet_name"], FILE)
                self.assertEqual(graph["104"]["class_type"], "MiniMaxH3ReferenceToVideo" if reference_only else "MiniMaxH3ImageToVideo")
                self.assertEqual(graph["104"]["inputs"]["clip"], ["901", 0])
                self.assertEqual(graph["9"]["inputs"]["steps"], 12)
                self.assertEqual(graph["9"]["inputs"]["scheduler"], "simple")
                self.assertEqual(graph["17"]["inputs"]["sampler_name"], "lcm")
                self.assertFalse(any(node["class_type"] == "LoraLoaderModelOnly" for node in graph.values()))
                self.assertEqual(graph["104"]["inputs"]["ref_images.ref_image_0" if reference_only else "first_frame"], ["114", 0])
        self.assertEqual(self.graph["17"]["inputs"]["sampler_name"], "res_multistep")

    def test_reject_extra_turbo_and_invalid_steps(self):
        for steps in (4, 20, True):
            with self.assertRaises(core.OrchestratorError):
                core.prepare_h3_workflow(self.graph, self.options(True), {"steps": steps})
        with self.assertRaisesRegex(core.OrchestratorError, "Turbo"):
            core.prepare_h3_workflow(self.graph, {**self.options(True), "h3_turbo": "turbo8"})

    def test_default_steps_and_exact_replay(self):
        with tempfile.TemporaryDirectory() as folder:
            image = Path(folder) / "reference.png"
            image.write_bytes(b"image")
            with patch.object(lmstudio.LMStudio, "interpret") as llm, patch.object(core, "ComfyUI") as factory:
                comfy = factory.return_value
                comfy.upload_image.return_value = "ref.png"
                comfy.submit.return_value = "id"
                comfy.wait.return_value = {"outputs": {}}
                for reference_only in (False, True):
                    result = core.execute(self.config, CONFIG, "", image=image,
                                          selected_workflow=core.H3_I2V_ID,
                                          overrides={**self.options(reference_only), "seed": 7})
                    graph = comfy.submit.call_args.args[0]
                    self.assertEqual(result["parameters"]["steps"], 8)
                    self.assertEqual(graph["9"]["inputs"]["steps"], 8)
                    self.assertEqual("<Picture 1>" in graph["104"]["inputs"]["prompt"], reference_only)
                    core.execute_saved(self.config, CONFIG, core.H3_I2V_ID,
                                       result["parameters"], reference_image=image)
                    self.assertEqual(comfy.submit.call_args.args[0], graph)
                llm.assert_not_called()

    def test_gui_choices_do_not_enable_extra_lora(self):
        var = lambda value: SimpleNamespace(get=lambda: value)
        app = SimpleNamespace(h3_model=var(core.h3_model_label(self.options(True)["h3_model"])),
                              h3_turbo=var("8 Steps"), h3_encoder_model=var("4B ClipProj (INT8)"),
                              h3_encoder_cpu=var(False))
        self.assertEqual(gui.Application._h3_choices(app), self.options(True))


if __name__ == "__main__":
    unittest.main()
