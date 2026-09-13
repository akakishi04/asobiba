"""C79: diagnose C78 direct-training drift without changing production code.

C78 was a valid negative integration result: initial effective weights matched
exactly, initial gradients matched to ~1e-9, final validation scores/semantics
matched, production native-vs-materialized recurrence matched, and state_dict
round-trips were exact.  The only failed integration flag was final validation
tensor allclose after long direct training, concentrated in Language.

C79 reuses the three C78 Language seeds because this is a mechanism diagnosis,
not a fresh quality estimate.  From one identical factorized initialization it
trains three paths on exactly the same batches:

A. accepted benchmark materialized Shared-Basis core;
B. production GEMM-native SharedBasisFixedRoutingCore;
C. the same production parameter layout as B, but materialized effective-weight
   arithmetic during forward.

If C tracks A while B drifts, the C78 failure is localized to accumulation from
GEMM-native floating-point arithmetic order during training.  If B and C both
drift from A, parameter layout / optimizer execution is also implicated.

No production implementation is modified by C79.
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

from fold_lm.v05.language_task import evaluate_language
from fold_lm.v05.modules import SharedBasisFixedRoutingCore
from fold_lm.v05_benchmarks.gate_b_baseline_comparison import _build_language
from fold_lm.v05_benchmarks.gate_c_shared_basis_aligned_joint_training import TASK_SPECS
from fold_lm.v05_benchmarks.gate_c_shared_basis_direct_joint_training import (
    JointTrainSharedBasisCore,
    _task_loss,
)
from fold_lm.v05_benchmarks.gate_c_shared_basis_production_optin_integration import (
    _copy_reference_into_production,
    _gap,
    _semantic_equal,
    _validation_output,
)

EXPERIMENT_ID = "C79-shared-basis-training-arithmetic-drift-diagnosis"
DEFAULT_PROTECTED_RESULT = Path("runs/chatgpt-last-result.json")
SEEDS = (20261011, 20261012, 20261013)
RANK = 4
CHECKPOINTS = (1, 10, 50, 150, 300, 450, 600)
RTOL = 5e-4
ATOL = 1e-4


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


class _MaterializedProductionCore(SharedBasisFixedRoutingCore):
    """Diagnostic only: production parameter layout with materialized arithmetic."""

    def forward(
        self,
        working: torch.Tensor,
        context: torch.Tensor,
        *,
        route_index: int,
    ) -> torch.Tensor:
        self._validate_route_index(route_index)
        self._validate_inputs(working, context)
        z = working + context
        shared_delta = self.shared(z)
        normalized = self.norms[route_index](z)
        up, down = self.materialized_role_weights(route_index)
        hidden = F.gelu(F.linear(normalized, up, self.up_biases[route_index]))
        routed_delta = F.linear(hidden, down, self.down_biases[route_index])
        gate = torch.sigmoid(self.gate_logits).to(dtype=working.dtype, device=working.device)
        updated = working + gate * (shared_delta + routed_delta)
        if not torch.isfinite(updated).all():
            raise ValueError("diagnostic materialized production update produced non-finite values")
        return updated


def _parameter_gap_reference_to_production(
    reference: JointTrainSharedBasisCore,
    production: SharedBasisFixedRoutingCore,
) -> float:
    hidden = int(reference.config.width * reference.config.hidden_mult)
    pairs: list[tuple[torch.Tensor, torch.Tensor]] = [
        (reference.gate_logits, production.gate_logits),
        (reference.up_base, production.up_projection[:hidden]),
        (reference.up_basis, production.up_projection[hidden:]),
        (reference.up_coeff, production.up_coeff),
        (reference.down_base, production.down_projection[: reference.config.width]),
        (reference.down_basis, production.down_projection[reference.config.width :]),
        (reference.down_coeff, production.down_coeff),
        (reference.up_biases, production.up_biases),
        (reference.down_biases, production.down_biases),
    ]
    for left_module, right_module in zip(reference.norms, production.norms, strict=True):
        pairs.extend(
            (left, right)
            for left, right in zip(left_module.parameters(), right_module.parameters(), strict=True)
        )
    pairs.extend(
        (left, right)
        for left, right in zip(reference.shared.parameters(), production.shared.parameters(), strict=True)
    )
    return max(float((left.detach().float() - right.detach().float()).abs().max().item()) for left, right in pairs)


def _parameter_gap_production_pair(
    left: SharedBasisFixedRoutingCore,
    right: SharedBasisFixedRoutingCore,
) -> float:
    left_params = dict(left.named_parameters())
    right_params = dict(right.named_parameters())
    if set(left_params) != set(right_params):
        raise RuntimeError("C79 production parameter names differ")
    return max(
        float((left_params[name].detach().float() - right_params[name].detach().float()).abs().max().item())
        for name in left_params
    )


@torch.inference_mode()
def _snapshot(
    *,
    reference_model,
    native_model,
    materialized_layout_model,
    validation,
    device: torch.device,
    step: int,
) -> dict:
    reference_output = _validation_output("language", reference_model, validation, device)
    native_output = _validation_output("language", native_model, validation, device)
    materialized_output = _validation_output(
        "language", materialized_layout_model, validation, device
    )
    native_gap = _gap(reference_output, native_output)
    materialized_gap = _gap(reference_output, materialized_output)
    native_score = float(evaluate_language(native_model, validation)["accuracy"])
    materialized_score = float(evaluate_language(materialized_layout_model, validation)["accuracy"])
    reference_score = float(evaluate_language(reference_model, validation)["accuracy"])
    return {
        "step": step,
        "reference_score": reference_score,
        "native_score": native_score,
        "materialized_layout_score": materialized_score,
        "native_semantic_equal": _semantic_equal("language", reference_output, native_output),
        "materialized_layout_semantic_equal": _semantic_equal(
            "language", reference_output, materialized_output
        ),
        "native_output_gap": native_gap,
        "materialized_layout_output_gap": materialized_gap,
        "native_parameter_max_abs_gap": _parameter_gap_reference_to_production(
            reference_model.core, native_model.core
        ),
        "materialized_layout_parameter_max_abs_gap": _parameter_gap_reference_to_production(
            reference_model.core, materialized_layout_model.core
        ),
        "native_vs_materialized_layout_parameter_max_abs_gap": _parameter_gap_production_pair(
            native_model.core, materialized_layout_model.core
        ),
    }


def _train_one_seed(seed: int, device: torch.device) -> dict:
    _config, initial_model, train, validation = _build_language(seed, "v5b", device)

    reference_model = copy.deepcopy(initial_model).to(device)
    reference_model.core = JointTrainSharedBasisCore(initial_model.core, RANK).to(device)

    native_model = copy.deepcopy(initial_model).to(device)
    native_model.core = SharedBasisFixedRoutingCore(initial_model.core, RANK).to(device)
    _copy_reference_into_production(reference_model.core, native_model.core)

    materialized_layout_model = copy.deepcopy(initial_model).to(device)
    materialized_layout_model.core = _MaterializedProductionCore(initial_model.core, RANK).to(device)
    _copy_reference_into_production(reference_model.core, materialized_layout_model.core)

    spec = TASK_SPECS["language"]
    steps = int(spec["steps"])
    if steps != max(CHECKPOINTS):
        raise RuntimeError(f"C79 expected {max(CHECKPOINTS)} language steps, got {steps}")
    lr = float(spec["common_lr"])
    batch_size = int(spec["batch_size"])

    optimizers = (
        torch.optim.AdamW(reference_model.parameters(), lr=lr, weight_decay=0.0),
        torch.optim.AdamW(native_model.parameters(), lr=lr, weight_decay=0.0),
        torch.optim.AdamW(materialized_layout_model.parameters(), lr=lr, weight_decay=0.0),
    )
    models = (reference_model, native_model, materialized_layout_model)
    sampler = torch.Generator(device="cpu").manual_seed(seed + 200)
    snapshots = []

    for model in models:
        model.train()

    for step in range(1, steps + 1):
        indices = torch.randint(train.size, (batch_size,), generator=sampler)
        losses = []
        for model, optimizer in zip(models, optimizers, strict=True):
            optimizer.zero_grad(set_to_none=True)
            loss = _task_loss("language", model, train, indices, device)
            if not torch.isfinite(loss):
                raise RuntimeError(f"C79 seed={seed} step={step} non-finite loss")
            loss.backward()
            optimizer.step()
            losses.append(float(loss.detach().item()))

        if step in CHECKPOINTS:
            snapshot = _snapshot(
                reference_model=reference_model,
                native_model=native_model,
                materialized_layout_model=materialized_layout_model,
                validation=validation,
                device=device,
                step=step,
            )
            snapshot["reference_loss"] = losses[0]
            snapshot["native_loss"] = losses[1]
            snapshot["materialized_layout_loss"] = losses[2]
            snapshots.append(snapshot)
            print(
                f"[C79] seed={seed} step={step}/{steps} "
                f"native_out={snapshot['native_output_gap']['max_abs']:.3e} "
                f"mat_out={snapshot['materialized_layout_output_gap']['max_abs']:.3e} "
                f"native_param={snapshot['native_parameter_max_abs_gap']:.3e} "
                f"mat_param={snapshot['materialized_layout_parameter_max_abs_gap']:.3e}",
                flush=True,
            )
            for model in models:
                model.train()

    final = snapshots[-1]
    return {
        "seed": seed,
        "snapshots": snapshots,
        "final_native_allclose": bool(final["native_output_gap"]["allclose"]),
        "final_materialized_layout_allclose": bool(
            final["materialized_layout_output_gap"]["allclose"]
        ),
        "final_native_semantic_equal": bool(final["native_semantic_equal"]),
        "final_materialized_layout_semantic_equal": bool(
            final["materialized_layout_semantic_equal"]
        ),
        "final_native_output_max_abs_gap": float(final["native_output_gap"]["max_abs"]),
        "final_materialized_layout_output_max_abs_gap": float(
            final["materialized_layout_output_gap"]["max_abs"]
        ),
        "final_native_parameter_max_abs_gap": float(final["native_parameter_max_abs_gap"]),
        "final_materialized_layout_parameter_max_abs_gap": float(
            final["materialized_layout_parameter_max_abs_gap"]
        ),
    }


def run(*, protected_result_path: Path, c78_summary_path: Path, output_dir: Path) -> dict:
    if not torch.cuda.is_available():
        raise RuntimeError("C79 requires CUDA")
    c78 = json.loads(c78_summary_path.read_text(encoding="utf-8"))
    if c78.get("experiment_id") != "C78-shared-basis-production-optin-integration":
        raise RuntimeError("C79 requires C78 summary")
    if c78.get("status") != "PASS":
        raise RuntimeError("C79 requires valid C78 execution")
    c78s = c78.get("summary", {})
    if bool(c78s.get("production_integration_gate_passed")):
        raise RuntimeError("C79 diagnosis is only for the failed C78 integration gate")
    if not bool(c78s.get("all_validation_scores_equal")) or not bool(
        c78s.get("all_validation_semantic_equal")
    ):
        raise RuntimeError("C79 expects C78 score/semantic equality")
    if bool(c78s.get("all_validation_outputs_allclose")):
        raise RuntimeError("C79 expects C78 tensor-allclose failure")

    protected_before = _sha256(protected_result_path)
    device = torch.device("cuda")
    torch.cuda.set_device(0)
    torch.set_num_threads(2)
    torch.set_float32_matmul_precision("highest")

    records = []
    for index, seed in enumerate(SEEDS, start=1):
        print(f"[C79] seed={seed} start ({index}/{len(SEEDS)})", flush=True)
        records.append(_train_one_seed(seed, device))
        torch.cuda.empty_cache()

    protected_after = _sha256(protected_result_path)
    if protected_after != protected_before:
        raise RuntimeError("protected C37 result changed during C79")

    native_allclose = [bool(row["final_native_allclose"]) for row in records]
    materialized_allclose = [bool(row["final_materialized_layout_allclose"]) for row in records]
    native_output_gaps = [float(row["final_native_output_max_abs_gap"]) for row in records]
    materialized_output_gaps = [
        float(row["final_materialized_layout_output_max_abs_gap"]) for row in records
    ]
    native_parameter_gaps = [float(row["final_native_parameter_max_abs_gap"]) for row in records]
    materialized_parameter_gaps = [
        float(row["final_materialized_layout_parameter_max_abs_gap"]) for row in records
    ]

    arithmetic_drift_supported = (
        all(materialized_allclose)
        and not all(native_allclose)
        and max(materialized_output_gaps) < max(native_output_gaps)
        and max(materialized_parameter_gaps) < max(native_parameter_gaps)
    )

    summary = {
        "seed_count": len(SEEDS),
        "seeds": list(SEEDS),
        "reuses_c78_failure_seeds_for_mechanism_diagnosis": True,
        "all_native_final_outputs_allclose": all(native_allclose),
        "all_materialized_layout_final_outputs_allclose": all(materialized_allclose),
        "all_native_final_semantics_equal": all(
            bool(row["final_native_semantic_equal"]) for row in records
        ),
        "all_materialized_layout_final_semantics_equal": all(
            bool(row["final_materialized_layout_semantic_equal"]) for row in records
        ),
        "native_final_output_max_abs_gap": _stats(native_output_gaps),
        "materialized_layout_final_output_max_abs_gap": _stats(materialized_output_gaps),
        "native_final_parameter_max_abs_gap": _stats(native_parameter_gaps),
        "materialized_layout_final_parameter_max_abs_gap": _stats(materialized_parameter_gaps),
        "training_arithmetic_order_drift_supported": arithmetic_drift_supported,
    }

    report = {
        "experiment_id": EXPERIMENT_ID,
        "stage": "V5-C",
        "status": "PASS",
        "status_meaning": "diagnosis of C78 long-training tensor drift",
        "task": "language",
        "rank": RANK,
        "seeds": list(SEEDS),
        "checkpoints": list(CHECKPOINTS),
        "records": records,
        "summary": summary,
        "C78_summary_sha256": _sha256(c78_summary_path),
        "C37_result_sha256_before": protected_before,
        "C37_result_sha256_after": protected_after,
        "production_runtime_modified": False,
        "gate_c_candidate": False,
        "limitations": [
            "C79 is a mechanism diagnosis on the exact C78 Language failure seeds",
            "C79 is not a fresh quality or generalization estimate",
            "C79 does not alter the production implementation",
            "C79 does not establish Gate C passage",
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
    parser.add_argument("--c78-summary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    started = time.perf_counter()
    result = run(
        protected_result_path=args.protected_result,
        c78_summary_path=args.c78_summary,
        output_dir=args.output_dir,
    )
    display = dict(result)
    display["records"] = "omitted from console; see summary.json"
    display["elapsed_seconds"] = time.perf_counter() - started
    print("\n=== C79 RESULT ===")
    print(json.dumps(display, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
