from __future__ import annotations
import hashlib, json, statistics
from pathlib import Path
import torch

from fold_lm.v05.reconciliation import receipt_matches_request
from fold_lm.v05_benchmarks import gate_e_c113_stale_eligibility_preflight as c113
from fold_lm.v05_benchmarks import gate_e_c116_authoritative_preflight_priority_refresh as c116
from fold_lm.v05_benchmarks import gate_e_c118_unknown_effect_containment as c118
from fold_lm.v05_benchmarks import gate_e_c119_reconcile_helper as c119h
from fold_lm.v05_benchmarks import gate_e_c119_idempotency_receipt_reconciliation as c119

EXPERIMENT_ID="C120-v5e-receipt-binding-falsification"
SEEDS=(20261401,20261402,20261403)
BINDINGS=("VALID","WRONG_KEY","WRONG_MECHANISM","STALE_EPOCH")
OUTCOMES=c119h.OUTCOMES
EPOCH=7

def _sha(p): return hashlib.file_digest(p.open("rb"),"sha256").hexdigest()
def _stats(v): return {"mean":statistics.mean(v),"median":statistics.median(v),"min":min(v),"max":max(v)}

def _receipt(key,action,binding):
    rk,rm,re=key,action,EPOCH
    if binding=="WRONG_KEY": rk=key+":other"
    elif binding=="WRONG_MECHANISM": rm=1 if action==4 else action+1
    elif binding=="STALE_EPOCH": re=EPOCH-1
    elif binding!="VALID": raise ValueError(binding)
    return rk,rm,re

def _evaluate(router,device):
    control_metrics,_=c119h.evaluate(router,device)
    rows=[]
    for visible,actual in c116._pairs():
        for hidden in (0,1):
            if not any(actual):
                control=c119h.scenario(router,visible,actual,hidden,"STILL_UNKNOWN",device)
                rows.append({"visible":list(visible),"actual":list(actual),"hidden":hidden,"binding":"NONE","outcome":"NONE_AVAILABLE","trace":control["trace"],"receipt_match":True,"commit":0,"retry":0,"fallback":0,"final":"UNRESOLVED","passed":bool(control["passed"])})
                continue
            ok,action,trace=c118._preflight(router,visible,actual,device)
            key=f"c120:{''.join(map(str,actual))}:{action}:{EPOCH}"
            for binding in BINDINGS:
                rk,rm,re=_receipt(key,action,binding)
                matched=receipt_matches_request(request_key=key,mechanism=action,epoch=EPOCH,receipt_key=rk,receipt_mechanism=rm,receipt_epoch=re)
                for outcome in OUTCOMES:
                    if binding=="VALID":
                        control=c119h.scenario(router,visible,actual,hidden,outcome,device)
                        commit=control["commit"]; retry=control["retry"]; fallback=control["fallback"]; final=control["final"]
                        passed=bool(ok and matched and control["passed"])
                        use_trace=control["trace"]
                    else:
                        commit=retry=fallback=0; final="UNRESOLVED_INVALID_RECEIPT"
                        passed=bool(ok and not matched)
                        use_trace=trace
                    rows.append({"visible":list(visible),"actual":list(actual),"hidden":hidden,"binding":binding,"outcome":outcome,"trace":use_trace,"receipt_match":matched,"commit":commit,"retry":retry,"fallback":fallback,"final":final,"passed":passed})
    valid=[r for r in rows if r["binding"]=="VALID"]
    invalid=[r for r in rows if r["binding"] in BINDINGS[1:]]
    none=[r for r in rows if r["binding"]=="NONE"]
    groups={}
    for r in rows:
        key=(tuple(r["visible"]),tuple(r["actual"]),r["binding"],r["outcome"])
        groups.setdefault(key,[]).append(r["trace"])
    hidden=float(all(len(v)==2 and v[0]==v[1] for v in groups.values()))
    m={
        "scenario_pass_rate":sum(r["passed"] for r in rows)/len(rows),
        "c119_control_gate_rate":float(control_metrics["gate_passed"]),
        "valid_binding_accept_rate":sum(r["receipt_match"] for r in valid)/len(valid),
        "invalid_binding_reject_rate":sum(not r["receipt_match"] for r in invalid)/len(invalid),
        "invalid_binding_containment_rate":sum(r["final"]=="UNRESOLVED_INVALID_RECEIPT" for r in invalid)/len(invalid),
        "invalid_binding_zero_commit_rate":sum(r["commit"]==0 for r in invalid)/len(invalid),
        "invalid_binding_zero_retry_rate":sum(r["retry"]==0 for r in invalid)/len(invalid),
        "invalid_binding_zero_fallback_rate":sum(r["fallback"]==0 for r in invalid)/len(invalid),
        "confirmed_none_stop_rate":sum(r["final"]=="UNRESOLVED" for r in none)/len(none),
        "hidden_trace_invariance":hidden,
        "mask_pair_count":len(c116._pairs()),"scenario_count":len(rows),"valid_receipt_case_count":len(valid),"invalid_binding_case_count":len(invalid),
    }
    deciding=[k for k in m if k.endswith("_rate") or k=="hidden_trace_invariance"]
    m["gate_passed"]=all(m[k]==1.0 for k in deciding)
    return m,rows

