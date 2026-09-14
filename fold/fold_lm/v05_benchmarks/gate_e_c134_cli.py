from __future__ import annotations

import json
from pathlib import Path
import time

from fold_lm.v05_benchmarks import gate_e_c133_real_retrieval_integration as c133
from fold_lm.v05_benchmarks import gate_e_c134_retrieval_miss_semantics as bench


def _latest_c133(runs: Path) -> Path:
    valid = []
    for p in runs.glob("c133-*"):
        summary = p / "summary.json"
        if not summary.exists():
            continue
        try:
            data = json.loads(summary.read_text(encoding="utf-8"))
        except Exception:
            continue
        if (
            data.get("experiment_id") == c133.EXPERIMENT_ID
            and data.get("status") == "PASS"
            and data.get("summary", {}).get("real_retrieval_vertical_integration_gate_passed")
        ):
            valid.append(summary)
    if not valid:
        raise RuntimeError("valid C133 summary not found")
    return max(valid, key=lambda p: p.stat().st_mtime)


def main() -> int:
    runs = Path("runs")
    prior = _latest_c133(runs)
    print(f"C134 prerequisite_summary = {prior}", flush=True)
    print(f"C134 corpus = {c133.CORPUS}", flush=True)
    out = runs / f"c134-v5e-retrieval-miss-{time.time_ns()}"
    report = bench.run(
        protected_result_path=runs / "chatgpt-last-result.json",
        c133_summary_path=prior,
        output_dir=out,
    )
    shown = dict(report)
    shown["records"] = "omitted; see summary.json"
    print("=== C134 RESULT ===")
    print(json.dumps(shown, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
