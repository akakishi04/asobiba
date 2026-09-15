from __future__ import annotations

import argparse
import json
from pathlib import Path
import time

from fold_lm.v05_benchmarks import gate_e_c141_color_alias_localization as bench


def _latest_accepted_c140(runs: Path) -> Path:
    valid: list[Path] = []
    for path in runs.glob("c140-*/summary.json"):
        try:
            bench._validate_prior(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError, KeyError, TypeError):
            continue
        valid.append(path)
    if not valid:
        raise RuntimeError("Accepted C140 full summary.json not found")
    return max(valid, key=lambda path: (path.stat().st_mtime_ns, str(path)))


def main() -> int:
    parser = argparse.ArgumentParser(description="C141 frozen-head paired color alias diagnostic")
    parser.add_argument("--c140-summary", type=Path)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    runs = Path("runs")
    prior = args.c140_summary or _latest_accepted_c140(runs)
    out = args.output_dir or runs / f"c141-v5e-color-alias-localization-{time.time_ns()}"
    print(f"C141 prerequisite_summary = {prior}", flush=True)
    print(f"C141 prerequisite_sha256 = {bench._sha(prior)}", flush=True)
    print("C141 question = does evaluation-only canonical color rescue all C140 errors without new errors?", flush=True)
    print("C141 seed_role = C140_REPLAY_NOT_FRESH", flush=True)
    print(f"C141 replay_seeds = {','.join(map(str, bench.SEEDS))}", flush=True)
    print("C141 baseline_cases = 144; intervention_cases = 144; total_cases = 288", flush=True)
    print("C141 changed = query color alias only; same frozen weights and 12 persisted candidates", flush=True)
    print("C141 oracle_diagnostic = True; canonical color introduces intentional lexical overlap", flush=True)
    print(f"C141 output_dir = {out}", flush=True)
    report = bench.run(
        protected_result_path=runs / "chatgpt-last-result.json",
        protected_fixture_path=runs / "fixtures" / "v05-c-composition-20260921.pt",
        c140_summary_path=prior,
        output_dir=out,
    )
    shown = dict(report)
    shown["records"] = "omitted; see summary.json"
    print("=== C141 RESULT ===", flush=True)
    print(json.dumps(shown, indent=2, allow_nan=False), flush=True)
    return 0  # A valid scientific FAIL is not a failed execution.


if __name__ == "__main__":
    raise SystemExit(main())
