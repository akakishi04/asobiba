"""Offline tests for durable submission, targeted cancellation and recovery."""
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from comfy_orchestrator import core, http_api
from comfy_orchestrator.jobs import JobJournal, JobCancellationRequested, run_job


class JobTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.journal = JobJournal(self.root / "jobs")
        self.comfy = Mock()
        self.comfy.base = "http://127.0.0.1:8188"
        self.graph = {"1": {"class_type": "RandomNoise", "inputs": {"noise_seed": 7}}}
        self.comfy.submit.side_effect = lambda graph, prompt_id: prompt_id
        self.comfy.wait.return_value = {"outputs": {"2": {"images": []}}, "status": {"completed": True}}

    def run_one(self, context=None):
        return run_job(self.comfy, self.graph, "wf", "i2v", {"seed": 7},
                       journal=self.journal, context=context)

    def test_pre_submit_snapshot_and_completion(self):
        image = self.root / "ref.png"
        image.write_bytes(b"original")
        def submit(graph, prompt_id):
            row = self.journal.read(prompt_id)
            self.assertEqual(row["state"], "submitting")
            self.assertEqual(row["graph"], graph)
            image.write_bytes(b"changed")
            self.assertEqual(self.journal.context_for_history(row)["reference_image"].read_bytes(), b"original")
            return prompt_id
        self.comfy.submit.side_effect = submit
        prompt_id, _, result = self.run_one({"reference_image": image, "request_text": "walk"})
        row = self.journal.read(result["job_id"])
        self.assertEqual(row["prompt_id"], prompt_id)
        self.assertEqual(row["state"], "completed")
        self.assertEqual(row["context"]["request_text"], "walk")
        self.assertEqual(self.journal.inspect(self.comfy, row)[0], "completed")
        self.journal.update(result["job_id"], state="collected")
        self.assertEqual(self.journal.recoverable(self.comfy.base), [])

    def test_lost_submit_response_retains_id_never_retries(self):
        self.comfy.submit.side_effect = core.OrchestratorError("connection reset")
        with self.assertRaises(core.OrchestratorError):
            self.run_one()
        row = self.journal.recoverable(self.comfy.base)[0]
        self.assertEqual(row["state"], "unknown")
        self.assertEqual(row["job_id"], row["prompt_id"])
        self.comfy.submit.assert_called_once()
        self.comfy.wait.assert_not_called()
        self.comfy.job_history.return_value = {"status": {"completed": True}, "outputs": {}}
        self.assertEqual(self.journal.inspect(self.comfy, row)[0], "completed")
        self.comfy.submit.assert_called_once()

    def test_only_matching_backend_recovery(self):
        self.run_one()
        self.assertEqual(self.journal.recoverable("http://other:8188"), [])

    def test_targeted_stop_never_sends_global_interrupt(self):
        cfg = {"base_url": self.comfy.base}
        stopped = threading.Event()
        stopped.set()
        with patch.object(http_api, "http_json", side_effect=[
            {"system": {"comfyui_version": "0.46.3"}}, {}, {},
        ]) as api:
            with self.assertRaises(JobCancellationRequested):
                core.ComfyUI(cfg).wait("target", cancel_event=stopped, cancel_remote=True)
        self.assertEqual(api.call_args_list[1].args[1:3], ("/queue", {"delete": ["target"]}))
        self.assertEqual(api.call_args_list[2].args[1:3], ("/interrupt", {"prompt_id": "target"}))
        with patch.object(http_api, "http_json", return_value={"system": {"comfyui_version": "0.40.0"}}) as api:
            with self.assertRaises(core.OrchestratorError):
                core.ComfyUI(cfg).wait("target", cancel_event=stopped, cancel_remote=True)
        api.assert_called_once()

    def test_cancel_requested_not_claimed_finished(self):
        self.comfy.wait.side_effect = JobCancellationRequested("requested")
        with self.assertRaises(JobCancellationRequested):
            self.run_one()
        self.assertEqual(self.journal.recoverable(self.comfy.base)[0]["state"], "cancel_requested")


if __name__ == "__main__":
    unittest.main()
