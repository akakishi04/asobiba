from __future__ import annotations

import hashlib
import json
from pathlib import Path
import statistics

import torch

from fold_lm.v05.retrieval_adapter import PersistedStructuralRetrievalAdapter
from fold_lm.v05.retrieval_query import address_to_structure
from fold_lm.v05_benchmarks import gate_e_c113_stale_eligibility_preflight as c113
from fold_lm.v05_benchmarks import gate_e_c137_content_addressed_corpus_growth as c137
from fold_lm.v05_benchmarks import gate_e_c138_compositional_alias_generalization as c138
from fold_lm.v05_benchmarks import gate_e_c139_hash_collision_diagnostic as c139

EXPERIMENT_ID = "C140-v5e-collision-free-multiseed-robustness"
SEEDS = tuple(range(20261601, 20261613))
ANSWER = c139.ANSWER
RETRIEVE = c139.RETRIEVE
VISIBLE_RETRIEVE = c139.VISIBLE_RETRIEVE


def _sha(path: Path) -> str:
    return hashlib.file_digest(path.open("rb"), "sha256").hexdigest()


def _stats(values):
    return {
        "mean": statistics.mean(values),
        "median": statistics.median(values),
        "min": min(values),
        "max": max(values),
    }


def _expected_margin_from_scores(row_scores: torch.Tensor, expected_index: int) -> dict:
    if row_scores.ndim != 1:
        raise ValueError("row_scores must be one-dimensional")
    if not 0 <= expected_index < row_scores.numel():
        raise ValueError("expected_index out of range")
    predicted = int(row_scores.argmax().item())
    expected_score = float(row_scores[expected_index].item())
    competitors = row_scores.clone()
    competitors[expected_index] = float("-inf")
    best_other_score_t, best_other_index_t = competitors.max(dim=0)
    best_other_score = float(best_other_score_t.item())
    best_other_index = int(best_other_index_t.item())
    return {
        "predicted_address": predicted,
        "expected_score": expected_score,
        "best_other_score": best_other_score,
        "best_other_address": best_other_index,
        "expected_margin": expected_score - best_other_score,
        "correct": predicted == expected_index,
    }


def _score_margins(head, rows, vocabulary, device: torch.device) -> list[dict]:
    record_features = c139._collision_free_text_features(
        [row["descriptor"] for row in rows], vocabulary, device=device
    )
    query_features = c139._collision_free_text_features(
        [row["validation"] for row in rows], vocabulary, device=device
    )
    with torch.inference_mode():
        scores = head.scores(query_features, record_features)
    result = []
    for index, row in enumerate(rows):
        margin = _expected_margin_from_scores(scores[index], index)
        result.append(
            {
                "key": row["key"],
                "split": row["split"],
                "expected_address": index,
                **margin,
            }
        )
    return result


def _evaluate_seed(router, head, device, adapter, rows, vocabulary, seed_index: int):
    values = c139._corpus_values()
    record_features = c139._collision_free_text_features(
        [row["descriptor"] for row in rows], vocabulary, device=device
    )
    cases = []
    total = len(rows)
    seed_total = len(SEEDS)

    for case_index, row in enumerate(rows, start=1):
        expected_address = case_index - 1
        expected_key = row["key"]
        initial = c113._predict(
            router,
            dependency=1,
            evidence_present=0,
            observed_hidden=0,
            visible_mask=VISIBLE_RETRIEVE,
            device=device,
        )
        query_features = c139._collision_free_text_features(
            [row["validation"]], vocabulary, device=device
        )
        with torch.inference_mode():
            predicted_address = int(head.select(query_features, record_features).item())
        structure = address_to_structure(predicted_address, address_count=len(rows))

        evidence = None
        stats = {}
        if initial == RETRIEVE:
            evidence, stats = adapter.retrieve(
                structure,
                c137.SEMANTICS,
                schema=c137.SCHEMA,
                exact=True,
            )

        provenance_ok = bool(
            evidence is not None
            and evidence.domain == "c137"
            and evidence.schema == c137.SCHEMA
            and evidence.operations == ("READ_EVIDENCE",)
            and evidence.source_sha256 == adapter.source_sha256
            and evidence.index_fingerprint == adapter.index_fingerprint
            and stats.get("source_sha256") == adapter.source_sha256
            and stats.get("index_fingerprint") == adapter.index_fingerprint
        )
        commit_count = int(evidence is not None and provenance_ok)
        final_action = None
        if commit_count:
            final_action = c113._predict(
                router,
                dependency=1,
                evidence_present=1,
                observed_hidden=evidence.evidence_value,
                visible_mask=VISIBLE_RETRIEVE,
                device=device,
            )

        hit_key = None if evidence is None else evidence.key
        retrieved_value = None if evidence is None else evidence.evidence_value
        expected_value = values[expected_key]
        passed = bool(
            initial == RETRIEVE
            and predicted_address == expected_address
            and hit_key == expected_key
            and provenance_ok
            and commit_count == 1
            and final_action == ANSWER
            and retrieved_value == expected_value
            and stats.get("mode") == "exact"
            and stats.get("vectors_scored") == adapter.record_count
        )
        cases.append(
            {
                "key": expected_key,
                "split": row["split"],
                "expected_address": expected_address,
                "predicted_address": predicted_address,
                "initial_action": initial,
                "hit_key": hit_key,
                "expected_value": expected_value,
                "retrieved_value": retrieved_value,
                "provenance_ok": provenance_ok,
                "commit_count": commit_count,
                "final_action": final_action,
                "passed": passed,
            }
        )
        print(
            f"[C140] seed {seed_index}/{seed_total} case {case_index}/{total} "
            f"split={row['split']} key={expected_key} predicted={predicted_address} "
            f"pass={passed} remaining={total-case_index}",
            flush=True,
        )
    return cases


