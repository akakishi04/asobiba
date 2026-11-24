"""Multi-image character references: evidence, explicit approval and replay provenance.

All tests are offline and require no Tk window, GPU or LM Studio server.
"""

from __future__ import annotations

import copy
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from comfy_orchestrator import character_refs, core, gui, lmstudio
from comfy_orchestrator.history import HistoryStore


PROJECT = Path(__file__).resolve().parents[1]


def observation(**custom):
    fields = {
        "hair_color": "black", "hair_style": "short bob",
        "eye_color": "blue", "eye_shape": "round",
        "face": "small mole under eye", "body": "unknown",
        "outfit": "white blouse", "accessories": "silver earrings",
        "other": "unknown",
    }
    fields.update(custom)
    return fields


def synthesis():
    return {
        "common": [
            {"feature": "hair_color", "value": "black", "images": [1, 2]},
            # A mistaken LLM label for partial evidence must be downgraded.
            {"feature": "eye_color", "value": "blue", "images": [1]},
        ],
        "candidates": [
            {"feature": "hair_style", "value": "short bob", "images": [1, 2]},
        ],
        "variable": [
            {"feature": "outfit", "details": "image 1 white blouse; image 2 blue coat"},
        ],
        "uncertain": [
            {"feature": "body", "details": "full body is not visible in either image"},
        ],
    }


