from __future__ import annotations

import json
import time
from pathlib import Path

from fold_lm.v05_benchmarks import gate_e_c130_lease_renewal_falsification as c130
from fold_lm.v05_benchmarks import gate_e_c131_sqlite_fencing_falsification as bench


def _latest_c130(runs: Path) -> Path:
    valid = []
    for directory in runs.glob("c130-*"):
        summary = directory / "summary.json"
        if not summary.exists():
            continue
        try:
            data = json.loads(summary.read_text(encoding="utf-8"))
        except Exception:
            continue
        if (
            data.get("experiment_id") == c130.EXPERIMENT_ID
            and data.get("status") == "PASS"
            and data.get("summary", {}).get("lease_renewal_boundary_falsification_gate_passed")
        ):
            valid.append(summary)
    if not valid:
        raise RuntimeError("valid C130 summary not found")
    return max(valid, key=lambda path: path.stat().st_mtime)


def main():
    runs = Path("runs")
    prior = _latest_c130(runs)
    print(f"C131 prerequisite_summary = {prior}", flush=True)
    out = runs / f"c131-v5e-sqlite-fencing-{time.time_ns()}"
    report = bench.run(
        protected_result_path=runs / "chatgpt-last-result.json",
        c130_summary_path=prior,
        output_dir=out,
    )
    shown = dict(report)
    shown["records"] = "omitted; see summary.json"
    print("=== C131 RESULT ===")
    print(json.dumps(shown, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