def _metrics(cases, margins, adapter, *, oov_count: int, collision_count: int, raw_unseen: float):
    base = c139._metrics(
        cases,
        adapter,
        oov_count=oov_count,
        collision_count=collision_count,
        raw_unseen=raw_unseen,
    )
    known_margins = [row["expected_margin"] for row in margins if row["split"] == "TRAIN_COMBINATION"]
    unseen_margins = [row["expected_margin"] for row in margins if row["split"] == "UNSEEN_COMBINATION"]
    base.update(
        {
            "known_positive_expected_margin_rate": sum(value > 0.0 for value in known_margins) / len(known_margins),
            "unseen_positive_expected_margin_rate": sum(value > 0.0 for value in unseen_margins) / len(unseen_margins),
            "known_min_expected_margin": min(known_margins),
            "unseen_min_expected_margin": min(unseen_margins),
            "unseen_mean_expected_margin": statistics.mean(unseen_margins),
        }
    )
    return base


def run(*, protected_result_path: Path, c139_summary_path: Path, output_dir: Path):
    prior = json.loads(c139_summary_path.read_text(encoding="utf-8"))
    prior_summary = prior.get("summary", {})
    unseen_prior = prior_summary.get("unseen_combination_accuracy", {})
    if (
        prior.get("experiment_id") != c139.EXPERIMENT_ID
        or prior.get("status") != "FAIL"
        or bool(prior_summary.get("hash_collision_composition_diagnostic_gate_passed"))
        or prior_summary.get("known_combination_accuracy", {}).get("min") != 1.0
        or prior_summary.get("collision_free_feature_rate", {}).get("min") != 1.0
        or prior_summary.get("accepted_c138_valid_negative_rate", {}).get("min") != 1.0
        or unseen_prior.get("max") != 1.0
        or not (float(unseen_prior.get("min", 1.0)) < 1.0)
    ):
        raise RuntimeError("C140 requires the accepted mixed-outcome valid-negative C139 summary")
    if not torch.cuda.is_available():
        raise RuntimeError("C140 requires CUDA")

    before = _sha(protected_result_path)
    rows = c138._load_fixture()
    vocabulary = c139._training_vocabulary(rows)
    oov_count = c139._fixture_oov_count(rows, vocabulary)
    collisions = c139._hash_collision_buckets(rows)
    if oov_count != 0:
        raise RuntimeError(f"C140 collision-free diagnostic has OOV tokens: {oov_count}")

    adapter = PersistedStructuralRetrievalAdapter(c137.CORPUS)
    output_dir.mkdir(parents=True, exist_ok=False)
    device = torch.device("cuda")
    torch.cuda.set_device(0)
    torch.set_num_threads(2)
    torch.set_float32_matmul_precision("highest")

    print(
        f"[C140] exact C139 configuration fresh_seeds={len(SEEDS)} "
        f"vocabulary={len(vocabulary)} oov={oov_count}",
        flush=True,
    )

    records = []
    for seed_index, seed in enumerate(SEEDS, start=1):
        print(f"[C140] seed {seed_index}/{len(SEEDS)} router train start seed={seed}", flush=True)
        router, router_loss = c113._train_router(seed, device)
        print(f"[C140] seed {seed_index}/{len(SEEDS)} router train done loss={router_loss:.8f}", flush=True)
        print(
            f"[C140] seed {seed_index}/{len(SEEDS)} content-head train start "
            f"encoding=collision_free_bow dim={len(vocabulary)}",
            flush=True,
        )
        head, content_loss = c139._train_content_head(seed, rows, vocabulary, device)
        print(
            f"[C140] seed {seed_index}/{len(SEEDS)} content-head train done loss={content_loss:.8f}",
            flush=True,
        )
        raw_unseen = c139._raw_unseen_accuracy(rows, vocabulary, device)
        cases = _evaluate_seed(router, head, device, adapter, rows, vocabulary, seed_index)
        margins = _score_margins(head, rows, vocabulary, device)
        metrics = _metrics(
            cases,
            margins,
            adapter,
            oov_count=oov_count,
            collision_count=len(collisions),
            raw_unseen=raw_unseen,
        )
        metrics["accepted_c139_valid_negative_rate"] = 1.0
        deciding = [key for key in metrics if key.endswith("_rate") or key.endswith("_accuracy")]
        gate_passed = bool(
            all(metrics[key] == 1.0 for key in deciding)
            and metrics["unseen_min_expected_margin"] > 0.0
        )
        records.append(
            {
                "seed": seed,
                "router_final_loss": router_loss,
                "content_head_final_loss": content_loss,
                "raw_collision_free_unseen_accuracy": raw_unseen,
                "metrics": metrics,
                "margins": margins,
                "cases": cases,
                "validation_passed": gate_passed,
            }
        )
        print(
            f"[C140] seed {seed_index}/{len(SEEDS)} complete "
            f"known={metrics['known_combination_accuracy']:.6f} "
            f"unseen={metrics['unseen_combination_accuracy']:.6f} "
            f"unseen_min_margin={metrics['unseen_min_expected_margin']:.8f} "
            f"pass={gate_passed}",
            flush=True,
        )

    metric_keys = [
        "scenario_pass_rate",
        "router_retrieve_rate",
        "known_combination_accuracy",
        "unseen_combination_accuracy",
        "unseen_retrieval_key_accuracy",
        "overall_retrieval_key_accuracy",
        "provenance_validation_rate",
        "evidence_commit_once_rate",
        "post_commit_answer_rate",
        "final_evidence_accuracy",
        "collision_free_feature_rate",
        "c138_collision_control_rate",
        "raw_collision_free_baseline_not_perfect_rate",
        "dynamic_candidate_growth_rate",
        "known_positive_expected_margin_rate",
        "unseen_positive_expected_margin_rate",
        "accepted_c139_valid_negative_rate",
    ]
    aggregate = {key: _stats([record["metrics"][key] for record in records]) for key in metric_keys}
    aggregate["unseen_min_expected_margin"] = _stats(
        [record["metrics"]["unseen_min_expected_margin"] for record in records]
    )
    aggregate["unseen_mean_expected_margin"] = _stats(
        [record["metrics"]["unseen_mean_expected_margin"] for record in records]
    )
    aggregate["full_seed_pass_count"] = sum(record["validation_passed"] for record in records)
    aggregate["full_seed_pass_rate"] = aggregate["full_seed_pass_count"] / len(records)

    all_passed = bool(aggregate["full_seed_pass_count"] == len(SEEDS))
    after = _sha(protected_result_path)
    report = {
        "experiment_id": EXPERIMENT_ID,
        "stage": "V5-E-COLLISION-FREE-MULTISEED-ROBUSTNESS",
        "status": "PASS" if all_passed else "FAIL",
        "summary": {
            "fresh_seeds": list(SEEDS),
            "encoding": "collision_free_training_vocabulary_bow",
            "feature_dim": len(vocabulary),
            "hidden_dim": c138.HIDDEN_DIM,
            "residual_scale": c138.RESIDUAL_SCALE,
            "training_candidate_count": 8,
            "evaluation_candidate_count": 12,
            "unseen_combination_count": 4,
            **aggregate,
            "all_validation_passed": all_passed,
            "collision_free_multiseed_robustness_gate_passed": all_passed,
        },
        "records": records,
        "C139_summary_sha256": _sha(c139_summary_path),
        "C37_result_sha256_before": before,
        "C37_result_sha256_after": after,
        "production_runtime_modified": False,
        "gate_e_candidate": False,
        "limitations": [
            "C140 is a fresh-seed robustness replication of the C139 collision-free diagnostic, not a production encoder proposal",
            "C140 does not change head width, objective, train steps, pooling, or retrieval semantics",
            "A full pass establishes robustness only on the controlled C138/C139 recombination fixture",
            "A failure establishes initialization/training sensitivity under the unchanged C139 configuration but does not by itself identify the optimization mechanism",
        ],
    }
    (output_dir / "summary.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    return report
