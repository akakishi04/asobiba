from __future__ import annotations
import hashlib,json,statistics
from pathlib import Path
import torch
from fold_lm.v05_benchmarks import gate_e_c113_stale_eligibility_preflight as c113
from fold_lm.v05_benchmarks import gate_e_c123_commit_context_falsification as c123
from fold_lm.v05_benchmarks import gate_e_c124_rows as rows_mod
from fold_lm.v05_benchmarks import gate_e_c124_metrics as metrics

EXPERIMENT_ID="C124-v5e-receipt-replay-falsification"
SEEDS=(20261441,20261442,20261443)

def _sha(p): return hashlib.file_digest(p.open("rb"),"sha256").hexdigest()
def _stats(v): return {"mean":statistics.mean(v),"median":statistics.median(v),"min":min(v),"max":max(v)}

def _measure(router,device):
    control,_=c123._measure(router,device); rows=rows_mod.rows_for(router,device)
    active=[r for r in rows if r["outcome"]!="NONE_AVAILABLE"]
    first=[r for r in active if r["count"]==1]; repeated=[r for r in active if r["count"]>1]
    applied=[r for r in active if r["outcome"]=="RECONCILED_APPLIED"]
    not_applied=[r for r in active if r["outcome"]=="RECONCILED_NOT_APPLIED"]
    unknown=[r for r in active if r["outcome"]=="STILL_UNKNOWN"]
    none=[r for r in rows if r["outcome"]=="NONE_AVAILABLE"]
    m={
      "scenario_pass_rate":sum(r["passed"] for r in rows)/len(rows),
      "c123_control_gate_rate":float(control["gate_passed"]),
      "first_delivery_single_claim_rate":sum(r["claims"]==1 for r in first)/len(first),
      "repeated_delivery_single_claim_rate":sum(r["claims"]==1 for r in repeated)/len(repeated),
      "applied_total_one_commit_rate":sum(r["commit"]==1 for r in applied)/len(applied),
      "applied_total_zero_retry_rate":sum(r["retry"]==0 for r in applied)/len(applied),
      "not_applied_total_one_retry_rate":sum(r["retry"]==1 for r in not_applied)/len(not_applied),
      "not_applied_total_one_commit_rate":sum(r["commit"]==1 for r in not_applied)/len(not_applied),
      "unknown_total_zero_commit_rate":sum(r["commit"]==0 for r in unknown)/len(unknown),
      "unknown_total_zero_retry_rate":sum(r["retry"]==0 for r in unknown)/len(unknown),
      "unknown_total_zero_fallback_rate":sum(r["fallback"]==0 for r in unknown)/len(unknown),
      "confirmed_none_stop_rate":sum(r["final"]=="UNRESOLVED" for r in none)/len(none),
      "hidden_trace_invariance":metrics.hidden_invariant(rows),
      "scenario_count":len(rows),"first_delivery_case_count":len(first),"repeated_delivery_case_count":len(repeated),
    }
    keys=[k for k in m if k.endswith("_rate") or k=="hidden_trace_invariance"]
    m["gate_passed"]=all(m[k]==1.0 for k in keys)
    return m,rows

def run(*,protected_result_path:Path,c123_summary_path:Path,output_dir:Path):
    prior=json.loads(c123_summary_path.read_text(encoding="utf-8"))
    if prior.get("experiment_id")!=c123.EXPERIMENT_ID or prior.get("status")!="PASS" or not prior.get("summary",{}).get("commit_context_falsification_gate_passed"):
        raise RuntimeError("C124 requires accepted C123")
    if not torch.cuda.is_available(): raise RuntimeError("C124 requires CUDA")
    before=_sha(protected_result_path); device=torch.device("cuda"); torch.cuda.set_device(0); torch.set_num_threads(2); torch.set_float32_matmul_precision("highest")
    records=[]
    for seed in SEEDS:
        router,loss=c113._train_router(seed,device); m,rows=_measure(router,device); passed=bool(m["gate_passed"])
        records.append({"seed":seed,"final_loss":loss,"metrics":m,"scenarios":rows,"validation_passed":passed})
        print(f"[C124] seed={seed} scenario={m['scenario_pass_rate']:.6f} first={m['first_delivery_single_claim_rate']:.6f} repeated={m['repeated_delivery_single_claim_rate']:.6f} pass={passed}",flush=True)
    after=_sha(protected_result_path)
    if before!=after: raise RuntimeError("protected C37 result changed during C124")
    ms=[r["metrics"] for r in records]; all_pass=all(r["validation_passed"] for r in records)
    keys=("scenario_pass_rate","c123_control_gate_rate","first_delivery_single_claim_rate","repeated_delivery_single_claim_rate","applied_total_one_commit_rate","applied_total_zero_retry_rate","not_applied_total_one_retry_rate","not_applied_total_one_commit_rate","unknown_total_zero_commit_rate","unknown_total_zero_retry_rate","unknown_total_zero_fallback_rate","confirmed_none_stop_rate","hidden_trace_invariance")
    summary={"fresh_seeds":list(SEEDS),"validation_base":3,"scenario_count":ms[0]["scenario_count"],"first_delivery_case_count":ms[0]["first_delivery_case_count"],"repeated_delivery_case_count":ms[0]["repeated_delivery_case_count"],**{k:_stats([m[k] for m in ms]) for k in keys},"all_validation_passed":all_pass,"receipt_replay_falsification_gate_passed":all_pass}
    report={"experiment_id":EXPERIMENT_ID,"stage":"V5-E-RUNTIME-RECEIPT-REPLAY-FALSIFICATION","status":"PASS","summary":summary,"records":records,"C123_summary_sha256":_sha(c123_summary_path),"C37_result_sha256_before":before,"C37_result_sha256_after":after,"production_runtime_modified":True,"gate_e_candidate":False,"limitations":["C124 tests sequential duplicate delivery, not concurrent claims or durable crash recovery","C124 remains synthetic"]}
    output_dir.mkdir(parents=True,exist_ok=False); (output_dir/"summary.json").write_text(json.dumps(report,indent=2,allow_nan=False),encoding="utf-8"); return report
