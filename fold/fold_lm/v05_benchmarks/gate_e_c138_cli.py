from __future__ import annotations

import json
from pathlib import Path
import time

from fold_lm.v05_benchmarks import gate_e_c137_content_addressed_corpus_growth as c137
from fold_lm.v05_benchmarks import gate_e_c138_compositional_alias_generalization as bench


def _latest_c137(runs: Path) -> Path:
    valid = []
    for path in runs.glob("c137-*"):
        summary = path / "summary.json"
        if not summary.exists():
            continue
        try:
            data = json.loads(summary.read_text(encoding="utf-8"))
        except Exception:
            continue
        if (
            data.get("experiment_id") == c137.EXPERIMENT_ID
            and data.get("status") == "PASS"
            and data.get("summary", {}).get("content_addressed_corpus_growth_gate_passed")
        ):
            valid.append(summary)
    if not valid:
        raise RuntimeError("valid C137 summary not found")
    return max(valid, key=lambda p: p.stat().st_mtime)


def main() -> int:
    runs = Path("runs")
    prior = _latest_c137(runs)
    print(f"C138 prerequisite_summary = {prior}", flush=True)
    print(f"C138 corpus = {c137.CORPUS}", flush=True)
    print(f"C138 query_fixture = {bench.QUERY_FIXTURE}", flush=True)
    print("C138 training = 8 known attribute combinations", flush=True)
    print("C138 evaluation = 12 combinations (4 held-out recombinations, zero paired lexical overlap)", flush=True)
    out = runs / f"c138-v5e-compositional-alias-{time.time_ns()}"
    report = bench.run(
        protected_result_path=runs / "chatgpt-last-result.json",
        c137_summary_path=prior,
        output_dir=out,
    )
    shown = dict(report)
    shown["records"] = "omitted; see summary.json"
    print("=== C138 RESULT ===")
    print(json.dumps(shown, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
