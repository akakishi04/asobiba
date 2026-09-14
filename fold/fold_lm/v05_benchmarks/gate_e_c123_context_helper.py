from __future__ import annotations

from fold_lm.v05.commit_context import commit_context_matches
from fold_lm.v05_benchmarks import gate_e_c116_authoritative_preflight_priority_refresh as c116
from fold_lm.v05_benchmarks import gate_e_c118_unknown_effect_containment as c118
from fold_lm.v05_benchmarks import gate_e_c119_reconcile_helper as c119h

REQ = 10
GEN = 4
CASES = ("SAME", "REQ_NEXT", "GEN_NEXT", "BOTH_NEXT")


def _now(name):
    req, gen = REQ, GEN
    if name in ("REQ_NEXT", "BOTH_NEXT"):
        req += 1
    if name in ("GEN_NEXT", "BOTH_NEXT"):
        gen += 1
    return req, gen


def evaluate(router, device):
    rows = []
    for visible, actual in c116._pairs():
        for hidden in (0, 1):
            if not any(actual):
                control = c119h.scenario(router, visible, actual, hidden, "STILL_UNKNOWN", device)
                rows.append({"visible":list(visible),"actual":list(actual),"hidden":hidden,"case":"NONE","outcome":"NONE_AVAILABLE","trace":control["trace"],"match":True,"commit":0,"retry":0,"fallback":0,"final":"UNRESOLVED","passed":bool(control["passed"])})
                continue
            ok, _, base_trace = c118._preflight(router, visible, actual, device)
            for outcome in c119h.OUTCOMES:
                for name in CASES:
                    req, gen = _now(name)
                    matched = commit_context_matches(verified_request_epoch=REQ,current_request_epoch=req,verified_provider_generation=GEN,current_provider_generation=gen)
                    if name == "SAME":
                        control = c119h.scenario(router, visible, actual, hidden, outcome, device)
                        commit, retry, fallback = control["commit"], control["retry"], control["fallback"]
                        final, trace = control["final"], control["trace"]
                        passed = bool(ok and matched and control["passed"])
                    else:
                        commit = retry = fallback = 0
                        final = "UNRESOLVED_CONTEXT_CHANGED"
                        trace = base_trace
                        passed = bool(ok and not matched)
                    rows.append({"visible":list(visible),"actual":list(actual),"hidden":hidden,"case":name,"outcome":outcome,"trace":trace,"match":matched,"commit":commit,"retry":retry,"fallback":fallback,"final":final,"passed":passed})
    return rows
