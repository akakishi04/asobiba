from __future__ import annotations

import hashlib
import json
from pathlib import Path
import statistics

import torch

from fold_lm.v05.retrieval_adapter import PersistedStructuralRetrievalAdapter
from fold_lm.v05_benchmarks import gate_e_c113_stale_eligibility_preflight as c113
from fold_lm.v05_benchmarks import gate_e_c132_os_process_fencing_falsification as c132

EXPERIMENT_ID = "C133-v5e-real-retrieval-vertical-integration"
SEEDS = (20261531, 20261532, 20261533)
ANSWER = 0
RETRIEVE = 2
VISIBLE_MASK = (0, 1, 0, 0)
SCHEMA = "decision-bit"
CORPUS = Path(__file__).resolve().parent / "fixtures" / "c133_structural_records.json"

CASES = (
    ("q0", (1,0,0,0,0,0,0,0), (1,0), 0),
    ("q1", (0,1,0,0,0,0,0,0), (0,1), 1),
    ("q2", (0,0,1,0,0,0,0,0), (1,0), 0),
    ("q3", (0,0,0,1,0,0,0,0), (0,1), 1),
    ("q4", (0,0,0,0,1,0,0,0), (1,0), 0),
    ("q5", (0,0,0,0,0,1,0,0), (0,1), 1),
    ("q6", (0,0,0,0,0,0,1,0), (1,0), 0),
    ("q7", (0,0,0,0,0,0,0,1), (0,1), 1),
)


def _sha(path: Path) -> str:
    return hashlib.file_digest(path.open("rb"), "sha256").hexdigest()


def _stats(values):
    return {
        "mean": statistics.mean(values),
        "median": statistics.median(values),
        "min": min(values),
        "max": max(values),
    }


def _evaluate_seed(router, device, adapter: PersistedStructuralRetrievalAdapter, seed_index: int):
    rows = []
    total = len(CASES)
    for case_index, (expected_key, structure, semantics, expected_value) in enumerate(CASES, start=1):
        initial = c113._predict(
            router,
            dependency=1,
            evidence_present=0,
            observed_hidden=0,
            visible_mask=VISIBLE_MASK,
            device=device,
        )
        retrieval_count = int(initial == RETRIEVE)
        evidence = None
        stats = {}
        if initial == RETRIEVE:
            evidence, stats = adapter.retrieve(
                structure,
                semantics,
                schema=SCHEMA,
                exact=True,
            )

        hit_ok = bool(evidence is not None and evidence.key == expected_key)
        provenance_ok = bool(
            evidence is not None
            and evidence.domain == "c133"
            and evidence.schema == SCHEMA
            and evidence.operations == ("READ_EVIDENCE",)
            and evidence.source_sha256 == adapter.source_sha256
            and evidence.index_fingerprint == adapter.index_fingerprint
            and stats.get("source_sha256") == adapter.source_sha256
            and stats.get("index_fingerprint") == adapter.index_fingerprint
        )
        exact_mode = stats.get("mode") == "exact"
        full_corpus_scored = stats.get("vectors_scored") == adapter.record_count
        commit_count = int(hit_ok and provenance_ok and exact_mode and full_corpus_scored)

        final_action = None
        if commit_count == 1:
            final_action = c113._predict(
                router,
                dependency=1,
                evidence_present=1,
                observed_hidden=evidence.evidence_value,
                visible_mask=VISIBLE_MASK,
                device=device,
            )
        answer_ok = final_action == ANSWER
        evidence_correct = bool(evidence is not None and evidence.evidence_value == expected_value)
        passed = bool(
            initial == RETRIEVE
            and retrieval_count == 1
            and hit_ok
            and provenance_ok
            and exact_mode
            and full_corpus_scored
            and commit_count == 1
            and answer_ok
            and evidence_correct
        )
        rows.append({
            "case": expected_key,
            "expected_value": expected_value,
            "initial_action": initial,
            "retrieval_count": retrieval_count,
            "hit_key": None if evidence is None else evidence.key,
            "retrieved_value": None if evidence is None else evidence.evidence_value,
            "provenance_ok": provenance_ok,
            "exact_mode": exact_mode,
            "vectors_scored": stats.get("vectors_scored"),
            "commit_count": commit_count,
            "final_action": final_action,
            "passed": passed,
        })
        remaining = total - case_index
        print(
            f"[C133] seed {seed_index}/3 case {case_index}/{total} "
            f"key={expected_key} pass={passed} remaining={remaining}",
            flush=True,
        )
    return rows


