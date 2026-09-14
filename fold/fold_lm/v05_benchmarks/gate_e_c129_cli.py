from __future__ import annotations
import json,time
from pathlib import Path
from fold_lm.v05_benchmarks import gate_e_c128_concurrent_recovery_ownership_falsification as c128
from fold_lm.v05_benchmarks import gate_e_c129_recovery_fencing_falsification as bench


def _latest_c128(runs: Path) -> Path:
    valid = []
    for p in runs.glob("c128-*"):
        summary = p / "summary.json"
        if not summary.exists():
            continue
        try:
            data = json.loads(summary.read_text(encoding="utf-8"))
        except Exception:
            continue
        if (
            data.get("experiment_id") == c128.EXPERIMENT_ID
            and data.get("status") == "PASS"
            and data.get("summary", {}).get("concurrent_recovery_ownership_falsification_gate_passed")
        ):
            valid.append(summary)
    if not valid:
        raise RuntimeError("valid C128 summary not found")
    return max(valid, key=lambda p: p.stat().st_mtime)


def main():
    runs=Path("runs")
    prior=_latest_c128(runs)
    print(f"C129 prerequisite_summary = {prior}")
    out=runs/f"c129-v5e-recovery-fencing-{time.time_ns()}"
    report=bench.run(protected_result_path=runs/"chatgpt-last-result.json",c128_summary_path=prior,output_dir=out)
    shown=dict(report); shown["records"]="omitted; see summary.json"
    print("=== C129 RESULT ==="); print(json.dumps(shown,indent=2,allow_nan=False))
    return 0

if __name__=="__main__": raise SystemExit(main())
