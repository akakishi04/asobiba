"""C147: frozen all-factor heads; a registered change of composition rule.

No new supervision, optimization, factor-slot matching or alias replacement.
Whitespace expressions are units: this fixture-aligned segmentation is a
limitation, not an automatically learned tokenizer or a production proposal.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import subprocess
import time

import torch
from torch.nn import functional as F

from fold_lm.v05.retrieval_content import SharedRetrievalContentHead

EXPERIMENT_ID = "C147-v5e-frozen-composition-order"
STAGE = "V5-E-FROZEN-COMPOSITION-ORDER"
C146_ID = "C146-v5e-all-factor-supervised-reference"
C146_COMMIT = "6582dac69fc6bab93cd8cdbc08ceef13d0542ba7"
C145_SHA = "c3c21bcb5687451ae6a1d4260e410dce7d47732c58bdf278dee8ac86ff670683"
MANIFEST_SHA = "5a19de10d8152ac262846682a79a13bb942eeacd7dca979afb09b70170ebdd65"
QUERY_SHA = "9235f8af27ba7c4c8b0b01d6243f3970b0013358f92a5947aa245a7ac2981aa2"
C37_SHA = "fd4a8da897bdaea9d103a252e30212c7ff842d23300d7c837333e146dee51931"
FIXTURE_SHA = "a52f8209703149407580f7e2965b61b78653030ee992af6d759865736741ca9e"
CONFIG = dict(feature_dim=49, hidden_dim=64, residual_scale=1.0)
SEEDS = tuple(range(20261661, 20261673))  # Existing C146 heads, not fresh seeds.
SOURCE_ARM = "ALL_FACTOR_AUX"
MODES = ("POOL_THEN_ENCODE", "ENCODE_THEN_POOL")
AXES = ("COLOR", "SHAPE", "MATERIAL")
REPLAY_ATOL = 1e-5
PRIOR_ERRORS = {
    "COLOR_MATERIAL_AUX": (24, 60, 82, 39, 57, 18, 10, 34, 20, 35, 7, 90),
    "ALL_FACTOR_AUX": (0, 0, 0, 2, 1, 7, 0, 0, 0, 0, 1, 0),
}
PRIOR_MASKS = {
    "COLOR_MATERIAL_AUX": {"COLOR": 31, "COLOR+MATERIAL": 6, "COLOR+SHAPE": 14,
        "COLOR+SHAPE+MATERIAL": 1, "MATERIAL": 18, "SHAPE": 392, "SHAPE+MATERIAL": 14},
    "ALL_FACTOR_AUX": {"COLOR": 5, "MATERIAL": 5, "SHAPE": 1},
}


def _sha(path: Path) -> str:
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def _fingerprint(head) -> str:
    digest = hashlib.sha256()
    for name, tensor in sorted(head.state_dict().items()):
        digest.update(name.encode())
        digest.update(str(tuple(tensor.shape)).encode())
        digest.update(str(tensor.dtype).encode())
        digest.update(tensor.detach().cpu().contiguous().numpy().tobytes())
    return digest.hexdigest()


def _rank(scores: torch.Tensor, expected: list[int]) -> list[dict]:
    if scores.ndim != 2 or scores.shape[0] != len(expected) or scores.shape[1] < 2:
        raise ValueError("Invalid score shape")
    if not torch.isfinite(scores).all():
        raise ValueError("Nonfinite scores")
    if any(type(x) is not int or not 0 <= x < scores.shape[1] for x in expected):
        raise ValueError("Invalid expected index")
    pred = scores.argmax(-1)
    labels = torch.tensor(expected, dtype=torch.long, device=scores.device)
    index = torch.arange(len(expected), device=scores.device)
    right = scores[index, labels]
    rivals = scores.clone()
    rivals[index, labels] = -torch.inf
    other, rival = rivals.max(-1)
    return [dict(predicted_address=p, correct=p == e, expected_score=s,
                 best_other_address=r, best_other_score=t, expected_margin=s-t)
            for p, e, s, r, t in zip(pred.tolist(), expected, right.tolist(), rival.tolist(), other.tolist(), strict=True)]


def _replay(actual: list[dict], prior: list[dict]) -> None:
    if len(actual) != len(prior):
        raise ValueError("Replay length mismatch")
    for a, b in zip(actual, prior, strict=True):
        if any(a[k] != b[k] for k in ("predicted_address", "best_other_address", "correct")):
            raise ValueError("Replay prediction/rival mismatch")
        for k in ("expected_score", "best_other_score", "expected_margin"):
            if not math.isfinite(a[k]) or not math.isfinite(b[k]) or abs(a[k]-b[k]) > REPLAY_ATOL:
                raise ValueError("Replay score drift")


def _units(text: str) -> tuple[str, ...]:
    if not isinstance(text, str) or not text.split():
        raise ValueError("Nonempty text required")
    # Preserve repetitions and hyphens. Sorting removes permutation roundoff.
    return tuple(sorted(text.split()))


def _compose(head, texts: list[str], features) -> tuple[torch.Tensor, dict]:
    """Normalize a sum of independently encoded units, without factor labels.

    `features` is the unchanged C139 feature function. A hyphenated unit is
    passed intact to it and can still tokenize into multiple feature tokens.
    """
    pieces = [_units(text) for text in texts]
    if not pieces:
        raise ValueError("Nonempty text batch required")
    unique = sorted({word for words in pieces for word in words})
    lookup = {word: i for i, word in enumerate(unique)}
    with torch.inference_mode():
        vectors = head.encode(features(unique))
        if vectors.ndim != 2 or vectors.shape[0] != len(unique) or not torch.isfinite(vectors).all():
            raise ValueError("Invalid unit embeddings")
        pooled = torch.stack([vectors[[lookup[word] for word in words]].sum(0) for words in pieces])
        norms = pooled.norm(dim=-1)
        if not torch.isfinite(pooled).all() or (norms <= 1e-12).any():
            raise ValueError("Undefined normalized unit sum")
        encoded = F.normalize(pooled, dim=-1)
    return encoded, dict(unique_encoded_units=len(unique), unit_occurrences=sum(map(len, pieces)),
                         encoded_dimension=vectors.shape[1], unit_cache_bytes=vectors.numel()*vectors.element_size())


def _perfect(rows) -> bool:
    return bool(rows) and all(r["correct"] and math.isfinite(r["expected_margin"])
                             and r["expected_margin"] > 0 for r in rows)


def _paired(before, after) -> dict:
    if not before or len(before) != len(after):
        raise ValueError("Nonempty equally-sized paired results required")
    return dict(rescued_errors=sum(not b["correct"] and a["correct"] for b, a in zip(before, after)),
                new_errors=sum(b["correct"] and not a["correct"] for b, a in zip(before, after)),
                both_correct=sum(b["correct"] and a["correct"] for b, a in zip(before, after)),
                both_wrong=sum(not b["correct"] and not a["correct"] for b, a in zip(before, after)))


def _validate_prior(data: dict, suite: dict, audit) -> list[dict]:
    """Use C146's frozen result auditor to recompute, not trust summary flags."""
    s = data.get("summary", {})
    if (data.get("experiment_id") != C146_ID or data.get("commit_sha") != C146_COMMIT
            or data.get("status") != "FAIL" or data.get("diagnostic_execution_valid") is not True
            or data.get("production_runtime_modified") is not False or data.get("gate_e_candidate") is not False
            or data.get("C145_summary_sha256") != C145_SHA
            or data.get("evaluation_manifest_sha256") != MANIFEST_SHA):
        raise ValueError("Expected accepted C146 valid negative")
    required = dict(fresh_seeds=list(SEEDS), paired_heads=24, **CONFIG, train_steps=600,
        learning_rate=0.002, logit_scale=12.0, color_weight=1.0, material_weight=1.0, shape_weight=1.0,
        full_candidate_count=64, queries_per_model=1728, full_cases_per_arm=20736,
        original12_cases_per_arm=144, training_main_queries=24, training_main_candidates=8,
        auxiliary_aliases_per_factor=12, auxiliary_candidates_per_factor=4,
        paired_initialization_verified=True, evaluation_weights_preserved=True,
        evaluation_oov_count=0, zero_paired_lexical_overlap=True, inference_oracle_used=False,
        runtime_path_exercised=False, all_factor_reference_gate_passed=False)
    if any(s.get(k) != v for k, v in required.items()):
        raise ValueError("C146 configuration/control mismatch")
    records = data.get("records")
    if not isinstance(records, list) or [r.get("seed") for r in records] != list(SEEDS):
        raise ValueError("Full ordered C146 records required; console report is insufficient")
    original_suite = dict(descriptors=suite["descriptors"][:12], queries=[dict(expected_address=i) for i in range(12)])
    for index, record in enumerate(records):
        for arm in PRIOR_ERRORS:
            entry = record["arms"][arm]
            if len(entry["results"]) != 1728 or len(entry["original12"]) != 12:
                raise ValueError("C146 result coverage mismatch")
            m = audit(entry["results"], suite)
            if m != entry["metrics"] or m["errors"] != PRIOR_ERRORS[arm][index]:
                raise ValueError("C146 per-model accounting mismatch")
            audit(entry["original12"], original_suite)
            if not _perfect(entry["original12"]) or entry["original12_all_pass"] is not True:
                raise ValueError("C146 original-12 control mismatch")
            fit = entry["training"].get("training_alignment_accuracy", {})
            if set(fit) != set(AXES) or any(not math.isfinite(float(x)) or not 0 <= x <= 1 for x in fit.values()):
                raise ValueError("Invalid source singleton-alignment diagnostics")
            if entry["training"]["optimizer_steps"] != 600:
                raise ValueError("C146 training-step mismatch")
        if record["arms"]["COLOR_MATERIAL_AUX"]["initial_head_sha256"] != record["arms"][SOURCE_ARM]["initial_head_sha256"]:
            raise ValueError("C146 paired initialization mismatch")
    repeated = dict(descriptors=suite["descriptors"], queries=suite["queries"]*12)
    for arm in PRIOR_ERRORS:
        rows = [r for record in records for r in record["arms"][arm]["results"]]
        m = audit(rows, repeated)
        m.update(full_model_pass_count=sum(_perfect(r["arms"][arm]["results"]) for r in records),
                 original12_full_pass_count=12)
        if m != s["arms"][arm] or m["mismatch_masks"] != PRIOR_MASKS[arm]:
            raise ValueError("C146 aggregate accounting mismatch")
    before = [r for record in records for r in record["arms"]["COLOR_MATERIAL_AUX"]["results"]]
    after = [r for record in records for r in record["arms"][SOURCE_ARM]["results"]]
    pairs = _paired(before, after)
    if pairs != dict(rescued_errors=469, new_errors=4, both_correct=20256, both_wrong=7):
        raise ValueError("C146 paired evidence mismatch")
    if any(s["paired"].get(k) != v for k, v in pairs.items()):
        raise ValueError("C146 paired summary mismatch")
    return records


