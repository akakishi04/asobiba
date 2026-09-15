from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import statistics

import torch
from torch.nn import functional as F

from fold_lm.v05.retrieval_adapter import PersistedStructuralRetrievalAdapter
from fold_lm.v05.retrieval_content import SharedRetrievalContentHead
from fold_lm.v05.retrieval_query import address_to_structure, hashed_text_features
from fold_lm.v05_benchmarks import gate_e_c113_stale_eligibility_preflight as c113
from fold_lm.v05_benchmarks import gate_e_c137_content_addressed_corpus_growth as c137
from fold_lm.v05_benchmarks import gate_e_c138_compositional_alias_generalization as c138

EXPERIMENT_ID = "C139-v5e-hash-collision-composition-diagnostic"
SEEDS = (20261591, 20261592, 20261593)
ANSWER = 0
RETRIEVE = 2
VISIBLE_RETRIEVE = (0, 1, 0, 0)
HIDDEN_DIM = c138.HIDDEN_DIM
RESIDUAL_SCALE = c138.RESIDUAL_SCALE
TRAIN_STEPS = c138.TRAIN_STEPS
LR = c138.LR
LOGIT_SCALE = c138.LOGIT_SCALE
TOKEN_RE = re.compile(r"[a-z0-9]+")


def _sha(path: Path) -> str:
    return hashlib.file_digest(path.open("rb"), "sha256").hexdigest()


def _stats(values):
    return {
        "mean": statistics.mean(values),
        "median": statistics.median(values),
        "min": min(values),
        "max": max(values),
    }


def _tokens(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())


def _training_vocabulary(rows: list[dict]) -> tuple[str, ...]:
    """Build the diagnostic vocabulary from training data only.

    No validation label or held-out combination is needed to allocate a token.
    C138 already requires every held-out alias token and every canonical factor
    value to occur somewhere in the training split.
    """
    known = [row for row in rows if row["split"] == "TRAIN_COMBINATION"]
    vocabulary: set[str] = set()
    for row in known:
        vocabulary.update(_tokens(row["descriptor"]))
        for text in row["train"]:
            vocabulary.update(_tokens(text))
    if not vocabulary:
        raise RuntimeError("C139 training vocabulary is empty")
    return tuple(sorted(vocabulary))


def _collision_free_text_features(
    texts: list[str],
    vocabulary: tuple[str, ...],
    *,
    device: torch.device,
) -> torch.Tensor:
    index = {token: i for i, token in enumerate(vocabulary)}
    result = torch.zeros(len(texts), len(vocabulary), dtype=torch.float32, device=device)
    for row_index, text in enumerate(texts):
        tokens = _tokens(text)
        if not tokens:
            raise ValueError("C139 text contains no tokens")
        for token in tokens:
            if token not in index:
                raise KeyError(f"C139 out-of-vocabulary token: {token}")
            result[row_index, index[token]] += 1.0
    return F.normalize(result, dim=-1)


def _fixture_oov_count(rows: list[dict], vocabulary: tuple[str, ...]) -> int:
    allowed = set(vocabulary)
    count = 0
    for row in rows:
        for text in (row["descriptor"], row["validation"]):
            count += sum(token not in allowed for token in _tokens(text))
    return count


def _hash_collision_buckets(rows: list[dict], feature_dim: int = c138.FEATURE_DIM) -> dict[int, tuple[str, ...]]:
    vocabulary = _training_vocabulary(rows)
    buckets: dict[int, list[str]] = {}
    for token in vocabulary:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        bucket = int.from_bytes(digest[:4], "little") % feature_dim
        buckets.setdefault(bucket, []).append(token)
    return {
        bucket: tuple(sorted(tokens))
        for bucket, tokens in buckets.items()
        if len(tokens) > 1
    }


def _train_content_head(seed: int, rows: list[dict], vocabulary: tuple[str, ...], device: torch.device):
    known = [row for row in rows if row["split"] == "TRAIN_COMBINATION"]
    descriptors = [row["descriptor"] for row in known]
    query_texts: list[str] = []
    labels: list[int] = []
    for address, row in enumerate(known):
        for text in row["train"]:
            query_texts.append(text)
            labels.append(address)

    query_features = _collision_free_text_features(query_texts, vocabulary, device=device)
    record_features = _collision_free_text_features(descriptors, vocabulary, device=device)
    targets = torch.tensor(labels, dtype=torch.long, device=device)

    torch.manual_seed(seed + 13900)
    head = SharedRetrievalContentHead(
        feature_dim=len(vocabulary),
        hidden_dim=HIDDEN_DIM,
        residual_scale=RESIDUAL_SCALE,
    ).to(device)
    opt = torch.optim.AdamW(head.parameters(), lr=LR, weight_decay=0.0)
    head.train()
    loss = None
    for _ in range(TRAIN_STEPS):
        opt.zero_grad(set_to_none=True)
        logits = head.scores(query_features, record_features) * LOGIT_SCALE
        loss = F.cross_entropy(logits, targets)
        if not torch.isfinite(loss):
            raise RuntimeError(f"C139 non-finite content-head loss seed={seed}")
        loss.backward()
        opt.step()
    head.eval()
    return head, float(loss.detach().item())


