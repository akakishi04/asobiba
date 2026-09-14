from __future__ import annotations
import json,time
from pathlib import Path
from fold_lm.v05_benchmarks import gate_e_c129_recovery_fencing_falsification as c129
from fold_lm.v05_benchmarks import gate_e_c130_lease_renewal_falsification as bench


def _latest_c129(runs: Path) -> Path:
    valid = []
    for p in runs.glob("c129-*"):
        summary = p / "summary.json"
        if not summary.exists():
            continue
        try:
            data = json.loads(summary.read_text(encoding="utf-8"))
        except Exception:
            continue
        if (
            data.get("experiment_id") == c129.EXPERIMENT_ID
            and data.get("status") == "PASS"
            and data.get("summary", {}).get("recovery_fencing_falsification_gate_passed")
        ):
            valid.append(summary)
    if not valid:
        raise RuntimeError("valid C129 summary not found")
    return max(valid, key=lambda p: p.stat().st_mtime)


def main():
    runs = Path("runs")
    prior = _latest_c129(runs)
    print(f"C130 prerequisite_summary = {prior}", flush=True)
    out = runs / f"c130-v5e-lease-renewal-{time.time_ns()}"
    report = bench.run(
        protected_result_path=runs / "chatgpt-last-result.json",
        c129_summary_path=prior,
        output_dir=out,
    )
    shown = dict(report)
    shown["records"] = "omitted; see summary.json"
    print("=== C130 RESULT ===")
    print(json.dumps(shown, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
