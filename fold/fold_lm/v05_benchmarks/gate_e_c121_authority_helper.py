from __future__ import annotations

from fold_lm.v05.reconciliation import receipt_is_authoritative, receipt_matches_request
from fold_lm.v05_benchmarks import gate_e_c116_authoritative_preflight_priority_refresh as c116
from fold_lm.v05_benchmarks import gate_e_c118_unknown_effect_containment as c118
from fold_lm.v05_benchmarks import gate_e_c119_reconcile_helper as c119h

PROVIDER="provider-a"
EPOCH=8
AUTHORITY=("VERIFIED","OTHER_PROVIDER","NOT_VERIFIED")


def _variant(name):
    if name=="VERIFIED": return PROVIDER,True
    if name=="OTHER_PROVIDER": return "provider-b",True
    if name=="NOT_VERIFIED": return PROVIDER,False
    raise ValueError(name)


def evaluate(router,device):
    rows=[]
    for visible,actual in c116._pairs():
        for hidden in (0,1):
            if not any(actual):
                control=c119h.scenario(router,visible,actual,hidden,"STILL_UNKNOWN",device)
                rows.append({"visible":list(visible),"actual":list(actual),"hidden":hidden,"authority":"NONE","outcome":"NONE_AVAILABLE","trace":control["trace"],"accepted":False,"commit":0,"retry":0,"fallback":0,"final":"UNRESOLVED","passed":bool(control["passed"])})
                continue
            ok,action,trace=c118._preflight(router,visible,actual,device)
            key=f"c121:{''.join(map(str,actual))}:{action}:{EPOCH}"
            binding=receipt_matches_request(request_key=key,mechanism=action,epoch=EPOCH,receipt_key=key,receipt_mechanism=action,receipt_epoch=EPOCH)
            for authority in AUTHORITY:
                receipt_provider,verified=_variant(authority)
                accepted=receipt_is_authoritative(expected_provider=PROVIDER,receipt_provider=receipt_provider,verification_passed=verified,binding_matches=binding)
                for outcome in c119h.OUTCOMES:
                    if authority=="VERIFIED":
                        control=c119h.scenario(router,visible,actual,hidden,outcome,device)
                        commit=control["commit"]; retry=control["retry"]; fallback=control["fallback"]; final=control["final"]; use_trace=control["trace"]
                        passed=bool(ok and binding and accepted and control["passed"])
                    else:
                        commit=retry=fallback=0; final="UNRESOLVED_UNTRUSTED_RECEIPT"; use_trace=trace
                        passed=bool(ok and binding and not accepted)
                    rows.append({"visible":list(visible),"actual":list(actual),"hidden":hidden,"authority":authority,"outcome":outcome,"trace":use_trace,"accepted":accepted,"commit":commit,"retry":retry,"fallback":fallback,"final":final,"passed":passed})
    return rows
