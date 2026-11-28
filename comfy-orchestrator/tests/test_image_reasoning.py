"""Reasoning-off routing for still-image planning without changing video policy."""
import json
import tempfile
import unittest
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

from comfy_orchestrator import core, lmstudio
from comfy_orchestrator.prompt_inference import request_validated, image_reasoning_option
from comfy_orchestrator.prompt_cache import make_cache_key
from comfy_orchestrator.app_config import load_local_config
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
        self.assertNotIn("max_output_tokens", payload)
        self.assertNotIn("response_format", payload)
        self.assertIn("Required JSON schema", payload["system_prompt"])
        self.assertIn("alternate_prompt", payload["system_prompt"])
        self.assertTrue(any("思考OFF" in note for note in notes))

    def test_unsupported_model_keeps_structured_output(self):
        calls, notes = self.run_plan(ANIMA_ID, ["on"])
        self.assertEqual(calls[1][0], "/v1/chat/completions")
        self.assertIn("response_format", calls[1][1])
        self.assertNotIn("max_tokens", calls[1][1])

    def test_on_uses_advertised_reasoning(self):
        self.settings["image_reasoning"] = "on"
        for options, expected in ((["off", "on"], "on"), (["low", "medium", "high"], "medium")):
            with self.subTest(options=options):
                calls, notes = self.run_plan(ANIMA_ID, options)
                self.assertEqual(calls[1][0], "/api/v1/chat")
                self.assertEqual(calls[1][1]["reasoning"], expected)
                self.assertTrue(any("思考ON" in line for line in notes))

    def test_auto_or_unsupported_on_keeps_structured_output(self):
        for preference, options in (("auto", ["off", "on"]), ("on", ["off"])):
            self.settings["image_reasoning"] = preference
            calls, notes = self.run_plan(ANIMA_ID, options)
            self.assertEqual(calls[1][0], "/v1/chat/completions")
            self.assertIn("response_format", calls[1][1])
            self.assertTrue(any("モデル既定" in line for line in notes))

    def test_outfit_fidelity_is_included_in_paired_prompt_policy(self):
        calls, _ = self.run_plan(ANIMA_ID, ["off", "on"])
        system = calls[1][1]["system_prompt"]
        for value in ("APPEARANCE AND COSTUME FIDELITY", "layers and their order",
                      "accessory location", "BOTH standalone positive prompts",
                      "pose/composition-only references"):
            self.assertIn(value, system)

    def test_reasoning_keeps_explicit_setting_on_validation_retry(self):
        client = SimpleNamespace(settings={**self.settings, "image_reasoning": "on"},
                                 _reasoning_options=("off", "on"))
        schema = {"type": "object", "properties": {"answer": {"type": "string"}},
                  "required": ["answer"], "additionalProperties": False}
        bad = {"output": [{"type": "message", "content": "not JSON"}],
               "stats": {"reasoning_output_tokens": 28}}
        good = {"output": [{"type": "message", "content": '{"answer":"ok"}'}]}
        with patch.object(lmstudio, "_request", side_effect=[bad, good]) as send:
            result = request_validated(client, "instance", "system", "input", schema,
                                       "image_prompt_patch", lambda reply: reply, direct_answer=True)
        self.assertEqual(result, {"answer": "ok"})
        self.assertEqual([c.args[2]["reasoning"] for c in send.call_args_list], ["on", "on"])

    def test_translation_keeps_reasoning_off_even_when_image_reasoning_on(self):
        client = SimpleNamespace(settings={**self.settings, "image_reasoning": "on"},
                                 _reasoning_options=("off", "on"))
        reply = {"output": [{"type": "message", "content": '{"text":"ok"}'}]}
        with patch.object(lmstudio, "_request", return_value=reply) as send:
            request_validated(client, "instance", "translate", "input",
                              {"type": "object"}, "translation", lambda value: value,
                              translation_chars=5)
        self.assertEqual(send.call_args.args[2]["reasoning"], "off")
        self.assertNotIn("max_output_tokens", send.call_args.args[2])

    def test_model_default_effort_is_used_when_on_is_not_an_option(self):
        client = SimpleNamespace(settings={**self.settings, "image_reasoning": "on"},
                                 _reasoning_options=("low", "medium", "high"),
                                 _reasoning_default="low")
        self.assertEqual(image_reasoning_option(client), "low")

    def test_preference_persists_and_separates_prompt_cache(self):
        workflows = {ANIMA_ID: self.config["workflows"][ANIMA_ID]}
        args = ("request",)
        off = make_cache_key(*args, {**self.settings, "image_reasoning": "off"}, workflows, {}, {}, None)
        on = make_cache_key(*args, {**self.settings, "image_reasoning": "on"}, workflows, {}, {}, None)
        self.assertNotEqual(off, on)
        with tempfile.TemporaryDirectory() as folder:
            # Config validation resolves relative graphs; use the original
            # example as the migration source and check the local saved data.
            target = Path(folder) / "config.json"
            old = dict(self.config)
            old["llm"] = {k: v for k, v in self.settings.items() if k != "image_reasoning"}
            target.write_text(json.dumps(old), encoding="utf-8")
            migrated = load_local_config(target, CONFIG)
            self.assertEqual(migrated["llm"]["image_reasoning"], "off")
            migrated["llm"]["image_reasoning"] = "on"
            target.write_text(json.dumps(migrated), encoding="utf-8")
            self.assertEqual(load_local_config(target, CONFIG)["llm"]["image_reasoning"], "on")

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
