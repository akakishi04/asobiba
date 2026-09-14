"""C97: V5-E oracle information-sufficiency baseline.

This first V5-E experiment does not train a controller and does not call memory,
retrieval, tools, or Vision.  It registers the minimal semantic distinction
between:

    ANSWER   -- currently visible evidence is sufficient for the conclusion
    ACQUIRE  -- a missing hidden condition can change the conclusion

The synthetic task includes a negative control where the same hidden condition
is missing but provably irrelevant to the answer.  Counterfactual pairs share
the same visible input while the hidden value changes the target, preventing an
internal-compute policy from legitimately guessing the missing fact.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from pathlib import Path
import time

import torch

EXPERIMENT_ID = "C97-v5e-information-sufficiency-oracle"
DEFAULT_PROTECTED_RESULT = Path("runs/chatgpt-last-result.json")
ANSWER = 0
ACQUIRE = 1


def _sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _target(base: int, dependency: int, hidden: int) -> int:
    base_bit = base & 1
    return base_bit if dependency == 0 else (base_bit ^ hidden)


def _visible_signature(base: int, dependency: int, evidence_present: int, hidden: int):
    # Hidden value is not exposed when evidence is absent.  The observed hidden
    # channel is forced to zero and the mask is the authority boundary.
    observed_hidden = hidden if evidence_present else 0
    return (base, dependency, evidence_present, observed_hidden)


def _oracle_action(dependency: int, evidence_present: int) -> int:
    return ACQUIRE if dependency == 1 and evidence_present == 0 else ANSWER


def _direct_answer(base: int, dependency: int, evidence_present: int, observed_hidden: int):
    if dependency == 1 and evidence_present == 0:
        return None
    return _target(base, dependency, observed_hidden)


def run(*, protected_result_path: Path, c96_summary_path: Path, output_dir: Path) -> dict:
    c96 = json.loads(c96_summary_path.read_text(encoding="utf-8"))
    if c96.get("experiment_id") != "C96-v5d-production-control-lane-runtime-vram":
        raise RuntimeError("C97 requires C96 summary")
    if c96.get("status") != "PASS" or not bool(
        c96.get("summary", {}).get("production_control_lane_gate_passed")
    ):
        raise RuntimeError("C97 requires accepted C96 production gate")

    protected_before = _sha256(protected_result_path)

    rows = []
    for base, dependency, hidden, evidence_present in itertools.product(
        range(4), (0, 1), (0, 1), (0, 1)
    ):
        visible = _visible_signature(base, dependency, evidence_present, hidden)
        target = _target(base, dependency, hidden)
        action = _oracle_action(dependency, evidence_present)
        direct = _direct_answer(*visible)
        final = target if action == ACQUIRE else direct
        rows.append(
            {
                "base": base,
                "dependency": dependency,
                "hidden": hidden,
                "evidence_present": evidence_present,
                "visible": list(visible),
                "target": target,
                "oracle_action": action,
                "direct_answer": direct,
                "final_answer_after_policy": final,
            }
        )

    required = [r for r in rows if r["dependency"] == 1 and r["evidence_present"] == 0]
    answerable = [r for r in rows if r not in required]
    irrelevant_missing = [
        r for r in rows if r["dependency"] == 0 and r["evidence_present"] == 0
    ]

    required_recall = sum(r["oracle_action"] == ACQUIRE for r in required) / len(required)
    unnecessary_acquire = sum(r["oracle_action"] == ACQUIRE for r in answerable) / len(answerable)
    direct_exact = sum(r["direct_answer"] == r["target"] for r in answerable) / len(answerable)
    irrelevant_missing_exact = sum(
        r["direct_answer"] == r["target"] for r in irrelevant_missing
    ) / len(irrelevant_missing)
    final_exact = sum(r["final_answer_after_policy"] == r["target"] for r in rows) / len(rows)
    direct_coverage = len(answerable) / len(rows)

    critical_pairs = 0
    irrelevant_pairs = 0
    grouped = {}
    for row in rows:
        if row["evidence_present"] != 0:
            continue
        key = (row["base"], row["dependency"], row["evidence_present"], 0)
        grouped.setdefault(key, []).append(row)
    for key, pair in grouped.items():
        if len(pair) != 2:
            raise RuntimeError(f"C97 counterfactual group malformed: {key}")
        same_visible = pair[0]["visible"] == pair[1]["visible"]
        if not same_visible:
            raise RuntimeError("C97 hidden value leaked into missing-evidence visible input")
        if pair[0]["dependency"] == 1 and pair[0]["target"] != pair[1]["target"]:
            critical_pairs += 1
        if pair[0]["dependency"] == 0 and pair[0]["target"] == pair[1]["target"]:
            irrelevant_pairs += 1

    ambiguous_direct_answer_attempts = sum(r["direct_answer"] is not None for r in required)

    gate = (
        critical_pairs > 0
        and irrelevant_pairs > 0
        and required_recall == 1.0
        and unnecessary_acquire == 0.0
        and ambiguous_direct_answer_attempts == 0
        and direct_exact == 1.0
        and irrelevant_missing_exact == 1.0
        and final_exact == 1.0
    )

    protected_after = _sha256(protected_result_path)
    if protected_after != protected_before:
        raise RuntimeError("protected C37 result changed during C97")

    summary = {
        "example_count": len(rows),
        "action_space": ["ANSWER", "ACQUIRE"],
        "critical_missing_counterfactual_pair_count": critical_pairs,
        "irrelevant_missing_counterfactual_pair_count": irrelevant_pairs,
        "required_acquisition_recall": required_recall,
        "unnecessary_acquisition_rate": unnecessary_acquire,
        "ambiguous_direct_answer_attempt_count": ambiguous_direct_answer_attempts,
        "direct_answerable_accuracy": direct_exact,
        "irrelevant_missing_direct_accuracy": irrelevant_missing_exact,
        "post_policy_final_accuracy": final_exact,
        "direct_answer_coverage": direct_coverage,
        "information_sufficiency_oracle_gate_passed": gate,
    }
    report = {
        "experiment_id": EXPERIMENT_ID,
        "stage": "V5-E",
        "status": "PASS",
        "status_meaning": "oracle information-sufficiency semantics baseline",
        "summary": summary,
        "records": rows,
        "C96_summary_sha256": _sha256(c96_summary_path),
        "C37_result_sha256_before": protected_before,
        "C37_result_sha256_after": protected_after,
        "production_runtime_modified": False,
        "gate_e_candidate": False,
        "limitations": [
            "C97 is an exhaustive synthetic oracle policy, not a learned acquisition controller",
            "ACQUIRE is abstract and does not yet choose memory/retrieval/observation/user-question mechanisms",
            "C97 has no external tool, memory, or Vision integration",
            "C97 does not establish Gate E passage",
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
    parser.add_argument("--c96-summary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    started = time.perf_counter()
    result = run(
        protected_result_path=args.protected_result,
        c96_summary_path=args.c96_summary,
        output_dir=args.output_dir,
    )
    display = dict(result)
    display["records"] = "omitted; see summary.json"
    display["elapsed_seconds"] = time.perf_counter() - started
    print("\n=== C97 RESULT ===")
    print(json.dumps(display, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
