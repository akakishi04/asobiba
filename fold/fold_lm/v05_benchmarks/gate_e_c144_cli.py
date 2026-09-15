from __future__ import annotations

import argparse
import json
from pathlib import Path

from fold_lm.v05_benchmarks import gate_e_c144_factor_mismatch_attribution as bench


def main() -> int:
    parser = argparse.ArgumentParser(description="C144 factor mismatch attribution over C143 results")
    parser.add_argument("--c143-summary", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(f"C144 c143_summary = {args.c143_summary}", flush=True)
    print(f"C144 evaluation_manifest = {args.manifest}", flush=True)
    print("C144 analysis_only = True; model_loading = False; additional_scoring = False", flush=True)
    print("C144 question = which factor-mismatch patterns dominate residual C143 errors?", flush=True)
    report = bench.analyze(args.c143_summary, args.manifest, args.output)
    print("=== C144 RESULT ===", flush=True)
    print(json.dumps(report, indent=2, allow_nan=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
