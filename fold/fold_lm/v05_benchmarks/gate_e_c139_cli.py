from __future__ import annotations

import json
from pathlib import Path
import time

from fold_lm.v05_benchmarks import gate_e_c138_compositional_alias_generalization as c138
from fold_lm.v05_benchmarks import gate_e_c139_hash_collision_diagnostic as bench


def _latest_valid_negative_c138(runs: Path) -> Path:
    valid = []
    for path in runs.glob("c138-*"):
        summary = path / "summary.json"
        if not summary.exists():
            continue
        try:
            data = json.loads(summary.read_text(encoding="utf-8"))
        except Exception:
            continue
        s = data.get("summary", {})
        if (
            data.get("experiment_id") == c138.EXPERIMENT_ID
            and data.get("status") == "FAIL"
            and not bool(s.get("compositional_alias_generalization_gate_passed"))
            and s.get("known_combination_accuracy", {}).get("min") == 1.0
            and s.get("zero_lexical_overlap_rate", {}).get("min") == 1.0
            and s.get("accepted_c137_prerequisite_rate", {}).get("min") == 1.0
        ):
            valid.append(summary)
    if not valid:
        raise RuntimeError("valid negative C138 summary not found")
    return max(valid, key=lambda p: p.stat().st_mtime)


def main() -> int:
    runs = Path("runs")
    prior = _latest_valid_negative_c138(runs)
    rows = c138._load_fixture()
    vocabulary = bench._training_vocabulary(rows)
    collisions = bench._hash_collision_buckets(rows)
    print(f"C139 prerequisite_summary = {prior}", flush=True)
    print(f"C139 corpus = {c138.c137.CORPUS}", flush=True)
    print(f"C139 query_fixture = {c138.QUERY_FIXTURE}", flush=True)
    print("C139 question = does C138 failure persist after removing feature-hash collisions?", flush=True)
    print(f"C139 collision_free_feature_dim = {len(vocabulary)}", flush=True)
    print(f"C139 reproduced_c138_collision_buckets = {len(collisions)}", flush=True)
    print("C139 training = same 8 combinations / same pooled SharedRetrievalContentHead", flush=True)
    print("C139 evaluation = same 12 combinations / 4 held-out recombinations", flush=True)
    out = runs / f"c139-v5e-hash-collision-diagnostic-{time.time_ns()}"
    report = bench.run(
        protected_result_path=runs / "chatgpt-last-result.json",
        c138_summary_path=prior,
        output_dir=out,
    )
    shown = dict(report)
    shown["records"] = "omitted; see summary.json"
    print("=== C139 RESULT ===")
    print(json.dumps(shown, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
