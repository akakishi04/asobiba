from __future__ import annotations

import hashlib
import json
from pathlib import Path
import statistics

import torch
from torch.nn import functional as F

from fold_lm.v05.retrieval_adapter import PersistedStructuralRetrievalAdapter
from fold_lm.v05.retrieval_query import RetrievalAddressHead, address_to_structure, hashed_text_features
from fold_lm.v05_benchmarks import gate_e_c113_stale_eligibility_preflight as c113
from fold_lm.v05_benchmarks import gate_e_c135_bounded_retrieval_recovery as c135

EXPERIMENT_ID = "C136-v5e-learned-retrieval-query-formation"
SEEDS = (20261561, 20261562, 20261563)
ANSWER = 0
RETRIEVE = 2
VISIBLE_RETRIEVE = (0, 1, 0, 0)
SCHEMA = "decision-bit"
NEUTRAL_SEMANTICS = (1.0, 1.0)
FEATURE_DIM = 128
HIDDEN_DIM = 32
ADDRESS_COUNT = 8
TRAIN_STEPS = 320
LR = 0.02
CORPUS = Path(__file__).resolve().parent / "fixtures" / "c136_query_records.json"
QUERIES = Path(__file__).resolve().parent / "fixtures" / "c136_query_paraphrases.json"


def _sha(path: Path) -> str:
    return hashlib.file_digest(path.open("rb"), "sha256").hexdigest()


def _stats(values):
    return {
        "mean": statistics.mean(values),
        "median": statistics.median(values),
        "min": min(values),
        "max": max(values),
    }


