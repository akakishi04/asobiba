"""C80: focused Language gate for materialized training -> GEMM-native inference."""
from __future__ import annotations
import argparse, copy, hashlib, json, time
from pathlib import Path
import torch
from fold_lm.v05.language_task import evaluate_language
from fold_lm.v05.modules import SharedBasisFixedRoutingCore
from fold_lm.v05_benchmarks.gate_b_baseline_comparison import _build_language
from fold_lm.v05_benchmarks.gate_c_shared_basis_aligned_joint_training import TASK_SPECS
from fold_lm.v05_benchmarks.gate_c_shared_basis_direct_joint_training import JointTrainSharedBasisCore, _task_loss
from fold_lm.v05_benchmarks.gate_c_shared_basis_production_optin_integration import _gap, _semantic_equal, _validation_output
from fold_lm.v05_benchmarks.gate_c_shared_basis_training_arithmetic_drift_diagnosis import _parameter_gap_reference_to_production

EXPERIMENT_ID = "C80-shared-basis-train-materialized-infer-native-policy"
SEEDS = (20261021, 20261022, 20261023)
RANK = 4


def _sha(path):
    with Path(path).open("rb") as f: return hashlib.file_digest(f, "sha256").hexdigest()


def _train(seed, reference, production, train, device):
    spec = TASK_SPECS["language"]
    ro = torch.optim.AdamW(reference.parameters(), lr=float(spec["common_lr"]), weight_decay=0.0)
    po = torch.optim.AdamW(production.parameters(), lr=float(spec["common_lr"]), weight_decay=0.0)
    g = torch.Generator(device="cpu").manual_seed(seed + 200)
    for _ in range(int(spec["steps"])):
        idx = torch.randint(train.size, (int(spec["batch_size"]),), generator=g)
        ro.zero_grad(set_to_none=True); rl = _task_loss("language", reference, train, idx, device); rl.backward(); ro.step()
        po.zero_grad(set_to_none=True); pl = _task_loss("language", production, train, idx, device); pl.backward(); po.step()
    return float(rl.detach()), float(pl.detach())


def run(*, protected_result_path: Path, c79_summary_path: Path, output_dir: Path):
    c79 = json.loads(c79_summary_path.read_text(encoding="utf-8"))
    if c79.get("status") != "PASS" or not c79["summary"]["training_arithmetic_order_drift_supported"]:
        raise RuntimeError("C80 requires accepted C79")
    before = _sha(protected_result_path); device = torch.device("cuda")
    records = []
    for seed in SEEDS:
        _cfg, initial, train, validation = _build_language(seed, "v5b", device)
        reference = copy.deepcopy(initial).to(device); reference.core = JointTrainSharedBasisCore(initial.core, RANK).to(device)
        production = copy.deepcopy(initial).to(device); production.core = SharedBasisFixedRoutingCore(initial.core, RANK, execution_mode="materialized").to(device)
        initial_gap = _parameter_gap_reference_to_production(reference.core, production.core)
        ref_loss, prod_loss = _train(seed, reference, production, train, device)
        final_gap = _parameter_gap_reference_to_production(reference.core, production.core)
        ref_out = _validation_output("language", reference, validation, device)
        mat_out = _validation_output("language", production, validation, device)
        mat_gap = _gap(ref_out, mat_out)
        ref_score = float(evaluate_language(reference, validation)["accuracy"])
        mat_score = float(evaluate_language(production, validation)["accuracy"])
        production.core.set_execution_mode("gemm_native")
        native_out = _validation_output("language", production, validation, device)
        native_gap = _gap(ref_out, native_out)
        native_score = float(evaluate_language(production, validation)["accuracy"])
        records.append({"seed": seed, "initial_parameter_gap": initial_gap, "final_parameter_gap": final_gap,
                        "reference_loss": ref_loss, "production_loss": prod_loss, "materialized_gap": mat_gap,
                        "native_gap": native_gap, "materialized_score_equal": ref_score == mat_score,
                        "native_score_equal": ref_score == native_score,
                        "materialized_semantic_equal": _semantic_equal("language", ref_out, mat_out),
                        "native_semantic_equal": _semantic_equal("language", ref_out, native_out)})
        print(f"[C80] seed={seed} param={final_gap:.3e} mat={mat_gap['max_abs']:.3e} native={native_gap['max_abs']:.3e}", flush=True)
    after = _sha(protected_result_path)
    if before != after: raise RuntimeError("protected result changed")
    summary = {"seed_count": len(records), "training_execution_mode": "materialized", "inference_execution_mode": "gemm_native",
               "all_training_parameters_exact": all(r["final_parameter_gap"] == 0.0 for r in records),
               "all_materialized_outputs_exact": all(r["materialized_gap"]["max_abs"] == 0.0 for r in records),
               "all_materialized_scores_equal": all(r["materialized_score_equal"] for r in records),
               "all_materialized_semantic_equal": all(r["materialized_semantic_equal"] for r in records),
               "all_native_outputs_allclose": all(r["native_gap"]["allclose"] for r in records),
               "all_native_scores_equal": all(r["native_score_equal"] for r in records),
               "all_native_semantic_equal": all(r["native_semantic_equal"] for r in records),
               "native_validation_max_abs_gap": max(float(r["native_gap"]["max_abs"]) for r in records)}
    summary["production_policy_gate_passed"] = all(bool(summary[k]) for k in summary if k.startswith("all_"))
    report = {"experiment_id": EXPERIMENT_ID, "stage": "V5-C", "status": "PASS", "records": records, "summary": summary,
              "C79_summary_sha256": _sha(c79_summary_path), "C37_result_sha256_before": before, "C37_result_sha256_after": after,
              "production_runtime_modified": True, "default_dense_runtime_changed": False, "gate_c_candidate": False}
    output_dir.mkdir(parents=True, exist_ok=False); (output_dir / "summary.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main(argv=None):
    p = argparse.ArgumentParser(); p.add_argument("--protected-result", type=Path, default=Path("runs/chatgpt-last-result.json")); p.add_argument("--c79-summary", type=Path, required=True); p.add_argument("--output-dir", type=Path, required=True)
    a = p.parse_args(argv); started = time.perf_counter(); r = run(protected_result_path=a.protected_result, c79_summary_path=a.c79_summary, output_dir=a.output_dir)
    d = dict(r); d["records"] = "omitted; see summary.json"; d["elapsed_seconds"] = time.perf_counter()-started; print("\n=== C80 RESULT ==="); print(json.dumps(d, indent=2)); return 0

if __name__ == "__main__": raise SystemExit(main())
