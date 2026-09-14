from __future__ import annotations

import hashlib
import json
import statistics
from pathlib import Path

import torch

from fold_lm.v05_benchmarks import gate_e_c113_stale_eligibility_preflight as c113
from fold_lm.v05_benchmarks import gate_e_c131_sqlite_fencing_falsification as c131
from fold_lm.v05_benchmarks import gate_e_c132_metrics as metrics
from fold_lm.v05_benchmarks import gate_e_c132_process_case as case

EXPERIMENT_ID = "C132-v5e-os-process-sqlite-fencing-falsification"
SEEDS = (20261521, 20261522, 20261523)


def _sha(path: Path) -> str:
    return hashlib.file_digest(path.open("rb"), "sha256").hexdigest()


def _stats(values):
    return {"mean": statistics.mean(values), "median": statistics.median(values), "min": min(values), "max": max(values)}


def _process_rows(seed: int, output_dir: Path) -> list[dict]:
    rows = []
    db_path = output_dir / f"c132-process-{seed}.db"
    matrix_dir = output_dir / f"process-matrix-{seed}"
    for workers in case.WORKERS:
        for mode in case.MODES:
            for repetition in range(case.REPETITIONS):
                receipt_id = f"c132:{seed}:{workers}:{mode}:{repetition}"
                row = case.evaluate_case(
                    db_path,
                    matrix_dir / f"w{workers}-{mode.lower()}-r{repetition}",
                    receipt_id,
                    workers,
                    mode,
                )
                row["repetition"] = repetition
                rows.append(row)
    return rows


def _measure(router, device, seed: int, output_dir: Path):
    control, _ = c131._measure(router, device, output_dir / f"c131-control-{seed}.db")
    rows = _process_rows(seed, output_dir)
    m = metrics.summarize(rows)
    m["c131_control_gate_rate"] = float(control["gate_passed"])
    deciding = [k for k in m if k.endswith("_rate")]
    m["gate_passed"] = all(m[k] == 1.0 for k in deciding)
    return m, rows


def run(*, protected_result_path: Path, c131_summary_path: Path, output_dir: Path):
    prior = json.loads(c131_summary_path.read_text(encoding="utf-8"))
    if (
        prior.get("experiment_id") != c131.EXPERIMENT_ID
        or prior.get("status") != "PASS"
        or not prior.get("summary", {}).get("sqlite_storage_fencing_falsification_gate_passed")
    ):
        raise RuntimeError("C132 requires accepted C131")
    if not torch.cuda.is_available():
        raise RuntimeError("C132 requires CUDA")

    before = _sha(protected_result_path)
    output_dir.mkdir(parents=True, exist_ok=False)
    device = torch.device("cuda")
    torch.cuda.set_device(0)
    torch.set_num_threads(2)
    torch.set_float32_matmul_precision("highest")

    records = []
    for seed in SEEDS:
        router, loss = c113._train_router(seed, device)
        m, rows = _measure(router, device, seed, output_dir)
        passed = bool(m["gate_passed"])
        records.append({"seed": seed, "final_loss": loss, "metrics": m, "process_cases": rows, "validation_passed": passed})
        print(
            f"[C132] seed={seed} process={m['process_case_pass_rate']:.6f} "
            f"single={m['process_single_takeover_rate']:.6f} stale_reject={m['process_stale_write_reject_rate']:.6f} pass={passed}",
            flush=True,
        )

    after = _sha(protected_result_path)
    if before != after:
        raise RuntimeError("protected C37 result changed during C132")

    ms = [r["metrics"] for r in records]
    all_pass = all(r["validation_passed"] for r in records)
    keys = [k for k in ms[0] if k.endswith("_rate")]
    summary = {
        "fresh_seeds": list(SEEDS),
        "validation_base": 3,
        "worker_counts": list(case.WORKERS),
        "modes": list(case.MODES),
        "repetitions_per_worker_mode": case.REPETITIONS,
        "process_case_count": ms[0]["process_case_count"],
        **{k: _stats([m[k] for m in ms]) for k in keys},
        "all_validation_passed": all_pass,
        "os_process_sqlite_fencing_falsification_gate_passed": all_pass,
    }
    report = {
        "experiment_id": EXPERIMENT_ID,
        "stage": "V5-E-RUNTIME-OS-PROCESS-SQLITE-FENCING-FALSIFICATION",
        "status": "PASS",
        "summary": summary,
        "records": records,
        "C131_summary_sha256": _sha(c131_summary_path),
        "C37_result_sha256_before": before,
        "C37_result_sha256_after": after,
        "production_runtime_modified": False,
        "gate_e_candidate": False,
        "limitations": [
            "C132 uses independent OS processes on one Windows host and one local SQLite file",
            "C132 does not establish distributed-database consensus or network-partition behavior",
            "C132 does not simulate power loss or filesystem corruption",
            "C132 retains deterministic logical time for lease expiry",
        ],
    }
    (output_dir / "summary.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    return report
