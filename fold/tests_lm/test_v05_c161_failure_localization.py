"""C161 trace-only failure-boundary localization helpers."""
from __future__ import annotations

from copy import deepcopy
import gzip
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

from fold_lm.v05_benchmarks import gate_e_c161_failure_localization as c


def source_report():
    records = [
        {
            "seed": seed,
            "arm": arm,
            "order": order,
            "file": f"queries-{seed}-{arm.lower()}-{order.lower()}.jsonl.gz",
            "sha256": "0" * 64,
            "serialized_bytes": 1,
        }
        for seed in c.HEAD_SEEDS for arm in c.ARMS for order in c.ORDERS
    ]
    summary = {
        "ranker_replay_cases": 41472,
        "original12_replay_cases": 288,
        "ranking_queries": c.EPISODES,
        "candidate_scores": 5308416,
        "episodes": c.EPISODES,
        "failed_episodes": c.EPISODES,
        "controller_decisions": 165888,
        "acquisitions": c.EPISODES,
        "publications": c.EPISODES,
        "answered": 0,
        "output_mutations": 0,
        "serialization_failures": 0,
        "weight_mutations": 0,
        "retrieval_calls": 165888,
        "vectors_scored": 10616832,
        "router_episodes": {str(k): 27648 for k in c.ROUTER_SEEDS},
        "c159_replay_calls": 6528,
        "loaded_rankers": 24,
        "loaded_routers": 3,
        "fresh_seed_count": 0,
        "training_steps": 0,
        "live_query_selection": True,
        "live_cycle_exercised": True,
        "structured_result_exercised": True,
        "answer_generation_exercised": False,
        "production_state_commit": False,
        "new_evidence_epoch": False,
        "live_query_result_gate_passed": False,
        "minimum_controller_margin": 6.14,
        "arms": {
            a: {o: {"cases": 20736, "binding_correct": 0, "semantic_correct": 0} for o in c.ORDERS}
            for a in c.ARMS
        },
    }
    return {
        "experiment_id": c.C160_EXPERIMENT_ID,
        "stage": c.C160_STAGE,
        "status": "FAIL",
        "diagnostic_execution_valid": True,
        "production_runtime_modified": False,
        "gate_e_candidate": False,
        "commit_sha": c.C160_COMMIT,
        "summary": summary,
        "records": records,
    }


def row(j=0, *, cycle_pass=True, reason="REFERENCE_MISMATCH", router_seed=None):
    checks = {"actions": cycle_pass, "statuses": True}
    return {
        "case_id": f"q{j}",
        "router_seed": c.ROUTER_SEEDS[j % 3] if router_seed is None else router_seed,
        "selected_key": f"k{j}",
        "passed": False,
        "cycle": {
            "terminal": "ANSWER_ACTION",
            "steps": [
                {"action": 2, "status": "REFERENCE_UNBOUND"},
                {"action": 0, "status": "RESOLVED"},
            ],
        },
        "cycle_assessment": {"passed": cycle_pass, "checks": checks, "margins": [6.0, 7.0]},
        "output": {"status": "REJECTED", "reason": reason},
        "output_assessment": {"bound": False, "semantic_correct": False, "serialization_ok": True},
    }


def write_trace(root: Path, rows):
    path = root / "trace.jsonl.gz"
    with gzip.open(path, "wt", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, sort_keys=True, separators=(",", ":")) + "\n")
    return {
        "seed": c.HEAD_SEEDS[0],
        "arm": c.ARMS[0],
        "order": c.ORDERS[0],
        "file": path.name,
        "sha256": c.sha(path),
        "serialized_bytes": path.stat().st_size,
    }


