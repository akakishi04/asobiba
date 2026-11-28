"""LM Studio owns context and output budgets, including legacy local settings."""
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from comfy_orchestrator import lmstudio
from comfy_orchestrator.parameters import OrchestratorError
from comfy_orchestrator.prompt_inference import (
    planning_batch_size, request_validated, structured_payload, token_policy_description,
)


SCHEMA = {"type": "object", "properties": {"text": {"type": "string"}},
          "required": ["text"], "additionalProperties": False}


class TokenDelegationTests(unittest.TestCase):
    def test_load_config_does_not_use_model_capacity_or_old_host_limits(self):
        settings = {"model": "test", "context_length": 8192, "max_tokens": 4096}
        client = lmstudio.LMStudio(settings)
        catalog = [{"key": "test", "max_context_length": 131072, "loaded_instances": []}]
        with patch.object(lmstudio, "list_models", return_value=catalog), \
                patch.object(lmstudio, "_request", return_value={
                    "status": "loaded", "instance_id": "loaded",
                    "load_config": {"context_length": 12288}}) as send:
            self.assertEqual(client._ensure_loaded(), "loaded")
        self.assertEqual(send.call_args.args[2], {"model": "test", "echo_load_config": True})
        self.assertEqual(client.loaded_context_length, 12288)

    def test_unknown_actual_context_never_defaults_to_model_capacity(self):
        client = lmstudio.LMStudio({"model": "test", "context_length": 8192})
        with patch.object(lmstudio, "list_models", return_value=[
                {"key": "test", "max_context_length": 262144,
                 "loaded_instances": [{"id": "loaded"}]}]):
            self.assertEqual(client._ensure_loaded(), "loaded")
        self.assertIsNone(client.loaded_context_length)
        self.assertIn("取得不可", token_policy_description(client))
        self.assertEqual(planning_batch_size(client, maximum=6, context_per_cut=1100), 6)

    def test_batch_size_uses_actual_context_but_is_not_a_token_limit(self):
        for context, expected in ((2048, 1), (4096, 3), (8192, 6), (32768, 6), (None, 6)):
            with self.subTest(context=context):
                client = SimpleNamespace(loaded_context_length=context,
                                         settings={"max_tokens": 4, "context_length": 4096})
                self.assertEqual(planning_batch_size(client, maximum=6, context_per_cut=1100), expected)
        self.assertNotIn("max_tokens", structured_payload("loaded", [], "plan", SCHEMA))

    def test_native_and_compatible_requests_delegate_even_with_old_settings(self):
        for preference, options, direct, translating in (
                ("on", ("off", "on"), True, False),
                ("off", ("off", "on"), True, False),
                ("auto", ("off", "on"), True, False),
                ("off", ("on",), True, False),
                ("on", ("off", "on"), False, True),
                ("off", ("on",), False, True),
                ("on", ("off", "on"), False, False)):
            with self.subTest(preference=preference, options=options, direct=direct, translating=translating):
                client = SimpleNamespace(settings={"max_tokens":4096, "context_length":8192,
                                                  "image_reasoning":preference},
                                         _reasoning_options=options, loaded_context_length=16384)
                native = (translating and "off" in options) or (
                    direct and preference in options and preference != "auto")
                reply = ({"output":[{"type":"message","content":'{"text":"ok"}'}]}
                         if native else {"choices":[{"message":{"content":'{"text":"ok"}'}}]})
                with patch.object(lmstudio, "_request", return_value=reply) as send:
                    value = request_validated(client, "loaded", "system", "request", SCHEMA,
                                              "test", lambda obj: obj, direct_answer=direct,
                                              translation_chars=5 if translating else None)
                self.assertEqual(value, {"text":"ok"})
                _, route, body = send.call_args.args
                self.assertEqual(route, "/api/v1/chat" if native else "/v1/chat/completions")
                for field in ("max_tokens", "max_output_tokens", "context_length"):
                    self.assertNotIn(field, body)
                self.assertEqual(body["temperature"], 0 if translating else 0.2)
                if native:
                    self.assertEqual(body["reasoning"], "off" if translating else preference)

    def test_empty_and_truncated_replies_do_not_retry(self):
        client = SimpleNamespace(settings={"max_tokens":4096}, loaded_context_length=16384)
        for reply, message in (
                ({"choices":[{"message":{"content":""}}]}, "最終回答が空"),
                ({"choices":[{"message":{"content":'{"text":'}, "finish_reason":"length"}]}, "長さ制限")):
            with self.subTest(message=message):
                with patch.object(lmstudio, "_request", return_value=reply) as send:
                    with self.assertRaisesRegex(OrchestratorError, message + ".*LM Studio管理"):
                        request_validated(client, "loaded", "system", "request", SCHEMA,
                                          "test", lambda value: value)
                    send.assert_called_once()

    def test_nonempty_invalid_json_retains_one_schema_retry_without_cap(self):
        client = SimpleNamespace(settings={"max_tokens":4096})
        with patch.object(lmstudio, "_request", side_effect=[
                {"choices":[{"message":{"content":"invalid"}}]},
                {"choices":[{"message":{"content":json.dumps({"text":"ok"})}}]}]) as send:
            value = request_validated(client, "loaded", "system", "request", SCHEMA,
                                      "test", lambda obj: obj)
        self.assertEqual(value, {"text":"ok"})
        self.assertEqual(send.call_count, 2)
        for call in send.call_args_list:
            self.assertNotIn("max_tokens", call.args[2])


if __name__ == "__main__":
    unittest.main()
