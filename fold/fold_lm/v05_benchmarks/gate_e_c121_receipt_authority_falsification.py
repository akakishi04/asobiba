from __future__ import annotations
import hashlib,json,statistics
from pathlib import Path
import torch
from fold_lm.v05_benchmarks import gate_e_c113_stale_eligibility_preflight as c113
from fold_lm.v05_benchmarks import gate_e_c120_receipt_binding_falsification as c120
from fold_lm.v05_benchmarks import gate_e_c121_authority_helper as helper

EXPERIMENT_ID="C121-v5e-receipt-authority-falsification"
SEEDS=(20261411,20261412,20261413)

def _sha(p): return hashlib.file_digest(p.open("rb"),"sha256").hexdigest()
def _stats(v): return {"mean":statistics.mean(v),"median":statistics.median(v),"min":min(v),"max":max(v)}

def _metrics(router,device):
    c120m,_=c120._evaluate(router,device); rows=helper.evaluate(router,device)
    trusted=[r for r in rows if r["authority"]=="VERIFIED"]
    other=[r for r in rows if r["authority"]=="OTHER_PROVIDER"]
    unverified=[r for r in rows if r["authority"]=="NOT_VERIFIED"]
    untrusted=other+unverified; none=[r for r in rows if r["authority"]=="NONE"]
    groups={}
    for r in rows:
        groups.setdefault((tuple(r["visible"]),tuple(r["actual"]),r["authority"],r["outcome"]),[]).append(r["trace"])
    hidden=float(all(len(v)==2 and v[0]==v[1] for v in groups.values()))
    m={
      "scenario_pass_rate":sum(r["passed"] for r in rows)/len(rows),
      "c120_control_gate_rate":float(c120m["gate_passed"]),
      "verified_receipt_accept_rate":sum(r["accepted"] for r in trusted)/len(trusted),
      "other_provider_reject_rate":sum(not r["accepted"] for r in other)/len(other),
      "unverified_reject_rate":sum(not r["accepted"] for r in unverified)/len(unverified),
      "untrusted_containment_rate":sum(r["final"]=="UNRESOLVED_UNTRUSTED_RECEIPT" for r in untrusted)/len(untrusted),
      "untrusted_zero_commit_rate":sum(r["commit"]==0 for r in untrusted)/len(untrusted),
      "untrusted_zero_retry_rate":sum(r["retry"]==0 for r in untrusted)/len(untrusted),
      "untrusted_zero_fallback_rate":sum(r["fallback"]==0 for r in untrusted)/len(untrusted),
      "confirmed_none_stop_rate":sum(r["final"]=="UNRESOLVED" for r in none)/len(none),
      "hidden_trace_invariance":hidden,
      "scenario_count":len(rows),"trusted_case_count":len(trusted),"untrusted_case_count":len(untrusted),
    }
    deciding=[k for k in m if k.endswith("_rate") or k=="hidden_trace_invariance"]
    m["gate_passed"]=all(m[k]==1.0 for k in deciding)
    return m,rows

def run(*,protected_result_path:Path,c120_summary_path:Path,output_dir:Path):
    prior=json.loads(c120_summary_path.read_text(encoding="utf-8"))
    if prior.get("experiment_id")!=c120.EXPERIMENT_ID or prior.get("status")!="PASS" or not prior.get("summary",{}).get("receipt_binding_falsification_gate_passed"):
        raise RuntimeError("C121 requires accepted C120")
    if not torch.cuda.is_available(): raise RuntimeError("C121 requires CUDA")
    before=_sha(protected_result_path); device=torch.device("cuda"); torch.cuda.set_device(0); torch.set_num_threads(2); torch.set_float32_matmul_precision("highest")
    records=[]
    for seed in SEEDS:
        router,loss=c113._train_router(seed,device); m,rows=_metrics(router,device); passed=bool(m["gate_passed"])
        records.append({"seed":seed,"final_loss":loss,"metrics":m,"scenarios":rows,"validation_passed":passed})
        print(f"[C121] seed={seed} scenario={m['scenario_pass_rate']:.6f} verified={m['verified_receipt_accept_rate']:.6f} contained={m['untrusted_containment_rate']:.6f} pass={passed}",flush=True)
    after=_sha(protected_result_path)
    if before!=after: raise RuntimeError("protected C37 result changed during C121")
    ms=[r["metrics"] for r in records]; all_pass=all(r["validation_passed"] for r in records)
    keys=("scenario_pass_rate","c120_control_gate_rate","verified_receipt_accept_rate","other_provider_reject_rate","unverified_reject_rate","untrusted_containment_rate","untrusted_zero_commit_rate","untrusted_zero_retry_rate","untrusted_zero_fallback_rate","confirmed_none_stop_rate","hidden_trace_invariance")
    summary={"fresh_seeds":list(SEEDS),"validation_base":3,"scenario_count":ms[0]["scenario_count"],"trusted_case_count":ms[0]["trusted_case_count"],"untrusted_case_count":ms[0]["untrusted_case_count"],**{k:_stats([m[k] for m in ms]) for k in keys},"all_validation_passed":all_pass,"receipt_authority_falsification_gate_passed":all_pass}
    report={"experiment_id":EXPERIMENT_ID,"stage":"V5-E-RUNTIME-RECEIPT-AUTHORITY-FALSIFICATION","status":"PASS","summary":summary,"records":records,"C120_summary_sha256":_sha(c120_summary_path),"C37_result_sha256_before":before,"C37_result_sha256_after":after,"production_runtime_modified":True,"gate_e_candidate":False,"limitations":["C121 consumes an external verification verdict; it does not validate the verifier itself","C121 remains synthetic"]}
    output_dir.mkdir(parents=True,exist_ok=False); (output_dir/"summary.json").write_text(json.dumps(report,indent=2,allow_nan=False),encoding="utf-8"); return report
