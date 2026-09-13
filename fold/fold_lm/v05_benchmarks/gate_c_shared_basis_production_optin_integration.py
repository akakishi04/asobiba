"""C78: opt-in production Shared-Basis direct-training integration gate.

C77 revalidated the final selected ranks (Condition 3, Composition 2, Language 4)
for materialized-vs-GEMM-native inference after materialized factorized training.
The remaining production gap is that the actual production class stores the
concatenated GEMM-native projections during training too.

C78 compares, from the same untrained dense initialization and the same batch
sequence:

1. the accepted benchmark materialized Shared-Basis training core;
2. the new opt-in production ``SharedBasisFixedRoutingCore``.

The accepted aligned-LR rule means all factor/common parameters use the same
learning rate, so concatenating base+basis into one trainable projection should
not intentionally change optimizer policy.  C78 verifies initialization,
training semantics, final task scores, production materialized-reference
recurrence, state-dict round-trip, and protected artifacts.  It does not change
the default dense core or establish Gate C passage by itself.
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
from fold_lm.v05_benchmarks.gate_b_baseline_comparison import _build_condition, _build_composition, _build_language
from fold_lm.v05_benchmarks.gate_c_shared_basis_aligned_joint_training import TASK_SPECS
from fold_lm.v05_benchmarks.gate_c_shared_basis_direct_joint_training import (
    JointTrainSharedBasisCore,
    _task_loss,
)


EXPERIMENT_ID = "C78-shared-basis-production-optin-integration"
DEFAULT_PROTECTED_RESULT = Path("runs/chatgpt-last-result.json")
TASKS = ("condition", "composition", "language")
SELECTED_RANKS = {"condition": 3, "composition": 2, "language": 4}
SEEDS = (20261011, 20261012, 20261013)
RECURRENCE_DEPTHS = (1, 2, 4, 8, 16, 32, 64)
STRESS_BATCH = 8
CONTEXT_SCALE = 0.05
RTOL = 5e-4
ATOL = 1e-4
GRAD_ATOL = 1e-5


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


def _build_task(task: str, seed: int, device: torch.device):
    if task == "condition":
        config, model, train, validation = _build_condition(seed, "v5b", device)
        from fold_lm.v05.condition_task import evaluate_condition
        return config, model, train, validation, evaluate_condition
    if task == "composition":
        config, model, train, validation = _build_composition(seed, "v5b", device)
        from fold_lm.v05.composition_task import evaluate_composition
        return config, model, train, validation, evaluate_composition
    if task == "language":
        config, model, train, validation = _build_language(seed, "v5b", device)
        from fold_lm.v05.language_task import evaluate_language
        return config, model, train, validation, evaluate_language
    raise ValueError(f"unknown task: {task}")


def _progress_marks(steps: int) -> tuple[int, ...]:
    return tuple(sorted({max(1, round(steps * x)) for x in (0.25, 0.5, 0.75, 1.0)}))


def _train_pair(*, task: str, seed: int, reference_model, production_model, train, device: torch.device):
    spec = TASK_SPECS[task]
    steps = int(spec["steps"])
    lr = float(spec["common_lr"])
    batch_size = int(spec["batch_size"])
    ref_optimizer = torch.optim.AdamW(reference_model.parameters(), lr=lr, weight_decay=0.0)
    prod_optimizer = torch.optim.AdamW(production_model.parameters(), lr=lr, weight_decay=0.0)
    sampler = torch.Generator(device="cpu").manual_seed(seed + 200)
    marks = _progress_marks(steps)
    ref_loss = None
    prod_loss = None

    reference_model.train()
    production_model.train()
    for step in range(1, steps + 1):
        indices = torch.randint(train.size, (batch_size,), generator=sampler)

        ref_optimizer.zero_grad(set_to_none=True)
        ref = _task_loss(task, reference_model, train, indices, device)
        if not torch.isfinite(ref):
            raise RuntimeError(f"C78 task={task} seed={seed} reference non-finite loss")
        ref.backward()
        ref_optimizer.step()

        prod_optimizer.zero_grad(set_to_none=True)
        prod = _task_loss(task, production_model, train, indices, device)
        if not torch.isfinite(prod):
            raise RuntimeError(f"C78 task={task} seed={seed} production non-finite loss")
        prod.backward()
        prod_optimizer.step()

        ref_loss = float(ref.detach().item())
        prod_loss = float(prod.detach().item())
        if step in marks:
            print(
                f"[C78] task={task} seed={seed} step={step}/{steps} "
                f"ref_loss={ref_loss:.8f} prod_loss={prod_loss:.8f}",
                flush=True,
            )
    return float(ref_loss), float(prod_loss)


@torch.inference_mode()
def _validation_output(task: str, model, validation, device: torch.device) -> torch.Tensor:
    model.eval()
    if task == "condition":
        return model(
            validation.initial_values.to(device),
            validation.operations.to(device),
            validation.candidates.to(device),
        )
    if task == "composition":
        return model(
            validation.initial_values.to(device),
            validation.operations.to(device),
            validation.operands.to(device),
        )
    if task == "language":
        return model(validation.tokens.to(device), validation.tasks.to(device))
    raise ValueError(task)


def _semantic_equal(task: str, reference: torch.Tensor, candidate: torch.Tensor) -> bool:
    if task in ("condition", "language"):
        return bool(torch.equal(reference.argmax(dim=-1), candidate.argmax(dim=-1)))
    return bool(torch.allclose(candidate, reference, rtol=RTOL, atol=ATOL))


def _gap(reference: torch.Tensor, candidate: torch.Tensor) -> dict[str, float | bool]:
    diff = (candidate.float() - reference.float()).reshape(-1)
    ref = reference.float().reshape(-1)
    max_abs = float(diff.abs().max().item()) if diff.numel() else 0.0
    l2 = float(torch.linalg.vector_norm(diff).item()) if diff.numel() else 0.0
    ref_l2 = float(torch.linalg.vector_norm(ref).item()) if ref.numel() else 0.0
    return {
        "max_abs": max_abs,
        "relative_l2": l2 / max(ref_l2, 1e-12),
        "allclose": bool(torch.allclose(candidate, reference, rtol=RTOL, atol=ATOL)),
    }


def _copy_reference_into_production(reference: JointTrainSharedBasisCore, production: SharedBasisFixedRoutingCore) -> None:
    hidden = int(reference.config.width * reference.config.hidden_mult)
    with torch.no_grad():
        production.shared.load_state_dict(reference.shared.state_dict())
        production.norms.load_state_dict(reference.norms.state_dict())
        production.gate_logits.copy_(reference.gate_logits)
        production.up_biases.copy_(reference.up_biases)
        production.down_biases.copy_(reference.down_biases)
        production.up_projection.copy_(torch.cat((reference.up_base, reference.up_basis), dim=0))
        production.down_projection.copy_(torch.cat((reference.down_base, reference.down_basis), dim=0))
        production.up_coeff.copy_(reference.up_coeff)
        production.down_coeff.copy_(reference.down_coeff)
    if production.up_projection.shape[0] != hidden + reference.rank:
        raise RuntimeError("C78 production up projection shape mismatch")


def _initial_effective_gap(reference: JointTrainSharedBasisCore, production: SharedBasisFixedRoutingCore) -> float:
    maximum = 0.0
    for route in range(reference.config.modules):
        ref_up, ref_down = reference._weight_pair(route)
        prod_up, prod_down = production.materialized_role_weights(route)
        maximum = max(
            maximum,
            float((ref_up - prod_up).abs().max().item()),
            float((ref_down - prod_down).abs().max().item()),
        )
    return maximum


def _gradient_equivalence(reference: JointTrainSharedBasisCore, production: SharedBasisFixedRoutingCore, seed: int) -> dict:
    ref = copy.deepcopy(reference)
    prod = copy.deepcopy(production)
    _copy_reference_into_production(ref, prod)
    generator = torch.Generator(device="cpu").manual_seed(seed + 50000)
    working = torch.randn(
        4, ref.config.slots, ref.config.width, generator=generator, dtype=torch.float32
    ).to(ref.up_base.device) * 0.05
    context = torch.randn(
        4, ref.config.slots, ref.config.width, generator=generator, dtype=torch.float32
    ).to(ref.up_base.device) * 0.05
    target = torch.randn(
        4, ref.config.slots, ref.config.width, generator=generator, dtype=torch.float32
    ).to(ref.up_base.device) * 0.05
    route = 1 if ref.config.modules > 1 else 0

    ref_out = ref(working, context, route_index=route)
    prod_out = prod(working, context, route_index=route)
    F.mse_loss(ref_out, target).backward()
    F.mse_loss(prod_out, target).backward()

    pairs = [
        ("gate_logits", ref.gate_logits.grad, prod.gate_logits.grad),
        ("up_base", ref.up_base.grad, prod.up_projection.grad[: ref.up_base.shape[0]]),
        ("up_basis", ref.up_basis.grad, prod.up_projection.grad[ref.up_base.shape[0] :]),
        ("up_coeff", ref.up_coeff.grad, prod.up_coeff.grad),
        ("down_base", ref.down_base.grad, prod.down_projection.grad[: ref.down_base.shape[0]]),
        ("down_basis", ref.down_basis.grad, prod.down_projection.grad[ref.down_base.shape[0] :]),
        ("down_coeff", ref.down_coeff.grad, prod.down_coeff.grad),
        ("up_biases", ref.up_biases.grad, prod.up_biases.grad),
        ("down_biases", ref.down_biases.grad, prod.down_biases.grad),
    ]
    max_abs = 0.0
    allclose = bool(torch.allclose(ref_out, prod_out, rtol=RTOL, atol=ATOL))
    for name, left, right in pairs:
        if left is None or right is None:
            raise RuntimeError(f"C78 missing gradient for {name}")
        max_abs = max(max_abs, float((left.float() - right.float()).abs().max().item()))
        allclose = allclose and bool(torch.allclose(left, right, rtol=RTOL, atol=GRAD_ATOL))
    return {"allclose": allclose, "max_abs": max_abs}


@torch.inference_mode()
def _production_materialized_forward(
    core: SharedBasisFixedRoutingCore,
    working: torch.Tensor,
    context: torch.Tensor,
    route_index: int,
) -> torch.Tensor:
    z = working + context
    shared_delta = core.shared(z)
    normalized = core.norms[route_index](z)
    up, down = core.materialized_role_weights(route_index)
    hidden = F.gelu(F.linear(normalized, up, core.up_biases[route_index]))
    routed_delta = F.linear(hidden, down, core.down_biases[route_index])
    gate = torch.sigmoid(core.gate_logits).to(dtype=z.dtype, device=z.device)
    return working + gate * (shared_delta + routed_delta)


@torch.inference_mode()
def _recurrence_equivalence(core: SharedBasisFixedRoutingCore, seed: int) -> dict:
    generator = torch.Generator(device="cpu").manual_seed(seed + 60000)
    native = core.initial_working_state(STRESS_BATCH)
    reference = native.clone()
    checkpoints = []
    for step in range(1, max(RECURRENCE_DEPTHS) + 1):
        context = torch.randn(
            STRESS_BATCH,
            core.config.slots,
            core.config.width,
            generator=generator,
            dtype=torch.float32,
        ).to(native.device) * CONTEXT_SCALE
        route = (step - 1) % core.config.modules
        native = core(native, context, route_index=route)
        reference = _production_materialized_forward(core, reference, context, route)
        if step in RECURRENCE_DEPTHS:
            checkpoints.append({"depth": step, **_gap(reference, native)})
    return {
        "checkpoints": checkpoints,
        "allclose": all(bool(row["allclose"]) for row in checkpoints),
        "max_abs": max(float(row["max_abs"]) for row in checkpoints),
        "max_relative_l2": max(float(row["relative_l2"]) for row in checkpoints),
    }


@torch.inference_mode()
def _state_dict_roundtrip(core: SharedBasisFixedRoutingCore, source_core, seed: int) -> bool:
    clone = SharedBasisFixedRoutingCore(source_core, core.rank).to(core.up_projection.device)
    clone.load_state_dict(core.state_dict(), strict=True)
    generator = torch.Generator(device="cpu").manual_seed(seed + 70000)
    working = torch.randn(
        3, core.config.slots, core.config.width, generator=generator, dtype=torch.float32
    ).to(core.up_projection.device) * 0.05
    context = torch.randn(
        3, core.config.slots, core.config.width, generator=generator, dtype=torch.float32
    ).to(core.up_projection.device) * 0.05
    return all(
        torch.equal(
            core(working, context, route_index=route),
            clone(working, context, route_index=route),
        )
        for route in range(core.config.modules)
    )


def run(*, protected_result_path: Path, c77_summary_path: Path, output_dir: Path) -> dict:
    if not torch.cuda.is_available():
        raise RuntimeError("C78 requires CUDA")
    c77 = json.loads(c77_summary_path.read_text(encoding="utf-8"))
    if c77.get("experiment_id") != "C77-shared-basis-final-selected-rank-recurrence-equivalence":
        raise RuntimeError("C78 requires accepted C77 summary")
    if c77.get("status") != "PASS":
        raise RuntimeError("C77 summary is not PASS")
    if c77.get("summary", {}).get("selected_ranks") != SELECTED_RANKS:
        raise RuntimeError("C78 selected ranks differ from C77")
    if not bool(c77.get("summary", {}).get("all_runtime_formula_equivalent")):
        raise RuntimeError("C78 requires C77 runtime equivalence")

    protected_before = _sha256(protected_result_path)
    device = torch.device("cuda")
    torch.cuda.set_device(0)
    torch.set_num_threads(2)
    torch.set_float32_matmul_precision("highest")

    records = []
    completed = 0
    total = len(TASKS) * len(SEEDS)
    for task in TASKS:
        rank = SELECTED_RANKS[task]
        spec = TASK_SPECS[task]
        for seed in SEEDS:
            print(f"[C78] task={task} seed={seed} start ({completed + 1}/{total}) rank={rank}", flush=True)
            _config, initial_model, train, validation, evaluator = _build_task(task, seed, device)

            reference_model = copy.deepcopy(initial_model).to(device)
            reference_model.core = JointTrainSharedBasisCore(initial_model.core, rank).to(device)
            production_model = copy.deepcopy(initial_model).to(device)
            production_model.core = SharedBasisFixedRoutingCore(initial_model.core, rank).to(device)

            initial_gap = _initial_effective_gap(reference_model.core, production_model.core)
            gradient = _gradient_equivalence(reference_model.core, production_model.core, seed)

            ref_loss, prod_loss = _train_pair(
                task=task,
                seed=seed,
                reference_model=reference_model,
                production_model=production_model,
                train=train,
                device=device,
            )

            reference_output = _validation_output(task, reference_model, validation, device)
            production_output = _validation_output(task, production_model, validation, device)
            output_gap = _gap(reference_output, production_output)
            semantic_equal = _semantic_equal(task, reference_output, production_output)
            score_name = str(spec["score_name"])
            reference_score = float(evaluator(reference_model, validation)[score_name])
            production_score = float(evaluator(production_model, validation)[score_name])

            recurrence = _recurrence_equivalence(production_model.core, seed)
            roundtrip = _state_dict_roundtrip(production_model.core, initial_model.core, seed)

            record = {
                "task": task,
                "seed": seed,
                "rank": rank,
                "initial_effective_weight_max_abs_gap": initial_gap,
                "gradient_equivalence": gradient,
                "reference_final_loss": ref_loss,
                "production_final_loss": prod_loss,
                "reference_validation_score": reference_score,
                "production_validation_score": production_score,
                "validation_score_equal": abs(reference_score - production_score) <= 1e-12,
                "validation_semantic_equal": semantic_equal,
                "validation_output_gap": output_gap,
                "production_materialized_recurrence": recurrence,
                "state_dict_roundtrip_exact": roundtrip,
            }
            records.append(record)
            completed += 1
            print(
                f"[C78] task={task} seed={seed} done ({completed}/{total}) "
                f"score_ref={reference_score:.8f} score_prod={production_score:.8f} "
                f"out_max_abs={output_gap['max_abs']:.3e} rec_max_abs={recurrence['max_abs']:.3e}",
                flush=True,
            )
            del initial_model, reference_model, production_model
            torch.cuda.empty_cache()

    protected_after = _sha256(protected_result_path)
    if protected_after != protected_before:
        raise RuntimeError("protected C37 result changed during C78")

    summary = {
        "run_count": len(records),
        "selected_ranks": SELECTED_RANKS,
        "seeds": list(SEEDS),
        "initial_effective_weight_max_abs_gap": _stats(
            [float(row["initial_effective_weight_max_abs_gap"]) for row in records]
        ),
        "gradient_max_abs_gap": _stats(
            [float(row["gradient_equivalence"]["max_abs"]) for row in records]
        ),
        "validation_output_max_abs_gap": _stats(
            [float(row["validation_output_gap"]["max_abs"]) for row in records]
        ),
        "recurrence_max_abs_gap": _stats(
            [float(row["production_materialized_recurrence"]["max_abs"]) for row in records]
        ),
        "all_initial_effective_weights_allclose": all(
            float(row["initial_effective_weight_max_abs_gap"]) <= 1e-5 for row in records
        ),
        "all_gradients_allclose": all(bool(row["gradient_equivalence"]["allclose"]) for row in records),
        "all_validation_scores_equal": all(bool(row["validation_score_equal"]) for row in records),
        "all_validation_semantic_equal": all(bool(row["validation_semantic_equal"]) for row in records),
        "all_validation_outputs_allclose": all(bool(row["validation_output_gap"]["allclose"]) for row in records),
        "all_production_materialized_recurrence_allclose": all(
            bool(row["production_materialized_recurrence"]["allclose"]) for row in records
        ),
        "all_state_dict_roundtrips_exact": all(bool(row["state_dict_roundtrip_exact"]) for row in records),
    }
    summary["production_integration_gate_passed"] = all(
        bool(summary[name])
        for name in (
            "all_initial_effective_weights_allclose",
            "all_gradients_allclose",
            "all_validation_scores_equal",
            "all_validation_semantic_equal",
            "all_validation_outputs_allclose",
            "all_production_materialized_recurrence_allclose",
            "all_state_dict_roundtrips_exact",
        )
    )

    report = {
        "experiment_id": EXPERIMENT_ID,
        "stage": "V5-C",
        "status": "PASS",
        "status_meaning": "opt-in production Shared-Basis direct-training integration verification",
        "tasks": list(TASKS),
        "selected_ranks": SELECTED_RANKS,
        "seeds": list(SEEDS),
        "records": records,
        "summary": summary,
        "C77_summary_sha256": _sha256(c77_summary_path),
        "C37_result_sha256_before": protected_before,
        "C37_result_sha256_after": protected_after,
        "production_runtime_modified": True,
        "default_dense_runtime_changed": False,
        "gate_c_candidate": False,
        "limitations": [
            "C78 covers only the current three tiny Gate-B task families",
            "direct-training comparison uses float32 CUDA and the current AdamW schedules",
            "production class is opt-in and does not yet replace default model construction",
            "C78 does not by itself establish broad-task quality or Gate C passage",
        ],
    }
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "summary.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protected-result", type=Path, default=DEFAULT_PROTECTED_RESULT)
    parser.add_argument("--c77-summary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    started = time.perf_counter()
    result = run(
        protected_result_path=args.protected_result,
        c77_summary_path=args.c77_summary,
        output_dir=args.output_dir,
    )
    display = dict(result)
    display["records"] = "omitted from console; see summary.json"
    display["elapsed_seconds"] = time.perf_counter() - started
    print("\n=== C78 RESULT ===")
    print(json.dumps(display, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
