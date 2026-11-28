"""Anima uses the mixed execution prompt without losing the standalone pair."""
import copy
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from comfy_orchestrator import core, image_prompts as p, lmstudio
from comfy_orchestrator.model_profiles import ANIMA_ID, ANIMA_BASE
from comfy_orchestrator.single_prompt import SinglePromptDraft
from comfy_orchestrator.image_adjust import ImageAdjustDraft
from comfy_orchestrator.prompt_cache import PromptCache
from comfy_orchestrator.history import HistoryStore
from comfy_orchestrator.history_presentation import history_prompt_details

CONFIG = Path(__file__).resolve().parents[1] / "config.example.json"
TAGS = {"positive_prompt": "1girl, black hair, long hair, window", "negative_prompt": "blurry, bad anatomy"}
NATURAL = {"positive_prompt": "A woman with long black hair sits by a window. Soft light outlines her shirt folds.",
           "negative_prompt": "Avoid blur and distorted anatomy."}
MIXED = TAGS["positive_prompt"] + "\n\n" + NATURAL["positive_prompt"]


class AnimaMixedPromptTests(unittest.TestCase):
    def setUp(self):
        self.config = core.load_config(CONFIG)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.params = {**self.config["workflows"][ANIMA_ID]["defaults"], **TAGS, "seed": 12,
                       "checkpoint_model": ANIMA_BASE}

    def make_draft(self, parameters):
        controller = SimpleNamespace(config=self.config, cancel_event=None, note=None)
        temporary = tempfile.TemporaryDirectory()
        draft = SinglePromptDraft(controller, {"workflow_id": ANIMA_ID, "parameters": parameters},
                                  "窓際の女性", {}, {}, temporary)
        self.addCleanup(draft.close)
        return draft

    def test_composition_preserves_sources_and_uses_tag_negative(self):
        combined = p.bind_bundle(ANIMA_ID, self.params, NATURAL)
        self.assertTrue(p.is_mixed(combined))
        self.assertEqual(combined["positive_prompt"], MIXED)
        self.assertEqual(combined["negative_prompt"], TAGS["negative_prompt"])
        clean, bundle = p.split_saved(combined, ANIMA_ID)
        self.assertEqual(bundle["prompts"], {"tags": TAGS, "natural": NATURAL})
        self.assertNotIn(p.KEY, clean)
        self.assertEqual(p.editor_pair(combined, ANIMA_ID), TAGS)
        self.assertEqual(self.params["positive_prompt"], TAGS["positive_prompt"])
        self.assertFalse(p.is_mixed(p.bind_bundle("wai_t2i_basic", TAGS, NATURAL)))
        self.assertFalse(p.is_mixed(p.bind_bundle("qwen_image_2512_t2i", NATURAL, TAGS)))

    def test_legacy_tag_bundle_and_no_bundle_are_not_migrated(self):
        previous = {**self.params, p.KEY: p.make_bundle(ANIMA_ID, self.params, NATURAL)}
        clean, bundle = p.split_saved(previous, ANIMA_ID)
        self.assertEqual(bundle["version"], 1)
        self.assertEqual(clean["positive_prompt"], TAGS["positive_prompt"])
        self.assertIsNone(p.split_saved(self.params, ANIMA_ID)[1])
        self.assertEqual(self.make_draft(previous).english(), TAGS)

    def test_reject_corrupt_or_oversized_mixed(self):
        combined = p.bind_bundle(ANIMA_ID, self.params, NATURAL)
        corrupt = copy.deepcopy(combined)
        corrupt[p.KEY]["prompts"].pop("natural")
        for bad in (corrupt, {**combined, "positive_prompt": "changed"}):
            with self.assertRaises(core.OrchestratorError):
                p.split_saved(bad, ANIMA_ID)
        with self.assertRaises(core.OrchestratorError):
            p.split_saved(combined, "wai_t2i_basic")
        with self.assertRaises(core.OrchestratorError):
            p.bind_bundle(ANIMA_ID, {**TAGS, "positive_prompt": "a" * 4000},
                          {**NATURAL, "positive_prompt": "b" * 2000})

    def test_review_no_edit_preserves_exact_execution_and_direct_edit_invalidates(self):
        combined = p.bind_bundle(ANIMA_ID, self.params, NATURAL)
        draft = self.make_draft(combined)
        self.assertEqual(draft.english(), TAGS)
        draft.set_english(draft.english())
        self.assertEqual(draft.parameters, combined)
        draft.set_english({**TAGS, "positive_prompt": "1girl, short hair"})
        self.assertEqual(draft.parameters["positive_prompt"], "1girl, short hair")
        self.assertFalse(p.is_mixed(draft.parameters))
        self.assertEqual(set(draft.parameters[p.KEY]["prompts"]), {"tags"})

    def test_revision_rebuilds_actual_prompt_without_duplicate_append(self):
        combined = p.bind_bundle(ANIMA_ID, self.params, NATURAL)
        draft = self.make_draft(combined)
        edits = [
            {"format": "tags", "field": "positive_prompt", "old": "long hair", "new": "short hair"},
            {"format": "natural", "field": "positive_prompt", "old": "long black hair", "new": "short black hair"},
        ]
        def reply(client, instance, system, payload, schema, name, validator, *args):
            self.assertIn("ANIMA MIXED CONDITIONING", system)
            return validator({"edits": edits})
        with patch.object(draft, "_session", side_effect=lambda action: action(None, None)), \
                patch.object(p, "request_validated", side_effect=reply):
            draft.revise("regenerate", None, instruction="髪を短く")
        updated = draft.parameters
        self.assertTrue(p.is_mixed(updated))
        self.assertEqual(updated["positive_prompt"].count("\n\n"), 1)
        self.assertIn("short black hair", updated["positive_prompt"])
        self.assertNotIn("long hair", updated["positive_prompt"])
        self.assertEqual(updated[p.KEY]["instructions"], ["髪を短く"])
        self.assertEqual(combined["positive_prompt"], MIXED)

    def test_generation_history_and_replay_use_literal_mixed(self):
        plan = {"workflow_id": ANIMA_ID, "parameters": TAGS, p.ALT: NATURAL}
        with patch.object(lmstudio.LMStudio, "interpret", return_value=plan) as infer, \
                patch.object(core, "ComfyUI") as factory:
            comfy = factory.return_value
            comfy.submit.return_value = "id"
            comfy.wait.return_value = {"outputs": {}}
            result = core.execute(self.config, CONFIG, "窓際の女性", selected_workflow=ANIMA_ID,
                                  overrides={"seed": 12, "checkpoint_model": ANIMA_BASE})
            graph = comfy.submit.call_args.args[0]
            self.assertEqual(graph["6"]["inputs"]["text"], MIXED)
            self.assertEqual(graph["7"]["inputs"]["text"], TAGS["negative_prompt"])
            self.assertEqual(result["parameters"]["positive_prompt"], MIXED)
            infer.assert_called_once()
            replay = core.execute_saved(self.config, CONFIG, ANIMA_ID, result["parameters"])
            self.assertEqual(comfy.submit.call_args.args[0], graph)
            self.assertEqual(replay["parameters"], result["parameters"])
            infer.assert_called_once()
            legacy = core.execute_saved(self.config, CONFIG, ANIMA_ID, self.params)
            self.assertEqual(comfy.submit.call_args.args[0]["6"]["inputs"]["text"], TAGS["positive_prompt"])
            self.assertNotIn(p.KEY, legacy["parameters"])
            version_one = {**self.params, p.KEY: p.make_bundle(ANIMA_ID, self.params, NATURAL)}
            replay_one = core.execute_saved(self.config, CONFIG, ANIMA_ID, version_one)
            self.assertEqual(comfy.submit.call_args.args[0]["6"]["inputs"]["text"], TAGS["positive_prompt"])
            self.assertEqual(replay_one["parameters"], version_one)
        store = HistoryStore(self.root)
        output = store.outputs / "out.png"
        output.write_bytes(b"image")
        entry = store.record(prompt_id="anima-test", workflow_id=ANIMA_ID, kind="t2i",
                             request_text="窓際の女性", parameters=result["parameters"], images=[output])
        details = history_prompt_details(entry)
        self.assertEqual(details["positive_prompt"], MIXED)
        self.assertEqual(details[p.KEY], result["parameters"][p.KEY])

    def test_cached_plan_is_composed_once_per_generation_without_new_inference(self):
        cache = PromptCache(self.root / "plans.sqlite3")
        plan = {"workflow_id": ANIMA_ID, "parameters": TAGS, p.ALT: NATURAL}
        with patch.object(lmstudio.LMStudio, "interpret", return_value=plan) as infer, \
                patch.object(core, "ComfyUI"):
            first = core.execute(self.config, CONFIG, "窓際の女性", selected_workflow=ANIMA_ID,
                                 dry_run=True, prompt_cache=cache, overrides={"seed": 12})
            second = core.execute(self.config, CONFIG, "窓際の女性", selected_workflow=ANIMA_ID,
                                  dry_run=True, prompt_cache=cache, overrides={"seed": 34})
        infer.assert_called_once()
        self.assertEqual(first["parameters"]["positive_prompt"], MIXED)
        self.assertEqual(second["parameters"]["positive_prompt"], MIXED)
        self.assertEqual(second["parameters"]["seed"], 34)
        self.assertEqual(first["parameters"][p.KEY], second["parameters"][p.KEY])

    def test_oversized_combination_keeps_both_sources_but_runs_tags(self):
        tags = {**TAGS, "positive_prompt": "a" * 4000}
        natural = {**NATURAL, "positive_prompt": "b" * 2000}
        plan = {"workflow_id": ANIMA_ID, "parameters": tags, p.ALT: natural}
        notes = []
        with patch.object(lmstudio.LMStudio, "interpret", return_value=plan), patch.object(core, "ComfyUI"):
            result = core.execute(self.config, CONFIG, "test", selected_workflow=ANIMA_ID,
                                  dry_run=True, progress=notes.append)
        params = result["parameters"]
        self.assertEqual(params["positive_prompt"], tags["positive_prompt"])
        self.assertEqual(params[p.KEY]["prompts"]["natural"], natural)
        self.assertFalse(p.is_mixed(params))
        self.assertTrue(any("タグ形式で生成" in note for note in notes))

    def test_switch_between_wai_qwen_and_anima_without_reinterpretation(self):
        store = HistoryStore(self.root)
        output = store.outputs / "sample.png"
        output.write_bytes(b"image")
        params = p.bind_bundle("wai_t2i_basic", {**TAGS, "seed": 12}, NATURAL)
        entry = store.record(prompt_id="source", workflow_id="wai_t2i_basic", kind="t2i",
                             request_text="窓際の女性", parameters=params, images=[output])
        controller = Mock(config=self.config, cancel_event=None)
        draft = ImageAdjustDraft.from_history(controller, entry)
        self.addCleanup(draft.close)
        draft.switch_t2i(ANIMA_ID, checkpoint=ANIMA_BASE)
        self.assertEqual(draft.parameters["positive_prompt"], MIXED)
        self.assertEqual(draft.english(), TAGS)
        numeric = {k: str(draft.parameters[k]) for k in draft.numeric_fields}
        draft.apply_edits(draft.english(), {**numeric, "steps": "29"}, ANIMA_BASE)
        self.assertEqual(draft.parameters["positive_prompt"], MIXED)
        self.assertTrue(p.is_mixed(draft.parameters))
        draft.switch_t2i(core.QWEN_T2I_ID)
        self.assertEqual(draft.english(), NATURAL)
        self.assertFalse(p.is_mixed(draft.parameters))
        draft.switch_t2i("wai_t2i_basic")
        self.assertEqual(draft.english(), TAGS)
        draft.switch_t2i(ANIMA_ID)
        self.assertEqual(draft.parameters["positive_prompt"], MIXED)
        controller.generate.assert_not_called()
        controller.generate_prepared.assert_not_called()


if __name__ == "__main__":
    unittest.main()
