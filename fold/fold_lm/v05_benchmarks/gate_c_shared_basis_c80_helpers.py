from __future__ import annotations

import copy
import torch

from fold_lm.v05.modules import SharedBasisFixedRoutingCore
from fold_lm.v05_benchmarks.gate_c_shared_basis_aligned_joint_training import TASK_SPECS
from fold_lm.v05_benchmarks.gate_c_shared_basis_direct_joint_training import _task_loss
from fold_lm.v05_benchmarks.gate_c_shared_basis_production_optin_integration import _gap
from fold_lm.v05_benchmarks.gate_c_shared_basis_training_arithmetic_drift_diagnosis import _parameter_gap_reference_to_production

DEPTHS = (1, 2, 4, 8, 16, 32, 64)


def train_pair(task, seed, reference_model, production_model, train, device):
    spec = TASK_SPECS[task]
    ref_opt = torch.optim.AdamW(reference_model.parameters(), lr=float(spec["common_lr"]), weight_decay=0.0)
    prod_opt = torch.optim.AdamW(production_model.parameters(), lr=float(spec["common_lr"]), weight_decay=0.0)
    generator = torch.Generator(device="cpu").manual_seed(seed + 200)
    for _step in range(1, int(spec["steps"]) + 1):
        indices = torch.randint(train.size, (int(spec["batch_size"]),), generator=generator)
        ref_opt.zero_grad(set_to_none=True)
        ref_loss = _task_loss(task, reference_model, train, indices, device)
        ref_loss.backward(); ref_opt.step()
        prod_opt.zero_grad(set_to_none=True)
        prod_loss = _task_loss(task, production_model, train, indices, device)
        prod_loss.backward(); prod_opt.step()
    return (
        float(ref_loss.detach()),
        float(prod_loss.detach()),
        _parameter_gap_reference_to_production(reference_model.core, production_model.core),
    )


@torch.inference_mode()
def recurrence_mode_gap(core: SharedBasisFixedRoutingCore, seed: int):
    materialized = copy.deepcopy(core); materialized.set_execution_mode("materialized")
    native = copy.deepcopy(core); native.set_execution_mode("gemm_native")
    reference = materialized.initial_working_state(8)
    candidate = native.initial_working_state(8)
    generator = torch.Generator(device="cpu").manual_seed(seed + 80000)
    gaps = []
    for step in range(1, 65):
        context = (torch.randn(8, core.config.slots, core.config.width, generator=generator) * 0.05).to(reference.device)
        route = (step - 1) % core.config.modules
        reference = materialized(reference, context, route_index=route)
        candidate = native(candidate, context, route_index=route)
        if step in DEPTHS:
            gaps.append(_gap(reference, candidate))
    return {
        "allclose": all(bool(row["allclose"]) for row in gaps),
        "max_abs": max(float(row["max_abs"]) for row in gaps),
    }
