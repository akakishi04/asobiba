"""Regression checks for the extracted module boundaries and compatibility API."""
import ast
import unittest
from pathlib import Path

from comfy_orchestrator import long_video, long_video_plan, project_store, video_media
from comfy_orchestrator import prompt_edit, prompt_review
from comfy_orchestrator import app_config, generation_form, history_presentation, gui
from comfy_orchestrator import output_views, settings_ui, prompt_viewer, generation_view, task_controller
from comfy_orchestrator import prompt_inference, project_draft, project_ui, h3_prompt, lmstudio
from comfy_orchestrator import core, workflow_registry, configuration, http_api, comfy_client, ollama_client
from comfy_orchestrator import generation_runtime, model_runtime, history_refresh, result_state, preview_geometry
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

    def test_prompt_and_draft_compatibility_entry_points(self):
        self.assertIs(lmstudio.read_json_reply, prompt_inference.read_json_reply)
        self.assertIs(h3_prompt._reply, prompt_inference.request_validated)
        self.assertIs(project_ui.ProjectDraft, project_draft.ProjectDraft)
        self.assertIs(project_ui.ProjectAction, project_draft.ProjectAction)

    def test_structured_payload_does_not_change_user_or_model_parameters(self):
        messages = [{"role": "system", "content": "instructions"},
                    {"role": "user", "content": [{"type": "text", "text": "request"}]}]
        schema = {"type": "object", "properties": {}}
        payload = prompt_inference.structured_payload("instance", messages, "test", schema,
                                                      temperature=0)
        self.assertEqual(payload, {"model": "instance", "messages": messages, "stream": False,
                                  "temperature": 0,
                                  "response_format": {"type": "json_schema",
                                                      "json_schema": {"name": "test", "schema": schema}}})
        self.assertEqual(prompt_inference.read_json_reply(
            {"choices": [{"message": {"content": '{"a":1}'}}]}, "test"), {"a": 1})
        with self.assertRaises(OrchestratorError):
            prompt_inference.read_json_reply({"choices": [{"message": {"content": "[]"}}]}, "test")

    def test_core_compatibility_exports_use_owner_implementations(self):
        for name in ("compatible_workflows", "load_workflow", "render_workflow", "validate_plan",
                     "plan_schema", "validate_video_parameters", "installed_model_choices"):
            self.assertIs(getattr(core, name), getattr(workflow_registry, name))
        self.assertIs(core.load_config, configuration.load_config)
        self.assertIs(core.ComfyUI, comfy_client.ComfyUI)
        self.assertIs(core.Ollama, ollama_client.Ollama)
        self.assertIs(core.http_json, http_api.http_json)
        self.assertIs(core.APIHTTPError, http_api.APIHTTPError)

    def test_backend_and_workflow_modules_do_not_depend_on_core(self):
        for module in (workflow_registry, configuration, http_api, comfy_client, ollama_client,
                       generation_runtime, model_runtime, long_video_plan, project_store, generation_form,
                       app_config, history_presentation, settings_ui, generation_view, prompt_viewer,
                       prompt_edit, h3_prompt):
            tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    self.assertNotEqual(node.module, "core")
                    self.assertFalse(any(alias.name == "core" for alias in node.names))
                elif isinstance(node, ast.Import):
                    self.assertFalse(any(alias.name.endswith(".core") for alias in node.names))

    def test_ui_views_do_not_import_application(self):
        for module in (output_views, settings_ui, prompt_viewer, generation_view):
            tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    self.assertNotEqual(node.module, "gui")
                    self.assertFalse(any(alias.name in ("gui", "Application") for alias in node.names))
                if isinstance(node, ast.Import):
                    self.assertFalse(any(alias.name.endswith(".gui") for alias in node.names))

    def test_extracted_services_do_not_import_gui_or_long_video_runner(self):
        for module in (long_video_plan, project_store, video_media, prompt_review,
                       generation_form, history_presentation, app_config, task_controller,
                       prompt_inference, project_draft, history_refresh, result_state, preview_geometry):
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