def _raw_unseen_accuracy(rows: list[dict], vocabulary: tuple[str, ...], device: torch.device) -> float:
    descriptors = _collision_free_text_features(
        [row["descriptor"] for row in rows], vocabulary, device=device
    )
    queries = _collision_free_text_features(
        [row["validation"] for row in rows], vocabulary, device=device
    )
    predicted = (queries @ descriptors.transpose(0, 1)).argmax(dim=-1)
    unseen_indices = [i for i, row in enumerate(rows) if row["split"] == "UNSEEN_COMBINATION"]
    expected = torch.tensor(unseen_indices, dtype=torch.long, device=device)
    return float((predicted[unseen_indices] == expected).float().mean().item())


def _corpus_values() -> dict[str, int]:
    payload = json.loads(c137.CORPUS.read_text(encoding="utf-8"))
    return {row["key"]: int(row["evidence_value"]) for row in payload["records"]}


def _evaluate_seed(router, head, device, adapter, rows, vocabulary, seed_index: int):
    values = _corpus_values()
    record_features = _collision_free_text_features(
        [row["descriptor"] for row in rows], vocabulary, device=device
    )
    cases = []
    total = len(rows)

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
        query_features = _collision_free_text_features(
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
        cases.append({
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
        })
        print(
            f"[C139] seed {seed_index}/3 case {case_index}/{total} "
            f"split={row['split']} key={expected_key} predicted={predicted_address} "
            f"pass={passed} remaining={total-case_index}",
            flush=True,
        )
    return cases


def _metrics(cases, adapter, *, oov_count: int, collision_count: int, raw_unseen: float):
    known = [row for row in cases if row["split"] == "TRAIN_COMBINATION"]
    unseen = [row for row in cases if row["split"] == "UNSEEN_COMBINATION"]
    return {
        "scenario_pass_rate": sum(row["passed"] for row in cases) / len(cases),
        "router_retrieve_rate": sum(row["initial_action"] == RETRIEVE for row in cases) / len(cases),
        "known_combination_accuracy": sum(row["predicted_address"] == row["expected_address"] for row in known) / len(known),
        "unseen_combination_accuracy": sum(row["predicted_address"] == row["expected_address"] for row in unseen) / len(unseen),
        "unseen_retrieval_key_accuracy": sum(row["hit_key"] == row["key"] for row in unseen) / len(unseen),
        "overall_retrieval_key_accuracy": sum(row["hit_key"] == row["key"] for row in cases) / len(cases),
        "provenance_validation_rate": sum(row["provenance_ok"] for row in cases) / len(cases),
        "evidence_commit_once_rate": sum(row["commit_count"] == 1 for row in cases) / len(cases),
        "post_commit_answer_rate": sum(row["final_action"] == ANSWER for row in cases) / len(cases),
        "final_evidence_accuracy": sum(row["retrieved_value"] == row["expected_value"] for row in cases) / len(cases),
        "collision_free_feature_rate": float(oov_count == 0),
        "c138_collision_control_rate": float(collision_count > 0),
        "raw_collision_free_baseline_not_perfect_rate": float(raw_unseen < 1.0),
        "dynamic_candidate_growth_rate": float(adapter.record_count == 12 and len(known) == 8 and len(unseen) == 4),
        "case_count": len(cases),
    }


def run(*, protected_result_path: Path, c138_summary_path: Path, output_dir: Path):
    prior = json.loads(c138_summary_path.read_text(encoding="utf-8"))
    summary = prior.get("summary", {})
    if (
        prior.get("experiment_id") != c138.EXPERIMENT_ID
        or prior.get("status") != "FAIL"
        or bool(summary.get("compositional_alias_generalization_gate_passed"))
        or summary.get("known_combination_accuracy", {}).get("min") != 1.0
        or summary.get("zero_lexical_overlap_rate", {}).get("min") != 1.0
        or summary.get("accepted_c137_prerequisite_rate", {}).get("min") != 1.0
    ):
        raise RuntimeError("C139 requires the accepted valid-negative C138 summary")
    if not torch.cuda.is_available():
        raise RuntimeError("C139 requires CUDA")

    before = _sha(protected_result_path)
    rows = c138._load_fixture()
    vocabulary = _training_vocabulary(rows)
    oov_count = _fixture_oov_count(rows, vocabulary)
    collisions = _hash_collision_buckets(rows)
    amber_red_collision = any({"amber", "red"}.issubset(set(tokens)) for tokens in collisions.values())
    if oov_count != 0:
        raise RuntimeError(f"C139 collision-free diagnostic has OOV tokens: {oov_count}")
    if not amber_red_collision:
        raise RuntimeError("C139 expected C138 amber/red hash collision was not reproduced")

    adapter = PersistedStructuralRetrievalAdapter(c137.CORPUS)
    output_dir.mkdir(parents=True, exist_ok=False)
    device = torch.device("cuda")
    torch.cuda.set_device(0)
    torch.set_num_threads(2)
    torch.set_float32_matmul_precision("highest")

    print(
        f"[C139] diagnostic vocabulary={len(vocabulary)} c138_collision_buckets={len(collisions)} "
        f"oov={oov_count} amber_red_collision={amber_red_collision}",
        flush=True,
    )

    records = []
    for seed_index, seed in enumerate(SEEDS, start=1):
        print(f"[C139] seed {seed_index}/3 router train start seed={seed}", flush=True)
        router, router_loss = c113._train_router(seed, device)
        print(f"[C139] seed {seed_index}/3 router train done loss={router_loss:.8f}", flush=True)
        print(
            f"[C139] seed {seed_index}/3 content-head train start "
            f"encoding=collision_free_bow dim={len(vocabulary)}",
            flush=True,
        )
        head, content_loss = _train_content_head(seed, rows, vocabulary, device)
        print(f"[C139] seed {seed_index}/3 content-head train done loss={content_loss:.8f}", flush=True)
        raw_unseen = _raw_unseen_accuracy(rows, vocabulary, device)
        print(
            f"[C139] seed {seed_index}/3 evaluation candidates=12 unseen_combinations=4 "
            f"raw_collision_free_unseen={raw_unseen:.6f}",
            flush=True,
        )
        cases = _evaluate_seed(router, head, device, adapter, rows, vocabulary, seed_index)
        m = _metrics(
            cases,
            adapter,
            oov_count=oov_count,
            collision_count=len(collisions),
            raw_unseen=raw_unseen,
        )
        m["accepted_c138_valid_negative_rate"] = 1.0
        deciding = [key for key in m if key.endswith("_rate") or key.endswith("_accuracy")]
        m["gate_passed"] = all(m[key] == 1.0 for key in deciding)
        records.append({
            "seed": seed,
            "router_final_loss": router_loss,
            "content_head_final_loss": content_loss,
            "raw_collision_free_unseen_accuracy": raw_unseen,
            "metrics": m,
            "cases": cases,
            "validation_passed": bool(m["gate_passed"]),
        })
        print(
            f"[C139] seed {seed_index}/3 complete known={m['known_combination_accuracy']:.6f} "
            f"unseen={m['unseen_combination_accuracy']:.6f} "
            f"unseen_hit={m['unseen_retrieval_key_accuracy']:.6f} pass={m['gate_passed']}",
            flush=True,
        )

    after = _sha(protected_result_path)
    if before != after:
        raise RuntimeError("protected C37 result changed during C139")

    ms = [record["metrics"] for record in records]
    all_pass = all(record["validation_passed"] for record in records)
    keys = [key for key in ms[0] if key.endswith("_rate") or key.endswith("_accuracy")]
    report_summary = {
        "fresh_seeds": list(SEEDS),
        "encoding": "collision_free_training_vocabulary_bow",
        "feature_dim": len(vocabulary),
        "hidden_dim": HIDDEN_DIM,
        "residual_scale": RESIDUAL_SCALE,
        "training_candidate_count": 8,
        "evaluation_candidate_count": 12,
        "unseen_combination_count": 4,
        "c138_hash_feature_dim": c138.FEATURE_DIM,
        "c138_hash_collision_bucket_count": len(collisions),
        "c138_amber_red_collision": amber_red_collision,
        "diagnostic_oov_count": oov_count,
        "raw_collision_free_unseen_accuracy": _stats(
            [record["raw_collision_free_unseen_accuracy"] for record in records]
        ),
        **{key: _stats([m[key] for m in ms]) for key in keys},
        "all_validation_passed": all_pass,
        "hash_collision_composition_diagnostic_gate_passed": all_pass,
    }
    report = {
        "experiment_id": EXPERIMENT_ID,
        "stage": "V5-E-HASH-COLLISION-COMPOSITION-DIAGNOSTIC",
        "status": "PASS" if all_pass else "FAIL",
        "summary": report_summary,
        "records": records,
        "C138_summary_sha256": _sha(c138_summary_path),
        "C37_result_sha256_before": before,
        "C37_result_sha256_after": after,
        "production_runtime_modified": False,
        "gate_e_candidate": False,
        "limitations": [
            "C139 is a diagnostic benchmark and does not change the production text feature front end",
            "Collision-free dimensions are allocated from training vocabulary only and are not a scalable tokenizer design",
            "C139 keeps the C138 pooled bag-of-token representation and SharedRetrievalContentHead",
            "A C139 pass would identify C138 hash collisions as a material confound, not prove open-domain compositional semantics",
            "A C139 failure would show the C138 compositional failure persists even after removing hash collisions",
        ],
    }
    (output_dir / "summary.json").write_text(
        json.dumps(report, indent=2, allow_nan=False), encoding="utf-8"
    )
    return report
