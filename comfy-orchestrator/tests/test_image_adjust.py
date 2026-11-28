"""Independent refinement state, exact prepared generation, and input safety."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
import threading

from comfy_orchestrator import core, image_prompts
from comfy_orchestrator.history import HistoryStore
from comfy_orchestrator.image_adjust import ImageAdjustDraft, can_adjust, I2I

CONFIG = Path(__file__).resolve().parents[1] / "config.example.json"


class ImageAdjustmentTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.store = HistoryStore(self.root)
        self.config = core.load_config(CONFIG)
        self.controller = Mock(config=self.config, cancel_event=threading.Event(), journal=None)
        self.image = self.store.outputs / "first.png"
        self.image.write_bytes(b"first")
        self.other = self.store.outputs / "other.png"
        self.other.write_bytes(b"other")

    def entry(self, workflow="wai_t2i_basic", params=None, **kwargs):
        return self.store.record(prompt_id=workflow + str(len(self.store.list_entries())),
            workflow_id=workflow, kind=self.config["workflows"][workflow]["kind"],
            request_text="tree", parameters={"positive_prompt": "tree", "seed": 19, **(params or {})},
            images=[self.image], **kwargs)

    def draft(self, entry=None, selected=None):
        draft = ImageAdjustDraft.from_history(self.controller, entry or self.entry(), selected)
        self.addCleanup(draft.close)
        return draft

    def values(self, draft, **changes):
        return {**{k: str(draft.parameters[k]) for k in draft.numeric_fields}, **changes}

    def completed(self, draft, image=None, **changes):
        return {"status": "completed", "workflow_id": draft.workflow_id,
                "parameters": {**draft.parameters, **changes}}, [image or self.other], "result-id"

    def test_initial_inputs_are_frozen_and_workflow_is_not_changed(self):
        source = self.root / "source.png"
        source.write_bytes(b"source")
        entry = self.entry(I2I, reference_image=source)
        draft = self.draft(entry)
        self.assertEqual(draft.workflow_id, I2I)
        self.assertEqual(draft.base_image.read_bytes(), b"first")
        self.assertEqual(draft.assets["image"].read_bytes(), b"source")
        self.assertNotEqual(draft.assets["image"], entry.reference_image)
        self.image.write_bytes(b"changed")
        entry.reference_image.write_bytes(b"changed input")
        self.assertEqual(draft.base_image.read_bytes(), b"first")
        self.assertEqual(draft.assets["image"].read_bytes(), b"source")

    def test_direct_edit_uses_prepared_generation_without_interpretation(self):
        draft = self.draft()
        draft.apply_edits({"positive_prompt": "green tree", "negative_prompt": "bad"},
                          self.values(draft, steps="12", cfg="4.25"))
        self.controller.generate_prepared.return_value = self.completed(draft)
        result = draft.generate_variant()
        self.controller.generate.assert_not_called()
        self.controller.generate_prepared.assert_called_once()
        _, workflow, params = self.controller.generate_prepared.call_args.args
        self.assertEqual(workflow, "wai_t2i_basic")
        self.assertEqual((params["positive_prompt"], params["steps"], params["cfg"], params["seed"]),
                         ("green tree", 12, 4.25, 19))
        self.assertIsNone(self.controller.generate_prepared.call_args.kwargs["image"])
        draft.accept_completed(result)
        self.assertEqual(draft.results, [self.other])
        self.assertEqual(draft.result_parameters[0]["seed"], 19)

    def test_random_seed_published_only_on_success(self):
        draft = self.draft()
        self.controller.generate_prepared.side_effect = lambda request, workflow, params, **kw: (
            {"status": "completed", "workflow_id": workflow, "parameters": params}, [self.other], "id")
        with patch("comfy_orchestrator.image_adjust.secrets.randbits", return_value=4321):
            result = draft.generate_variant(fixed_seed=False)
        self.assertEqual(draft.parameters["seed"], 19)
        draft.accept_completed(result)
        self.assertEqual(draft.parameters["seed"], 4321)
        self.controller.generate_prepared.side_effect = core.OrchestratorError("failure")
        with patch("comfy_orchestrator.image_adjust.secrets.randbits", return_value=1234):
            with self.assertRaises(core.OrchestratorError):
                draft.generate_variant(fixed_seed=False)
        self.assertEqual(draft.parameters["seed"], 4321)

    def test_baseline_adoption_does_not_change_input_until_explicit_i2i(self):
        draft = self.draft()
        draft.accept_completed(self.completed(draft))
        before = dict(draft.parameters)
        draft.adopt_result(self.other)
        self.assertEqual(draft.base_image.read_bytes(), b"other")
        self.assertEqual(draft.parameters, before)
        self.assertIsNone(draft.assets["image"])
        draft.use_base_as_input()
        self.assertEqual(draft.workflow_id, I2I)
        self.assertEqual(draft.assets["image"], draft.base_image)
        self.assertNotIn("width", draft.parameters)
        self.assertIn("denoise", draft.parameters)
        self.assertEqual(draft.parameters["positive_prompt"], before["positive_prompt"])
        new = self.store.outputs / "new.png"
        new.write_bytes(b"new")
        draft.accept_completed(self.completed(draft, new))
        old_source = draft.assets["image"]
        draft.adopt_result(new)
        self.assertEqual(old_source.read_bytes(), b"other")
        self.assertEqual(draft.assets["image"], old_source)
        draft.use_base_as_input()
        self.assertFalse(old_source.exists())
        self.assertEqual(draft.assets["image"].read_bytes(), b"new")
        self.assertTrue(self.other.is_file())

    def test_inpaint_inputs_preserved_and_then_cleared_only_on_i2i_switch(self):
        source = self.root / "source.png"
        mask = self.root / "mask.png"
        source.write_bytes(b"source")
        mask.write_bytes(b"mask")
        draft = self.draft(self.entry("wai_inpaint_basic", reference_image=source, mask_image=mask))
        self.assertEqual(draft.assets["mask_image"].read_bytes(), b"mask")
        draft.use_base_as_input()
        self.assertIsNone(draft.assets["mask_image"])
        self.assertEqual(draft.assets["image"], draft.base_image)
        self.assertTrue(mask.is_file())

    def test_invalid_edit_is_atomic_and_fixed_model_constraints_are_real(self):
        draft = self.draft()
        old = dict(draft.parameters)
        for edits in ({"steps": "1.5"}, {"width": "123"}, {"cfg": "nan"}):
            with self.assertRaises(core.OrchestratorError):
                draft.apply_edits(draft.english(), self.values(draft, **edits))
            self.assertEqual(draft.parameters, old)
        turbo = "sd_xl_turbo_1.0_fp16.safetensors"
        with self.assertRaises(core.OrchestratorError):
            draft.apply_edits(draft.english(), self.values(draft), turbo)
        draft.apply_edits(draft.english(), self.values(draft, steps="4", cfg="1"), turbo)
        self.assertFalse(draft.can_use_base_as_input())
        with self.assertRaises(core.OrchestratorError):
            draft.use_base_as_input()
        self.assertEqual(draft.workflow_id, "wai_t2i_basic")

    def test_qwen_lightning_keeps_fixed_sampler_and_cannot_convert_to_sdxl(self):
        draft = self.draft(self.entry(core.QWEN_LIGHTNING_ID))
        self.assertTrue(draft.fixed_sampler())
        self.assertFalse(draft.checkpoint_selectable)
        self.assertFalse(draft.can_use_base_as_input())
        with self.assertRaises(core.OrchestratorError):
            draft.apply_edits(draft.english(), self.values(draft, width="1032"))
        with self.assertRaises(core.OrchestratorError):
            draft.apply_edits(draft.english(), self.values(draft, steps="8"))

    def test_t2i_switch_uses_other_prompt_and_target_defaults_without_llm(self):
        tags = {"positive_prompt": "tree", "negative_prompt": "bad"}
        natural = {"positive_prompt": "A tree.", "negative_prompt": "Avoid blur."}
        bundle = image_prompts.make_bundle("wai_t2i_basic", tags, natural)
        draft = self.draft(self.entry(params={**tags, image_prompts.KEY: bundle}))
        draft.switch_t2i(core.QWEN_LIGHTNING_ID)
        self.assertEqual(draft.english(), natural)
        self.assertEqual((draft.parameters["steps"], draft.parameters["cfg"], draft.parameters["seed"]),
                         (4, 1, 19))
        self.assertEqual(draft.parameters[image_prompts.KEY]["active_format"], "natural")
        draft.switch_t2i("wai_t2i_basic")
        self.assertEqual(draft.english(), tags)
        self.assertEqual(draft.parameters["steps"], 28)
        self.controller.generate.assert_not_called()
        self.controller.generate_prepared.assert_not_called()

    def test_switch_without_other_format_or_from_i2i_refused(self):
        draft = self.draft()
        original = dict(draft.parameters)
        with self.assertRaises(core.OrchestratorError):
            draft.switch_t2i(core.QWEN_T2I_ID)
        self.assertEqual(draft.parameters, original)
        self.assertEqual(draft.workflow_id, "wai_t2i_basic")
        draft.use_base_as_input()
        self.assertEqual(draft.t2i_choices(), ())
        with self.assertRaises(core.OrchestratorError):
            draft.switch_t2i(core.QWEN_T2I_ID)

    def test_missing_saved_input_or_wrong_selected_output_refused(self):
        entry = self.entry()
        self.assertTrue(can_adjust(entry, self.config["workflows"]))
        with self.assertRaisesRegex(core.OrchestratorError, "出力"):
            self.draft(entry, self.other)
        source = self.root / "source.png"
        source.write_bytes(b"source")
        entry = self.entry(I2I, reference_image=source)
        entry.reference_image.unlink()
        with self.assertRaises(core.OrchestratorError):
            self.draft(entry)


if __name__ == "__main__":
    unittest.main()
