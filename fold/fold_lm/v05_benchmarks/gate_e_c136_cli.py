from __future__ import annotations

import json
from pathlib import Path
import time

from fold_lm.v05_benchmarks import gate_e_c135_bounded_retrieval_recovery as c135
from fold_lm.v05_benchmarks import gate_e_c136_learned_query_formation as bench


def _latest_c135(runs: Path) -> Path:
    valid = []
    for p in runs.glob("c135-*"):
        summary = p / "summary.json"
        if not summary.exists():
            continue
        try:
            data = json.loads(summary.read_text(encoding="utf-8"))
        except Exception:
            continue
        if (
            data.get("experiment_id") == c135.EXPERIMENT_ID
            and data.get("status") == "PASS"
            and data.get("summary", {}).get("bounded_retrieval_exact_recovery_gate_passed")
        ):
            valid.append(summary)
    if not valid:
        raise RuntimeError("valid C135 summary not found")
    return max(valid, key=lambda p: p.stat().st_mtime)


def main() -> int:
    runs = Path("runs")
    prior = _latest_c135(runs)
    print(f"C136 prerequisite_summary = {prior}", flush=True)
    print(f"C136 corpus = {bench.CORPUS}", flush=True)
    print(f"C136 query_fixture = {bench.QUERIES}", flush=True)
    print("C136 evaluation = held-out paraphrase per retrieval address", flush=True)
    out = runs / f"c136-v5e-query-formation-{time.time_ns()}"
    report = bench.run(
        protected_result_path=runs / "chatgpt-last-result.json",
        c135_summary_path=prior,
        output_dir=out,
    )
    shown = dict(report)
    shown["records"] = "omitted; see summary.json"
    print("=== C136 RESULT ===")
    print(json.dumps(shown, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
