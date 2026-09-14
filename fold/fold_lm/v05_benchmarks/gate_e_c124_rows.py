from __future__ import annotations

from fold_lm.v05.receipt_replay import claim_receipt_once
from fold_lm.v05_benchmarks import gate_e_c116_authoritative_preflight_priority_refresh as c116
from fold_lm.v05_benchmarks import gate_e_c119_reconcile_helper as c119h

COUNTS = (1, 2, 3)


def rows_for(router, device):
    rows = []
    for visible, actual in c116._pairs():
        for hidden in (0, 1):
            if not any(actual):
                control = c119h.scenario(router, visible, actual, hidden, "STILL_UNKNOWN", device)
                rows.append({"visible":list(visible),"actual":list(actual),"hidden":hidden,"outcome":"NONE_AVAILABLE","count":0,"claims":0,"commit":0,"retry":0,"fallback":0,"trace":control["trace"],"final":"UNRESOLVED","passed":bool(control["passed"])})
                continue
            for outcome in c119h.OUTCOMES:
                control = c119h.scenario(router, visible, actual, hidden, outcome, device)
                rid = f"c124:{''.join(map(str, actual))}:{outcome}"
                for count in COUNTS:
                    state = frozenset(); claims = commit = retry = fallback = 0
                    for _ in range(count):
                        claimed, state = claim_receipt_once(receipt_id=rid, processed_receipt_ids=state)
                        if claimed:
                            claims += 1; commit += control["commit"]; retry += control["retry"]; fallback += control["fallback"]
                    passed = bool(control["passed"] and claims==1 and len(state)==1 and commit==control["commit"] and retry==control["retry"] and fallback==control["fallback"])
                    rows.append({"visible":list(visible),"actual":list(actual),"hidden":hidden,"outcome":outcome,"count":count,"claims":claims,"commit":commit,"retry":retry,"fallback":fallback,"trace":control["trace"],"final":control["final"],"passed":passed})
    return rows
