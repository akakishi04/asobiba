"""Regression checks for the extracted module boundaries and compatibility API."""
import ast
import unittest
from pathlib import Path

from comfy_orchestrator import long_video, long_video_plan, project_store, video_media
from comfy_orchestrator import prompt_edit, prompt_review
from comfy_orchestrator import app_config, generation_form, history_presentation, gui
from comfy_orchestrator import output_views, settings_ui, prompt_viewer
from comfy_orchestrator.parameters import OrchestratorError


class ModuleBoundariesTests(unittest.TestCase):
    def test_long_video_compatibility_exports_have_one_implementation(self):
        for module, names in (
            (long_video_plan, ("LongVideoPaused", "segment_plan", "manifest_windows", "manifest_schedule",
                               "project_cut_lengths", "first_changed_cut", "connection_changed_from",
                               "planned_segment_parameters", "validate_structured_timing")),
            (project_store, ("LongVideoStore", "edit_project", "restore_project_plan", "project_generation_inputs")),
            (video_media, ("FFmpeg",)),
        ):
            for name in names:
                self.assertIs(getattr(long_video, name), getattr(module, name), name)
        self.assertTrue(issubclass(long_video.LongVideoPaused, OrchestratorError))

    def test_prompt_review_compatibility_exports_share_cache_and_token_rules(self):
        for name in ("TranslationCache", "protect", "restore", "TOKEN", "prepare_plan_review"):
            self.assertIs(getattr(prompt_edit, name), getattr(prompt_review, name), name)

    def test_gui_helpers_are_the_same_pure_functions(self):
        for name in ("resolution_preset_label", "resolve_generation_workflow", "parameter_visibility",
                     "reference_visibility", "image_aware_overrides", "connection_frames"):
            self.assertIs(getattr(gui, name), getattr(generation_form, name))
        for name in ("history_request_text", "history_prompt_details"):
            self.assertIs(getattr(gui, name), getattr(history_presentation, name))

    def test_generation_parameter_builders_work_without_tk(self):
        from comfy_orchestrator import core
        self.assertEqual(generation_form.common_overrides(
            {}, None, width="768", height="1024", steps="20", cfg="5", seed="9"),
            {"width": 768, "height": 1024, "steps": 20, "cfg": 5.0, "seed": 9})
        self.assertEqual(generation_form.h3_overrides(
            size="480 × 864", duration="約5秒 (124f)", steps="20", seed="", choices={}),
            {"width": 480, "height": 864, "frames": 124, "fps": 24, "steps": 20})
        fast = generation_form.qwen_overrides(
            core.QWEN_LIGHTNING_ID, width="768", height="768", steps="unused", cfg="unused", seed="7")
        self.assertEqual((fast["steps"], fast["cfg"], fast["seed"]), (4, 1, 7))

    def test_history_action_policy_does_not_need_widgets(self):
        import tempfile
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as folder:
            image = Path(folder) / "result.png"
            image.write_bytes(b"image")
            entry = SimpleNamespace(legacy=False, workflow_id="wai_t2i_basic", kind="t2i",
                                    first_image=image, reference_image=None, mask_image=None,
                                    pose_image=None, character_traits=None, character_analysis=None,
                                    character_references=(), prompt_profile=None, request_text="test",
                                    parameters={"positive_prompt": "a test"})
            workflows = {"wai_t2i_basic": {}}
            self.assertTrue(history_presentation.history_can_replay([entry], workflows, working=False))
            state = history_presentation.history_action_state([entry], workflows, working=False)
            self.assertTrue(state["open"] and state["restore"] and state["request"] and state["prompt"])
            self.assertTrue(state["use_as_source"])
            self.assertFalse(state["compare"] or state["character"])
            self.assertFalse(history_presentation.history_can_replay([entry], workflows, working=True))
            state = history_presentation.history_action_state([entry], workflows, working=True)
            self.assertFalse(state["restore"] or state["request"] or state["use_as_source"])

    def test_ui_views_do_not_import_application(self):
        for module in (output_views, settings_ui, prompt_viewer):
            tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    self.assertNotEqual(node.module, "gui")
                    self.assertFalse(any(alias.name in ("gui", "Application") for alias in node.names))
                if isinstance(node, ast.Import):
                    self.assertFalse(any(alias.name.endswith(".gui") for alias in node.names))

    def test_extracted_services_do_not_import_gui_or_long_video_runner(self):
        for module in (long_video_plan, project_store, video_media, prompt_review,
                       generation_form, history_presentation, app_config):
            syntax = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
            for node in ast.walk(syntax):
                if isinstance(node, ast.ImportFrom):
                    if node.level:
                        self.assertNotIn(node.module, ("gui", "long_video", "project_ui", "prompt_edit"))
                        self.assertFalse(any(alias.name in ("gui", "long_video", "project_ui", "prompt_edit")
                                             for alias in node.names))
                elif isinstance(node, ast.Import):
                    self.assertFalse(any(alias.name.startswith("tkinter") for alias in node.names))


if __name__ == "__main__":
    unittest.main()
