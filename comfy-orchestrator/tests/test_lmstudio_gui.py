"""Offline tests for LM Studio lifecycle, GUI data, and packaged workflow."""

from __future__ import annotations

import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from comfy_orchestrator import core, gui, lmstudio


ROOT = Path(__file__).resolve().parents[1]
MODEL = "local/test-llm"
INSTANCE = "local/test-llm:session"


class LMStudioTests(unittest.TestCase):
    def setUp(self):
        self.settings = {
            "provider": "lmstudio",
            "base_url": "http://127.0.0.1:1234",
            "model": MODEL,
            "unload_after_inference": True,
            "context_length": 4096,
        }
        self.workflows = {
            "wai": {
                "kind": "t2i", "description": "anime SDXL",
                "bindings": {"positive_prompt": {"node": "8", "input": "text"}},
            }
        }
        self.plan = {"workflow_id": "wai", "parameters": {"positive_prompt": "anime, girl"}}

    def test_model_list_load_infer_and_unload_order(self):
        calls = []

        def fake_request(settings, route, payload=None):
            calls.append((route, payload))
            if route == "/api/v1/models":
                return {"models": [{"type": "llm", "key": MODEL, "loaded_instances": []}]}
            if route == "/api/v1/models/load":
                self.assertEqual(payload["model"], MODEL)
                self.assertEqual(payload["context_length"], 4096)
                return {"status": "loaded", "instance_id": INSTANCE}
            if route == "/v1/chat/completions":
                self.assertEqual(payload["model"], INSTANCE)
                self.assertEqual(payload["response_format"]["type"], "json_schema")
                return {"choices": [{"message": {"content": json.dumps(self.plan)}}]}
            if route == "/api/v1/models/unload":
                self.assertEqual(payload, {"instance_id": INSTANCE})
                return {"instance_id": INSTANCE}
            self.fail(route)

        with patch.object(lmstudio, "_request", side_effect=fake_request):
            actual = lmstudio.LMStudio(self.settings).interpret("アニメ絵", self.workflows, None)
        self.assertEqual(actual, self.plan)
        self.assertEqual([r for r, _ in calls], [
            "/api/v1/models", "/api/v1/models/load", "/v1/chat/completions",
            "/api/v1/models/unload",
        ])

    def test_preloaded_instance_is_reused_then_unloaded(self):
        calls = []

        def fake_request(settings, route, payload=None):
            calls.append(route)
            if route == "/api/v1/models":
                return {"models": [{"type": "llm", "key": MODEL,
                                    "loaded_instances": [{"id": INSTANCE}]}]}
            if route == "/v1/chat/completions":
                return {"choices": [{"message": {"content": json.dumps(self.plan)}}]}
            if route == "/api/v1/models/unload":
                return {"instance_id": INSTANCE}
            self.fail(route)

        with patch.object(lmstudio, "_request", side_effect=fake_request):
            lmstudio.LMStudio(self.settings).interpret("アニメ絵", self.workflows, None)
        self.assertNotIn("/api/v1/models/load", calls)
        self.assertEqual(calls[-1], "/api/v1/models/unload")

    def test_unload_failure_blocks_subsequent_generation(self):
        calls = []

        def fake_request(settings, route, payload=None):
            calls.append(route)
            if route == "/api/v1/models":
                return {"models": [{"type": "llm", "key": MODEL,
                                    "loaded_instances": [{"id": INSTANCE}]}]}
            if route == "/v1/chat/completions":
                return {"choices": [{"message": {"content": json.dumps(self.plan)}}]}
            if route == "/api/v1/models/unload":
                return {"instance_id": "wrong-instance"}
            self.fail(route)

        with patch.object(lmstudio, "_request", side_effect=fake_request):
            with self.assertRaisesRegex(core.OrchestratorError, "アンロード"):
                lmstudio.LMStudio(self.settings).interpret("request", self.workflows, None)
        self.assertNotIn("/api/v1/models/load", calls)

    def test_failed_generation_attempts_unload_in_finally(self):
        calls = []

        def fake_request(settings, route, payload=None):
            calls.append(route)
            if route == "/api/v1/models":
                return {"models": [{"type": "llm", "key": MODEL,
                                    "loaded_instances": [{"id": INSTANCE}]}]}
            if route == "/v1/chat/completions":
                raise core.OrchestratorError("mocked LLM failure")
            if route == "/api/v1/models/unload":
                return {"instance_id": INSTANCE}
            self.fail(route)

        with patch.object(lmstudio, "_request", side_effect=fake_request):
            with self.assertRaisesRegex(core.OrchestratorError, "mocked LLM failure"):
                lmstudio.LMStudio(self.settings).interpret("request", self.workflows, None)
        self.assertEqual(calls[-1], "/api/v1/models/unload")


class GUIAndConfigTests(unittest.TestCase):
    def test_packaged_config_and_workflow_are_valid(self):
        c = core.load_config(ROOT / "config.example.json")
        self.assertEqual(c["llm"]["provider"], "lmstudio")
        self.assertIn("wai_t2i_basic", c["workflows"])
        self.assertTrue(c["llm"]["unload_after_inference"])

    def test_gui_filters_image_outputs(self):
        images = gui.output_images({
            "outputs": {
                "13": {"images": [
                    {"filename": "ComfyUI_00001.png", "subfolder": "", "type": "output"},
                    {"filename": "ComfyUI_00002.png"},
                ]},
                "other": {"text": ["not an image"]},
            }
        })
        self.assertEqual(len(images), 2)
        self.assertEqual(images[0]["filename"], "ComfyUI_00001.png")
        self.assertEqual(images[1]["type"], "output")

    def test_gui_bootstrap_migrates_legacy_ollama_settings(self):
        with tempfile.TemporaryDirectory() as name:
            config = Path(name) / "config.json"
            config.write_text(json.dumps({
                "ollama": {"base_url": "http://127.0.0.1:11434", "model": "x"},
                "comfyui": {"base_url": "http://127.0.0.1:8188"},
                "workflows": {},
            }), encoding="utf-8")
            with patch.object(gui, "CONFIG", config):
                result = gui.bootstrap_config()
            self.assertEqual(result["llm"]["provider"], "lmstudio")
            self.assertIn("ollama", result)

    def test_cancellation_before_any_network(self):
        cfg = core.load_config(ROOT / "config.example.json")
        stopped = threading.Event()
        stopped.set()
        with self.assertRaisesRegex(core.OrchestratorError, "中止"):
            core.execute(cfg, ROOT / "config.example.json", "test", cancel_event=stopped)

    def test_selected_workflow_and_gui_overrides_for_dry_run(self):
        cfg = core.load_config(ROOT / "config.example.json")
        cfg["llm"]["model"] = MODEL
        plan = {"workflow_id": "wai_t2i_basic", "parameters": {"positive_prompt": "1girl"}}

        class FakeLM:
            def __init__(self, settings):
                pass

            def interpret(self, text, workflows, image, progress=None):
                self_test.assertEqual(list(workflows), ["wai_t2i_basic"])
                return plan

        self_test = self
        with patch.object(lmstudio, "LMStudio", FakeLM):
            result = core.execute(
                cfg, ROOT / "config.example.json", "test", dry_run=True,
                selected_workflow="wai_t2i_basic",
                overrides={"width": 768, "height": 768, "steps": 20, "cfg": 5.0},
            )
        self.assertEqual(result["status"], "dry_run")
        self.assertEqual(result["parameters"]["width"], 768)
        self.assertEqual(result["parameters"]["steps"], 20)
        self.assertIsInstance(result["parameters"]["seed"], int)


if __name__ == "__main__":
    unittest.main()
