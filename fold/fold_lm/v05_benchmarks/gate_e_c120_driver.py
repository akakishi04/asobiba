"""Tracked execution driver for C120."""
from __future__ import annotations
import hashlib, json, subprocess, time
from pathlib import Path
from fold_lm.v05_benchmarks import gate_e_c120_receipt_binding_falsification as bench

REPO=Path(r"M:\asobiba\fold"); RUNS=REPO/"runs"
C37=RUNS/"chatgpt-last-result.json"; FIXTURE=RUNS/"fixtures"/"v05-c-composition-20260921.pt"
EXPECTED_C37="FD4A8DA897BDAEA9D103A252E30212C7FF842D23300D7C837333E146DEE51931"
EXPECTED_FIXTURE="A52F8209703149407580F7E2965B61B78653030EE992AF6D759865736741CA9E"
BRANCH="feat/sft-target-loss"

def _run(*args):
    r=subprocess.run(args,cwd=REPO,check=True,text=True,capture_output=True)
    if r.stdout: print(r.stdout.rstrip())
    if r.stderr: print(r.stderr.rstrip())
    return r.stdout.strip()
def _cap(*args): return subprocess.run(args,cwd=REPO,check=True,text=True,capture_output=True).stdout.strip()
def _sha(p): return hashlib.sha256(p.read_bytes()).hexdigest().upper()
def _latest():
    xs=[p for p in RUNS.glob("c119-v5e-reconciliation-*") if (p/"summary.json").exists()]
    if not xs: raise RuntimeError("C119 summary not found")
    return max(xs,key=lambda p:(p/"summary.json").stat().st_mtime)/"summary.json"

def main():
    started=time.perf_counter(); print("=== FOLD C120 V5-E falsification: receipt binding ===")
    print("=== syncing repository ==="); _run("git","pull","--rebase","origin",BRANCH)
    branch=_cap("git","branch","--show-current"); head=_cap("git","rev-parse","HEAD")
    print(f"branch = {branch}"); print(f"commit = {head}"); print("stage = V5-E-RUNTIME-RECEIPT-BINDING-FALSIFICATION")
    print("task = reject wrong-key, wrong-mechanism, and stale-epoch reconciliation receipts")
    print("fresh_seeds = 20261401,20261402,20261403")
    print("runtime_rule = only exact request binding may drive reconciliation state transition")
    if branch!=BRANCH: raise RuntimeError(f"Unexpected branch: {branch}")
    if _cap("git","status","--porcelain","--untracked-files=no"): raise RuntimeError("Tracked working tree is not clean")
    if _sha(C37)!=EXPECTED_C37 or _sha(FIXTURE)!=EXPECTED_FIXTURE: raise RuntimeError("Protected artifact mismatch before C120")
    out=RUNS/f"c120-v5e-receipt-binding-{time.time_ns()}"; prior=_latest()
    print("=== import preflight ==="); print("C120 import OK:",bench.EXPERIMENT_ID,bench.SEEDS)
    print("=== focused regression ===")
    py=str(REPO/".venv-py31315"/"Scripts"/"python.exe")
    _run(py,"-m","unittest","tests_lm.test_v05_controller","tests_lm.test_v05_reconciliation","-v")
    print(f"output_directory = {out}"); print(f"C37_result_sha256_before = {_sha(C37)}"); print(f"fixture_sha256_before = {_sha(FIXTURE)}")
    print("=== C120 benchmark ==="); report=bench.run(protected_result_path=C37,c119_summary_path=prior,output_dir=out)
    shown=dict(report); shown["records"]="omitted; see summary.json"; shown["elapsed_seconds"]=time.perf_counter()-started
    print("\n=== C120 RESULT ==="); print(json.dumps(shown,indent=2,allow_nan=False))
    s=report["summary"]; dirty=_cap("git","status","--porcelain","--untracked-files=no")
    print("\n=== C120 SUMMARY ==="); print(f"status = {report['status']}"); print(f"receipt_binding_falsification_gate_passed = {s['receipt_binding_falsification_gate_passed']}")
    print(f"mask_pair_count = {s['mask_pair_count']}"); print(f"scenario_count = {s['scenario_count']}"); print(f"valid_receipt_case_count = {s['valid_receipt_case_count']}"); print(f"invalid_binding_case_count = {s['invalid_binding_case_count']}")
    print(f"scenario_pass_rate_min = {s['scenario_pass_rate']['min']}"); print(f"valid_binding_accept_rate_min = {s['valid_binding_accept_rate']['min']}"); print(f"invalid_binding_reject_rate_min = {s['invalid_binding_reject_rate']['min']}"); print(f"invalid_binding_zero_commit_rate_min = {s['invalid_binding_zero_commit_rate']['min']}"); print(f"invalid_binding_zero_retry_rate_min = {s['invalid_binding_zero_retry_rate']['min']}"); print(f"hidden_trace_invariance_min = {s['hidden_trace_invariance']['min']}")
    print(f"C37_preserved = {_sha(C37)==EXPECTED_C37}"); print(f"fixture_preserved = {_sha(FIXTURE)==EXPECTED_FIXTURE}"); print(f"repository_tracked_clean = {not bool(dirty)}"); print(f"output_directory = {out}"); print("production_runtime_modified = True"); print("gate_e_candidate = False"); print("\n=== script error, if any ===")
    return 0
if __name__=="__main__": raise SystemExit(main())
