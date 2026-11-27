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

    def test_translate_all_skips_cached_and_duplicate_text_in_one_model_session(self):
        plan = {**self.plan, "segments": ["One.", "Two.", "One."]}
        manifest = self.project(plan, complete=True)
        before = copy.deepcopy(manifest)
        self.cache.put("common", plan["common"], False, "共通条件")
        self.config["llm"]["unload_after_inference"] = True
        translated = []
        def response(settings, route, payload):
            if route == "/api/v1/models/unload":
                self.assertEqual(payload["instance_id"], "instance")
                return {"instance_id": "instance"}
            self.assertEqual(route, "/v1/chat/completions")
            self.assertEqual(payload["response_format"]["json_schema"]["name"], "h3_japanese_review")
            text = json.loads(payload["messages"][1]["content"])["text"]
            translated.append(text)
            return reply({"text": "翻訳 " + text})
        logs = []
        result, load, req = self.run_edit(manifest, plan, "translate_all", response, progress=logs.append)
        self.assertEqual(translated, ["One.", "Two."])
        self.assertEqual(result["translated_count"], 2)
        load.assert_called_once()
        self.assertEqual([c.args[1] for c in req.call_args_list],
                         ["/v1/chat/completions", "/v1/chat/completions", "/api/v1/models/unload"])
        self.assertTrue(any("1/2: カット1" in line for line in logs))
        self.assertTrue(any("2/2: カット2" in line for line in logs))
        self.assertEqual(result["after"], plan)
        self.assertEqual(manifest, before)
        self.cache = TranslationCache(self.root / "japanese.sqlite3")
        again, load, req = self.run_edit(manifest, plan, "translate_all", response)
        self.assertEqual(again["translated_count"], 0)
        load.assert_not_called()
        req.assert_not_called()
        self.assertEqual(self.cache.get("cut", "One.", False), "翻訳 One.")
        self.assertEqual(ProjectDraft(manifest).valid_prefix(), 3)

    def test_translate_all_failure_preserves_completed_cache_and_resumes_remaining(self):
        manifest = self.project()
        attempted = []
        def response(settings, route, payload):
            source = json.loads(payload["messages"][1]["content"])["text"]
            attempted.append(source)
            if len(attempted) == 2:
                raise core.OrchestratorError("通信タイムアウト")
            return reply({"text": "訳 " + source})
        with patch.object(lmstudio, "list_models", return_value=self.catalog), \
                patch.object(lmstudio, "_request", side_effect=response):
            with self.assertRaisesRegex(core.OrchestratorError, "カット1.*1/4件完了"):
                edit_prompts(self.config, manifest, self.plan, self.cuts, 1, "translate_all", self.cache)
        self.assertEqual(self.cache.get("common", self.plan["common"], False), "訳 " + self.plan["common"])
        self.assertEqual([v[0] for v in self.cache.missing(self.plan)], ["カット1", "カット2", "カット3"])
        attempted.clear()
        def retry(settings, route, payload):
            source = json.loads(payload["messages"][1]["content"])["text"]
            attempted.append(source)
            return reply({"text": "訳 " + source})
        result, _, _ = self.run_edit(manifest, self.plan, "translate_all", retry)
        self.assertEqual(attempted, self.plan["segments"])
        self.assertEqual(result["translated_count"], 3)
        self.assertFalse(self.cache.missing(self.plan))
        self.assertEqual(manifest["prompt_plan"], self.plan)

    def test_translate_all_cancel_stops_between_items_and_leaves_previous_results(self):
        import threading
        stop = threading.Event()
        manifest = self.project()
        calls = []
        def response(settings, route, payload):
            calls.append(payload)
            if len(calls) == 2:
                stop.set()
            return reply({"text": "翻訳"})
        with patch.object(lmstudio, "list_models", return_value=self.catalog), \
                patch.object(lmstudio, "_request", side_effect=response):
            with self.assertRaises(JobCancellationRequested):
                edit_prompts(self.config, manifest, self.plan, self.cuts, 1, "translate_all",
                             self.cache, cancel_event=stop)
        self.assertEqual(len(calls), 2)
        self.assertEqual(self.cache.get("common", self.plan["common"], False), "翻訳")
        self.assertEqual(len(self.cache.missing(self.plan)), 3)
        self.assertEqual(manifest["prompt_plan"], self.plan)

    def test_translation_cache_covers_maximum_project_and_batches_disk_reads(self):
        plan = {"common": "Common.", "segments": [f"Cut {i}." for i in range(300)]}
        for label, kind, source in self.cache.missing(plan):
            self.cache.put(kind, source, False, "訳 " + source)
        self.assertEqual(self.cache.disk.stats()["entries"], 301)
        loaded = TranslationCache(self.root / "japanese.sqlite3")
        with patch.object(loaded.disk, "get_many", wraps=loaded.disk.get_many) as lookup:
            self.assertFalse(loaded.missing(plan))
            self.assertFalse(loaded.missing(plan))
            lookup.assert_called_once()
        self.assertEqual(loaded.get("cut", plan["segments"][299], False), "訳 Cut 299.")

    def test_workspace_dispatches_all_translation_without_rewriting_or_selecting_cut(self):
        manifest = self.project()
        draft = ProjectDraft(manifest)
        draft.current = 1
        fake = SimpleNamespace(enabled=True, draft=draft, on_prompt_action=Mock(),
                               _read=Mock(return_value=True), translation_cache=self.cache)
        ProjectWorkspace._prompt_action(fake, "translate_all")
        fake._read.assert_called_once_with(allow_japanese_edits=False)
        fake.on_prompt_action.assert_called_once_with(
            manifest, self.plan, self.cuts, 1, "translate_all", {}, "", self.cache)
        self.assertEqual(draft.current, 1)
        self.assertEqual(draft.plan(), self.plan)

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

    def test_batch_rewrite_uses_updated_previous_prompt_and_one_model_session(self):
        manifest = self.project(complete=True)
        before = copy.deepcopy(manifest)
        contexts, translations = [], []
        self.cache.put("common", self.plan["common"], False, "共通")
        def response(settings, route, payload):
            name = payload["response_format"]["json_schema"]["name"]
            body = json.loads(payload["messages"][1]["content"])
            if name == "h3_cut_rewrite":
                contexts.append(body)
                return reply({"text": f"Rewritten cut {body['cut']}."})
            translations.append(body["text"])
            return reply({"text": "訳 " + body["text"]})
        result, load, _ = self.run_edit(manifest, self.plan, "regenerate", response,
                                       index=2, selected_indices=(2, 1, 2), instruction="同じ傘")
        self.assertEqual([c["cut"] for c in contexts], [2, 3])
        self.assertEqual(contexts[0]["previous_cut_prompt"], "Executed prompt 1.")
        self.assertEqual(contexts[1]["previous_cut_prompt"], "Rewritten cut 2.")
        self.assertEqual(contexts[1]["previous_prompt_source"], "planned")
        self.assertTrue(all(c["repair_instruction"] == "同じ傘" for c in contexts))
        self.assertEqual(translations, ["Rewritten cut 2.", "Rewritten cut 3."])
        self.assertEqual(result["rewritten_indices"], [1, 2])
        self.assertEqual(result["after"]["segments"], [self.plan["segments"][0], *translations])
        self.assertEqual(result["after"]["common"], self.plan["common"])
        self.assertEqual(manifest, before)
        load.assert_called_once()
        draft = ProjectDraft(manifest)
        draft.select_cuts((2, 1), 2)
        fake = SimpleNamespace(draft=draft, _load_cut=Mock(), _refresh_rows=Mock())
        self.assertTrue(ProjectWorkspace.accept_prompt_result(fake, manifest["run_id"], self.cuts, result))
        self.assertEqual(draft.plan(), result["after"])
        self.assertEqual(draft.valid_prefix(), 1)

    def test_nonadjacent_batch_preserves_unselected_cut(self):
        manifest = self.project()
        self.cache.put("common", self.plan["common"], False, "共通")
        def response(settings, route, payload):
            name = payload["response_format"]["json_schema"]["name"]
            body = json.loads(payload["messages"][1]["content"])
            return reply({"text": f"Rewritten {body['cut']}."} if name == "h3_cut_rewrite" else {"text": "訳"})
        result, _, _ = self.run_edit(manifest, self.plan, "regenerate", response,
                                    index=0, selected_indices=(0, 2))
        self.assertEqual(result["after"]["segments"], ["Rewritten 1.", self.plan["segments"][1], "Rewritten 3."])

    def test_batch_rewrite_error_leaves_original_plan_unchanged(self):
        manifest = self.project()
        before = copy.deepcopy(manifest)
        original_plan = copy.deepcopy(self.plan)
        attempted = []
        def response(settings, route, payload):
            body = json.loads(payload["messages"][1]["content"])
            attempted.append(body["cut"])
            if body["cut"] == 2:
                raise core.OrchestratorError("通信失敗")
            return reply({"text": "New first cut."})
        with self.assertRaises(core.OrchestratorError):
            self.run_edit(manifest, self.plan, "regenerate", response,
                          index=0, selected_indices=(0, 1))
        self.assertIn(2, attempted)
        self.assertEqual(manifest, before)
        self.assertEqual(self.plan, original_plan)

    def test_batch_rewrite_cancel_does_not_publish_partial_plan(self):
        import threading
        manifest = self.project()
        before = copy.deepcopy(manifest)
        original_plan = copy.deepcopy(self.plan)
        stop = threading.Event()
        def response(settings, route, payload):
            stop.set()
            return reply({"text": "Rewritten."})
        with self.assertRaises(JobCancellationRequested):
            self.run_edit(manifest, self.plan, "regenerate", response,
                          index=0, selected_indices=(0, 2), cancel_event=stop)
        self.assertEqual(self.plan, original_plan)
        self.assertEqual(manifest, before)

    def test_batch_dispatch_and_worker_result_selection_guard(self):
        manifest = self.project()
        draft = ProjectDraft(manifest)
        draft.select_cuts((0, 2), 2)
        fake = SimpleNamespace(enabled=True, draft=draft, on_prompt_action=Mock(),
                               _read=Mock(return_value=True), translation_cache=self.cache,
                               _load_cut=Mock(), _refresh_rows=Mock())
        with patch("comfy_orchestrator.project_ui.simpledialog.askstring", return_value="修正"):
            ProjectWorkspace._prompt_action(fake, "regenerate")
        fake.on_prompt_action.assert_called_once_with(
            manifest, self.plan, self.cuts, 2, "regenerate", {}, "修正", self.cache,
            selected_indices=(0, 2))
        after = copy.deepcopy(self.plan)
        after["segments"][0] = "New first."
        after["segments"][2] = "New third."
        result = {"before": self.plan, "after": after, "index": 2, "rewritten_indices": [0, 2]}
        draft.select_cuts((2,), 2)
        self.assertFalse(ProjectWorkspace.accept_prompt_result(fake, manifest["run_id"], self.cuts, result))
        self.assertEqual(draft.plan(), self.plan)
        draft.select_cuts((0, 2), 2)
        after["segments"][1] = "Unexpected change."
        self.assertFalse(ProjectWorkspace.accept_prompt_result(fake, manifest["run_id"], self.cuts, result))
        self.assertEqual(draft.plan(), self.plan)

    def test_invalid_batch_targets_rejected_before_loading(self):
        manifest = self.project()
        with patch.object(lmstudio, "list_models") as load:
            for selected in ((), (-1, 1), (1, 3), (True, 1), (0, 2)):
                with self.subTest(selected=selected):
                    with self.assertRaises(core.OrchestratorError):
                        edit_prompts(self.config, manifest, self.plan, self.cuts, 1,
                                     "regenerate", self.cache, selected_indices=selected)
            load.assert_not_called()

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
