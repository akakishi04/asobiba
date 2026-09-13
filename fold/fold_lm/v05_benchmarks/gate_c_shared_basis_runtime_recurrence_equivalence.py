"""C70: GEMM-native shared-basis execution equivalence under recurrence.

C69 found no systematic condition-quality deficit for aligned rank-4 shared-basis
training across 12 exhaustive seeds.  The next Gate-C question is therefore not
more rank, but whether the GPU-friendly execution formula identified in C58 can
replace per-call effective-weight materialization without changing model
semantics as recurrent state updates accumulate.

For each accepted Gate-B task family and each of the original three deterministic
seeds, C70:

1. trains the selected shared-basis model directly from initialization using the
   accepted C67 rule ``factor_lr = common_lr``;
2. keeps that trained model as the materialized-weight reference;
3. clones its parameters into a GEMM-native inference core that stores
   ``[W_base; B_shared]`` and evaluates ``base + latent @ A_module.T`` without
   materializing ``W_base + A_module @ B_shared``;
4. compares complete task validation outputs;
5. stress-tests the two cores for 64 recurrent updates with identical contexts
   and alternating routes, recording gaps at depths 1/2/4/8/16/32/64.

C70 is a pre-integration numerical/semantic equivalence gate.  It does not modify
``fold_lm.v05.modules`` and does not benchmark latency or memory yet.
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
from torch import nn
from torch.nn import functional as F

from fold_lm.v05.modules import LearnedCoreConfig
from fold_lm.v05_benchmarks.gate_b_baseline_comparison import DEFAULT_SEEDS
from fold_lm.v05_benchmarks.gate_c_shared_basis_aligned_joint_training import TASK_SPECS
from fold_lm.v05_benchmarks.gate_c_shared_basis_direct_joint_training import (
    JointTrainSharedBasisCore,
    _build_task,
    _task_loss,
)
from fold_lm.v05_benchmarks.gate_c_shared_basis_task_aware_recovery import _storage


EXPERIMENT_ID = "C70-shared-basis-runtime-recurrence-equivalence"
DEFAULT_PROTECTED_RESULT = Path("runs/chatgpt-last-result.json")
SEEDS = tuple(int(seed) for seed in DEFAULT_SEEDS)
TASKS = ("condition", "composition", "language")
RECURRENCE_DEPTHS = (1, 2, 4, 8, 16, 32, 64)
STRESS_BATCH = 8
CONTEXT_SCALE = 0.05
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


def _progress_marks(steps: int) -> tuple[int, ...]:
    return tuple(sorted({max(1, round(steps * x)) for x in (0.25, 0.5, 0.75, 1.0)}))


class GemmNativeSharedBasisCore(nn.Module):
    """Inference-only algebraic form of a trained shared-basis routed core.

    Persistent routed-role storage is a concatenated projection matrix plus the
    module-specific coefficient bank.  No effective routed weight matrix is
    materialized in ``forward``.
    """

    def __init__(self, source: JointTrainSharedBasisCore) -> None:
        super().__init__()
        if not isinstance(source, JointTrainSharedBasisCore):
            raise TypeError("source must be JointTrainSharedBasisCore")
        self.config: LearnedCoreConfig = source.config
        self.rank = int(source.rank)
        self.shared = copy.deepcopy(source.shared)
        self.norms = copy.deepcopy(source.norms)
        self.gate_logits = nn.Parameter(source.gate_logits.detach().clone())
        self.up_projection = nn.Parameter(
            torch.cat((source.up_base.detach(), source.up_basis.detach()), dim=0).clone()
        )
        self.down_projection = nn.Parameter(
            torch.cat((source.down_base.detach(), source.down_basis.detach()), dim=0).clone()
        )
        self.up_coeff = nn.Parameter(source.up_coeff.detach().clone())
        self.down_coeff = nn.Parameter(source.down_coeff.detach().clone())
        self.up_biases = nn.Parameter(source.up_biases.detach().clone())
        self.down_biases = nn.Parameter(source.down_biases.detach().clone())

    def initial_working_state(
        self,
        batch_size: int,
        *,
        device: torch.device | str | None = None,
        dtype: torch.dtype | None = None,
    ) -> torch.Tensor:
        if type(batch_size) is not int or batch_size <= 0:
            raise ValueError("batch_size must be positive")
        return torch.zeros(
            batch_size,
            self.config.slots,
            self.config.width,
            device=self.up_projection.device if device is None else device,
            dtype=self.up_projection.dtype if dtype is None else dtype,
        )

    @staticmethod
    def _role_forward(
        value: torch.Tensor,
        projection: torch.Tensor,
        coeff: torch.Tensor,
        bias: torch.Tensor,
        *,
        output_width: int,
    ) -> torch.Tensor:
        original_shape = tuple(value.shape[:-1])
        flat = value.reshape(-1, value.shape[-1])
        projected = F.linear(flat, projection, None)
        base = projected[:, :output_width]
        latent = projected[:, output_width:]
        output = torch.addmm(base, latent, coeff.transpose(0, 1))
        output = output + bias
        return output.reshape(*original_shape, output_width)

    def forward(
        self,
        working: torch.Tensor,
        context: torch.Tensor,
        *,
        route_index: int,
    ) -> torch.Tensor:
        if type(route_index) is not int or not 0 <= route_index < self.config.modules:
            raise ValueError("route_index out of range")
        if working.ndim != 3 or tuple(working.shape[1:]) != (
            self.config.slots,
            self.config.width,
        ):
            raise ValueError("working shape does not match configured slots/width")
        if context.shape != working.shape:
            raise ValueError("context shape must match working")

        z = working + context
        shared_delta = self.shared(z)
        normalized = self.norms[route_index](z)
        hidden = self._role_forward(
            normalized,
            self.up_projection,
            self.up_coeff[route_index],
            self.up_biases[route_index],
            output_width=self.config.width * self.config.hidden_mult,
        )
        hidden = F.gelu(hidden)
        routed_delta = self._role_forward(
            hidden,
            self.down_projection,
            self.down_coeff[route_index],
            self.down_biases[route_index],
            output_width=self.config.width,
        )
        gate = torch.sigmoid(self.gate_logits).to(dtype=z.dtype, device=z.device)
        return working + gate * (shared_delta + routed_delta)


def _train_factorized(*, task: str, seed: int, model, train, device: torch.device) -> float:
    spec = TASK_SPECS[task]
    steps = int(spec["steps"])
    lr = float(spec["common_lr"])
    batch_size = int(spec["batch_size"])
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=0.0)
    sampler = torch.Generator(device="cpu").manual_seed(seed + 200)
    marks = _progress_marks(steps)
    final_loss = None
    model.train()
    for step in range(1, steps + 1):
        indices = torch.randint(train.size, (batch_size,), generator=sampler)
        optimizer.zero_grad(set_to_none=True)
        loss = _task_loss(task, model, train, indices, device)
        if not torch.isfinite(loss):
            raise RuntimeError(f"C70 task={task} seed={seed} non-finite training loss")
        loss.backward()
        optimizer.step()
        final_loss = float(loss.detach().item())
        if step in marks:
            print(
                f"[C70] task={task} seed={seed} train step={step}/{steps} "
                f"loss={final_loss:.8f}",
                flush=True,
            )
    return float(final_loss)


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
    raise ValueError(f"unknown task: {task}")


def _gap(reference: torch.Tensor, candidate: torch.Tensor) -> dict[str, float | bool]:
    diff = (candidate.float() - reference.float()).reshape(-1)
    ref = reference.float().reshape(-1)
    max_abs = float(diff.abs().max().item()) if diff.numel() else 0.0
    l2 = float(torch.linalg.vector_norm(diff).item()) if diff.numel() else 0.0
    ref_l2 = float(torch.linalg.vector_norm(ref).item()) if ref.numel() else 0.0
    rel_l2 = l2 / max(ref_l2, 1e-12)
    return {
        "max_abs": max_abs,
        "relative_l2": rel_l2,
        "allclose": bool(torch.allclose(candidate, reference, rtol=RTOL, atol=ATOL)),
    }


def _semantic_equal(task: str, reference: torch.Tensor, candidate: torch.Tensor) -> bool:
    if task in ("condition", "language"):
        return bool(torch.equal(reference.argmax(dim=-1), candidate.argmax(dim=-1)))
    if task == "composition":
        return bool(torch.allclose(candidate, reference, rtol=RTOL, atol=ATOL))
    raise ValueError(f"unknown task: {task}")


@torch.inference_mode()
def _recurrence_stress(
    *,
    reference_core: JointTrainSharedBasisCore,
    runtime_core: GemmNativeSharedBasisCore,
    task_index: int,
    seed: int,
    device: torch.device,
) -> dict:
    reference_core.eval()
    runtime_core.eval()
    generator = torch.Generator(device="cpu").manual_seed(seed + 10000 + 1000 * task_index)
    reference = reference_core.initial_working_state(STRESS_BATCH, device=device)
    runtime = runtime_core.initial_working_state(STRESS_BATCH, device=device)
    checkpoints: list[dict] = []

    for step in range(1, max(RECURRENCE_DEPTHS) + 1):
        context = (
            torch.randn(
                STRESS_BATCH,
                reference_core.config.slots,
                reference_core.config.width,
                generator=generator,
                dtype=torch.float32,
            )
            * CONTEXT_SCALE
        ).to(device)
        route_index = (step - 1) % reference_core.config.modules
        reference = reference_core(reference, context, route_index=route_index)
        runtime = runtime_core(runtime, context, route_index=route_index)
        if not torch.isfinite(reference).all() or not torch.isfinite(runtime).all():
            raise RuntimeError(
                f"C70 recurrence produced non-finite state at task_index={task_index} "
                f"seed={seed} step={step}"
            )
        if step in RECURRENCE_DEPTHS:
            record = {"depth": step, **_gap(reference, runtime)}
            record["reference_max_abs"] = float(reference.abs().max().item())
            checkpoints.append(record)

    return {
        "checkpoints": checkpoints,
        "all_depths_allclose": all(bool(row["allclose"]) for row in checkpoints),
        "max_abs_gap": max(float(row["max_abs"]) for row in checkpoints),
        "max_relative_l2_gap": max(float(row["relative_l2"]) for row in checkpoints),
    }


def run(*, protected_result_path: Path, c69_summary_path: Path, output_dir: Path) -> dict:
    if not torch.cuda.is_available():
        raise RuntimeError("C70 requires CUDA")

    c69 = json.loads(c69_summary_path.read_text(encoding="utf-8"))
    if c69.get("experiment_id") != "C69-shared-basis-condition-12seed-exhaustive-robustness":
        raise RuntimeError("C70 requires accepted C69 summary")
    if c69.get("status") != "PASS":
        raise RuntimeError("C69 summary is not PASS")
    c69s = c69.get("summary", {})
    if int(c69s.get("seed_count", -1)) != 12:
        raise RuntimeError("C70 requires the accepted 12-seed C69 run")
    if int(c69s.get("direct_win_seed_count", -1)) != 6 or int(
        c69s.get("dense_win_seed_count", -1)
    ) != 6:
        raise RuntimeError("C70 requires the accepted mixed-sign C69 result")

    protected_before = _sha256(protected_result_path)
    device = torch.device("cuda")
    torch.cuda.set_device(0)
    torch.set_num_threads(2)
    torch.set_float32_matmul_precision("highest")

    records: list[dict] = []
    total = len(TASKS) * len(SEEDS)
    completed = 0

    for task_index, task in enumerate(TASKS):
        spec = TASK_SPECS[task]
        rank = int(spec["rank"])
        for seed in SEEDS:
            print(
                f"[C70] task={task} seed={seed} start ({completed + 1}/{total}) rank={rank}",
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
                raise RuntimeError(f"C70 task={task} selected rank is not sub-dense")

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
                f"[C70] task={task} seed={seed} done ({completed}/{total}) "
                f"score_ref={reference_score:.6f} score_runtime={runtime_score:.6f} "
                f"val_max_abs={float(validation_gap['max_abs']):.3e} "
                f"rec64_max_abs={float(recurrence['checkpoints'][-1]['max_abs']):.3e} "
                f"rec_allclose={recurrence['all_depths_allclose']}",
                flush=True,
            )

            del initial_model, reference_model, runtime_model
            torch.cuda.empty_cache()

    protected_after = _sha256(protected_result_path)
    if protected_after != protected_before:
        raise RuntimeError("protected C37 result changed during C70")

    validation_max_abs = [float(row["validation_output_gap"]["max_abs"]) for row in records]
    recurrence_max_abs = [float(row["recurrence"]["max_abs_gap"]) for row in records]
    recurrence_rel_l2 = [float(row["recurrence"]["max_relative_l2_gap"]) for row in records]
    all_validation_scores_equal = all(bool(row["validation_score_equal"]) for row in records)
    all_validation_semantic_equal = all(bool(row["validation_semantic_equal"]) for row in records)
    all_validation_outputs_allclose = all(
        bool(row["validation_output_gap"]["allclose"]) for row in records
    )
    all_recurrence_allclose = all(bool(row["recurrence"]["all_depths_allclose"]) for row in records)
    all_runtime_formula_equivalent = (
        all_validation_scores_equal
        and all_validation_semantic_equal
        and all_validation_outputs_allclose
        and all_recurrence_allclose
    )

    summary = {
        "run_count": len(records),
        "recurrence_depths": list(RECURRENCE_DEPTHS),
        "rtol": RTOL,
        "atol": ATOL,
        "validation_max_abs_gap": _stats(validation_max_abs),
        "recurrence_max_abs_gap": _stats(recurrence_max_abs),
        "recurrence_max_relative_l2_gap": _stats(recurrence_rel_l2),
        "all_validation_scores_equal": all_validation_scores_equal,
        "all_validation_semantic_equal": all_validation_semantic_equal,
        "all_validation_outputs_allclose": all_validation_outputs_allclose,
        "all_recurrence_allclose": all_recurrence_allclose,
        "all_runtime_formula_equivalent": all_runtime_formula_equivalent,
    }

    report = {
        "experiment_id": EXPERIMENT_ID,
        "stage": "V5-C",
        "status": "PASS",
        "status_meaning": "GEMM-native shared-basis execution equivalence under repeated state updates",
        "tasks": list(TASKS),
        "seeds": list(SEEDS),
        "training_rule": "factor_lr_equals_common_lr",
        "execution_reference": "materialize W_base + A_module @ B_shared then F.linear",
        "execution_candidate": "F.linear([W_base; B_shared]) plus coefficient addmm, no effective-weight materialization",
        "records": records,
        "summary": summary,
        "C69_summary_sha256": _sha256(c69_summary_path),
        "C37_result_sha256_before": protected_before,
        "C37_result_sha256_after": protected_after,
        "production_runtime_modified": False,
        "gate_c_candidate": False,
        "limitations": [
            "C70 is numerical/semantic equivalence only; it does not benchmark latency or memory",
            "recurrence stress uses deterministic synthetic contexts rather than a new learned long-horizon task",
            "only the three current Gate-B task shapes and three original seeds are covered",
            "the GEMM-native core exists only inside the benchmark and is not yet production integration",
            "C70 cannot establish Gate C pass by itself",
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
    parser.add_argument("--c69-summary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)

    started = time.perf_counter()
    result = run(
        protected_result_path=args.protected_result,
        c69_summary_path=args.c69_summary,
        output_dir=args.output_dir,
    )
    display = dict(result)
    display["records"] = "omitted from console; see summary.json"
    display["elapsed_seconds"] = time.perf_counter() - started
    print("\n=== C70 RESULT ===")
    print(json.dumps(display, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
