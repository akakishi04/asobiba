from __future__ import annotations

import hashlib
import json
from pathlib import Path
import statistics

import torch

from fold_lm.v05.retrieval_adapter import PersistedStructuralRetrievalAdapter
from fold_lm.v05_benchmarks import gate_e_c113_stale_eligibility_preflight as c113
from fold_lm.v05_benchmarks import gate_e_c133_real_retrieval_integration as c133

EXPERIMENT_ID = "C134-v5e-retrieval-miss-semantics"
SEEDS = (20261541, 20261542, 20261543)
ANSWER = 0
RETRIEVE = 2
STOP_UNRESOLVED = 5
VISIBLE_RETRIEVE = (0, 1, 0, 0)
VISIBLE_NONE = (0, 0, 0, 0)
CASE_TYPES = ("MATCH", "STRUCTURE_MISS", "WRONG_SCHEMA")


def _sha(path: Path) -> str:
    return hashlib.file_digest(path.open("rb"), "sha256").hexdigest()


def _stats(values):
    return {
        "mean": statistics.mean(values),
        "median": statistics.median(values),
        "min": min(values),
        "max": max(values),
    }


def _query(case_type: str, structure, semantics):
    if case_type == "MATCH":
        return structure, semantics, c133.SCHEMA
    if case_type == "STRUCTURE_MISS":
        return tuple(-x for x in structure), semantics, c133.SCHEMA
    if case_type == "WRONG_SCHEMA":
        return structure, semantics, "wrong-schema"
    raise ValueError(case_type)


def _evaluate_seed(router, device, adapter: PersistedStructuralRetrievalAdapter, seed_index: int):
    rows = []
    total = len(c133.CASES) * len(CASE_TYPES)
    case_index = 0
    for expected_key, structure, semantics, expected_value in c133.CASES:
        for case_type in CASE_TYPES:
            case_index += 1
            initial = c113._predict(
                router,
                dependency=1,
                evidence_present=0,
                observed_hidden=0,
                visible_mask=VISIBLE_RETRIEVE,
                device=device,
            )
            q_structure, q_semantics, q_schema = _query(case_type, structure, semantics)
            evidence = None
            stats = {}
            if initial == RETRIEVE:
                evidence, stats = adapter.retrieve(
                    q_structure,
                    q_semantics,
                    schema=q_schema,
                    exact=True,
                )

            provenance_stats_ok = bool(
                stats.get("source_sha256") == adapter.source_sha256
                and stats.get("index_fingerprint") == adapter.index_fingerprint
                and stats.get("mode") == "exact"
                and stats.get("vectors_scored") == adapter.record_count
            )
            hit_ok = bool(evidence is not None and evidence.key == expected_key)
            evidence_provenance_ok = bool(
                evidence is not None
                and evidence.source_sha256 == adapter.source_sha256
                and evidence.index_fingerprint == adapter.index_fingerprint
                and evidence.schema == c133.SCHEMA
            )

            commit_count = 0
            final_action = None
            final_status = "UNSET"
            if case_type == "MATCH":
                if hit_ok and evidence_provenance_ok and provenance_stats_ok:
                    commit_count = 1
                    final_action = c113._predict(
                        router,
                        dependency=1,
                        evidence_present=1,
                        observed_hidden=evidence.evidence_value,
                        visible_mask=VISIBLE_RETRIEVE,
                        device=device,
                    )
                final_status = "ANSWERED" if final_action == ANSWER else "MATCH_FAILED"
                passed = bool(
                    initial == RETRIEVE
                    and commit_count == 1
                    and final_action == ANSWER
                    and evidence is not None
                    and evidence.evidence_value == expected_value
                    and provenance_stats_ok
                )
            else:
                # A real zero-hit result is not evidence. Runtime marks RETRIEVE
                # unavailable for this attempt, reobserves, and must stop rather
                # than fabricate or commit a value.
                if evidence is None and provenance_stats_ok:
                    final_action = c113._predict(
                        router,
                        dependency=1,
                        evidence_present=0,
                        observed_hidden=0,
                        visible_mask=VISIBLE_NONE,
                        device=device,
                    )
                final_status = "UNRESOLVED" if final_action == STOP_UNRESOLVED else "MISS_FAILED"
                passed = bool(
                    initial == RETRIEVE
                    and evidence is None
                    and commit_count == 0
                    and provenance_stats_ok
                    and final_action == STOP_UNRESOLVED
                )

            row = {
                "case": expected_key,
                "case_type": case_type,
                "initial_action": initial,
                "hit_key": None if evidence is None else evidence.key,
                "commit_count": commit_count,
                "final_action": final_action,
                "final_status": final_status,
                "provenance_stats_ok": provenance_stats_ok,
                "passed": passed,
            }
            rows.append(row)
            remaining = total - case_index
            print(
                f"[C134] seed {seed_index}/3 case {case_index}/{total} "
                f"type={case_type} key={expected_key} pass={passed} remaining={remaining}",
                flush=True,
            )
    return rows


