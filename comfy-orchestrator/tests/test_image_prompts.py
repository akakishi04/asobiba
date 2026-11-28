import unittest
from types import SimpleNamespace
from unittest.mock import patch

from comfy_orchestrator import image_prompts as p
from comfy_orchestrator.parameters import OrchestratorError


class ImagePromptBundleTests(unittest.TestCase):
    def setUp(self):
        self.workflow = "wai_t2i_basic"
        self.tags = {"positive_prompt": "black hair, long hair, window", "negative_prompt": "blurry"}
        self.natural = {"positive_prompt": "A woman with long black hair sits by a window.", "negative_prompt": "Avoid blur."}
        self.bundle = p.make_bundle(self.workflow, self.tags, self.natural)
        self.parameters = {**self.tags, "seed": 12, p.KEY: self.bundle}

    def test_saved_bundle_is_not_a_graph_parameter(self):
        clean, bundle = p.split_saved(self.parameters, self.workflow)
        self.assertNotIn(p.KEY, clean)
        self.assertEqual(bundle, self.bundle)
        self.assertEqual(clean["seed"], 12)
        self.assertEqual(p.split_saved({**self.tags, "seed": 12}, self.workflow)[1], None)

    def test_rejects_mismatched_active_and_video_metadata(self):
        with self.assertRaises(OrchestratorError):
            p.split_saved({**self.parameters, "positive_prompt": "other"}, self.workflow)
        with self.assertRaises(OrchestratorError):
            p.split_saved(self.parameters, "minimax_h3_i2v")

    def test_direct_edit_invalidates_alternative_only_when_prompt_changes(self):
        self.assertEqual(p.synchronize({**self.parameters, "seed": 42}, self.workflow, self.parameters)[p.KEY], self.bundle)
        updated = p.synchronize({**self.parameters, "positive_prompt": "short hair"}, self.workflow, self.parameters)
        self.assertEqual(set(updated[p.KEY]["prompts"]), {"tags"})
        p.split_saved(updated, self.workflow)

    def test_exact_patch_both_formats(self):
        edits = [
            {"format": "tags", "field": "positive_prompt", "old": "long hair", "new": "short hair"},
            {"format": "natural", "field": "positive_prompt", "old": "long black hair", "new": "short black hair"},
        ]
        result = p.apply_patches(self.bundle["prompts"], edits)
        self.assertEqual(result["tags"]["positive_prompt"], "black hair, short hair, window")
        self.assertEqual(result["natural"]["positive_prompt"], "A woman with short black hair sits by a window.")
        self.assertEqual(result["tags"]["negative_prompt"], "blurry")
        self.assertEqual(self.bundle["prompts"]["tags"], self.tags)

    def test_ambiguous_and_missing_substrings_rejected(self):
        for old in ("not present", "hair"):
            with self.assertRaises(OrchestratorError):
                p.apply_patches(self.bundle["prompts"], [
                    {"format": "tags", "field": "positive_prompt", "old": old, "new": "x"}])

    def test_revision_updates_both_and_keeps_original_immutable(self):
        draft = SimpleNamespace(parameters=self.parameters, workflow_id=self.workflow,
            request="窓辺の女性", controller=SimpleNamespace(note=None, cancel_event=None),
            _session=lambda action: action(None, None))
        edits = [
            {"format": "tags", "field": "positive_prompt", "old": "long hair", "new": "short hair"},
            {"format": "natural", "field": "positive_prompt", "old": "long black hair", "new": "short black hair"},
        ]
        def response(client, instance, system, payload, schema, name, validator, *args, **kwargs):
            return validator({"edits": edits})
        with patch.object(p, "request_validated", side_effect=response):
            updated = p.revise_bundle(draft, "髪を短く")
        _, bundle = p.split_saved(updated, self.workflow)
        self.assertEqual(bundle["instructions"], ["髪を短く"])
        self.assertEqual(bundle["prompts"]["tags"]["positive_prompt"], "black hair, short hair, window")
        self.assertIn("short black hair", bundle["prompts"]["natural"]["positive_prompt"])
        self.assertEqual(draft.parameters, self.parameters)

    def test_legacy_revision_generates_missing_format_in_same_response(self):
        draft = SimpleNamespace(parameters={**self.tags, "seed": 12}, workflow_id=self.workflow,
            request="窓辺の女性", controller=SimpleNamespace(note=None, cancel_event=None),
            _session=lambda action: action(None, None))
        def response(client, instance, system, payload, schema, name, validator, *args, **kwargs):
            self.assertIn(p.ALT, schema["required"])
            return validator({"edits": [], p.ALT: self.natural})
        with patch.object(p, "request_validated", side_effect=response):
            updated = p.revise_bundle(draft, "元の内容を維持")
        _, bundle = p.split_saved(updated, self.workflow)
        self.assertEqual(bundle["prompts"]["natural"], self.natural)

    def test_schema_and_split_plan_are_image_only(self):
        schema = {"type": "object", "properties": {}, "required": []}
        workflows = {self.workflow: {}}
        extended = p.extend_schema(schema, workflows)
        self.assertIn(p.ALT, extended["required"])
        self.assertNotIn(p.ALT, schema["required"])
        plan = {"workflow_id": self.workflow, "parameters": self.tags, p.ALT: self.natural}
        clean, alt = p.split_plan(plan, workflows)
        self.assertNotIn(p.ALT, clean)
        self.assertEqual(alt, self.natural)
        self.assertEqual(p.extend_schema(schema, {"minimax_h3_i2v": {}}), schema)
        self.assertEqual(p.prompt_format("qwen_image_2512_t2i"), "natural")


if __name__ == "__main__":
    unittest.main()
