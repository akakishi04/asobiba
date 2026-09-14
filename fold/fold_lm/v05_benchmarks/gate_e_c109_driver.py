"""Tracked execution driver for C109."""
from __future__ import annotations
import hashlib,json,subprocess,time
from pathlib import Path
from fold_lm.v05_benchmarks import gate_e_c109_reencoding_failure_localization as bench

REPO=Path(r"M:\asobiba\fold")
RUNS=REPO/"runs"
C37=RUNS/"chatgpt-last-result.json"
FIXTURE=RUNS/"fixtures"/"v05-c-composition-20260921.pt"
EXPECTED_C37="FD4A8DA897BDAEA9D103A252E30212C7FF842D23300D7C837333E146DEE51931"
EXPECTED_FIXTURE="A52F8209703149407580F7E2965B61B78653030EE992AF6D759865736741CA9E"
BRANCH="feat/sft-target-loss"

def cap(*args):
    return subprocess.run(args,cwd=REPO,check=True,text=True,capture_output=True).stdout.strip()

def run_show(*args):
    r=subprocess.run(args,cwd=REPO,check=True,text=True,capture_output=True)
    if r.stdout: print(r.stdout.rstrip())
    if r.stderr: print(r.stderr.rstrip())

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest().upper()

def latest_c108():
    xs=[p for p in RUNS.glob("c108-v5e-feature-reencoding-*") if (p/"summary.json").exists()]
    if not xs: raise RuntimeError("C108 summary not found")
    return max(xs,key=lambda p:(p/"summary.json").stat().st_mtime)/"summary.json"

def main():
    started=time.perf_counter()
    print("=== FOLD C109 V5-E diagnostic: re-encoding failure localization ===")
    print("=== syncing repository ===")
    run_show("git","pull","--rebase","origin",BRANCH)
    branch=cap("git","branch","--show-current"); head=cap("git","rev-parse","HEAD")
    print(f"branch = {branch}"); print(f"commit = {head}")
    print("stage = V5-E-FALSIFICATION-DIAGNOSTIC")
    print("task = localize C108 codebook/class failure without changing training")
    print("replay_seeds = 20261311,20261312,20261313")
    print("training_and_thresholds_changed = false")
    if branch!=BRANCH: raise RuntimeError(f"Unexpected branch: {branch}")
    if cap("git","status","--porcelain","--untracked-files=no"): raise RuntimeError("Tracked working tree is not clean")
    before=sha(C37); fb=sha(FIXTURE)
    if before!=EXPECTED_C37 or fb!=EXPECTED_FIXTURE: raise RuntimeError("Protected artifact mismatch before C109")
    c108=latest_c108(); out=RUNS/f"c109-v5e-reencoding-localization-{time.time_ns()}"
    print("=== import preflight ==="); print("C109 import OK:",bench.EXPERIMENT_ID,bench.REPLAY_SEEDS)
    print("=== focused regression ===")
    run_show(str(REPO/".venv-py31315"/"Scripts"/"python.exe"),"-m","unittest","tests_lm.test_v05_controller","-v")
    print(f"output_directory = {out}"); print(f"C37_result_sha256_before = {before}"); print(f"fixture_sha256_before = {fb}")
    print("=== C109 diagnostic ===")
    report=bench.run(protected_result_path=C37,c108_summary_path=c108,output_dir=out)
    shown=dict(report); shown["failing_conditions"]="omitted; see summary.json"; shown["elapsed_seconds"]=time.perf_counter()-started
    print("\n=== C109 RESULT ==="); print(json.dumps(shown,indent=2,allow_nan=False))
    after=sha(C37); fa=sha(FIXTURE); dirty=cap("git","status","--porcelain","--untracked-files=no"); s=report["summary"]
    print("\n=== C109 SUMMARY ===")
    print(f"status = {report['status']}")
    print(f"failure_localization_completed = {s['failure_localization_completed']}")
    print(f"known_c108_negative_reproduced = {s['known_c108_negative_reproduced']}")
    print(f"failing_condition_count = {s['failing_condition_count']}")
    print(f"failing_seed_codebook_pairs = {s['failing_seed_codebook_pairs']}")
    print(f"replay_anchor_action_accuracy_min = {s['replay_anchor_action_accuracy']['min']}")
    print(f"replay_ood_action_accuracy_min = {s['replay_ood_action_accuracy']['min']}")
    print(f"C37_preserved = {after==EXPECTED_C37}"); print(f"fixture_preserved = {fa==EXPECTED_FIXTURE}"); print(f"repository_tracked_clean = {not bool(dirty)}")
    print(f"output_directory = {out}"); print("production_runtime_modified = False"); print("gate_e_candidate = False")
    print("\n=== script error, if any ===")
    return 0

if __name__=="__main__": raise SystemExit(main())
