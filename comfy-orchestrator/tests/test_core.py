"""Offline tests for mapping, validation, and the unload-before-submit barrier."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from comfy_orchestrator import core


TEMPLATE = {
    "6": {"class_type": "CLIPTextEncode", "inputs": {"text": "old"}},
    "7": {"class_type": "LoadImage", "inputs": {"image": "old.png"}},
    "3": {"class_type": "KSampler", "inputs": {"steps": 20}},
}


class ConfigFixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "flow.json").write_text(json.dumps(TEMPLATE), encoding="utf-8")
        self.entry = {
            "kind": "i2i", "description": "test", "file": "flow.json",
            "bindings": {
                "positive_prompt": {"node": "6", "input": "text"},
                "image": {"node": "7", "input": "image"},
                "steps": {"node": "3", "input": "steps"},
            }, "defaults": {"steps": 25},
        }
        self.config = {
            "ollama": {"base_url": "http://127.0.0.1:11434", "model": "test:model"},
            "comfyui": {"base_url": "http://127.0.0.1:8188", "free_before_llm": True},
            "workflows": {"i2i": self.entry},
        }
        self.config_path = self.root / "config.json"
        self.save()

    def save(self):
        self.config_path.write_text(json.dumps(self.config), encoding="utf-8")

    def test_valid_config_and_api_workflow(self):
        self.assertEqual(core.load_config(self.config_path)["workflows"]["i2i"]["kind"], "i2i")

    def test_example_config_can_have_no_workflows(self):
        self.config["workflows"] = {}
        self.save()
        self.assertEqual(core.load_config(self.config_path)["workflows"], {})
        with self.assertRaisesRegex(core.OrchestratorError, "workflowsが空"):
            core.execute(self.config, self.config_path, "hi")

    def test_missing_node_is_rejected(self):
        self.entry["bindings"]["steps"]["node"] = "100"
        self.save()
        with self.assertRaisesRegex(core.OrchestratorError, "指定先が存在しません"):
            core.load_config(self.config_path)

    def test_non_api_json_is_rejected(self):
        (self.root / "flow.json").write_text(json.dumps({"nodes": []}), encoding="utf-8")
        with self.assertRaisesRegex(core.OrchestratorError, "API形式"):
            core.load_config(self.config_path)

    def test_bad_defaults_and_escaping_paths_are_rejected(self):
        self.entry["defaults"]["steps"] = 0
        self.save()
        with self.assertRaises(core.OrchestratorError):
            core.load_config(self.config_path)
        self.entry["defaults"]["steps"] = 10
        self.entry["file"] = "../outside.json"
        self.save()
        with self.assertRaisesRegex(core.OrchestratorError, "フォルダ内"):
            core.load_config(self.config_path)

    def test_plan_allowlist_and_image_required(self):
        plan = {"workflow_id": "i2i", "parameters": {"positive_prompt": "cute", "steps": 32}}
        with self.assertRaisesRegex(core.OrchestratorError, "--image"):
            core.validate_plan(plan, self.config["workflows"], False)
        selected, params = core.validate_plan(plan, self.config["workflows"], True)
        self.assertEqual((selected, params["steps"]), ("i2i", 32))
        with self.assertRaisesRegex(core.OrchestratorError, "変更できません"):
            core.validate_plan({"workflow_id": "i2i", "parameters": {"positive_prompt": "x", "cfg": 40}}, self.config["workflows"], True)
        with self.assertRaisesRegex(core.OrchestratorError, "未登録"):
            core.validate_plan({"workflow_id": "unknown", "parameters": {}}, self.config["workflows"], True)

    def test_render_does_not_mutate_template(self):
        out = core.render_workflow(TEMPLATE, self.entry["bindings"], {"positive_prompt": "new", "steps": 30}, "in.png")
        self.assertEqual(out["6"]["inputs"]["text"], "new")
        self.assertEqual(out["3"]["inputs"]["steps"], 30)
        self.assertEqual(out["7"]["inputs"]["image"], "in.png")
        self.assertEqual(TEMPLATE["6"]["inputs"]["text"], "old")

    def test_unload_precedes_prompt_and_failure_blocks_submission(self):
        calls = []
        image = self.root / "person.png"
        image.write_bytes(b"fake png")
        plan = {"workflow_id": "i2i", "parameters": {"positive_prompt": "anime portrait"}}

        def fake_http(base, route, payload=None, timeout=60, allow_empty=False):
            calls.append(route)
            if route == "/queue":
                return {"queue_running": [], "queue_pending": []}
            if route == "/free":
                return {}
            if route == "/api/generate" and payload.get("prompt"):
                return {"response": json.dumps(plan)}
            if route == "/api/generate":
                return {"done": True, "done_reason": "unload"}
            if route == "/prompt":
                return {"prompt_id": "fake-id"}
            if route == "/history/fake-id":
                return {"fake-id": {"outputs": {"6": {"images": [{"filename": "out.png"}]}}, "status": {"completed": True}}}
            raise AssertionError(route)

        with patch.object(core, "http_json", side_effect=fake_http), patch.object(core.ComfyUI, "upload_image", return_value="person.png"):
            result = core.execute(core.load_config(self.config_path), self.config_path, "picture", image)
        self.assertEqual(result["prompt_id"], "fake-id")
        self.assertEqual(calls, ["/queue", "/free", "/api/generate", "/api/generate", "/prompt", "/history/fake-id"])

        calls.clear()

        def failed_unload(base, route, payload=None, timeout=60, allow_empty=False):
            calls.append(route)
            if route == "/queue":
                return {"queue_running": [], "queue_pending": []}
            if route == "/free":
                return {}
            if route == "/api/generate" and payload.get("prompt"):
                return {"response": json.dumps(plan)}
            raise core.OrchestratorError("unload failed")

        with patch.object(core, "http_json", side_effect=failed_unload):
            with self.assertRaisesRegex(core.OrchestratorError, "unload failed"):
                core.execute(core.load_config(self.config_path), self.config_path, "picture", image)
        self.assertNotIn("/prompt", calls)

    def test_busy_queue_does_not_unload_or_invoke_llm(self):
        with patch.object(core, "http_json", return_value={"queue_running": [[1]], "queue_pending": []}) as api:
            with self.assertRaisesRegex(core.OrchestratorError, "他の実行"):
                core.execute(core.load_config(self.config_path), self.config_path, "picture")
        self.assertEqual(api.call_count, 1)

    def test_dry_run_never_contacts_comfyui(self):
        self.entry["bindings"].pop("image")
        self.save()
        calls = []
        plan = {"workflow_id": "i2i", "parameters": {"positive_prompt": "x"}}
        def fake_http(base, route, payload=None, timeout=60, allow_empty=False):
            calls.append(route)
            return {"response": json.dumps(plan)} if payload.get("prompt") else {"done": True}
        with patch.object(core, "http_json", side_effect=fake_http):
            result = core.execute(core.load_config(self.config_path), self.config_path, "picture", dry_run=True)
        self.assertEqual(result["status"], "dry_run")
        self.assertEqual(calls, ["/api/generate", "/api/generate"])


if __name__ == "__main__":
    unittest.main()
