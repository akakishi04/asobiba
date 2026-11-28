"""Reasoning-off routing for still-image planning without changing video policy."""
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from comfy_orchestrator import core, lmstudio
from comfy_orchestrator.image_prompts import ALT
from comfy_orchestrator.model_profiles import ANIMA_ID

CONFIG = Path(__file__).resolve().parents[1] / "config.example.json"


class ImageReasoningTests(unittest.TestCase):
    def setUp(self):
        self.config = core.load_config(CONFIG)
        self.settings = {**self.config["llm"], "model": "test-model"}

    def run_plan(self, workflow, options, *, native_reply=None, timeout=False):
        answer = {"workflow_id": workflow,
                  "parameters": {"positive_prompt": "1girl, sitting", "negative_prompt": "blurry"}}
        if workflow == ANIMA_ID:
            answer[ALT] = {"positive_prompt": "A woman sits by a window.", "negative_prompt": "Avoid blur."}
        requests = []
        notes = []
        catalog = {"models": [{"type": "llm", "key": self.settings["model"],
                                "capabilities": {"reasoning": {"allowed_options": options}},
                                "loaded_instances": [{"id": "instance"}]}]}

        def fake(settings, route, payload=None):
            requests.append((route, payload))
            if route == "/api/v1/models":
                return catalog
            if route == "/api/v1/models/unload":
                return {"instance_id": "instance"}
            if timeout:
                raise core.OrchestratorError("LM Studioの自然文解釈で通信タイムアウトしました")
            if route == "/api/v1/chat":
                return native_reply if native_reply is not None else {
                    "output": [{"type": "message", "content": json.dumps(answer)}]}
            if route == "/v1/chat/completions":
                return {"choices": [{"message": {"content": json.dumps(answer)}}]}
            raise AssertionError(route)

        with patch.object(lmstudio, "_request", side_effect=fake):
            if timeout or native_reply is not None:
                with self.assertRaises(core.OrchestratorError):
                    lmstudio.LMStudio(self.settings).interpret(
                        "窓際に座る", {workflow: self.config["workflows"][workflow]},
                        None, progress=notes.append)
            else:
                result = lmstudio.LMStudio(self.settings).interpret(
                    "窓際に座る", {workflow: self.config["workflows"][workflow]},
                    None, progress=notes.append)
                self.assertEqual(result, answer)
        return requests, notes

    def test_supported_model_uses_native_reasoning_off(self):
        calls, notes = self.run_plan(ANIMA_ID, ["off", "on"])
        self.assertEqual([r for r, _ in calls], ["/api/v1/models", "/api/v1/chat", "/api/v1/models/unload"])
        payload = calls[1][1]
        self.assertEqual(payload["reasoning"], "off")
        self.assertFalse(payload["store"])
        self.assertEqual(payload["max_output_tokens"], self.settings["max_tokens"])
        self.assertNotIn("response_format", payload)
        self.assertIn("Required JSON schema", payload["system_prompt"])
        self.assertIn("alternate_prompt", payload["system_prompt"])
        self.assertTrue(any("思考OFF" in note for note in notes))

    def test_unsupported_model_keeps_structured_output(self):
        calls, notes = self.run_plan(ANIMA_ID, ["on"])
        self.assertEqual(calls[1][0], "/v1/chat/completions")
        self.assertIn("response_format", calls[1][1])

    def test_video_keeps_existing_inference_route(self):
        calls, _ = self.run_plan(core.WAN_I2V_ID, ["off", "on"])
        self.assertEqual(calls[1][0], "/v1/chat/completions")

    def test_timeout_does_not_retry_and_unloads_model(self):
        calls, _ = self.run_plan(ANIMA_ID, ["off", "on"], timeout=True)
        self.assertEqual([r for r, _ in calls], ["/api/v1/models", "/api/v1/chat", "/api/v1/models/unload"])

    def test_empty_final_answer_never_uses_reasoning_as_prompt(self):
        calls, _ = self.run_plan(ANIMA_ID, ["off", "on"], native_reply={
            "output": [{"type": "reasoning", "content": '{"workflow_id":"anima_t2i_basic"}'}]})
        self.assertEqual([r for r, _ in calls], ["/api/v1/models", "/api/v1/chat", "/api/v1/models/unload"])


if __name__ == "__main__":
    unittest.main()
