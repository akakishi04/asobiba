"""Regression: model-generated seeds must never override GUI/user seed policy."""

from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from comfy_orchestrator import core, gui, lmstudio

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_CONFIG = ROOT / "config.example.json"


class SeedPolicyTests(unittest.TestCase):
    def setUp(self):
        self.config = core.load_config(TEMPLATE_CONFIG)
        self.config["llm"]["model"] = "test-model"

    def run_with_model_seed(self, model_seed, overrides=None):
        llm_result = {
            "workflow_id": "wai_t2i_basic",
            "parameters": {
                "positive_prompt": "1girl, silver hair, beach, sunset, anime style",
                "seed": model_seed,
            },
        }

        class FakeLMStudio:
            def __init__(self, settings):
                pass

            def interpret(self, text, workflows, image, progress=None):
                return llm_result

        with patch.object(lmstudio, "LMStudio", FakeLMStudio), patch.object(
            core.secrets, "randbits", return_value=12345678
        ) as generate_seed:
            result = core.execute(
                self.config, TEMPLATE_CONFIG, "夕暮れの海辺の少女",
                dry_run=True, selected_workflow="wai_t2i_basic", overrides=overrides
            )
        return result, generate_seed

    def test_llm_schema_does_not_offer_seed_field(self):
        fields = core.plan_schema(self.config["workflows"])["properties"]["parameters"]["properties"]
        self.assertNotIn("seed", fields)
        self.assertIn("positive_prompt", fields)
        self.assertIn("steps", fields)

    def test_out_of_range_llm_seed_is_ignored(self):
        result, generated = self.run_with_model_seed(10 ** 80, overrides={
            "width": 768, "height": 768, "steps": 20, "cfg": 5.0,
        })
        self.assertEqual(result["status"], "dry_run")
        self.assertEqual(result["parameters"]["seed"], 12345678)
        self.assertEqual(result["parameters"]["width"], 768)
        generated.assert_called_once_with(32)

    def test_negative_model_seed_never_causes_failure(self):
        result, generated = self.run_with_model_seed(-1)
        self.assertEqual(result["parameters"]["seed"], 12345678)
        generated.assert_called_once()

    def test_non_numeric_model_seed_is_ignored(self):
        result, generated = self.run_with_model_seed("random")
        self.assertEqual(result["parameters"]["seed"], 12345678)
        generated.assert_called_once()

    def test_gui_seed_has_priority_over_model_seed(self):
        result, generated = self.run_with_model_seed(10 ** 80, overrides={
            "seed": 98765,
        })
        self.assertEqual(result["parameters"]["seed"], 98765)
        generated.assert_not_called()

    def test_gui_invalid_seed_remains_a_validation_error(self):
        with self.assertRaisesRegex(core.OrchestratorError, "seed の範囲"):
            self.run_with_model_seed(100, overrides={"seed": -1})

    def test_empty_gui_seed_is_not_sent_as_override(self):
        def field(value):
            return SimpleNamespace(get=lambda: value)

        fake_gui = SimpleNamespace(
            width=field("768"), height=field("768"),
            steps=field("20"), cfg=field("5.0"), seed=field(""),
        )
        overrides = gui.Application._overrides(fake_gui)
        self.assertEqual(overrides, {
            "width": 768, "height": 768, "steps": 20, "cfg": 5.0,
        })
        self.assertNotIn("seed", overrides)


if __name__ == "__main__":
    unittest.main()
