"""Offline comparison routing, exact shared prompts, durable results and failure isolation."""
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from comfy_orchestrator import core, image_prompts
from comfy_orchestrator.model_profiles import ANIMA_ID, WAI_ID, QWEN_ID, QWEN_FAST_ID, ImageModelChoice
from comfy_orchestrator.model_registry import registration, image_key
from comfy_orchestrator.model_comparison import (
    ComparisonStore, prepare_targets, project_prompt_pair, representative, run_comparison,
)
from comfy_orchestrator.history import HistoryStore, HistoryError
from comfy_orchestrator.generation_controller import record_history
from comfy_orchestrator.jobs import JobJournal

CONFIG = Path(__file__).resolve().parents[1] / "config.example.json"
TAGS = {"positive_prompt": "1girl, blue jacket, gold buttons", "negative_prompt": "blurry"}
NATURAL = {"positive_prompt": "A woman wearing a blue jacket with gold buttons.",
           "negative_prompt": "Avoid blur."}
WAI = ImageModelChoice("WAI", WAI_ID, core.DEFAULT_SDXL_CHECKPOINT)
ANIMA = ImageModelChoice("Anima", ANIMA_ID, "AnimaIka_v52.safetensors")
QWEN = ImageModelChoice("Qwen", QWEN_ID)
FAST = ImageModelChoice("Lightning", QWEN_FAST_ID)


