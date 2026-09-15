from __future__ import annotations

import json
from pathlib import Path
import time

from fold_lm.v05_benchmarks import gate_e_c139_hash_collision_diagnostic as c139
from fold_lm.v05_benchmarks import gate_e_c140_collision_free_multiseed_robustness as bench


def _latest_valid_negative_c139(runs: Path) -> Path:
    valid = []
    for path in runs.glob("c139-*"):
        summary = path / "summary.json"
        if not summary.exists():
            continue
        try:
            data = json.loads(summary.read_text(encoding="utf-8"))
        except Exception:
            continue
        s = data.get("summary", {})
        unseen = s.get("unseen_combination_accuracy", {})
        if (
            data.get("experiment_id") == c139.EXPERIMENT_ID
            and data.get("status") == "FAIL"
            and not bool(s.get("hash_collision_composition_diagnostic_gate_passed"))
            and s.get("known_combination_accuracy", {}).get("min") == 1.0
            and s.get("collision_free_feature_rate", {}).get("min") == 1.0
            and s.get("accepted_c138_valid_negative_rate", {}).get("min") == 1.0
            and unseen.get("max") == 1.0
            and float(unseen.get("min", 1.0)) < 1.0
        ):
            valid.append(summary)
    if not valid:
        raise RuntimeError("mixed-outcome valid-negative C139 summary not found")
    return max(valid, key=lambda p: p.stat().st_mtime)


def main() -> int:
    runs = Path("runs")
    prior = _latest_valid_negative_c139(runs)
    rows = c139.c138._load_fixture()
    vocabulary = c139._training_vocabulary(rows)
    print(f"C140 prerequisite_summary = {prior}", flush=True)
    print("C140 question = is the unchanged collision-free C139 solution robust across fresh initialization seeds?", flush=True)
    print(f"C140 fresh_seed_count = {len(bench.SEEDS)}", flush=True)
    print(f"C140 fresh_seeds = {','.join(str(seed) for seed in bench.SEEDS)}", flush=True)
    print(f"C140 collision_free_feature_dim = {len(vocabulary)}", flush=True)
    print("C140 training = exact C139 schedule / same pooled SharedRetrievalContentHead", flush=True)
    print("C140 evaluation = same 12 combinations / 4 held-out recombinations / expected-class margins", flush=True)
    out = runs / f"c140-v5e-collision-free-multiseed-robustness-{time.time_ns()}"
    report = bench.run(
        protected_result_path=runs / "chatgpt-last-result.json",
        c139_summary_path=prior,
        output_dir=out,
    )
    shown = dict(report)
    shown["records"] = "omitted; see summary.json"
    print("=== C140 RESULT ===")
    print(json.dumps(shown, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