def _load_head(run_dir: Path, seed: int, entry: dict, vocabulary, device):
    name = f"seed-{seed}-{SOURCE_ARM.lower()}.pt"
    meta = entry["checkpoint"]
    if meta["path"].replace("\\", "/").rsplit("/", 1)[-1] != name:
        raise ValueError("Checkpoint filename mismatch")
    path = run_dir / name
    if path.resolve().parent != run_dir.resolve():
        raise ValueError("Checkpoint escapes original run directory")
    if _sha(path) != meta["sha256"] or path.stat().st_size != meta["serialized_bytes"]:
        raise ValueError("Checkpoint byte identity mismatch")
    saved = torch.load(path, map_location="cpu", weights_only=True)
    if saved.get("config") != CONFIG or tuple(saved.get("vocabulary", ())) != tuple(vocabulary):
        raise ValueError("Checkpoint config/vocabulary mismatch")
    head = SharedRetrievalContentHead(**CONFIG)
    head.load_state_dict(saved["state_dict"], strict=True)
    if _fingerprint(head) != entry["final_head_sha256"]:
        raise ValueError("Checkpoint tensor fingerprint mismatch")
    return head.to(device).eval().requires_grad_(False), path


def _details(suite, before, after):
    return [dict(case_id=q["case_id"], text=q["text"], bucket=q["bucket"],
                 expected=suite["descriptors"][q["expected_address"]],
                 pooled_prediction=suite["descriptors"][b["predicted_address"]],
                 composed_prediction=suite["descriptors"][a["predicted_address"]],
                 pooled_margin=b["expected_margin"], composed_margin=a["expected_margin"],
                 originally_wrong=not b["correct"], composed_correct=a["correct"])
            for q, b, a in zip(suite["queries"], before, after, strict=True)
            if not b["correct"] or not a["correct"]]


