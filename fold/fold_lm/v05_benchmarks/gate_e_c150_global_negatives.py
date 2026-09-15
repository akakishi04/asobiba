"""C150: change auxiliary competing candidates, not the inference score.

Existing training positive pairs are retained. Global negatives add exclusion
constraints between existing concepts; this is NOT unchanged supervision or
unsupervised factor discovery. No fourth named attribute or loss is added.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import subprocess
import time

import torch
from torch.nn import functional as F

EXPERIMENT_ID = "C150-v5e-global-auxiliary-negatives"
STAGE = "V5-E-GLOBAL-AUXILIARY-NEGATIVES"
SEEDS = tuple(range(20261701, 20261713))
ARMS = ("WITHIN_FACTOR", "GLOBAL_CONCEPT")
AXES = ("COLOR", "SHAPE", "MATERIAL")
LOSS_ORDER = ("COLOR", "MATERIAL", "SHAPE")
CONFIG = dict(feature_dim=49, hidden_dim=64, residual_scale=1.0)
STEPS, LR, SCALE = 600, 0.002, 12.0
TRAIN_MODE, EVAL_MODE = "POOL_THEN_ENCODE", "ENCODE_THEN_POOL"
C149_ID = "C149-v5e-frozen-margin-accounting"
C149_COMMIT = "f02b3612183753973c1282924216f9703b49dbbe"
C149_SHA = "d2fdfab39fdc09f250ed5c9cdbdae159b148c3d06bd023288961993913a54250"
C148_SHA = "4a2b32d45eff90295505440c6258808319f20e2751ba798f7779763c4fe6d30e"
MANIFEST_SHA = "5a19de10d8152ac262846682a79a13bb942eeacd7dca979afb09b70170ebdd65"
QUERY_SHA = "9235f8af27ba7c4c8b0b01d6243f3970b0013358f92a5947aa245a7ac2981aa2"
C37_SHA = "fd4a8da897bdaea9d103a252e30212c7ff842d23300d7c837333e146dee51931"
FIXTURE_SHA = "a52f8209703149407580f7e2965b61b78653030ee992af6d759865736741ca9e"
PARTS = ("same_factor", "cross_factor", "candidate_norm")


def _sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _candidate_specs(specs: dict, scope: str) -> dict:
    """Take only the already extracted TRAIN positive-pair specifications."""
    if scope not in ARMS or set(specs) != set(AXES):
        raise ValueError("Unregistered scope or factor set")
    canonical, aliases_seen = [], set()
    for axis in AXES:
        aliases, words, labels = specs[axis]
        if (not aliases or len(aliases) != len(labels) or not words
                or len(set(words)) != len(words) or len(set(aliases)) != len(aliases)
                or any(not isinstance(s, str) or not s.strip() for s in (*aliases, *words))
                or any(type(y) is not int or not 0 <= y < len(words) for y in labels)):
            raise ValueError("Invalid positive-pair specification")
        if aliases_seen.intersection(aliases):
            raise ValueError("Cross-factor ambiguous alias; cannot infer unique global target")
        aliases_seen.update(aliases)
        canonical.extend(words)
    if len(set(canonical)) != len(canonical):
        raise ValueError("Canonical concepts must be disjoint in this diagnostic")
    if aliases_seen.intersection(canonical):
        raise ValueError("Unexpected direct lexical overlap")
    global_words = tuple(sorted(canonical))
    result = {}
    for axis in AXES:
        aliases, words, labels = specs[axis]
        candidates = tuple(words) if scope == ARMS[0] else global_words
        targets = tuple(candidates.index(words[y]) for y in labels)
        result[axis] = tuple(aliases), candidates, targets
    return result


def _objective(head, main, alignments):
    def ce(data):
        queries, candidates, labels = data
        return F.cross_entropy(head.scores(queries, candidates) * SCALE, labels)
    ml = ce(main)  # Pooled full text in BOTH arms, same as C148 POOLED_TRAIN.
    cl, matl, sl = (ce(alignments[axis]) for axis in LOSS_ORDER)
    total = ml + 1.0 * cl + 1.0 * matl + 1.0 * sl
    if not all(torch.isfinite(x).item() for x in (total, ml, cl, matl, sl)):
        raise RuntimeError("Nonfinite objective")
    return total, ml, cl, matl, sl


def _train(head, main, alignments, *, steps=STEPS, progress=None):
    if type(steps) is not int or steps < 1:
        raise ValueError("Positive integer step count required")
    optimizer = torch.optim.AdamW(head.parameters(), lr=LR, weight_decay=0.0)
    head.train()
    for step in range(1, steps + 1):
        optimizer.zero_grad(set_to_none=True)
        values = _objective(head, main, alignments)
        values[0].backward()
        optimizer.step()
        if progress and (step == 1 or step == steps or step % 200 == 0):
            progress(step, [v.detach().item() for v in values[1:]])
    head.eval()
    with torch.inference_mode():
        values = _objective(head, main, alignments)
    return dict(optimizer_steps=steps, training_composition=TRAIN_MODE,
                final_losses=dict(zip(("total", "main", "color", "material", "shape"),
                                      [v.item() for v in values], strict=True)))


def _fit(head, alignments) -> dict:
    with torch.inference_mode():
        return {axis: (head.select(q, d) == y).float().mean().item()
                for axis, (q, d, y) in alignments.items()}


def _perfect(rows) -> bool:
    return bool(rows) and all(r["correct"] and math.isfinite(r["expected_margin"])
                             and r["expected_margin"] > 0 for r in rows)


def _validate_audit(data, source, suite, summarize):
    """Reaggregate full C149 accounting, cross-checking validated C148 records."""
    if (data.get("experiment_id") != C149_ID or data.get("commit_sha") != C149_COMMIT
            or data.get("status") != "PASS" or data.get("diagnostic_execution_valid") is not True
            or data.get("production_runtime_modified") is not False or data.get("gate_e_candidate") is not False
            or data.get("C148_summary_sha256") != C148_SHA or data.get("evaluation_manifest_sha256") != MANIFEST_SHA):
        raise ValueError("Expected accepted C149 accounting PASS")
    s = data.get("summary", {})
    required = dict(analysis_only=True, loaded_checkpoints=24, fresh_seed_count=0,
                    additional_training_steps=0, scoring_rule_changed=False, runtime_path_exercised=False,
                    full_replay_cases=41472, original12_replay_cases=288, full_replay_match_rate=1.0,
                    frozen_weights_preserved_rate=1.0, accounting_complete=True, reconstruction_atol=1e-5)
    if any(s.get(k) != v for k, v in required.items()):
        raise ValueError("C149 execution-control mismatch")
    source_arms = ("POOLED_TRAIN", "COMPOSED_TRAIN")
    records = data.get("records")
    identities = [(seed, arm) for seed in range(20261681, 20261693) for arm in source_arms]
    if not isinstance(records, list) or [(r.get("seed"), r.get("arm")) for r in records] != identities:
        raise ValueError("Full ordered C149 records required")
    sources = {r["seed"]: r for r in source["records"]}
    flat = {a: [] for a in source_arms}
    compact = []
    for record in records:
        entry = sources[record["seed"]]["arms"][record["arm"]]
        cases = record["cases"]
        if (len(cases) != 1728 or record["checkpoint_sha256"] != entry["checkpoint"]["sha256"]
                or record["frozen_head_sha256"] != entry["final_head_sha256"]
                or record["source_singleton_fit"] != entry["training"]["training_alignment_accuracy"]):
            raise ValueError("C149 source identity/coverage mismatch")
        for case, old, query in zip(cases, entry["results"], suite["queries"], strict=True):
            if (case["case_id"] != query["case_id"] or case["bucket"] != query["bucket"]
                    or any(case[k] != old[k] for k in ("correct", "predicted_address", "best_other_address"))):
                raise ValueError("C149 case identity/ranking mismatch")
            if not all(math.isfinite(case[k]) for k in PARTS + ("expected_margin", "reconstructed_margin", "reconstruction_error")):
                raise ValueError("C149 nonfinite accounting")
            rebuilt = sum(case[k] for k in PARTS)
            residual = abs(case["reconstructed_margin"] - case["expected_margin"])
            if (abs(case["expected_margin"] - old["expected_margin"]) > 1e-5
                    or abs(rebuilt - case["reconstructed_margin"]) > 1e-10
                    or residual > 1e-5 or abs(residual - case["reconstruction_error"]) > 1e-12):
                raise ValueError("C149 margin reconstruction mismatch")
        if summarize(cases) != record["accounting"]:
            raise ValueError("C149 per-head aggregate mismatch")
        errors = [c for c in cases if not c["correct"]]
        details = record["error_details"]
        if len(details) != len(errors):
            raise ValueError("C149 error detail count mismatch")
        for detail, case in zip(details, errors, strict=True):
            if any(detail.get(k) != v for k, v in case.items()):
                raise ValueError("C149 error detail differs from accounting")
            compact.append(dict(seed=record["seed"], arm=record["arm"], **{k: detail[k] for k in
                ("text", "expected", "selected", "expected_margin") + PARTS}))
        flat[record["arm"]].extend(cases)
    totals = {arm: summarize(cases) for arm, cases in flat.items()}
    if (totals != s["arms"] or s["source_paired"] != source["summary"]["paired"]
            or compact != s["residual_case_details"]
            or [totals[a]["errors"] for a in source_arms] != [11, 12]):
        raise ValueError("C149 aggregate/source-pair mismatch")


def _save_head(path, head, vocabulary, scope, config=CONFIG):
    torch.save(dict(state_dict={k: v.detach().cpu().clone() for k, v in head.state_dict().items()},
                    config=config, vocabulary=list(vocabulary), auxiliary_candidate_scope=scope,
                    training_composition=TRAIN_MODE, inference_composition=EVAL_MODE,
                    experiment_id=EXPERIMENT_ID), path)
    return dict(path=str(path), sha256=_sha(path), serialized_bytes=path.stat().st_size)


def run(*, c149_summary: Path, c148_summary: Path, output_dir: Path) -> dict:
    from fold_lm.v05.retrieval_content import SharedRetrievalContentHead
    from fold_lm.v05_benchmarks import gate_e_c139_hash_collision_diagnostic as c139
    from fold_lm.v05_benchmarks import gate_e_c143_frozen_factorial_audit as c143
    from fold_lm.v05_benchmarks import gate_e_c146_all_factor_alignment as c146
    from fold_lm.v05_benchmarks import gate_e_c147_composition_order as c147
    from fold_lm.v05_benchmarks import gate_e_c148_train_consistent_composition as c148
    from fold_lm.v05_benchmarks import gate_e_c149_margin_accounting as c149
    output_dir.mkdir(parents=True, exist_ok=False)
    completed = []
    try:
        fixture = Path(__file__).parent / "fixtures/c138_compositional_alias_queries.json"
        manifest_source = c148_summary.parent / "evaluation-manifest.json"
        protected = {c149_summary: C149_SHA, c148_summary: C148_SHA, manifest_source: MANIFEST_SHA,
                     fixture: QUERY_SHA, Path("runs/chatgpt-last-result.json"): C37_SHA,
                     Path("runs/fixtures/v05-c-composition-20260921.pt"): FIXTURE_SHA}
        def check_files():
            for path, digest in protected.items():
                if _sha(path) != digest:
                    raise RuntimeError(f"Input/protected identity mismatch: {path}")
        check_files()
        if c148.CONFIG != CONFIG or (c148.STEPS, c148.LR, c148.SCALE) != (STEPS, LR, SCALE):
            raise RuntimeError("Reference configuration changed")
        rows = json.loads(fixture.read_text(encoding="utf-8"))["queries"]
        suite = json.loads(manifest_source.read_text(encoding="utf-8"))
        if suite != c143._build_suite(rows):
            raise RuntimeError("Fixed manifest/generator mismatch")
        source = json.loads(c148_summary.read_text(encoding="utf-8"))
        c149._validate_prior(source, suite, c146._audit_results, c146._pair, c148._perfect)
        _validate_audit(json.loads(c149_summary.read_text(encoding="utf-8")), source, suite, c149._diagnostic_summary)
        manifest = output_dir / "evaluation-manifest.json"
        manifest.write_bytes(manifest_source.read_bytes())
        protected[manifest] = MANIFEST_SHA
        main_spec, pair_specs = c146._training_specs(rows)
        specs = {scope: _candidate_specs(pair_specs, scope) for scope in ARMS}
        if (len(main_spec[0]), len(main_spec[1])) != (24, 8) or any(
                (len(q), len(d)) != (12, 4 if arm == ARMS[0] else 12)
                for arm in ARMS for q, d, _ in specs[arm].values()):
            raise RuntimeError("Training candidate/positive-pair counts differ")
        vocabulary = c139._training_vocabulary(rows)
        if len(vocabulary) != 49 or c139._fixture_oov_count(rows, vocabulary):
            raise RuntimeError("Vocabulary/OOV mismatch")
        if not torch.cuda.is_available():
            raise RuntimeError("Formal C150 training requires CUDA")
        torch.cuda.set_device(0)
        torch.set_num_threads(2)
        torch.set_float32_matmul_precision("highest")
        device = torch.device("cuda")
        def features(texts):
            return c139._collision_free_text_features(list(texts), vocabulary, device=device)
        def tensors(spec):
            return features(spec[0]), features(spec[1]), torch.tensor(spec[2], dtype=torch.long, device=device)
        main = tensors(main_spec)
        alignments = {arm: {axis: tensors(spec) for axis, spec in specs[arm].items()} for arm in ARMS}
        qt, dt = [q["text"] for q in suite["queries"]], suite["descriptors"]
        batch = c148._prepare(qt + dt, features)
        labels = [q["expected_address"] for q in suite["queries"]]
        old_indices = [qt.index(r["validation"]) for r in rows]
        inputs_before = copy.deepcopy((rows, suite, specs))
        started = time.perf_counter()
        for i, seed in enumerate(SEEDS, 1):
            torch.manual_seed(seed + 13900)
            prototype = SharedRetrievalContentHead(**CONFIG).to(device)
            initial = c148._fingerprint(prototype)
            heads = {arm: copy.deepcopy(prototype) for arm in ARMS}
            if any(c148._fingerprint(h) != initial for h in heads.values()):
                raise RuntimeError("Paired initialization mismatch")
            del prototype
            print(f"[C150] seed {i}/12 seed={seed} paired_initial_weights_equal=True", flush=True)
            entries = {}
            for arm in ARMS:
                head = heads[arm]
                def progress(step, loss):
                    print(f"[C150] seed {i}/12 arm={arm} train {step}/600 main={loss[0]:.8f} "
                          f"color={loss[1]:.8f} material={loss[2]:.8f} shape={loss[3]:.8f}", flush=True)
                torch.cuda.synchronize()
                torch.cuda.reset_peak_memory_stats()
                start = time.perf_counter()
                training = _train(head, main, alignments[arm], progress=progress)
                torch.cuda.synchronize()
                training.update(wall_clock_seconds=time.perf_counter() - start,
                    peak_allocated_bytes=torch.cuda.max_memory_allocated(), peak_reserved_bytes=torch.cuda.max_memory_reserved(),
                    within_factor_fit=_fit(head, alignments[ARMS[0]]), global_concept_fit=_fit(head, alignments[ARMS[1]]))
                frozen = c148._fingerprint(head)
                with torch.inference_mode():
                    encoded = c148._encode(head, batch, EVAL_MODE)
                reference, cost = c147._compose(head, qt + dt, features)
                if not torch.allclose(encoded, reference, atol=1e-6, rtol=0):
                    raise RuntimeError("Evaluation composition reference mismatch")
                eq, ed = encoded[:1728], encoded[1728:]
                results = []
                with torch.inference_mode():
                    for offset in range(0, 1728, 216):
                        results.extend(c147._rank(eq[offset:offset+216] @ ed.T, labels[offset:offset+216]))
                        print(f"[C150] seed {i}/12 arm={arm} audited={offset+216}/1728 "
                              f"correct={sum(r['correct'] for r in results)} remaining={1512-offset}", flush=True)
                    old = c147._rank(eq[old_indices] @ ed[:12].T, list(range(12)))
                if c148._fingerprint(head) != frozen or (rows, suite, specs) != inputs_before:
                    raise RuntimeError("Evaluation mutated model/inputs")
                entries[arm] = dict(training=training, initial_head_sha256=initial, final_head_sha256=frozen,
                    auxiliary_candidate_scope=arm, evaluation_composition=EVAL_MODE, composition_reference_match=True,
                    composition_accounting=cost, metrics=c146._audit_results(results, suite), results=results,
                    original12=old, original12_all_pass=_perfect(old), parameter_count=sum(p.numel() for p in head.parameters()),
                    checkpoint=_save_head(output_dir/f"seed-{seed}-{arm.lower()}.pt", head, vocabulary, arm))
            paired = c146._pair(entries[ARMS[0]]["results"], entries[ARMS[1]]["results"], suite)
            completed.append(dict(seed=seed, arms=entries, paired=paired))
            print(f"[C150] seed {i}/12 complete within_errors={entries[ARMS[0]]['metrics']['errors']} "
                  f"global_errors={entries[ARMS[1]]['metrics']['errors']} rescued={paired['rescued_errors']} "
                  f"new_errors={paired['new_errors']} remaining_seeds={12-i}", flush=True)
            del heads, head, encoded, reference, eq, ed
        check_files()
        repeated = dict(descriptors=dt, queries=suite["queries"] * 12)
        flat = {a: [r for model in completed for r in model["arms"][a]["results"]] for a in ARMS}
        aggregates = {}
        for arm in ARMS:
            aggregates[arm] = c146._audit_results(flat[arm], repeated)
            aggregates[arm].update(full_model_pass_count=sum(_perfect(m["arms"][arm]["results"]) for m in completed),
                original12_full_pass_count=sum(m["arms"][arm]["original12_all_pass"] for m in completed))
        paired = c146._pair(flat[ARMS[0]], flat[ARMS[1]], repeated)
        passed = aggregates[ARMS[1]]["full_model_pass_count"] == 12 and aggregates[ARMS[1]]["original12_full_pass_count"] == 12
        report = dict(experiment_id=EXPERIMENT_ID, stage=STAGE, status="PASS" if passed else "FAIL",
            diagnostic_execution_valid=True, production_runtime_modified=False, gate_e_candidate=False,
            commit_sha=subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
            C149_summary_sha256=C149_SHA, C148_summary_sha256=C148_SHA, evaluation_manifest_sha256=MANIFEST_SHA,
            input_sha256={str(p): h for p, h in protected.items()},
            environment=dict(torch=str(torch.__version__), cuda=torch.version.cuda, device=torch.cuda.get_device_name(0), precision="float32/highest"),
            summary=dict(fresh_seeds=list(SEEDS), paired_heads=24, **CONFIG, train_steps=STEPS, learning_rate=LR,
                logit_scale=SCALE, training_composition=TRAIN_MODE, evaluation_composition=EVAL_MODE,
                changed_variable="auxiliary candidate scope: within factor 4 -> global concepts 12",
                positive_alias_pairs=36, auxiliary_coefficients=[1.0,1.0,1.0], auxiliary_loss_reduction="sum of three 12-alias means",
                control_auxiliary_candidates=4, treatment_auxiliary_candidates=12, training_main_queries=24, training_main_candidates=8,
                full_candidate_count=64, queries_per_model=1728, full_cases_per_arm=20736, original12_cases_per_arm=144,
                paired_initialization_verified=True, evaluation_weights_preserved=True, evaluation_oov_count=0,
                inference_oracle_used=False, scoring_rule_changed=False, runtime_path_exercised=False,
                composition_reference_match_rate=1.0, baseline_error_contrast_available=aggregates[ARMS[0]]["errors"] > 0,
                training_alignment_specs=specs, arms=aggregates, paired=paired,
                global_negative_gate_passed=passed, wall_clock_seconds=time.perf_counter() - started), records=completed,
            limitations=["Existing 36 positive alias pairs retained, but eight extra cross-factor negatives per alias add exclusion constraints",
                         "No new factor/loss coefficient, same sum-of-three-means weighting; negative pool and its gradient/compute change",
                         "No cross term or normalization is removed at inference; scorer is unchanged",
                         "Same explicitly supervised synthetic development task; no independent task or automatic factor discovery claim",
                         "Fresh seeds are paired, not repeated tuning or continuation of previous failure checkpoints",
                         "Candidate competition may improve rankings without identifying a unique causal mechanism or enforcing orthogonality",
                         "Equal optimizer steps/parameters do not imply equal compute; timings have both models resident and fixed arm order",
                         "All evaluation is ranking-only, including original12; no runtime/Gate E promotion"])
        tmp = output_dir / "summary.partial.json"
        tmp.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
        tmp.replace(output_dir / "summary.json")
        return report
    except Exception as exc:
        (output_dir / "invalid.json").write_text(json.dumps(dict(experiment_id=EXPERIMENT_ID, status="INVALID",
            diagnostic_execution_valid=False, error=str(exc), completed_seeds=len(completed)), indent=2), encoding="utf-8")
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description="C150 paired auxiliary negative-pool intervention")
    parser.add_argument("--c149-summary", type=Path, required=True)
    parser.add_argument("--c148-summary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(f"C150 prerequisite_summary = {args.c149_summary}", flush=True)
    print("C150 fresh_seeds = 20261701..20261712; paired_heads = 24", flush=True)
    print("C150 changed = auxiliary competing candidates 4 -> 12; positive_pairs=36 unchanged", flush=True)
    print("C150 main training = POOL_THEN_ENCODE; both arms evaluate ENCODE_THEN_POOL", flush=True)
    print("C150 coefficients=1,1,1; steps=600; new_named_losses=0; scorer_changed=False; runtime=False", flush=True)
    report = run(c149_summary=args.c149_summary, c148_summary=args.c148_summary, output_dir=args.output_dir)
    print("=== C150 RESULT ===", flush=True)
    print(json.dumps(dict(report, records="omitted; see summary.json"), indent=2, allow_nan=False), flush=True)
    return 0  # Valid scientific FAIL is not an execution error.


if __name__ == "__main__":
    raise SystemExit(main())
