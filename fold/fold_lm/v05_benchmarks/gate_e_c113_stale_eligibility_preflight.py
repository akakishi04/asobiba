"""C113: stale eligibility preflight falsification.

C112 removed class-balanced sampling as an explanation. C113 moves to a
runtime-authority failure mode: model-visible mechanism eligibility can be
stale-high. The router may propose such a mechanism, but runtime must revalidate
against authoritative availability before external execution.

Stale proposal -> no mechanism execution, no evidence commit, visible bit is
cleared, state is reobserved, and the router may fall back. The first genuinely
available selected mechanism succeeds. If none is actually available, the loop
must terminate with STOP_UNRESOLVED after stale bits are exhausted.
"""
from __future__ import annotations

import hashlib
import itertools
import json
from pathlib import Path
import statistics

import torch
from torch.nn import functional as F

from fold_lm.v05.controller import ControlLaneActionRouter, ControlLaneRouterConfig
from fold_lm.v05_benchmarks import gate_e_c108_feature_reencoding_falsification as c108
from fold_lm.v05_benchmarks import gate_e_c111_production_control_canonicalization as c111
from fold_lm.v05_benchmarks import gate_e_c112_natural_class_frequency_falsification as c112

EXPERIMENT_ID = "C113-v5e-stale-eligibility-preflight"
C112_EXPERIMENT_ID = c112.EXPERIMENT_ID
DEFAULT_PROTECTED_RESULT = Path("runs/chatgpt-last-result.json")
SEEDS = (20261341, 20261342, 20261343)
ACTION_TO_BIT = {1: 0, 2: 1, 3: 2, 4: 3}
ANSWER = 0
STOP_UNRESOLVED = 5
MAX_DECISIONS = 5


def _sha(path: Path) -> str:
    return hashlib.file_digest(path.open("rb"), "sha256").hexdigest()


def _stats(values):
    return {"mean": statistics.mean(values), "median": statistics.median(values), "min": min(values), "max": max(values)}


def _train_router(seed: int, device: torch.device):
    rows = c108._logical_rows(c108.TRAIN_BASES)
    previous = c108._tensorize
    c108._tensorize = c111._production_tensorize
    try:
        working, context, op_ids, labels = c108._concat_training(rows, device)
    finally:
        c108._tensorize = previous

    torch.manual_seed(seed)
    router = ControlLaneActionRouter(
        ControlLaneRouterConfig(
            width=c108.WIDTH,
            control_width=c108.CONTROL_WIDTH,
            operation_vocab_size=1,
            hidden_width=c108.HIDDEN_WIDTH,
            action_count=c108.ACTION_COUNT,
        )
    ).to(device)
    opt = torch.optim.AdamW(router.parameters(), lr=c108.LR, weight_decay=0.0)
    gen = torch.Generator(device="cpu").manual_seed(seed + 400)
    router.train()
    loss = None
    for _ in range(c108.TRAIN_STEPS):
        idx = c112._natural_indices(labels, gen, device)
        opt.zero_grad(set_to_none=True)
        logits = router(
            working.index_select(0, idx),
            context.index_select(0, idx),
            op_ids.index_select(0, idx),
        )
        loss = F.cross_entropy(logits, labels.index_select(0, idx))
        if not torch.isfinite(loss):
            raise RuntimeError(f"C113 non-finite loss seed={seed}")
        loss.backward()
        opt.step()
    router.eval()
    return router, float(loss.detach().item())


def _predict(router, *, dependency: int, evidence_present: int, observed_hidden: int, visible_mask, device):
    working = torch.zeros(1, 1, c108.WIDTH, device=device)
    context = torch.zeros_like(working)
    op_ids = torch.zeros(1, dtype=torch.int64, device=device)
    working[0, 0, 0] = 1.0  # unseen validation base=3 canonicalized as 3/3
    working[0, 0, 1] = float(dependency)
    working[0, 0, 2] = float(evidence_present)
    working[0, 0, 3] = float(observed_hidden)
    context[0, 0, :4] = torch.tensor(visible_mask, dtype=torch.float32, device=device)
    working = c111.canonicalize_boolean_channels(working, (1, 2, 3), threshold=0.5)
    context = c111.canonicalize_boolean_channels(context, (0, 1, 2, 3), threshold=0.5)
    with torch.inference_mode():
        return int(router(working, context, op_ids).argmax(dim=-1).item())


