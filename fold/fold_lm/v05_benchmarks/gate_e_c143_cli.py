from __future__ import annotations

import argparse
import json
from pathlib import Path
import time

from fold_lm.v05_benchmarks import gate_e_c143_frozen_factorial_audit as bench


def main() -> int:
    parser = argparse.ArgumentParser(description="C143 frozen full-factorial ranking audit")
    parser.add_argument("--c142-summary", required=True, type=Path)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    output = args.output_dir or Path("runs") / f"c143-v5e-frozen-factorial-audit-{time.time_ns()}"
    print(f"C143 prerequisite_summary = {args.c142_summary}", flush=True)
    print("C143 question = do frozen C142 heads generalize across the full in-vocabulary factor product?", flush=True)
    print("C143 fresh_seeds = none; checkpoints = 24; additional_training_steps = 0", flush=True)
    print("C143 candidates = 64; new_combinations = 52; alias_variants_per_combination = 27", flush=True)
    print("C143 cases_per_model = 1728; total_ranking_cases = 41472; original12_replay_cases = 288", flush=True)
    print("C143 ranking_only = True; runtime_path_exercised = False; inference_oracle_used = False", flush=True)
    print(f"C143 output_dir = {output}", flush=True)
    report = bench.run(c142_summary_path=args.c142_summary, output_dir=output,
                       protected_result_path=Path("runs/chatgpt-last-result.json"),
                       protected_fixture_path=Path("runs/fixtures/v05-c-composition-20260921.pt"))
    shown = dict(report)
    shown["records"] = "omitted; see summary.json and evaluation-manifest.json"
    print("=== C143 RESULT ===", flush=True)
    print(json.dumps(shown, indent=2, allow_nan=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
