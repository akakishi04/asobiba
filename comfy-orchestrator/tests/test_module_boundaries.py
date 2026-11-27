"""Regression checks for the extracted module boundaries and compatibility API."""
import ast
import unittest
from pathlib import Path

from comfy_orchestrator import long_video, long_video_plan, project_store, video_media
from comfy_orchestrator import prompt_edit, prompt_review
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

    def test_extracted_services_do_not_import_gui_or_long_video_runner(self):
        for module in (long_video_plan, project_store, video_media, prompt_review):
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
