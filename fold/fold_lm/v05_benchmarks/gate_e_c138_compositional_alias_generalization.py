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

EXPERIMENT_ID = "C138-v5e-compositional-alias-generalization"
SEEDS = (20261581, 20261582, 20261583)
ANSWER = 0
RETRIEVE = 2
VISIBLE_RETRIEVE = (0, 1, 0, 0)
FEATURE_DIM = 128
HIDDEN_DIM = 64
RESIDUAL_SCALE = 1.0
TRAIN_STEPS = 600
LR = 2e-3
LOGIT_SCALE = 12.0
QUERY_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "c138_compositional_alias_queries.json"
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


def _load_fixture() -> list[dict]:
    payload = json.loads(QUERY_FIXTURE.read_text(encoding="utf-8"))
    if type(payload) is not dict or payload.get("schema_version") != 1:
        raise ValueError("invalid C138 query fixture schema")
    rows = payload.get("queries")
    if type(rows) is not list or len(rows) != 12:
        raise ValueError("C138 requires exactly 12 query records")
    if [row.get("key") for row in rows] != [f"q{i}" for i in range(12)]:
        raise ValueError("C138 query keys must be q0..q11 in order")
    known = [row for row in rows if row.get("split") == "TRAIN_COMBINATION"]
    unseen = [row for row in rows if row.get("split") == "UNSEEN_COMBINATION"]
    if len(known) != 8 or len(unseen) != 4:
        raise ValueError("C138 requires 8 train combinations and 4 unseen combinations")
    if any(len(row.get("train", [])) != 3 for row in known):
        raise ValueError("train combinations require three training queries")
    if any(row.get("train") != [] for row in unseen):
        raise ValueError("unseen combinations must have zero training queries")
    return rows


def _token_set(text: str) -> set[str]:
    return set(TOKEN_RE.findall(text.lower()))


def _fixture_controls(rows: list[dict]) -> tuple[float, float]:
    zero_overlap = float(all(not (_token_set(row["validation"]) & _token_set(row["descriptor"])) for row in rows))
    training_tokens: set[str] = set()
    for row in rows:
        for text in row["train"]:
            training_tokens.update(_token_set(text))
    unseen = [row for row in rows if row["split"] == "UNSEEN_COMBINATION"]
    alias_coverage = float(all(_token_set(row["validation"]) <= training_tokens for row in unseen))
    return zero_overlap, alias_coverage


def _train_content_head(seed: int, rows: list[dict], device: torch.device):
    known = [row for row in rows if row["split"] == "TRAIN_COMBINATION"]
    descriptors = [row["descriptor"] for row in known]
    query_texts = []
    labels = []
    for address, row in enumerate(known):
        for text in row["train"]:
            query_texts.append(text)
            labels.append(address)

    query_features = hashed_text_features(query_texts, feature_dim=FEATURE_DIM, device=device)
    record_features = hashed_text_features(descriptors, feature_dim=FEATURE_DIM, device=device)
    targets = torch.tensor(labels, dtype=torch.long, device=device)

    torch.manual_seed(seed + 13800)
    head = SharedRetrievalContentHead(
        feature_dim=FEATURE_DIM,
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
            raise RuntimeError(f"C138 non-finite content-head loss seed={seed}")
        loss.backward()
        opt.step()
    head.eval()
    return head, float(loss.detach().item())


def _corpus_values() -> dict[str, int]:
    payload = json.loads(c137.CORPUS.read_text(encoding="utf-8"))
    return {row["key"]: int(row["evidence_value"]) for row in payload["records"]}


def _raw_unseen_accuracy(rows: list[dict], device: torch.device) -> float:
    descriptors = hashed_text_features([row["descriptor"] for row in rows], feature_dim=FEATURE_DIM, device=device)
    queries = hashed_text_features([row["validation"] for row in rows], feature_dim=FEATURE_DIM, device=device)
    predicted = (queries @ descriptors.transpose(0, 1)).argmax(dim=-1)
    unseen_indices = [i for i, row in enumerate(rows) if row["split"] == "UNSEEN_COMBINATION"]
    expected = torch.tensor(unseen_indices, dtype=torch.long, device=device)
    return float((predicted[unseen_indices] == expected).float().mean().item())


def _evaluate_seed(router, head, device, adapter, rows, seed_index: int):
    values = _corpus_values()
    all_descriptors = [row["descriptor"] for row in rows]
    record_features = hashed_text_features(all_descriptors, feature_dim=FEATURE_DIM, device=device)
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
        query_features = hashed_text_features([row["validation"]], feature_dim=FEATURE_DIM, device=device)
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
            f"[C138] seed {seed_index}/3 case {case_index}/{total} split={row['split']} "
            f"key={expected_key} predicted={predicted_address} pass={passed} remaining={total-case_index}",
            flush=True,
        )
    return cases


def _metrics(cases, adapter, zero_overlap: float, alias_coverage: float, raw_unseen: float):
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
        "zero_lexical_overlap_rate": zero_overlap,
        "unseen_alias_training_coverage_rate": alias_coverage,
        "raw_baseline_not_perfect_rate": float(raw_unseen < 1.0),
        "raw_unseen_baseline_accuracy_value": raw_unseen,
        "dynamic_candidate_growth_rate": float(adapter.record_count == 12 and len(known) == 8 and len(unseen) == 4),
        "case_count": len(cases),
    }


