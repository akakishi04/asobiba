from __future__ import annotations

import hashlib
import json
import statistics
from pathlib import Path

import torch

from fold_lm.v05_benchmarks import gate_e_c113_stale_eligibility_preflight as c113
from fold_lm.v05_benchmarks import gate_e_c125_atomic_claim_falsification as c125
from fold_lm.v05_benchmarks import gate_e_c126_recovery_helper as helper

EXPERIMENT_ID = "C126-v5e-restart-recovery-falsification"
SEEDS = (20261461, 20261462, 20261463)


def _sha(path: Path) -> str:
    return hashlib.file_digest(path.open("rb"), "sha256").hexdigest()


def _stats(values):
    return {"mean": statistics.mean(values), "median": statistics.median(values), "min": min(values), "max": max(values)}


def _hidden_invariant(rows):
    groups = {}
    for row in rows:
        key = (tuple(row["visible"]), tuple(row["actual"]), row["outcome"], row["restarts"])
        groups.setdefault(key, []).append(row["trace"])
    return float(all(len(v) == 2 and v[0] == v[1] for v in groups.values()))


def _measure(router, device):
    control, _ = c125._measure(router, device)
    rows = helper.rows_for(router, device)
    active = [r for r in rows if r["outcome"] != "NONE_AVAILABLE"]
    applied = [r for r in active if r["outcome"] == "RECONCILED_APPLIED"]
    not_applied = [r for r in active if r["outcome"] == "RECONCILED_NOT_APPLIED"]
    unknown = [r for r in active if r["outcome"] == "STILL_UNKNOWN"]
    none = [r for r in rows if r["outcome"] == "NONE_AVAILABLE"]
    m = {
        "scenario_pass_rate": sum(r["passed"] for r in rows) / len(rows),
        "c125_control_gate_rate": float(control["gate_passed"]),
        "naive_processed_set_failure_detected_rate": float(helper.naive_processed_set_loses_pending_work()),
        "first_claim_rate": sum(r["first_claim"] for r in active) / len(active),
        "pending_snapshot_survival_rate": sum(r["pending_survived"] for r in active) / len(active),
        "restart_duplicate_reject_rate": sum(r["restart_duplicate_rejected"] for r in active) / len(active),
        "exactly_one_resume_rate": sum(r["resume_count"] == 1 for r in active) / len(active),
        "completion_persistence_rate": sum(r["completion_persisted"] for r in active) / len(active),
        "post_completion_duplicate_reject_rate": sum(r["post_completion_duplicate_rejected"] for r in active) / len(active),
        "applied_total_one_commit_rate": sum(r["commit"] == 1 for r in applied) / len(applied),
        "applied_total_zero_retry_rate": sum(r["retry"] == 0 for r in applied) / len(applied),
        "not_applied_total_one_retry_rate": sum(r["retry"] == 1 for r in not_applied) / len(not_applied),
        "not_applied_total_one_commit_rate": sum(r["commit"] == 1 for r in not_applied) / len(not_applied),
        "unknown_total_zero_commit_rate": sum(r["commit"] == 0 for r in unknown) / len(unknown),
        "unknown_total_zero_retry_rate": sum(r["retry"] == 0 for r in unknown) / len(unknown),
        "unknown_total_zero_fallback_rate": sum(r["fallback"] == 0 for r in unknown) / len(unknown),
        "confirmed_none_stop_rate": sum(r["final"] == "UNRESOLVED" for r in none) / len(none),
        "hidden_trace_invariance": _hidden_invariant(rows),
        "scenario_count": len(rows),
        "restart_recovery_case_count": len(active),
    }
    for restarts in helper.RESTARTS:
        subset = [r for r in active if r["restarts"] == restarts]
        m[f"restarts_{restarts}_recovery_rate"] = sum(r["passed"] for r in subset) / len(subset)
    deciding = [k for k in m if k.endswith("_rate") or k == "hidden_trace_invariance"]
    m["gate_passed"] = all(m[k] == 1.0 for k in deciding)
    return m, rows


def run(*, protected_result_path: Path, c125_summary_path: Path, output_dir: Path):
    prior = json.loads(c125_summary_path.read_text(encoding="utf-8"))
    if prior.get("experiment_id") != c125.EXPERIMENT_ID or prior.get("status") != "PASS" or not prior.get("summary", {}).get("atomic_receipt_claim_falsification_gate_passed"):
        raise RuntimeError("C126 requires accepted C125")
    if not torch.cuda.is_available():
        raise RuntimeError("C126 requires CUDA")
    before = _sha(protected_result_path)
    device = torch.device("cuda")
    torch.cuda.set_device(0)
    torch.set_num_threads(2)
    torch.set_float32_matmul_precision("highest")
    records = []
    for seed in SEEDS:
        router, loss = c113._train_router(seed, device)
        m, rows = _measure(router, device)
        passed = bool(m["gate_passed"])
        records.append({"seed": seed, "final_loss": loss, "metrics": m, "scenarios": rows, "validation_passed": passed})
        print(f"[C126] seed={seed} scenario={m['scenario_pass_rate']:.6f} pending={m['pending_snapshot_survival_rate']:.6f} resume={m['exactly_one_resume_rate']:.6f} pass={passed}", flush=True)
    after = _sha(protected_result_path)
    if before != after:
        raise RuntimeError("protected C37 result changed during C126")
    ms = [r["metrics"] for r in records]
    all_pass = all(r["validation_passed"] for r in records)
    keys = [k for k in ms[0] if k.endswith("_rate") or k == "hidden_trace_invariance"]
    summary = {
        "fresh_seeds": list(SEEDS),
        "validation_base": 3,
        "restart_counts": list(helper.RESTARTS),
        "scenario_count": ms[0]["scenario_count"],
        "restart_recovery_case_count": ms[0]["restart_recovery_case_count"],
        **{k: _stats([m[k] for m in ms]) for k in keys},
        "all_validation_passed": all_pass,
        "restart_recovery_falsification_gate_passed": all_pass,
    }
    report = {
        "experiment_id": EXPERIMENT_ID,
        "stage": "V5-E-RUNTIME-RESTART-RECOVERY-FALSIFICATION",
        "status": "PASS",
        "summary": summary,
        "records": records,
        "C125_summary_sha256": _sha(c125_summary_path),
        "C37_result_sha256_before": before,
        "C37_result_sha256_after": after,
        "production_runtime_modified": True,
        "gate_e_candidate": False,
        "limitations": [
            "C126 models persisted snapshots and restart reconstruction; it does not prove filesystem fsync durability",
            "C126 crash point is after claim persistence and before downstream transition begins",
            "C126 does not test concurrent recovery ownership after restart",
            "C126 remains synthetic",
        ],
    }
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "summary.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    return report
