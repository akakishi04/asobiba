"""C85: first supervised V5-D router over the C84 oracle action policy.

C84 established the oracle semantics HOLD->ANSWER/no-op and
UPDATE->COMPUTE(update,1). C85 asks whether a small learned controller can
reproduce that policy from observable state, event context, and operation token
without losing exhaustive quality or the ~50% logical-compute reduction.
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

from fold_lm.v05.controller import ActionRouterConfig, SupervisedActionRouter
from fold_lm.v05.modules import SharedBasisFixedRoutingCore
from fold_lm.v05_benchmarks.gate_b_baseline_comparison import _build_condition
from fold_lm.v05_benchmarks.gate_c_shared_basis_condition_exhaustive_generalization import _exhaustive_complement
from fold_lm.v05_benchmarks.gate_d_condition_answer_noop_oracle_baseline import _train
from fold_lm.v05_benchmarks.gate_d_c85_router_train import build_examples, train_router
from fold_lm.v05_benchmarks.gate_d_c85_router_eval import evaluate

EXPERIMENT_ID = "C85-v5d-condition-supervised-action-router"
DEFAULT_PROTECTED_RESULT = Path("runs/chatgpt-last-result.json")
SEEDS = (20261101, 20261102, 20261103)
RANK = 3
MIN_ACTION_ACCURACY = 0.995
MIN_CLASS_RECALL = 0.995
MIN_MEAN_EXACT_DELTA = -0.002
MAX_COMPUTE_ACTIONS_PER_EVENT = 0.55
MIN_ANSWER_RATE = 0.45


def _sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _stats(values):
    return {
        "mean": statistics.mean(values),
        "median": statistics.median(values),
        "min": min(values),
        "max": max(values),
    }


def run(*, protected_result_path: Path, c84_summary_path: Path, output_dir: Path) -> dict:
    if not torch.cuda.is_available():
        raise RuntimeError("C85 requires CUDA")
    c84 = json.loads(c84_summary_path.read_text(encoding="utf-8"))
    if c84.get("experiment_id") != "C84-v5d-condition-answer-noop-oracle-baseline":
        raise RuntimeError("C85 requires C84 summary")
    if c84.get("status") != "PASS" or not bool(c84.get("summary", {}).get("answer_noop_oracle_gate_passed")):
        raise RuntimeError("C85 requires accepted C84 oracle gate")

    protected_before = _sha256(protected_result_path)
    device = torch.device("cuda")
    torch.cuda.set_device(0)
    torch.set_num_threads(2)
    torch.set_float32_matmul_precision("highest")

    records = []
    for index, seed in enumerate(SEEDS, start=1):
        config, initial_model, train, _validation = _build_condition(seed, "v5b", device)
        model = copy.deepcopy(initial_model).to(device)
        model.core = SharedBasisFixedRoutingCore(
            initial_model.core,
            RANK,
            execution_mode="materialized",
        ).to(device)
        final_model_loss = _train(model, train, seed, device)
        model.core.set_execution_mode("gemm_native")
        for parameter in model.parameters():
            parameter.requires_grad_(False)

        router = SupervisedActionRouter(ActionRouterConfig(width=config.width)).to(device)
        states, contexts, labels = build_examples(model, train, device)
        final_router_loss = train_router(router, states, contexts, labels, seed=seed)

        exhaustive = _exhaustive_complement(config, train)
        metrics = evaluate(model, router, exhaustive)
        metrics.update({
            "seed": seed,
            "final_model_loss": final_model_loss,
            "final_router_loss": final_router_loss,
        })
        records.append(metrics)
        print(
            f"[C85] seed={seed} done ({index}/{len(SEEDS)}) "
            f"action={metrics['action_accuracy']:.6f} "
            f"delta={metrics['exact_delta_vs_oracle']:+.8f} "
            f"compute/event={metrics['logical_compute_actions_per_event']:.4f}",
            flush=True,
        )

    action = [float(row["action_accuracy"]) for row in records]
    hold = [float(row["hold_answer_recall"]) for row in records]
    update = [float(row["update_compute_recall"]) for row in records]
    deltas = [float(row["exact_delta_vs_oracle"]) for row in records]
    compute = [float(row["logical_compute_actions_per_event"]) for row in records]
    answer = [float(row["logical_answer_rate"]) for row in records]

    summary = {
        "seed_count": len(SEEDS),
        "rank": RANK,
        "action_space": ["ANSWER", "COMPUTE(update,1)"],
        "controller_observations": ["working_state", "candidate_context", "operation_token"],
        "target_or_oracle_action_is_not_controller_input": True,
        "action_accuracy": _stats(action),
        "hold_answer_recall": _stats(hold),
        "update_compute_recall": _stats(update),
        "exact_delta_vs_c84_oracle": _stats(deltas),
        "logical_compute_actions_per_event": _stats(compute),
        "logical_answer_rate": _stats(answer),
        "minimum_action_accuracy": MIN_ACTION_ACCURACY,
        "minimum_class_recall": MIN_CLASS_RECALL,
        "minimum_mean_exact_delta": MIN_MEAN_EXACT_DELTA,
        "maximum_compute_actions_per_event": MAX_COMPUTE_ACTIONS_PER_EVENT,
        "minimum_answer_rate": MIN_ANSWER_RATE,
    }
    summary["supervised_router_gate_passed"] = (
        min(action) >= MIN_ACTION_ACCURACY
        and min(hold) >= MIN_CLASS_RECALL
        and min(update) >= MIN_CLASS_RECALL
        and float(summary["exact_delta_vs_c84_oracle"]["mean"]) >= MIN_MEAN_EXACT_DELTA
        and max(compute) <= MAX_COMPUTE_ACTIONS_PER_EVENT
        and min(answer) >= MIN_ANSWER_RATE
    )

    protected_after = _sha256(protected_result_path)
    if protected_after != protected_before:
        raise RuntimeError("protected C37 result changed during C85")

    report = {
        "experiment_id": EXPERIMENT_ID,
        "stage": "V5-D",
        "status": "PASS",
        "status_meaning": "first supervised V5-D action-router verification",
        "seeds": list(SEEDS),
        "records": records,
        "summary": summary,
        "C84_summary_sha256": _sha256(c84_summary_path),
        "C37_result_sha256_before": protected_before,
        "C37_result_sha256_after": protected_after,
        "production_runtime_modified": True,
        "gate_d_candidate": False,
        "limitations": [
            "C85 uses an explicit observable HOLD/UPDATE operation token",
            "logical compute reduction is not yet sparse GPU wall-clock speedup",
            "C85 covers only the tiny Condition task",
            "C85 does not establish Gate D passage",
        ],
    }
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "summary.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protected-result", type=Path, default=DEFAULT_PROTECTED_RESULT)
    parser.add_argument("--c84-summary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    started = time.perf_counter()
    result = run(
        protected_result_path=args.protected_result,
        c84_summary_path=args.c84_summary,
        output_dir=args.output_dir,
    )
    display = dict(result)
    display["records"] = "omitted; see summary.json"
    display["elapsed_seconds"] = time.perf_counter() - started
    print("\n=== C85 RESULT ===")
    print(json.dumps(display, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
