"""C143: frozen C142 heads, exhaustive in-vocabulary ranking audit.

This is NOT a new end-to-end retrieval/commit experiment. The evaluator
constructs labeled test queries from the training fixture's factor schema;
only raw text features and candidate descriptors enter the frozen scorer.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import itertools
import json
import math
from pathlib import Path
import re
import subprocess
import time

import torch

from fold_lm.v05.retrieval_content import SharedRetrievalContentHead

EXPERIMENT_ID = "C143-v5e-frozen-factorial-ranking-audit"
STAGE = "V5-E-FROZEN-FACTORIAL-RANKING-AUDIT"
C142_ID = "C142-v5e-training-only-color-alignment"
C142_COMMIT = "680ad7b4063e284504a36e0ded1c05a781d467a3"
C141_SHA = "1a3ded18c9066cfbfc7ab4a60839058ced82120abc3036258dad9170fc7deadc"
C37_SHA = "fd4a8da897bdaea9d103a252e30212c7ff842d23300d7c837333e146dee51931"
FIXTURE_SHA = "a52f8209703149407580f7e2965b61b78653030ee992af6d759865736741ca9e"
QUERIES_SHA = "9235f8af27ba7c4c8b0b01d6243f3970b0013358f92a5947aa245a7ac2981aa2"
CORPUS_SHA = "48be60a0babc0692deb19431a911ef6cbea9ded186238ef5ae1ac305531401f0"
SEEDS = tuple(range(20261621, 20261633))  # Stored C142 heads, NOT fresh seeds.
ARMS = ("BASELINE", "COLOR_AUX")
CONFIG = dict(feature_dim=49, hidden_dim=64, residual_scale=1.0)
REPLAY_ATOL = 1e-5
TOKEN_RE = re.compile(r"[a-z0-9]+")


def _sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _json_sha(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def _head_sha(head) -> str:
    digest = hashlib.sha256()
    for name, tensor in sorted(head.state_dict().items()):
        digest.update(name.encode())
        digest.update(str(tuple(tensor.shape)).encode())
        digest.update(str(tensor.dtype).encode())
        digest.update(tensor.detach().cpu().contiguous().numpy().tobytes())
    return digest.hexdigest()


def _build_suite(rows: list[dict]) -> dict:
    """No model access. Derive factor aliases solely from the training rows."""
    tables = [{}, {}, {}]
    reverse = [{}, {}, {}]
    train_pairs = set()
    for row in rows:
        if row["split"] != "TRAIN_COMBINATION":
            continue
        canonical = row["descriptor"].split()
        if len(canonical) != 3:
            raise ValueError("Expected color/shape/material descriptor")
        for text in row["train"]:
            aliases = text.split()
            if len(aliases) != 3:
                raise ValueError("Expected three whitespace-separated alias fields")
            train_pairs.add((text, row["descriptor"]))
            for axis, (alias, value) in enumerate(zip(aliases, canonical, strict=True)):
                if alias in reverse[axis] and reverse[axis][alias] != value:
                    raise ValueError("Ambiguous training factor alias")
                reverse[axis][alias] = value
                tables[axis].setdefault(value, set()).add(alias)
    if any(len(table) != 4 or any(len(aliases) != 3 for aliases in table.values()) for table in tables):
        raise ValueError("C143 requires four values per factor, three aliases per value")
    universe = {" ".join(p) for p in itertools.product(*(sorted(t) for t in tables))}
    old = [r["descriptor"] for r in rows]
    if (len(rows) != 12 or len(set(old)) != 12 or not set(old) <= universe
            or Counter(r["split"] for r in rows) != {"TRAIN_COMBINATION": 8, "UNSEEN_COMBINATION": 4}):
        raise ValueError("Original 8+4 combination profile mismatch")
    descriptors = old + sorted(universe - set(old))  # Keep old candidate identities 0..11.
    known = {r["descriptor"] for r in rows if r["split"] == "TRAIN_COMBINATION"}
    original = {(r["validation"], r["descriptor"]) for r in rows}
    queries = []
    for address, descriptor in enumerate(descriptors):
        factors = descriptor.split()
        bucket = ("TRAIN_COMBINATION" if descriptor in known else
                  "PRIOR_HELDOUT_COMBINATION" if descriptor in set(old) else "NEW_COMBINATION")
        for variant, aliases in enumerate(itertools.product(*(sorted(tables[i][v]) for i, v in enumerate(factors)))):
            text = " ".join(aliases)
            if set(TOKEN_RE.findall(text.lower())) & set(TOKEN_RE.findall(descriptor.lower())):
                raise ValueError("Generated query/target descriptor lexical overlap")
            queries.append(dict(case_id=f"{address:02d}-{variant:02d}", text=text,
                                expected_address=address, bucket=bucket,
                                original_training_query=(text, descriptor) in train_pairs,
                                original_validation_query=(text, descriptor) in original))
    if len({q["text"] for q in queries}) != 1728 or sum(q["original_validation_query"] for q in queries) != 12:
        raise ValueError("Generated query uniqueness/original-query coverage mismatch")
    return dict(schema_version=1, descriptors=descriptors, queries=queries,
                factor_aliases=[{v: sorted(a) for v, a in sorted(t.items())} for t in tables],
                candidate_count=64, query_count=1728, new_combination_count=52,
                variants_per_combination=27, training_only_query_generator=True)


def _validate_prior(data: dict, rows: list[dict]) -> list[dict]:
    s = data.get("summary", {})
    if (data.get("experiment_id") != C142_ID or data.get("status") != "PASS"
            or data.get("diagnostic_execution_valid") is not True or data.get("commit_sha") != C142_COMMIT
            or data.get("production_runtime_modified") is not False or data.get("gate_e_candidate") is not False
            or data.get("C141_summary_sha256") != C141_SHA or s.get("fresh_seeds") != list(SEEDS)
            or s.get("color_alignment_gate_passed") is not True or s.get("inference_oracle_used") is not False):
        raise ValueError("Accepted C142 identity/gate mismatch")
    expected = dict(unique_fresh_seed_count=12, trained_heads=24, **CONFIG, train_steps=600,
                    auxiliary_weight=1.0, baseline_cases=144, treatment_cases=144,
                    baseline_failure_count=9, rescued_failure_count=9, baseline_success_count=135,
                    preserved_success_count=135, new_error_count=0, evaluation_oov_count=0,
                    zero_paired_lexical_overlap_rate=1.0, paired_initial_weights_equal_rate=1.0,
                    evaluation_weights_preserved_rate=1.0)
    if any(s.get(k) != v for k, v in expected.items()):
        raise ValueError("Accepted C142 configuration/count profile mismatch")
    for prefix, value in (("C37_result", C37_SHA), ("fixture", FIXTURE_SHA)):
        if any(data.get(f"{prefix}_sha256_{suffix}") != value for suffix in ("before", "after")):
            raise ValueError("C142 protected artifact identity mismatch")
    records = data.get("records")
    if not isinstance(records, list) or [r.get("seed") for r in records] != list(SEEDS):
        raise ValueError("Full ordered C142 records required, not console-only report")
    errors = {}
    for record in records:
        for arm in ARMS:
            entry = record["arms"][arm]
            cases = entry["cases"]
            if len(cases) != 12 or entry["training"]["optimizer_steps"] != 600:
                raise ValueError("C142 case count or training-step mismatch")
            if not re.fullmatch(r"[0-9a-f]{64}", entry["final_head_sha256"]):
                raise ValueError("Missing C142 head fingerprint")
            for i, (case, row) in enumerate(zip(cases, rows, strict=True)):
                if (case["seed"] != record["seed"] or case["key"] != row["key"]
                        or case["query_text"] != row["validation"] or case["expected_address"] != i
                        or case["split"] != row["split"] or case["provenance_ok"] is not True
                        or case["initial_action"] != 2 or case["final_action"] != 0 or case["commit_count"] != 1):
                    raise ValueError("C142 case identity/authority mismatch")
                if type(case["predicted_address"]) is not int or not 0 <= case["predicted_address"] < 12:
                    raise ValueError("C142 prediction outside catalog")
                correct = case["predicted_address"] == i
                if case["passed"] is not correct:
                    raise ValueError("C142 inconsistent pass flag")
                if not all(math.isfinite(float(case[k])) for k in ("expected_score", "best_other_score", "expected_margin")):
                    raise ValueError("Nonfinite C142 score")
                if arm == "COLOR_AUX" and (not correct or case["expected_margin"] <= 0):
                    raise ValueError("C142 treatment was not successful")
                if arm == "BASELINE" and not correct:
                    errors[(record["seed"], row["key"])] = case["predicted_address"]
        if record["arms"]["BASELINE"]["initial_head_sha256"] != record["arms"]["COLOR_AUX"]["initial_head_sha256"]:
            raise ValueError("C142 paired initial fingerprints differ")
    accepted_errors = {(20261622, "q9"): 2, (20261623, "q11"): 1, (20261625, "q10"): 2,
                       (20261628, "q11"): 1, (20261629, "q10"): 2, (20261629, "q11"): 1,
                       (20261631, "q10"): 2, (20261631, "q11"): 1, (20261632, "q11"): 1}
    if errors != accepted_errors:
        raise ValueError("C142 error profile differs from accepted user log")
    return records


def _load_head(prior_dir: Path, seed: int, arm: str, entry: dict, vocabulary: tuple[str, ...], device):
    # Never follow arbitrary paths from a JSON report.
    name = f"seed-{seed}-{arm.lower()}.pt"
    metadata = entry["checkpoint"]
    if metadata["path"].replace("\\", "/").rsplit("/", 1)[-1] != name:
        raise ValueError("Checkpoint filename mismatch")
    path = prior_dir / name
    if path.resolve().parent != prior_dir.resolve():
        raise ValueError("Checkpoint must be inside the C142 run directory")
    if _sha(path) != metadata["sha256"] or path.stat().st_size != metadata["serialized_bytes"]:
        raise ValueError("Checkpoint bytes/hash mismatch")
    payload = torch.load(path, map_location="cpu", weights_only=True)
    if payload.get("config") != CONFIG or tuple(payload.get("vocabulary", ())) != vocabulary:
        raise ValueError("Checkpoint config/vocabulary mismatch")
    head = SharedRetrievalContentHead(**CONFIG)
    head.load_state_dict(payload["state_dict"], strict=True)
    if _head_sha(head) != entry["final_head_sha256"]:
        raise ValueError("Checkpoint tensor fingerprint mismatch")
    head.to(device).eval().requires_grad_(False)
    return head, path


def _score(head, queries, descriptors, expected: list[int]) -> list[dict]:
    with torch.inference_mode():
        scores = head.scores(queries, descriptors)
    if scores.shape != (len(expected), len(descriptors)) or not torch.isfinite(scores).all():
        raise RuntimeError("Invalid candidate score matrix")
    labels = torch.tensor(expected, dtype=torch.long, device=scores.device)
    if (labels < 0).any() or (labels >= scores.shape[1]).any() or scores.shape[1] < 2:
        raise ValueError("Expected label outside candidate set")
    selected = scores.argmax(-1)
    correct_scores = scores[torch.arange(len(labels), device=scores.device), labels]
    rivals = scores.clone()
    rivals[torch.arange(len(labels), device=scores.device), labels] = -torch.inf
    rival_scores, rival_indices = rivals.max(-1)
    values = zip(selected.tolist(), labels.tolist(), correct_scores.tolist(),
                 rival_indices.tolist(), rival_scores.tolist(), strict=True)
    return [dict(predicted_address=p, correct=(p == e), expected_score=s,
                 best_other_address=r, best_other_score=t, expected_margin=s-t)
            for p, e, s, r, t in values]


def _check_replay(actual: list[dict], reference: list[dict]) -> None:
    if len(actual) != len(reference):
        raise RuntimeError("Original-12 replay count mismatch")
    for a, b in zip(actual, reference, strict=True):
        if any(a[k] != b[k] for k in ("predicted_address", "best_other_address")) or a["correct"] != b["passed"]:
            raise RuntimeError("Original-12 checkpoint replay prediction mismatch")
        if any(not math.isfinite(a[k]) or abs(a[k]-b[k]) > REPLAY_ATOL
               for k in ("expected_score", "best_other_score", "expected_margin")):
            raise RuntimeError("Original-12 checkpoint replay score drift")


def _metrics(results: list[dict]) -> dict:
    if not results:
        raise ValueError("Empty evaluation group")
    return dict(case_count=len(results), correct_count=sum(r["correct"] for r in results),
                accuracy=sum(r["correct"] for r in results)/len(results),
                positive_margin_count=sum(r["expected_margin"] > 0 for r in results),
                min_expected_margin=min(r["expected_margin"] for r in results))


def _passed(results: list[dict]) -> bool:
    return bool(results) and all(r["correct"] and math.isfinite(r["expected_margin"])
                                and r["expected_margin"] > 0 for r in results)


def _group_metrics(suite: dict, results: list[dict]) -> dict:
    if len(results) != len(suite["queries"]):
        raise ValueError("Suite/result count mismatch")
    groups = {"ALL": _metrics(results)}
    for group in ("TRAIN_COMBINATION", "PRIOR_HELDOUT_COMBINATION", "NEW_COMBINATION"):
        groups[group] = _metrics([r for q, r in zip(suite["queries"], results, strict=True) if q["bucket"] == group])
    groups["ORIGINAL_VALIDATION_IN_64"] = _metrics(
        [r for q, r in zip(suite["queries"], results, strict=True) if q["original_validation_query"]])
    return groups


def run(*, c142_summary_path: Path, output_dir: Path, protected_result_path: Path,
        protected_fixture_path: Path) -> dict:
    # Use the original feature implementation; no import-time benchmark or training.
    from fold_lm.v05_benchmarks import gate_e_c139_hash_collision_diagnostic as c139
    fixture = Path(__file__).parent / "fixtures" / "c138_compositional_alias_queries.json"
    corpus = Path(__file__).parent / "fixtures" / "c137_content_records.json"
    output_dir.mkdir(parents=True, exist_ok=False)
    completed = []
    try:
        rows = json.loads(fixture.read_text(encoding="utf-8"))["queries"]
        data = json.loads(c142_summary_path.read_text(encoding="utf-8"))
        prior_records = _validate_prior(data, rows)
        protected = {c142_summary_path: _sha(c142_summary_path), protected_result_path: C37_SHA,
                     protected_fixture_path: FIXTURE_SHA, fixture: QUERIES_SHA, corpus: CORPUS_SHA}
        def check_files():
            for path, expected_hash in protected.items():
                if _sha(path) != expected_hash:
                    raise RuntimeError(f"Input/checkpoint/protected hash mismatch: {path}")
        check_files()
        # Freeze the complete test manifest BEFORE loading or scoring any head.
        suite = _build_suite(rows)
        suite_sha = _json_sha(suite)
        manifest = output_dir / "evaluation-manifest.json"
        manifest.write_text(json.dumps(suite, indent=2, allow_nan=False), encoding="utf-8")
        protected[manifest] = _sha(manifest)
        vocabulary = c139._training_vocabulary(rows)
        if len(vocabulary) != 49 or c139._fixture_oov_count(rows, vocabulary):
            raise RuntimeError("Training vocabulary/OOV mismatch")
        if not torch.cuda.is_available():
            raise RuntimeError("C143 formal checkpoint replay requires CUDA")
        device = torch.device("cuda")
        torch.cuda.set_device(0)
        torch.set_num_threads(2)
        torch.set_float32_matmul_precision("highest")
        def features(texts):
            return c139._collision_free_text_features(texts, vocabulary, device=device)
        query_features = features([q["text"] for q in suite["queries"]])
        descriptor_features = features(suite["descriptors"])
        old_queries = features([r["validation"] for r in rows])
        old_descriptors = features([r["descriptor"] for r in rows])
        expected = [q["expected_address"] for q in suite["queries"]]
        started = time.perf_counter()
        for seed_index, record in enumerate(prior_records, 1):
            arms = {}
            for arm in ARMS:
                entry = record["arms"][arm]
                print(f"[C143] model {seed_index}/12 arm={arm} checkpoint load seed={record['seed']}", flush=True)
                head, path = _load_head(c142_summary_path.parent, record["seed"], arm, entry, vocabulary, device)
                protected[path] = entry["checkpoint"]["sha256"]
                frozen = _head_sha(head)
                replay = _score(head, old_queries, old_descriptors, list(range(12)))
                _check_replay(replay, entry["cases"])
                print(f"[C143] model {seed_index}/12 arm={arm} original12_replay_match=True", flush=True)
                results = []
                # Actual bounded scoring batches, not simulated progress after a full run.
                for start in range(0, 1728, 216):
                    stop = start + 216
                    results.extend(_score(head, query_features[start:stop], descriptor_features, expected[start:stop]))
                    good = sum(r["correct"] for r in results)
                    print(f"[C143] model {seed_index}/12 arm={arm} audited={stop}/1728 "
                          f"correct={good} remaining={1728-stop}", flush=True)
                if _head_sha(head) != frozen or _json_sha(suite) != suite_sha:
                    raise RuntimeError("Frozen model or evaluation suite mutated")
                arms[arm] = dict(checkpoint_sha256=entry["checkpoint"]["sha256"], frozen_head_sha256=frozen,
                                 original12_replay=replay, metrics=_group_metrics(suite, results), results=results)
                del head
            baseline = arms["BASELINE"]["results"]
            treatment = arms["COLOR_AUX"]["results"]
            paired = dict(rescued_errors=sum(not b["correct"] and a["correct"] for b, a in zip(baseline, treatment)),
                          new_errors=sum(b["correct"] and not a["correct"] for b, a in zip(baseline, treatment)))
            completed.append(dict(seed=record["seed"], arms=arms, paired=paired))
            print(f"[C143] model {seed_index}/12 complete baseline={arms['BASELINE']['metrics']['ALL']['accuracy']:.6f} "
                  f"aux={arms['COLOR_AUX']['metrics']['ALL']['accuracy']:.6f} remaining_models={12-seed_index}", flush=True)
        check_files()
        all_by_arm = {arm: [x for record in completed for x in record["arms"][arm]["results"]] for arm in ARMS}
        summary_arms = {}
        for arm in ARMS:
            summary_arms[arm] = {"ALL": _metrics(all_by_arm[arm]),
                                 "full_model_pass_count": sum(_passed(r["arms"][arm]["results"]) for r in completed)}
            for group in ("TRAIN_COMBINATION", "PRIOR_HELDOUT_COMBINATION", "NEW_COMBINATION", "ORIGINAL_VALIDATION_IN_64"):
                groups = [r["arms"][arm]["metrics"][group] for r in completed]
                count = sum(g["case_count"] for g in groups)
                correct = sum(g["correct_count"] for g in groups)
                summary_arms[arm][group] = dict(case_count=count, correct_count=correct, accuracy=correct/count,
                                                min_expected_margin=min(g["min_expected_margin"] for g in groups))
        passed = _passed(all_by_arm["COLOR_AUX"])
        report = dict(experiment_id=EXPERIMENT_ID, stage=STAGE, status="PASS" if passed else "FAIL",
                      diagnostic_execution_valid=True, production_runtime_modified=False, gate_e_candidate=False,
                      commit_sha=subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
                      C142_summary_sha256=protected[c142_summary_path], evaluation_manifest_sha256=protected[manifest],
                      input_sha256={str(p): h for p, h in protected.items()},
                      environment=dict(torch=str(torch.__version__), cuda=torch.version.cuda,
                                       device=torch.cuda.get_device_name(0), precision="float32/highest"),
                      summary=dict(source_seeds=list(SEEDS), fresh_seed_count=0, additional_training_steps=0,
                                   reused_checkpoint_count=24, old_candidate_count=12, candidate_count=64,
                                   training_combinations=8, previously_evaluated_heldout_combinations=4,
                                   new_combinations=52, aliases_per_factor_value=3, queries_per_combination=27,
                                   queries_per_model=1728, total_ranking_cases=41472, original12_replay_cases=288,
                                   original12_replay_match_rate=1.0, frozen_weights_preserved_rate=1.0,
                                   evaluation_oov_count=0, zero_paired_lexical_overlap_rate=1.0,
                                   inference_oracle_used=False, runtime_path_exercised=False,
                                   arms=summary_arms, paired={k: sum(r["paired"][k] for r in completed)
                                                           for k in ("rescued_errors", "new_errors")},
                                   frozen_factorial_ranking_gate_passed=passed,
                                   wall_clock_seconds=time.perf_counter()-started), records=completed,
                      limitations=["Ranking-only audit: no new persisted retrieval, provenance, commit or ANSWER execution",
                                   "Frozen C142 models, no fresh initialization or training evidence",
                                   "Exhaustive 64 combinations and 27 spellings only within this fixed factor vocabulary",
                                   "52 combinations are newly evaluated; not an independently sourced sealed task dataset",
                                   "Catalog growth and query coverage expand together; inspect original queries in 64 candidates separately",
                                   "Generator uses training fixture factor structure; no oracle map is given to the scorer",
                                   "The 216 known-combination strings include the 24 original training queries",
                                   "No production encoder change; Gate E remains NOT PASSED"])
        temporary = output_dir / "summary.partial.json"
        temporary.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
        temporary.replace(output_dir / "summary.json")
        return report
    except Exception as exc:
        (output_dir / "invalid.json").write_text(json.dumps(dict(experiment_id=EXPERIMENT_ID, status="INVALID",
            diagnostic_execution_valid=False, error=str(exc), completed_models=len(completed)), indent=2), encoding="utf-8")
        raise
