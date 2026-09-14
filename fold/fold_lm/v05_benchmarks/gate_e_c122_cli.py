from __future__ import annotations
import json,time
from pathlib import Path
from fold_lm.v05_benchmarks import gate_e_c122_verdict_scope_falsification as bench


def main():
    runs=Path("runs")
    prior=max((p for p in runs.glob("c121-v5e-receipt-authority-*") if (p/"summary.json").exists()),key=lambda p:(p/"summary.json").stat().st_mtime)/"summary.json"
    out=runs/f"c122-v5e-verdict-scope-{time.time_ns()}"
    report=bench.run(protected_result_path=runs/"chatgpt-last-result.json",c121_summary_path=prior,output_dir=out)
    shown=dict(report); shown["records"]="omitted; see summary.json"
    print("=== C122 RESULT ==="); print(json.dumps(shown,indent=2,allow_nan=False))
    return 0

if __name__=="__main__": raise SystemExit(main())
