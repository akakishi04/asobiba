"""Tracked execution driver for C117."""
from __future__ import annotations
import hashlib, json, subprocess, time
from pathlib import Path
from fold_lm.v05_benchmarks import gate_e_c117_post_preflight_failure_fallback as bench

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
    xs=[p for p in RUNS.glob("c116-v5e-priority-refresh-*") if (p/"summary.json").exists()]
    if not xs: raise RuntimeError("C116 summary not found")
    return max(xs,key=lambda p:(p/"summary.json").stat().st_mtime)/"summary.json"

def main():
    started=time.perf_counter(); print("=== FOLD C117 V5-E falsification: post-preflight failure fallback ===")
    print("=== syncing repository ==="); _run("git","pull","--rebase","origin",BRANCH)
    branch=_cap("git","branch","--show-current"); head=_cap("git","rev-parse","HEAD")
    print(f"branch = {branch}"); print(f"commit = {head}"); print("stage = V5-E-RUNTIME-AUTHORITY-FALSIFICATION")
    print("task = compose authoritative preflight with post-preflight no-commit fallback")
    print("fresh_seeds = 20261371,20261372,20261373")
    if branch!=BRANCH: raise RuntimeError(f"Unexpected branch: {branch}")
    if _cap("git","status","--porcelain","--untracked-files=no"): raise RuntimeError("Tracked working tree is not clean")
    if _sha(C37)!=EXPECTED_C37 or _sha(FIXTURE)!=EXPECTED_FIXTURE: raise RuntimeError("Protected artifact mismatch before C117")
    out=RUNS/f"c117-v5e-post-preflight-fallback-{time.time_ns()}"; prior=_latest()
    print("=== import preflight ===")
    print("C117 import OK:",bench.EXPERIMENT_ID,bench.SEEDS)
    smoke0=bench.helper._row(0); smoke1=bench.helper._row(1)
    if (smoke0["target"],smoke1["target"]) != (1,0):
        raise RuntimeError(f"C117 target smoke mismatch: {(smoke0['target'],smoke1['target'])}")
    print("C117 target-construction smoke OK: hidden0->1 hidden1->0")
    print("=== focused regression ==="); _run(str(REPO/".venv-py31315"/"Scripts"/"python.exe"),"-m","unittest","tests_lm.test_v05_controller","-v")
    print(f"output_directory = {out}"); print(f"C37_result_sha256_before = {_sha(C37)}"); print(f"fixture_sha256_before = {_sha(FIXTURE)}")
    print("=== C117 benchmark ==="); report=bench.run(protected_result_path=C37,c116_summary_path=prior,output_dir=out)
    shown=dict(report); shown["records"]="omitted; see summary.json"; shown["elapsed_seconds"]=time.perf_counter()-started
    print("\n=== C117 RESULT ==="); print(json.dumps(shown,indent=2,allow_nan=False))
    s=report["summary"]; dirty=_cap("git","status","--porcelain","--untracked-files=no")
    print("\n=== C117 SUMMARY ==="); print(f"status = {report['status']}"); print(f"post_preflight_execution_failure_fallback_gate_passed = {s['post_preflight_execution_failure_fallback_gate_passed']}")
    print(f"mask_pair_count = {s['mask_pair_count']}"); print(f"trajectory_count = {s['trajectory_count']}"); print(f"trajectory_pass_rate_min = {s['trajectory_pass_rate']['min']}")
    print(f"preflight_correct_rate_min = {s['preflight_correct_rate']['min']}"); print(f"failure_fallback_recovery_rate_min = {s['failure_fallback_recovery_rate']['min']}")
    print(f"ineligible_mechanism_count_sum = {s['ineligible_mechanism_count']['sum']}"); print(f"repeat_failed_mechanism_count_sum = {s['repeat_failed_mechanism_count']['sum']}"); print(f"budget_violation_count_sum = {s['budget_violation_count']['sum']}")
    print(f"hidden_trace_invariance_min = {s['hidden_action_trace_invariance']['min']}"); print(f"C37_preserved = {_sha(C37)==EXPECTED_C37}"); print(f"fixture_preserved = {_sha(FIXTURE)==EXPECTED_FIXTURE}"); print(f"repository_tracked_clean = {not bool(dirty)}"); print(f"output_directory = {out}"); print("production_runtime_modified = False"); print("gate_e_candidate = False"); print("\n=== script error, if any ===")
    return 0
if __name__=="__main__": raise SystemExit(main())