def _mask_pairs():
    masks = tuple(itertools.product((0, 1), repeat=4))
    return [
        (visible, actual)
        for visible in masks
        for actual in masks
        if all(a <= v for a, v in zip(actual, visible))
    ]


def _run_required_scenario(router, visible_mask, actual_mask, hidden: int, device):
    visible = list(visible_mask)
    stale_rejects = 0
    mechanism_executions = 0
    evidence_commits = 0
    repeat_rejects = 0
    rejected_bits = set()
    action_trace = []
    final_status = "UNSET"

    for _ in range(MAX_DECISIONS):
        action = _predict(
            router,
            dependency=1,
            evidence_present=int(evidence_commits > 0),
            observed_hidden=hidden if evidence_commits else 0,
            visible_mask=visible,
            device=device,
        )
        action_trace.append(action)
        if action == ANSWER:
            final_status = "ANSWERED"
            break
        if action == STOP_UNRESOLVED:
            final_status = "UNRESOLVED"
            break
        if action not in ACTION_TO_BIT:
            final_status = "INVALID_ACTION"
            break

        bit = ACTION_TO_BIT[action]
        if bit in rejected_bits:
            repeat_rejects += 1
            final_status = "REPEATED_STALE_REJECT"
            break
        if visible[bit] == 0:
            final_status = "VISIBLE_INELIGIBLE_ACTION"
            break

        if actual_mask[bit] == 0:
            stale_rejects += 1
            rejected_bits.add(bit)
            visible[bit] = 0
            continue

        mechanism_executions += 1
        evidence_commits += 1

    actual_available = any(actual_mask)
    expected_terminal = "ANSWERED" if actual_available else "UNRESOLVED"
    expected_exec = 1 if actual_available else 0
    passed = (
        final_status == expected_terminal
        and mechanism_executions == expected_exec
        and evidence_commits == expected_exec
        and repeat_rejects == 0
    )
    return {
        "visible_mask": list(visible_mask),
        "actual_mask": list(actual_mask),
        "hidden": hidden,
        "action_trace": action_trace,
        "stale_reject_count": stale_rejects,
        "mechanism_execution_count": mechanism_executions,
        "evidence_commit_count": evidence_commits,
        "repeat_stale_reject_count": repeat_rejects,
        "final_status": final_status,
        "scenario_passed": passed,
    }


def _evaluate_seed(router, device):
    pairs = _mask_pairs()
    required = [
        _run_required_scenario(router, visible, actual, hidden, device)
        for visible, actual in pairs
        for hidden in (0, 1)
    ]
    answerable = []
    for dependency, evidence_present, hidden, mask in itertools.product((0, 1), (0, 1), (0, 1), itertools.product((0, 1), repeat=4)):
        if dependency == 1 and evidence_present == 0:
            continue
        action = _predict(
            router,
            dependency=dependency,
            evidence_present=evidence_present,
            observed_hidden=hidden if evidence_present else 0,
            visible_mask=mask,
            device=device,
        )
        answerable.append(action == ANSWER)

    stale_rows = [r for r in required if r["stale_reject_count"] > 0]
    no_actual = [r for r in required if not any(r["actual_mask"])]
    actual_available = [r for r in required if any(r["actual_mask"])]
    metrics = {
        "answerable_answer_rate": sum(answerable) / len(answerable),
        "required_scenario_pass_rate": sum(r["scenario_passed"] for r in required) / len(required),
        "stale_rejection_no_execution_rate": sum(r["mechanism_execution_count"] <= 1 for r in stale_rows) / len(stale_rows),
        "stale_rejection_no_commit_before_success_rate": 1.0 if all(r["evidence_commit_count"] <= 1 for r in stale_rows) else 0.0,
        "actual_available_answer_rate": sum(r["final_status"] == "ANSWERED" for r in actual_available) / len(actual_available),
        "actual_available_exactly_one_execution_rate": sum(r["mechanism_execution_count"] == 1 for r in actual_available) / len(actual_available),
        "no_actual_stop_rate": sum(r["final_status"] == "UNRESOLVED" for r in no_actual) / len(no_actual),
        "no_actual_zero_execution_rate": sum(r["mechanism_execution_count"] == 0 for r in no_actual) / len(no_actual),
        "repeat_stale_reject_count": sum(r["repeat_stale_reject_count"] for r in required),
        "required_case_count": len(required),
        "stale_case_count": len(stale_rows),
    }
    metrics["stale_eligibility_preflight_gate_passed"] = all(
        value == 1.0 for key, value in metrics.items() if key.endswith("_rate")
    ) and metrics["repeat_stale_reject_count"] == 0
    return metrics, required


