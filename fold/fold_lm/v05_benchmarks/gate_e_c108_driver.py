"""Tracked execution driver for C108 feature re-encoding falsification."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import time

from fold_lm.v05_benchmarks import gate_e_c108_feature_reencoding_falsification as bench

REPO = Path(r"M:\asobiba\fold")
RUNS = REPO / "runs"
C37 = RUNS / "chatgpt-last-result.json"
FIXTURE = RUNS / "fixtures" / "v05-c-composition-20260921.pt"
EXPECTED_C37 = "FD4A8DA897BDAEA9D103A252E30212C7FF842D23300D7C837333E146DEE51931"
EXPECTED_FIXTURE = "A52F8209703149407580F7E2965B61B78653030EE992AF6D759865736741CA9E"
BRANCH = "feat/sft-target-loss"


def _run(*args: str) -> str:
    result = subprocess.run(args, cwd=REPO, check=True, text=True, capture_output=True)
    if result.stdout:
        print(result.stdout.rstrip())
    if result.stderr:
        print(result.stderr.rstrip())
    return result.stdout.strip()


def _capture(*args: str) -> str:
    return subprocess.run(args, cwd=REPO, check=True, text=True, capture_output=True).stdout.strip()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _latest_c107() -> Path:
    candidates = [p for p in RUNS.glob("c107-v5e-independent-eval-*") if (p / "summary.json").exists()]
    if not candidates:
        raise RuntimeError("C107 summary not found")
    return max(candidates, key=lambda p: (p / "summary.json").stat().st_mtime) / "summary.json"


def main() -> int:
    started = time.perf_counter()
    print("=== FOLD C108 V5-E falsification: feature re-encoding ===")
    print("=== syncing repository ===")
    _run("git", "pull", "--rebase", "origin", BRANCH)
    branch = _capture("git", "branch", "--show-current")
    head = _capture("git", "rev-parse", "HEAD")
    print(f"branch = {branch}")
    print(f"commit = {head}")
    print("stage = V5-E-FALSIFICATION")
    print("task = held-out signed-codebook feature re-encoding")
    print(f"fresh_seeds = {','.join(str(x) for x in bench.SEEDS)}")
    print("train_bases = 0,1,2")
    print("validation_base = 3 (unseen)")
    print(f"training_codebooks = {bench.TRAIN_CODEBOOKS}")
    print(f"ood_codebooks = {bench.OOD_CODEBOOKS}")
    print("shared_semantic_contract = false < 0 < true")
    if branch != BRANCH:
        raise RuntimeError(f"Unexpected branch: {branch}")
    dirty = _capture("git", "status", "--porcelain", "--untracked-files=no")
    if dirty:
        raise RuntimeError(f"Tracked working tree is not clean:\n{dirty}")

    c37_before = _sha(C37)
    fixture_before = _sha(FIXTURE)
    if c37_before != EXPECTED_C37 or fixture_before != EXPECTED_FIXTURE:
        raise RuntimeError("Protected artifact mismatch before C108")

    c107_summary = _latest_c107()
    out_dir = RUNS / f"c108-v5e-feature-reencoding-{time.time_ns()}"
    print("=== import preflight ===")
    print("C108 import OK:", bench.EXPERIMENT_ID, bench.SEEDS)
    print("=== focused regression ===")
    _run(str(REPO / ".venv-py31315" / "Scripts" / "python.exe"), "-m", "unittest", "tests_lm.test_v05_controller", "-v")
    print(f"output_directory = {out_dir}")
    print(f"C37_result_sha256_before = {c37_before}")
    print(f"fixture_sha256_before = {fixture_before}")
    print("=== C108 benchmark ===")

    report = bench.run(protected_result_path=C37, c107_summary_path=c107_summary, output_dir=out_dir)
    shown = dict(report)
    shown["records"] = "omitted; see summary.json"
    shown["elapsed_seconds"] = time.perf_counter() - started
    print("\n=== C108 RESULT ===")
    print(json.dumps(shown, indent=2, allow_nan=False))

    c37_after = _sha(C37)
    fixture_after = _sha(FIXTURE)
    dirty_after = _capture("git", "status", "--porcelain", "--untracked-files=no")
    s = report["summary"]
    print("\n=== C108 SUMMARY ===")
    print(f"status = {report['status']}")
    print(f"feature_reencoding_falsification_gate_passed = {s['feature_reencoding_falsification_gate_passed']}")
    print(f"ood_scalar_values_absent_from_training = {s['ood_scalar_values_absent_from_training']}")
    print(f"anchor_action_accuracy_min = {s['anchor_action_accuracy']['min']}")
    print(f"anchor_minimum_class_recall_min = {s['anchor_minimum_class_recall']['min']}")
    print(f"ood_action_accuracy_min = {s['ood_action_accuracy']['min']}")
    print(f"ood_minimum_class_recall_min = {s['ood_minimum_class_recall']['min']}")
    print(f"ood_minimum_burden_rate_min = {s['ood_minimum_burden_rate']['min']}")
    print(f"ood_ineligible_mechanism_count_sum = {s['ood_ineligible_mechanism_count']['sum']}")
    print(f"ood_action_flip_count_sum = {s['ood_action_flip_count']['sum']}")
    print(f"ood_hidden_invariance_min = {s['ood_hidden_counterfactual_action_invariance']['min']}")
    print(f"C37_preserved = {c37_after == EXPECTED_C37}")
    print(f"fixture_preserved = {fixture_after == EXPECTED_FIXTURE}")
    print(f"repository_tracked_clean = {not bool(dirty_after)}")
    print(f"output_directory = {out_dir}")
    print("production_runtime_modified = False")
    print("gate_e_candidate = False")
    print("\n=== script error, if any ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
