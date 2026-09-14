from __future__ import annotations
import hashlib,json,statistics
from pathlib import Path
import torch
from fold_lm.v05_benchmarks import gate_e_c113_stale_eligibility_preflight as c113
from fold_lm.v05_benchmarks import gate_e_c121_receipt_authority_falsification as c121
from fold_lm.v05_benchmarks import gate_e_c122_scope_helper as helper

EXPERIMENT_ID="C122-v5e-verdict-scope-falsification"
SEEDS=(20261421,20261422,20261423)

def _sha(p): return hashlib.file_digest(p.open("rb"),"sha256").hexdigest()
def _stats(v): return {"mean":statistics.mean(v),"median":statistics.median(v),"min":min(v),"max":max(v)}

def _metrics(router,device):
    c121m,_=c121._metrics(router,device); rows=helper.evaluate(router,device)
    valid=[r for r in rows if r["scope"]=="VALID"]
    invalid=[r for r in rows if r["scope"] in helper.VARIANTS[1:]]
    none=[r for r in rows if r["scope"]=="NONE"]
    groups={}
    for r in rows:
        groups.setdefault((tuple(r["visible"]),tuple(r["actual"]),r["scope"],r["outcome"]),[]).append(r["trace"])
    hidden=float(all(len(v)==2 and v[0]==v[1] for v in groups.values()))
    m={
      "scenario_pass_rate":sum(r["passed"] for r in rows)/len(rows),
      "c121_control_gate_rate":float(c121m["gate_passed"]),
      "valid_scope_accept_rate":sum(r["match"] for r in valid)/len(valid),
      "invalid_scope_reject_rate":sum(not r["match"] for r in invalid)/len(invalid),
      "invalid_scope_containment_rate":sum(r["final"]=="UNRESOLVED_SCOPE_MISMATCH" for r in invalid)/len(invalid),
      "invalid_scope_zero_commit_rate":sum(r["commit"]==0 for r in invalid)/len(invalid),
      "invalid_scope_zero_retry_rate":sum(r["retry"]==0 for r in invalid)/len(invalid),
      "invalid_scope_zero_fallback_rate":sum(r["fallback"]==0 for r in invalid)/len(invalid),
      "confirmed_none_stop_rate":sum(r["final"]=="UNRESOLVED" for r in none)/len(none),
      "hidden_trace_invariance":hidden,
      "scenario_count":len(rows),"valid_scope_case_count":len(valid),"invalid_scope_case_count":len(invalid),
    }
    deciding=[k for k in m if k.endswith("_rate") or k=="hidden_trace_invariance"]
    m["gate_passed"]=all(m[k]==1.0 for k in deciding)
    return m,rows

def run(*,protected_result_path:Path,c121_summary_path:Path,output_dir:Path):
    prior=json.loads(c121_summary_path.read_text(encoding="utf-8"))
    if prior.get("experiment_id")!=c121.EXPERIMENT_ID or prior.get("status")!="PASS" or not prior.get("summary",{}).get("receipt_authority_falsification_gate_passed"):
        raise RuntimeError("C122 requires accepted C121")
    if not torch.cuda.is_available(): raise RuntimeError("C122 requires CUDA")
    before=_sha(protected_result_path); device=torch.device("cuda"); torch.cuda.set_device(0); torch.set_num_threads(2); torch.set_float32_matmul_precision("highest")
    records=[]
    for seed in SEEDS:
        router,loss=c113._train_router(seed,device); m,rows=_metrics(router,device); passed=bool(m["gate_passed"])
        records.append({"seed":seed,"final_loss":loss,"metrics":m,"scenarios":rows,"validation_passed":passed})
        print(f"[C122] seed={seed} scenario={m['scenario_pass_rate']:.6f} valid={m['valid_scope_accept_rate']:.6f} invalid={m['invalid_scope_reject_rate']:.6f} pass={passed}",flush=True)
    after=_sha(protected_result_path)
    if before!=after: raise RuntimeError("protected C37 result changed during C122")
    ms=[r["metrics"] for r in records]; all_pass=all(r["validation_passed"] for r in records)
    keys=("scenario_pass_rate","c121_control_gate_rate","valid_scope_accept_rate","invalid_scope_reject_rate","invalid_scope_containment_rate","invalid_scope_zero_commit_rate","invalid_scope_zero_retry_rate","invalid_scope_zero_fallback_rate","confirmed_none_stop_rate","hidden_trace_invariance")
    summary={"fresh_seeds":list(SEEDS),"validation_base":3,"scenario_count":ms[0]["scenario_count"],"valid_scope_case_count":ms[0]["valid_scope_case_count"],"invalid_scope_case_count":ms[0]["invalid_scope_case_count"],**{k:_stats([m[k] for m in ms]) for k in keys},"all_validation_passed":all_pass,"verdict_scope_falsification_gate_passed":all_pass}
    report={"experiment_id":EXPERIMENT_ID,"stage":"V5-E-RUNTIME-VERDICT-SCOPE-FALSIFICATION","status":"PASS","summary":summary,"records":records,"C121_summary_sha256":_sha(c121_summary_path),"C37_result_sha256_before":before,"C37_result_sha256_after":after,"production_runtime_modified":True,"gate_e_candidate":False,"limitations":["C122 validates verdict scope metadata, not the external verifier implementation","C122 remains synthetic"]}
    output_dir.mkdir(parents=True,exist_ok=False); (output_dir/"summary.json").write_text(json.dumps(report,indent=2,allow_nan=False),encoding="utf-8"); return report
