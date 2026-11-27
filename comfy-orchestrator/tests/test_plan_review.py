"""Automatic Japanese review at plan creation; no running services needed."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from comfy_orchestrator import core, h3_prompt as hp, lmstudio, prompt_edit
from comfy_orchestrator.prompt_cache import PromptCache
from comfy_orchestrator.prompt_edit import TranslationCache, TOKEN, protect
from comfy_orchestrator.timeline import generation_frames_for_cuts, plan_long_prompts

ROOT = Path(__file__).resolve().parents[1]


def reply(value):
    return {"choices": [{"message": {"content": json.dumps(value, ensure_ascii=False)}}]}


class AutomaticPlanReviewTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.config = core.load_config(ROOT / "config.example.json")
        self.config["llm"].update(model="test", h3_prompt_format=hp.FORMAT,
                                  unload_after_inference=True)
        self.config["comfyui"]["free_before_llm"] = False
        self.cache = TranslationCache(self.root / "japanese.sqlite3")
        self.plan_cache = PromptCache(self.root / "plans.sqlite3")
        self.cuts = [72, 96]
        self.frames = generation_frames_for_cuts(self.cuts)
        self.source = self.root / "ref.png"
        self.source.write_bytes(b"ref")
        self.catalog = [{"key": "test", "capabilities": {"vision": False},
                         "loaded_instances": [{"id": "instance"}]}]
        self.official = {"common": "Consistent painted linework.",
                         "segments": {
                             "cut_1": hp.default_sections(False),
                             "cut_2": {**hp.default_sections(False),
                                       "integrated_multimodal_description": "[Shot 1] She moves."},
                         }}
        self.legacy = {"common": "Same style.", "segments": ["Move.", "Rest."]}
        self.calls = []
        self.logs = []

    def plan(self, request="歩く", **kwargs):
        return plan_long_prompts(self.config, request, self.frames, sum(self.cuts)/24,
                                 cut_frames=self.cuts, image=self.source, release_comfy=False,
                                 translation_cache=self.cache, progress=self.logs.append, **kwargs)

    def request(self, settings, route, payload):
        if route == "/api/v1/models/unload":
            self.calls.append("unload")
            return {"instance_id": "instance"}
        name = payload["response_format"]["json_schema"]["name"]
        self.calls.append(name)
        if name == "h3_long_batch":
            return reply(self.official)
        if name == "continuous_video_prompt_plan":
            return reply(self.legacy)
        if name == "h3_japanese_review":
            masked = json.loads(payload["messages"][1]["content"])
            return reply({key: "訳 " + " ".join(TOKEN.findall(value))
                          for key, value in masked.items()})
        raise AssertionError(name)

    def test_official_review_is_in_same_loaded_session_before_unload(self):
        original = copy.deepcopy(self.official)
        with patch.object(lmstudio, "list_models", return_value=self.catalog) as load, \
                patch.object(lmstudio, "_request", side_effect=self.request):
            plan = self.plan()
        load.assert_called_once()
        self.assertEqual(self.calls, ["h3_long_batch", "h3_japanese_review",
                                      "h3_japanese_review", "h3_japanese_review", "unload"])
        self.assertEqual(self.official, original)
        self.assertEqual(plan["common"], original["common"])
        self.assertEqual(plan["segments"][1], hp.section_text(original["segments"]["cut_2"], False))
        self.assertFalse(self.cache.missing(plan))
        self.assertIn("[Shot 1]", self.cache.get("cut", plan["segments"][1], True))
        self.assertFalse(TranslationCache(self.cache.disk.database).missing(plan))

    def test_legacy_review_is_in_same_loaded_session_before_unload(self):
        self.config["llm"]["h3_prompt_format"] = hp.LEGACY
        with patch.object(lmstudio, "list_models", return_value=self.catalog) as load, \
                patch.object(lmstudio, "_request", side_effect=self.request):
            plan = self.plan()
        load.assert_called_once()
        self.assertEqual(plan, self.legacy)
        self.assertEqual(self.calls, ["continuous_video_prompt_plan", "h3_japanese_review",
                                      "h3_japanese_review", "h3_japanese_review", "unload"])
        self.assertFalse(self.cache.missing(plan))

    def test_failed_review_preserves_plan_and_cached_retry_fills_only_missing(self):
        with patch.object(lmstudio, "list_models", return_value=self.catalog) as load, \
                patch.object(lmstudio, "_request", side_effect=self.request):
            with patch.object(prompt_edit, "_translate", side_effect=[
                    "共通", core.OrchestratorError("翻訳通信失敗")]):
                plan = self.plan(prompt_cache=self.plan_cache)
            self.assertEqual(len(self.cache.missing(plan)), 2)
            self.assertTrue(any("英語計画と完了分を保持" in line for line in self.logs))
            self.assertEqual(plan["common"], self.official["common"])
            self.assertEqual(self.plan(prompt_cache=self.plan_cache), plan)
            self.assertFalse(self.cache.missing(plan))
            self.assertEqual(self.plan(prompt_cache=self.plan_cache), plan)
        self.assertEqual(load.call_count, 2)
        self.assertEqual(self.calls, ["h3_long_batch", "unload",
                                      "h3_japanese_review", "h3_japanese_review", "unload"])

    def test_empty_image_only_default_plans_need_no_llm_including_ref_first(self):
        with patch.object(lmstudio.LMStudio, "_ensure_loaded") as load:
            for reference_only in (False, True):
                plan = plan_long_prompts(self.config, "", self.frames, sum(self.cuts)/24,
                                         reference_only, cut_frames=self.cuts, image=self.source,
                                         translation_cache=self.cache)
                self.assertFalse(self.cache.missing(plan))
                for raw in plan["segments"]:
                    fields, _ = hp.parse_sections(raw)
                    ja = self.cache.get("cut", raw, True)
                    for field in fields.values():
                        _, tokens = protect(field)
                        for token in tokens:
                            self.assertIn(token, ja)
            self.config["llm"]["h3_prompt_format"] = hp.LEGACY
            legacy = self.plan("")
            self.assertFalse(self.cache.missing(legacy))
        load.assert_not_called()

    def test_cached_plan_with_complete_review_needs_no_load_or_comfy_release(self):
        with patch.object(lmstudio, "list_models", return_value=self.catalog), \
                patch.object(lmstudio, "_request", side_effect=self.request):
            plan = self.plan(prompt_cache=self.plan_cache)
        with patch.object(lmstudio.LMStudio, "_ensure_loaded") as load, \
                patch("comfy_orchestrator.model_runtime.release_comfy_before_llm") as release:
            result = plan_long_prompts(self.config, "歩く", self.frames, sum(self.cuts)/24,
                                       cut_frames=self.cuts, image=self.source,
                                       prompt_cache=self.plan_cache, translation_cache=self.cache,
                                       release_comfy=True)
        self.assertEqual(result, plan)
        load.assert_not_called()
        release.assert_not_called()

    def test_gui_passes_workspace_cache_to_new_plan(self):
        import inspect
        from comfy_orchestrator.gui import Application
        source = inspect.getsource(Application._start_long_prompt_plan)
        self.assertIn("translation_cache = self.project_workspace.translation_cache", source)
        self.assertIn("translation_cache=translation_cache", source)


if __name__ == "__main__":
    unittest.main()
