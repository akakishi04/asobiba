from __future__ import annotations
import hashlib, json, statistics
from pathlib import Path
import torch
from fold_lm.v05_benchmarks import gate_e_c113_stale_eligibility_preflight as c113
from fold_lm.v05_benchmarks import gate_e_c118_unknown_effect_containment as c118
from fold_lm.v05_benchmarks import gate_e_c119_reconcile_helper as helper

EXPERIMENT_ID="C119-v5e-idempotency-receipt-reconciliation"
SEEDS=(20261391,20261392,20261393)

def _sha(p): return hashlib.file_digest(p.open("rb"),"sha256").hexdigest()
def _stats(v): return {"mean":statistics.mean(v),"median":statistics.median(v),"min":min(v),"max":max(v)}

def run(*,protected_result_path:Path,c118_summary_path:Path,output_dir:Path):
    prior=json.loads(c118_summary_path.read_text(encoding="utf-8"))
    if prior.get("experiment_id")!=c118.EXPERIMENT_ID or prior.get("status")!="PASS" or not prior.get("summary",{}).get("unknown_effect_containment_gate_passed"):
        raise RuntimeError("C119 requires accepted C118")
    if not torch.cuda.is_available(): raise RuntimeError("C119 requires CUDA")
    before=_sha(protected_result_path); device=torch.device("cuda"); torch.cuda.set_device(0); torch.set_num_threads(2); torch.set_float32_matmul_precision("highest")
    records=[]
    for seed in SEEDS:
        router,loss=c113._train_router(seed,device); m,rows=helper.evaluate(router,device); passed=bool(m["gate_passed"])
        records.append({"seed":seed,"final_loss":loss,"metrics":m,"scenarios":rows,"validation_passed":passed})
        print(f"[C119] seed={seed} scenario={m['scenario_pass_rate']:.6f} applied={m['applied_answer_rate']:.6f} not_applied={m['not_applied_answer_rate']:.6f} unknown={m['unknown_containment_rate']:.6f} pass={passed}",flush=True)
    after=_sha(protected_result_path)
    if before!=after: raise RuntimeError("protected C37 result changed during C119")
    ms=[r["metrics"] for r in records]; all_pass=all(r["validation_passed"] for r in records)
    keys=("scenario_pass_rate","reconciliation_once_rate","applied_answer_rate","applied_zero_retry_rate","applied_one_commit_rate","not_applied_answer_rate","not_applied_one_retry_rate","not_applied_same_key_rate","not_applied_one_commit_rate","unknown_containment_rate","unknown_zero_retry_rate","unknown_zero_commit_rate","unknown_zero_fallback_rate","recovered_one_logical_effect_rate","confirmed_none_stop_rate","hidden_trace_invariance")
    summary={"fresh_seeds":list(SEEDS),"validation_base":3,"mask_pair_count":ms[0]["mask_pair_count"],"scenario_count":ms[0]["scenario_count"],"reconciliation_case_count":ms[0]["reconciliation_case_count"],**{k:_stats([m[k] for m in ms]) for k in keys},"all_validation_passed":all_pass,"idempotency_receipt_reconciliation_gate_passed":all_pass}
    report={"experiment_id":EXPERIMENT_ID,"stage":"V5-E-RUNTIME-RECONCILIATION-FALSIFICATION","status":"PASS","summary":summary,"records":records,"C118_summary_sha256":_sha(c118_summary_path),"C37_result_sha256_before":before,"C37_result_sha256_after":after,"production_runtime_modified":False,"gate_e_candidate":False}
    output_dir.mkdir(parents=True,exist_ok=False); (output_dir/"summary.json").write_text(json.dumps(report,indent=2,allow_nan=False),encoding="utf-8"); return report