class ModelComparisonTests(unittest.TestCase):
    def setUp(self):
        self.config = core.load_config(CONFIG)
        self.workflows = self.config["workflows"]
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.history = HistoryStore(Path(self.temp.name))
        self.store = ComparisonStore(self.history)

    def targets(self, choices=(WAI, ANIMA, QWEN), **kwargs):
        return prepare_targets(self.workflows, choices, (),
                               **{"width": 1024, "height": 768, "seed": 123, **kwargs})

    def plan(self):
        return {"workflow_id": ANIMA_ID,
                "parameters": image_prompts.bind_bundle(ANIMA_ID, TAGS, NATURAL)}

    def test_common_seed_and_model_specific_defaults(self):
        targets = self.targets(seed=None)
        self.assertEqual(len({t["overrides"]["seed"] for t in targets}), 1)
        self.assertEqual([(t["overrides"]["steps"], t["overrides"]["cfg"]) for t in targets],
                         [(28, 5.5), (28, 3.5), (50, 4)])
        self.assertEqual(representative(targets)["workflow_id"], ANIMA_ID)
        for t in targets:
            self.assertEqual((t["overrides"]["width"], t["overrides"]["height"]), (1024, 768))
        common = self.targets(policy="common", steps=20, cfg=4)
        self.assertEqual([(t["overrides"]["steps"], t["overrides"]["cfg"]) for t in common],
                         [(20, 4)] * 3)

    def test_fixed_models_and_invalid_selection(self):
        fast = self.targets((WAI, FAST))
        self.assertEqual((fast[1]["overrides"]["steps"], fast[1]["overrides"]["cfg"]), (4, 1))
        for choices, opts in (((WAI,), {}), ((WAI, WAI), {}),
                              ((WAI, FAST), {"policy": "common", "steps": 28, "cfg": 5}),
                              ((WAI, ANIMA), {"width": 1000})):
            with self.subTest(choices=choices, opts=opts), self.assertRaises(core.OrchestratorError):
                self.targets(choices, **opts)

    def test_registered_defaults_used(self):
        registered = registration("anima", "custom.safetensors", 25, 3.25)
        model = ImageModelChoice("Custom", ANIMA_ID, image_key("anima", registered.filename))
        targets = prepare_targets(self.workflows, (WAI, model), (registered,),
                                  width=1024, height=1024, seed=123)
        self.assertEqual(targets[1]["overrides"]["steps"], 25)
        self.assertEqual(targets[1]["overrides"]["cfg"], 3.25)

    def test_prompt_projection_preserves_both_formats_and_exact_seed(self):
        targets = self.targets()
        w, a, q = project_prompt_pair(self.plan(), targets, self.workflows)
        self.assertEqual(w["positive_prompt"], TAGS["positive_prompt"])
        self.assertEqual(a["positive_prompt"], TAGS["positive_prompt"] + "\n\n" + NATURAL["positive_prompt"])
        self.assertEqual(a["negative_prompt"], TAGS["negative_prompt"])
        self.assertEqual(q["positive_prompt"], NATURAL["positive_prompt"])
        self.assertEqual(q["negative_prompt"], NATURAL["negative_prompt"])
        for t, p in zip(targets, (w, a, q)):
            self.assertEqual(p["seed"], 123)
            _, bundle = image_prompts.split_saved(p, t["workflow_id"])
            self.assertEqual(bundle["prompts"], {"tags": TAGS, "natural": NATURAL})
        with self.assertRaises(core.OrchestratorError):
            project_prompt_pair({"workflow_id": WAI_ID, "parameters": TAGS}, targets, self.workflows)

    def fake_controller(self, group, *, fail_at=None, cancel_after=None):
        controller = Mock()
        controller.config = self.config
        controller.config_path = CONFIG
        controller.cancel_event = threading.Event()
        controller.generate.return_value = (self.plan(), [], None)
        calls = []

        def generate(request, workflow, parameters, **context):
            index = context["comparison_index"]
            calls.append(index)
            self.assertEqual(context["comparison_group_id"], group["id"])
            if index == fail_at:
                raise core.OrchestratorError("unresolved generation")
            image = self.history.outputs / f"model-{index}.png"
            image.write_bytes(b"test")
            entry = self.history.record(prompt_id=f"prompt-{index}", workflow_id=workflow,
                                        kind="t2i", request_text=request, parameters=parameters,
                                        images=[image], comparison_group_id=group["id"],
                                        comparison_index=index)
            if index == cancel_after:
                controller.cancel_event.set()
            return {"parameters": parameters, "elapsed_seconds": 1.25}, [image], entry.id

        controller.generate_prepared.side_effect = generate
        return controller, calls

    def test_sequential_generation_and_persisted_history(self):
        group = self.store.create("衣装を維持", self.targets(), "recommended")
        controller, calls = self.fake_controller(group)
        snapshots = []
        with patch("comfy_orchestrator.model_comparison.preflight") as check:
            done = run_comparison(controller, self.store, group, on_update=snapshots.append)
        self.assertEqual(done["status"], "completed")
        self.assertEqual(calls, [0, 1, 2])
        controller.generate.assert_called_once()
        self.assertTrue(controller.generate.call_args.kwargs["dry_run"])
        self.assertEqual(check.call_count, 3)
        restored = self.store.read(group["id"])
        self.assertEqual(restored, done)
        self.assertEqual([e.comparison_index for e in self.history.comparison_entries(group["id"])], [0, 1, 2])
        self.assertTrue(all(self.store.images_for(t) for t in restored["targets"]))
        self.assertTrue(any(s["targets"][0]["status"] == "completed" for s in snapshots))

    def test_error_stops_new_jobs_and_preserves_finished_image(self):
        group = self.store.create("test", self.targets(), "recommended")
        controller, calls = self.fake_controller(group, fail_at=1)
        with patch("comfy_orchestrator.model_comparison.preflight"):
            done = run_comparison(controller, self.store, group)
        self.assertEqual(done["status"], "error")
        self.assertEqual(calls, [0, 1])
        self.assertEqual([t["status"] for t in done["targets"]], ["completed", "error", "pending"])
        self.assertTrue(self.store.images_for(self.store.read(group["id"])["targets"][0]))

    def test_cancel_stops_before_next_job(self):
        group = self.store.create("test", self.targets(), "recommended")
        controller, calls = self.fake_controller(group, cancel_after=0)
        with patch("comfy_orchestrator.model_comparison.preflight"):
            done = run_comparison(controller, self.store, group)
        self.assertEqual(done["status"], "interrupted")
        self.assertEqual(calls, [0])
        self.assertEqual([t["status"] for t in done["targets"]], ["completed", "pending", "pending"])

    def test_preflight_failure_never_invokes_llm(self):
        group = self.store.create("test", self.targets(), "recommended")
        controller, calls = self.fake_controller(group)
        with patch("comfy_orchestrator.model_comparison.preflight", side_effect=core.OrchestratorError("missing")):
            done = run_comparison(controller, self.store, group)
        self.assertEqual(done["status"], "error")
        controller.generate.assert_not_called()
        self.assertEqual(calls, [])

    def test_recovered_job_restores_comparison_slot(self):
        group = self.store.create("test", self.targets(), "recommended")
        p = project_prompt_pair(self.plan(), group["targets"], self.workflows)[1]
        journal = JobJournal(self.history.data / "jobs")
        record = journal.create("http://127.0.0.1:8188", ANIMA_ID, "t2i", p, {},
                                {"request_text": "test", "comparison_group_id": group["id"],
                                 "comparison_index": 1})
        output = self.history.outputs / "recovered.png"
        output.write_bytes(b"test")
        result = {"workflow_id": ANIMA_ID, "parameters": p, "prompt_id": record["prompt_id"],
                  "job_id": record["job_id"]}
        history_id = record_history(self.config, self.history, journal, result, [output], "test")
        self.assertIsNotNone(history_id)
        self.assertEqual(self.history.get(history_id).comparison_group_id, group["id"])
        resolved = self.store.resolved(self.store.read(group["id"]))
        self.assertEqual(resolved["targets"][1]["status"], "completed")
        self.assertEqual(resolved["targets"][1]["history_id"], history_id)
        self.assertEqual(self.store.images_for(resolved["targets"][1]), (output,))
        self.assertEqual(self.store.images_for({"images": ["../outside.png"]}), ())

    def test_history_rejects_invalid_slot(self):
        output = self.history.outputs / "bad.png"
        output.write_bytes(b"test")
        with self.assertRaises(HistoryError):
            self.history.record(prompt_id="bad", workflow_id=WAI_ID, kind="t2i",
                                request_text="test", parameters=TAGS, images=[output],
                                comparison_group_id="invalid", comparison_index=0)


if __name__ == "__main__":
    unittest.main()
