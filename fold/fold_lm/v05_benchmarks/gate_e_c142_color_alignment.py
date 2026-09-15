"""C142: train-only color alignment; unchanged raw-query evaluation.

The color-first fixture structure supplies extra training supervision. It is
not an automatically discovered semantic factorization. No alias map is used
by evaluation, and no production runtime is changed by this benchmark.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import statistics
import subprocess
import time

import torch
from torch.nn import functional as F

EXPERIMENT_ID = "C142-v5e-training-only-color-alignment"
STAGE = "V5-E-TRAINING-ONLY-COLOR-ALIGNMENT"
SEEDS = tuple(range(20261621, 20261633))
AUX_WEIGHT = 1.0  # Preregistered; no sweep or validation-selected checkpoint.
C141_ID = "C141-v5e-color-alias-localization"
C141_COMMIT = "b913e56950e7c0454ca63ec58f1f05f7439e7205"
C140_SUMMARY_SHA = "a0b23c3a24d6674efd3f9c229d994543af4b1918318e4caa1e9c4c5e6e8d8ca8"
C37_SHA = "fd4a8da897bdaea9d103a252e30212c7ff842d23300d7c837333e146dee51931"
FIXTURE_SHA = "a52f8209703149407580f7e2965b61b78653030ee992af6d759865736741ca9e"
CORPUS_SHA = "48be60a0babc0692deb19431a911ef6cbea9ded186238ef5ae1ac305531401f0"
QUERIES_SHA = "9235f8af27ba7c4c8b0b01d6243f3970b0013358f92a5947aa245a7ac2981aa2"


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


@dataclass(frozen=True)
class TrainingSpec:
    queries: tuple[str, ...]
    descriptors: tuple[str, ...]
    targets: tuple[int, ...]
    color_aliases: tuple[str, ...]
    canonical_colors: tuple[str, ...]
    color_targets: tuple[int, ...]


def _training_spec(rows: list[dict]) -> TrainingSpec:
    """Read TRAIN_COMBINATION fields only, not validation text or labels."""
    queries, descriptors, targets, color_map = [], [], [], {}
    for row in rows:
        if row["split"] != "TRAIN_COMBINATION":
            continue
        parts = row["descriptor"].split()
        if len(parts) != 3 or not row["train"]:
            raise ValueError("Expected color-first training descriptor and queries")
        address = len(descriptors)
        descriptors.append(row["descriptor"])
        for text in row["train"]:
            words = text.split(maxsplit=1)
            if len(words) != 2:
                raise ValueError("Training query lacks color/context")
            alias, color = words[0], parts[0]
            if alias in color_map and color_map[alias] != color:
                raise ValueError(f"Ambiguous training color alias: {alias}")
            color_map[alias] = color
            queries.append(text)
            targets.append(address)
    if not descriptors or not color_map:
        raise ValueError("Empty training split")
    aliases = tuple(sorted(color_map))
    colors = tuple(sorted(set(color_map.values())))
    return TrainingSpec(tuple(queries), tuple(descriptors), tuple(targets), aliases,
                        colors, tuple(colors.index(color_map[a]) for a in aliases))


def _validate_prior(data: dict) -> None:
    s = data.get("summary", {})
    if (data.get("experiment_id") != C141_ID or data.get("status") != "PASS"
            or data.get("diagnostic_execution_valid") is not True
            or data.get("commit_sha") != C141_COMMIT
            or data.get("production_runtime_modified") is not False
            or data.get("gate_e_candidate") is not False
            or data.get("C140_summary_sha256") != C140_SUMMARY_SHA):
        raise ValueError("C142 requires the accepted C141 diagnostic PASS")
    for name, expected in (("C37_result_sha256_before", C37_SHA),
                           ("C37_result_sha256_after", C37_SHA),
                           ("fixture_sha256_before", FIXTURE_SHA),
                           ("fixture_sha256_after", FIXTURE_SHA)):
        if data.get(name) != expected:
            raise ValueError(f"C141 protected identity mismatch: {name}")
    required = dict(fresh_seed_count=0, feature_dim=49, baseline_cases=144,
                    intervention_cases=144, baseline_replay_match_rate=1.0,
                    frozen_weights_preserved_rate=1.0, evaluation_oov_count=0,
                    baseline_failure_count=4, rescued_failure_count=4,
                    baseline_success_count=140, preserved_success_count=140,
                    new_error_count=0)
    if any(s.get(k) != v for k, v in required.items()):
        raise ValueError("C141 counts or controls do not match accepted evidence")
    if (s.get("color_alias_localization_gate_passed") is not True
            or s.get("replay_seeds") != list(range(20261601, 20261613))):
        raise ValueError("C141 gate/seed profile mismatch")
    for k in ("canonical_known_accuracy", "canonical_unseen_accuracy",
              "canonical_scenario_accuracy", "canonical_positive_margin_rate"):
        if s.get(k, {}).get("min") != 1.0:
            raise ValueError(f"C141 unsuccessful canonical control: {k}")
    inputs = {k.replace("\\", "/").rsplit("/", 1)[-1]: v
              for k, v in data.get("input_sha256", {}).items()}
    if (inputs.get("c137_content_records.json") != CORPUS_SHA
            or inputs.get("c138_compositional_alias_queries.json") != QUERIES_SHA):
        raise ValueError("C141 input identity mismatch")
    records = data.get("records")
    if not isinstance(records, list) or [r.get("seed") for r in records] != s["replay_seeds"]:
        raise ValueError("Full ordered C141 records required, not console-only summary")
    errors = {}
    for r in records:
        for arm in ("baseline_cases", "canonical_color_cases"):
            cases = r.get(arm, [])
            if [c.get("key") for c in cases] != [f"q{i}" for i in range(12)]:
                raise ValueError("C141 case coverage mismatch")
            for i, c in enumerate(cases):
                correct = c.get("predicted_address") == i
                if (c.get("expected_address") != i or c.get("provenance_ok") is not True
                        or c.get("commit_count") != 1 or c.get("initial_action") != 2
                        or c.get("final_action") != 0 or c.get("passed") is not correct):
                    raise ValueError("C141 invalid case evidence")
                if not correct:
                    if arm != "baseline_cases":
                        raise ValueError("C141 canonical case was not successful")
                    errors[(r["seed"], c["key"])] = c["predicted_address"]
        margins = r.get("canonical_color_margins", [])
        if [m.get("key") for m in margins] != [f"q{i}" for i in range(12)]:
            raise ValueError("C141 treatment margin coverage mismatch")
        if any(not math.isfinite(float(m["expected_margin"])) or m["expected_margin"] <= 0
               for m in margins):
            raise ValueError("C141 canonical margin invalid")
    if errors != {(20261602, "q10"): 2, (20261604, "q11"): 1,
                  (20261606, "q11"): 1, (20261612, "q10"): 2}:
        raise ValueError("C141 baseline error profile mismatch")


def _objective(head, main, auxiliary, *, weight: float, logit_scale: float):
    if not math.isfinite(weight) or weight < 0 or not math.isfinite(logit_scale) or logit_scale <= 0:
        raise ValueError("Invalid objective weight/scale")
    q, d, labels = main
    main_loss = F.cross_entropy(head.scores(q, d) * logit_scale, labels)
    aux_loss = main_loss.new_zeros(())
    if weight:
        aliases, colors, labels = auxiliary
        aux_loss = F.cross_entropy(head.scores(aliases, colors) * logit_scale, labels)
    total = main_loss if weight == 0 else main_loss + weight * aux_loss
    if not torch.isfinite(total):
        raise RuntimeError("Non-finite C142 training loss")
    return total, main_loss, aux_loss


def _train(head, main, auxiliary, *, weight: float, steps: int,
           lr: float, logit_scale: float, progress=None) -> dict:
    if type(steps) is not int or steps < 1:
        raise ValueError("steps must be a positive integer")
    optimizer = torch.optim.AdamW(head.parameters(), lr=lr, weight_decay=0.0)
    head.train()
    for step in range(1, steps + 1):
        optimizer.zero_grad(set_to_none=True)
        total, primary, aux = _objective(head, main, auxiliary, weight=weight, logit_scale=logit_scale)
        total.backward()
        optimizer.step()
        if progress and (step == 1 or step == steps or step % 200 == 0):
            progress(step, float(primary.detach()), float(aux.detach()))
    head.eval()
    with torch.inference_mode():
        total, primary, aux = _objective(head, main, auxiliary, weight=weight, logit_scale=logit_scale)
        alias_acc = (head.select(auxiliary[0], auxiliary[1]) == auxiliary[2]).float().mean().item()
    return dict(final_main_loss=primary.item(), final_aux_loss=aux.item(),
                final_total_loss=total.item(), training_alias_accuracy=alias_acc, optimizer_steps=steps)


def _paired_outcomes(before: list[dict], after: list[dict]) -> dict:
    if not before or len(before) != len(after):
        raise ValueError("Expected nonempty paired cases")
    if any((b["seed"], b["key"]) != (a["seed"], a["key"])
           for b, a in zip(before, after, strict=True)):
        raise ValueError("Paired case identity mismatch")
    return dict(baseline_failure_count=sum(not b["passed"] for b in before),
                rescued_failure_count=sum(not b["passed"] and a["passed"] for b, a in zip(before, after)),
                baseline_success_count=sum(b["passed"] for b in before),
                preserved_success_count=sum(b["passed"] and a["passed"] for b, a in zip(before, after)),
                new_error_count=sum(b["passed"] and not a["passed"] for b, a in zip(before, after)))


def _metrics(cases: list[dict]) -> dict:
    known = [c for c in cases if c["split"] == "TRAIN_COMBINATION"]
    unseen = [c for c in cases if c["split"] == "UNSEEN_COMBINATION"]
    if not known or not unseen:
        raise ValueError("Both evaluation splits are required")
    return dict(known_accuracy=sum(c["passed"] for c in known) / len(known),
                unseen_accuracy=sum(c["passed"] for c in unseen) / len(unseen),
                scenario_accuracy=sum(c["passed"] for c in cases) / len(cases),
                positive_margin_rate=sum(c["expected_margin"] > 0 for c in cases) / len(cases),
                unseen_min_expected_margin=min(c["expected_margin"] for c in unseen))


def _treatment_passed(cases: list[dict]) -> bool:
    return bool(cases) and all(c["passed"] and math.isfinite(c["expected_margin"])
                               and c["expected_margin"] > 0 for c in cases)


def _evaluate(head, router, rows, vocabulary, adapter, *, seed, seed_index, arm, deps):
    """No color mapping argument: both arms consume the original queries."""
    c113, c137, c139, address_to_structure = deps
    device = next(head.parameters()).device
    descriptors = c139._collision_free_text_features([r["descriptor"] for r in rows], vocabulary, device=device)
    queries = c139._collision_free_text_features([r["validation"] for r in rows], vocabulary, device=device)
    values = c139._corpus_values()
    with torch.inference_mode():
        scores = head.scores(queries, descriptors)
    if scores.shape != (12, 12) or not torch.isfinite(scores).all():
        raise RuntimeError("Invalid evaluation scores")
    cases = []
    for i, row in enumerate(rows):
        with torch.inference_mode():
            predicted = int(head.select(queries[i:i+1], descriptors).item())
        if predicted != int(scores[i].argmax()):
            raise RuntimeError("Batched/single-query ranking disagreement")
        other = scores[i].clone()
        other[i] = -torch.inf
        rival = int(other.argmax())
        margin = float(scores[i, i] - other[rival])
        initial = c113._predict(router, dependency=1, evidence_present=0, observed_hidden=0,
                                visible_mask=(0, 1, 0, 0), device=device)
        structure = address_to_structure(predicted, address_count=len(rows))
        evidence, stats = (adapter.retrieve(structure, c137.SEMANTICS, schema=c137.SCHEMA, exact=True)
                           if initial == 2 else (None, {}))
        provenance = bool(evidence is not None and evidence.domain == "c137"
                          and evidence.schema == c137.SCHEMA and evidence.operations == ("READ_EVIDENCE",)
                          and evidence.source_sha256 == adapter.source_sha256
                          and evidence.index_fingerprint == adapter.index_fingerprint
                          and stats.get("source_sha256") == adapter.source_sha256
                          and stats.get("index_fingerprint") == adapter.index_fingerprint)
        commits = int(provenance)  # Existing harness indicator, not a transactional commit API.
        final = (c113._predict(router, dependency=1, evidence_present=1,
                              observed_hidden=evidence.evidence_value,
                              visible_mask=(0, 1, 0, 0), device=device) if commits else None)
        if not (initial == 2 and provenance and commits == 1 and final == 0
                and stats.get("mode") == "exact" and stats.get("vectors_scored") == 12):
            raise RuntimeError("Retrieval/authority control failed; not a scientific negative")
        passed = bool(predicted == i and evidence.key == row["key"] and evidence.evidence_value == values[row["key"]])
        cases.append(dict(seed=seed, key=row["key"], split=row["split"], query_text=row["validation"],
                          expected_address=i, predicted_address=predicted, hit_key=evidence.key,
                          expected_value=values[row["key"]], retrieved_value=evidence.evidence_value,
                          initial_action=initial, final_action=final, provenance_ok=provenance,
                          commit_count=commits, passed=passed, expected_score=float(scores[i, i]),
                          best_other_address=rival, best_other_score=float(other[rival]), expected_margin=margin))
        print(f"[C142] seed {seed_index}/12 arm={arm} case {i+1}/12 key={row['key']} "
              f"predicted={predicted} pass={passed} margin={margin:.8f} remaining={11-i}", flush=True)
    return cases


def _save_head(path: Path, head, *, vocabulary, config) -> dict:
    torch.save(dict(state_dict={k: v.detach().cpu().clone() for k, v in head.state_dict().items()},
                    vocabulary=list(vocabulary), config=config), path)
    return dict(path=str(path), sha256=_sha(path), serialized_bytes=path.stat().st_size)


def run(*, c141_summary_path: Path, output_dir: Path, protected_result_path: Path,
        protected_fixture_path: Path) -> dict:
    from fold_lm.v05.retrieval_content import SharedRetrievalContentHead
    from fold_lm.v05.retrieval_adapter import PersistedStructuralRetrievalAdapter
    from fold_lm.v05.retrieval_query import address_to_structure
    from fold_lm.v05_benchmarks import gate_e_c113_stale_eligibility_preflight as c113
    from fold_lm.v05_benchmarks import gate_e_c137_content_addressed_corpus_growth as c137
    from fold_lm.v05_benchmarks import gate_e_c138_compositional_alias_generalization as c138
    from fold_lm.v05_benchmarks import gate_e_c139_hash_collision_diagnostic as c139

    output_dir.mkdir(parents=True, exist_ok=False)
    records = []
    try:
        _validate_prior(json.loads(c141_summary_path.read_text(encoding="utf-8")))
        required = {protected_result_path: C37_SHA, protected_fixture_path: FIXTURE_SHA,
                    c137.CORPUS: CORPUS_SHA, c138.QUERY_FIXTURE: QUERIES_SHA,
                    c141_summary_path: _sha(c141_summary_path)}
        def check_files():
            for path, expected in required.items():
                if _sha(path) != expected:
                    raise RuntimeError(f"Protected/input/prerequisite hash mismatch: {path}")
        check_files()
        if not torch.cuda.is_available():
            raise RuntimeError("C142 formal experiment requires CUDA")
        if (c139.HIDDEN_DIM, c139.RESIDUAL_SCALE, c139.TRAIN_STEPS, c139.LR, c139.LOGIT_SCALE) != (64, 1.0, 600, 0.002, 12.0):
            raise RuntimeError("C139 training configuration drifted")
        rows = c138._load_fixture()
        rows_sha = _json_sha(rows)
        spec = _training_spec(rows)
        vocabulary = c139._training_vocabulary(rows)
        if (len(vocabulary), len(spec.descriptors), len(spec.queries), len(spec.color_aliases), len(spec.canonical_colors)) != (49, 8, 24, 12, 4):
            raise RuntimeError("Training specification size mismatch")
        if c139._fixture_oov_count(rows, vocabulary) or c138._fixture_controls(rows) != (1.0, 1.0):
            raise RuntimeError("OOV/lexical overlap/alias coverage control failed")
        device = torch.device("cuda")
        torch.cuda.set_device(0)
        torch.set_num_threads(2)
        torch.set_float32_matmul_precision("highest")
        def features(texts):
            return c139._collision_free_text_features(list(texts), vocabulary, device=device)
        main = (features(spec.queries), features(spec.descriptors), torch.tensor(spec.targets, device=device))
        auxiliary = (features(spec.color_aliases), features(spec.canonical_colors), torch.tensor(spec.color_targets, device=device))
        adapter = PersistedStructuralRetrievalAdapter(c137.CORPUS)
        if adapter.record_count != 12:
            raise RuntimeError("Corpus size mismatch")
        config = dict(feature_dim=49, hidden_dim=64, residual_scale=1.0)
        started = time.perf_counter()
        for seed_index, seed in enumerate(SEEDS, 1):
            print(f"[C142] seed {seed_index}/12 router train start seed={seed}", flush=True)
            router, router_loss = c113._train_router(seed, device)
            router_sha = _head_sha(router)
            print(f"[C142] seed {seed_index}/12 router train done loss={router_loss:.8f}", flush=True)
            torch.manual_seed(seed + 13900)
            prototype = SharedRetrievalContentHead(**config).to(device)
            heads = {arm: copy.deepcopy(prototype) for arm in ("BASELINE", "COLOR_AUX")}
            initial_sha = _head_sha(prototype)
            if any(_head_sha(h) != initial_sha for h in heads.values()):
                raise RuntimeError("Paired initialization mismatch")
            del prototype
            print(f"[C142] seed {seed_index}/12 paired_initial_weights_equal=True", flush=True)
            arms = {}
            for arm, weight in (("BASELINE", 0.0), ("COLOR_AUX", AUX_WEIGHT)):
                head = heads[arm]
                torch.cuda.synchronize()
                torch.cuda.reset_peak_memory_stats()
                start = time.perf_counter()
                def progress(step, primary, aux):
                    print(f"[C142] seed {seed_index}/12 arm={arm} train {step}/600 "
                          f"main_loss={primary:.8f} aux_loss={aux:.8f}", flush=True)
                train_metrics = _train(head, main, auxiliary, weight=weight, steps=c139.TRAIN_STEPS,
                                       lr=c139.LR, logit_scale=c139.LOGIT_SCALE, progress=progress)
                torch.cuda.synchronize()
                train_metrics.update(wall_clock_seconds=time.perf_counter()-start,
                                     peak_allocated_bytes=torch.cuda.max_memory_allocated(),
                                     peak_reserved_bytes=torch.cuda.max_memory_reserved())
                frozen_sha = _head_sha(head)
                cases = _evaluate(head, router, rows, vocabulary, adapter, seed=seed, seed_index=seed_index,
                                  arm=arm, deps=(c113, c137, c139, address_to_structure))
                if _head_sha(head) != frozen_sha or _head_sha(router) != router_sha or _json_sha(rows) != rows_sha:
                    raise RuntimeError("Evaluation modified weights/router/queries")
                checkpoint = _save_head(output_dir / f"seed-{seed}-{arm.lower()}.pt", head,
                                        vocabulary=vocabulary, config=config)
                arms[arm] = dict(training=train_metrics, initial_head_sha256=initial_sha,
                                 final_head_sha256=frozen_sha, metrics=_metrics(cases), cases=cases,
                                 checkpoint=checkpoint, parameter_count=sum(p.numel() for p in head.parameters()))
            paired = _paired_outcomes(arms["BASELINE"]["cases"], arms["COLOR_AUX"]["cases"])
            records.append(dict(seed=seed, arms=arms, paired=paired, router_final_loss=router_loss))
            print(f"[C142] seed {seed_index}/12 complete baseline_unseen={arms['BASELINE']['metrics']['unseen_accuracy']:.6f} "
                  f"aux_unseen={arms['COLOR_AUX']['metrics']['unseen_accuracy']:.6f} "
                  f"rescued={paired['rescued_failure_count']} new_errors={paired['new_error_count']} remaining_seeds={12-seed_index}", flush=True)
            del heads, head, router
        check_files()
        base_cases = [c for r in records for c in r["arms"]["BASELINE"]["cases"]]
        aux_cases = [c for r in records for c in r["arms"]["COLOR_AUX"]["cases"]]
        paired = _paired_outcomes(base_cases, aux_cases)
        passed = _treatment_passed(aux_cases)
        by_arm = {}
        for arm in ("BASELINE", "COLOR_AUX"):
            by_arm[arm] = {key: dict(mean=statistics.mean(v), min=min(v), max=max(v))
                           for key in records[0]["arms"][arm]["metrics"]
                           for v in [[r["arms"][arm]["metrics"][key] for r in records]]}
            by_arm[arm]["full_seed_pass_count"] = sum(_treatment_passed(r["arms"][arm]["cases"]) for r in records)
        report = dict(experiment_id=EXPERIMENT_ID, stage=STAGE, status="PASS" if passed else "FAIL",
                      diagnostic_execution_valid=True, production_runtime_modified=False, gate_e_candidate=False,
                      commit_sha=subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
                      C141_summary_sha256=required[c141_summary_path], input_sha256={str(k): v for k, v in required.items()},
                      C37_result_sha256_before=C37_SHA, C37_result_sha256_after=_sha(protected_result_path),
                      fixture_sha256_before=FIXTURE_SHA, fixture_sha256_after=_sha(protected_fixture_path),
                      environment=dict(torch=str(torch.__version__), cuda=torch.version.cuda,
                                       device=torch.cuda.get_device_name(0), precision="float32/highest"),
                      summary=dict(fresh_seeds=list(SEEDS), unique_fresh_seed_count=12, trained_heads=24,
                                   feature_dim=49, hidden_dim=64, residual_scale=1.0, train_steps=600,
                                   learning_rate=0.002, logit_scale=12.0, auxiliary_weight=AUX_WEIGHT,
                                   training_candidate_count=8, evaluation_candidate_count=12,
                                   primary_training_queries=24, auxiliary_alias_pairs=12, auxiliary_color_candidates=4,
                                   baseline_cases=144, treatment_cases=144, inference_oracle_used=False,
                                   zero_paired_lexical_overlap_rate=1.0, evaluation_oov_count=0,
                                   paired_initial_weights_equal_rate=1.0, evaluation_weights_preserved_rate=1.0,
                                   training_spec_sha256=_json_sha(spec.__dict__), evaluation_queries_sha256=rows_sha,
                                   baseline_error_contrast_available=paired["baseline_failure_count"] > 0,
                                   **paired, arms=by_arm, color_alignment_gate_passed=passed,
                                   wall_clock_seconds=time.perf_counter()-started), records=records,
                      limitations=["Color-first training fixture supplies extra factor supervision; not unsupervised discovery",
                                   "Same optimizer steps, but auxiliary loss adds forward/backward work; not compute-matched",
                                   "Fresh seeds reuse only four distinct held-out queries; no independent task replication",
                                   "No inference-time alias replacement; raw query text is identical in both arms",
                                   "If both arms are perfect, treatment sufficiency is supported but improvement is not identified",
                                   "Timing/VRAM are diagnostic, with both heads resident; no production performance claim",
                                   "Exact retrieval and commit-once harness remain scoped; not a new durability proof",
                                   "No production runtime change; Gate E remains NOT PASSED"])
        temporary = output_dir / "summary.partial.json"
        temporary.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
        temporary.replace(output_dir / "summary.json")
        return report
    except Exception as exc:
        (output_dir / "invalid.json").write_text(json.dumps(dict(experiment_id=EXPERIMENT_ID,
            status="INVALID", diagnostic_execution_valid=False, error=str(exc), completed_seeds=len(records),
            records=records), indent=2, allow_nan=False), encoding="utf-8")
        raise
