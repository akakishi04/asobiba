from __future__ import annotations

import json
from pathlib import Path
import time

from fold_lm.v05_benchmarks import gate_e_c132_os_process_fencing_falsification as c132
from fold_lm.v05_benchmarks import gate_e_c133_real_retrieval_integration as bench


def _latest_c132(runs: Path) -> Path:
    valid = []
    for directory in runs.glob("c132-*"):
        summary = directory / "summary.json"
        if not summary.exists():
            continue
        try:
            data = json.loads(summary.read_text(encoding="utf-8"))
        except Exception:
            continue
        if (
            data.get("experiment_id") == c132.EXPERIMENT_ID
            and data.get("status") == "PASS"
            and data.get("summary", {}).get("os_process_sqlite_fencing_falsification_gate_passed")
        ):
            valid.append(summary)
    if not valid:
        raise RuntimeError("valid C132 summary not found")
    return max(valid, key=lambda path: path.stat().st_mtime)


def main() -> int:
    runs = Path("runs")
    prior = _latest_c132(runs)
    print(f"C133 prerequisite_summary = {prior}", flush=True)
    print(f"C133 corpus = {bench.CORPUS}", flush=True)
    out = runs / f"c133-v5e-real-retrieval-{time.time_ns()}"
    report = bench.run(
        protected_result_path=runs / "chatgpt-last-result.json",
        c132_summary_path=prior,
        output_dir=out,
    )
    shown = dict(report)
    shown["records"] = "omitted; see summary.json"
    print("=== C133 RESULT ===")
    print(json.dumps(shown, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
