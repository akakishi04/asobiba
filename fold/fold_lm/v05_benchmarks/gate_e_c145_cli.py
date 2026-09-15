from __future__ import annotations

import argparse
import json
from pathlib import Path
import time

from fold_lm.v05_benchmarks import gate_e_c145_material_alignment_intervention as bench


def main() -> int:
    parser = argparse.ArgumentParser(description="C145 paired material-alignment intervention")
    parser.add_argument("--c144-result", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    runs = Path("runs")
    out = args.output_dir or runs / f"c145-v5e-material-alignment-{time.time_ns()}"
    print(f"C145 c144_result = {args.c144_result}", flush=True)
    print("C145 question = does adding material alignment on top of color alignment eliminate material-involved residuals without paired regressions?", flush=True)
    print(f"C145 fresh_seeds = {','.join(map(str, bench.SEEDS))}", flush=True)
    print("C145 arms = COLOR_AUX vs COLOR_MATERIAL_AUX", flush=True)
    print("C145 changed_variable = material-alignment auxiliary loss only", flush=True)
    print("C145 train_steps = 600; color_weight = 1.0; material_weight = 1.0", flush=True)
    print("C145 full_candidates = 64; queries_per_model = 1728; full_cases_per_arm = 20736", flush=True)
    print("C145 ranking_only_full_catalog = True; inference_oracle_used = False", flush=True)
    print(f"C145 output_dir = {out}", flush=True)
    report = bench.run(c144_result_path=args.c144_result, output_dir=out,
                       protected_result_path=runs/"chatgpt-last-result.json",
                       protected_fixture_path=runs/"fixtures"/"v05-c-composition-20260921.pt")
    shown = dict(report)
    shown["records"] = "omitted; see summary.json"
    print("=== C145 RESULT ===", flush=True)
    print(json.dumps(shown, indent=2, allow_nan=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
