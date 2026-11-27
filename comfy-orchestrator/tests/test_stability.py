"""Foundation regressions: definitive rejection, recovery and immutable inputs."""
import io
import os
import queue
import time
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from comfy_orchestrator import core, gui, lmstudio, http_api
from comfy_orchestrator.history import HistoryStore
from comfy_orchestrator.jobs import JobJournal, JobSubmissionRejected, UnknownLongJob, run_job
from comfy_orchestrator.long_video import existing_result

PROJECT = Path(__file__).resolve().parents[1]


class StabilityTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.journal = JobJournal(self.root / "jobs")
        self.backend = "http://localhost:8188"
        self.comfy = Mock(base=self.backend)
        self.comfy.submit.side_effect = lambda graph, prompt_id: prompt_id

    def test_http_rejection_vs_uncertain_transport(self):
        comfy = core.ComfyUI({"base_url": self.backend})
        for status, expected in ((400, "failed"), (422, "failed"), (503, "unknown")):
            error = core.APIHTTPError(status, self.backend + "/prompt", "test")
            with patch.object(http_api, "http_json", side_effect=error):
                with self.assertRaises(core.OrchestratorError):
                    run_job(comfy, {}, "wf", "t2i", {}, journal=self.journal)
            rows = [self.journal.read(path.parent.name) for path in self.journal.root.glob("*/record.json")]
            self.assertEqual(max(rows, key=lambda r: r["created_at"])["state"], expected)

    def test_wait_rejection_does_not_become_submit_failure(self):
        self.comfy.wait.side_effect = core.APIHTTPError(400, self.backend + "/history", "error")
        with self.assertRaises(core.OrchestratorError):
            run_job(self.comfy, {}, "wf", "t2i", {}, journal=self.journal)
        row = self.journal.recoverable(self.backend)[0]
        self.assertEqual(row["state"], "unknown")

    def test_unknown_long_job_requires_confirmation_and_idle_queue(self):
        manifest = {"run_id": "long"}
        row = self.journal.create(self.backend, "wf", "i2v", {}, {},
                                  {"long_run_id": "long", "long_segment": 0})
        self.journal.update(row["job_id"], state="unknown")
        self.comfy.job_history.return_value = None
        self.comfy.job_queue_state.return_value = "unknown"
        self.comfy.queue_is_idle.return_value = False
        with self.assertRaises(UnknownLongJob):
            existing_result(self.journal, self.comfy, manifest, 0, None)
        with self.assertRaises(core.OrchestratorError):
            existing_result(self.journal, self.comfy, manifest, 0, None, confirm_unknown=lambda r: True)
        self.assertEqual(self.journal.read(row["job_id"])["state"], "unknown")
        self.comfy.queue_is_idle.return_value = True
        self.assertIsNone(existing_result(self.journal, self.comfy, manifest, 0, None,
                                          confirm_unknown=lambda r: True))
        self.assertEqual(self.journal.read(row["job_id"])["failure_kind"], "operator_abandoned")
        self.comfy.submit.assert_not_called()

    def test_unknown_job_completion_during_confirmation_is_not_discarded(self):
        row = self.journal.create(self.backend, "wf", "i2v", {}, {})
        self.journal.update(row["job_id"], state="unknown")
        self.comfy.job_history.side_effect = [None, {"outputs": {"x": {}}, "status": {"completed": True}}]
        self.comfy.job_queue_state.return_value = "unknown"
        self.comfy.queue_is_idle.return_value = True
        self.assertFalse(self.journal.abandon_unknown(self.comfy, row["job_id"]))
        self.assertEqual(self.journal.read(row["job_id"])["state"], "completed")

    def test_partial_download_is_recoverable_without_redownloading_saved_file(self):
        outputs = {"1": {"images": [{"filename": "a.png"}, {"filename": "b.png"}]}}
        row = self.journal.create(self.backend, "wf", "t2i", {}, {})
        self.journal.update(row["job_id"], state="completed", outputs=outputs)
        result = {"job_id": row["job_id"], "prompt_id": row["prompt_id"], "outputs": outputs}
        root = self.root / "outputs"
        root.mkdir()
        saved = root / "a.png"
        saved.write_bytes(b"already downloaded")
        second = root / "b.png"
        with patch.object(gui, "OUTPUTS", root), patch.object(
            gui, "save_output_image", side_effect=[saved, OSError("lost connection")]
        ):
            with self.assertRaises(core.OrchestratorError):
                gui.collect_generation_outputs(self.backend, result, "t2i", journal=self.journal)
        partial = self.journal.read(row["job_id"])
        self.assertEqual(partial["state"], "completed")
        self.assertEqual(partial["collection_state"], "download_failed")
        self.assertEqual(len(partial["downloaded_outputs"]), 1)
        second.write_bytes(b"downloaded")
        with patch.object(gui, "OUTPUTS", root), patch.object(gui, "save_output_image", return_value=second) as download:
            images = gui.collect_generation_outputs(self.backend, result, "t2i", journal=self.journal)
        self.assertEqual(images, [saved.resolve(), second.resolve()])
        self.assertEqual(download.call_count, 1)
        self.assertEqual(download.call_args.args[1]["filename"], "b.png")
        self.assertEqual(self.journal.read(row["job_id"])["collection_state"], "downloaded")

    def test_empty_output_is_not_success(self):
        row = self.journal.create(self.backend, "wf", "t2i", {}, {})
        self.journal.update(row["job_id"], state="completed", outputs={})
        with self.assertRaises(core.OrchestratorError):
            gui.collect_generation_outputs(self.backend, {
                "job_id": row["job_id"], "prompt_id": row["prompt_id"], "outputs": {}
            }, "t2i", journal=self.journal)
        self.assertEqual(self.journal.read(row["job_id"])["collection_state"], "download_failed")

    def test_same_name_in_different_subfolders_does_not_overwrite(self):
        root = self.root / "outputs"
        with patch.object(gui, "OUTPUTS", root), patch.object(gui.urllib.request, "urlopen",
                side_effect=[io.BytesIO(b"one"), io.BytesIO(b"two")]):
            a = gui.save_output_image(self.backend, {"filename": "a.png", "type": "output", "subfolder": "one"}, "id")
            b = gui.save_output_image(self.backend, {"filename": "a.png", "type": "output", "subfolder": "two"}, "id")
        self.assertNotEqual(a, b)
        self.assertEqual(a.read_bytes(), b"one")
        self.assertEqual(b.read_bytes(), b"two")

    def test_input_snapshot_shared_by_llm_upload_and_history(self):
        config_path = PROJECT / "config.example.json"
        cfg = core.load_config(config_path)
        image = self.root / "source.png"
        image.write_bytes(b"original")
        self.comfy.base = cfg["comfyui"]["base_url"]
        self.comfy.wait.return_value = {"outputs": {"1": {"images": [{"filename": "out.png"}]}}}
        def interpret(request, workflows, source, **kw):
            self.assertEqual(source.read_bytes(), b"original")
            image.write_bytes(b"changed while interpreting")
            return {"workflow_id": "wai_i2i_basic", "parameters": {"positive_prompt": "Edit."}}
        def upload(source):
            self.assertEqual(source.read_bytes(), b"original")
            return "snapshot.png"
        self.comfy.upload_image.side_effect = upload
        with patch.object(core, "ComfyUI", return_value=self.comfy), \
                patch.object(lmstudio.LMStudio, "interpret", side_effect=interpret):
            result = core.execute(cfg, config_path, "edit", image=image,
                                  selected_workflow="wai_i2i_basic", job_journal=self.journal)
        image.unlink()
        row = self.journal.read(result["job_id"])
        self.assertEqual(self.journal.context_for_history(row)["reference_image"].read_bytes(), b"original")
        history = HistoryStore(self.root)
        output = history.outputs / "out.png"
        output.write_bytes(b"output")
        app = SimpleNamespace(job_journal=self.journal, history_store=history,
                              config=cfg, messages=queue.Queue())
        history_id = gui.Application._record_completed_generation(
            app, result, [output], "wrong request", image)
        self.assertIsNotNone(history_id)
        entry = history.get(history_id)
        self.assertEqual(entry.reference_image.read_bytes(), b"original")
        self.assertEqual(entry.request_text, "edit")
        self.assertEqual(self.journal.read(result["job_id"])["state"], "collected")


class LegacyRecoveryTests(unittest.TestCase):
    def test_legacy_import_ignores_reserved_and_downloaded_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = HistoryStore(root)
            journal = JobJournal(store.data / "jobs")
            row = journal.create("http://localhost:8188", "wf", "t2i", {}, {})
            journal.update(row["job_id"], reserved_outputs={"a": "reserved.png"},
                           downloaded_outputs={"b": "downloaded.png"})
            old_time = time.time() - 60
            for name in ("reserved.png", "downloaded.png", "old.png"):
                path = store.outputs / name
                path.write_bytes(b"image")
                os.utime(path, (old_time, old_time))
            self.assertEqual(store.import_legacy_outputs(), 1)


if __name__ == "__main__":
    unittest.main()