def run(*, c146_summary: Path, output_dir: Path) -> dict:
    from fold_lm.v05_benchmarks import gate_e_c139_hash_collision_diagnostic as c139
    from fold_lm.v05_benchmarks import gate_e_c143_frozen_factorial_audit as c143
    from fold_lm.v05_benchmarks import gate_e_c146_all_factor_alignment as c146
    output_dir.mkdir(parents=True, exist_ok=False)
    completed = []
    try:
        fixture = Path(__file__).parent / "fixtures/c138_compositional_alias_queries.json"
        manifest = c146_summary.parent / "evaluation-manifest.json"
        protected = {c146_summary: _sha(c146_summary), manifest: MANIFEST_SHA, fixture: QUERY_SHA,
                     Path("runs/chatgpt-last-result.json"): C37_SHA,
                     Path("runs/fixtures/v05-c-composition-20260921.pt"): FIXTURE_SHA}
        def check_files():
            for path, value in protected.items():
                if _sha(path) != value:
                    raise RuntimeError(f"Input/protected/checkpoint mismatch: {path}")
        check_files()
        rows = json.loads(fixture.read_text(encoding="utf-8"))["queries"]
        suite = json.loads(manifest.read_text(encoding="utf-8"))
        if suite != c143._build_suite(rows):
            raise RuntimeError("Manifest differs from fixed C143 generator")
        suite_copy = json.dumps(suite, sort_keys=True)
        records = _validate_prior(json.loads(c146_summary.read_text(encoding="utf-8")), suite, c146._audit_results)
        vocabulary = c139._training_vocabulary(rows)
        if len(vocabulary) != 49 or c139._fixture_oov_count(rows, vocabulary):
            raise RuntimeError("Vocabulary/OOV mismatch")
        if not torch.cuda.is_available():
            raise RuntimeError("Formal C147 checkpoint replay requires CUDA; no CPU fallback")
        torch.cuda.set_device(0)
        torch.set_num_threads(2)
        torch.set_float32_matmul_precision("highest")
        device = torch.device("cuda")
        def features(texts):
            return c139._collision_free_text_features(list(texts), vocabulary, device=device)
        qtexts = [q["text"] for q in suite["queries"]]
        dtexts = suite["descriptors"]
        labels = [q["expected_address"] for q in suite["queries"]]
        qf, df = features(qtexts), features(dtexts)
        oq = features([r["validation"] for r in rows])
        od = features([r["descriptor"] for r in rows])
        old_indices = [qtexts.index(r["validation"]) for r in rows]
        started = time.perf_counter()
        for index, source in enumerate(records, 1):
            seed = source["seed"]
            entry = source["arms"][SOURCE_ARM]
            print(f"[C147] model {index}/12 checkpoint load seed={seed} source={SOURCE_ARM}", flush=True)
            head, path = _load_head(c146_summary.parent, seed, entry, vocabulary, device)
            protected[path] = entry["checkpoint"]["sha256"]
            frozen = _fingerprint(head)
            old_before = c143._score(head, oq, od, list(range(12)))
            _replay(old_before, entry["original12"])
            before = []
            for start in range(0, 1728, 216):
                batch = c143._score(head, qf[start:start+216], df, labels[start:start+216])
                _replay(batch, entry["results"][start:start+216])
                before.extend(batch)
            print(f"[C147] model {index}/12 full1728_and_original12_replay_match=True", flush=True)
            encoded, cost = _compose(head, qtexts+dtexts, features)
            eq, ed = encoded[:1728], encoded[1728:]
            after = []
            for start in range(0, 1728, 216):
                with torch.inference_mode():
                    scores = eq[start:start+216] @ ed.T
                after.extend(_rank(scores, labels[start:start+216]))
                print(f"[C147] model {index}/12 mode=ENCODE_THEN_POOL audited={start+216}/1728 "
                      f"correct={sum(r['correct'] for r in after)} remaining={1512-start}", flush=True)
            with torch.inference_mode():
                old_after = _rank(eq[old_indices] @ ed[:12].T, list(range(12)))
            if _fingerprint(head) != frozen or json.dumps(suite, sort_keys=True) != suite_copy:
                raise RuntimeError("Evaluation mutated head/manifest")
            modes = {MODES[0]: dict(results=before, original12=old_before, metrics=c146._audit_results(before, suite)),
                     MODES[1]: dict(results=after, original12=old_after, metrics=c146._audit_results(after, suite))}
            pairs = _paired(before, after)
            detail = _details(suite, before, after)
            completed.append(dict(seed=seed, checkpoint_sha256=protected[path], frozen_head_sha256=frozen,
                source_training_alignment_accuracy=entry["training"]["training_alignment_accuracy"],
                modes=modes, paired=pairs, changed_or_wrong_cases=detail, composition_accounting=cost))
            print(f"[C147] model {index}/12 complete original_errors={sum(not r['correct'] for r in before)} "
                  f"composed_errors={sum(not r['correct'] for r in after)} rescued={pairs['rescued_errors']} "
                  f"new_errors={pairs['new_errors']} remaining_models={12-index}", flush=True)
            del head, encoded, eq, ed
        check_files()
        repeated = dict(descriptors=dtexts, queries=suite["queries"]*12)
        aggregates = {}
        for mode in MODES:
            all_rows = [r for record in completed for r in record["modes"][mode]["results"]]
            aggregates[mode] = c146._audit_results(all_rows, repeated)
            aggregates[mode]["full_model_pass_count"] = sum(_perfect(r["modes"][mode]["results"]) for r in completed)
            aggregates[mode]["original12_full_pass_count"] = sum(_perfect(r["modes"][mode]["original12"]) for r in completed)
        pairs = {k: sum(r["paired"][k] for r in completed) for k in completed[0]["paired"]}
        passed = (aggregates[MODES[1]]["full_model_pass_count"] == 12
                  and aggregates[MODES[1]]["original12_full_pass_count"] == 12)
        residual_cases = [dict(seed=r["seed"], **case) for r in completed
                          for case in r["changed_or_wrong_cases"] if case["originally_wrong"]]
        report = dict(experiment_id=EXPERIMENT_ID, stage=STAGE, status="PASS" if passed else "FAIL",
            diagnostic_execution_valid=True, production_runtime_modified=False, gate_e_candidate=False,
            commit_sha=subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
            C146_summary_sha256=protected[c146_summary], evaluation_manifest_sha256=MANIFEST_SHA,
            input_sha256={str(p): h for p, h in protected.items()},
            environment=dict(torch=str(torch.__version__), cuda=torch.version.cuda,
                             device=torch.cuda.get_device_name(0), precision="float32/highest"),
            summary=dict(source_seeds=list(SEEDS), source_arm=SOURCE_ARM, loaded_checkpoints=12,
                fresh_seed_count=0, additional_training_steps=0, inference_oracle_used=False,
                runtime_path_exercised=False, source_supervision="C146 explicit three-factor training",
                expression_segmentation="whitespace, hyphens retained; no typed slots",
                baseline_full_replay_cases=20736, treatment_full_ranking_cases=20736,
                original12_replay_cases=144, original12_treatment_cases=144,
                full_replay_match_rate=1.0, frozen_weights_preserved_rate=1.0,
                modes=aggregates, paired=pairs, original_11_error_cases=residual_cases,
                source_singleton_alignment_fit={axis: dict(min=min(r["source_training_alignment_accuracy"][axis] for r in completed),
                    max=max(r["source_training_alignment_accuracy"][axis] for r in completed)) for axis in AXES},
                composition_order_gate_passed=passed, wall_clock_seconds=time.perf_counter()-started),
            records=completed, limitations=[
                "Inference-only composition-rule intervention on fixed supervised C146 heads",
                "Encode-then-pool includes per-unit normalization/equal unit weighting, not an isolated nonlinear-layer ablation",
                "Whitespace boundaries align with this synthetic fixture's factor expressions; not automatic segmentation",
                "Hyphenated expressions still use the original feature tokenizer inside each unit",
                "No factor names/axis matching/alias dictionary/expected labels enter the encoder or candidate scorer",
                "Success is not automatically learned composition or a production-ready replacement",
                "A negative rejects sufficiency of this fixed composition rule, not all additive representations",
                "Same development fixture and models; no fresh-seed/task evidence; no expanded runtime test",
                "No coefficient/width/step sweep or selecting only the previously perfect heads; Gate E remains NOT PASSED"])
        tmp = output_dir / "summary.partial.json"
        tmp.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
        tmp.replace(output_dir / "summary.json")
        return report
    except Exception as exc:
        (output_dir / "invalid.json").write_text(json.dumps(dict(experiment_id=EXPERIMENT_ID,
            status="INVALID", diagnostic_execution_valid=False, error=str(exc), completed_models=len(completed)), indent=2), encoding="utf-8")
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description="Frozen C146 composition-order diagnostic")
    parser.add_argument("--c146-summary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(f"C147 prerequisite_summary = {args.c146_summary}", flush=True)
    print("C147 source = all 12 ALL_FACTOR_AUX heads; fresh_seeds=0; training_steps=0", flush=True)
    print("C147 changed = POOL_THEN_ENCODE -> ENCODE_THEN_POOL on both query and descriptor", flush=True)
    print("C147 typed_factor_matching=False; inference_alias_dictionary=False; runtime=False", flush=True)
    report = run(c146_summary=args.c146_summary, output_dir=args.output_dir)
    print("=== C147 RESULT ===", flush=True)
    print(json.dumps(dict(report, records="omitted; see summary.json"), indent=2, allow_nan=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
