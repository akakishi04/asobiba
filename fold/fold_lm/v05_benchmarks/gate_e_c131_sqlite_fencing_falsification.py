from __future__ import annotations

import hashlib
import json
import statistics
from pathlib import Path

import torch

from fold_lm.v05_benchmarks import gate_e_c113_stale_eligibility_preflight as c113
from fold_lm.v05_benchmarks import gate_e_c130_lease_renewal_falsification as c130
from fold_lm.v05_benchmarks import gate_e_c131_metrics as metrics
from fold_lm.v05_benchmarks import gate_e_c131_sqlite_case as case
from fold_lm.v05_benchmarks import gate_e_c131_sqlite_rows as rows_mod

EXPERIMENT_ID = "C131-v5e-sqlite-storage-fencing-falsification"
SEEDS = (20261511, 20261512, 20261513)


def _sha(path: Path) -> str:
    return hashlib.file_digest(path.open("rb"), "sha256").hexdigest()


def _stats(values):
    return {"mean": statistics.mean(values), "median": statistics.median(values), "min": min(values), "max": max(values)}


def _measure(router, device, db_path: Path):
    control, _ = c130._measure(router, device)
    rows = rows_mod.rows_for(router, device, db_path)
    m = metrics.summarize(rows)
    m["c130_control_gate_rate"] = float(control["gate_passed"])
    deciding = [k for k in m if k.endswith("_rate") or k == "hidden_trace_invariance"]
    m["gate_passed"] = all(m[k] == 1.0 for k in deciding)
    return m, rows


def run(*, protected_result_path: Path, c130_summary_path: Path, output_dir: Path):
    prior = json.loads(c130_summary_path.read_text(encoding="utf-8"))
    if prior.get("experiment_id") != c130.EXPERIMENT_ID or prior.get("status") != "PASS" or not prior.get("summary", {}).get("lease_renewal_boundary_falsification_gate_passed"):
        raise RuntimeError("C131 requires accepted C130")
    if not torch.cuda.is_available():
        raise RuntimeError("C131 requires CUDA")
    before = _sha(protected_result_path)
    output_dir.mkdir(parents=True, exist_ok=False)
    device = torch.device("cuda")
    torch.cuda.set_device(0)
    torch.set_num_threads(2)
    torch.set_float32_matmul_precision("highest")
    records = []
    for seed in SEEDS:
        router, loss = c113._train_router(seed, device)
        m, rows = _measure(router, device, output_dir / f"sqlite-fencing-{seed}.db")
        passed = bool(m["gate_passed"])
        records.append({"seed": seed, "final_loss": loss, "metrics": m, "scenarios": rows, "validation_passed": passed})
        print(f"[C131] seed={seed} scenario={m['scenario_pass_rate']:.6f} takeover={m['storage_single_takeover_rate']:.6f} stale_reject={m['storage_stale_write_reject_rate']:.6f} pass={passed}", flush=True)
    after = _sha(protected_result_path)
    if before != after:
        raise RuntimeError("protected C37 result changed during C131")
    ms = [r["metrics"] for r in records]
    all_pass = all(r["validation_passed"] for r in records)
    keys = [k for k in ms[0] if k.endswith("_rate") or k == "hidden_trace_invariance"]
    summary = {
        "fresh_seeds": list(SEEDS),
        "validation_base": 3,
        "worker_counts": list(case.WORKERS),
        "sqlite_journal_mode": "WAL",
        "sqlite_synchronous": "FULL",
        "scenario_count": ms[0]["scenario_count"],
        "storage_fencing_case_count": ms[0]["storage_fencing_case_count"],
        **{k: _stats([m[k] for m in ms]) for k in keys},
        "all_validation_passed": all_pass,
        "sqlite_storage_fencing_falsification_gate_passed": all_pass,
    }
    report = {
        "experiment_id": EXPERIMENT_ID,
        "stage": "V5-E-RUNTIME-SQLITE-STORAGE-FENCING-FALSIFICATION",
        "status": "PASS",
        "summary": summary,
        "records": records,
        "C130_summary_sha256": _sha(c130_summary_path),
        "C37_result_sha256_before": before,
        "C37_result_sha256_after": after,
        "production_runtime_modified": True,
        "gate_e_candidate": False,
        "limitations": [
            "C131 uses a local SQLite file rather than a distributed database",
            "C131 uses Python threads with independent SQLite transactions rather than independent OS processes",
            "C131 does not simulate power loss or filesystem corruption",
            "C131 still uses deterministic logical time for lease expiry",
        ],
    }
    (output_dir / "summary.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    return report
