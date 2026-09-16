"""C161: localize the universal C160 failure boundary from preserved traces.

Read-only diagnostic. No model execution, retrieval, training, threshold change,
checkpoint selection, or mutation of the accepted C160 artifacts.
"""
from __future__ import annotations

import argparse
from collections import Counter
import gzip
import hashlib
import json
import math
from pathlib import Path, PureWindowsPath
import subprocess
import time

EXPERIMENT_ID = "C161-v5e-c160-failure-boundary-localization"
STAGE = "V5-E-C160-FAILURE-BOUNDARY-LOCALIZATION"
C160_EXPERIMENT_ID = "C160-v5e-live-query-to-terminal-result"
C160_STAGE = "V5-E-LIVE-QUERY-TO-TERMINAL-RESULT"
C160_SHA = "1c99ab5395e67c859a7730e1a9111d4595e2668b85cb56d0a31dfff79aea4bbd"
C160_COMMIT = "d2c1468a19e9a13a8fa47fafe3aad5fa01597aec"
HEAD_SEEDS = tuple(range(20261721, 20261733))
ROUTER_SEEDS = (20261741, 20261742, 20261743)
ARMS = ("WITHIN_FACTOR", "GLOBAL_CONCEPT")
ORDERS = ("CANONICAL", "PERMUTED")
ROWS_PER_STREAM = 1728
STREAMS = 48
EPISODES = 82944


class InvalidInput(ValueError):
    """Invalid source artifact/schema/coverage, not a scientific negative."""


def require(ok, message):
    if not ok:
        raise InvalidInput(message)


