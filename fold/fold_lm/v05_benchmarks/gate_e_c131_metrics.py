from __future__ import annotations

from fold_lm.v05.post_transition_recovery import APPLIED, NOT_APPLIED, STILL_UNKNOWN
from fold_lm.v05_benchmarks import gate_e_c131_sqlite_case as case


def summarize(rows):
    active = [r for r in rows if r["transition_outcome"] != "NONE_AVAILABLE"]
    resolved = [r for r in active if r["transition_outcome"] in (APPLIED, NOT_APPLIED)]
    unknown = [r for r in active if r["transition_outcome"] == STILL_UNKNOWN]
    none = [r for r in rows if r["transition_outcome"] == "NONE_AVAILABLE"]
    groups = {}
    for row in rows:
        key = (tuple(row["visible"]), tuple(row["actual"]), row["transition_outcome"], row["workers"])
        groups.setdefault(key, []).append(row["trace"])
    hidden = float(all(len(v) == 2 and v[0] == v[1] for v in groups.values()))
    m = {
        "scenario_pass_rate": sum(r["passed"] for r in rows) / len(rows),
        "storage_single_takeover_rate": sum(r["winner_count"] == 1 for r in active) / len(active),
        "storage_higher_token_rate": sum(r["higher_token"] for r in active) / len(active),
        "storage_stale_write_reject_rate": sum(r["stale_accepts"] == 0 for r in active) / len(active),
        "resolved_current_write_accept_rate": sum(r["current_accepts"] == 1 for r in resolved) / len(resolved),
        "resolved_current_state_rate": sum(r["stored_current"] for r in resolved) / len(resolved),
        "unknown_zero_write_rate": sum(r["current_accepts"] == 0 and r["stale_accepts"] == 0 for r in unknown) / len(unknown),
        "unknown_empty_storage_rate": sum(r["stored_none"] for r in unknown) / len(unknown),
        "confirmed_none_stop_rate": sum(r["passed"] for r in none) / len(none),
        "hidden_trace_invariance": hidden,
        "scenario_count": len(rows),
        "storage_fencing_case_count": len(active),
    }
    for workers in case.WORKERS:
        subset = [r for r in active if r["workers"] == workers]
        m[f"workers_{workers}_single_takeover_rate"] = sum(r["winner_count"] == 1 for r in subset) / len(subset)
        m[f"workers_{workers}_stale_reject_rate"] = sum(r["stale_accepts"] == 0 for r in subset) / len(subset)
    return m
