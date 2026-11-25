"""Regression tests for off-schema LM Studio character feature replies.

An unexpected key from a local VLM must not discard otherwise usable results,
nor may it silently create approved character traits without valid evidence.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from comfy_orchestrator import character_refs, character_repair, core, lmstudio


def observation(**extra):
    obj = {name: "unknown" for name in character_refs.FEATURES}
    obj.update({"hair_color": "black", "hair_style": "short", "face": "oval face"})
    obj.update(extra)
    return obj


def raw_synthesis(**override):
    content = {
        "common": [
            {"feature": "hair_color", "value": "black", "images": [1, 2]},
        ],
        "candidates": [],
        "variable": [],
        "uncertain": [],
        "identity_hypotheses": [],
    }
    content.update(override)
    return content


class ModelRepairTests(unittest.TestCase):
    def test_unrecognized_common_feature_keeps_good_results(self):
        result = character_repair.repair_model_analysis([
            observation(), observation(),
        ], raw_synthesis(common=[
            {"feature": "hair_color", "value": "black", "images": [1, 2]},
            {"feature": "hair", "value": "short black bob", "images": [1, 2]},
        ]))
        self.assertEqual(
            [(c["feature"], c["value"]) for c in result["common"]],
            [("hair_color", "black")],
        )
        self.assertIn("hair", " ".join(result["warnings"]))
        self.assertIn("short black bob", " ".join(result["warnings"]))
        self.assertNotIn("short black bob", character_refs.suggested_traits(result))
        self.assertIn(
            "要確認：形式不一致", character_refs.format_evidence(result),
        )

    def test_known_aliases_can_be_used_with_reliable_citations(self):
        result = character_repair.repair_model_analysis([
            observation(), observation(),
        ], raw_synthesis(common=[
            {"feature": "face_shape", "value": "rounded cheeks", "images": ["1", "2"]},
            {"feature": "eye_colour", "value": "blue", "images": [1]},
            {"feature": "hairstyle", "value": "a short bob", "images": [2, 1, 2]},
        ]))
        self.assertEqual({v["feature"] for v in result["common"]}, {
            "facial_geometry", "hair_style",
        })
        self.assertEqual(
            result["candidates"][0]["feature"], "eye_color",
        )
        self.assertEqual(result["common"][1]["images"], [1, 2])

    def test_bad_values_and_broken_support_are_dropped_not_automatically_adopted(self):
        result = character_repair.repair_model_analysis([
            observation(), observation(),
        ], raw_synthesis(common=[
            {"feature": "hair_color", "value": None, "images": [1, 2]},
            {"feature": "eye_color", "value": "blue", "images": [0, 2]},
            {"feature": "body", "value": "slim", "images": ["²"]},
            {"feature": "face", "value": "narrow chin", "images": "all"},
        ]))
        self.assertEqual(result["common"], [])
        self.assertEqual(len(result["warnings"]), 4)
        self.assertEqual(character_refs.suggested_traits(result), "")

    def test_one_invalid_variable_does_not_discard_good_hypothesis(self):
        hypothesis = {
            "aspect": "face", "description": "round cheeks and narrow jaw",
            "supporting_images": [1, 2], "conflicting_images": [],
            "confidence": "MEDIUM", "rationale": "visible in both illustrations",
        }
        result = character_repair.repair_model_analysis([
            observation(), observation(),
        ], raw_synthesis(
            variable=[
                {"feature": "art_style", "details": "different rendering style"},
            ],
            identity_hypotheses=[hypothesis, {
                **hypothesis, "aspect": "wrong", "description": "not grounded",
            }],
        ))
        self.assertEqual(result["identity_hypotheses"][0]["confidence"], "medium")
        self.assertEqual(len(result["identity_hypotheses"]), 1)
        self.assertIn("round cheeks", character_refs.suggested_traits(result))
        self.assertEqual(len(result["warnings"]), 2)

    def test_invalid_observation_field_is_unknown_with_diagnostics(self):
        result = character_repair.repair_model_analysis([
            observation(eye_color=None), observation(),
        ], raw_synthesis())
        self.assertEqual(result["observations"][0]["eye_color"], "unknown")
        self.assertTrue(any("eye_color" in s for s in result["warnings"]))

    def test_diagnostic_warnings_survive_sheet_save_and_reload(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            images = []
            for i in range(2):
                p = root / f"{i}.png"
                p.write_bytes(b"image")
                images.append(p)
            analysis = character_repair.repair_model_analysis(
                [observation(), observation()],
                raw_synthesis(common=[
                    {"feature": "hair", "value": "dark bob", "images": [1, 2]},
                ]),
            )
            character_refs.save_character_sheet(
                root, tuple(images), analysis, "black hair",
            )
            refs, reopened, approved = character_refs.load_character_sheet(root)
            self.assertEqual(refs, tuple(p.resolve() for p in images))
            self.assertEqual(approved, "black hair")
            self.assertEqual(reopened["warnings"], analysis["warnings"])
            self.assertIn("dark bob", character_refs.format_evidence(reopened))

    def test_strict_validation_still_rejects_unsupported_features(self):
        with self.assertRaisesRegex(core.OrchestratorError, "共通特徴の項目"):
            character_refs.normalize_analysis(
                [observation(), observation()],
                raw_synthesis(common=[
                    {"feature": "hair", "value": "unknown alias", "images": [1, 2]},
                ]),
            )

    def test_local_llm_regression_original_error_is_recovered(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = []
            for i in range(2):
                p = Path(directory) / f"{i}.png"
                p.write_bytes(b"fake image")
                paths.append(p)
            responses = [
                observation(), observation(),
                raw_synthesis(common=[
                    {"feature": "hair_color", "value": "black", "images": [1, 2]},
                    {"feature": "hair", "value": "black short bob", "images": [1, 2]},
                ]),
            ]
            progress = []

            def fake_request(_settings, endpoint, payload=None):
                if endpoint == "/v1/chat/completions":
                    return {"choices": [{"message": {
                        "content": json.dumps(responses.pop(0)),
                    }}]}
                if endpoint == "/api/v1/models/unload":
                    return {"instance_id": "test-model"}
                raise AssertionError(endpoint)

            with patch.object(
                lmstudio.LMStudio, "_ensure_loaded", return_value="test-model"
            ), patch.object(lmstudio, "_request", side_effect=fake_request):
                result = lmstudio.LMStudio({
                    "model": "local-model", "unload_after_inference": True,
                }).analyze_character_references(paths, progress.append)
            self.assertEqual(result["common"][0]["feature"], "hair_color")
            self.assertEqual(len(result["warnings"]), 1)
            self.assertTrue(any("形式違い" in p for p in progress))

    def test_all_invalid_proposals_still_show_raw_observations_and_warnings(self):
        result = character_repair.repair_model_analysis([
            observation(), observation(),
        ], {"common": "not an array", "candidates": None,
            "variable": [], "uncertain": [], "identity_hypotheses": []})
        self.assertEqual(result["common"], [])
        self.assertEqual(len(result["observations"]), 2)
        self.assertEqual(len(result["warnings"]), 2)
        self.assertIn("画像ごとの観察結果", character_refs.format_evidence(result))


if __name__ == "__main__":
    unittest.main()
