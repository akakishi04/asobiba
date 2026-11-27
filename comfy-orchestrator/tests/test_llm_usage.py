"""Actual HTTP response accounting, including retries, native reasoning and missing usage."""
import csv
import json
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from comfy_orchestrator import lmstudio, http_api
from comfy_orchestrator.llm_usage import (UsageStore, parse_usage, format_count, format_summary,
                                         measured_request, inference_purpose)
from comfy_orchestrator.parameters import OrchestratorError
from comfy_orchestrator.prompt_inference import request_validated
from comfy_orchestrator.ollama_client import Ollama

SETTINGS = {"base_url": "http://127.0.0.1:1234", "model": "test-model", "max_tokens": 4096}


def reply(value, *, input_tokens=100, output_tokens=20, reasoning=0):
    return {"choices": [{"message": {"content": json.dumps(value)}}],
            "usage": {"prompt_tokens": input_tokens, "completion_tokens": output_tokens,
                      "completion_tokens_details": {"reasoning_tokens": reasoning},
                      "prompt_tokens_details": {"cached_tokens": 10}}}


class UsageTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.store = UsageStore(self.root / "usage.sqlite3")

    def rows(self):
        path = self.store.export_csv(self.root / "export.csv")
        with path.open(encoding="utf-8-sig", newline="") as stream:
            return list(csv.DictReader(stream))

    def test_openai_usage_counts_actual_requests_not_model_management(self):
        payload = {"model": "instance", "messages": [
            {"role": "user", "content": [{"type": "image_url", "image_url": {"url": "secret-image"}},
                                         {"type": "text", "text": "secret-prompt"}]}],
            "response_format": {"json_schema": {"name": "h3_visual_observation"}}}
        response = reply({"answer": "secret-output"}, input_tokens=1000, output_tokens=120, reasoning=80)
        notify = Mock()
        def operation():
            lmstudio._request(SETTINGS, "/api/v1/models")
            lmstudio._request(SETTINGS, "/api/v1/models/load", {"model": "test-model"})
            result = lmstudio._request(SETTINGS, "/v1/chat/completions", payload)
            lmstudio._request(SETTINGS, "/api/v1/models/unload", {"instance_id": "instance"})
            return result
        with patch.object(lmstudio, "_open_json", return_value=response) as send:
            self.assertIs(self.store.run(operation, action="generate", mode="video", frames=124, notify=notify), response)
        self.assertEqual(send.call_count, 4)
        total = self.store.report()["total"]
        self.assertEqual((total["calls"], total["input_tokens"], total["output_tokens"],
                          total["reasoning_tokens"], total["cached_input_tokens"], total["missing"]),
                         (1, 1000, 120, 80, 10, 0))
        row = self.rows()[0]
        self.assertEqual(row["purpose"], "h3_visual_observation")
        self.assertEqual(row["model"], SETTINGS["model"])
        self.assertEqual(row["vision"], "1")
        self.assertEqual(row["frames"], "124")
        self.assertIn("IN 1,000 / OUT 120", notify.call_args.args[0])
        self.assertNotIn("secret", str(self.rows()))

    def test_native_usage_survives_normalization_and_keeps_reasoning_subset(self):
        client = SimpleNamespace(settings=SETTINGS, _reasoning_options=("off",))
        response = {"output": [{"type": "message", "content": '{"text":"日本語"}'}],
                    "stats": {"input_tokens": 250, "total_output_tokens": 55,
                              "reasoning_output_tokens": 5}}
        with patch.object(lmstudio, "_open_json", return_value=response):
            result = self.store.run(
                lambda: request_validated(client, "instance", "translate", "data",
                                          {"properties": {"text": {}}}, "single_japanese_review",
                                          lambda value: value, translation_chars=20),
                action="review_translate")
        self.assertEqual(result, {"text": "日本語"})
        row = self.rows()[0]
        self.assertEqual(row["route"], "/api/v1/chat")
        self.assertEqual(row["purpose"], "single_japanese_review")
        self.assertEqual((row["input_tokens"], row["output_tokens"], row["reasoning_tokens"]),
                         ("250", "55", "5"))
        self.assertEqual(row["cached_input_tokens"], "")

    def test_invalid_response_and_repair_both_count(self):
        client = SimpleNamespace(settings=SETTINGS)
        def validate(value):
            if "correct" not in value:
                raise OrchestratorError("invalid")
            return value
        with patch.object(lmstudio, "_open_json", side_effect=[
                reply({"wrong": 1}, input_tokens=100, output_tokens=20),
                reply({"correct": 1}, input_tokens=140, output_tokens=30)]) as send:
            result = self.store.run(
                lambda: request_validated(client, "instance", "instructions", "request",
                                          {"type": "object"}, "h3_official_prompt", validate),
                action="generate")
        self.assertEqual(result, {"correct": 1})
        self.assertEqual(send.call_count, 2)
        row = self.store.report()["operations"][0]
        self.assertEqual((row["calls"], row["input_tokens"], row["output_tokens"]), (2, 240, 50))

    def test_missing_usage_and_timeout_are_not_zero(self):
        def operation():
            lmstudio._request(SETTINGS, "/v1/chat/completions", {})
            lmstudio._request(SETTINGS, "/v1/chat/completions", {})
            lmstudio._request(SETTINGS, "/api/v1/chat", {})
        with patch.object(lmstudio, "_open_json", side_effect=[
                reply({"ok": True}), {"usage": {"prompt_tokens": 40}},
                OrchestratorError("timed out")]):
            with self.assertRaisesRegex(OrchestratorError, "タイムアウト"):
                self.store.run(operation, action="long_plan")
        row = self.store.report()["operations"][0]
        self.assertEqual(row["operation_status"], "interrupted")
        self.assertEqual((row["calls"], row["missing"], row["failed"]), (3, 2, 1))
        self.assertEqual(format_count(row, "input_tokens"), "≥140")
        self.assertEqual(format_count(row, "output_tokens"), "≥20")
        rows = self.rows()
        self.assertEqual(sum(r["request_status"] == "error" for r in rows), 1)
        self.assertEqual(sum(r["output_tokens"] == "" for r in rows), 2)

    def test_zero_request_operations_and_review_group_export(self):
        with patch.object(lmstudio, "_open_json", return_value=reply({"ok": True})):
            self.store.run(lambda: lmstudio._request(SETTINGS, "/v1/chat/completions", {}),
                           action="review", group_id="review-one")
        self.store.run(lambda: 7, action="review_generate", group_id="review-one")
        report = UsageStore(self.store.database).report()
        self.assertEqual(report["total"]["operations"], 2)
        self.assertEqual(report["total"]["calls"], 1)
        row = next(r for r in report["operations"] if r["action"] == "review_generate")
        self.assertEqual(format_summary(row), "IN 0 / OUT 0 / 0リクエスト")
        rows = self.rows()
        self.assertEqual({r["group_id"] for r in rows}, {"review-one"})
        self.assertEqual(next(r for r in rows if r["action"] == "review_generate")["request_id"], "")

    def test_ollama_unload_is_not_inference(self):
        answer = {"response": '{"workflow_id":"wai","parameters":{}}',
                  "prompt_eval_count": 80, "eval_count": 12}
        settings = {"model": "ollama-test", "base_url": "http://localhost:11434"}
        with patch.object(http_api, "http_json", side_effect=[answer, {"done": True, "done_reason": "unload"}]) as send:
            value = self.store.run(lambda: Ollama(settings).interpret("tree", {
                "wai": {"kind": "t2i", "bindings": {"positive_prompt": {}}}}, None),
                action="cli_review")
        self.assertEqual(value["workflow_id"], "wai")
        self.assertEqual(send.call_count, 2)
        row = self.rows()[0]
        self.assertEqual((row["provider"], row["input_tokens"], row["output_tokens"]), ("ollama", "80", "12"))

    def test_logging_failure_does_not_mask_success_or_original_error(self):
        notify = Mock()
        with patch.object(self.store, "_begin", side_effect=sqlite3.OperationalError("disk")):
            operation = Mock(return_value=42)
            self.assertEqual(self.store.run(operation, action="generate", notify=notify), 42)
            operation.assert_called_once()
        with patch.object(self.store, "_start_request", side_effect=sqlite3.OperationalError("disk")), \
                patch.object(lmstudio, "_open_json", return_value=reply({"ok": True})):
            self.store.run(lambda: lmstudio._request(SETTINGS, "/v1/chat/completions", {}),
                           action="generate", notify=notify)
        row = self.store.report()["operations"][0]
        self.assertEqual(row["recording_errors"], 1)
        self.assertEqual(format_count(row, "input_tokens"), "—")
        with patch.object(self.store, "_finish_request", side_effect=sqlite3.OperationalError("disk")), \
                patch.object(lmstudio, "_open_json", side_effect=OrchestratorError("original")):
            with self.assertRaisesRegex(OrchestratorError, "original"):
                self.store.run(lambda: lmstudio._request(SETTINGS, "/v1/chat/completions", {}),
                               action="generate", notify=notify)
        self.assertGreater(notify.call_count, 0)

    def test_thread_scopes_are_independent_and_unscoped_calls_are_ignored(self):
        barrier = threading.Barrier(2)
        errors = []
        def worker(action, count):
            try:
                def operation():
                    barrier.wait(5)
                    measured_request("lmstudio", "/v1/chat/completions", {}, action,
                                     lambda: reply({}, input_tokens=count, output_tokens=count))
                self.store.run(operation, action=action)
            except Exception as exc:
                errors.append(exc)
        threads = [threading.Thread(target=worker, args=(action, count))
                   for action, count in (("generate", 20), ("review", 40))]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(10)
        self.assertFalse(errors, errors)
        self.assertTrue(all(not thread.is_alive() for thread in threads))
        measured_request("lmstudio", "/v1/chat/completions", {}, "unscoped", lambda: reply({}))
        rows = {r["action"]: r for r in self.store.report()["operations"]}
        self.assertEqual(rows["generate"]["input_tokens"], 20)
        self.assertEqual(rows["review"]["input_tokens"], 40)
        self.assertEqual(self.store.report()["total"]["calls"], 2)

    def test_parse_malformed_usage_is_unknown_and_native_output_not_double_counted(self):
        self.assertEqual(parse_usage("lmstudio", "/api/v1/chat", {"stats": {
            "input_tokens": True, "total_output_tokens": 90, "reasoning_output_tokens": 40}}),
            {"input_tokens": None, "output_tokens": 90, "reasoning_tokens": 40,
             "cached_input_tokens": None})
        self.assertIsNone(parse_usage("lmstudio", "/v1/chat/completions", {"usage": {"prompt_tokens": -1}})["input_tokens"])

    def test_running_operation_and_request_preserve_unknowns(self):
        self.store._begin("operation", "generate", "video", "h3", 124, None, None)
        self.store._start_request("operation", "lmstudio", "/v1/chat/completions", {}, "test")
        report = self.store.report()
        row = report["operations"][0]
        self.assertEqual(row["operation_status"], "running")
        self.assertEqual(row["missing"], 1)
        self.assertEqual(format_count(row, "output_tokens"), "—")
        self.assertEqual(report["total"]["unfinished"], 1)


if __name__ == "__main__":
    unittest.main()