class V05C161FailureLocalizationTests(unittest.TestCase):
    def test_blob_is_deterministic_and_rejects_nan(self):
        self.assertEqual(c.blob({"b": 2, "a": 1}), c.blob({"a": 1, "b": 2}))
        with self.assertRaises(ValueError):
            c.blob({"x": float("nan")})

    def test_safe_child_rejects_escape_and_windows_path(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            for name in ("../x", r"..\x", "a/b"):
                with self.assertRaises(c.InvalidInput):
                    c.safe_child(root, name)

    def test_validate_c160_report_accepts_registered_profile(self):
        self.assertEqual(len(c.validate_c160_report(source_report())), 48)

    def test_validate_c160_report_rejects_wrong_identity_or_status(self):
        for key, value in (("experiment_id", "other"), ("status", "PASS"),
                           ("commit_sha", "0" * 40), ("diagnostic_execution_valid", False)):
            report = source_report()
            report[key] = value
            with self.assertRaises(c.InvalidInput):
                c.validate_c160_report(report)

    def test_validate_c160_report_rejects_aggregate_drift(self):
        report = source_report()
        report["summary"]["answered"] = 1
        with self.assertRaises(c.InvalidInput):
            c.validate_c160_report(report)

    def test_validate_c160_report_rejects_stream_identity_drift(self):
        report = source_report()
        report["records"][0] = deepcopy(report["records"][1])
        with self.assertRaises(c.InvalidInput):
            c.validate_c160_report(report)

    def test_analyze_rows_accepts_single_post_cycle_rejection(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            rows = [row(i) for i in range(3)]
            record = write_trace(root, rows)
            with patch.object(c, "EPISODES", 3), patch.object(c, "ROWS_PER_STREAM", 3):
                summary, protected = c.analyze_rows([record], root)
            self.assertTrue(summary["single_post_cycle_rejection"])
            self.assertEqual(summary["localized_reason"], "REFERENCE_MISMATCH")
            self.assertEqual(summary["cycle_passed"], 3)
            self.assertEqual(summary["boundary_counts"], {"POST_CYCLE_TERMINAL_REJECTION": 3})
            self.assertEqual(len(protected), 1)

    def test_analyze_rows_marks_cycle_failure_as_valid_negative_pattern(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            rows = [row(0, cycle_pass=False), row(1), row(2)]
            record = write_trace(root, rows)
            with patch.object(c, "EPISODES", 3), patch.object(c, "ROWS_PER_STREAM", 3):
                summary, _ = c.analyze_rows([record], root)
            self.assertFalse(summary["single_post_cycle_rejection"])
            self.assertEqual(summary["cycle_failed"], 1)
            self.assertEqual(summary["cycle_false_check_counts"]["actions"], 1)

    def test_analyze_rows_marks_multiple_terminal_reasons_as_negative(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            rows = [row(0), row(1, reason="PAYLOAD_MISMATCH"), row(2)]
            record = write_trace(root, rows)
            with patch.object(c, "EPISODES", 3), patch.object(c, "ROWS_PER_STREAM", 3):
                summary, _ = c.analyze_rows([record], root)
            self.assertFalse(summary["single_post_cycle_rejection"])
            self.assertEqual(summary["output_reason_counts"],
                             {"PAYLOAD_MISMATCH": 1, "REFERENCE_MISMATCH": 2})

    def test_analyze_rows_rejects_router_schedule_drift(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            rows = [row(0, router_seed=c.ROUTER_SEEDS[1]), row(1), row(2)]
            record = write_trace(root, rows)
            with patch.object(c, "EPISODES", 3), patch.object(c, "ROWS_PER_STREAM", 3):
                with self.assertRaises(c.InvalidInput):
                    c.analyze_rows([record], root)

    def test_analyze_rows_rejects_trace_hash_tamper(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            record = write_trace(root, [row(i) for i in range(3)])
            record["sha256"] = "f" * 64
            with patch.object(c, "EPISODES", 3), patch.object(c, "ROWS_PER_STREAM", 3):
                with self.assertRaises(c.InvalidInput):
                    c.analyze_rows([record], root)

    def test_run_rejects_wrong_c160_summary_hash_before_analysis(self):
        with TemporaryDirectory() as d:
            root = Path(d)
            source = root / "summary.json"
            source.write_text("{}", encoding="utf-8")
            with self.assertRaises(c.InvalidInput):
                c.run(c160_summary=source, output_dir=root / "out")


if __name__ == "__main__":
    unittest.main()
