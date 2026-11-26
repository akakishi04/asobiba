"""Regression tests for the embedded workspace and mode settings."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from comfy_orchestrator import core, gui
from comfy_orchestrator.long_video import LongVideoStore, restore_project_plan, edit_project, project_generation_inputs
from comfy_orchestrator.jobs import JobJournal
from comfy_orchestrator.mode_settings import MODE_FIELDS, ModeSettings
from comfy_orchestrator.project_ui import ProjectDraft, ProjectAction, ProjectWorkspace


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


    def completed_project(self):
        folder = self.store.folder(self.manifest["run_id"])
        self.manifest["first_parameters"] = {**self.params, "positive_prompt": "Scene. One."}
        for i in range(len(self.cuts)):
            file = folder / f"segment_{i:03d}" / "clip.mp4"
            file.parent.mkdir()
            file.write_bytes(f"clip{i}".encode())
            self.manifest["segments"].append({
                "file": file.relative_to(folder).as_posix(),
                "parameters": {**self.params, "seed": self.params["seed"] + i},
            })
        self.manifest["state"] = "completed"
        self.store.save(self.manifest)

    def test_left_settings_change_invalidates_every_clip_and_keeps_cut_lengths(self):
        self.completed_project()
        journal = JobJournal(self.root / "jobs")
        live = {**self.params, "width": 480, "height": 864, "frames": 362,
                "seed": 1234}
        revised = edit_project(self.store, self.manifest, journal, self.plan, self.cuts,
                               overrides=live, source=self.source, regenerate_from=1)
        self.assertEqual(revised["changed_from"], 0)
        self.assertEqual(revised["segments"], [])
        self.assertEqual(revised["cut_frames"], self.cuts)
        self.assertEqual(revised["plan"], self.manifest["plan"])
        self.assertEqual(revised["overrides"]["width"], 480)
        self.assertEqual(revised["overrides"]["height"], 864)
        self.assertEqual(revised["overrides"]["frames"], 124)
        self.assertEqual(revised["cut_seeds"], [1234, 1235, 1236])
        self.assertEqual(self.store.load(self.store.folder(self.manifest["run_id"]) / "manifest.json"),
                         self.manifest)

    def test_same_settings_and_same_image_content_preserve_existing_cuts(self):
        self.completed_project()
        journal = JobJournal(self.root / "jobs")
        duplicate = self.root / "copy.png"
        duplicate.write_bytes(self.source.read_bytes())
        same = edit_project(self.store, self.manifest, journal, self.plan, self.cuts,
                            overrides={**self.params, "frames": 362}, source=duplicate)
        self.assertEqual(same["run_id"], self.manifest["run_id"])
        revised_plan = {**self.plan, "segments": ["One.", "New.", "Three."]}
        revised = edit_project(self.store, self.manifest, journal, revised_plan, self.cuts,
                               overrides=self.params, source=duplicate)
        self.assertEqual(revised["changed_from"], 1)
        self.assertEqual(len(revised["segments"]), 1)

    def test_reference_change_invalidates_all_and_snapshots_new_source(self):
        self.completed_project()
        journal = JobJournal(self.root / "jobs")
        other = self.root / "other.png"
        other.write_bytes(b"new reference")
        revised = edit_project(self.store, self.manifest, journal, self.plan, self.cuts,
                               overrides=self.params, source=other)
        self.assertEqual(revised["changed_from"], 0)
        self.assertEqual(revised["segments"], [])
        self.assertEqual(self.store.asset(revised, revised["source"]).read_bytes(), b"new reference")
        other.unlink()
        self.assertEqual(self.store.asset(revised, revised["source"]).read_bytes(), b"new reference")
        self.assertEqual(self.store.asset(self.manifest, self.manifest["source"]).read_bytes(), b"source")

    def test_gui_generation_captures_left_settings_but_join_does_not(self):
        app = SimpleNamespace(
            working=False, character_analysis_running=False, reference_image=Var(str(self.source)),
            h3_connection=Var(gui.connection_label(12)),
            _h3_overrides=Mock(return_value={**self.params, "width": 480, "height": 864}),
            long_video_store=self.store, _save_settings=Mock(return_value=True),
            _project_config=Mock(return_value={"comfyui": {"base_url": "http://localhost:8188"}}),
            use_prompt_cache=Var(False), prompt_cache=Mock(), seed=Var("11"),
            _run_project_action=Mock(),
        )
        generate = ProjectAction("generate_join", self.plan, self.cuts)
        gui.Application._project_action(app, self.manifest, generate)
        self.assertEqual(app._run_project_action.call_args.kwargs["overrides"]["width"], 480)
        self.assertEqual(app._run_project_action.call_args.kwargs["overrides"]["height"], 864)
        self.assertEqual(app._run_project_action.call_args.kwargs["overlap_frames"], 12)
        self.assertEqual(app._run_project_action.call_args.kwargs["source"],
                         self.store.asset(self.manifest, self.manifest["source"]))
        app._h3_overrides.reset_mock()
        app._save_settings.reset_mock()
        gui.Application._project_action(app, self.manifest, ProjectAction("join", self.plan, self.cuts))
        app._h3_overrides.assert_not_called()
        app._save_settings.assert_not_called()
        self.assertIsNone(app._run_project_action.call_args.kwargs["overrides"])
        self.assertIsNone(app._run_project_action.call_args.kwargs["overlap_frames"])

    def test_connection_selection_reuses_first_clip_and_seed_in_both_directions(self):
        self.completed_project()
        journal = JobJournal(self.root / "jobs")
        self.assertEqual(gui.connection_frames(gui.connection_label(0)), 0)
        self.assertEqual(gui.connection_frames(gui.connection_label(12)), 12)
        self.assertEqual(gui.connection_label(None), gui.connection_label(22))
        self.assertEqual(gui.connection_frames(gui.connection_label(22)), 22)
        with self.assertRaises(core.OrchestratorError):
            gui.connection_frames("invalid")
        app = SimpleNamespace(
            working=False, character_analysis_running=False, reference_image=Var(str(self.source)),
            h3_connection=Var(gui.connection_label(12)), _h3_overrides=Mock(return_value=self.params),
            long_video_store=self.store, _save_settings=Mock(return_value=True),
            _project_config=Mock(return_value={"comfyui": {"base_url": self.manifest["backend"]}}),
            use_prompt_cache=Var(False), prompt_cache=Mock(), seed=Var("11"), _run_project_action=Mock(),
        )
        action = ProjectAction("generate_join", self.plan, self.cuts)
        with patch.object(gui.messagebox, "askyesno", return_value=False) as ask:
            gui.Application._project_action(app, self.manifest, action)
            self.assertIn("カット2以降", ask.call_args.args[1])
            app._run_project_action.assert_not_called()
        with patch.object(gui.messagebox, "askyesno", return_value=True):
            gui.Application._project_action(app, self.manifest, action)
        kwargs = app._run_project_action.call_args.kwargs
        self.assertEqual(kwargs["overlap_frames"], 12)
        revised = edit_project(self.store, self.manifest, journal, self.plan, self.cuts, **kwargs)
        self.assertEqual(revised["changed_from"], 1)
        self.assertEqual(len(revised["segments"]), 1)
        self.assertEqual(revised["cut_seeds"], [11, 12, 13])
        self.assertEqual(revised["overlap_frames"], 12)
        back = edit_project(self.store, revised, journal, self.plan, self.cuts,
                            overlap_frames=0, overrides=self.params, source=self.source)
        self.assertEqual(back["changed_from"], 1)
        self.assertEqual(len(back["segments"]), 1)
        self.assertEqual(back["cut_seeds"], revised["cut_seeds"])
        self.assertNotIn("overlap_frames", back)

    def test_primary_button_dispatches_to_current_plan_only_in_continuous_mode(self):
        app = SimpleNamespace(working=False, generation_mode=Var("continuous"),
                              project_workspace=SimpleNamespace(draft=object(), _accept=Mock()),
                              _start=Mock())
        gui.Application._run_primary(app)
        app.project_workspace._accept.assert_called_once_with("generate_join")
        app._start.assert_not_called()
        app.project_workspace.draft = None
        gui.Application._run_primary(app)
        app._start.assert_called_once_with(False)
        app._start.reset_mock()
        app.generation_mode.set("image")
        gui.Application._run_primary(app)
        app._start.assert_called_once_with(False)

    def test_project_menu_states_match_available_clips(self):
        draft = ProjectDraft(self.manifest)
        fake = SimpleNamespace(draft=draft, enabled=True, _missing_clips=set())
        self.assertTrue(ProjectWorkspace.available_actions(fake)["generate_join"])
        self.assertFalse(ProjectWorkspace.available_actions(fake)["join"])
        self.manifest["segments"] = [{}, {}, {}]
        self.assertTrue(ProjectWorkspace.available_actions(fake)["join"])
        draft.parts[1] = "changed"
        self.assertFalse(ProjectWorkspace.available_actions(fake)["join"])
        fake.enabled = False
        self.assertFalse(any(ProjectWorkspace.available_actions(fake).values()))


if __name__ == "__main__":
    unittest.main()
