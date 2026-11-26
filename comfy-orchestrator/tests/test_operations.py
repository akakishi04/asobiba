"""Timing estimates, asset reuse, storage accounting and journal indexing."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from comfy_orchestrator.asset_store import save_snapshot
from comfy_orchestrator.jobs import JobJournal
from comfy_orchestrator.long_video import series_index
from comfy_orchestrator.project_lock import project_lock
from comfy_orchestrator.prompt_cache import PromptCache
from comfy_orchestrator.storage_report import storage_report
from comfy_orchestrator.timing import Estimate, TimingStore, observe, report_estimate

BACKEND = "http://localhost:8188"
WORKFLOW = "minimax_h3_i2v"


class OperationsTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()

    def test_eta_median_exact_and_bounded_frame_scaling(self):
        book = TimingStore(self.root / "times.sqlite3")
        p = {"width": 864, "height": 480, "frames": 124, "steps": 8, "h3_model": "w4a8", "seed": 4}
        self.assertIsNone(book.estimate(BACKEND, WORKFLOW, p))
        for i, value in enumerate((10, 20, 100)):
            book.record(str(i), BACKEND, WORKFLOW, p, value)
        self.assertEqual(book.estimate(BACKEND, WORKFLOW, {**p, "seed": 99, "positive_prompt": "new"}), Estimate(20, 3))
        self.assertEqual(book.estimate(BACKEND, WORKFLOW, {**p, "frames": 248}), Estimate(40, 3, True))
        self.assertIsNone(book.estimate(BACKEND, WORKFLOW, {**p, "frames": 362}))
        self.assertIsNone(book.estimate(BACKEND, WORKFLOW, {**p, "steps": 9}))
        self.assertIsNone(book.estimate("http://other:8188", WORKFLOW, p))
        self.assertEqual(book.sequence(BACKEND, WORKFLOW, [p, p, {**p, "frames": 248}]), Estimate(80, 3, True))

    def test_bootstrap_imports_only_unambiguous_success_once(self):
        journal = JobJournal(self.root / "jobs")
        p = {"width": 864, "height": 480, "frames": 124, "steps": 8}
        for state, seconds, error in (("collected", 90, None), ("failed", 2, "failed"), ("completed", 3, "uncertain")):
            record = journal.create(BACKEND, WORKFLOW, "i2v", p, {})
            journal.update(record["job_id"], state=state, elapsed_seconds=seconds, error=error)
        journal.timings.bootstrap(journal.root)
        journal.timings.bootstrap(journal.root)
        self.assertEqual(journal.timings.estimate(BACKEND, WORKFLOW, p), Estimate(90, 1))

    def test_timing_observer_is_scoped(self):
        events = []
        report_estimate(Estimate(1, 1))
        with observe(events.append):
            report_estimate(Estimate(15, 2), label="残カット生成待ち")
        report_estimate(None)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0][0], "timing")
        self.assertEqual(events[0][1]["estimate"], Estimate(15, 2))

    def test_series_index_reads_once_and_filters_other_runs(self):
        journal = JobJournal(self.root / "jobs")
        for run, index, state in (("a", 0, "completed"), ("a", 1, "unknown"), ("b", 0, "completed"), ("a", 2, "failed")):
            row = journal.create(BACKEND, WORKFLOW, "i2v", {}, {},
                                 {"long_run_id": run, "long_segment": index})
            journal.update(row["job_id"], state=state)
        with patch.object(journal, "read", wraps=journal.read) as read:
            index = series_index(journal, "a", BACKEND)
        self.assertEqual(read.call_count, 4)
        self.assertEqual(set(index), {0, 1})
        self.assertEqual(index[1][0]["state"], "unknown")

    def test_snapshot_aliases_are_independent_from_user_original(self):
        source = self.root / "original.png"
        source.write_bytes(b"reference")
        pool = self.root / "data" / "asset_pool"
        a = self.root / "data" / "references" / "a.png"
        b = self.root / "data" / "jobs" / "b.png"
        save_snapshot(source, a, pool)
        save_snapshot(source, b, pool)
        source.write_bytes(b"changed!")
        self.assertEqual(a.read_bytes(), b"reference")
        self.assertEqual(b.read_bytes(), b"reference")
        self.assertFalse(os.path.samefile(source, a))
        if os.path.samefile(a, b):
            report = storage_report(self.root)
            self.assertEqual(report["unique_bytes"], len(b"reference"))
            self.assertEqual(report["shared_bytes"], 2 * len(b"reference"))
        a.unlink()
        self.assertEqual(b.read_bytes(), b"reference")

    def test_unsupported_hardlink_uses_copy(self):
        source = self.root / "input.png"
        source.write_bytes(b"copy")
        with patch("comfy_orchestrator.asset_store.os.link", side_effect=OSError("unsupported")):
            target = save_snapshot(source, self.root / "a.png", self.root / "pool")
        self.assertEqual(target.read_bytes(), b"copy")
        self.assertFalse(os.path.samefile(source, target))

    def test_pool_corruption_is_not_reused_or_overwritten(self):
        source = self.root / "input.png"
        source.write_bytes(b"good")
        pool = self.root / "pool"
        a = save_snapshot(source, self.root / "a.png", pool)
        blobs = list(pool.glob("*.blob"))
        if not blobs:
            self.skipTest("hardlinks unavailable")
        blobs[0].write_bytes(b"evil")
        b = save_snapshot(source, self.root / "b.png", pool)
        self.assertEqual(b.read_bytes(), b"good")
        self.assertEqual(blobs[0].read_bytes(), b"evil")

    def test_storage_counts_regular_files(self):
        out = self.root / "outputs"
        out.mkdir()
        (out / "result.mp4").write_bytes(b"x" * 25)
        report = storage_report(self.root)
        self.assertEqual(report["logical_bytes"], 25)
        self.assertEqual(report["unique_bytes"], 25)
        self.assertGreater(report["disk_total_bytes"], 0)

    def test_cache_counts_hits_misses_and_entries(self):
        cache = PromptCache(self.root / ".cache" / "plans.sqlite3")
        self.assertIsNone(cache.get("missing"))
        cache.put("a", {"positive": "x"})
        self.assertEqual(cache.get("a"), {"positive": "x"})
        stats = cache.stats()
        self.assertEqual((stats["hits"], stats["misses"], stats["entries"], stats["writes"]), (1, 1, 1, 1))
        cache.clear()
        self.assertEqual(cache.stats()["entries"], 0)

    def test_project_lock_blocks_other_process_and_releases(self):
        folder = self.root / "project"
        folder.mkdir()
        command = [sys.executable, "-c",
                   "import sys; from pathlib import Path; from comfy_orchestrator.project_lock import project_lock\nwith project_lock(Path(sys.argv[1])): pass",
                   str(folder)]
        with project_lock(folder):
            blocked = subprocess.run(command, capture_output=True, timeout=10)
        self.assertNotEqual(blocked.returncode, 0)
        self.assertIn(b"OrchestratorError", blocked.stderr)
        released = subprocess.run(command, capture_output=True, timeout=10)
        self.assertEqual(released.returncode, 0, released.stderr)


if __name__ == "__main__":
    unittest.main()
