from __future__ import annotations

import hashlib
import json
from pathlib import Path
import statistics

import torch

from fold_lm.v05.retrieval_adapter import PersistedStructuralRetrievalAdapter
from fold_lm.v05_benchmarks import gate_e_c113_stale_eligibility_preflight as c113
from fold_lm.v05_benchmarks import gate_e_c133_real_retrieval_integration as c133
from fold_lm.v05_benchmarks import gate_e_c134_retrieval_miss_semantics as c134

EXPERIMENT_ID = "C135-v5e-bounded-retrieval-exact-recovery"
SEEDS = (20261551, 20261552, 20261553)
ANSWER = 0
RETRIEVE = 2
STOP_UNRESOLVED = 5
VISIBLE_RETRIEVE = (0, 1, 0, 0)
VISIBLE_NONE = (0, 0, 0, 0)
SCAN_LIMIT = 1
PROBES = 1

CASES = (
    (
        "BOUNDED_HIT",
        "q5",
        (0, 0, 0, 0, 0, 1, 0, 0),
        (0, 1),
        c133.SCHEMA,
        1,
    ),
    (
        "BOUNDED_FALSE_NEGATIVE",
        "q6",
        (0, 0, 0, 0, 0, 0, 1, 0),
        (1, 0),
        c133.SCHEMA,
        0,
    ),
    (
        "TRUE_MISS",
        None,
        (-1, 0, 0, 0, 0, 0, 0, 0),
        (1, 0),
        c133.SCHEMA,
        None,
    ),
    (
        "WRONG_SCHEMA",
        None,
        (1, 0, 0, 0, 0, 0, 0, 0),
        (1, 0),
        "other-schema",
        None,
    ),
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


def _provenance_ok(evidence, trace, adapter) -> bool:
    bounded = trace.get("bounded") or {}
    exact = trace.get("exact")
    common = (
        bounded.get("source_sha256") == adapter.source_sha256
        and bounded.get("index_fingerprint") == adapter.index_fingerprint
    )
    if exact is not None:
        common = common and (
            exact.get("source_sha256") == adapter.source_sha256
            and exact.get("index_fingerprint") == adapter.index_fingerprint
        )
    if evidence is None:
        return bool(common)
    return bool(
        common
        and evidence.source_sha256 == adapter.source_sha256
        and evidence.index_fingerprint == adapter.index_fingerprint
        and evidence.domain == "c133"
        and evidence.operations == ("READ_EVIDENCE",)
    )


def _evaluate_seed(router, device, adapter, seed_index: int):
    rows = []
    total = len(CASES)
    for case_index, (case_type, expected_key, structure, semantics, schema, expected_value) in enumerate(CASES, start=1):
        initial = c113._predict(
            router,
            dependency=1,
            evidence_present=0,
            observed_hidden=0,
            visible_mask=VISIBLE_RETRIEVE,
            device=device,
        )
        evidence = None
        trace = {}
        if initial == RETRIEVE:
            evidence, trace = adapter.retrieve_with_exact_recovery(
                structure,
                semantics,
                schema=schema,
                scan_limit=SCAN_LIMIT,
                probes=PROBES,
            )

        provenance_ok = _provenance_ok(evidence, trace, adapter)
        bounded_zero_hit = bool(initial == RETRIEVE and trace and trace["bounded"]["vectors_scored"] == 1 and evidence is None)
        commit_count = 0
        final_action = None
        if evidence is not None and provenance_ok:
            commit_count = 1
            final_action = c113._predict(
                router,
                dependency=1,
                evidence_present=1,
                observed_hidden=evidence.evidence_value,
                visible_mask=VISIBLE_RETRIEVE,
                device=device,
            )
        elif initial == RETRIEVE:
            final_action = c113._predict(
                router,
                dependency=1,
                evidence_present=0,
                observed_hidden=0,
                visible_mask=VISIBLE_NONE,
                device=device,
            )

        hit_key = None if evidence is None else evidence.key
        if case_type == "BOUNDED_HIT":
            passed = bool(
                initial == RETRIEVE
                and hit_key == expected_key
                and evidence.evidence_value == expected_value
                and trace.get("final_mode") == "bounded_lsh"
                and not trace.get("exact_attempted")
                and commit_count == 1
                and final_action == ANSWER
                and provenance_ok
            )
        elif case_type == "BOUNDED_FALSE_NEGATIVE":
            passed = bool(
                initial == RETRIEVE
                and hit_key == expected_key
                and evidence.evidence_value == expected_value
                and trace.get("bounded", {}).get("mode") == "bounded_lsh"
                and trace.get("bounded", {}).get("vectors_scored") == 1
                and trace.get("exact_attempted")
                and trace.get("recovered_from_bounded_miss")
                and trace.get("final_mode") == "exact"
                and trace.get("exact", {}).get("vectors_scored") == adapter.record_count
                and commit_count == 1
                and final_action == ANSWER
                and provenance_ok
            )
        else:
            passed = bool(
                initial == RETRIEVE
                and evidence is None
                and trace.get("exact_attempted")
                and not trace.get("recovered_from_bounded_miss")
                and trace.get("final_mode") == "none"
                and commit_count == 0
                and final_action == STOP_UNRESOLVED
                and provenance_ok
            )

        rows.append({
            "case_type": case_type,
            "expected_key": expected_key,
            "expected_value": expected_value,
            "initial_action": initial,
            "bounded_vectors_scored": None if not trace else trace["bounded"].get("vectors_scored"),
            "exact_attempted": bool(trace.get("exact_attempted")) if trace else False,
            "recovered_from_bounded_miss": bool(trace.get("recovered_from_bounded_miss")) if trace else False,
            "final_mode": trace.get("final_mode") if trace else None,
            "hit_key": hit_key,
            "retrieved_value": None if evidence is None else evidence.evidence_value,
            "provenance_ok": provenance_ok,
            "commit_count": commit_count,
            "final_action": final_action,
            "bounded_zero_hit": bounded_zero_hit,
            "passed": passed,
        })
        print(
            f"[C135] seed {seed_index}/3 case {case_index}/{total} "
            f"type={case_type} pass={passed} remaining={total-case_index}",
            flush=True,
        )
    return rows


def _metrics(rows):
    by_type = {row["case_type"]: row for row in rows}
    bounded_hit = by_type["BOUNDED_HIT"]
    false_negative = by_type["BOUNDED_FALSE_NEGATIVE"]
    true_miss = by_type["TRUE_MISS"]
    wrong_schema = by_type["WRONG_SCHEMA"]
    miss_controls = (true_miss, wrong_schema)
    return {
        "scenario_pass_rate": sum(row["passed"] for row in rows) / len(rows),
        "router_retrieve_rate": sum(row["initial_action"] == RETRIEVE for row in rows) / len(rows),
        "bounded_hit_no_exact_rate": float(
            bounded_hit["hit_key"] == "q5"
            and not bounded_hit["exact_attempted"]
            and bounded_hit["final_mode"] == "bounded_lsh"
        ),
        "bounded_false_negative_detection_rate": float(
            false_negative["bounded_vectors_scored"] == 1
            and false_negative["exact_attempted"]
            and false_negative["hit_key"] == "q6"
        ),
        "false_negative_exact_recovery_rate": float(
            false_negative["recovered_from_bounded_miss"]
            and false_negative["final_mode"] == "exact"
        ),
        "false_negative_commit_once_rate": float(false_negative["commit_count"] == 1),
        "false_negative_answer_rate": float(false_negative["final_action"] == ANSWER),
        "true_miss_safe_rate": float(
            true_miss["hit_key"] is None
            and true_miss["commit_count"] == 0
            and true_miss["final_action"] == STOP_UNRESOLVED
        ),
        "wrong_schema_safe_rate": float(
            wrong_schema["hit_key"] is None
            and wrong_schema["commit_count"] == 0
            and wrong_schema["final_action"] == STOP_UNRESOLVED
        ),
        "exact_miss_zero_commit_rate": sum(row["commit_count"] == 0 for row in miss_controls) / len(miss_controls),
        "exact_miss_stop_unresolved_rate": sum(row["final_action"] == STOP_UNRESOLVED for row in miss_controls) / len(miss_controls),
        "provenance_validation_rate": sum(row["provenance_ok"] for row in rows) / len(rows),
        "case_count": len(rows),
    }


def run(*, protected_result_path: Path, c134_summary_path: Path, output_dir: Path):
    prior = json.loads(c134_summary_path.read_text(encoding="utf-8"))
    if (
        prior.get("experiment_id") != c134.EXPERIMENT_ID
        or prior.get("status") != "PASS"
        or not prior.get("summary", {}).get("retrieval_miss_semantics_gate_passed")
    ):
        raise RuntimeError("C135 requires accepted C134")
    if not torch.cuda.is_available():
        raise RuntimeError("C135 requires CUDA")

    before = _sha(protected_result_path)
    adapter = PersistedStructuralRetrievalAdapter(c133.CORPUS)
    output_dir.mkdir(parents=True, exist_ok=False)
    device = torch.device("cuda")
    torch.cuda.set_device(0)
    torch.set_num_threads(2)
    torch.set_float32_matmul_precision("highest")

    records = []
    for seed_index, seed in enumerate(SEEDS, start=1):
        print(f"[C135] seed {seed_index}/3 train start seed={seed}", flush=True)
        router, loss = c113._train_router(seed, device)
        print(f"[C135] seed {seed_index}/3 train done loss={loss:.8f}", flush=True)
        rows = _evaluate_seed(router, device, adapter, seed_index)
        m = _metrics(rows)
        m["accepted_c134_prerequisite_rate"] = 1.0
        deciding = [key for key in m if key.endswith("_rate")]
        m["gate_passed"] = all(m[key] == 1.0 for key in deciding)
        records.append({
            "seed": seed,
            "final_loss": loss,
            "metrics": m,
            "cases": rows,
            "validation_passed": bool(m["gate_passed"]),
        })
        print(
            f"[C135] seed {seed_index}/3 complete "
            f"false_negative={m['bounded_false_negative_detection_rate']:.6f} "
            f"recovery={m['false_negative_exact_recovery_rate']:.6f} "
            f"safe_miss={m['exact_miss_zero_commit_rate']:.6f} pass={m['gate_passed']}",
            flush=True,
        )

    after = _sha(protected_result_path)
    if before != after:
        raise RuntimeError("protected C37 result changed during C135")

    ms = [record["metrics"] for record in records]
    all_pass = all(record["validation_passed"] for record in records)
    keys = [key for key in ms[0] if key.endswith("_rate")]
    summary = {
        "fresh_seeds": list(SEEDS),
        "validation_base": 3,
        "bounded_scan_limit": SCAN_LIMIT,
        "bounded_probes": PROBES,
        "case_types": [case[0] for case in CASES],
        "case_count": len(CASES),
        "corpus_record_count": adapter.record_count,
        "corpus_sha256": adapter.source_sha256,
        "index_fingerprint": adapter.index_fingerprint,
        **{key: _stats([m[key] for m in ms]) for key in keys},
        "all_validation_passed": all_pass,
        "bounded_retrieval_exact_recovery_gate_passed": all_pass,
    }
    report = {
        "experiment_id": EXPERIMENT_ID,
        "stage": "V5-E-BOUNDED-RETRIEVAL-EXACT-RECOVERY",
        "status": "PASS" if all_pass else "FAIL",
        "summary": summary,
        "records": records,
        "C134_summary_sha256": _sha(c134_summary_path),
        "C37_result_sha256_before": before,
        "C37_result_sha256_after": after,
        "production_runtime_modified": True,
        "gate_e_candidate": False,
        "limitations": [
            "C135 uses a controlled deterministic LSH false-negative in the eight-record persisted corpus",
            "C135 validates exact escalation policy, not learned retrieval-budget selection",
            "C135 does not establish natural-language query formation or open-domain retrieval quality",
            "Exact fallback scans the full corpus and is therefore a correctness recovery path, not a scaling claim",
        ],
    }
    (output_dir / "summary.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    return report
