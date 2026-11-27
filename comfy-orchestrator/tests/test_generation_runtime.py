"""Shared execution, controller and model-handoff regressions without GPU inference."""
import queue
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from comfy_orchestrator import core, generation_runtime, output_collection
from comfy_orchestrator.generation_controller import GenerationController, active_aux_inputs, worker_events
from comfy_orchestrator.jobs import JobCancellationRequested
from comfy_orchestrator.model_runtime import release_comfy_before_llm

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config.example.json"


class SharedRuntimeTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.config = core.load_config(CONFIG)

    def test_new_generation_and_replay_use_same_submission_function(self):
        workflow_id = "wai_t2i_basic"
        result = {"status": "completed", "workflow_id": workflow_id, "parameters": {}}
        with patch.object(core, "ComfyUI"), \
                patch("comfy_orchestrator.lmstudio.LMStudio.interpret",
                      return_value={"workflow_id": workflow_id,
                                    "parameters": {"positive_prompt": "A tree."}}), \
                patch.object(core, "submit_prepared", return_value=result) as submit:
            first = core.execute(self.config, CONFIG, "tree", selected_workflow=workflow_id,
                                 overrides={"seed": 42})
            original = submit.call_args.args
            saved = original[5]
            replay = core.execute_saved(self.config, CONFIG, workflow_id, saved)
            self.assertEqual(first, replay)
            self.assertEqual(submit.call_count, 2)
            self.assertEqual(original[3:6], submit.call_args.args[3:6])

    def test_long_preflight_checks_both_hybrid_conditioning_modes(self):
        model = core.h3_hybrid_model_key("10Eros_Max_8stepTurbo_v1.0_hybrid.safetensors",
                                        reference_only=True)
        overrides = {"h3_model": model, "h3_turbo": "off",
                     "width": 864, "height": 480, "fps": 24, "frames": 124, "steps": 8}
        with patch.object(generation_runtime, "ComfyUI") as factory:
            generation_runtime.preflight_long(self.config, CONFIG, overrides, [124, 107])
        checked = factory.return_value.ensure_video_dependencies.call_args_list
        self.assertEqual(len(checked), 2)
        self.assertEqual(checked[0].args[0]["104"]["class_type"], "MiniMaxH3ReferenceToVideo")
        self.assertEqual(checked[1].args[0]["104"]["class_type"], "MiniMaxH3ImageToVideo")

    def test_invalid_long_frames_stop_before_backend_call(self):
        with patch.object(generation_runtime, "ComfyUI") as factory:
            with self.assertRaises(core.OrchestratorError):
                generation_runtime.preflight_long(
                    self.config, CONFIG, {"width": 864, "height": 480, "fps": 24, "steps": 8},
                    [124, 109])
        factory.assert_not_called()

    def test_shared_vram_policy_and_opt_out(self):
        comfy = Mock()
        release_comfy_before_llm({"free_before_llm": False}, comfy=comfy)
        release_comfy_before_llm({"free_before_llm": True}, comfy=comfy, enabled=False)
        comfy.free_if_idle.assert_not_called()
        release_comfy_before_llm({"free_before_llm": True}, comfy=comfy)
        comfy.free_if_idle.assert_called_once()

    def test_gui_preview_can_release_but_default_core_dry_run_stays_offline(self):
        wf = "wai_t2i_basic"
        response = {"workflow_id": wf, "parameters": {"positive_prompt": "A tree."}}
        with patch.object(core, "ComfyUI") as factory, \
                patch("comfy_orchestrator.lmstudio.LMStudio.interpret", return_value=response):
            core.execute(self.config, CONFIG, "tree", selected_workflow=wf, dry_run=True)
            factory.return_value.free_if_idle.assert_not_called()
            core.execute(self.config, CONFIG, "tree", selected_workflow=wf, dry_run=True,
                         release_before_dry_run=True)
            factory.return_value.free_if_idle.assert_called_once()

    def test_video_does_not_consume_hidden_still_inputs(self):
        values = ("mask.png", "pose.png", "composition.png")
        self.assertEqual(active_aux_inputs("i2v", *values), (None, None, None))
        self.assertEqual(active_aux_inputs("inpaint", *values), values)

    def test_controller_dry_run_skips_collection_and_history(self):
        service = GenerationController(self.config, CONFIG, self.root, Mock(), Mock())
        result = {"status": "dry_run", "workflow_id": core.H3_I2V_ID, "parameters": {}}
        with patch.object(core, "execute", return_value=result) as execute, \
                patch.object(output_collection, "collect_generation_outputs") as collect:
            actual = service.generate("walk", core.H3_I2V_ID, {}, image=self.root / "ref.png",
                                      mask_image="unused", pose_image="unused",
                                      composition_image="unused", dry_run=True)
        self.assertEqual(actual, (result, [], None))
        for key in ("mask_image", "pose_image", "composition_image"):
            self.assertIsNone(execute.call_args.kwargs[key])
        collect.assert_not_called()
        service.history_store.record.assert_not_called()

    def test_worker_events_always_release_busy_state(self):
        for operation, expected in (
            (lambda: 7, ("done", 7)),
            (Mock(side_effect=JobCancellationRequested("stop")), ("cancel_requested", "stop")),
            (Mock(side_effect=RuntimeError("bad")), ("error", "bad")),
        ):
            events = []
            worker_events(operation, events.append)
            self.assertEqual(events, [expected, ("idle", None)])


if __name__ == "__main__":
    unittest.main()