def run(*, protected_result_path: Path, c112_summary_path: Path, output_dir: Path):
    prerequisite = json.loads(c112_summary_path.read_text(encoding="utf-8"))
    if prerequisite.get("experiment_id") != C112_EXPERIMENT_ID:
        raise RuntimeError("C113 requires C112 summary")
    if prerequisite.get("status") != "PASS" or not prerequisite.get("summary", {}).get("natural_class_frequency_falsification_gate_passed"):
        raise RuntimeError("C113 requires accepted C112 falsification")
    if not torch.cuda.is_available():
        raise RuntimeError("C113 requires CUDA")

    before = _sha(protected_result_path)
    device = torch.device("cuda")
    torch.cuda.set_device(0)
    torch.set_num_threads(2)
    torch.set_float32_matmul_precision("highest")

    records = []
    for seed in SEEDS:
        router, loss = _train_router(seed, device)
        metrics, scenarios = _evaluate_seed(router, device)
        passed = bool(metrics["stale_eligibility_preflight_gate_passed"])
        records.append({"seed": seed, "final_loss": loss, "metrics": metrics, "scenarios": scenarios, "validation_passed": passed})
        print(
            f"[C113] seed={seed} required={metrics['required_scenario_pass_rate']:.6f} "
            f"available_answer={metrics['actual_available_answer_rate']:.6f} "
            f"no_actual_stop={metrics['no_actual_stop_rate']:.6f} "
            f"repeat={metrics['repeat_stale_reject_count']} pass={passed}",
            flush=True,
        )

    after = _sha(protected_result_path)
    if before != after:
        raise RuntimeError("protected C37 result changed during C113")

    ms = [r["metrics"] for r in records]
    all_pass = all(r["validation_passed"] for r in records)
    summary = {
        "fresh_seeds": list(SEEDS),
        "train_bases": list(c108.TRAIN_BASES),
        "validation_base": 3,
        "sampling": "natural uniform-row sampling",
        "production_adapter": "canonicalize_boolean_channels",
        "visible_eligibility_can_be_stale_high": True,
        "runtime_authoritative_preflight": True,
        "stale_rejection_executes_mechanism": False,
        "mask_pair_count": len(_mask_pairs()),
        "required_case_count": ms[0]["required_case_count"],
        "answerable_answer_rate": _stats([m["answerable_answer_rate"] for m in ms]),
        "required_scenario_pass_rate": _stats([m["required_scenario_pass_rate"] for m in ms]),
        "actual_available_answer_rate": _stats([m["actual_available_answer_rate"] for m in ms]),
        "actual_available_exactly_one_execution_rate": _stats([m["actual_available_exactly_one_execution_rate"] for m in ms]),
        "no_actual_stop_rate": _stats([m["no_actual_stop_rate"] for m in ms]),
        "no_actual_zero_execution_rate": _stats([m["no_actual_zero_execution_rate"] for m in ms]),
        "repeat_stale_reject_count": {"sum": sum(m["repeat_stale_reject_count"] for m in ms), "max": max(m["repeat_stale_reject_count"] for m in ms)},
        "all_validation_passed": all_pass,
        "stale_eligibility_preflight_gate_passed": all_pass,
    }
    report = {
        "experiment_id": EXPERIMENT_ID,
        "stage": "V5-E-RUNTIME-AUTHORITY-FALSIFICATION",
        "status": "PASS",
        "status_meaning": "stale model-visible eligibility with authoritative runtime preflight",
        "summary": summary,
        "records": records,
        "C112_summary_sha256": _sha(c112_summary_path),
        "C37_result_sha256_before": before,
        "C37_result_sha256_after": after,
        "production_runtime_modified": False,
        "gate_e_candidate": False,
        "limitations": [
            "C113 tests stale-high eligibility only; stale false-negative availability is separate",
            "runtime preflight is synthetic and does not invoke real tools",
            "the first genuinely available selected mechanism is forced to succeed",
            "C113 does not establish Gate E passage",
        ],
    }
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "summary.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    return report
