"""Standalone review uses a frozen, validated plan and never reinterprets on execute."""
import copy
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

from comfy_orchestrator import core, h3_prompt as hp, lmstudio, single_prompt as sp
from comfy_orchestrator.generation_controller import GenerationController
from comfy_orchestrator.jobs import JobCancellationRequested
from comfy_orchestrator.prompt_review import TranslationCache, TOKEN


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config.example.json"


class SinglePromptTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.config = core.load_config(CONFIG)
        self.config["llm"].update(model="test", unload_after_inference=True,
                                  h3_prompt_format=hp.FORMAT)
        self.config["comfyui"]["free_before_llm"] = False
        self.cancel = threading.Event()
        self.service = GenerationController(self.config, CONFIG, self.root, Mock(), None,
                                            cancel_event=self.cancel)
        self.cache = TranslationCache(self.root / "ja.sqlite3")
        self.catalog = [{"key": "test", "capabilities": {"vision": False},
                         "loaded_instances": [{"id": "instance"}]}]
        self.wf = "wai_t2i_basic"
        self.result = {"status": "dry_run", "workflow_id": self.wf,
                       "parameters": {"positive_prompt": "1girl, black hair",
                                      "negative_prompt": "blurry", "seed": 123}}

    def draft(self, result=None, **kwargs):
        result = result or self.result
        with patch.object(core, "execute", return_value=result):
            draft = sp.SinglePromptDraft.prepare(self.service, "黒髪", result["workflow_id"],
                                                 {}, **kwargs)
        self.addCleanup(draft.close)
        return draft

    def test_edited_plan_executes_saved_parameters_and_frozen_assets(self):
        source = self.root / "image.png"
        source.write_bytes(b"original")
        result = {**self.result, "workflow_id": "wai_i2i_basic"}
        draft = self.draft(result, image=source)
        source.write_bytes(b"replaced")
        draft.set_english({"positive_prompt": "silver hair", "negative_prompt": "blurry"})
        self.assertEqual(draft.assets["image"].read_bytes(), b"original")
        self.assertEqual(draft.parameters["seed"], 123)
        completed = {"status": "completed", "workflow_id": draft.workflow_id,
                     "parameters": copy.deepcopy(draft.parameters)}
        def execute_saved(*args, **kwargs):
            self.assertEqual(kwargs["reference_image"].read_bytes(), b"original")
            self.assertEqual(args[3]["positive_prompt"], "silver hair")
            self.assertEqual(args[3]["seed"], 123)
            self.assertFalse(kwargs.get("new_seed", False))
            self.assertEqual(kwargs["job_context"]["request_text"], "黒髪")
            return completed
        with patch.object(core, "execute", side_effect=AssertionError("LLM reinterpretation")) as llm, \
                patch.object(core, "execute_saved", side_effect=execute_saved) as saved, \
                patch.object(self.service, "finish", return_value=(completed, [], None)):
            self.assertEqual(draft.generate()[0], completed)
        llm.assert_not_called()
        saved.assert_called_once()
        asset = draft.assets["image"]
        draft.close()
        self.assertFalse(asset.exists())

    def test_invalid_edits_do_not_change_seed_or_draft(self):
        draft = self.draft()
        before = copy.deepcopy(draft.parameters)
        for bad in ({"positive_prompt": "", "negative_prompt": "bad"},
                    {"positive_prompt": "a", "negative_prompt": "", "seed": 0},
                    {"positive_prompt": "x"*5001, "negative_prompt": ""}):
            with self.assertRaises(core.OrchestratorError):
                draft.set_english(bad)
            self.assertEqual(draft.parameters, before)

    def test_h3_official_compiler_retains_header_and_validates_timing(self):
        sections = hp.default_sections(False)
        result = {"status": "dry_run", "workflow_id": core.H3_I2V_ID, "parameters": {
            "positive_prompt": hp.compile_prompt(sections, False, kept_frames=124),
            "frames": 124, "seed": 17}}
        draft = self.draft(result)
        self.assertNotIn(hp.I2VA_HEADER, draft.english()["positive_prompt"])
        text = draft.english()["positive_prompt"]
        draft.set_english({"positive_prompt": text.replace("initial composition", "opening composition")})
        self.assertTrue(draft.parameters["positive_prompt"].startswith(hp.I2VA_HEADER))
        before = copy.deepcopy(draft.parameters)
        with self.assertRaises(core.OrchestratorError):
            draft.set_english({"positive_prompt": hp.section_text(
                {**sections, "integrated_multimodal_description":
                    "[Shot 1] Walk. [Shot 2] At 00:10.000, Stop."}, False)})
        self.assertEqual(draft.parameters, before)

    def test_japanese_review_uses_same_cache_and_does_not_repeat_inference(self):
        draft = self.draft()
        calls = []
        def responder(settings, route, payload):
            if route == "/api/v1/models/unload":
                calls.append("unload")
                return {"instance_id": "instance"}
            name = payload["response_format"]["json_schema"]["name"]
            calls.append(name)
            raw = json.loads(payload["messages"][1]["content"])
            return {"choices": [{"message": {"content": json.dumps(
                {key: "訳 " + " ".join(TOKEN.findall(value)) for key, value in raw.items()},
                ensure_ascii=False)}}]}
        with patch.object(lmstudio, "list_models", return_value=self.catalog) as load, \
                patch.object(lmstudio, "_request", side_effect=responder):
            draft.translate(self.cache)
            draft.translate(self.cache)
        self.assertEqual(calls, ["single_japanese_review", "single_japanese_review", "unload"])
        load.assert_called_once()
        self.assertTrue(all(draft.japanese(self.cache).values()))
        self.assertEqual(draft.english(), {"positive_prompt": "1girl, black hair", "negative_prompt": "blurry"})

    def test_apply_changes_only_the_edited_field_and_refreshes_review(self):
        draft = self.draft()
        for key, raw in draft.english().items():
            kind, official = draft._cache_kind(key)
            self.cache.put(kind, raw, official, "黒髪" if key == "positive_prompt" else "ぼやけ")
        with patch.object(draft, "_session", side_effect=lambda action: action(Mock(), "instance")), \
                patch.object(sp, "request_validated", side_effect=lambda c, i, sys, raw, schema, name, validate, *a, **kw:
                             validate({"positive_prompt": "1girl, silver hair"})), \
                patch.object(draft, "_translate_loaded") as translate:
            draft.revise("apply", self.cache, japanese={"positive_prompt": "銀髪", "negative_prompt": "ぼやけ"})
        self.assertEqual(draft.english(), {"positive_prompt": "1girl, silver hair", "negative_prompt": "blurry"})
        self.assertEqual(draft.parameters["seed"], 123)
        translate.assert_called_once()

    def test_cancelled_rewrite_is_not_published(self):
        draft = self.draft()
        before = copy.deepcopy(draft.parameters)
        with patch.object(draft, "_session", side_effect=lambda action: action(Mock(), "instance")), \
                patch.object(sp, "request_validated", side_effect=lambda c, i, sys, raw, schema, name, validate, *a, **kw:
                             validate({"positive_prompt": "new", "negative_prompt": ""})), \
                patch.object(draft, "_translate_loaded", side_effect=JobCancellationRequested("stop")):
            with self.assertRaises(JobCancellationRequested):
                draft.revise("regenerate", self.cache, instruction="new")
        self.assertEqual(draft.parameters, before)

    def test_translation_failure_keeps_english_and_unload_failure_blocks_submission(self):
        draft = self.draft()
        before = draft.english()
        with patch.object(draft, "_session", side_effect=core.OrchestratorError("offline")):
            draft.translate(self.cache, best_effort=True)
        self.assertEqual(draft.english(), before)
        draft._unreleased = True
        with patch.object(self.service, "generate_prepared") as execute:
            with self.assertRaisesRegex(core.OrchestratorError, "解放"):
                draft.generate()
        execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()
