"""I2I/inpaint preserve-vs-edit policy, history prompt viewer and old-data safety.

All tests run offline without Tk windows, LM Studio or ComfyUI.
"""

from __future__ import annotations

import copy
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from comfy_orchestrator import core, gui, lmstudio, prompt_profiles
from comfy_orchestrator.history import HistoryStore


ROOT = Path(__file__).resolve().parents[1]


class I2IPromptProfileTests(unittest.TestCase):
    def setUp(self):
        self.config = core.load_config(ROOT / "config.example.json")
        self.config["llm"]["model"] = "local-model"
        self.i2i = {"wai_i2i_basic": self.config["workflows"]["wai_i2i_basic"]}
        self.inpaint = {"wai_inpaint_basic": self.config["workflows"]["wai_inpaint_basic"]}

    def test_default_profile_and_comparison_label(self):
        self.assertEqual(self.config["llm"]["i2i_prompt_profile"], "preserve_edit_v1")
        self.assertIn("legacy", prompt_profiles.I2I_PROFILES)
        self.assertEqual(
            set(prompt_profiles.I2I_PROFILE_LABELS),
            set(prompt_profiles.I2I_PROFILES),
        )

    def test_legacy_is_bit_for_bit_unchanged(self):
        original = "baseline workflow selection prompt. "
        for workflows in (self.i2i, self.inpaint):
            self.assertEqual(
                prompt_profiles.apply_i2i_profile(original, workflows, "legacy"),
                original,
            )

    def test_i2i_profile_adds_preserve_edit_rules_without_inpaint_only_text(self):
        enhanced = prompt_profiles.apply_i2i_profile("base", self.i2i, "preserve_edit_v1")
        for token in (
            "PRESERVE", "EDIT:", "SOURCE IMAGE", "camera", "clothes",
            "When the reference image has NOT been shown", "negative_prompt",
        ):
            self.assertIn(token.lower(), enhanced.lower())
        self.assertNotIn("INPAINT-SPECIFIC", enhanced)

    def test_inpainting_has_additional_mask_constraint(self):
        enhanced = prompt_profiles.apply_i2i_profile(
            "base", self.inpaint, "preserve_edit_v1",
        )
        self.assertIn("INPAINT-SPECIFIC", enhanced)
        self.assertIn("outside the mask", enhanced)
        self.assertIn("do not claim to know the mask's exact outline", enhanced.lower())

    def test_non_i2i_workflows_do_not_receive_edit_instructions(self):
        for key in ("wai_t2i_basic", "wai_pose_detect", "wai_pose_skeleton"):
            with self.subTest(workflow=key):
                entry = {key: self.config["workflows"][key]}
                self.assertEqual(
                    prompt_profiles.apply_i2i_profile(
                        "old text", entry, "preserve_edit_v1",
                    ),
                    "old text",
                )

    def test_incompatible_non_illustrious_i2i_not_altered(self):
        unrelated = {"other_i2i": {
            "kind": "i2i", "description": "general image transformer",
            "bindings": {"positive_prompt": {"node": "1", "input": "text"}},
        }}
        self.assertFalse(prompt_profiles.is_i2i_context(unrelated))
        self.assertEqual(
            prompt_profiles.apply_i2i_profile("unchanged", unrelated, "preserve_edit_v1"),
            "unchanged",
        )

    def test_edit_strength_boundaries(self):
        for denoise, expected in (
            (0, "preserve-oriented"), (0.4, "preserve-oriented"),
            (0.401, "balanced"), (0.6, "balanced"),
            (0.601, "transform-oriented"), (1, "transform-oriented"),
        ):
            with self.subTest(denoise=denoise):
                self.assertEqual(prompt_profiles.edit_strength_hint(denoise), expected)
        for invalid in (-0.1, 1.1, "0.5", True):
            with self.assertRaises(ValueError):
                prompt_profiles.edit_strength_hint(invalid)

    def test_lmstudio_receives_extra_edit_policy_only_for_improved_profile(self):
        def one(profile: str, workflows: dict):
            settings = dict(
                self.config["llm"], i2i_prompt_profile=profile,
                _edit_denoise=0.53,
            )
            calls = []
            answer = {
                "workflow_id": next(iter(workflows)),
                "parameters": {"positive_prompt": "1girl, original pose"},
            }

            def fake_request(_settings, route, payload=None):
                calls.append((route, payload))
                if route == "/v1/chat/completions":
                    return {"choices": [
                        {"message": {"content": json.dumps(answer)}},
                    ]}
                if route == "/api/v1/models/unload":
                    return {"instance_id": "profile-instance"}
                raise AssertionError(route)

            with patch.object(
                lmstudio.LMStudio, "_ensure_loaded", return_value="profile-instance"
            ), patch.object(lmstudio, "_request", side_effect=fake_request):
                result = lmstudio.LMStudio(settings).interpret(
                    "髪だけ自然に整えて", workflows, None,
                )
            self.assertEqual(result, answer)
            self.assertEqual(
                [route for route, _ in calls],
                ["/v1/chat/completions", "/api/v1/models/unload"],
            )
            return calls[0][1]

        new = one("preserve_edit_v1", self.i2i)
        old = one("legacy", self.i2i)
        new_system = new["messages"][0]["content"]
        old_system = old["messages"][0]["content"]
        self.assertIn("conservative image-edit prompt designer", new_system)
        self.assertNotIn("conservative image-edit prompt designer", old_system)
        self.assertEqual(new["response_format"], old["response_format"])
        self.assertEqual(new["temperature"], old["temperature"])
        self.assertEqual(new["max_tokens"], old["max_tokens"])
        self.assertIn("Edit strength hint: balanced", new["messages"][1]["content"])
        self.assertIn("Mask present: no", new["messages"][1]["content"])
        self.assertNotIn("Edit strength hint:", old["messages"][1]["content"])
        self.assertNotIn("Mask present:", old["messages"][1]["content"])
        masked = one("preserve_edit_v1", self.inpaint)
        self.assertIn("Mask present: yes", masked["messages"][1]["content"])
        self.assertIn("INPAINT-SPECIFIC", masked["messages"][0]["content"])

    def test_core_passes_effective_host_denoise_without_changing_config(self):
        actual_settings = []
        class FakeLM:
            def __init__(self, settings):
                actual_settings.append(settings)
            def interpret(self, text, workflows, image, progress=None):
                return {
                    "workflow_id": next(iter(workflows)),
                    "parameters": {"positive_prompt": "original hairstyle, better folds"},
                }

        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "source.png"
            mask = Path(directory) / "mask.png"
            image.write_bytes(b"data")
            mask.write_bytes(b"data")
            with patch.object(lmstudio, "LMStudio", FakeLM):
                first = core.execute(
                    self.config, ROOT / "config.example.json", "布だけ直す",
                    image=image, selected_workflow="wai_i2i_basic",
                    dry_run=True, overrides={"denoise": 0.38},
                )
                second = core.execute(
                    self.config, ROOT / "config.example.json", "指だけ直す",
                    image=image, mask_image=mask,
                    selected_workflow="wai_inpaint_basic", dry_run=True,
                )
        self.assertEqual(first["parameters"]["denoise"], 0.38)
        self.assertEqual(actual_settings[0]["_edit_denoise"], 0.38)
        self.assertEqual(actual_settings[1]["_edit_denoise"], 0.65)
        self.assertEqual(second["parameters"]["denoise"], 0.65)
        self.assertNotIn("_edit_denoise", self.config["llm"])

    def test_gui_migrates_i2i_setting_without_overwriting_user_model(self):
        cfg = copy.deepcopy(self.config)
        cfg["llm"].pop("i2i_prompt_profile")
        cfg["llm"]["model"] = "saved-model-key"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps(cfg), encoding="utf-8")
            with patch.object(gui, "CONFIG", path):
                migrated = gui.bootstrap_config()
        self.assertEqual(migrated["llm"]["i2i_prompt_profile"], "preserve_edit_v1")
        self.assertEqual(migrated["llm"]["model"], "saved-model-key")

    def test_invalid_i2i_profile_rejected_before_workflow_io(self):
        cfg = copy.deepcopy(self.config)
        cfg["llm"]["i2i_prompt_profile"] = "invented"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps(cfg), encoding="utf-8")
            with self.assertRaisesRegex(core.OrchestratorError, "i2i_prompt_profile"):
                core.load_config(path)


class SavedHistoryPromptTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = HistoryStore(Path(self.temp.name))
        self.output = self.store.outputs / "out.png"
        self.output.write_bytes(b"dummy output")
        self.params = {
            "positive_prompt": "1girl, same red dress, improved hair",
            "negative_prompt": "worst quality, bad anatomy",
            "denoise": 0.53, "seed": 9786, "steps": 28, "cfg": 5.5,
        }

    def new_entry(self, prompt_id, profile="preserve_edit_v1"):
        return self.store.record(
            prompt_id=prompt_id, workflow_id="wai_i2i_basic",
            kind="i2i", request_text=f"日本語修正指示 {prompt_id}",
            parameters=dict(self.params), images=[self.output],
            prompt_profile=profile,
        )

    def test_literal_positive_negative_available_after_reopening(self):
        saved = self.new_entry("i2i-one")
        reopened = HistoryStore(Path(self.temp.name)).get(saved.id)
        info = gui.history_prompt_details(reopened)
        self.assertEqual(info["positive_prompt"], self.params["positive_prompt"])
        self.assertEqual(info["negative_prompt"], self.params["negative_prompt"])
        self.assertEqual(info["profile"], "preserve_edit_v1")
        self.assertEqual(info["request_text"], "日本語修正指示 i2i-one")
        self.assertEqual(info["denoise"], 0.53)
        self.assertEqual(info["seed"], 9786)

    def test_history_selection_uses_selected_not_latest_run(self):
        first = self.new_entry("first", "legacy")
        self.params["positive_prompt"] = "long hair, orange sky"
        second = self.new_entry("second", "preserve_edit_v1")

        class FakeApp:
            latest_prompt_plan = {"parameters": {"positive_prompt": "LATEST WRONG"}}
            def __init__(self, selected):
                self.selected = selected
                self.calls = []
            def _one_history(self):
                return self.selected
            def _open_prompt_details(self, details, *, from_history):
                self.calls.append((details, from_history))

        fake = FakeApp(first)
        gui.Application._show_selected_history_prompt(fake)
        self.assertEqual(fake.calls[0][0]["positive_prompt"],
                         "1girl, same red dress, improved hair")
        self.assertEqual(fake.calls[0][0]["profile"], "legacy")
        self.assertTrue(fake.calls[0][1])
        fake.selected = second
        gui.Application._show_selected_history_prompt(fake)
        self.assertEqual(fake.calls[1][0]["positive_prompt"], "long hair, orange sky")
        self.assertEqual(fake.calls[1][0]["profile"], "preserve_edit_v1")

    def test_legacy_import_has_no_invented_prompts(self):
        other = self.store.outputs / "old.png"
        other.write_bytes(b"old")
        self.store.import_legacy_outputs()
        entries = self.store.list_entries()
        old = next(entry for entry in entries if entry.legacy)
        self.assertIsNone(gui.history_prompt_details(old))
        self.assertIsNone(old.prompt_profile)

    def test_missing_negative_prompt_is_not_invented(self):
        entry = self.store.record(
            prompt_id="missing-neg", workflow_id="wai_i2i_basic",
            kind="i2i", request_text="edit",
            parameters={"positive_prompt": "1girl"}, images=[self.output],
        )
        info = gui.history_prompt_details(entry)
        self.assertEqual(info["positive_prompt"], "1girl")
        self.assertIsNone(info["negative_prompt"])
        self.assertIsNone(info["profile"])

    def test_existing_database_without_profile_is_migrated_losslessly(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            db_folder = root / "data"
            db_folder.mkdir()
            with sqlite3.connect(db_folder / "history.sqlite3") as con:
                con.execute("""CREATE TABLE generations (
                    id TEXT PRIMARY KEY, created_at TEXT NOT NULL,
                    prompt_id TEXT NOT NULL UNIQUE, workflow_id TEXT NOT NULL,
                    kind TEXT NOT NULL, request_text TEXT NOT NULL,
                    parameters_json TEXT NOT NULL, images_json TEXT NOT NULL,
                    reference_file TEXT, legacy INTEGER NOT NULL DEFAULT 0
                )""")
                con.execute(
                    "INSERT INTO generations VALUES (?,?,?,?,?,?,?,?,?,?)",
                    ("old", "2026-10-01T00:00:00+00:00", "old",
                     "wai_i2i_basic", "i2i", "元の指示",
                     json.dumps(self.params), json.dumps(["old.png"]), None, 0),
                )
            migrated = HistoryStore(root).get("old")
            self.assertIsNone(migrated.prompt_profile)
            self.assertEqual(migrated.parameters, self.params)
            self.assertEqual(gui.history_prompt_details(migrated)["positive_prompt"],
                             self.params["positive_prompt"])


if __name__ == "__main__":
    unittest.main()
