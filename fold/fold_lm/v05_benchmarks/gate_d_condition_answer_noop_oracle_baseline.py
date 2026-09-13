"""C84: first V5-D oracle action baseline on Condition.

Gate C is closed. V5-D begins by registering the minimal action semantics before
training a controller. The Condition task is ideal because HOLD/UPDATE are
already authoritative teacher operations.

C84 asks one narrow question:

    Can HOLD be represented as ANSWER/no-op (zero core compute), while UPDATE
    remains COMPUTE(update_module, 1), without materially reducing exhaustive
    task quality?

This is a semantic/oracle-compute diagnostic. It does not yet implement sparse
GPU execution or train a router, so logical compute reduction is reported
separately from wall-clock runtime.
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
from torch.nn import functional as F

from fold_lm.v05.modules import SharedBasisFixedRoutingCore
from fold_lm.v05_benchmarks.gate_b_baseline_comparison import _build_condition
from fold_lm.v05_benchmarks.gate_c_shared_basis_condition_exhaustive_generalization import (
    _exhaustive_complement,
)
from fold_lm.v05_benchmarks.gate_c_shared_basis_direct_joint_training import _task_loss

EXPERIMENT_ID = "C84-v5d-condition-answer-noop-oracle-baseline"
DEFAULT_PROTECTED_RESULT = Path("runs/chatgpt-last-result.json")
SEEDS = (20261031, 20261032, 20261033)
RANK = 3
STEPS = 260
LR = 0.01
BATCH_SIZE = 32
EVAL_BATCH = 1024
MIN_MEAN_EXACT_DELTA = -0.002
MAX_COMPUTE_ACTIONS_PER_EVENT = 0.55
MIN_ANSWER_RATE = 0.45


def _sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _train(model, train, seed: int, device: torch.device) -> float:
    model.core.set_execution_mode("materialized")
    optimizer = torch.optim.AdamW(model.parameters(), lr=LR, weight_decay=0.0)
    sampler = torch.Generator(device="cpu").manual_seed(seed + 200)
    model.train()
    loss = None
    for step in range(1, STEPS + 1):
        indices = torch.randint(train.size, (BATCH_SIZE,), generator=sampler)
        optimizer.zero_grad(set_to_none=True)
        loss = _task_loss("condition", model, train, indices, device)
        if not torch.isfinite(loss):
            raise RuntimeError(f"C84 seed={seed} non-finite loss")
        loss.backward()
        optimizer.step()
        if step in (65, 130, 195, 260):
            print(
                f"[C84] seed={seed} train step={step}/{STEPS} loss={float(loss.detach()):.8f}",
                flush=True,
            )
    model.core.set_execution_mode("gemm_native")
    return float(loss.detach())


@torch.inference_mode()
def _minimal_policy_logits(model, initial, operations, candidates):
    working = model.state_embedding(initial).unsqueeze(1)
    logits = [model._decode(working)]
    for step in range(model.config.operation_steps):
        context = model.event_embedding(candidates[:, step]).unsqueeze(1)
        update_state = model.core(
            working,
            context,
            route_index=model.config.update_route,
        )
        update_mask = operations[:, step].bool().view(-1, 1, 1)
        # HOLD -> ANSWER/no-op. UPDATE -> COMPUTE(update, 1).
        working = torch.where(update_mask, update_state, working)
        logits.append(model._decode(working))
    return torch.stack(logits, dim=1)


@torch.inference_mode()
def _evaluate_pair(model, examples):
    model.eval()
    device = next(model.parameters()).device
    baseline_exact = 0
    policy_exact = 0
    baseline_final = 0
    policy_final = 0
    total_examples = 0
    update_events = 0
    total_events = 0
    output_max_abs = 0.0

    for start in range(0, examples.size, EVAL_BATCH):
        end = min(start + EVAL_BATCH, examples.size)
        initial = examples.initial_values[start:end].to(device)
        operations = examples.operations[start:end].to(device)
        candidates = examples.candidates[start:end].to(device)
        targets = examples.targets[start:end].to(device)

        baseline = model(initial, operations, candidates)
        policy = _minimal_policy_logits(model, initial, operations, candidates)
        output_max_abs = max(output_max_abs, float((baseline - policy).abs().max().item()))

        baseline_pred = baseline.argmax(dim=-1)
        policy_pred = policy.argmax(dim=-1)
        baseline_match = baseline_pred == targets
        policy_match = policy_pred == targets

        baseline_exact += int(baseline_match.all(dim=1).sum().item())
        policy_exact += int(policy_match.all(dim=1).sum().item())
        baseline_final += int(baseline_match[:, -1].sum().item())
        policy_final += int(policy_match[:, -1].sum().item())
        total_examples += int(targets.shape[0])
        update_events += int(operations.sum().item())
        total_events += int(operations.numel())

    compute_rate = update_events / total_events
    answer_rate = 1.0 - compute_rate
    return {
        "examples": total_examples,
        "baseline_exact_accuracy": baseline_exact / total_examples,
        "policy_exact_accuracy": policy_exact / total_examples,
        "exact_delta": (policy_exact - baseline_exact) / total_examples,
        "baseline_final_accuracy": baseline_final / total_examples,
        "policy_final_accuracy": policy_final / total_examples,
        "final_delta": (policy_final - baseline_final) / total_examples,
        "logical_compute_actions_per_event": compute_rate,
        "logical_answer_noop_rate": answer_rate,
        "logical_compute_reduction_vs_one_compute_per_event": 1.0 - compute_rate,
        "logical_route_eval_reduction_vs_current_dual_route_reference": 1.0 - (compute_rate / 2.0),
        "baseline_vs_policy_output_max_abs_gap": output_max_abs,
    }


def _stats(values: list[float]) -> dict[str, float]:
    return {
        "mean": statistics.mean(values),
        "median": statistics.median(values),
        "min": min(values),
        "max": max(values),
    }


def run(*, protected_result_path: Path, c83_summary_path: Path, output_dir: Path) -> dict:
    if not torch.cuda.is_available():
        raise RuntimeError("C84 requires CUDA")
    c83 = json.loads(c83_summary_path.read_text(encoding="utf-8"))
    if c83.get("experiment_id") != "C83-shared-basis-production-vram-headroom":
        raise RuntimeError("C84 requires accepted C83 summary")
    if c83.get("status") != "PASS" or not bool(
        c83.get("summary", {}).get("production_vram_headroom_gate_passed")
    ):
        raise RuntimeError("C84 requires accepted C83 VRAM gate")

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
        final_loss = _train(model, train, seed, device)
        exhaustive = _exhaustive_complement(config, train)
        metrics = _evaluate_pair(model, exhaustive)
        metrics.update({"seed": seed, "final_training_loss": final_loss})
        records.append(metrics)
        print(
            f"[C84] seed={seed} done ({index}/{len(SEEDS)}) "
            f"baseline={metrics['baseline_exact_accuracy']:.8f} "
            f"policy={metrics['policy_exact_accuracy']:.8f} "
            f"delta={metrics['exact_delta']:+.8f} "
            f"compute/event={metrics['logical_compute_actions_per_event']:.4f}",
            flush=True,
        )

    exact_deltas = [float(row["exact_delta"]) for row in records]
    compute_rates = [float(row["logical_compute_actions_per_event"]) for row in records]
    answer_rates = [float(row["logical_answer_noop_rate"]) for row in records]

    summary = {
        "seed_count": len(SEEDS),
        "rank": RANK,
        "action_space": ["ANSWER", "COMPUTE(update,1)"],
        "candidate_semantics": "HOLD->ANSWER/no-op; UPDATE->COMPUTE(update,1)",
        "exhaustive_examples_per_seed": records[0]["examples"],
        "exact_delta": _stats(exact_deltas),
        "logical_compute_actions_per_event": _stats(compute_rates),
        "logical_answer_noop_rate": _stats(answer_rates),
        "minimum_mean_exact_delta": MIN_MEAN_EXACT_DELTA,
        "maximum_compute_actions_per_event": MAX_COMPUTE_ACTIONS_PER_EVENT,
        "minimum_answer_rate": MIN_ANSWER_RATE,
    }
    summary["answer_noop_oracle_gate_passed"] = (
        float(summary["exact_delta"]["mean"]) >= MIN_MEAN_EXACT_DELTA
        and float(summary["logical_compute_actions_per_event"]["max"])
        <= MAX_COMPUTE_ACTIONS_PER_EVENT
        and float(summary["logical_answer_noop_rate"]["min"]) >= MIN_ANSWER_RATE
    )

    protected_after = _sha256(protected_result_path)
    if protected_after != protected_before:
        raise RuntimeError("protected C37 result changed during C84")

    report = {
        "experiment_id": EXPERIMENT_ID,
        "stage": "V5-D",
        "status": "PASS",
        "status_meaning": "first V5-D ANSWER/no-op oracle compute baseline",
        "seeds": list(SEEDS),
        "records": records,
        "summary": summary,
        "C83_summary_sha256": _sha256(c83_summary_path),
        "C37_result_sha256_before": protected_before,
        "C37_result_sha256_after": protected_after,
        "production_runtime_modified": False,
        "gate_d_candidate": False,
        "limitations": [
            "C84 measures logical action/computation semantics, not sparse GPU wall-clock speedup",
            "C84 uses only the existing tiny Condition task",
            "C84 uses teacher operation semantics rather than a learned controller",
            "C84 does not establish Gate D passage",
        ],
    }
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "summary.json").write_text(
        json.dumps(report, indent=2, allow_nan=False), encoding="utf-8"
    )
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protected-result", type=Path, default=DEFAULT_PROTECTED_RESULT)
    parser.add_argument("--c83-summary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    started = time.perf_counter()
    result = run(
        protected_result_path=args.protected_result,
        c83_summary_path=args.c83_summary,
        output_dir=args.output_dir,
    )
    display = dict(result)
    display["records"] = "omitted; see summary.json"
    display["elapsed_seconds"] = time.perf_counter() - started
    print("\n=== C84 RESULT ===")
    print(json.dumps(display, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
