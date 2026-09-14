from __future__ import annotations

import hashlib
import json
import statistics
from pathlib import Path

import torch

from fold_lm.v05.post_transition_recovery import APPLIED, NOT_APPLIED, STILL_UNKNOWN
from fold_lm.v05_benchmarks import gate_e_c113_stale_eligibility_preflight as c113
from fold_lm.v05_benchmarks import gate_e_c127_post_transition_crash_falsification as c127
from fold_lm.v05_benchmarks import gate_e_c128_ownership_helper as helper

EXPERIMENT_ID = "C128-v5e-concurrent-recovery-ownership-falsification"
SEEDS = (20261481, 20261482, 20261483)


def _sha(path: Path) -> str:
    return hashlib.file_digest(path.open("rb"), "sha256").hexdigest()


def _stats(values):
    return {"mean": statistics.mean(values), "median": statistics.median(values), "min": min(values), "max": max(values)}


def _hidden_invariant(rows):
    groups = {}
    for row in rows:
        key = (tuple(row["visible"]), tuple(row["actual"]), row["transition_outcome"], row["workers"])
        groups.setdefault(key, []).append(row["trace"])
    return float(all(len(v) == 2 and v[0] == v[1] for v in groups.values()))


def _measure(router, device):
    control, _ = c127._measure(router, device)
    rows = helper.rows_for(router, device)
    active = [r for r in rows if r["transition_outcome"] != "NONE_AVAILABLE"]
    applied = [r for r in active if r["transition_outcome"] == APPLIED]
    not_applied = [r for r in active if r["transition_outcome"] == NOT_APPLIED]
    unknown = [r for r in active if r["transition_outcome"] == STILL_UNKNOWN]
    none = [r for r in rows if r["transition_outcome"] == "NONE_AVAILABLE"]
    m = {
        "scenario_pass_rate": sum(r["passed"] for r in rows) / len(rows),
        "c127_control_gate_rate": float(control["gate_passed"]),
        "naive_ownership_race_detection_rate": float(helper.negative_control_detected()),
        "single_owner_rate": sum(r["winner_count"] == 1 for r in active) / len(active),
        "owner_identity_rate": sum(r["owner_matches"] for r in active) / len(active),
        "loser_zero_action_rate": sum(r["loser_action_count"] == 0 for r in active) / len(active),
        "ownership_release_rate": sum(r["ownership_released"] for r in active) / len(active),
        "applied_zero_replay_rate": sum(r["replay_count"] == 0 for r in applied) / len(applied),
        "applied_complete_once_rate": sum(r["complete_count"] == 1 for r in applied) / len(applied),
        "applied_one_logical_effect_rate": sum(r["logical_effect_count"] == 1 for r in applied) / len(applied),
        "not_applied_one_replay_rate": sum(r["replay_count"] == 1 for r in not_applied) / len(not_applied),
        "not_applied_complete_once_rate": sum(r["complete_count"] == 1 for r in not_applied) / len(not_applied),
        "not_applied_one_logical_effect_rate": sum(r["logical_effect_count"] == 1 for r in not_applied) / len(not_applied),
        "unknown_zero_replay_rate": sum(r["replay_count"] == 0 for r in unknown) / len(unknown),
        "unknown_zero_complete_rate": sum(r["complete_count"] == 0 for r in unknown) / len(unknown),
        "unknown_pending_preserved_rate": sum(r["pending_after"] for r in unknown) / len(unknown),
        "unknown_effect_count_unasserted_rate": sum(r["logical_effect_count"] is None for r in unknown) / len(unknown),
        "confirmed_none_stop_rate": sum(r["final"] == "UNRESOLVED" for r in none) / len(none),
        "hidden_trace_invariance": _hidden_invariant(rows),
        "scenario_count": len(rows),
        "concurrent_recovery_case_count": len(active),
    }
    for workers in helper.WORKERS:
        subset = [r for r in active if r["workers"] == workers]
        m[f"workers_{workers}_single_owner_rate"] = sum(r["winner_count"] == 1 for r in subset) / len(subset)
    deciding = [k for k in m if k.endswith("_rate") or k == "hidden_trace_invariance"]
    m["gate_passed"] = all(m[k] == 1.0 for k in deciding)
    return m, rows


def run(*, protected_result_path: Path, c127_summary_path: Path, output_dir: Path):
    prior = json.loads(c127_summary_path.read_text(encoding="utf-8"))
    if prior.get("experiment_id") != c127.EXPERIMENT_ID or prior.get("status") != "PASS" or not prior.get("summary", {}).get("post_transition_crash_falsification_gate_passed"):
        raise RuntimeError("C128 requires accepted C127")
    if not torch.cuda.is_available():
        raise RuntimeError("C128 requires CUDA")
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
        print(f"[C128] seed={seed} scenario={m['scenario_pass_rate']:.6f} owner={m['single_owner_rate']:.6f} naive_detect={m['naive_ownership_race_detection_rate']:.6f} pass={passed}", flush=True)
    after = _sha(protected_result_path)
    if before != after:
        raise RuntimeError("protected C37 result changed during C128")
    ms = [r["metrics"] for r in records]
    all_pass = all(r["validation_passed"] for r in records)
    keys = [k for k in ms[0] if k.endswith("_rate") or k == "hidden_trace_invariance"]
    summary = {
        "fresh_seeds": list(SEEDS),
        "validation_base": 3,
        "worker_counts": list(helper.WORKERS),
        "scenario_count": ms[0]["scenario_count"],
        "concurrent_recovery_case_count": ms[0]["concurrent_recovery_case_count"],
        **{k: _stats([m[k] for m in ms]) for k in keys},
        "all_validation_passed": all_pass,
        "concurrent_recovery_ownership_falsification_gate_passed": all_pass,
    }
    report = {
        "experiment_id": EXPERIMENT_ID,
        "stage": "V5-E-RUNTIME-CONCURRENT-RECOVERY-OWNERSHIP-FALSIFICATION",
        "status": "PASS",
        "summary": summary,
        "records": records,
        "C127_summary_sha256": _sha(c127_summary_path),
        "C37_result_sha256_before": before,
        "C37_result_sha256_after": after,
        "production_runtime_modified": True,
        "gate_e_candidate": False,
        "limitations": [
            "C128 tests in-process Python-thread recovery ownership only",
            "C128 does not test owner death, lease expiry, takeover, or stale-owner fencing",
            "C128 does not establish distributed storage ownership semantics",
            "C128 remains synthetic",
        ],
    }
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "summary.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    return report
