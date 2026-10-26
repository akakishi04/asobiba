"""Offline integration coverage for the uploaded wai I2I API workflow."""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from comfy_orchestrator import core, gui, lmstudio


ROOT = Path(__file__).resolve().parents[1]


class RegisteredI2ITests(unittest.TestCase):
    def setUp(self):
        self.config = core.load_config(ROOT / "config.example.json")
        self.workflows = self.config["workflows"]
        self.entry = self.workflows["wai_i2i_basic"]

    def test_packaged_graph_uses_uploaded_image_and_i2i_denoise(self):
        self.assertEqual(self.entry["kind"], "i2i")
        bindings = self.entry["bindings"]
        template = core.load_workflow(ROOT / self.entry["file"], bindings)
        self.assertEqual(len(template), 8)
        self.assertEqual(template["2"]["inputs"]["ckpt_name"], "waiIllustriousSDXL_v170.safetensors")
        self.assertEqual(template["16"]["class_type"], "LoadImage")
        self.assertEqual(template["17"]["inputs"]["pixels"], ["16", 0])
        self.assertEqual(template["11"]["inputs"]["latent_image"], ["17", 0])
        self.assertEqual(template["11"]["inputs"]["denoise"], 0.53)
        self.assertEqual(bindings["image"], {"node": "16", "input": "image"})
        self.assertEqual(bindings["denoise"], {"node": "11", "input": "denoise"})
        self.assertNotIn("width", bindings)
        self.assertNotIn("height", bindings)

        params = {
            "positive_prompt": "1girl, brown hair, portrait",
            "negative_prompt": "blurry",
            "steps": 20, "cfg": 5.0,
            "seed": 42, "denoise": 0.65,
        }
        output = core.render_workflow(template, bindings, params, "uploaded_reference.png")
        self.assertEqual(output["16"]["inputs"]["image"], "uploaded_reference.png")
        self.assertEqual(output["11"]["inputs"]["denoise"], 0.65)
        self.assertEqual(output["8"]["inputs"]["text"], params["positive_prompt"])
        self.assertEqual(output["5"]["inputs"]["text"], "blurry")
        self.assertEqual(output["17"]["inputs"]["pixels"], ["16", 0])
        self.assertEqual(output["13"]["inputs"]["images"], ["12", 0])
        self.assertEqual(template["16"]["inputs"]["image"], "イラスト5.png")

    def test_auto_routing_filters_workflows_before_the_llm(self):
        seen = []
        self.config["llm"]["model"] = "test-model"

        class FakeLM:
            def __init__(self, settings):
                pass

            def interpret(self, request, workflows, image, progress=None):
                seen.append((tuple(workflows), image))
                key = next(iter(workflows))
                return {
                    "workflow_id": key,
                    "parameters": {"positive_prompt": "anime portrait"},
                }

        with patch.object(lmstudio, "LMStudio", FakeLM):
            out = core.execute(
                self.config, ROOT / "config.example.json", "アニメ調の顔",
                dry_run=True, overrides={"width": 768, "height": 768},
            )
            self.assertEqual(out["workflow_id"], "wai_t2i_basic")
            with tempfile.TemporaryDirectory() as folder:
                image = Path(folder) / "reference.png"
                image.write_bytes(b"example")
                out = core.execute(
                    self.config, ROOT / "config.example.json", "髪の色を茶色にして",
                    image=image, dry_run=True, overrides={"denoise": 0.53},
                )
                self.assertEqual(out["workflow_id"], "wai_i2i_basic")
        self.assertEqual(seen[0][0], ("wai_t2i_basic",))
        self.assertEqual(seen[1][0], ("wai_i2i_basic",))

    def test_wrong_image_mode_is_rejected_before_model_load(self):
        with tempfile.TemporaryDirectory() as folder:
            image = Path(folder) / "reference.png"
            image.write_bytes(b"example")
            with self.assertRaisesRegex(core.OrchestratorError, "参照画像"):
                core.execute(
                    self.config, ROOT / "config.example.json", "test", image=image,
                    selected_workflow="wai_t2i_basic", dry_run=True
                )
            with self.assertRaisesRegex(core.OrchestratorError, "参照画像"):
                core.execute(
                    self.config, ROOT / "config.example.json", "test",
                    selected_workflow="wai_i2i_basic", dry_run=True
                )

    def test_gui_prepares_only_supported_i2i_parameters(self):
        base = {"width": 768, "height": 768, "steps": 20, "cfg": 5.0, "seed": 999}
        selected = gui.resolve_generation_workflow(self.config, "自動", True)
        self.assertEqual(selected, "wai_i2i_basic")
        overrides = gui.image_aware_overrides(self.config, selected, True, base, "0.53")
        self.assertEqual(
            overrides,
            {"steps": 20, "cfg": 5.0, "seed": 999, "denoise": 0.53},
        )
        self.assertEqual(gui.resolve_generation_workflow(self.config, "自動", False), "wai_t2i_basic")
        t2i = gui.image_aware_overrides(
            self.config, "wai_t2i_basic", False, base, "not-a-number"
        )
        self.assertEqual(t2i, base)

    def test_gui_switches_from_t2i_to_i2i_on_image_selection(self):
        class Value:
            def __init__(self, value):
                self.value = value

            def get(self):
                return self.value

            def set(self, value):
                self.value = value

        class FakeGui:
            def __init__(self, config):
                self.config = config
                self.workflow = Value("wai_t2i_basic")
                self.reference_image = Value("")
                self.refreshed = 0

            def _update_generation_controls(self):
                self.refreshed += 1

        fake = FakeGui(self.config)
        fake.reference_image.set("C:/images/portrait.png")
        gui.Application._on_reference_image_changed(fake)
        self.assertEqual(fake.workflow.get(), "wai_i2i_basic")
        fake.reference_image.set("")
        gui.Application._on_reference_image_changed(fake)
        self.assertEqual(fake.workflow.get(), "wai_t2i_basic")
        self.assertEqual(fake.refreshed, 2)

    def test_gui_bad_i2i_denoise_is_rejected(self):
        with self.assertRaises(ValueError):
            gui.image_aware_overrides(self.config, "wai_i2i_basic", True, {}, "abc")
        with self.assertRaisesRegex(core.OrchestratorError, "denoise の範囲"):
            gui.image_aware_overrides(self.config, "wai_i2i_basic", True, {}, "2.0")

    def test_lm_studio_can_interpret_i2i_without_image_vision(self):
        settings = dict(self.config["llm"], model="test-model")
        self.assertFalse(settings["send_reference_to_llm"])
        plan = {"workflow_id": "wai_i2i_basic", "parameters": {"positive_prompt": "1girl"}}
        requests = []

        def fake_request(settings, route, payload=None):
            requests.append((route, payload))
            if route == "/v1/chat/completions":
                return {"choices": [{"message": {"content": json.dumps(plan)}}]}
            if route == "/api/v1/models/unload":
                return {"instance_id": "test-instance"}
            raise AssertionError(route)

        with tempfile.TemporaryDirectory() as folder:
            image = Path(folder) / "ref.png"
            image.write_bytes(b"image data")
            with patch.object(lmstudio.LMStudio, "_ensure_loaded", return_value="test-instance"):
                with patch.object(lmstudio, "_request", side_effect=fake_request):
                    actual = lmstudio.LMStudio(settings).interpret(
                        "髪を茶色に", {"wai_i2i_basic": self.entry}, image,
                    )
            self.assertEqual(actual, plan)
        message = requests[0][1]["messages"][1]["content"]
        self.assertIsInstance(message, str)
        self.assertIn("Reference image routed to ComfyUI: yes", message)
        self.assertIn("Reference image visible to the LLM: no", message)
        self.assertEqual(requests[-1][0], "/api/v1/models/unload")


if __name__ == "__main__":
    unittest.main()
