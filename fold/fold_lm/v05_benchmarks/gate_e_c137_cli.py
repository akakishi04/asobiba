from __future__ import annotations

import json
from pathlib import Path
import time

from fold_lm.v05_benchmarks import gate_e_c136_learned_query_formation as c136
from fold_lm.v05_benchmarks import gate_e_c137_content_addressed_corpus_growth as bench


def _latest_c136(runs: Path) -> Path:
    valid = []
    for p in runs.glob("c136-*"):
        summary = p / "summary.json"
        if not summary.exists():
            continue
        try:
            data = json.loads(summary.read_text(encoding="utf-8"))
        except Exception:
            continue
        if (
            data.get("experiment_id") == c136.EXPERIMENT_ID
            and data.get("status") == "PASS"
            and data.get("summary", {}).get("learned_retrieval_query_formation_gate_passed")
        ):
            valid.append(summary)
    if not valid:
        raise RuntimeError("valid C136 summary not found")
    return max(valid, key=lambda path: path.stat().st_mtime)


def main() -> int:
    runs = Path("runs")
    prior = _latest_c136(runs)
    print(f"C137 prerequisite_summary = {prior}", flush=True)
    print(f"C137 corpus = {bench.CORPUS}", flush=True)
    print(f"C137 query_fixture = {bench.QUERY_FIXTURE}", flush=True)
    print("C137 training_catalog = 8 known entities", flush=True)
    print("C137 evaluation_catalog = 12 entities (4 unseen after training)", flush=True)
    out = runs / f"c137-v5e-content-address-growth-{time.time_ns()}"
    report = bench.run(
        protected_result_path=runs / "chatgpt-last-result.json",
        c136_summary_path=prior,
        output_dir=out,
    )
    shown = dict(report)
    shown["records"] = "omitted; see summary.json"
    print("=== C137 RESULT ===")
    print(json.dumps(shown, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