def run(*, protected_result_path: Path, c137_summary_path: Path, output_dir: Path):
    prior = json.loads(c137_summary_path.read_text(encoding="utf-8"))
    if (
        prior.get("experiment_id") != c137.EXPERIMENT_ID
        or prior.get("status") != "PASS"
        or not prior.get("summary", {}).get("content_addressed_corpus_growth_gate_passed")
    ):
        raise RuntimeError("C138 requires accepted C137")
    if not torch.cuda.is_available():
        raise RuntimeError("C138 requires CUDA")

    before = _sha(protected_result_path)
    rows = _load_fixture()
    zero_overlap, alias_coverage = _fixture_controls(rows)
    adapter = PersistedStructuralRetrievalAdapter(c137.CORPUS)
    output_dir.mkdir(parents=True, exist_ok=False)
    device = torch.device("cuda")
    torch.cuda.set_device(0)
    torch.set_num_threads(2)
    torch.set_float32_matmul_precision("highest")
    raw_unseen = _raw_unseen_accuracy(rows, device)

    records = []
    for seed_index, seed in enumerate(SEEDS, start=1):
        print(f"[C138] seed {seed_index}/3 router train start seed={seed}", flush=True)
        router, router_loss = c113._train_router(seed, device)
        print(f"[C138] seed {seed_index}/3 router train done loss={router_loss:.8f}", flush=True)
        print(f"[C138] seed {seed_index}/3 content-head train start train_combinations=8 candidates=8", flush=True)
        head, content_loss = _train_content_head(seed, rows, device)
        print(f"[C138] seed {seed_index}/3 content-head train done loss={content_loss:.8f}", flush=True)
        print(
            f"[C138] seed {seed_index}/3 evaluation candidates=12 unseen_combinations=4 "
            f"raw_unseen={raw_unseen:.6f}",
            flush=True,
        )
        cases = _evaluate_seed(router, head, device, adapter, rows, seed_index)
        m = _metrics(cases, adapter, zero_overlap, alias_coverage, raw_unseen)
        m["accepted_c137_prerequisite_rate"] = 1.0
        deciding = [
            key for key in m
            if key.endswith("_rate") or key in (
                "known_combination_accuracy",
                "unseen_combination_accuracy",
                "unseen_retrieval_key_accuracy",
                "overall_retrieval_key_accuracy",
                "final_evidence_accuracy",
            )
        ]
        m["gate_passed"] = all(m[key] == 1.0 for key in deciding)
        records.append({
            "seed": seed,
            "router_final_loss": router_loss,
            "content_head_final_loss": content_loss,
            "metrics": m,
            "cases": cases,
            "validation_passed": bool(m["gate_passed"]),
        })
        print(
            f"[C138] seed {seed_index}/3 complete known={m['known_combination_accuracy']:.6f} "
            f"unseen={m['unseen_combination_accuracy']:.6f} "
            f"unseen_hit={m['unseen_retrieval_key_accuracy']:.6f} pass={m['gate_passed']}",
            flush=True,
        )

    after = _sha(protected_result_path)
    if before != after:
        raise RuntimeError("protected C37 result changed during C138")

    ms = [record["metrics"] for record in records]
    all_pass = all(record["validation_passed"] for record in records)
    summary_keys = [
        key for key in ms[0]
        if key.endswith("_rate") or key.endswith("_accuracy") or key.endswith("_value")
    ]
    summary = {
        "fresh_seeds": list(SEEDS),
        "feature_dim": FEATURE_DIM,
        "hidden_dim": HIDDEN_DIM,
        "residual_scale": RESIDUAL_SCALE,
        "training_candidate_count": 8,
        "evaluation_candidate_count": 12,
        "unseen_combination_count": 4,
        "train_queries_per_known_combination": 3,
        "validation_queries": 12,
        "corpus_record_count": adapter.record_count,
        "corpus_sha256": adapter.source_sha256,
        "index_fingerprint": adapter.index_fingerprint,
        "query_fixture_sha256": _sha(QUERY_FIXTURE),
        **{key: _stats([m[key] for m in ms]) for key in summary_keys},
        "all_validation_passed": all_pass,
        "compositional_alias_generalization_gate_passed": all_pass,
    }
    report = {
        "experiment_id": EXPERIMENT_ID,
        "stage": "V5-E-COMPOSITIONAL-ALIAS-GENERALIZATION",
        "status": "PASS" if all_pass else "FAIL",
        "summary": summary,
        "records": records,
        "C137_summary_sha256": _sha(c137_summary_path),
        "C37_result_sha256_before": before,
        "C37_result_sha256_after": after,
        "production_runtime_modified": False,
        "gate_e_candidate": False,
        "limitations": [
            "C138 uses a controlled attribute-composition vocabulary rather than open-domain semantics",
            "All unseen-combination alias tokens appear somewhere in training; only their combination is held out",
            "C138 reuses the C137 persisted corpus and exact retrieval after candidate selection",
            "A valid C138 failure is scientific evidence against compositional generalization of the current shared content head, not an execution failure",
        ],
    }
    (output_dir / "summary.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    return report