class EvidenceTests(unittest.TestCase):
    def test_consensus_requires_all_images(self):
        result = character_refs.normalize_analysis(
            [observation(), observation(outfit="blue coat")], synthesis(),
        )
        self.assertEqual({item["feature"] for item in result["common"]},
                         {"hair_color", "hair_style"})
        self.assertEqual([x["feature"] for x in result["candidates"]],
                         ["eye_color"])
        self.assertEqual(character_refs.suggested_traits(result),
                         "髪色: black\n髪型・前髪: short bob")
        report = character_refs.format_evidence(result)
        self.assertIn("2/2", report)
        self.assertIn("1/2", report)
        self.assertIn("画像ごとの差分", report)
        self.assertIn("不明・矛盾", report)
        self.assertNotIn("目の色: blue\n", character_refs.suggested_traits(result))

    def test_invalid_evidence_indices_are_rejected(self):
        for source_ids in ([0], [3], [1, 1], [True], ["1"], []):
            with self.subTest(indices=source_ids):
                bad = synthesis()
                bad["common"][0]["images"] = source_ids
                with self.assertRaises(core.OrchestratorError):
                    character_refs.normalize_analysis(
                        [observation(), observation()], bad,
                    )

    def test_observation_schema_is_bounded_and_unknown_allowed(self):
        schema = character_refs.observation_schema()
        self.assertEqual(set(schema["required"]), set(character_refs.FEATURES))
        self.assertFalse(schema["additionalProperties"])
        self.assertIn("body", schema["properties"])
        self.assertIn("common", character_refs.intersection_schema()["properties"])

    def test_images_two_through_four_unique_and_bounded(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = []
            for i in range(5):
                p = Path(folder) / f"{i}.png"
                p.write_bytes(b"tiny test image")
                paths.append(p)
            self.assertEqual(len(character_refs.validate_images(paths[:4])), 4)
            with self.assertRaises(core.OrchestratorError):
                character_refs.validate_images(paths[:1])
            with self.assertRaises(core.OrchestratorError):
                character_refs.validate_images(paths)
            with self.assertRaises(core.OrchestratorError):
                character_refs.validate_images([paths[0], paths[0]])

    def test_approved_text_cannot_be_empty_or_unbounded(self):
        self.assertEqual(character_refs.normalize_approved(" 髪色: 黒 "), "髪色: 黒")
        for bad in ("", "  ", "a" * 3001, 123):
            with self.assertRaises(core.OrchestratorError):
                character_refs.normalize_approved(bad)

    def test_local_approved_sheet_persists_and_can_be_cleared(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            refs = []
            for i in range(2):
                p = root / f"p{i}.png"
                p.write_bytes(b"image")
                refs.append(p)
            data = character_refs.normalize_analysis(
                [observation(), observation()], synthesis(),
            )
            character_refs.save_character_sheet(root, tuple(refs), data, "blue eyes")
            loaded_refs, loaded_data, traits = character_refs.load_character_sheet(root)
            self.assertEqual(loaded_refs, tuple(refs))
            self.assertEqual(loaded_data, data)
            self.assertEqual(traits, "blue eyes")
            character_refs.clear_character_sheet(root)
            self.assertEqual(character_refs.load_character_sheet(root), ((), None, ""))

    def test_sheet_missing_original_images_is_not_reused(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            refs = []
            for i in range(2):
                p = root / f"ref{i}.png"
                p.write_bytes(b"image")
                refs.append(p)
            data = character_refs.normalize_analysis(
                [observation(), observation()], synthesis(),
            )
            character_refs.save_character_sheet(root, tuple(refs), data, "short hair")
            refs[0].unlink()
            self.assertEqual(character_refs.load_character_sheet(root), ((), None, ""))


class MultiImageInferenceTests(unittest.TestCase):
    def test_each_reference_observed_separately_then_merged_and_unloaded(self):
        with tempfile.TemporaryDirectory() as folder:
            image1 = Path(folder) / "front.png"
            image2 = Path(folder) / "side.png"
            image1.write_bytes(b"img1")
            image2.write_bytes(b"img2")
            requests = []
            answers = [observation(), observation(outfit="blue coat"), synthesis()]
            progress = []

            def fake_request(_settings, route, body=None):
                requests.append((route, body))
                if route == "/v1/chat/completions":
                    return {"choices": [{"message": {
                        "content": json.dumps(answers.pop(0)),
                    }}]}
                if route == "/api/v1/models/unload":
                    return {"instance_id": "instance-1"}
                raise AssertionError(route)

            settings = {
                "model": "local-vision-model", "base_url": "http://127.0.0.1:1234",
                "max_tokens": 4096, "unload_after_inference": True,
                "send_reference_to_llm": False,
            }
            with patch.object(
                lmstudio.LMStudio, "_ensure_loaded", return_value="instance-1"
            ), patch.object(lmstudio, "_request", side_effect=fake_request):
                result = lmstudio.LMStudio(settings).analyze_character_references(
                    [image1, image2], progress.append,
                )
            self.assertEqual([name for name, _ in requests], [
                "/v1/chat/completions", "/v1/chat/completions",
                "/v1/chat/completions", "/api/v1/models/unload",
            ])
            first, second, merged = [p for _, p in requests[:3]]
            self.assertEqual(first["messages"][1]["content"][1]["type"], "image_url")
            self.assertEqual(second["messages"][1]["content"][1]["type"], "image_url")
            self.assertNotEqual(
                first["messages"][1]["content"][1]["image_url"]["url"],
                second["messages"][1]["content"][1]["image_url"]["url"],
            )
            self.assertIsInstance(merged["messages"][1]["content"], str)
            self.assertIn("blue coat", merged["messages"][1]["content"])
            self.assertEqual(len(result["observations"]), 2)
            self.assertEqual(result["common"][0]["feature"], "hair_color")
            self.assertEqual(len(progress), 5)

    def test_failed_image_analysis_still_unloads_selected_model(self):
        with tempfile.TemporaryDirectory() as folder:
            refs = []
            for i in range(2):
                p = Path(folder) / f"{i}.png"
                p.write_bytes(b"i")
                refs.append(p)
            routes = []
            def fake_request(_settings, route, body=None):
                routes.append(route)
                if route == "/v1/chat/completions":
                    raise core.OrchestratorError("test inference error")
                if route == "/api/v1/models/unload":
                    return {"instance_id": "instance-1"}
                raise AssertionError(route)
            settings = {
                "model": "vision", "base_url": "http://127.0.0.1:1234",
                "unload_after_inference": True,
            }
            with patch.object(
                lmstudio.LMStudio, "_ensure_loaded", return_value="instance-1"
            ), patch.object(lmstudio, "_request", side_effect=fake_request):
                with self.assertRaisesRegex(core.OrchestratorError, "test inference"):
                    lmstudio.LMStudio(settings).analyze_character_references(refs)
            self.assertEqual(routes[-1], "/api/v1/models/unload")

    def test_core_injects_only_explicitly_approved_text(self):
        config = core.load_config(PROJECT / "config.example.json")
        config["llm"]["model"] = "fake-model"
        seen = []
        class FakeLM:
            def __init__(self, settings):
                pass
            def interpret(self, text, workflows, image, progress=None, **kwargs):
                seen.append(kwargs)
                return {"workflow_id": "wai_t2i_basic",
                        "parameters": {"positive_prompt": "silver bob, blue eyes"}}
        with patch.object(lmstudio, "LMStudio", FakeLM):
            core.execute(
                config, PROJECT / "config.example.json", "draw a new scene",
                selected_workflow="wai_t2i_basic", dry_run=True,
                character_traits="silver bob, blue eyes",
            )
            core.execute(
                config, PROJECT / "config.example.json", "no character reference",
                selected_workflow="wai_t2i_basic", dry_run=True,
            )
        self.assertEqual(seen[0]["character_traits"], "silver bob, blue eyes")
        self.assertNotIn("character_traits", seen[1])

    def test_vlm_planner_receives_confirmed_identity_but_no_candidate_notes(self):
        config = core.load_config(PROJECT / "config.example.json")
        settings = {**config["llm"], "model": "fake-model"}
        calls = []
        def fake_request(_settings, route, payload=None):
            calls.append((route, payload))
            if route == "/v1/chat/completions":
                return {"choices": [{"message": {"content": json.dumps({
                    "workflow_id": "wai_t2i_basic",
                    "parameters": {"positive_prompt": "1girl, black bob"},
                })}}]}
            if route == "/api/v1/models/unload":
                return {"instance_id": "instance"}
            raise AssertionError(route)
        with patch.object(
            lmstudio.LMStudio, "_ensure_loaded", return_value="instance"
        ), patch.object(lmstudio, "_request", side_effect=fake_request):
            lmstudio.LMStudio(settings).interpret(
                "person at café", {"wai_t2i_basic": config["workflows"]["wai_t2i_basic"]},
                None, character_traits="short black hair, blue eyes",
            )
        user_text = calls[0][1]["messages"][1]["content"]
        self.assertIn("short black hair, blue eyes", user_text)
        self.assertIn("USER-APPROVED", calls[0][1]["messages"][0]["content"])
        self.assertNotIn("variable_traits", user_text)


class CharacterHistoryTests(unittest.TestCase):
    def test_approved_sheet_and_images_survive_original_deletion(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            store = HistoryStore(root)
            output = store.outputs / "result.png"
            output.write_bytes(b"generated image")
            refs = []
            for i in range(2):
                p = root / f"reference{i}.png"
                p.write_bytes(f"img{i}".encode())
                refs.append(p)
            analysis = character_refs.normalize_analysis(
                [observation(), observation()], synthesis(),
            )
            entry = store.record(
                prompt_id="character-1", workflow_id="wai_t2i_basic",
                kind="t2i", request_text="new portrait",
                parameters={"positive_prompt": "girl, bob cut"},
                images=[output], character_references=tuple(refs),
                character_traits="髪型: 黒いショート", character_analysis=analysis,
            )
            for p in refs:
                p.unlink()
            saved = HistoryStore(root).get(entry.id)
            self.assertEqual(saved.character_traits, "髪型: 黒いショート")
            self.assertEqual(saved.character_analysis, analysis)
            self.assertEqual(
                [p.read_bytes() for p in saved.character_references],
                [b"img0", b"img1"],
            )
            self.assertNotEqual(
                saved.character_references[0], saved.character_references[1]
            )
            self.assertEqual(
                gui.history_prompt_details(saved)["character_traits"],
                "髪型: 黒いショート",
            )

    def test_old_history_without_character_fields_is_readable(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            db = root / "data"
            db.mkdir()
            with sqlite3.connect(db / "history.sqlite3") as con:
                con.execute("""CREATE TABLE generations (
                    id TEXT PRIMARY KEY, created_at TEXT NOT NULL,
                    prompt_id TEXT NOT NULL UNIQUE, workflow_id TEXT NOT NULL,
                    kind TEXT NOT NULL, request_text TEXT NOT NULL,
                    parameters_json TEXT NOT NULL, images_json TEXT NOT NULL,
                    reference_file TEXT, legacy INTEGER NOT NULL DEFAULT 0
                )""")
                con.execute(
                    "INSERT INTO generations VALUES (?,?,?,?,?,?,?,?,?,?)",
                    ("old", "2026-01-01", "old", "wai_t2i_basic",
                     "t2i", "old request", '{"positive_prompt":"old"}',
                     "[]", None, 0),
                )
            old = HistoryStore(root).get("old")
            self.assertIsNone(old.character_traits)
            self.assertEqual(old.character_references, ())
            self.assertIsNone(old.character_analysis)
            self.assertEqual(old.parameters["positive_prompt"], "old")

    def test_dedicated_editor_and_user_approval_are_separate_actions(self):
        import inspect
        from comfy_orchestrator.character_ui import CharacterReferenceWindow
        self.assertIn("def analyze(", inspect.getsource(CharacterReferenceWindow))
        self.assertIn("def confirm(", inspect.getsource(CharacterReferenceWindow))
        self.assertIn("self.on_confirm(", inspect.getsource(CharacterReferenceWindow.confirm))
        self.assertIn("character_traits=approved_traits",
                      inspect.getsource(gui.Application._start))
        self.assertIn("self._one_history()",
                      inspect.getsource(gui.Application._show_selected_history_prompt))


if __name__ == "__main__":
    unittest.main()
