"""C77: final selected-rank GEMM-native recurrence equivalence refresh.

C76 prospectively established Condition rank3 as non-inferior to rank4 on the
current synthetic Condition domain under the predeclared -0.002 engineering
margin. The selected Gate-C ranks are therefore now:

- Condition: rank3
- Composition: rank2
- Language: rank4

C70 already established the materialized-vs-GEMM-native arithmetic at the older
Condition rank4 point. C77 changes only the selected rank set and repeats the
same semantic/output and recurrent-state equivalence checks on fresh seeds
before any production ``fold_lm.v05.modules`` integration.

Experiment PASS means the benchmark executed correctly. The scientific gate is
reported separately through the summary all-* flags.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import statistics
import time

import torch

from fold_lm.v05_benchmarks.gate_c_shared_basis_aligned_joint_training import TASK_SPECS
from fold_lm.v05_benchmarks.gate_c_shared_basis_direct_joint_training import (
    JointTrainSharedBasisCore,
    _build_task,
)
from fold_lm.v05_benchmarks.gate_c_shared_basis_runtime_recurrence_equivalence import (
    ATOL,
    RTOL,
    RECURRENCE_DEPTHS,
    GemmNativeSharedBasisCore,
    _gap,
    _recurrence_stress,
    _semantic_equal,
    _train_factorized,
    _validation_output,
)
from fold_lm.v05_benchmarks.gate_c_shared_basis_task_aware_recovery import _storage


EXPERIMENT_ID = "C77-shared-basis-final-selected-rank-recurrence-equivalence"
DEFAULT_PROTECTED_RESULT = Path("runs/chatgpt-last-result.json")
TASKS = ("condition", "composition", "language")
SELECTED_RANKS = {
    "condition": 3,
    "composition": 2,
    "language": 4,
}
SEEDS = (20261001, 20261002, 20261003)


def _sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _stats(values: list[float]) -> dict[str, float]:
    return {
        "mean": statistics.mean(values),
        "median": statistics.median(values),
        "min": min(values),
        "max": max(values),
    }


def run(*, protected_result_path: Path, c76_summary_path: Path, output_dir: Path) -> dict:
    if not torch.cuda.is_available():
        raise RuntimeError("C77 requires CUDA")

    c76 = json.loads(c76_summary_path.read_text(encoding="utf-8"))
    if c76.get("experiment_id") != "C76-shared-basis-condition-rank3-prospective-noninferiority":
        raise RuntimeError("C77 requires accepted C76 summary")
    if c76.get("status") != "PASS":
        raise RuntimeError("C76 summary is not PASS")
    c76s = c76.get("summary", {})
    if not bool(c76s.get("noninferiority_gate_passed", False)):
        raise RuntimeError("C77 requires C76 non-inferiority gate PASS")
    if int(c76.get("rank3", -1)) != 3 or int(c76.get("rank4", -1)) != 4:
        raise RuntimeError("C77 requires the accepted C76 rank3/rank4 decision")
    if abs(float(c76s.get("noninferiority_margin_absolute_accuracy", -1.0)) - 0.002) > 1e-12:
        raise RuntimeError("C77 requires the prospective C76 0.002 margin")

    old_seeds = {int(seed) for seed in c76.get("seeds", ())}
    if old_seeds.intersection(SEEDS):
        raise RuntimeError("C77 refresh seeds must be disjoint from C76")

    protected_before = _sha256(protected_result_path)
    device = torch.device("cuda")
    torch.cuda.set_device(0)
    torch.set_num_threads(2)
    torch.set_float32_matmul_precision("highest")

    records: list[dict] = []
    total = len(TASKS) * len(SEEDS)
    completed = 0

    for task_index, task in enumerate(TASKS):
        rank = int(SELECTED_RANKS[task])
        spec = TASK_SPECS[task]
        for seed in SEEDS:
            print(
                f"[C77] task={task} seed={seed} start ({completed + 1}/{total}) rank={rank}",
                flush=True,
            )
            _config, initial_model, train, validation, evaluator = _build_task(task, seed, device)
            reference_model = copy.deepcopy(initial_model).to(device)
            reference_model.core = JointTrainSharedBasisCore(initial_model.core, rank).to(device)
            reference_model = reference_model.to(device)

            width = int(reference_model.core.config.width)
            hidden = width * int(reference_model.core.config.hidden_mult)
            storage = _storage(width=width, hidden=hidden, rank=rank)
            if not bool(storage["below_dense_weight_bytes"]):
                raise RuntimeError(f"C77 task={task} selected rank is not sub-dense")

            final_loss = _train_factorized(
                task=task,
                seed=seed,
                model=reference_model,
                train=train,
                device=device,
            )

            runtime_model = copy.deepcopy(reference_model).to(device)
            runtime_model.core = GemmNativeSharedBasisCore(reference_model.core).to(device)
            runtime_model = runtime_model.to(device)

            reference_output = _validation_output(task, reference_model, validation, device)
            runtime_output = _validation_output(task, runtime_model, validation, device)
            validation_gap = _gap(reference_output, runtime_output)
            semantic_equal = _semantic_equal(task, reference_output, runtime_output)

            score_name = str(spec["score_name"])
            reference_score = float(evaluator(reference_model, validation)[score_name])
            runtime_score = float(evaluator(runtime_model, validation)[score_name])

            recurrence = _recurrence_stress(
                reference_core=reference_model.core,
                runtime_core=runtime_model.core,
                task_index=task_index,
                seed=seed,
                device=device,
            )

            record = {
                "task": task,
                "seed": seed,
                "rank": rank,
                "learning_rate": float(spec["common_lr"]),
                **storage,
                "final_training_loss": final_loss,
                "reference_validation_score": reference_score,
                "runtime_validation_score": runtime_score,
                "validation_score_equal": abs(reference_score - runtime_score) <= 1e-12,
                "validation_semantic_equal": semantic_equal,
                "validation_output_gap": validation_gap,
                "recurrence": recurrence,
            }
            records.append(record)
            completed += 1
            print(
                f"[C77] task={task} seed={seed} done ({completed}/{total}) "
                f"score_ref={reference_score:.8f} score_runtime={runtime_score:.8f} "
                f"val_max_abs={validation_gap['max_abs']:.3e} "
                f"rec_max_abs={recurrence['max_abs_gap']:.3e}",
                flush=True,
            )

            del initial_model, reference_model, runtime_model
            torch.cuda.empty_cache()

    protected_after = _sha256(protected_result_path)
    if protected_after != protected_before:
        raise RuntimeError("protected C37 result changed during C77")

    validation_abs = [float(row["validation_output_gap"]["max_abs"]) for row in records]
    recurrence_abs = [float(row["recurrence"]["max_abs_gap"]) for row in records]
    recurrence_rel = [float(row["recurrence"]["max_relative_l2_gap"]) for row in records]

    summary = {
        "run_count": len(records),
        "selected_ranks": SELECTED_RANKS,
        "seeds_disjoint_from_c76": True,
        "recurrence_depths": list(RECURRENCE_DEPTHS),
        "rtol": RTOL,
        "atol": ATOL,
        "validation_max_abs_gap": _stats(validation_abs),
        "recurrence_max_abs_gap": _stats(recurrence_abs),
        "recurrence_max_relative_l2_gap": _stats(recurrence_rel),
        "all_validation_scores_equal": all(bool(row["validation_score_equal"]) for row in records),
        "all_validation_semantic_equal": all(bool(row["validation_semantic_equal"]) for row in records),
        "all_validation_outputs_allclose": all(
            bool(row["validation_output_gap"]["allclose"]) for row in records
        ),
        "all_recurrence_allclose": all(
            bool(row["recurrence"]["all_depths_allclose"]) for row in records
        ),
    }
    summary["all_runtime_formula_equivalent"] = all(
        bool(summary[name])
        for name in (
            "all_validation_scores_equal",
            "all_validation_semantic_equal",
            "all_validation_outputs_allclose",
            "all_recurrence_allclose",
        )
    )

    report = {
        "experiment_id": EXPERIMENT_ID,
        "stage": "V5-C",
        "status": "PASS",
        "status_meaning": "final selected-rank pre-production GEMM-native recurrence equivalence refresh",
        "tasks": list(TASKS),
        "selected_ranks": SELECTED_RANKS,
        "seeds": list(SEEDS),
        "records": records,
        "summary": summary,
        "C76_summary_sha256": _sha256(c76_summary_path),
        "C37_result_sha256_before": protected_before,
        "C37_result_sha256_after": protected_after,
        "training": "selected_rank_aligned_lr_equivalence_refresh",
        "production_runtime_modified": False,
        "gate_c_candidate": False,
        "limitations": [
            "C77 refreshes execution equivalence only; rank3 quality acceptance comes from C76",
            "recurrence stress remains synthetic and deterministic rather than a learned long-horizon task",
            "only the current three tiny Gate-B task families and float32 execution are covered",
            "C77 does not by itself establish broad-task quality or Gate C passage",
        ],
    }

    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "summary.json").write_text(
        json.dumps(report, indent=2, allow_nan=False), encoding="utf-8"
    )
    display = dict(report)
    display["records"] = "omitted from console; see summary.json"
    return display


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protected-result", type=Path, default=DEFAULT_PROTECTED_RESULT)
    parser.add_argument("--c76-summary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)

    started = time.perf_counter()
    result = run(
        protected_result_path=args.protected_result,
        c76_summary_path=args.c76_summary,
        output_dir=args.output_dir,
    )
    result["elapsed_seconds"] = time.perf_counter() - started
    print("\n=== C77 RESULT ===")
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