def sha(path):
    with Path(path).open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def blob(data):
    return (json.dumps(data, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def safe_child(root, name):
    require(isinstance(name, str) and name not in ("", ".", "..")
            and Path(name).name == PureWindowsPath(name).name == name,
            "Unsafe trace filename")
    path = root / name
    require(path.resolve().parent == root.resolve(), "Trace escaped C160 run directory")
    return path


def validate_c160_report(report):
    require(report.get("experiment_id") == C160_EXPERIMENT_ID
            and report.get("stage") == C160_STAGE
            and report.get("status") == "FAIL"
            and report.get("diagnostic_execution_valid") is True
            and report.get("production_runtime_modified") is False
            and report.get("gate_e_candidate") is False
            and report.get("commit_sha") == C160_COMMIT,
            "Expected accepted valid C160 FAIL source")
    s = report.get("summary")
    require(isinstance(s, dict), "Missing C160 summary")
    expected = {
        "ranker_replay_cases": 41472,
        "original12_replay_cases": 288,
        "ranking_queries": EPISODES,
        "candidate_scores": 5308416,
        "episodes": EPISODES,
        "failed_episodes": EPISODES,
        "controller_decisions": 165888,
        "acquisitions": EPISODES,
        "publications": EPISODES,
        "answered": 0,
        "output_mutations": 0,
        "serialization_failures": 0,
        "weight_mutations": 0,
        "retrieval_calls": 165888,
        "vectors_scored": 10616832,
        "router_episodes": {str(k): 27648 for k in ROUTER_SEEDS},
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
    }
    require(all(s.get(k) == v for k, v in expected.items()), "C160 aggregate/profile drift")
    margin = s.get("minimum_controller_margin")
    require(type(margin) in (int, float) and math.isfinite(margin) and margin > 0,
            "C160 controller margin invalid")
    arms = s.get("arms")
    require(isinstance(arms, dict), "Missing C160 arm summary")
    for arm in ARMS:
        for order in ORDERS:
            require(arms.get(arm, {}).get(order) == {
                "cases": 20736, "binding_correct": 0, "semantic_correct": 0
            }, "C160 arm/layout result drift")
    records = report.get("records")
    require(isinstance(records, list) and len(records) == STREAMS, "Expected 48 C160 trace records")
    identities = []
    for r in records:
        require(isinstance(r, dict), "Malformed C160 trace record")
        identities.append((r.get("seed"), r.get("arm"), r.get("order")))
    require(set(identities) == {(seed, arm, order)
                               for seed in HEAD_SEEDS for arm in ARMS for order in ORDERS}
            and len(identities) == len(set(identities)),
            "C160 trace stream identity coverage drift")
    return records


def _counter_dict(counter):
    return {str(k): int(v) for k, v in sorted(counter.items(), key=lambda kv: str(kv[0]))}


def analyze_rows(records, root):
    totals = Counter()
    cycle_false_checks = Counter()
    output_status = Counter()
    output_reason = Counter()
    boundary = Counter()
    arm_order_boundary = {a: {o: Counter() for o in ORDERS} for a in ARMS}
    router_counts = Counter()
    examples = {}
    protected = {}

    for record in records:
        path = safe_child(root, record["file"])
        require(path.is_file(), f"Missing C160 trace: {path}")
        wanted_sha = record.get("sha256")
        wanted_size = record.get("serialized_bytes")
        require(isinstance(wanted_sha, str) and len(wanted_sha) == 64
                and type(wanted_size) is int and wanted_size > 0,
                "Malformed C160 trace metadata")
        require(sha(path) == wanted_sha and path.stat().st_size == wanted_size,
                "C160 trace bytes mismatch")
        protected[str(path)] = wanted_sha

        seen_case_ids = set()
        row_count = 0
        with gzip.open(path, "rt", encoding="utf-8") as f:
            for j, line in enumerate(f):
                require(line.strip() != "", "Blank C160 trace row")
                row = json.loads(line)
                row_count += 1
                case_id = row.get("case_id")
                require(isinstance(case_id, str) and case_id and case_id not in seen_case_ids,
                        "Duplicate/missing case_id in C160 stream")
                seen_case_ids.add(case_id)
                expected_router = ROUTER_SEEDS[j % 3]
                require(row.get("router_seed") == expected_router, "Router schedule drift in C160 trace")
                router_counts[str(expected_router)] += 1

                selected_key = row.get("selected_key")
                require(isinstance(selected_key, str) and selected_key, "Missing selected key")
                cycle = row.get("cycle")
                ca = row.get("cycle_assessment")
                out = row.get("output")
                oa = row.get("output_assessment")
                require(all(isinstance(x, dict) for x in (cycle, ca, out, oa)),
                        "Malformed C160 trace subrecord")
                require(type(ca.get("passed")) is bool and isinstance(ca.get("checks"), dict)
                        and ca["checks"] and all(type(v) is bool for v in ca["checks"].values()),
                        "Malformed cycle assessment")
                require(isinstance(ca.get("margins"), list)
                        and ca["margins"]
                        and all(type(x) in (int, float) and math.isfinite(x) for x in ca["margins"]),
                        "Malformed cycle margins")
                require(type(oa.get("bound")) is bool
                        and type(oa.get("semantic_correct")) is bool
                        and type(oa.get("serialization_ok")) is bool,
                        "Malformed output assessment")
                require(type(row.get("passed")) is bool, "Malformed C160 pass bit")
                require(row["passed"] is False, "C160 source no longer represents the accepted universal FAIL")
                status, reason = out.get("status"), out.get("reason")
                require(isinstance(status, str) and status and isinstance(reason, str) and reason,
                        "Malformed terminal output status/reason")
                output_status[status] += 1
                output_reason[reason] += 1
                totals["episodes"] += 1
                totals["cycle_passed"] += int(ca["passed"])
                totals["cycle_failed"] += int(not ca["passed"])
                totals["output_bound"] += int(oa["bound"])
                totals["output_unbound"] += int(not oa["bound"])
                totals["serialization_ok"] += int(oa["serialization_ok"])
                totals["serialization_bad"] += int(not oa["serialization_ok"])
                for name, ok in ca["checks"].items():
                    if not ok:
                        cycle_false_checks[name] += 1

                if ca["passed"] and status == "ANSWERED" and oa["bound"]:
                    b = "COMPOSED_ANSWER"
                elif ca["passed"]:
                    b = "POST_CYCLE_TERMINAL_REJECTION"
                elif status == "ANSWERED" and oa["bound"]:
                    b = "CYCLE_ASSESSMENT_FAILURE_WITH_ANSWER"
                else:
                    b = "CYCLE_OR_EARLIER_AND_TERMINAL_FAILURE"
                boundary[b] += 1
                arm_order_boundary[record["arm"]][record["order"]][b] += 1

                key = f"{b}|{reason}"
                if key not in examples:
                    steps = cycle.get("steps")
                    require(isinstance(steps, list) and steps, "Missing compact cycle steps")
                    examples[key] = {
                        "seed": record["seed"],
                        "arm": record["arm"],
                        "order": record["order"],
                        "case_id": case_id,
                        "router_seed": row["router_seed"],
                        "selected_key": selected_key,
                        "output_status": status,
                        "output_reason": reason,
                        "cycle_terminal": cycle.get("terminal"),
                        "actions": [s.get("action") for s in steps],
                        "statuses": [s.get("status") for s in steps],
                        "false_cycle_checks": sorted(k for k, v in ca["checks"].items() if not v),
                    }

        require(row_count == ROWS_PER_STREAM and len(seen_case_ids) == ROWS_PER_STREAM,
                "C160 stream row coverage mismatch")

    require(totals["episodes"] == EPISODES, "C160 trace episode coverage mismatch")
    require(dict(router_counts) == {str(k): EPISODES // 3 for k in ROUTER_SEEDS},
            "C160 trace router coverage mismatch")

    single_post_cycle_rejection = bool(
        totals["cycle_passed"] == EPISODES
        and totals["cycle_failed"] == 0
        and output_status == Counter({"REJECTED": EPISODES})
        and len(output_reason) == 1
        and totals["output_bound"] == 0
        and totals["serialization_ok"] == EPISODES
        and not cycle_false_checks
        and boundary == Counter({"POST_CYCLE_TERMINAL_REJECTION": EPISODES})
    )

    summary = {
        **{k: int(v) for k, v in totals.items()},
        "output_status_counts": _counter_dict(output_status),
        "output_reason_counts": _counter_dict(output_reason),
        "cycle_false_check_counts": _counter_dict(cycle_false_checks),
        "boundary_counts": _counter_dict(boundary),
        "router_episodes": _counter_dict(router_counts),
        "arm_order_boundary_counts": {
            a: {o: _counter_dict(arm_order_boundary[a][o]) for o in ORDERS} for a in ARMS
        },
        "single_post_cycle_rejection": single_post_cycle_rejection,
        "localized_reason": next(iter(output_reason)) if single_post_cycle_rejection else None,
        "trace_files": len(records),
        "examples": examples,
    }
    return summary, protected


def run(*, c160_summary, output_dir):
    output_dir.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    require(sha(c160_summary) == C160_SHA, "C160 summary hash mismatch")
    report = json.loads(c160_summary.read_text(encoding="utf-8"))
    records = validate_c160_report(report)
    summary, protected = analyze_rows(records, c160_summary.parent)
    status = "PASS" if summary["single_post_cycle_rejection"] else "FAIL"
    result = {
        "experiment_id": EXPERIMENT_ID,
        "stage": STAGE,
        "status": status,
        "diagnostic_execution_valid": True,
        "production_runtime_modified": False,
        "gate_e_candidate": False,
        "commit_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "C160_summary_sha256": C160_SHA,
        "input_sha256": {str(c160_summary): C160_SHA, **protected},
        "summary": summary,
        "fresh_seed_count": 0,
        "training_steps": 0,
        "model_execution": False,
        "retrieval_execution": False,
        "live_cycle_execution": False,
        "wall_clock_seconds": time.perf_counter() - started,
        "interpretation": (
            "PASS means every C160 episode passed the stored C158 cycle assessment and "
            "was rejected at the same post-cycle terminal reason. FAIL is a valid negative "
            "for that single-boundary hypothesis; neither status repairs or reruns C160."
        ),
    }
    tmp = output_dir / "summary.partial.json"
    tmp.write_bytes(blob(result))
    tmp.replace(output_dir / "summary.json")
    return result


def main():
    p = argparse.ArgumentParser(description="C161 read-only localization of the universal C160 failure")
    p.add_argument("--c160-summary", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    args = p.parse_args()
    print("C161 source=C160 preserved traces; model/retrieval/live-cycle execution=0", flush=True)
    print("C161 hypothesis=single post-cycle terminal rejection after accepted C158 cycle assessment", flush=True)
    report = run(**vars(args))
    print("=== C161 RESULT ===", flush=True)
    print(json.dumps(report, indent=2, allow_nan=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
