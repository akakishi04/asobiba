from __future__ import annotations
import fold_lm.v05_benchmarks.gate_e_acquisition_mechanism_closed_loop as b

EXPERIMENT_ID = b.EXPERIMENT_ID
SEEDS = b.SEEDS
_orig = b._evaluate_scenario


def _guard(router, row, initial_mask, scenario_name, success_index, device):
    r = _orig(router, row, initial_mask, scenario_name, success_index, device)
    rem = list(initial_mask)
    for a in r["attempt_trace"]:
        if a["outcome"] != "SUCCESS" and a["action"] in b.ACTION_TO_BIT:
            rem[b.ACTION_TO_BIT[a["action"]]] = 0
    if r["final_status"] == "UNRESOLVED" and any(rem):
        r["scenario_passed"] = False
    return r


def run(*args, **kwargs):
    prev = b._evaluate_scenario
    b._evaluate_scenario = _guard
    try:
        return b.run(*args, **kwargs)
    finally:
        b._evaluate_scenario = prev


def main(argv=None):
    prev = b.run
    b.run = run
    try:
        return b.main(argv)
    finally:
        b.run = prev


if __name__ == "__main__":
    raise SystemExit(main())
