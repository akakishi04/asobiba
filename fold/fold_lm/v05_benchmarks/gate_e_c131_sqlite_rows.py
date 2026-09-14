from __future__ import annotations

from pathlib import Path

from fold_lm.v05.post_transition_recovery import APPLIED, NOT_APPLIED, STILL_UNKNOWN
from fold_lm.v05.sqlite_recovery_fencing import SqliteRecoveryFencingStore
from fold_lm.v05_benchmarks import gate_e_c116_authoritative_preflight_priority_refresh as c116
from fold_lm.v05_benchmarks import gate_e_c118_unknown_effect_containment as c118
from fold_lm.v05_benchmarks import gate_e_c131_sqlite_case as case

OUTCOMES = (APPLIED, NOT_APPLIED, STILL_UNKNOWN)


def rows_for(router, device, db_path: Path):
    store = SqliteRecoveryFencingStore(db_path)
    rows = []
    for visible, actual in c116._pairs():
        for hidden in (0, 1):
            ok, action, trace = c118._preflight(router, visible, actual, device)
            if not any(actual):
                rows.append({
                    "visible": list(visible), "actual": list(actual), "hidden": hidden,
                    "transition_outcome": "NONE_AVAILABLE", "workers": 0, "trace": trace,
                    "winner_count": 0, "higher_token": True, "current_accepts": 0,
                    "stale_accepts": 0, "stored_current": False, "stored_none": True,
                    "passed": bool(ok and action == 5),
                })
                continue
            for outcome in OUTCOMES:
                for workers in case.WORKERS:
                    rid = (
                        f"c131:{''.join(map(str, visible))}:{''.join(map(str, actual))}:"
                        f"{hidden}:{outcome}:{workers}"
                    )
                    result = case.evaluate_case(
                        store,
                        rid,
                        workers,
                        write_current=outcome != STILL_UNKNOWN,
                    )
                    if outcome == STILL_UNKNOWN:
                        storage_ok = (
                            result["current_accepts"] == 0
                            and result["stale_accepts"] == 0
                            and result["stored_none"]
                        )
                    else:
                        storage_ok = (
                            result["current_accepts"] == 1
                            and result["stale_accepts"] == 0
                            and result["stored_current"]
                        )
                    rows.append({
                        "visible": list(visible), "actual": list(actual), "hidden": hidden,
                        "transition_outcome": outcome, "workers": workers, "trace": trace,
                        **result,
                        "passed": bool(ok and result["winner_count"] == 1 and result["higher_token"] and storage_ok),
                    })
    return rows
