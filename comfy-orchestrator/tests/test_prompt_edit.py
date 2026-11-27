"""Japanese review/edit is independent of video generation and project revisions."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from comfy_orchestrator import core, h3_prompt as hp, lmstudio
from comfy_orchestrator.jobs import JobJournal, JobCancellationRequested
from comfy_orchestrator.long_video import LongVideoStore, edit_project
from comfy_orchestrator.prompt_edit import TranslationCache, cut_context, edit_prompts, protect, restore
from comfy_orchestrator.project_ui import ProjectDraft, ProjectWorkspace

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config.example.json"
BACKEND = "http://localhost:8188"


def reply(value):
    return {"choices": [{"message": {"content": json.dumps(value, ensure_ascii=False)}}]}


def base(body):
    return {"integrated_multimodal_description": body, "overall_soundscape": "Quiet rain.",
            "non_diegetic_music": "N/A"}


class PromptEditTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.config = core.load_config(CONFIG)
        self.config["llm"].update(model="test", unload_after_inference=False)
        self.config["comfyui"]["free_before_llm"] = False
        self.cache = TranslationCache(self.root / "japanese.sqlite3")
        self.source = self.root / "ref.png"
        self.source.write_bytes(b"ref")
        self.store = LongVideoStore(self.root / "projects")
        self.cuts = [72, 96, 120]
        self.params = {"width": 864, "height": 480, "fps": 24, "frames": 124,
                       "steps": 8, "seed": 11, "h3_model": "w4a8", "h3_turbo": "turbo8"}
        self.plan = {"common": "Keep the pink umbrella.",
                     "segments": ["She holds the umbrella.", "She closes it.", "She walks."]}
        self.catalog = [{"key": "test", "capabilities": {"vision": False},
                         "loaded_instances": [{"id": "instance"}]}]

    def project(self, plan=None, complete=False):
        manifest = self.store.create(BACKEND, "傘を閉じて歩く", self.source, self.params,
                                     sum(self.cuts)/24, prompt_plan=plan or self.plan,
                                     cut_frames=self.cuts, overlap_frames=22, draft=True)
        if complete:
            folder = self.store.folder(manifest["run_id"])
            manifest["first_parameters"] = {**self.params, "positive_prompt": "Actual first prompt."}
            for i in range(len(self.cuts)):
                clip = folder / f"clip{i}.mp4"
                clip.write_bytes(b"clip")
                manifest["segments"].append({"file": clip.name,
                    "parameters": {**self.params, "seed": 11+i, "positive_prompt": f"Executed prompt {i+1}."}})
            self.store.save(manifest)
        return manifest

    def run_edit(self, manifest, plan, operation, responder, index=1, **kw):
        with patch.object(lmstudio, "list_models", return_value=self.catalog) as load, \
                patch.object(lmstudio, "_request", side_effect=responder) as req, \
                patch.object(core, "execute_saved") as generate:
            result = edit_prompts(self.config, manifest, plan, self.cuts, index, operation,
                                  self.cache, **kw)
            generate.assert_not_called()
        return result, load, req

    def test_translation_protected_tokens_roundtrip_and_validation(self):
        raw = '[Shot 1] <Subject 1> (S1) says <d>[English] Go!</d>. [Shot 2] At 00:02.500, "OPEN" appears.'
        masked, tokens = protect(raw)
        self.assertNotIn("Go!", masked)
        self.assertEqual(restore(masked, tokens), raw)
        with self.assertRaises(core.OrchestratorError):
            restore(masked.replace("__H3KEEP_0000__", ""), tokens)
        with self.assertRaises(core.OrchestratorError):
            restore(masked + "__H3KEEP_0000__", tokens)

    def test_translation_cache_only_review_preserves_exact_plan_and_persisted_clips(self):
        manifest = self.project(complete=True)
        before = copy.deepcopy(manifest)
        def response(settings, route, payload):
            self.assertEqual(route, "/v1/chat/completions")
            self.assertEqual(payload["response_format"]["json_schema"]["name"], "h3_japanese_review")
            return reply({"text": "傘の動きと外見を維持する。"})
        result, load, req = self.run_edit(manifest, self.plan, "translate", response)
        self.assertEqual(result["before"], self.plan)
        self.assertEqual(result["after"], self.plan)
        self.assertEqual(req.call_count, 2)
        self.assertEqual(manifest, before)
        self.cache = TranslationCache(self.root / "japanese.sqlite3")
        again, load, req = self.run_edit(manifest, self.plan, "translate", response)
        self.assertEqual(again, result)
        load.assert_not_called()
        req.assert_not_called()
        self.assertEqual(ProjectDraft(manifest).valid_prefix(), 3)
        self.assertIsNone(self.cache.get("cut", "She closes a different umbrella.", False))

    def test_native_translation_disables_reasoning_and_bounds_short_output(self):
        self.catalog[0]["capabilities"]["reasoning"] = {
            "allowed_options": ["off", "on"], "default": "on"}
        manifest = self.project(complete=True)
        before = copy.deepcopy(manifest)
        def response(settings, route, payload):
            self.assertEqual(route, "/api/v1/chat")
            self.assertEqual(payload["model"], "instance")
            self.assertEqual(payload["reasoning"], "off")
            self.assertFalse(payload["store"])
            self.assertFalse(payload["stream"])
            self.assertLess(payload["max_output_tokens"], 512)
            self.assertEqual(payload["temperature"], 0)
            self.assertNotIn("response_format", payload)
            self.assertIn("Required JSON schema", payload["system_prompt"])
            self.assertIn("Translate directly", payload["system_prompt"])
            self.assertIn("text", json.loads(payload["input"]))
            return {"output": [{"type": "message", "content": json.dumps({"text": "傘を維持する。"})}],
                    "stats": {"reasoning_output_tokens": 0}}
        result, _, req = self.run_edit(manifest, self.plan, "translate", response)
        self.assertEqual(req.call_count, 2)
        self.assertEqual(result["after"], self.plan)
        self.assertEqual(manifest, before)

    def test_empty_final_answer_is_not_retried_or_saved(self):
        manifest = self.project()
        def response(settings, route, payload):
            self.assertEqual(route, "/v1/chat/completions")
            self.assertLess(payload["max_tokens"], 512)
            return {"choices": [{"message": {"content": "", "reasoning_content": "Thinking..."},
                                 "finish_reason": "length"}]}
        with patch.object(lmstudio, "list_models", return_value=self.catalog), \
                patch.object(lmstudio, "_request", side_effect=response) as req:
            with self.assertRaisesRegex(core.OrchestratorError, "最終回答が空"):
                edit_prompts(self.config, manifest, self.plan, self.cuts, 1, "translate", self.cache)
            req.assert_called_once()
        self.assertIsNone(self.cache.get("common", self.plan["common"], False))
        self.assertEqual(manifest["prompt_plan"], self.plan)

    def test_native_reasoning_output_never_used_as_translation(self):
        self.catalog[0]["capabilities"]["reasoning"] = {"allowed_options": ["off", "on"]}
        manifest = self.project()
        with patch.object(lmstudio, "list_models", return_value=self.catalog), \
                patch.object(lmstudio, "_request", return_value={
                    "output": [{"type": "reasoning", "content": '{"text":"推論内の訳"}'}],
                    "stats": {"reasoning_output_tokens": 1927}}) as req:
            with self.assertRaisesRegex(core.OrchestratorError, "最終回答が空"):
                edit_prompts(self.config, manifest, self.plan, self.cuts, 1, "translate", self.cache)
            req.assert_called_once()
        self.assertIsNone(self.cache.get("common", self.plan["common"], False))

    def test_native_translation_and_rewrite_keep_separate_inference_policies(self):
        self.catalog[0]["capabilities"]["reasoning"] = {"allowed_options": ["off", "on"]}
        manifest = self.project()
        routes = []
        def response(settings, route, payload):
            routes.append(route)
            if route == "/v1/chat/completions":
                self.assertEqual(payload["response_format"]["json_schema"]["name"], "h3_cut_rewrite")
                self.assertEqual(payload["max_tokens"], self.config["llm"]["max_tokens"])
                self.assertNotIn("reasoning", payload)
                return reply({"text": "She closes the same pink umbrella."})
            self.assertEqual(payload["reasoning"], "off")
            return {"output": [{"type": "message", "content": json.dumps({"text": "同じ傘を閉じる。"})}]}
        result, _, _ = self.run_edit(manifest, self.plan, "regenerate", response)
        self.assertEqual(routes, ["/v1/chat/completions", "/api/v1/chat", "/api/v1/chat"])
        self.assertEqual(result["after"]["segments"][1], "She closes the same pink umbrella.")

    def test_rewrite_uses_valid_executed_previous_prompt_and_changes_only_current(self):
        manifest = self.project(complete=True)
        before = copy.deepcopy(manifest)
        captured = []
        def response(settings, route, payload):
            name = payload["response_format"]["json_schema"]["name"]
            if name == "h3_cut_rewrite":
                captured.append(json.loads(payload["messages"][1]["content"]))
                return reply({"text": "She slides the runner down the same umbrella shaft."})
            return reply({"text": "傘を閉じる。"})
        result, load, req = self.run_edit(manifest, self.plan, "regenerate", response,
                                          instruction="同じ傘を保持")
        self.assertEqual(captured[0]["previous_cut_prompt"], "Executed prompt 1.")
        self.assertEqual(captured[0]["previous_prompt_source"], "executed_prompt")
        self.assertEqual(captured[0]["next_cut_prompt"], "She walks.")
        self.assertEqual(captured[0]["retained_frames"], 96)
        self.assertEqual(captured[0]["repair_instruction"], "同じ傘を保持")
        self.assertEqual(result["after"]["common"], self.plan["common"])
        self.assertEqual(result["after"]["segments"][::2], self.plan["segments"][::2])
        self.assertEqual(manifest, before)
        revised = edit_project(self.store, manifest, JobJournal(self.root / "jobs"),
                               result["after"], self.cuts)
        self.assertEqual(revised["changed_from"], 1)
        self.assertEqual(len(revised["segments"]), 1)
        self.assertEqual(revised["cut_seeds"], [11, 12, 13])
        changed = copy.deepcopy(self.plan)
        changed["segments"][0] = "Edited preceding plan."
        context = cut_context(manifest, changed, self.cuts, 1)
        self.assertEqual(context["previous_cut_prompt"], "Edited preceding plan.")
        self.assertEqual(context["previous_prompt_source"], "planned")

    def test_edited_japanese_only_translates_changed_field_and_reviews_new_english(self):
        manifest = self.project()
        self.cache.put("common", self.plan["common"], False, "ピンクの傘を維持。")
        calls = []
        def response(settings, route, payload):
            name = payload["response_format"]["json_schema"]["name"]
            calls.append(name)
            if name == "h3_cut_from_japanese":
                body = json.loads(payload["messages"][1]["content"])
                self.assertEqual(body["edited_japanese"], "傘をゆっくり閉じる。")
                return reply({"text": "She closes the umbrella slowly."})
            if name == "h3_japanese_review":
                return reply({"text": "彼女が傘をゆっくりと閉じる。"})
            raise AssertionError(name)
        result, _, _ = self.run_edit(manifest, self.plan, "apply", response,
                                      japanese={"cut": "傘をゆっくり閉じる。"})
        self.assertEqual(calls, ["h3_cut_from_japanese", "h3_japanese_review"])
        self.assertEqual(result["after"]["segments"][1], "She closes the umbrella slowly.")
        self.assertEqual(result["japanese"]["cut"], "彼女が傘をゆっくりと閉じる。")
        self.assertEqual(result["after"]["common"], self.plan["common"])
        self.assertEqual(manifest["prompt_plan"], self.plan)

    def test_official_rewrite_preserves_format_and_validates_local_time(self):
        plan = {"format": hp.FORMAT, "common": "",
                "segments": [hp.section_text(base("[Shot 1] She holds the pink umbrella."), False),
                             hp.section_text(base("[Shot 1] She closes the umbrella."), False),
                             hp.section_text(base("[Shot 1] She walks."), False)]}
        manifest = self.project(plan)
        calls = []
        def response(settings, route, payload):
            name = payload["response_format"]["json_schema"]["name"]
            calls.append(name)
            if name == "h3_cut_rewrite":
                # 4 seconds is exactly the retained duration, so the first
                # response is invalid and receives the bounded repair.
                if calls.count(name) == 1:
                    return reply(base("[Shot 1] She moves. [Shot 2] At 00:04.000, she stops."))
                return reply(base("[Shot 1] She closes the same pink umbrella."))
            masked = json.loads(payload["messages"][1]["content"])
            return reply({key: "日本語 " + " ".join(__import__("re").findall(r"__H3KEEP_\d{4}__", text))
                          for key, text in masked.items()})
        result, _, _ = self.run_edit(manifest, plan, "regenerate", response)
        self.assertEqual(calls.count("h3_cut_rewrite"), 2)
        self.assertEqual(result["after"]["format"], hp.FORMAT)
        self.assertIn("same pink umbrella", result["after"]["segments"][1])
        self.assertIn("【映像・動作・カメラ・台詞】", result["japanese"]["cut"])
        self.assertEqual(hp.parse_sections(result["after"]["segments"][1])[1], False)
        self.assertEqual(result["after"]["segments"][::2], plan["segments"][::2])

    def test_failed_back_translation_does_not_publish_edited_plan(self):
        manifest = self.project()
        before = copy.deepcopy(manifest)
        def response(settings, route, payload):
            if payload["response_format"]["json_schema"]["name"] == "h3_cut_from_japanese":
                return reply({"text": "A new cut."})
            return reply({"bad": "invalid"})
        with self.assertRaises(core.OrchestratorError):
            self.run_edit(manifest, self.plan, "apply", response, japanese={"cut": "新しいカット"})
        self.assertEqual(manifest, before)

    def test_unapplied_japanese_cannot_replace_english_plan(self):
        manifest = self.project()
        draft = ProjectDraft(manifest)
        draft.current = 1
        fake = SimpleNamespace(draft=draft, duration=Mock(), common=Mock(), cut_prompt=Mock(),
                               _display_language="日本語",
                               _ja_baseline={"common": "共通条件", "cut": "カット2"},
                               _edited_japanese=lambda: {"cut": "変更した日本語"})
        fake.duration.get.return_value = "4"
        fake.common.get.return_value = "共通条件"
        fake.cut_prompt.get.return_value = "変更した日本語"
        self.assertFalse(ProjectWorkspace._read(fake, strict=False))
        self.assertTrue(ProjectWorkspace._read(fake, allow_japanese_edits=True))
        self.assertEqual(draft.plan(), self.plan)

    def test_worker_result_guard_and_only_selected_draft_changes(self):
        manifest = self.project(complete=True)
        draft = ProjectDraft(manifest)
        draft.current = 1
        fake = SimpleNamespace(draft=draft, _load_cut=Mock(), _refresh_rows=Mock())
        after = copy.deepcopy(self.plan)
        after["segments"][1] = "Rewritten."
        result = {"before": self.plan, "after": after, "index": 1}
        self.assertFalse(ProjectWorkspace.accept_prompt_result(fake, "different", self.cuts, result))
        self.assertEqual(draft.plan(), self.plan)
        self.assertTrue(ProjectWorkspace.accept_prompt_result(fake, manifest["run_id"], self.cuts, result))
        self.assertEqual(draft.plan(), after)
        self.assertEqual(draft.valid_prefix(), 1)
        self.assertEqual(manifest["prompt_plan"], self.plan)


if __name__ == "__main__":
    unittest.main()
