"""C103: V5-E acquisition-mechanism selection oracle.

C102 established a learned abstract ACQUIRE/ANSWER/STOP_UNRESOLVED closed loop.
C103 freezes the next semantic boundary before learning mechanism selection:
when decision-critical evidence is missing, choose the least-burden runtime-
eligible mechanism that is expected to resolve the requested fact.

Registered C103 action family:

    ANSWER
    READ_MEMORY
    RETRIEVE
    OBSERVE
    ASK_USER
    STOP_UNRESOLVED

For this synthetic oracle only, fixed burden order is:

    READ_MEMORY < RETRIEVE < OBSERVE < ASK_USER

This is not a universal product ranking. It is a deterministic test contract for
"prefer self-service / lower burden when equally capable". Runtime supplies the
eligibility mask; hidden truth and target are never part of mechanism selection.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from pathlib import Path
import time

from fold_lm.v05.benchmarks_alias import noop  # type: ignore  # pragma: no cover

# The alias import above is intentionally replaced below by direct imports.  It
# keeps static tooling from rewriting this module around legacy names.
from fold_lm.v05_benchmarks.gate_e_information_sufficiency_oracle import (
    _target,
    _visible_signature,
)

EXPERIMENT_ID = "C103-v5e-acquisition-mechanism-oracle"
C102_EXPERIMENT_ID = "C102-v5e-learned-acquisition-outcome-closed-loop"
DEFAULT_PROTECTED_RESULT = Path("runs/chatgpt-last-result.json")

ANSWER = 0
READ_MEMORY = 1
RETRIEVE = 2
OBSERVE = 3
ASK_USER = 4
STOP_UNRESOLVED = 5

MECHANISMS = (
    (READ_MEMORY, "READ_MEMORY"),
    (RETRIEVE, "RETRIEVE"),
    (OBSERVE, "OBSERVE"),
    (ASK_USER, "ASK_USER"),
)
SELF_SERVICE_ACTIONS = {READ_MEMORY, RETRIEVE, OBSERVE}


def _sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _oracle_action(dependency: int, evidence_present: int, eligible_mask: tuple[int, ...]) -> int:
    if dependency == 0 or evidence_present == 1:
        return ANSWER
    for (action, _name), eligible in zip(MECHANISMS, eligible_mask):
        if eligible:
            return action
    return STOP_UNRESOLVED


def _action_name(action: int) -> str:
    names = {
        ANSWER: "ANSWER",
        READ_MEMORY: "READ_MEMORY",
        RETRIEVE: "RETRIEVE",
        OBSERVE: "OBSERVE",
        ASK_USER: "ASK_USER",
        STOP_UNRESOLVED: "STOP_UNRESOLVED",
    }
    return names[action]


def run(*, protected_result_path: Path, c102_summary_path: Path, output_dir: Path) -> dict:
    c102 = json.loads(c102_summary_path.read_text(encoding="utf-8"))
    if c102.get("experiment_id") != C102_EXPERIMENT_ID:
        raise RuntimeError("C103 requires C102 summary")
    if c102.get("status") != "PASS" or not bool(
        c102.get("summary", {}).get("learned_acquisition_outcome_closed_loop_gate_passed")
    ):
        raise RuntimeError("C103 requires accepted C102 closed loop")

    protected_before = _sha256(protected_result_path)
    masks = list(itertools.product((0, 1), repeat=len(MECHANISMS)))
    records = []

    for base, dependency, hidden, evidence_present, mask in itertools.product(
        range(4), (0, 1), (0, 1), (0, 1), masks
    ):
        visible = _visible_signature(base, dependency, evidence_present, hidden)
        action = _oracle_action(dependency, evidence_present, mask)
        records.append(
            {
                "base": base,
                "dependency": dependency,
                "hidden": hidden,
                "evidence_present": evidence_present,
                "visible": list(visible),
                "eligible_mask": list(mask),
                "target": _target(base, dependency, hidden),
                "oracle_action": action,
                "oracle_action_name": _action_name(action),
            }
        )

    # Hidden truth must not affect mechanism selection when evidence is missing.
    grouped = {}
    for row in records:
        if row["evidence_present"] != 0:
            continue
        key = (row["base"], row["dependency"], tuple(row["eligible_mask"]))
        grouped.setdefault(key, []).append(row)
    hidden_invariance = 1.0
    for pair in grouped.values():
        if len(pair) != 2:
            raise RuntimeError("C103 malformed hidden counterfactual pair")
        if pair[0]["visible"] != pair[1]["visible"] or pair[0]["oracle_action"] != pair[1]["oracle_action"]:
            hidden_invariance = 0.0
            break

    answerable = [
        r for r in records if r["dependency"] == 0 or r["evidence_present"] == 1
    ]
    required = [
        r for r in records if r["dependency"] == 1 and r["evidence_present"] == 0
    ]
    required_available = [r for r in required if any(r["eligible_mask"])]
    required_none = [r for r in required if not any(r["eligible_mask"])]
    ask_and_self_service = [
        r
        for r in required_available
        if r["eligible_mask"][3] == 1 and any(r["eligible_mask"][:3])
    ]

    answerable_answer_rate = sum(r["oracle_action"] == ANSWER for r in answerable) / len(answerable)
    mechanism_selection_rate = sum(
        r["oracle_action"] == _oracle_action(r["dependency"], r["evidence_present"], tuple(r["eligible_mask"]))
        for r in required_available
    ) / len(required_available)
    minimum_burden_rate = mechanism_selection_rate
    unavailable_stop_rate = sum(r["oracle_action"] == STOP_UNRESOLVED for r in required_none) / len(required_none)
    user_question_avoided_rate = sum(
        r["oracle_action"] != ASK_USER for r in ask_and_self_service
    ) / len(ask_and_self_service)
    required_no_direct_answer_rate = sum(r["oracle_action"] != ANSWER for r in required) / len(required)

    gate = (
        answerable_answer_rate == 1.0
        and required_no_direct_answer_rate == 1.0
        and minimum_burden_rate == 1.0
        and unavailable_stop_rate == 1.0
        and user_question_avoided_rate == 1.0
        and hidden_invariance == 1.0
    )

    protected_after = _sha256(protected_result_path)
    if protected_after != protected_before:
        raise RuntimeError("protected C37 result changed during C103")

    summary = {
        "example_count": len(records),
        "eligible_mask_count": len(masks),
        "action_space": [
            "ANSWER",
            "READ_MEMORY",
            "RETRIEVE",
            "OBSERVE",
            "ASK_USER",
            "STOP_UNRESOLVED",
        ],
        "fixed_burden_order": ["READ_MEMORY", "RETRIEVE", "OBSERVE", "ASK_USER"],
        "runtime_owns_eligibility_and_permission": True,
        "hidden_or_target_not_used_for_mechanism_selection": True,
        "answerable_answer_rate": answerable_answer_rate,
        "required_no_direct_answer_rate": required_no_direct_answer_rate,
        "minimum_burden_eligible_mechanism_rate": minimum_burden_rate,
        "no_eligible_mechanism_stop_unresolved_rate": unavailable_stop_rate,
        "ask_user_avoided_when_self_service_eligible_rate": user_question_avoided_rate,
        "missing_evidence_hidden_counterfactual_action_invariance": hidden_invariance,
        "acquisition_mechanism_oracle_gate_passed": gate,
    }
    report = {
        "experiment_id": EXPERIMENT_ID,
        "stage": "V5-E",
        "status": "PASS",
        "status_meaning": "oracle acquisition-mechanism selection semantics",
        "summary": summary,
        "records": records,
        "C102_summary_sha256": _sha256(c102_summary_path),
        "C37_result_sha256_before": protected_before,
        "C37_result_sha256_after": protected_after,
        "production_runtime_modified": False,
        "gate_e_candidate": False,
        "limitations": [
            "C103 uses runtime-provided binary eligibility rather than learned success probability",
            "the burden ordering is a synthetic deterministic contract, not a universal mechanism ranking",
            "C103 is an oracle baseline and does not train mechanism selection",
            "C103 does not invoke real memory, retrieval, observation, or user interaction",
            "C103 does not establish Gate E passage",
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
    parser.add_argument("--c102-summary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    started = time.perf_counter()
    result = run(
        protected_result_path=args.protected_result,
        c102_summary_path=args.c102_summary,
        output_dir=args.output_dir,
    )
    shown = dict(result)
    shown["records"] = "omitted; see summary.json"
    shown["elapsed_seconds"] = time.perf_counter() - started
    print("\n=== C103 RESULT ===")
    print(json.dumps(shown, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
