"""Regression tests for long-running LM Studio reasoning requests."""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from comfy_orchestrator import core, gui, lmstudio


ROOT = Path(__file__).resolve().parents[1]


class InferenceTimeoutTests(unittest.TestCase):
    def setUp(self):
        self.example = json.loads((ROOT / "config.example.json").read_text(encoding="utf-8"))
        self.assertNotIn("context_length", self.example["llm"])
        self.assertNotIn("max_tokens", self.example["llm"])
        self.assertEqual(self.example["llm"]["inference_timeout_seconds"], 1200)

    def test_chat_uses_extended_timeout_only_for_inference(self):
        settings = self.example["llm"]
        observed = []

        def fake_open(request, timeout, allow_empty=False):
            observed.append((request.full_url, timeout))
            return {}

        with patch.object(lmstudio, "_open_json", side_effect=fake_open):
            lmstudio._request(settings, "/api/v1/models")
            lmstudio._request(settings, "/api/v1/models/load", {"model": "local"})
            lmstudio._request(settings, "/v1/chat/completions", {"model": "local"})
            lmstudio._request(settings, "/api/v1/models/unload", {"instance_id": "x"})
        self.assertEqual([round(t) for _, t in observed], [240, 240, 1200, 240])

    def test_timeout_error_identifies_stage_and_config(self):
        with patch.object(
            lmstudio, "_open_json", side_effect=core.OrchestratorError("API connection: timed out")
        ):
            with self.assertRaisesRegex(core.OrchestratorError, "自然文解釈.*1200秒"):
                lmstudio._request(self.example["llm"], "/v1/chat/completions", {"model": "local"})
            with self.assertRaisesRegex(core.OrchestratorError, "API操作.*240秒"):
                lmstudio._request(self.example["llm"], "/api/v1/models")

    def test_non_timeout_errors_are_not_mislabeled(self):
        with patch.object(
            lmstudio, "_open_json", side_effect=core.OrchestratorError("HTTP 400: invalid request")
        ):
            with self.assertRaisesRegex(core.OrchestratorError, "HTTP 400"):
                lmstudio._request(self.example["llm"], "/v1/chat/completions", {"model": "local"})

    def test_old_local_config_is_migrated_without_touching_other_values(self):
        with tempfile.TemporaryDirectory() as root:
            config_path = Path(root) / "config.json"
            old = copy.deepcopy(self.example)
            del old["llm"]["inference_timeout_seconds"]
            old["llm"]["base_url"] = "http://127.0.0.1:57317"
            old["llm"]["model"] = "gemma-4-12b"
            old["llm"]["timeout_seconds"] = 240
            config_path.write_text(json.dumps(old), encoding="utf-8")
            with patch.object(gui, "CONFIG", config_path):
                upgraded = gui.bootstrap_config()
            self.assertEqual(upgraded["llm"]["inference_timeout_seconds"], 1200)
            self.assertEqual(upgraded["llm"]["timeout_seconds"], 240)
            self.assertNotIn("context_length", upgraded["llm"])
            self.assertNotIn("max_tokens", upgraded["llm"])
            self.assertEqual(upgraded["llm"]["model"], "gemma-4-12b")
            self.assertEqual(upgraded["llm"]["base_url"], "http://127.0.0.1:57317")

    def test_old_stock_timeout_is_upgraded_once(self):
        with tempfile.TemporaryDirectory() as root:
            config_path = Path(root) / "config.json"
            old = copy.deepcopy(self.example)
            old["llm"]["inference_timeout_seconds"] = 600
            config_path.write_text(json.dumps(old), encoding="utf-8")
            with patch.object(gui, "CONFIG", config_path):
                upgraded = gui.bootstrap_config()
                self.assertEqual(upgraded["llm"]["inference_timeout_seconds"], 1200)
                self.assertTrue(upgraded["ui"]["inference_timeout_v2_applied"])
                upgraded["llm"]["inference_timeout_seconds"] = 600
                config_path.write_text(json.dumps(upgraded), encoding="utf-8")
                self.assertEqual(gui.bootstrap_config()["llm"]["inference_timeout_seconds"], 600)

    def test_custom_inference_timeout_is_preserved(self):
        with tempfile.TemporaryDirectory() as root:
            config_path = Path(root) / "config.json"
            old = copy.deepcopy(self.example)
            old["llm"]["inference_timeout_seconds"] = 900
            config_path.write_text(json.dumps(old), encoding="utf-8")
            with patch.object(gui, "CONFIG", config_path):
                upgraded = gui.bootstrap_config()
            self.assertEqual(upgraded["llm"]["inference_timeout_seconds"], 900)

    def test_legacy_configs_use_default_if_no_separate_timeout(self):
        settings = {**self.example["llm"]}
        settings.pop("inference_timeout_seconds")
        with patch.object(lmstudio, "_open_json", return_value={}) as fake_open:
            lmstudio._request(settings, "/v1/chat/completions", {"model": "local"})
        self.assertEqual(fake_open.call_args.kwargs["timeout"], 1200)


if __name__ == "__main__":
    unittest.main()
