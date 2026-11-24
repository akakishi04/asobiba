"""Character abstraction regressions for varied art styles and viewpoints.

Offline: mocks LM Studio; does not depend on local GPU, image encoders or Tk.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from comfy_orchestrator import character_refs, core, lmstudio


def observed(**extra):
    data = {name: "unknown" for name in character_refs.FEATURES}
    data.update({
        "hair_color": "black",
        "hair_style": "side-swept bob",
        "eye_shape": "upturned",
        "face": "small pointed chin",
    })
    data.update(extra)
    return data


def synthesis(hypotheses=None):
    return {
        "common": [],
        "candidates": [],
        "variable": [{"feature": "outfit", "details": "different outfits"}],
        "uncertain": [],
        "identity_hypotheses": hypotheses or [],
    }


def hypothesis(
    aspect="face",
    description="small pointed chin and wide-set eyes",
    support=(1, 2), conflict=(), confidence="medium",
):
    return {
        "aspect": aspect,
        "description": description,
        "supporting_images": list(support),
        "conflicting_images": list(conflict),
        "confidence": confidence,
        "rationale": "Both illustrations show compatible facial proportions",
    }


class CharacterAbstractionTests(unittest.TestCase):
    def test_morphology_schema_exposes_viewpoint_invariant_features(self):
        properties = character_refs.observation_schema()["properties"]
        self.assertIn("facial_geometry", properties)
        self.assertIn("silhouette", properties)
        self.assertIn("shape_language", properties)
        self.assertIn("distinctive_motifs", properties)
        schema = character_refs.intersection_schema()
        self.assertIn("identity_hypotheses", schema["required"])
        details = schema["properties"]["identity_hypotheses"]["items"]["properties"]
        self.assertEqual(set(details["confidence"]["enum"]), {"high", "medium", "low"})
        self.assertIn("conflicting_images", details)

    def test_abstract_character_feature_survives_variation_without_exact_match(self):
        result = character_refs.normalize_analysis(
            [
                observed(
                    facial_geometry="rounded face, pointed chin",
                    outfit="white blouse",
                ),
                observed(
                    facial_geometry="soft cheek outline, narrow jaw",
                    outfit="dark armor",
                    hair_color="unknown",
                ),
            ],
            synthesis([hypothesis()]),
        )
        self.assertEqual(result["common"], [])
        self.assertEqual(result["identity_hypotheses"][0]["confidence"], "medium")
        draft = character_refs.suggested_traits(result)
        self.assertIn("キャラの核", draft)
        self.assertIn("small pointed chin", draft)
        self.assertNotIn("dark armor", draft)
        report = character_refs.format_evidence(result)
        self.assertIn("支持2/2", report)
        self.assertIn("根拠・変化の説明", report)

    def test_missing_view_is_not_a_contradiction(self):
        result = character_refs.normalize_analysis(
            [observed(), observed(), observed(face="unknown")],
            synthesis([hypothesis(support=(1, 2), conflict=(), confidence="medium")]),
        )
        self.assertIn("small pointed chin", character_refs.suggested_traits(result))
        self.assertIn("支持2/3", character_refs.format_evidence(result))

    def test_true_contradictions_prevent_auto_drafting(self):
        result = character_refs.normalize_analysis(
            [observed(), observed(), observed(face="square chin")],
            synthesis([
                hypothesis(support=(1, 2), conflict=(3,), confidence="high"),
                hypothesis(
                    aspect="hair", description="black bob hair",
                    support=(1,), confidence="high",
                ),
            ]),
        )
        self.assertEqual(
            [x["confidence"] for x in result["identity_hypotheses"]],
            ["low", "low"],
        )
        self.assertNotIn("black bob hair", character_refs.suggested_traits(result))
        self.assertNotIn("small pointed chin", character_refs.suggested_traits(result))
        self.assertIn("反証 (画像3)", character_refs.format_evidence(result))

    def test_invalid_evidence_is_rejected(self):
        for item in (
            hypothesis(support=(1,), conflict=(1,)),
            hypothesis(support=(4,)),
            hypothesis(support=(True,)),
            hypothesis(support=(1, 1)),
            {**hypothesis(), "confidence": []},
            {**hypothesis(), "aspect": "artist_style"},
            {**hypothesis(), "rationale": ""},
        ):
            with self.subTest(item=item):
                with self.assertRaises(core.OrchestratorError):
                    character_refs.normalize_analysis(
                        [observed(), observed()], synthesis([item]),
                    )

    def test_existing_legacy_observations_and_draft_remain_readable(self):
        old = [observed(), observed()]
        old_synthesis = {
            "common": [{"feature": "hair_color", "value": "black", "images": [1, 2]}],
            "candidates": [], "variable": [], "uncertain": [],
        }
        analysis = character_refs.normalize_analysis(old, old_synthesis)
        self.assertEqual(analysis["identity_hypotheses"], [])
        self.assertEqual(analysis["observations"][0]["facial_geometry"], "unknown")
        self.assertEqual(character_refs.suggested_traits(analysis), "髪色: black")
        with tempfile.TemporaryDirectory() as folder:
            refs = []
            for i in range(2):
                p = Path(folder) / f"ref_{i}.png"
                p.write_bytes(b"image")
                refs.append(p)
            character_refs.save_character_sheet(
                Path(folder), tuple(refs), old_synthesis | {"observations": old},
                "髪色: black",
            )
            loaded = character_refs.load_character_sheet(Path(folder))
            self.assertEqual(loaded[2], "髪色: black")
            self.assertEqual(loaded[1]["identity_hypotheses"], [])

    def test_model_asked_for_identity_signature_separate_from_exact_overlap(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = []
            for i in range(2):
                image = Path(folder) / f"{i}.png"
                image.write_bytes(f"image{i}".encode())
                paths.append(image)
            responses = [
                observed(facial_geometry="soft jaw with pointed chin"),
                observed(facial_geometry="rounded cheeks, narrow chin"),
                synthesis([hypothesis()]),
            ]
            calls = []

            def reply(_settings, endpoint, payload=None):
                calls.append((endpoint, payload))
                if endpoint == "/v1/chat/completions":
                    return {"choices": [{"message": {
                        "content": json.dumps(responses.pop(0)),
                    }}]}
                if endpoint == "/api/v1/models/unload":
                    return {"instance_id": "test"}
                raise AssertionError(endpoint)

            with patch.object(
                lmstudio.LMStudio, "_ensure_loaded", return_value="test"
            ), patch.object(lmstudio, "_request", side_effect=reply):
                result = lmstudio.LMStudio({
                    "model": "vision", "base_url": "http://127.0.0.1:1234",
                    "unload_after_inference": True,
                }).analyze_character_references(paths)
            vision_system = calls[0][1]["messages"][0]["content"]
            merge_system = calls[2][1]["messages"][0]["content"]
            self.assertIn("FACIAL GEOMETRY", vision_system)
            self.assertIn("SHAPE LANGUAGE", vision_system)
            self.assertIn("VISUAL IDENTITY SIGNATURE", merge_system)
            self.assertIn("not merely", merge_system.lower())
            self.assertEqual(calls[-1][0], "/api/v1/models/unload")
            self.assertEqual(result["identity_hypotheses"][0]["aspect"], "face")


if __name__ == "__main__":
    unittest.main()