def _load_query_fixture():
    payload = json.loads(QUERIES.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1 or type(payload.get("queries")) is not list:
        raise ValueError("invalid C136 query fixture")
    rows = payload["queries"]
    if len(rows) != ADDRESS_COUNT:
        raise ValueError("C136 requires exactly eight query-address rows")
    expected_keys = [f"q{i}" for i in range(ADDRESS_COUNT)]
    if [row.get("key") for row in rows] != expected_keys:
        raise ValueError("C136 query keys must be q0..q7 in address order")
    if [row.get("address") for row in rows] != list(range(ADDRESS_COUNT)):
        raise ValueError("C136 query addresses must be 0..7")
    for row in rows:
        train = row.get("train")
        validation = row.get("validation")
        if type(train) is not list or len(train) != 3 or any(not isinstance(text, str) or not text for text in train):
            raise ValueError("each C136 query row requires three training paraphrases")
        if not isinstance(validation, str) or not validation:
            raise ValueError("each C136 query row requires one validation paraphrase")
    return rows


def _load_expected_values():
    payload = json.loads(CORPUS.read_text(encoding="utf-8"))
    rows = payload.get("records")
    if payload.get("schema_version") != 1 or type(rows) is not list or len(rows) != ADDRESS_COUNT:
        raise ValueError("invalid C136 corpus fixture")
    return {row["key"]: int(row["evidence_value"]) for row in rows}


def _train_query_head(seed: int, device: torch.device, rows):
    train_texts = []
    labels = []
    for row in rows:
        for text in row["train"]:
            train_texts.append(text)
            labels.append(row["address"])
    features = hashed_text_features(train_texts, feature_dim=FEATURE_DIM, device=device)
    targets = torch.tensor(labels, dtype=torch.long, device=device)

    torch.manual_seed(seed + 1360)
    head = RetrievalAddressHead(
        feature_dim=FEATURE_DIM,
        hidden_dim=HIDDEN_DIM,
        address_count=ADDRESS_COUNT,
    ).to(device)
    opt = torch.optim.AdamW(head.parameters(), lr=LR, weight_decay=0.0)
    head.train()
    loss = None
    for _ in range(TRAIN_STEPS):
        opt.zero_grad(set_to_none=True)
        logits = head(features)
        loss = F.cross_entropy(logits, targets)
        if not torch.isfinite(loss):
            raise RuntimeError(f"C136 non-finite query-head loss seed={seed}")
        loss.backward()
        opt.step()
    head.eval()
    return head, float(loss.detach().item())


def _provenance_ok(evidence, stats, adapter) -> bool:
    return bool(
        evidence is not None
        and evidence.domain == "c136"
        and evidence.schema == SCHEMA
        and evidence.operations == ("READ_EVIDENCE",)
        and evidence.source_sha256 == adapter.source_sha256
        and evidence.index_fingerprint == adapter.index_fingerprint
        and stats.get("source_sha256") == adapter.source_sha256
        and stats.get("index_fingerprint") == adapter.index_fingerprint
        and stats.get("mode") == "exact"
    )


def _evaluate_seed(router, query_head, device, adapter, query_rows, expected_values, seed_index: int):
    rows = []
    total = len(query_rows)
    for case_index, row in enumerate(query_rows, start=1):
        expected_key = row["key"]
        expected_address = int(row["address"])
        query_text = row["validation"]

        initial_action = c113._predict(
            router,
            dependency=1,
            evidence_present=0,
            observed_hidden=0,
            visible_mask=VISIBLE_RETRIEVE,
            device=device,
        )

        features = hashed_text_features([query_text], feature_dim=FEATURE_DIM, device=device)
        with torch.inference_mode():
            predicted_address = int(query_head(features).argmax(dim=-1).item())
        structure = address_to_structure(predicted_address, address_count=ADDRESS_COUNT)

        evidence = None
        stats = {}
        if initial_action == RETRIEVE:
            evidence, stats = adapter.retrieve(
                structure,
                NEUTRAL_SEMANTICS,
                schema=SCHEMA,
                exact=True,
            )

        address_ok = predicted_address == expected_address
        hit_ok = bool(evidence is not None and evidence.key == expected_key)
        provenance_ok = _provenance_ok(evidence, stats, adapter)
        commit_count = int(initial_action == RETRIEVE and address_ok and hit_ok and provenance_ok)
        final_action = None
        if commit_count == 1:
            final_action = c113._predict(
                router,
                dependency=1,
                evidence_present=1,
                observed_hidden=evidence.evidence_value,
                visible_mask=VISIBLE_RETRIEVE,
                device=device,
            )
        evidence_correct = bool(
            evidence is not None
            and evidence.evidence_value == expected_values[expected_key]
        )
        passed = bool(
            initial_action == RETRIEVE
            and address_ok
            and hit_ok
            and provenance_ok
            and commit_count == 1
            and final_action == ANSWER
            and evidence_correct
            and stats.get("vectors_scored") == adapter.record_count
        )
        rows.append({
            "case": expected_key,
            "query_text": query_text,
            "expected_address": expected_address,
            "predicted_address": predicted_address,
            "initial_action": initial_action,
            "hit_key": None if evidence is None else evidence.key,
            "retrieved_value": None if evidence is None else evidence.evidence_value,
            "expected_value": expected_values[expected_key],
            "provenance_ok": provenance_ok,
            "commit_count": commit_count,
            "final_action": final_action,
            "vectors_scored": stats.get("vectors_scored"),
            "passed": passed,
        })
        print(
            f"[C136] seed {seed_index}/3 case {case_index}/{total} "
            f"key={expected_key} address={predicted_address} pass={passed} remaining={total-case_index}",
            flush=True,
        )
    return rows


def _metrics(rows, adapter):
    return {
        "scenario_pass_rate": sum(row["passed"] for row in rows) / len(rows),
        "router_retrieve_rate": sum(row["initial_action"] == RETRIEVE for row in rows) / len(rows),
        "heldout_query_address_accuracy": sum(row["predicted_address"] == row["expected_address"] for row in rows) / len(rows),
        "retrieval_key_accuracy": sum(row["hit_key"] == row["case"] for row in rows) / len(rows),
        "provenance_validation_rate": sum(row["provenance_ok"] for row in rows) / len(rows),
        "evidence_commit_once_rate": sum(row["commit_count"] == 1 for row in rows) / len(rows),
        "post_commit_answer_rate": sum(row["final_action"] == ANSWER for row in rows) / len(rows),
        "final_evidence_accuracy": sum(row["retrieved_value"] == row["expected_value"] for row in rows) / len(rows),
        "full_corpus_scored_rate": sum(row["vectors_scored"] == adapter.record_count for row in rows) / len(rows),
        "case_count": len(rows),
    }


def run(*, protected_result_path: Path, c135_summary_path: Path, output_dir: Path):
    prior = json.loads(c135_summary_path.read_text(encoding="utf-8"))
    if (
        prior.get("experiment_id") != c135.EXPERIMENT_ID
        or prior.get("status") != "PASS"
        or not prior.get("summary", {}).get("bounded_retrieval_exact_recovery_gate_passed")
    ):
        raise RuntimeError("C136 requires accepted C135")
    if not torch.cuda.is_available():
        raise RuntimeError("C136 requires CUDA")

    before = _sha(protected_result_path)
    adapter = PersistedStructuralRetrievalAdapter(CORPUS)
    query_rows = _load_query_fixture()
    expected_values = _load_expected_values()
    output_dir.mkdir(parents=True, exist_ok=False)

    device = torch.device("cuda")
    torch.cuda.set_device(0)
    torch.set_num_threads(2)
    torch.set_float32_matmul_precision("highest")

    records = []
    for seed_index, seed in enumerate(SEEDS, start=1):
        print(f"[C136] seed {seed_index}/3 router train start seed={seed}", flush=True)
        router, router_loss = c113._train_router(seed, device)
        print(f"[C136] seed {seed_index}/3 router train done loss={router_loss:.8f}", flush=True)
        print(f"[C136] seed {seed_index}/3 query-head train start", flush=True)
        query_head, query_loss = _train_query_head(seed, device, query_rows)
        print(f"[C136] seed {seed_index}/3 query-head train done loss={query_loss:.8f}", flush=True)

        rows = _evaluate_seed(
            router,
            query_head,
            device,
            adapter,
            query_rows,
            expected_values,
            seed_index,
        )
        m = _metrics(rows, adapter)
        m["accepted_c135_prerequisite_rate"] = 1.0
        deciding = [key for key in m if key.endswith("_rate") or key in ("heldout_query_address_accuracy", "retrieval_key_accuracy", "final_evidence_accuracy")]
        m["gate_passed"] = all(m[key] == 1.0 for key in deciding)
        records.append({
            "seed": seed,
            "router_final_loss": router_loss,
            "query_head_final_loss": query_loss,
            "metrics": m,
            "cases": rows,
            "validation_passed": bool(m["gate_passed"]),
        })
        print(
            f"[C136] seed {seed_index}/3 complete "
            f"address={m['heldout_query_address_accuracy']:.6f} "
            f"hit={m['retrieval_key_accuracy']:.6f} answer={m['post_commit_answer_rate']:.6f} "
            f"pass={m['gate_passed']}",
            flush=True,
        )

    after = _sha(protected_result_path)
    if before != after:
        raise RuntimeError("protected C37 result changed during C136")

    ms = [record["metrics"] for record in records]
    all_pass = all(record["validation_passed"] for record in records)
    keys = [key for key in ms[0] if key.endswith("_rate") or key in ("heldout_query_address_accuracy", "retrieval_key_accuracy", "final_evidence_accuracy")]
    summary = {
        "fresh_seeds": list(SEEDS),
        "validation_base": 3,
        "feature_dim": FEATURE_DIM,
        "hidden_dim": HIDDEN_DIM,
        "address_count": ADDRESS_COUNT,
        "train_paraphrases_per_address": 3,
        "heldout_paraphrases_per_address": 1,
        "case_count": ADDRESS_COUNT,
        "corpus_record_count": adapter.record_count,
        "corpus_sha256": adapter.source_sha256,
        "index_fingerprint": adapter.index_fingerprint,
        "query_fixture_sha256": _sha(QUERIES),
        **{key: _stats([m[key] for m in ms]) for key in keys},
        "all_validation_passed": all_pass,
        "learned_retrieval_query_formation_gate_passed": all_pass,
    }
    report = {
        "experiment_id": EXPERIMENT_ID,
        "stage": "V5-E-LEARNED-RETRIEVAL-QUERY-FORMATION",
        "status": "PASS" if all_pass else "FAIL",
        "summary": summary,
        "records": records,
        "C135_summary_sha256": _sha(c135_summary_path),
        "C37_result_sha256_before": before,
        "C37_result_sha256_after": after,
        "production_runtime_modified": True,
        "gate_e_candidate": False,
        "limitations": [
            "C136 is controlled eight-address retrieval, not open-domain query formation",
            "Held-out paraphrases retain the address-specific codeword seen during training",
            "The query head predicts a discrete retrieval address rather than a free continuous signature",
            "C136 does not establish natural-language semantic generalization to unseen entities or corpus growth",
        ],
    }
    (output_dir / "summary.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    return report
