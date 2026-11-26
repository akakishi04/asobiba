"""Regression tests for the embedded workspace and mode settings."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from comfy_orchestrator import core
from comfy_orchestrator.long_video import LongVideoStore, restore_project_plan
from comfy_orchestrator.mode_settings import MODE_FIELDS, ModeSettings
from comfy_orchestrator.project_ui import ProjectDraft


class Var:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class ModeSettingsTests(unittest.TestCase):
    def test_modes_preserve_independent_generation_parameters(self):
        owner = SimpleNamespace(**{key: Var("original") for fields in MODE_FIELDS.values() for key in fields})
        owner.reference_image = Var("ref.png")
        bank = ModeSettings(owner, "image")
        owner.seed.set("17")
        owner.steps.set("25")
        bank.switch(owner, "video")
        self.assertEqual(owner.seed.get(), "original")
        owner.h3_model.set("video-model")
        owner.seed.set("18")
        bank.switch(owner, "continuous")
        owner.h3_model.set("long-model")
        owner.seed.set("19")
        bank.switch(owner, "video")
        self.assertEqual(owner.h3_model.get(), "video-model")
        self.assertEqual(owner.seed.get(), "18")
        bank.switch(owner, "image")
        self.assertEqual(owner.steps.get(), "25")
        self.assertEqual(owner.seed.get(), "17")
        self.assertEqual(owner.reference_image.get(), "ref.png")
        saved = bank.snapshot(owner)
        self.assertEqual(saved["continuous"]["h3_model"], "long-model")
        self.assertEqual(saved["continuous"]["seed"], "19")
        restored = ModeSettings(owner, "continuous", saved)
        self.assertEqual(owner.seed.get(), "19")
        self.assertEqual(owner.h3_model.get(), "long-model")


class ProjectWorkspaceTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.store = LongVideoStore(self.root / "projects")
        self.source = self.root / "source.png"
        self.source.write_bytes(b"source")
        self.params = {"width": 864, "height": 480, "fps": 24, "frames": 124,
                       "steps": 8, "seed": 11, "h3_model": "w4a8", "h3_turbo": "turbo8"}
        self.plan = {"common": "Scene.", "segments": ["One.", "Two.", "Three."]}
        self.cuts = [72, 120, 192]
        self.manifest = self.store.create("http://localhost:8188", "walk", self.source,
                                         self.params, 16, prompt_plan=self.plan,
                                         cut_frames=self.cuts, draft=True)

    def test_editing_does_not_mutate_manifest_and_invalidates_only_suffix(self):
        self.manifest["segments"] = [{}, {}, {}]
        draft = ProjectDraft(self.manifest)
        self.assertEqual(draft.valid_prefix(), 3)
        draft.parts[1] = "Changed."
        self.assertTrue(draft.dirty())
        self.assertEqual(draft.changed_from(), 1)
        self.assertEqual(draft.valid_prefix(), 1)
        self.assertEqual(self.manifest["prompt_plan"]["segments"][1], "Two.")
        with self.assertRaises(core.OrchestratorError):
            draft.action("join")
        draft.current = 1
        action = draft.action("generate", regenerate=True)
        self.assertEqual(action.regenerate_from, 1)
        self.assertEqual(action.prompt_plan["segments"][1], "Changed.")
        draft.common = "New scene."
        self.assertEqual(draft.valid_prefix(), 0)

    def test_plan_recovery_preserves_explicit_seeds_without_old_clips(self):
        entry = SimpleNamespace(parameters={
            **self.params, "long_prompt_plan": self.plan, "long_base_overrides": self.params,
            "long_cut_frames": self.cuts, "long_cut_seeds": [11, 88, 99],
            "long_seconds": 16, "long_run_id": self.manifest["run_id"],
            "long_backend": "http://localhost:8188",
        }, reference_image=self.source, request_text="walk", prompt_profile=None)
        restored = restore_project_plan(self.store, entry, "http://other:8188")
        self.assertEqual(restored["cut_seeds"], [11, 88, 99])
        self.assertEqual(restored["prompt_plan"], self.plan)
        self.assertEqual(restored["cut_frames"], self.cuts)
        self.assertEqual(restored["segments"], [])
        self.assertEqual(restored["backend"], "http://localhost:8188")
        self.assertEqual(restored["state"], "draft")
        self.assertNotEqual(restored["run_id"], self.manifest["run_id"])


if __name__ == "__main__":
    unittest.main()
