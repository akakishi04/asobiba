from __future__ import annotations

import hashlib
import json
from pathlib import Path
import statistics

import torch
from torch.nn import functional as F

from fold_lm.v05.retrieval_adapter import PersistedStructuralRetrievalAdapter
from fold_lm.v05.retrieval_content import SharedRetrievalContentHead
from fold_lm.v05.retrieval_query import address_to_structure, hashed_text_features
from fold_lm.v05_benchmarks import gate_e_c113_stale_eligibility_preflight as c113
from fold_lm.v05_benchmarks import gate_e_c136_learned_query_formation as c136

EXPERIMENT_ID = "C137-v5e-content-addressed-corpus-growth"
SEEDS = (20261571, 20261572, 20261573)
ANSWER = 0
RETRIEVE = 2
VISIBLE_RETRIEVE = (0, 1, 0, 0)
SCHEMA = "decision-bit"
SEMANTICS = (1.0, 0.0)
FEATURE_DIM = 128
HIDDEN_DIM = 32
RESIDUAL_SCALE = 0.25
TRAIN_STEPS = 300
LR = 2e-3
LOGIT_SCALE = 10.0
CORPUS = Path(__file__).resolve().parent / "fixtures" / "c137_content_records.json"
QUERY_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "c137_content_queries.json"


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
        raise ValueError("invalid C137 query fixture schema")
    rows = payload.get("queries")
    if type(rows) is not list or len(rows) != 12:
        raise ValueError("C137 requires exactly 12 query records")
    if [row.get("key") for row in rows] != [f"q{i}" for i in range(12)]:
        raise ValueError("C137 query keys must be q0..q11 in order")
    train_rows = [row for row in rows if row.get("split") == "TRAIN_ENTITY"]
    unseen_rows = [row for row in rows if row.get("split") == "UNSEEN_ENTITY"]
    if len(train_rows) != 8 or len(unseen_rows) != 4:
        raise ValueError("C137 requires 8 train entities and 4 unseen entities")
    if any(len(row.get("train", [])) != 3 for row in train_rows):
        raise ValueError("train entities require three training paraphrases")
    if any(row.get("train") != [] for row in unseen_rows):
        raise ValueError("unseen entities must have zero training paraphrases")
    return rows


def _train_content_head(seed: int, rows: list[dict], device: torch.device):
    train_rows = [row for row in rows if row["split"] == "TRAIN_ENTITY"]
    descriptors = [row["descriptor"] for row in train_rows]
    query_texts = []
    labels = []
    for address, row in enumerate(train_rows):
        for text in row["train"]:
            query_texts.append(text)
            labels.append(address)

    query_features = hashed_text_features(query_texts, feature_dim=FEATURE_DIM, device=device)
    record_features = hashed_text_features(descriptors, feature_dim=FEATURE_DIM, device=device)
    targets = torch.tensor(labels, dtype=torch.long, device=device)

    torch.manual_seed(seed + 13700)
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
            raise RuntimeError(f"C137 non-finite content-head loss seed={seed}")
        loss.backward()
        opt.step()
    head.eval()
    return head, float(loss.detach().item())


def _corpus_values() -> dict[str, int]:
    payload = json.loads(CORPUS.read_text(encoding="utf-8"))
    return {row["key"]: int(row["evidence_value"]) for row in payload["records"]}


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
                SEMANTICS,
                schema=SCHEMA,
                exact=True,
            )

        provenance_ok = bool(
            evidence is not None
            and evidence.domain == "c137"
            and evidence.schema == SCHEMA
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
            f"[C137] seed {seed_index}/3 case {case_index}/{total} "
            f"split={row['split']} key={expected_key} predicted={predicted_address} "
            f"pass={passed} remaining={total-case_index}",
            flush=True,
        )
    return cases


def _metrics(cases, adapter):
    known = [row for row in cases if row["split"] == "TRAIN_ENTITY"]
    unseen = [row for row in cases if row["split"] == "UNSEEN_ENTITY"]
    return {
        "scenario_pass_rate": sum(row["passed"] for row in cases) / len(cases),
        "router_retrieve_rate": sum(row["initial_action"] == RETRIEVE for row in cases) / len(cases),
        "known_entity_address_accuracy": sum(row["predicted_address"] == row["expected_address"] for row in known) / len(known),
        "unseen_entity_address_accuracy": sum(row["predicted_address"] == row["expected_address"] for row in unseen) / len(unseen),
        "unseen_entity_retrieval_key_accuracy": sum(row["hit_key"] == row["key"] for row in unseen) / len(unseen),
        "overall_retrieval_key_accuracy": sum(row["hit_key"] == row["key"] for row in cases) / len(cases),
        "provenance_validation_rate": sum(row["provenance_ok"] for row in cases) / len(cases),
        "evidence_commit_once_rate": sum(row["commit_count"] == 1 for row in cases) / len(cases),
        "post_commit_answer_rate": sum(row["final_action"] == ANSWER for row in cases) / len(cases),
        "final_evidence_accuracy": sum(row["retrieved_value"] == row["expected_value"] for row in cases) / len(cases),
        "dynamic_candidate_growth_rate": float(adapter.record_count == 12 and len(known) == 8 and len(unseen) == 4),
        "case_count": len(cases),
        "train_entity_count": len(known),
        "unseen_entity_count": len(unseen),
    }


