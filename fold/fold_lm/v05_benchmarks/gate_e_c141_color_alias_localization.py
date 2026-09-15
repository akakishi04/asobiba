"""C141: evaluation-only color alias intervention on replayed C140 heads.

The positional alias map is an oracle diagnostic derived from training rows.
It is never installed in production or used for training. A diagnostic PASS
is not model generalization, and does not supersede C140's negative result.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
import statistics
import subprocess
import time

import torch

EXPERIMENT_ID = "C141-v5e-color-alias-localization"
STAGE = "V5-E-COLOR-ALIAS-LOCALIZATION"
C140_ID = "C140-v5e-collision-free-multiseed-robustness"
SEEDS = tuple(range(20261601, 20261613))  # Replay, NOT fresh evidence.
MARGIN_ATOL = 1e-5
C37_SHA256 = "fd4a8da897bdaea9d103a252e30212c7ff842d23300d7c837333e146dee51931"
FIXTURE_SHA256 = "a52f8209703149407580f7e2965b61b78653030ee992af6d759865736741ca9e"
AUTHORITY_RATES = (
    "router_retrieve_rate", "provenance_validation_rate",
    "evidence_commit_once_rate", "post_commit_answer_rate",
    "collision_free_feature_rate", "c138_collision_control_rate",
    "raw_collision_free_baseline_not_perfect_rate", "dynamic_candidate_growth_rate",
    "accepted_c139_valid_negative_rate",
)
CASE_FIELDS = (
    "key", "split", "expected_address", "predicted_address", "initial_action",
    "hit_key", "expected_value", "retrieved_value", "provenance_ok",
    "commit_count", "final_action", "passed",
)


def _sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _training_color_map(rows: list[dict]) -> dict[str, str]:
    """Exploit the documented color-first fixture schema, training rows only."""
    mapping: dict[str, str] = {}
    for row in rows:
        if row["split"] != "TRAIN_COMBINATION":
            continue
        descriptor = row["descriptor"].split()
        if len(descriptor) != 3:
            raise ValueError("C141 requires color/shape/material descriptors")
        color = descriptor[0]
        for text in row["train"]:
            parts = text.split(maxsplit=1)
            if len(parts) != 2:
                raise ValueError("C141 training query lacks a color and context")
            alias = parts[0]
            if alias in mapping and mapping[alias] != color:
                raise ValueError(f"Ambiguous training color alias: {alias}")
            mapping[alias] = color
    if not mapping:
        raise ValueError("C141 training color map is empty")
    return mapping


def _canonical_color_rows(rows: list[dict], mapping: dict[str, str]) -> list[dict]:
    result = copy.deepcopy(rows)
    for row in result:
        color, context = row["validation"].split(maxsplit=1)
        if color not in mapping:
            raise ValueError(f"Uncovered validation color alias: {color}")
        # Neither the expected key nor this row's descriptor selects the color.
        row["validation"] = mapping[color] + " " + context
    return result


def _color_redundancy_audit(rows: list[dict]) -> dict:
    known = [row for row in rows if row["split"] == "TRAIN_COMBINATION"]
    pairs = [tuple(row["descriptor"].split()[1:]) for row in known]
    return {
        "training_rows": len(known),
        "distinct_training_shape_material_pairs": len(set(pairs)),
        "training_records_identifiable_without_color": len(set(pairs)) == len(known),
    }


def _validate_prior(data: dict) -> dict[int, dict]:
    """Bind to the accepted C140 result, not an arbitrary FAIL JSON."""
    s = data.get("summary", {})
    if (data.get("experiment_id") != C140_ID or data.get("status") != "FAIL"
            or s.get("collision_free_multiseed_robustness_gate_passed") is not False
            or s.get("fresh_seeds") != list(SEEDS)
            or s.get("full_seed_pass_count") != 8
            or s.get("known_combination_accuracy", {}).get("min") != 1.0
            or s.get("feature_dim") != 49
            or data.get("production_runtime_modified") is not False
            or data.get("gate_e_candidate") is not False):
        raise ValueError("C141 requires the accepted valid-negative C140 profile")
    for field in AUTHORITY_RATES:
        if s.get(field, {}).get("min") != 1.0:
            raise ValueError(f"Invalid C140 authority/control rate: {field}")
    for field in ("C37_result_sha256_before", "C37_result_sha256_after"):
        if str(data.get(field, "")).lower() != C37_SHA256:
            raise ValueError("C140 protected C37 identity mismatch")
    records = data.get("records")
    if not isinstance(records, list) or len(records) != len(SEEDS):
        raise ValueError("Full C140 records are required; console summary is insufficient")
    by_seed = {record["seed"]: record for record in records}
    if set(by_seed) != set(SEEDS):
        raise ValueError("Missing or duplicate C140 seed")
    errors = {}
    for seed, record in by_seed.items():
        cases = record.get("cases", [])
        margins = record.get("margins", [])
        if ([case.get("key") for case in cases] != [f"q{i}" for i in range(12)]
                or [row.get("key") for row in margins] != [f"q{i}" for i in range(12)]):
            raise ValueError("C140 case/margin order or coverage mismatch")
        for index, case in enumerate(cases):
            if (case.get("expected_address") != index
                    or case.get("provenance_ok") is not True
                    or case.get("commit_count") != 1
                    or case.get("initial_action") != 2 or case.get("final_action") != 0):
                raise ValueError("Invalid C140 case authority or expected address")
            correct = case.get("predicted_address") == index
            if case.get("passed") is not correct:
                raise ValueError("C140 pass flag contradicts the accepted selection outcome")
            if not correct:
                errors[(seed, case["key"])] = case["predicted_address"]
        for margin in margins:
            if not all(math.isfinite(float(margin[field])) for field in
                       ("expected_score", "best_other_score", "expected_margin")):
                raise ValueError("Non-finite C140 margin")
    expected_errors = {
        (20261602, "q10"): 2, (20261604, "q11"): 1,
        (20261606, "q11"): 1, (20261612, "q10"): 2,
    }
    if errors != expected_errors:
        raise ValueError("C140 error profile differs from the accepted log")
    return by_seed


def _check_replay(cases: list[dict], margins: list[dict], prior: dict) -> None:
    if len(cases) != len(prior["cases"]) or len(margins) != len(prior["margins"]):
        raise RuntimeError("C141 INVALID: baseline replay length mismatch")
    for actual, expected in zip(cases, prior["cases"], strict=True):
        if any(actual.get(field) != expected.get(field) for field in CASE_FIELDS):
            raise RuntimeError(f"C141 INVALID: baseline replay differs at {expected['key']}")
    for actual, expected in zip(margins, prior["margins"], strict=True):
        if any(actual[field] != expected[field] for field in
               ("key", "predicted_address", "best_other_address", "correct")):
            raise RuntimeError("C141 INVALID: baseline margin ranking differs")
        for field in ("expected_score", "best_other_score", "expected_margin"):
            value = float(actual[field])
            if not math.isfinite(value) or abs(value - float(expected[field])) > MARGIN_ATOL:
                raise RuntimeError(f"C141 INVALID: baseline {field} outside replay tolerance")


def _head_sha(head) -> str:
    digest = hashlib.sha256()
    for name, tensor in sorted(head.state_dict().items()):
        digest.update(name.encode())
        digest.update(str(tuple(tensor.shape)).encode())
        digest.update(str(tensor.dtype).encode())
        digest.update(tensor.detach().cpu().contiguous().numpy().tobytes())
    return digest.hexdigest()


def _pair_metrics(before: list[dict], after: list[dict]) -> dict:
    if len(before) != len(after) or not before:
        raise ValueError("Non-empty paired cases of equal length are required")
    if any(b["key"] != a["key"] for b, a in zip(before, after, strict=True)):
        raise ValueError("Paired case keys differ")
    failures = [i for i, case in enumerate(before) if not case["passed"]]
    successes = [i for i, case in enumerate(before) if case["passed"]]
    known = [case for case in after if case["split"] == "TRAIN_COMBINATION"]
    unseen = [case for case in after if case["split"] == "UNSEEN_COMBINATION"]
    return {
        "baseline_failure_count": len(failures),
        "rescued_failure_count": sum(after[i]["passed"] for i in failures),
        "baseline_success_count": len(successes),
        "preserved_success_count": sum(after[i]["passed"] for i in successes),
        "new_error_count": sum(not after[i]["passed"] for i in successes),
        "canonical_known_accuracy": sum(c["passed"] for c in known) / len(known),
        "canonical_unseen_accuracy": sum(c["passed"] for c in unseen) / len(unseen),
        "canonical_scenario_accuracy": sum(c["passed"] for c in after) / len(after),
    }


def _evaluate(router, head, rows, vocabulary, adapter, device, seed_index, arm, deps):
    c113, c137, c139, c140 = deps
    record_features = c139._collision_free_text_features(
        [row["descriptor"] for row in rows], vocabulary, device=device)
    values = c139._corpus_values()
    cases = []
    for index, row in enumerate(rows):
        initial = c113._predict(router, dependency=1, evidence_present=0,
                                observed_hidden=0, visible_mask=c140.VISIBLE_RETRIEVE, device=device)
        features = c139._collision_free_text_features([row["validation"]], vocabulary, device=device)
        with torch.inference_mode():
            predicted = int(head.select(features, record_features).item())
        structure = c140.address_to_structure(predicted, address_count=len(rows))
        evidence, stats = (adapter.retrieve(structure, c137.SEMANTICS, schema=c137.SCHEMA, exact=True)
                           if initial == c140.RETRIEVE else (None, {}))
        provenance = bool(evidence is not None and evidence.domain == "c137"
                          and evidence.schema == c137.SCHEMA
                          and evidence.operations == ("READ_EVIDENCE",)
                          and evidence.source_sha256 == adapter.source_sha256
                          and evidence.index_fingerprint == adapter.index_fingerprint
                          and stats.get("source_sha256") == adapter.source_sha256
                          and stats.get("index_fingerprint") == adapter.index_fingerprint)
        # Preserve C140's harness-level commit indicator; not a new crash-safety test.
        commits = int(evidence is not None and provenance)
        final = (c113._predict(router, dependency=1, evidence_present=1,
                              observed_hidden=evidence.evidence_value,
                              visible_mask=c140.VISIBLE_RETRIEVE, device=device) if commits else None)
        key = None if evidence is None else evidence.key
        value = None if evidence is None else evidence.evidence_value
        passed = bool(initial == c140.RETRIEVE and predicted == index and key == row["key"]
                      and provenance and commits == 1 and final == c140.ANSWER
                      and value == values[row["key"]] and stats.get("mode") == "exact"
                      and stats.get("vectors_scored") == adapter.record_count)
        if not (provenance and commits == 1 and initial == c140.RETRIEVE and final == c140.ANSWER
                and stats.get("mode") == "exact" and stats.get("vectors_scored") == 12):
            raise RuntimeError("C141 INVALID: retrieval/authority control failed")
        cases.append(dict(key=row["key"], split=row["split"], expected_address=index,
                          predicted_address=predicted, initial_action=initial, hit_key=key,
                          expected_value=values[row["key"]], retrieved_value=value,
                          provenance_ok=provenance, commit_count=commits, final_action=final,
                          passed=passed, query_text=row["validation"]))
        print(f"[C141] seed {seed_index}/12 arm={arm} case {index+1}/12 "
              f"key={row['key']} predicted={predicted} pass={passed} remaining={11-index}", flush=True)
    margins = c140._score_margins(head, rows, vocabulary, device)
    if any(case["predicted_address"] != margin["predicted_address"]
           for case, margin in zip(cases, margins, strict=True)):
        raise RuntimeError("C141 INVALID: batched/single-query ranking disagreement")
    if not all(math.isfinite(row[field]) for row in margins for field in
               ("expected_score", "best_other_score", "expected_margin")):
        raise RuntimeError("C141 INVALID: non-finite probe scores")
    return cases, margins


def run(*, protected_result_path: Path, protected_fixture_path: Path,
        c140_summary_path: Path, output_dir: Path) -> dict:
    # Lazy imports keep pure diagnostic helpers independently testable on CPU.
    from fold_lm.v05_benchmarks import gate_e_c113_stale_eligibility_preflight as c113
    from fold_lm.v05_benchmarks import gate_e_c137_content_addressed_corpus_growth as c137
    from fold_lm.v05_benchmarks import gate_e_c138_compositional_alias_generalization as c138
    from fold_lm.v05_benchmarks import gate_e_c139_hash_collision_diagnostic as c139
    from fold_lm.v05_benchmarks import gate_e_c140_collision_free_multiseed_robustness as c140
    from fold_lm.v05.retrieval_adapter import PersistedStructuralRetrievalAdapter

    prior_sha = _sha(c140_summary_path)
    prior = _validate_prior(json.loads(c140_summary_path.read_text(encoding="utf-8")))
    protected = {protected_result_path: C37_SHA256, protected_fixture_path: FIXTURE_SHA256}
    for path, expected in protected.items():
        if _sha(path) != expected:
            raise RuntimeError(f"Protected artifact mismatch: {path}")
    if not torch.cuda.is_available():
        raise RuntimeError("C141 paired replay requires the original CUDA environment")
    rows = c138._load_fixture()
    vocabulary = c139._training_vocabulary(rows)
    mapping = _training_color_map(rows)
    canonical = _canonical_color_rows(rows, mapping)
    if len(vocabulary) != 49 or c139._fixture_oov_count(canonical, vocabulary) != 0:
        raise RuntimeError("C141 vocabulary/OOV mismatch")
    input_paths = (c137.CORPUS, c138.QUERY_FIXTURE)
    input_hashes = {str(path): _sha(path) for path in input_paths}
    output_dir.mkdir(parents=True, exist_ok=False)
    device = torch.device("cuda")
    torch.cuda.set_device(0)
    torch.set_num_threads(2)
    torch.set_float32_matmul_precision("highest")
    adapter = PersistedStructuralRetrievalAdapter(c137.CORPUS)
    if adapter.record_count != 12:
        raise RuntimeError("C141 requires the unchanged 12-record corpus")
    started = time.perf_counter()
    records = []
    try:
        for seed_index, seed in enumerate(SEEDS, start=1):
            print(f"[C141] seed {seed_index}/12 REPLAY router train start seed={seed}", flush=True)
            router, router_loss = c113._train_router(seed, device)
            print(f"[C141] seed {seed_index}/12 router train done loss={router_loss:.8f}", flush=True)
            print(f"[C141] seed {seed_index}/12 exact C139 content-head train start", flush=True)
            head, content_loss = c139._train_content_head(seed, rows, vocabulary, device)
            print(f"[C141] seed {seed_index}/12 content-head train done loss={content_loss:.8f}", flush=True)
            frozen_sha = _head_sha(head)
            baseline, baseline_margins = _evaluate(router, head, rows, vocabulary, adapter, device,
                                                  seed_index, "BASELINE_REPLAY", (c113, c137, c139, c140))
            _check_replay(baseline, baseline_margins, prior[seed])
            print(f"[C141] seed {seed_index}/12 baseline_replay_match=True", flush=True)
            treated, treated_margins = _evaluate(router, head, canonical, vocabulary, adapter, device,
                                                seed_index, "CANONICAL_COLOR", (c113, c137, c139, c140))
            if _head_sha(head) != frozen_sha:
                raise RuntimeError("C141 INVALID: intervention mutated model weights")
            m = _pair_metrics(baseline, treated)
            m["canonical_positive_margin_rate"] = sum(r["expected_margin"] > 0 for r in treated_margins) / 12
            records.append(dict(seed=seed, seed_role="C140_REPLAY_NOT_FRESH",
                                router_final_loss=router_loss, content_head_final_loss=content_loss,
                                frozen_head_sha256=frozen_sha, baseline_cases=baseline,
                                baseline_margins=baseline_margins, canonical_color_cases=treated,
                                canonical_color_margins=treated_margins, metrics=m))
            print(f"[C141] seed {seed_index}/12 complete rescued={m['rescued_failure_count']}/"
                  f"{m['baseline_failure_count']} new_errors={m['new_error_count']} "
                  f"canonical_unseen={m['canonical_unseen_accuracy']:.6f} remaining_seeds={12-seed_index}", flush=True)
        for path, expected in protected.items():
            if _sha(path) != expected:
                raise RuntimeError(f"C141 INVALID: protected artifact changed: {path}")
        if _sha(c140_summary_path) != prior_sha or any(_sha(p) != input_hashes[str(p)] for p in input_paths):
            raise RuntimeError("C141 INVALID: prerequisite or input file mutated")
        totals = {key: sum(r["metrics"][key] for r in records) for key in
                  ("baseline_failure_count", "rescued_failure_count", "baseline_success_count",
                   "preserved_success_count", "new_error_count")}
        aggregate = {key: {"mean": statistics.mean(v), "min": min(v), "max": max(v)}
                     for key in ("canonical_known_accuracy", "canonical_unseen_accuracy",
                                 "canonical_scenario_accuracy", "canonical_positive_margin_rate")
                     for v in [[r["metrics"][key] for r in records]]}
        passed = (totals["baseline_failure_count"] == 4 and totals["rescued_failure_count"] == 4
                  and totals["baseline_success_count"] == 140 and totals["new_error_count"] == 0
                  and aggregate["canonical_positive_margin_rate"]["min"] == 1.0)
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
        report = dict(
            experiment_id=EXPERIMENT_ID, stage=STAGE, status="PASS" if passed else "FAIL",
            diagnostic_execution_valid=True, production_runtime_modified=False, gate_e_candidate=False,
            commit_sha=commit, C140_summary_sha256=prior_sha, input_sha256=input_hashes,
            C37_result_sha256_before=C37_SHA256, C37_result_sha256_after=_sha(protected_result_path),
            fixture_sha256_before=FIXTURE_SHA256, fixture_sha256_after=_sha(protected_fixture_path),
            environment={"torch": torch.__version__, "cuda": torch.version.cuda,
                         "device": torch.cuda.get_device_name(0), "precision": "float32/highest"},
            summary={"replay_seeds": list(SEEDS), "fresh_seed_count": 0,
                     "feature_dim": 49, "baseline_cases": 144, "intervention_cases": 144,
                     "baseline_replay_match_rate": 1.0, "frozen_weights_preserved_rate": 1.0,
                     "evaluation_oov_count": 0, "training_only_color_map": mapping,
                     **_color_redundancy_audit(rows), **totals, **aggregate,
                     "color_alias_localization_gate_passed": passed,
                     "wall_clock_seconds": time.perf_counter() - started}, records=records,
            limitations=[
                "Oracle, color-first training-fixture map; not a learned or production canonicalizer",
                "Canonical color creates intentional lexical overlap; rescue need not mean semantic reasoning",
                "C140 seeds are replayed; no fresh-seed generalization or production improvement claim",
                "Replay compares full discrete outcomes and score margins within absolute tolerance 1e-5, not saved weights",
                "A FAIL may mean partial rescue or new errors; inspect per-case metrics before attributing mechanisms",
                "Commit-once retains C140's harness indicator, not a new transactional durability test",
                "Gate E remains NOT PASSED regardless of this diagnostic result",
            ])
        (output_dir / "summary.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
        return report
    except Exception as exc:
        invalid = dict(experiment_id=EXPERIMENT_ID, status="INVALID", diagnostic_execution_valid=False,
                       error=str(exc), completed_seeds=len(records), records=records,
                       C140_summary_sha256=prior_sha, production_runtime_modified=False, gate_e_candidate=False)
        (output_dir / "invalid.json").write_text(json.dumps(invalid, indent=2, allow_nan=False), encoding="utf-8")
        raise
