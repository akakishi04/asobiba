from __future__ import annotations

import argparse
import json
from pathlib import Path
import time

from fold_lm.v05_benchmarks import gate_e_c142_color_alignment as bench


def _latest_accepted_c141(runs: Path) -> Path:
    accepted = []
    for path in runs.glob("c141-*/summary.json"):
        try:
            bench._validate_prior(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError, KeyError, TypeError, AttributeError, OverflowError):
            continue
        accepted.append(path)
    if not accepted:
        raise RuntimeError("Accepted full C141 summary.json not found")
    return max(accepted, key=lambda p: (p.stat().st_mtime_ns, str(p)))


def main() -> int:
    parser = argparse.ArgumentParser(description="C142 paired train-only color alignment diagnostic")
    parser.add_argument("--c141-summary", type=Path)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    runs = Path("runs")
    prior = args.c141_summary or _latest_accepted_c141(runs)
    output = args.output_dir or runs / f"c142-v5e-training-only-color-alignment-{time.time_ns()}"
    print(f"C142 prerequisite_summary = {prior}", flush=True)
    print(f"C142 prerequisite_sha256 = {bench._sha(prior)}", flush=True)
    print("C142 question = can train-only color alignment solve raw held-out alias queries across fresh seeds?", flush=True)
    print(f"C142 fresh_seeds = {','.join(map(str, bench.SEEDS))}", flush=True)
    print("C142 paired_heads = BASELINE vs COLOR_AUX; same initial weights per seed", flush=True)
    print("C142 unique_fresh_seeds = 12; trained_heads = 24; total_cases = 288", flush=True)
    print("C142 train_queries = 24; train_candidates = 8; auxiliary_aliases = 12; auxiliary_colors = 4", flush=True)
    print(f"C142 auxiliary_weight = {bench.AUX_WEIGHT}; optimizer_steps = 600 per arm", flush=True)
    print("C142 inference_oracle_used = False; raw_evaluation_queries_unchanged = True", flush=True)
    print(f"C142 output_dir = {output}", flush=True)
    report = bench.run(c141_summary_path=prior, output_dir=output,
                       protected_result_path=runs / "chatgpt-last-result.json",
                       protected_fixture_path=runs / "fixtures" / "v05-c-composition-20260921.pt")
    shown = dict(report)
    shown["records"] = "omitted; see summary.json"
    print("=== C142 RESULT ===", flush=True)
    print(json.dumps(shown, indent=2, allow_nan=False), flush=True)
    return 0  # Scientific FAIL is valid execution; exceptions return nonzero.


if __name__ == "__main__":
    raise SystemExit(main())
