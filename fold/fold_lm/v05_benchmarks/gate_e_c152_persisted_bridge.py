"""C152: frozen C151 selection -> real persisted evidence, with reordered catalogs.

Engineering integration, not new learning or open-set relevance verification.
No router, evidence commit, ANSWER, miss recovery or production modification.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path, PureWindowsPath
import subprocess
import time

import torch

EXPERIMENT_ID = "C152-v5e-frozen-persisted-retrieval-bridge"
STAGE = "V5-E-FROZEN-PERSISTED-RETRIEVAL-BRIDGE"
SOURCE_ID = "C151-v5e-cross-split-replication"
SOURCE_COMMIT = "1e8c4bfa18f3c28a654e6530ac56909a484411fb"
SOURCE_SHA = "d2b48acb36d28f0422d09067cc23af882c812d020a00ccfc8c6e8286fd896afa"
MANIFEST_SHA = "5a19de10d8152ac262846682a79a13bb942eeacd7dca979afb09b70170ebdd65"
PLAN_SHA = "db65d4754e465c55bfc19438f9d50324bb49e928911a53643deddc531625f4c0"
QUERY_SHA = "9235f8af27ba7c4c8b0b01d6243f3970b0013358f92a5947aa245a7ac2981aa2"
C37_SHA = "fd4a8da897bdaea9d103a252e30212c7ff842d23300d7c837333e146dee51931"
FIXTURE_SHA = "a52f8209703149407580f7e2965b61b78653030ee992af6d759865736741ca9e"
CONFIG = dict(feature_dim=49, hidden_dim=64, residual_scale=1.0)
ARMS = ("WITHIN_FACTOR", "GLOBAL_CONCEPT")
ORDERS = ("CANONICAL", "PERMUTED")
SEEDS = tuple(range(20261721, 20261733))
DOMAIN, SCHEMA = "c152", "c152-descriptor-handle-v1"
OPERATIONS = ("READ_EVIDENCE",)
REPLAY_ATOL = 1e-5


def _sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _bytes(value) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def _fingerprint(head) -> str:
    h = hashlib.sha256()
    for name, tensor in sorted(head.state_dict().items()):
        h.update(name.encode()); h.update(str(tuple(tensor.shape)).encode()); h.update(str(tensor.dtype).encode())
        h.update(tensor.detach().cpu().contiguous().numpy().tobytes())
    return h.hexdigest()


def _key(descriptor: str) -> str:
    return "c152-" + hashlib.sha256(descriptor.encode("utf-8")).hexdigest()


def _snapshot_payloads(descriptors: list[str], order: str) -> tuple[dict, list[dict]]:
    """Descriptors only. No query/expected-label/seed interface or evidence in catalog."""
    if order not in ORDERS or len(descriptors) < 2 or len(set(descriptors)) != len(descriptors):
        raise ValueError("Distinct descriptors and a registered order are required")
    if any(not isinstance(d, str) or not d.strip() for d in descriptors):
        raise ValueError("Nonempty descriptors required")
    # Stable identity signatures are catalog metadata, not a learned fixed classifier.
    slots = {d: i for i, d in enumerate(sorted(descriptors))}
    catalog, records = [], []
    for d in descriptors:
        structure = [float(i == slots[d]) for i in range(len(descriptors))]
        handle = dict(key=_key(d), domain=DOMAIN, schema=SCHEMA, structure=structure,
                      semantics=[1.0, 0.0], operations=list(OPERATIONS))
        catalog.append(dict(descriptor=d, **handle))
        value = hashlib.sha256(("C152-PAYLOAD|" + handle["key"]).encode()).digest()[0] & 1
        records.append(dict(**handle, evidence_value=value))
    records.sort(key=lambda r: r["key"])
    if order == "PERMUTED":
        catalog = catalog[1:] + catalog[:1]  # All positions move, independent of labels.
        records = list(reversed(records))   # Separate physical storage ordering.
    return dict(schema_version=1, records=records), catalog


@dataclass(frozen=True)
class Snapshot:
    adapter: object
    catalog: tuple[dict, ...]
    corpus_path: Path
    catalog_path: Path
    values: dict[str, int]  # Used ONLY after retrieval for scoring; never passed to selector.
    catalog_sha256: str


def _persist_snapshot(directory: Path, descriptors: list[str], order: str, adapter_class) -> Snapshot:
    directory.mkdir(parents=True, exist_ok=False)
    payload, catalog = _snapshot_payloads(descriptors, order)
    corpus_path, catalog_path = directory / "records.json", directory / "catalog.json"
    corpus_path.write_bytes(_bytes(payload))
    catalog_path.write_bytes(_bytes(dict(schema_version=1, source_sha256=_sha(corpus_path), entries=catalog)))
    return _load_snapshot(catalog_path, corpus_path, adapter_class)


def _load_snapshot(catalog_path: Path, corpus_path: Path, adapter_class) -> Snapshot:
    wrapper = json.loads(catalog_path.read_text(encoding="utf-8"))
    source = json.loads(corpus_path.read_text(encoding="utf-8"))
    if wrapper.get("schema_version") != 1 or wrapper.get("source_sha256") != _sha(corpus_path):
        raise ValueError("Catalog/corpus snapshot binding mismatch")
    entries = wrapper.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ValueError("Empty catalog")
    records = source.get("records", [])
    by_key = {r["key"]: r for r in records}
    if (len(by_key) != len(records) or len(entries) != len(records)
            or len({e["key"] for e in entries}) != len(entries)
            or len({e["descriptor"] for e in entries}) != len(entries)):
        raise ValueError("Catalog/record identity coverage mismatch")
    for e in entries:
        fields = set(e) - {"descriptor"}
        if (set(e) != {"descriptor", "key", "domain", "schema", "structure", "semantics", "operations"}
                or e["key"] != _key(e["descriptor"]) or e["key"] not in by_key
                or any(e[k] != by_key[e["key"]].get(k) for k in fields)):
            raise ValueError("Catalog handle does not bind the stored record")
    if len({tuple(e["structure"]) for e in entries}) != len(entries):
        raise ValueError("Duplicate identity signatures")
    adapter = adapter_class(corpus_path)
    if adapter.record_count != len(entries) or adapter.source_sha256 != wrapper["source_sha256"]:
        raise ValueError("Adapter snapshot mismatch")
    return Snapshot(adapter, tuple(entries), corpus_path.resolve(), catalog_path.resolve(),
                    {k:r["evidence_value"] for k,r in by_key.items()}, _sha(catalog_path))


def _fetch_selected(adapter, handle: dict, corpus_path: Path) -> dict:
    """No expected key/answer/label argument. Validate returned identity against request."""
    evidence, stats = adapter.retrieve(handle["structure"], handle["semantics"], schema=handle["schema"],
                                      exact=True, scan_limit=64, probes=1, min_structure=0.999999)
    provenance = bool(evidence is not None and evidence.key == handle["key"]
                      and evidence.domain == handle["domain"] and evidence.schema == handle["schema"]
                      and evidence.operations == tuple(handle["operations"])
                      and evidence.source_sha256 == adapter.source_sha256
                      and evidence.index_fingerprint == adapter.index_fingerprint
                      and evidence.source_path == str(corpus_path.resolve())
                      and stats.get("source_sha256") == adapter.source_sha256
                      and stats.get("index_fingerprint") == adapter.index_fingerprint)
    cost_ok = (stats.get("mode") == "exact" and stats.get("vectors_scored") == adapter.record_count
               and stats.get("bucket_entries_visited") == adapter.record_count
               and stats.get("records") == adapter.record_count)
    return dict(selected_key=handle["key"], returned_key=None if evidence is None else evidence.key,
                evidence_value=None if evidence is None else evidence.evidence_value,
                provenance_valid=provenance, cost_valid=cost_ok, accepted=bool(provenance and cost_ok),
                vectors_scored=stats.get("vectors_scored"), mode=stats.get("mode"))


def _check_replay(actual, expected) -> None:
    if not actual or len(actual) != len(expected):
        raise ValueError("Replay coverage mismatch")
    for a, e in zip(actual, expected, strict=True):
        for key in ("predicted_address", "best_other_address", "correct"):
            if a[key] != e[key]: raise ValueError(f"Replay {key} mismatch")
        for key in ("expected_score", "best_other_score", "expected_margin"):
            if not math.isfinite(a[key]) or abs(a[key] - e[key]) > REPLAY_ATOL:
                raise ValueError(f"Replay {key} drift")


def _header(data) -> None:
    if (data.get("experiment_id") != SOURCE_ID or data.get("commit_sha") != SOURCE_COMMIT
            or data.get("status") != "PASS" or data.get("diagnostic_execution_valid") is not True
            or data.get("production_runtime_modified") is not False or data.get("gate_e_candidate") is not False
            or data.get("evaluation_manifest_sha256") != MANIFEST_SHA or data.get("split_plan_sha256") != PLAN_SHA):
        raise ValueError("Expected accepted C151 PASS")
    s = data.get("summary", {})
    required = dict(fresh_seeds=list(SEEDS), new_splits=4, seeds_per_split=3, paired_heads=24, **CONFIG,
                    train_steps=600, learning_rate=.002, logit_scale=12., auxiliary_coefficients=[1.,1.,1.],
                    training_main_queries=24, training_main_candidates=8, positive_alias_pairs=36,
                    full_cases_per_arm=20736, original12_cases_per_arm=144, heldout_combinations_per_split=56,
                    recipe_changed=False, independent_task=False, inference_oracle_used=False,
                    runtime_path_exercised=False, paired_initialization_verified=True,
                    evaluation_weights_preserved=True, composition_reference_match_rate=1., cross_split_gate_passed=True)
    if any(s.get(k) != v for k, v in required.items()): raise ValueError("C151 configuration/control mismatch")
    records = data.get("records")
    if not isinstance(records, list) or [r.get("seed") for r in records] != list(SEEDS):
        raise ValueError("Full ordered C151 records required")


def _validate_source(data, suite, plan, c151, c146) -> None:
    _header(data)
    records, s = data["records"], data["summary"]
    split_map = {seed:p for p in plan["splits"] for seed in p["fresh_seeds"]}
    old_suite = dict(descriptors=suite["descriptors"][:12], queries=[dict(expected_address=i) for i in range(12)])
    flat = {arm:[] for arm in ARMS}
    for r in records:
        split = split_map[r["seed"]]
        if r["split_id"] != split["split_id"] or set(r["arms"]) != set(ARMS):
            raise ValueError("Source split/arm mismatch")
        for arm in ARMS:
            e = r["arms"][arm]
            m = c151._partition_metrics(e["results"], suite, split["descriptors"], c146._audit_results)
            expected_errors = 9 if arm == ARMS[0] and r["seed"] == 20261726 else 0
            if (m != e["metrics"] or m["errors"] != expected_errors or len(e["results"]) != 1728
                    or len(e["original12"]) != 12 or not c151._perfect(e["original12"])
                    or e["original12_all_pass"] is not True or e["training"]["optimizer_steps"] != 600):
                raise ValueError("Source case/configuration accounting mismatch")
            c146._audit_results(e["original12"], old_suite)
            flat[arm].extend(e["results"])
        if (r["arms"][ARMS[0]]["initial_head_sha256"] != r["arms"][ARMS[1]]["initial_head_sha256"]
                or c146._pair(r["arms"][ARMS[0]]["results"], r["arms"][ARMS[1]]["results"], suite) != r["paired"]):
            raise ValueError("Source paired accounting mismatch")
    for arm in ARMS:
        result = flat[arm]
        totals = dict(cases=len(result), correct=sum(x["correct"] for x in result),
                      errors=sum(not x["correct"] for x in result), min_expected_margin=min(x["expected_margin"] for x in result),
                      full_model_pass_count=sum(c151._perfect(r["arms"][arm]["results"]) for r in records),
                      original12_full_pass_count=12)
        if totals != s["arms"][arm]: raise ValueError("Source aggregate mismatch")
    for split in plan["splits"]:
        models = [r for r in records if r["split_id"] == split["split_id"]]
        repeat = dict(descriptors=suite["descriptors"], queries=suite["queries"]*3)
        for arm in ARMS:
            result = [x for r in models for x in r["arms"][arm]["results"]]
            m = c151._partition_metrics(result, repeat, split["descriptors"], c146._audit_results)
            m.update(full_model_pass_count=sum(c151._perfect(r["arms"][arm]["results"]) for r in models), original12_full_pass_count=3)
            if m != s["by_split"][split["split_id"]][arm]: raise ValueError("Source split aggregate mismatch")
    p = c146._pair(flat[ARMS[0]], flat[ARMS[1]], dict(descriptors=suite["descriptors"], queries=suite["queries"]*12))
    if p != s["paired"] or (p["rescued_errors"],p["new_errors"],p["both_wrong"]) != (9,0,0):
        raise ValueError("Source total paired mismatch")


def _load_head(root, record, arm, vocabulary, head_class, device):
    entry = record["arms"][arm]; meta = entry["checkpoint"]
    name = f"{record['split_id']}-seed-{record['seed']}-{arm.lower()}.pt"
    if PureWindowsPath(meta["path"]).name != name or ".." in PureWindowsPath(meta["path"]).parts:
        raise ValueError("Unexpected checkpoint filename")
    path = root / name  # Metadata cannot redirect loading outside the run directory.
    if _sha(path) != meta["sha256"] or path.stat().st_size != meta["serialized_bytes"]:
        raise ValueError("Checkpoint bytes mismatch")
    obj = torch.load(path, map_location="cpu", weights_only=True)
    expected = dict(config=CONFIG, vocabulary=list(vocabulary), experiment_id=SOURCE_ID,
                    split_id=record["split_id"], auxiliary_candidate_scope=arm, split_plan_sha256=PLAN_SHA,
                    training_composition="POOL_THEN_ENCODE", inference_composition="ENCODE_THEN_POOL")
    if any(obj.get(k) != v for k,v in expected.items()): raise ValueError("Checkpoint metadata mismatch")
    head = head_class(**CONFIG)
    head.load_state_dict(obj["state_dict"], strict=True)
    fingerprint = _fingerprint(head)
    if (fingerprint != entry["final_head_sha256"] or fingerprint != meta["tensor_sha256"]
            or sum(p.numel() for p in head.parameters()) != entry["parameter_count"]):
        raise ValueError("Checkpoint tensor identity mismatch")
    return head.to(device).eval().requires_grad_(False), path


def _metrics(cases):
    if not cases: raise ValueError("Empty integration results")
    return dict(cases=len(cases), accepted=sum(r["accepted"] for r in cases),
                selected_identity_preserved=sum(r["returned_key"] == r["selected_key"] for r in cases),
                provenance_valid=sum(r["provenance_valid"] for r in cases),
                cost_valid=sum(r["cost_valid"] for r in cases),
                payload_matches_selected_record=sum(r["payload_correct"] for r in cases),
                semantic_evidence_correct=sum(r["semantic_correct"] for r in cases),
                vectors_scored=sum(r["vectors_scored"] or 0 for r in cases))


def _bridge_passed(groups):
    for arm in ARMS:
        for order in ORDERS:
            m = groups[arm][order]
            if m["cases"] != 20736 or any(m[k] != m["cases"] for k in
                    ("accepted", "selected_identity_preserved", "provenance_valid", "cost_valid", "payload_matches_selected_record")):
                return False
            if arm == "GLOBAL_CONCEPT" and m["semantic_evidence_correct"] != m["cases"]:
                return False
    return True


def run(*, c151_summary: Path, output_dir: Path):
    from fold_lm.v05.retrieval_content import SharedRetrievalContentHead
    from fold_lm.v05.retrieval_adapter import PersistedStructuralRetrievalAdapter
    from fold_lm.v05_benchmarks import gate_e_c139_hash_collision_diagnostic as c139
    from fold_lm.v05_benchmarks import gate_e_c143_frozen_factorial_audit as c143
    from fold_lm.v05_benchmarks import gate_e_c146_all_factor_alignment as c146
    from fold_lm.v05_benchmarks import gate_e_c147_composition_order as c147
    from fold_lm.v05_benchmarks import gate_e_c151_cross_split as c151

    started = time.perf_counter()
    output_dir.mkdir(parents=True, exist_ok=False)
    records = []
    try:
        root = c151_summary.parent
        fixture = Path(__file__).parent / "fixtures/c138_compositional_alias_queries.json"
        required = {c151_summary:SOURCE_SHA, root/"evaluation-manifest.json":MANIFEST_SHA,
                    root/"split-plan.json":PLAN_SHA, fixture:QUERY_SHA,
                    Path("runs/chatgpt-last-result.json"):C37_SHA,
                    Path("runs/fixtures/v05-c-composition-20260921.pt"):FIXTURE_SHA}
        def check_files():
            for p, sha in required.items():
                if _sha(p) != sha: raise RuntimeError(f"Input/protected hash mismatch: {p}")
        check_files()
        prior = json.loads(c151_summary.read_text(encoding="utf-8"))
        suite = json.loads((root/"evaluation-manifest.json").read_text(encoding="utf-8"))
        plan = json.loads((root/"split-plan.json").read_text(encoding="utf-8"))
        rows = json.loads(fixture.read_text(encoding="utf-8"))["queries"]
        if suite != c143._build_suite(rows) or plan != c151._build_plan(rows):
            raise ValueError("Source manifest/plan generator mismatch")
        _validate_source(prior, suite, plan, c151, c146)
        snapshots = {o:_persist_snapshot(output_dir/o.lower(), suite["descriptors"], o,
                                         PersistedStructuralRetrievalAdapter) for o in ORDERS}
        for snapshot in snapshots.values():
            required[snapshot.corpus_path] = snapshot.adapter.source_sha256
            required[snapshot.catalog_path] = snapshot.catalog_sha256
        if not torch.cuda.is_available(): raise RuntimeError("C152 source replay requires CUDA")
        torch.cuda.set_device(0); torch.set_num_threads(2); torch.set_float32_matmul_precision("highest")
        device = torch.device("cuda")
        vocabulary = c139._training_vocabulary(rows)
        if len(vocabulary) != 49 or c139._fixture_oov_count(rows, vocabulary): raise ValueError("Vocabulary/OOV drift")
        def features(texts): return c139._collision_free_text_features(list(texts), vocabulary, device=device)
        qt = [q["text"] for q in suite["queries"]]; dt = suite["descriptors"]
        labels = [q["expected_address"] for q in suite["queries"]]
        old_indices = [qt.index(r["validation"]) for r in rows]
        setup_seconds = time.perf_counter() - started
        torch.cuda.reset_peak_memory_stats()
        for index, model in enumerate(prior["records"], 1):
            for arm in ARMS:
                head, path = _load_head(root, model, arm, vocabulary, SharedRetrievalContentHead, device)
                required[path] = model["arms"][arm]["checkpoint"]["sha256"]
                frozen = _fingerprint(head)
                print(f"[C152] model {index}/12 arm={arm} checkpoint_loaded=True seed={model['seed']}", flush=True)
                encoded, compose_cost = c147._compose(head, qt + dt, features)
                eq, ed = encoded[:1728], encoded[1728:]
                actual=[]
                with torch.inference_mode():
                    for offset in range(0,1728,216):
                        actual.extend(c147._rank(eq[offset:offset+216] @ ed.T, labels[offset:offset+216]))
                    old = c147._rank(eq[old_indices] @ ed[:12].T, list(range(12)))
                _check_replay(actual, model["arms"][arm]["results"])
                _check_replay(old, model["arms"][arm]["original12"])
                print(f"[C152] model {index}/12 arm={arm} full_and_original12_replay_match=True", flush=True)
                modes={}
                for order,snapshot in snapshots.items():
                    # Catalog is read from disk; candidate order is not an address.
                    descriptors = [h["descriptor"] for h in snapshot.catalog]
                    live_encoded, _ = c147._compose(head, qt + descriptors, features)
                    qv, dv = live_encoded[:1728], live_encoded[1728:]
                    selected=[]
                    with torch.inference_mode():
                        for offset in range(0,1728,216):
                            scores=qv[offset:offset+216] @ dv.T
                            if not torch.isfinite(scores).all(): raise ValueError("Nonfinite live scores")
                            selected.extend(scores.argmax(dim=-1).cpu().tolist())
                    cases=[]
                    for j,(q,position,source_result) in enumerate(zip(suite["queries"],selected,actual,strict=True)):
                        handle=snapshot.catalog[position]
                        if handle["descriptor"] != dt[source_result["predicted_address"]]:
                            raise ValueError("Reordered catalog changed source selection identity")
                        observed=_fetch_selected(snapshot.adapter, handle, snapshot.corpus_path)
                        # Expected identity and value are only consulted AFTER retrieval.
                        truth_key=_key(dt[q["expected_address"]])
                        payload_correct=observed["evidence_value"] == snapshot.values[handle["key"]]
                        semantic_correct=bool(observed["accepted"] and observed["returned_key"] == truth_key
                                              and observed["evidence_value"] == snapshot.values[truth_key])
                        cases.append(dict(case_id=q["case_id"], selected_position=position, **observed,
                                          payload_correct=payload_correct, semantic_correct=semantic_correct))
                        if (j+1)%216 == 0:
                            print(f"[C152] model {index}/12 arm={arm} order={order} "
                                  f"retrieved={j+1}/1728 remaining={1727-j}",flush=True)
                    modes[order]=dict(metrics=_metrics(cases), cases=cases)
                if _fingerprint(head) != frozen: raise ValueError("Frozen model mutated")
                records.append(dict(seed=model["seed"], split_id=model["split_id"], arm=arm,
                                    checkpoint_sha256=required[path], frozen_head_sha256=frozen,
                                    composition_accounting=compose_cost, modes=modes))
                print(f"[C152] model {index}/12 arm={arm} complete remaining_heads={24-len(records)}",flush=True)
                del head,encoded,eq,ed,live_encoded,qv,dv
        check_files()
        groups={a:{o:_metrics([c for r in records if r["arm"]==a for c in r["modes"][o]["cases"]])
                   for o in ORDERS} for a in ARMS}
        passed=_bridge_passed(groups)
        report=dict(experiment_id=EXPERIMENT_ID,stage=STAGE,status="PASS" if passed else "FAIL",
                    diagnostic_execution_valid=True,production_runtime_modified=False,gate_e_candidate=False,
                    commit_sha=subprocess.check_output(["git","rev-parse","HEAD"],text=True).strip(),
                    C151_summary_sha256=SOURCE_SHA,input_sha256={str(p):s for p,s in required.items()},
                    snapshots={o:dict(corpus_sha256=v.adapter.source_sha256,catalog_sha256=v.catalog_sha256,
                                      index_fingerprint=v.adapter.index_fingerprint,record_count=v.adapter.record_count,
                                      corpus_bytes=v.corpus_path.stat().st_size,catalog_bytes=v.catalog_path.stat().st_size)
                               for o,v in snapshots.items()},
                    environment=dict(torch=str(torch.__version__),cuda=torch.version.cuda,
                                     device=torch.cuda.get_device_name(0),precision="float32/highest"),
                    summary=dict(loaded_heads=24,fresh_seed_count=0,additional_training_steps=0,
                                 full_replay_cases=41472,original12_replay_cases=288,
                                 corpus_orders=list(ORDERS),retrieval_calls=82944,candidates_per_call=64,
                                 full_replay_match_rate=1.0,catalog_order_selection_match_rate=1.0,
                                 frozen_weights_preserved_rate=1.0,evaluation_oov_count=0,
                                 persisted_retrieval_exercised=True,provenance_validation_exercised=True,
                                 controller_exercised=False,evidence_commit_exercised=False,answer_exercised=False,
                                 exact_scan_declared=True,inference_oracle_used=False,arms=groups,
                                 persisted_bridge_gate_passed=passed,setup_wall_clock_seconds=setup_seconds,
                                 peak_cuda_allocated_bytes=torch.cuda.max_memory_allocated(),
                                 peak_cuda_reserved_bytes=torch.cuda.max_memory_reserved(),
                                 wall_clock_seconds=time.perf_counter()-started),
                    records=records,limitations=[
                        "Frozen C151 checkpoints; no new learned capability, fresh tasks or production promotion",
                        "One-hot record signatures and catalog handles are explicit adapter plumbing, not a learned fixed class head",
                        "Full 64-record scan is explicit per request; not bounded sublinear retrieval or a latency claim",
                        "Catalog has every target; no missing-answer detection, ambiguity, stale refresh or abstention claim",
                        "Key equality is mandatory; Boolean payload equality alone cannot establish record identity",
                        "Provenance binds to the selected record, not semantic correctness of that selection",
                        "No router, commit-once, persistence recovery or ANSWER; Gate E remains NOT PASSED",
                        "Catalog and corpus share a trusted generated snapshot; not a signed or adversarial provenance proof"])
        temp=output_dir/"summary.partial.json";temp.write_bytes(_bytes(report));temp.replace(output_dir/"summary.json")
        return report
    except Exception as exc:
        (output_dir/"invalid.json").write_bytes(_bytes(dict(experiment_id=EXPERIMENT_ID,status="INVALID",
            diagnostic_execution_valid=False,error=str(exc),completed_heads=len(records))))
        raise


def main():
    parser=argparse.ArgumentParser(description="C152 frozen selection -> persisted evidence bridge")
    parser.add_argument("--c151-summary",type=Path,required=True);parser.add_argument("--output-dir",type=Path,required=True)
    args=parser.parse_args()
    print("C152 frozen_heads=24; fresh_seeds=0; additional_training_steps=0",flush=True)
    print("C152 orders=CANONICAL,PERMUTED; real_retrieval_calls=82944; exact_records_per_call=64",flush=True)
    print("C152 retrieval=True; provenance=True; router=False; commit=False; ANSWER=False",flush=True)
    r=run(c151_summary=args.c151_summary,output_dir=args.output_dir)
    print("=== C152 RESULT ===",flush=True)
    print(json.dumps(dict(r,records="omitted; see summary.json"),indent=2,allow_nan=False),flush=True)
    return 0


if __name__=="__main__": raise SystemExit(main())
