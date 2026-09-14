from __future__ import annotations


def summarize(rows: list[dict]) -> dict:
    resolved = [r for r in rows if r["mode"] == "RESOLVED"]
    unknown = [r for r in rows if r["mode"] == "UNKNOWN"]
    metrics = {
        "process_case_pass_rate": sum(r["passed"] for r in rows) / len(rows),
        "process_identity_rate": sum(r["takeover_process_identity"] and r["write_process_identity"] for r in rows) / len(rows),
        "process_single_takeover_rate": sum(r["winner_count"] == 1 for r in rows) / len(rows),
        "process_higher_token_rate": sum(r["higher_token"] for r in rows) / len(rows),
        "process_stale_write_reject_rate": sum(r["stale_accepts"] == 0 for r in rows) / len(rows),
        "resolved_current_write_accept_rate": sum(r["current_accepts"] == 1 for r in resolved) / len(resolved),
        "resolved_current_state_rate": sum(r["stored_current"] for r in resolved) / len(resolved),
        "unknown_zero_write_rate": sum(r["current_accepts"] == 0 and r["stale_accepts"] == 0 for r in unknown) / len(unknown),
        "unknown_empty_storage_rate": sum(r["stored_none"] for r in unknown) / len(unknown),
        "process_case_count": len(rows),
    }
    worker_counts = sorted({int(r["workers"]) for r in rows})
    for workers in worker_counts:
        subset = [r for r in rows if r["workers"] == workers]
        metrics[f"workers_{workers}_process_pass_rate"] = sum(r["passed"] for r in subset) / len(subset)
        metrics[f"workers_{workers}_single_takeover_rate"] = sum(r["winner_count"] == 1 for r in subset) / len(subset)
        metrics[f"workers_{workers}_stale_reject_rate"] = sum(r["stale_accepts"] == 0 for r in subset) / len(subset)
    return metrics