def run(*,protected_result_path:Path,c119_summary_path:Path,output_dir:Path):
    prior=json.loads(c119_summary_path.read_text(encoding="utf-8"))
    if prior.get("experiment_id")!=c119.EXPERIMENT_ID or prior.get("status")!="PASS" or not prior.get("summary",{}).get("idempotency_receipt_reconciliation_gate_passed"):
        raise RuntimeError("C120 requires accepted C119")
    if not torch.cuda.is_available(): raise RuntimeError("C120 requires CUDA")
    before=_sha(protected_result_path); device=torch.device("cuda"); torch.cuda.set_device(0); torch.set_num_threads(2); torch.set_float32_matmul_precision("highest")
    records=[]
    for seed in SEEDS:
        router,loss=c113._train_router(seed,device); m,rows=_evaluate(router,device); passed=bool(m["gate_passed"])
        records.append({"seed":seed,"final_loss":loss,"metrics":m,"scenarios":rows,"validation_passed":passed})
        print(f"[C120] seed={seed} scenario={m['scenario_pass_rate']:.6f} valid={m['valid_binding_accept_rate']:.6f} invalid={m['invalid_binding_reject_rate']:.6f} pass={passed}",flush=True)
    after=_sha(protected_result_path)
    if before!=after: raise RuntimeError("protected C37 result changed during C120")
    ms=[r["metrics"] for r in records]; all_pass=all(r["validation_passed"] for r in records)
    keys=("scenario_pass_rate","c119_control_gate_rate","valid_binding_accept_rate","invalid_binding_reject_rate","invalid_binding_containment_rate","invalid_binding_zero_commit_rate","invalid_binding_zero_retry_rate","invalid_binding_zero_fallback_rate","confirmed_none_stop_rate","hidden_trace_invariance")
    summary={"fresh_seeds":list(SEEDS),"validation_base":3,"mask_pair_count":ms[0]["mask_pair_count"],"scenario_count":ms[0]["scenario_count"],"valid_receipt_case_count":ms[0]["valid_receipt_case_count"],"invalid_binding_case_count":ms[0]["invalid_binding_case_count"],**{k:_stats([m[k] for m in ms]) for k in keys},"all_validation_passed":all_pass,"receipt_binding_falsification_gate_passed":all_pass}
    report={"experiment_id":EXPERIMENT_ID,"stage":"V5-E-RUNTIME-RECEIPT-BINDING-FALSIFICATION","status":"PASS","summary":summary,"records":records,"C119_summary_sha256":_sha(c119_summary_path),"C37_result_sha256_before":before,"C37_result_sha256_after":after,"production_runtime_modified":True,"gate_e_candidate":False}
    output_dir.mkdir(parents=True,exist_ok=False); (output_dir/"summary.json").write_text(json.dumps(report,indent=2,allow_nan=False),encoding="utf-8"); return report
