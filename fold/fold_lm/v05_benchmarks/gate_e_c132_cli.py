from __future__ import annotations

import json
import time
from pathlib import Path

from fold_lm.v05_benchmarks import gate_e_c131_sqlite_fencing_falsification as c131
from fold_lm.v05_benchmarks import gate_e_c132_os_process_fencing_falsification as bench


def _latest_c131(runs: Path) -> Path:
    valid = []
    for p in runs.glob("c131-*"):
        summary = p / "summary.json"
        if not summary.exists():
            continue
        try:
            data = json.loads(summary.read_text(encoding="utf-8"))
        except Exception:
            continue
        if (
            data.get("experiment_id") == c131.EXPERIMENT_ID
            and data.get("status") == "PASS"
            and data.get("summary", {}).get("sqlite_storage_fencing_falsification_gate_passed")
        ):
            valid.append(summary)
    if not valid:
        raise RuntimeError("valid C131 summary not found")
    return max(valid, key=lambda p: p.stat().st_mtime)


def main() -> int:
    runs = Path("runs")
    prior = _latest_c131(runs)
    print(f"C132 prerequisite_summary = {prior}", flush=True)
    out = runs / f"c132-v5e-os-process-fencing-{time.time_ns()}"
    report = bench.run(
        protected_result_path=runs / "chatgpt-last-result.json",
        c131_summary_path=prior,
        output_dir=out,
    )
    shown = dict(report)
    shown["records"] = "omitted; see summary.json"
    print("=== C132 RESULT ===")
    print(json.dumps(shown, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
