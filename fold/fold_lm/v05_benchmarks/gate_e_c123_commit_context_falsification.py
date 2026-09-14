from __future__ import annotations
import hashlib,json,statistics
from pathlib import Path
import torch
from fold_lm.v05_benchmarks import gate_e_c113_stale_eligibility_preflight as c113
from fold_lm.v05_benchmarks import gate_e_c122_verdict_scope_falsification as c122
from fold_lm.v05_benchmarks import gate_e_c123_context_helper as helper
from fold_lm.v05_benchmarks import gate_e_c123_metrics as metrics

EXPERIMENT_ID="C123-v5e-commit-context-falsification"
SEEDS=(20261431,20261432,20261433)

def _sha(p): return hashlib.file_digest(p.open("rb"),"sha256").hexdigest()
def _stats(v): return {"mean":statistics.mean(v),"median":statistics.median(v),"min":min(v),"max":max(v)}

def _measure(router,device):
    control,_=c122._metrics(router,device); rows=helper.evaluate(router,device)
    same=[r for r in rows if r["case"]=="SAME"]
    changed=[r for r in rows if r["case"] in helper.CASES[1:]]
    none=[r for r in rows if r["case"]=="NONE"]
    m={
      "scenario_pass_rate":sum(r["passed"] for r in rows)/len(rows),
      "c122_control_gate_rate":float(control["gate_passed"]),
      "unchanged_context_accept_rate":sum(r["match"] for r in same)/len(same),
      "changed_context_reject_rate":sum(not r["match"] for r in changed)/len(changed),
      "changed_context_zero_commit_rate":sum(r["commit"]==0 for r in changed)/len(changed),
      "changed_context_zero_retry_rate":sum(r["retry"]==0 for r in changed)/len(changed),
      "changed_context_zero_fallback_rate":sum(r["fallback"]==0 for r in changed)/len(changed),
      "confirmed_none_stop_rate":sum(r["final"]=="UNRESOLVED" for r in none)/len(none),
      "hidden_trace_invariance":metrics.hidden_invariant(rows),
      "scenario_count":len(rows),"unchanged_context_case_count":len(same),"changed_context_case_count":len(changed),
    }
    keys=[k for k in m if k.endswith("_rate") or k=="hidden_trace_invariance"]
    m["gate_passed"]=all(m[k]==1.0 for k in keys)
    return m,rows

def run(*,protected_result_path:Path,c122_summary_path:Path,output_dir:Path):
    prior=json.loads(c122_summary_path.read_text(encoding="utf-8"))
    if prior.get("experiment_id")!=c122.EXPERIMENT_ID or prior.get("status")!="PASS" or not prior.get("summary",{}).get("verdict_scope_falsification_gate_passed"):
        raise RuntimeError("C123 requires accepted C122")
    if not torch.cuda.is_available(): raise RuntimeError("C123 requires CUDA")
    before=_sha(protected_result_path); device=torch.device("cuda"); torch.cuda.set_device(0); torch.set_num_threads(2); torch.set_float32_matmul_precision("highest")
    records=[]
    for seed in SEEDS:
        router,loss=c113._train_router(seed,device); m,rows=_measure(router,device); passed=bool(m["gate_passed"])
        records.append({"seed":seed,"final_loss":loss,"metrics":m,"scenarios":rows,"validation_passed":passed})
        print(f"[C123] seed={seed} scenario={m['scenario_pass_rate']:.6f} same={m['unchanged_context_accept_rate']:.6f} changed={m['changed_context_reject_rate']:.6f} pass={passed}",flush=True)
    after=_sha(protected_result_path)
    if before!=after: raise RuntimeError("protected C37 result changed during C123")
    ms=[r["metrics"] for r in records]; all_pass=all(r["validation_passed"] for r in records)
    keys=("scenario_pass_rate","c122_control_gate_rate","unchanged_context_accept_rate","changed_context_reject_rate","changed_context_zero_commit_rate","changed_context_zero_retry_rate","changed_context_zero_fallback_rate","confirmed_none_stop_rate","hidden_trace_invariance")
    summary={"fresh_seeds":list(SEEDS),"validation_base":3,"scenario_count":ms[0]["scenario_count"],"unchanged_context_case_count":ms[0]["unchanged_context_case_count"],"changed_context_case_count":ms[0]["changed_context_case_count"],**{k:_stats([m[k] for m in ms]) for k in keys},"all_validation_passed":all_pass,"commit_context_falsification_gate_passed":all_pass}
    report={"experiment_id":EXPERIMENT_ID,"stage":"V5-E-RUNTIME-COMMIT-CONTEXT-FALSIFICATION","status":"PASS","summary":summary,"records":records,"C122_summary_sha256":_sha(c122_summary_path),"C37_result_sha256_before":before,"C37_result_sha256_after":after,"production_runtime_modified":True,"gate_e_candidate":False,"limitations":["C123 models versioned commit context rather than concurrent real providers","C123 remains synthetic"]}
    output_dir.mkdir(parents=True,exist_ok=False); (output_dir/"summary.json").write_text(json.dumps(report,indent=2,allow_nan=False),encoding="utf-8"); return report
