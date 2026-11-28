"""Manual registration, exact replay identity and H3 conditioning contracts."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from comfy_orchestrator import core, h3
from comfy_orchestrator.model_registry import (
    registration, image_key, h3_key, parse_h3_key, parse_image_key, model_filename,
    load_registrations, save_registrations, installed_registrations, validate_registrations,
)
from comfy_orchestrator.model_profiles import image_model_choices, selected_label, defaults_for, ANIMA_ID
from comfy_orchestrator.h3_model_picker import model_choices
from comfy_orchestrator.long_video_plan import continuation_model

CONFIG = Path(__file__).resolve().parents[1] / "config.example.json"


class ManualModelRegistryTests(unittest.TestCase):
    def setUp(self):
        self.config = core.load_config(CONFIG)
        self.h3_entry = self.config["workflows"][core.H3_I2V_ID]
        self.graph = core.load_workflow(CONFIG.parent / self.h3_entry["file"], self.h3_entry["bindings"])

    def test_persist_and_reject_invalid_entries(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "models.json"
            self.assertEqual(load_registrations(path), ())
            items = (registration("anima", "folder/Custom.safetensors", 25, 3.0),
                     registration("h3_euler_hybrid", "TriPRISM.safetensors", 8))
            self.assertEqual(save_registrations(path, items), items)
            self.assertEqual(load_registrations(path), items)
            for args in (("anima", "../bad.safetensors"), ("h3_fl2va", "C:/bad.safetensors"),
                         ("h3_euler_hybrid", "a.safetensors", 7),
                         ("h3_ref2va", "a.safetensors", 20, 4)):
                with self.assertRaises(core.OrchestratorError):
                    registration(*args)
            with self.assertRaises(core.OrchestratorError):
                validate_registrations((items[0], items[0]))
            path.write_text("broken", encoding="utf-8")
            with self.assertRaises(core.OrchestratorError):
                load_registrations(path)
            self.assertEqual(path.read_text(encoding="utf-8"), "broken")

    def test_model_discovery_and_picker(self):
        a = registration("anima", "custom.safetensors", 25, 3.25)
        s = registration("sdxl", "unknown.safetensors")
        q = registration("qwen", "QwenCustom.safetensors", 32, 4)
        regs = (a, s, q)
        inv = {"UNETLoader": [a.filename, q.filename], "CheckpointLoaderSimple": [s.filename]}
        result = core.installed_model_choices(inv, regs)
        self.assertEqual(result["anima"], a.keys)
        self.assertEqual(result["sdxl"], s.keys)
        self.assertEqual(result["qwen"], q.keys)
        self.assertEqual(core.installed_model_choices({}, regs)["anima"], ())
        picker = image_model_choices(self.config["workflows"], inv, result["sdxl"],
                                     core.DEFAULT_SDXL_CHECKPOINT, a.keys[0], regs, q.keys[0])
        choice = next(c for c in picker if c.filename == a.keys[0])
        self.assertEqual(defaults_for(self.config["workflows"], choice, registrations=regs)["steps"], 25)
        self.assertEqual(defaults_for(self.config["workflows"], choice, registrations=regs)["cfg"], 3.25)
        self.assertEqual(selected_label(picker, core.QWEN_T2I_ID, "", "", q.keys[0]),
                         next(c.label for c in picker if c.filename == q.keys[0]))

    def test_image_keys_replay_without_registry(self):
        cases = (("sdxl", "wai_t2i_basic", "2", "ckpt_name"),
                 ("anima", ANIMA_ID, "2", "unet_name"),
                 ("qwen", core.QWEN_T2I_ID, "226", "unet_name"))
        for profile, workflow, node, field in cases:
            key = image_key(profile, "folder/custom.safetensors")
            params = {**self.config["workflows"][workflow]["defaults"], "positive_prompt": "tree",
                      "seed": 7, "checkpoint_model": key}
            with patch.object(core, "ComfyUI") as factory:
                comfy = factory.return_value
                comfy.submit.return_value = "id"
                comfy.wait.return_value = {"outputs": {}}
                result = core.execute_saved(self.config, CONFIG, workflow, params)
                self.assertEqual(comfy.submit.call_args.args[0][node]["inputs"][field], "folder/custom.safetensors")
                self.assertEqual(result["parameters"], params)
            self.assertEqual(parse_image_key(key), (profile, "folder/custom.safetensors"))
        with self.assertRaises(core.OrchestratorError):
            core.split_checkpoint_option({"checkpoint_model": image_key("anima", "a.safetensors")},
                                         {"wai_t2i_basic"})

    def test_h3_registered_turbo_fixed_and_vae_unchanged(self):
        reg = registration("h3_euler_hybrid", "TriPRISM.safetensors", 8)
        installed = core.installed_model_choices({"UNETLoader": [reg.filename]}, (reg,))["h3"]
        opening, reference = reg.keys
        self.assertEqual(set(installed), set(reg.keys))
        picker = model_choices(installed, reference)
        self.assertEqual(len(picker), 1)
        self.assertEqual(picker[0].opening, opening)
        self.assertEqual(picker[0].reference, reference)
        for mode in (opening, reference):
            self.assertEqual(h3.h3_model_from_label(h3.h3_model_label(mode)), mode)
            _, opts = h3.split_h3_options({"h3_model": mode, "h3_turbo": "off"}, enabled=True)
            self.assertEqual(opts["h3_performance"], "euler_dense")
            graph = h3.prepare_h3_workflow(self.graph, opts, {"steps": 8})
            self.assertEqual(graph["6"]["inputs"]["unet_name"], reg.filename)
            self.assertEqual(graph["17"]["inputs"]["sampler_name"], "euler")
            self.assertEqual(graph["9"]["inputs"]["scheduler"], "simple")
            self.assertEqual(graph["11"], self.graph["11"])
            self.assertEqual(graph["10"], self.graph["10"])
            self.assertEqual(graph["24"], self.graph["24"])
            shift = next(node for node in graph.values() if node["class_type"] == "MiniMaxH3SigmaShift")
            self.assertEqual((shift["inputs"]["shift_video"], shift["inputs"]["shift_audio"]), (12, 3))
            self.assertEqual(graph["104"]["class_type"], "MiniMaxH3ReferenceToVideo" if mode == reference else "MiniMaxH3ImageToVideo")
            self.assertEqual(continuation_model(mode), opening)
            with self.assertRaises(core.OrchestratorError):
                h3.split_h3_options({"h3_model": mode, "h3_turbo": "turbo8"}, enabled=True)
            with self.assertRaises(core.OrchestratorError):
                h3.prepare_h3_workflow(self.graph, opts, {"steps": 7})
        self.assertEqual(h3.h3_text_model_options({"h3_model": reference})["h3_model"], opening)

    def test_h3_reference_only_cannot_be_used_for_continuation(self):
        model = h3_key("h3_euler_ref2va", "reference", "custom.safetensors")
        self.assertIsNone(h3_key("h3_euler_ref2va", "opening", "custom.safetensors"))
        self.assertEqual(parse_h3_key(model), ("h3_euler_ref2va", "reference", "custom.safetensors"))
        with self.assertRaises(core.OrchestratorError):
            continuation_model(model)
        with self.assertRaises(core.OrchestratorError):
            h3.h3_text_model_options({"h3_model": model})
        regular = h3_key("h3_fl2va", "opening", "base.safetensors")
        graph = h3.prepare_h3_workflow(self.graph, {"h3_model": regular, "h3_turbo": "off"}, {"steps": 20})
        self.assertEqual(graph["6"]["inputs"]["unet_name"], "base.safetensors")
        self.assertEqual(graph["17"], self.graph["17"])


if __name__ == "__main__":
    unittest.main()
