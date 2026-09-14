"""C117: compose authoritative preflight with learned fallback trajectories."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import statistics
import torch

from fold_lm.v05_benchmarks import gate_e_c113_stale_eligibility_preflight as c113
from fold_lm.v05_benchmarks import gate_e_c116_authoritative_preflight_priority_refresh as c116
from fold_lm.v05_benchmarks import gate_e_c117_eval_helper as helper

EXPERIMENT_ID = "C117-v5e-post-preflight-execution-failure-fallback"
C116_EXPERIMENT_ID = c116.EXPERIMENT_ID
DEFAULT_PROTECTED_RESULT = Path("runs/chatgpt-last-result.json")
SEEDS = (20261371, 20261372, 20261373)


def _sha(path: Path) -> str:
    return hashlib.file_digest(path.open("rb"), "sha256").hexdigest()


def _stats(values):
    return {
        "mean": statistics.mean(values),
        "median": statistics.median(values),
        "min": min(values),
        "max": max(values),
    }


def run(*, protected_result_path: Path, c116_summary_path: Path, output_dir: Path):
    prerequisite = json.loads(c116_summary_path.read_text(encoding="utf-8"))
    if prerequisite.get("experiment_id") != C116_EXPERIMENT_ID:
        raise RuntimeError("C117 requires C116 summary")
    if prerequisite.get("status") != "PASS" or not prerequisite.get("summary", {}).get(
        "authoritative_preflight_priority_refresh_gate_passed"
    ):
        raise RuntimeError("C117 requires accepted C116")
    if not torch.cuda.is_available():
        raise RuntimeError("C117 requires CUDA")

    before = _sha(protected_result_path)
    device = torch.device("cuda")
    torch.cuda.set_device(0)
    torch.set_num_threads(2)
    torch.set_float32_matmul_precision("highest")

    records = []
    for seed in SEEDS:
        router, loss = c113._train_router(seed, device)
        metrics, trajectories = helper.evaluate_router(router, device)
        passed = bool(metrics["gate_passed"])
        records.append(
            {
                "seed": seed,
                "final_loss": loss,
                "metrics": metrics,
                "trajectories": trajectories,
                "validation_passed": passed,
            }
        )
        print(
            f"[C117] seed={seed} trajectory={metrics['trajectory_pass_rate']:.6f} "
            f"preflight={metrics['preflight_correct_rate']:.6f} "
            f"fallback={metrics['failure_fallback_recovery_rate']:.6f} pass={passed}",
            flush=True,
        )

    after = _sha(protected_result_path)
    if before != after:
        raise RuntimeError("protected C37 result changed during C117")

    metrics = [r["metrics"] for r in records]
    all_passed = all(r["validation_passed"] for r in records)
    summary = {
        "fresh_seeds": list(SEEDS),
        "validation_base": 3,
        "production_adapter": "canonicalize_boolean_channels",
        "composition": "C116 authoritative preflight plus C105 failure fallback",
        "mask_pair_count": metrics[0]["mask_pair_count"],
        "trajectory_count": metrics[0]["trajectory_count"],
        "trajectory_pass_rate": _stats([m["trajectory_pass_rate"] for m in metrics]),
        "preflight_correct_rate": _stats([m["preflight_correct_rate"] for m in metrics]),
        "failure_fallback_recovery_rate": _stats([m["failure_fallback_recovery_rate"] for m in metrics]),
        "hidden_action_trace_invariance": _stats([m["hidden_action_trace_invariance"] for m in metrics]),
        "ineligible_mechanism_count": {
            "sum": sum(m["ineligible_mechanism_count"] for m in metrics),
            "max": max(m["ineligible_mechanism_count"] for m in metrics),
        },
        "repeat_failed_mechanism_count": {
            "sum": sum(m["repeat_failed_mechanism_count"] for m in metrics),
            "max": max(m["repeat_failed_mechanism_count"] for m in metrics),
        },
        "budget_violation_count": {
            "sum": sum(m["budget_violation_count"] for m in metrics),
            "max": max(m["budget_violation_count"] for m in metrics),
        },
        "all_validation_passed": all_passed,
        "post_preflight_execution_failure_fallback_gate_passed": all_passed,
    }
    report = {
        "experiment_id": EXPERIMENT_ID,
        "stage": "V5-E-RUNTIME-AUTHORITY-FALSIFICATION",
        "status": "PASS",
        "status_meaning": "authoritative preflight composed with no-commit failure fallback",
        "summary": summary,
        "records": records,
        "C116_summary_sha256": _sha(c116_summary_path),
        "C37_result_sha256_before": before,
        "C37_result_sha256_after": after,
        "production_runtime_modified": False,
        "gate_e_candidate": False,
        "limitations": [
            "C117 composes registered synthetic preflight and fallback semantics",
            "C117 does not invoke real tools or model partial/non-idempotent external effects",
            "C117 does not establish Gate E passage",
        ],
    }
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "summary.json").write_text(
        json.dumps(report, indent=2, allow_nan=False), encoding="utf-8"
    )
    return report