def _metrics(rows):
    match = [r for r in rows if r["case_type"] == "MATCH"]
    misses = [r for r in rows if r["case_type"] != "MATCH"]
    structure_miss = [r for r in rows if r["case_type"] == "STRUCTURE_MISS"]
    wrong_schema = [r for r in rows if r["case_type"] == "WRONG_SCHEMA"]
    return {
        "scenario_pass_rate": sum(r["passed"] for r in rows) / len(rows),
        "router_retrieve_rate": sum(r["initial_action"] == RETRIEVE for r in rows) / len(rows),
        "match_control_pass_rate": sum(r["passed"] for r in match) / len(match),
        "miss_zero_hit_rate": sum(r["hit_key"] is None for r in misses) / len(misses),
        "miss_zero_commit_rate": sum(r["commit_count"] == 0 for r in misses) / len(misses),
        "miss_stop_unresolved_rate": sum(r["final_status"] == "UNRESOLVED" for r in misses) / len(misses),
        "structure_miss_safe_rate": sum(r["passed"] for r in structure_miss) / len(structure_miss),
        "wrong_schema_safe_rate": sum(r["passed"] for r in wrong_schema) / len(wrong_schema),
        "retrieval_provenance_stats_rate": sum(r["provenance_stats_ok"] for r in rows) / len(rows),
        "scenario_count": len(rows),
        "miss_case_count": len(misses),
    }


def run(*, protected_result_path: Path, c133_summary_path: Path, output_dir: Path):
    prior = json.loads(c133_summary_path.read_text(encoding="utf-8"))
    if (
        prior.get("experiment_id") != c133.EXPERIMENT_ID
        or prior.get("status") != "PASS"
        or not prior.get("summary", {}).get("real_retrieval_vertical_integration_gate_passed")
    ):
        raise RuntimeError("C134 requires accepted C133")
    if not torch.cuda.is_available():
        raise RuntimeError("C134 requires CUDA")

    before = _sha(protected_result_path)
    adapter = PersistedStructuralRetrievalAdapter(c133.CORPUS)
    output_dir.mkdir(parents=True, exist_ok=False)
    device = torch.device("cuda")
    torch.cuda.set_device(0)
    torch.set_num_threads(2)
    torch.set_float32_matmul_precision("highest")

    records = []
    for seed_index, seed in enumerate(SEEDS, start=1):
        print(f"[C134] seed {seed_index}/3 train start seed={seed}", flush=True)
        router, loss = c113._train_router(seed, device)
        print(f"[C134] seed {seed_index}/3 train done loss={loss:.8f}", flush=True)
        rows = _evaluate_seed(router, device, adapter, seed_index)
        m = _metrics(rows)
        m["accepted_c133_prerequisite_rate"] = 1.0
        deciding = [k for k in m if k.endswith("_rate")]
        m["gate_passed"] = all(m[k] == 1.0 for k in deciding)
        records.append({
            "seed": seed,
            "final_loss": loss,
            "metrics": m,
            "cases": rows,
            "validation_passed": bool(m["gate_passed"]),
        })
        print(
            f"[C134] seed {seed_index}/3 complete match={m['match_control_pass_rate']:.6f} "
            f"miss_no_commit={m['miss_zero_commit_rate']:.6f} stop={m['miss_stop_unresolved_rate']:.6f} "
            f"pass={m['gate_passed']}",
            flush=True,
        )

    after = _sha(protected_result_path)
    if before != after:
        raise RuntimeError("protected C37 result changed during C134")

    ms = [r["metrics"] for r in records]
    all_pass = all(r["validation_passed"] for r in records)
    keys = [k for k in ms[0] if k.endswith("_rate")]
    summary = {
        "fresh_seeds": list(SEEDS),
        "validation_base": 3,
        "retrieval_mode": "exact",
        "case_types": list(CASE_TYPES),
        "case_count": ms[0]["scenario_count"],
        "miss_case_count": ms[0]["miss_case_count"],
        "corpus_record_count": adapter.record_count,
        "corpus_sha256": adapter.source_sha256,
        "index_fingerprint": adapter.index_fingerprint,
        **{k: _stats([m[k] for m in ms]) for k in keys},
        "all_validation_passed": all_pass,
        "retrieval_miss_semantics_gate_passed": all_pass,
    }
    report = {
        "experiment_id": EXPERIMENT_ID,
        "stage": "V5-E-REAL-RETRIEVAL-MISS-SEMANTICS",
        "status": "PASS" if all_pass else "FAIL",
        "summary": summary,
        "records": records,
        "C133_summary_sha256": _sha(c133_summary_path),
        "C37_result_sha256_before": before,
        "C37_result_sha256_after": after,
        "production_runtime_modified": False,
        "gate_e_candidate": False,
        "limitations": [
            "C134 tests exact-search zero-hit semantics, not bounded-LSH recall failure",
            "C134 does not test stale corpus or learned query formation",
            "C134 uses a controlled persisted corpus rather than a natural-language knowledge base",
        ],
    }
    (output_dir / "summary.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    return report
