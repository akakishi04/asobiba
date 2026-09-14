from __future__ import annotations

import hashlib
import json
import statistics
from pathlib import Path

import torch

from fold_lm.v05.post_transition_recovery import APPLIED, NOT_APPLIED, STILL_UNKNOWN
from fold_lm.v05_benchmarks import gate_e_c113_stale_eligibility_preflight as c113
from fold_lm.v05_benchmarks import gate_e_c126_restart_recovery_falsification as c126
from fold_lm.v05_benchmarks import gate_e_c127_transition_recovery_helper as helper

EXPERIMENT_ID = "C127-v5e-post-transition-crash-falsification"
SEEDS = (20261471, 20261472, 20261473)


def _sha(path: Path) -> str:
    return hashlib.file_digest(path.open("rb"), "sha256").hexdigest()


def _stats(values):
    return {"mean": statistics.mean(values), "median": statistics.median(values), "min": min(values), "max": max(values)}


def _hidden_invariant(rows):
    groups = {}
    for row in rows:
        key = (tuple(row["visible"]), tuple(row["actual"]), row["transition_outcome"], row["restarts"])
        groups.setdefault(key, []).append(row["trace"])
    return float(all(len(v) == 2 and v[0] == v[1] for v in groups.values()))


def _measure(router, device):
    control, _ = c126._measure(router, device)
    rows = helper.rows_for(router, device)
    active = [r for r in rows if r["transition_outcome"] != "NONE_AVAILABLE"]
    applied = [r for r in active if r["transition_outcome"] == APPLIED]
    not_applied = [r for r in active if r["transition_outcome"] == NOT_APPLIED]
    unknown = [r for r in active if r["transition_outcome"] == STILL_UNKNOWN]
    none = [r for r in rows if r["transition_outcome"] == "NONE_AVAILABLE"]
    m = {
        "scenario_pass_rate": sum(r["passed"] for r in rows) / len(rows),
        "c126_control_gate_rate": float(control["gate_passed"]),
        "applied_zero_replay_rate": sum(r["replay_count"] == 0 for r in applied) / len(applied),
        "applied_complete_once_rate": sum(r["complete_count"] == 1 for r in applied) / len(applied),
        "applied_one_logical_effect_rate": sum(r["logical_effect_count"] == 1 for r in applied) / len(applied),
        "not_applied_one_replay_rate": sum(r["replay_count"] == 1 for r in not_applied) / len(not_applied),
        "not_applied_same_key_rate": sum(r["same_key"] for r in not_applied) / len(not_applied),
        "not_applied_complete_once_rate": sum(r["complete_count"] == 1 for r in not_applied) / len(not_applied),
        "not_applied_one_logical_effect_rate": sum(r["logical_effect_count"] == 1 for r in not_applied) / len(not_applied),
        "unknown_zero_replay_rate": sum(r["replay_count"] == 0 for r in unknown) / len(unknown),
        "unknown_zero_complete_rate": sum(r["complete_count"] == 0 for r in unknown) / len(unknown),
        "unknown_pending_preserved_rate": sum(r["pending_after"] for r in unknown) / len(unknown),
        "unknown_effect_count_unasserted_rate": sum(r["logical_effect_count"] is None for r in unknown) / len(unknown),
        "duplicate_reject_rate": sum(r["duplicate_rejected"] for r in active) / len(active),
        "confirmed_none_stop_rate": sum(r["final"] == "UNRESOLVED" for r in none) / len(none),
        "hidden_trace_invariance": _hidden_invariant(rows),
        "scenario_count": len(rows),
        "post_transition_crash_case_count": len(active),
    }
    for restarts in helper.RESTARTS:
        subset = [r for r in active if r["restarts"] == restarts]
        m[f"restarts_{restarts}_recovery_rate"] = sum(r["passed"] for r in subset) / len(subset)
    deciding = [k for k in m if k.endswith("_rate") or k == "hidden_trace_invariance"]
    m["gate_passed"] = all(m[k] == 1.0 for k in deciding)
    return m, rows


def run(*, protected_result_path: Path, c126_summary_path: Path, output_dir: Path):
    prior = json.loads(c126_summary_path.read_text(encoding="utf-8"))
    if prior.get("experiment_id") != c126.EXPERIMENT_ID or prior.get("status") != "PASS" or not prior.get("summary", {}).get("restart_recovery_falsification_gate_passed"):
        raise RuntimeError("C127 requires accepted C126")
    if not torch.cuda.is_available():
        raise RuntimeError("C127 requires CUDA")
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
        print(f"[C127] seed={seed} scenario={m['scenario_pass_rate']:.6f} applied={m['applied_zero_replay_rate']:.6f} not_applied={m['not_applied_one_replay_rate']:.6f} unknown={m['unknown_pending_preserved_rate']:.6f} pass={passed}", flush=True)
    after = _sha(protected_result_path)
    if before != after:
        raise RuntimeError("protected C37 result changed during C127")
    ms = [r["metrics"] for r in records]
    all_pass = all(r["validation_passed"] for r in records)
    keys = [k for k in ms[0] if k.endswith("_rate") or k == "hidden_trace_invariance"]
    summary = {
        "fresh_seeds": list(SEEDS),
        "validation_base": 3,
        "restart_counts": list(helper.RESTARTS),
        "scenario_count": ms[0]["scenario_count"],
        "post_transition_crash_case_count": ms[0]["post_transition_crash_case_count"],
        **{k: _stats([m[k] for m in ms]) for k in keys},
        "all_validation_passed": all_pass,
        "post_transition_crash_falsification_gate_passed": all_pass,
    }
    report = {
        "experiment_id": EXPERIMENT_ID,
        "stage": "V5-E-RUNTIME-POST-TRANSITION-CRASH-FALSIFICATION",
        "status": "PASS",
        "summary": summary,
        "records": records,
        "C126_summary_sha256": _sha(c126_summary_path),
        "C37_result_sha256_before": before,
        "C37_result_sha256_after": after,
        "production_runtime_modified": True,
        "gate_e_candidate": False,
        "limitations": [
            "C127 assumes an authoritative reconciliation source can classify the downstream transition as APPLIED, NOT_APPLIED, or STILL_UNKNOWN",
            "C127 does not prove filesystem transaction durability or distributed recovery ownership",
            "C127 remains synthetic",
        ],
    }
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "summary.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    return report