def _metrics(rows, adapter):
    return {
        "scenario_pass_rate": sum(r["passed"] for r in rows) / len(rows),
        "router_retrieve_rate": sum(r["initial_action"] == RETRIEVE for r in rows) / len(rows),
        "persisted_exact_hit_rate": sum(r["hit_key"] == r["case"] for r in rows) / len(rows),
        "provenance_validation_rate": sum(r["provenance_ok"] for r in rows) / len(rows),
        "evidence_commit_once_rate": sum(r["commit_count"] == 1 for r in rows) / len(rows),
        "post_commit_answer_rate": sum(r["final_action"] == ANSWER for r in rows) / len(rows),
        "final_evidence_accuracy": sum(r["retrieved_value"] == r["expected_value"] for r in rows) / len(rows),
        "exact_mode_rate": sum(r["exact_mode"] for r in rows) / len(rows),
        "full_corpus_scored_rate": sum(r["vectors_scored"] == adapter.record_count for r in rows) / len(rows),
        "pre_retrieval_action_invariance": float(len({r["initial_action"] for r in rows}) == 1),
        "scenario_count": len(rows),
    }


def run(*, protected_result_path: Path, c132_summary_path: Path, output_dir: Path):
    prior = json.loads(c132_summary_path.read_text(encoding="utf-8"))
    if (
        prior.get("experiment_id") != c132.EXPERIMENT_ID
        or prior.get("status") != "PASS"
        or not prior.get("summary", {}).get("os_process_sqlite_fencing_falsification_gate_passed")
    ):
        raise RuntimeError("C133 requires accepted C132")
    if not torch.cuda.is_available():
        raise RuntimeError("C133 requires CUDA")

    before = _sha(protected_result_path)
    adapter = PersistedStructuralRetrievalAdapter(CORPUS)
    output_dir.mkdir(parents=True, exist_ok=False)
    device = torch.device("cuda")
    torch.cuda.set_device(0)
    torch.set_num_threads(2)
    torch.set_float32_matmul_precision("highest")

    records = []
    for seed_index, seed in enumerate(SEEDS, start=1):
        print(f"[C133] seed {seed_index}/3 train start seed={seed}", flush=True)
        router, loss = c113._train_router(seed, device)
        print(f"[C133] seed {seed_index}/3 train done loss={loss:.8f}", flush=True)
        rows = _evaluate_seed(router, device, adapter, seed_index)
        m = _metrics(rows, adapter)
        m["accepted_c132_prerequisite_rate"] = 1.0
        deciding = [k for k in m if k.endswith("_rate") or k in ("final_evidence_accuracy", "pre_retrieval_action_invariance")]
        m["gate_passed"] = all(m[k] == 1.0 for k in deciding)
        records.append({"seed": seed, "final_loss": loss, "metrics": m, "cases": rows, "validation_passed": bool(m["gate_passed"])})
        print(
            f"[C133] seed {seed_index}/3 complete "
            f"retrieve={m['router_retrieve_rate']:.6f} hit={m['persisted_exact_hit_rate']:.6f} "
            f"answer={m['post_commit_answer_rate']:.6f} pass={m['gate_passed']}",
            flush=True,
        )

    after = _sha(protected_result_path)
    if before != after:
        raise RuntimeError("protected C37 result changed during C133")

    ms = [r["metrics"] for r in records]
    all_pass = all(r["validation_passed"] for r in records)
    keys = [k for k in ms[0] if k.endswith("_rate") or k in ("final_evidence_accuracy", "pre_retrieval_action_invariance")]
    summary = {
        "fresh_seeds": list(SEEDS),
        "validation_base": 3,
        "retrieval_mode": "exact",
        "case_count": len(CASES),
        "corpus_record_count": adapter.record_count,
        "corpus_sha256": adapter.source_sha256,
        "index_fingerprint": adapter.index_fingerprint,
        **{k: _stats([m[k] for m in ms]) for k in keys},
        "all_validation_passed": all_pass,
        "real_retrieval_vertical_integration_gate_passed": all_pass,
    }
    report = {
        "experiment_id": EXPERIMENT_ID,
        "stage": "V5-E-REAL-RETRIEVAL-VERTICAL-INTEGRATION",
        "status": "PASS" if all_pass else "FAIL",
        "summary": summary,
        "records": records,
        "C132_summary_sha256": _sha(c132_summary_path),
        "C37_result_sha256_before": before,
        "C37_result_sha256_after": after,
        "production_runtime_modified": True,
        "gate_e_candidate": False,
        "limitations": [
            "C133 validates vertical RETRIEVE integration, not learned query formation",
            "C133 uses exact StructuralIndex search to isolate integration from approximate-retrieval recall",
            "C133 does not yet test retrieval miss, wrong schema, stale corpus, or bounded-LSH failure semantics",
            "The persisted corpus and signatures are controlled evaluation fixtures, not a natural-language knowledge base",
        ],
    }
    (output_dir / "summary.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    return report
