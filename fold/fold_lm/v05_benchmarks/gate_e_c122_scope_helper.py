from __future__ import annotations

from fold_lm.v05.receipt_scope import receipt_scope_matches
from fold_lm.v05_benchmarks import gate_e_c116_authoritative_preflight_priority_refresh as c116
from fold_lm.v05_benchmarks import gate_e_c118_unknown_effect_containment as c118
from fold_lm.v05_benchmarks import gate_e_c119_reconcile_helper as c119h

SRC="source-a"; EPOCH=9; VARIANTS=("VALID","OTHER_ID","OTHER_SOURCE","OLD_EPOCH")

def _variant(item_id,name):
    sid=item_id; src=SRC; ep=EPOCH
    if name=="OTHER_ID": sid=item_id+":x"
    elif name=="OTHER_SOURCE": src="source-b"
    elif name=="OLD_EPOCH": ep=EPOCH-1
    elif name!="VALID": raise ValueError(name)
    return sid,src,ep

def evaluate(router,device):
    rows=[]
    for visible,actual in c116._pairs():
        for hidden in (0,1):
            if not any(actual):
                control=c119h.scenario(router,visible,actual,hidden,"STILL_UNKNOWN",device)
                rows.append({"visible":list(visible),"actual":list(actual),"hidden":hidden,"scope":"NONE","outcome":"NONE_AVAILABLE","trace":control["trace"],"match":True,"commit":0,"retry":0,"fallback":0,"final":"UNRESOLVED","passed":bool(control["passed"])})
                continue
            ok,action,base_trace=c118._preflight(router,visible,actual,device)
            for outcome in c119h.OUTCOMES:
                item_id=f"c122:{''.join(map(str,actual))}:{action}:{outcome}"
                for name in VARIANTS:
                    sid,src,ep=_variant(item_id,name)
                    matched=receipt_scope_matches(receipt_id=item_id,scope_receipt_id=sid,expected_source=SRC,scope_source=src,current_epoch=EPOCH,scope_epoch=ep)
                    if name=="VALID":
                        control=c119h.scenario(router,visible,actual,hidden,outcome,device)
                        commit=control["commit"]; retry=control["retry"]; fallback=control["fallback"]; final=control["final"]; trace=control["trace"]
                        passed=bool(ok and matched and control["passed"])
                    else:
                        commit=retry=fallback=0; final="UNRESOLVED_SCOPE_MISMATCH"; trace=base_trace; passed=bool(ok and not matched)
                    rows.append({"visible":list(visible),"actual":list(actual),"hidden":hidden,"scope":name,"outcome":outcome,"trace":trace,"match":matched,"commit":commit,"retry":retry,"fallback":fallback,"final":final,"passed":passed})
    return rows