def run(*, protected_result_path: Path, c136_summary_path: Path, output_dir: Path):
    prior = json.loads(c136_summary_path.read_text(encoding="utf-8"))
    if (
        prior.get("experiment_id") != c136.EXPERIMENT_ID
        or prior.get("status") != "PASS"
        or not prior.get("summary", {}).get("learned_retrieval_query_formation_gate_passed")
    ):
        raise RuntimeError("C137 requires accepted C136")
    if not torch.cuda.is_available():
        raise RuntimeError("C137 requires CUDA")

    before = _sha(protected_result_path)
    rows = _load_fixture()
    adapter = PersistedStructuralRetrievalAdapter(CORPUS)
    output_dir.mkdir(parents=True, exist_ok=False)
    device = torch.device("cuda")
    torch.cuda.set_device(0)
    torch.set_num_threads(2)
    torch.set_float32_matmul_precision("highest")

    records = []
    for seed_index, seed in enumerate(SEEDS, start=1):
        print(f"[C137] seed {seed_index}/3 router train start seed={seed}", flush=True)
        router, router_loss = c113._train_router(seed, device)
        print(f"[C137] seed {seed_index}/3 router train done loss={router_loss:.8f}", flush=True)
        print(f"[C137] seed {seed_index}/3 content-head train start train_entities=8 candidates=8", flush=True)
        head, content_loss = _train_content_head(seed, rows, device)
        print(f"[C137] seed {seed_index}/3 content-head train done loss={content_loss:.8f}", flush=True)
        print(f"[C137] seed {seed_index}/3 evaluation catalog grown candidates=12 unseen_entities=4", flush=True)
        cases = _evaluate_seed(router, head, device, adapter, rows, seed_index)
        m = _metrics(cases, adapter)
        m["accepted_c136_prerequisite_rate"] = 1.0
        deciding = [key for key in m if key.endswith("_rate") or key.endswith("_accuracy")]
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
            f"[C137] seed {seed_index}/3 complete known={m['known_entity_address_accuracy']:.6f} "
            f"unseen={m['unseen_entity_address_accuracy']:.6f} "
            f"unseen_hit={m['unseen_entity_retrieval_key_accuracy']:.6f} pass={m['gate_passed']}",
            flush=True,
        )

    after = _sha(protected_result_path)
    if before != after:
        raise RuntimeError("protected C37 result changed during C137")

    ms = [record["metrics"] for record in records]
    all_pass = all(record["validation_passed"] for record in records)
    keys = [key for key in ms[0] if key.endswith("_rate") or key.endswith("_accuracy")]
    summary = {
        "fresh_seeds": list(SEEDS),
        "feature_dim": FEATURE_DIM,
        "hidden_dim": HIDDEN_DIM,
        "residual_scale": RESIDUAL_SCALE,
        "training_candidate_count": 8,
        "evaluation_candidate_count": 12,
        "unseen_entity_count": 4,
        "train_paraphrases_per_known_entity": 3,
        "validation_queries": 12,
        "corpus_record_count": adapter.record_count,
        "corpus_sha256": adapter.source_sha256,
        "index_fingerprint": adapter.index_fingerprint,
        "query_fixture_sha256": _sha(QUERY_FIXTURE),
        **{key: _stats([m[key] for m in ms]) for key in keys},
        "all_validation_passed": all_pass,
        "content_addressed_corpus_growth_gate_passed": all_pass,
    }
    report = {
        "experiment_id": EXPERIMENT_ID,
        "stage": "V5-E-CONTENT-ADDRESSED-CORPUS-GROWTH",
        "status": "PASS" if all_pass else "FAIL",
        "summary": summary,
        "records": records,
        "C136_summary_sha256": _sha(c136_summary_path),
        "C37_result_sha256_before": before,
        "C37_result_sha256_after": after,
        "production_runtime_modified": True,
        "gate_e_candidate": False,
        "limitations": [
            "C137 tests unseen entity labels through shared lexical content, not unseen semantic aliases",
            "Record descriptors and validation queries share the unseen entity token",
            "C137 remains a controlled small corpus and uses exact evidence retrieval after candidate selection",
            "C137 establishes dynamic candidate-set growth, not open-domain retrieval quality",
        ],
    }
    (output_dir / "summary.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    return report
