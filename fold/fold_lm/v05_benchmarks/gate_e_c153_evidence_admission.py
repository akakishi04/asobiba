"""C153: retrieved evidence -> immutable diagnostic inbox, with rejected deliveries.

Sequential in-process admission only: not production commit, crash recovery,
concurrent atomicity, semantic verification, learned abstention or ANSWER.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict, dataclass, replace
import hashlib
import json
from pathlib import Path
import subprocess
import time

from fold_lm.v05.commit_context import commit_context_matches
from fold_lm.v05.receipt_replay import claim_receipt_once

EXPERIMENT_ID = "C153-v5e-validated-evidence-admission"
STAGE = "V5-E-VALIDATED-EVIDENCE-ADMISSION"
PRIOR_ID = "C152-v5e-frozen-persisted-retrieval-bridge"
PRIOR_COMMIT = "7bd822c5b4086db7a09e83523fdfa75ac0bdfd0e"
PRIOR_SHA = "d70b57b6d7c0aa8876c0647ab1d858ec2808fd3478cf12c02b3d83be8cf2d844"
C151_SHA = "d2b48acb36d28f0422d09067cc23af882c812d020a00ccfc8c6e8286fd896afa"
ARMS = ("WITHIN_FACTOR", "GLOBAL_CONCEPT")
ORDERS = ("CANONICAL", "PERMUTED")
FAULTS = ("MISSING", "WRONG_KEY", "WRONG_SOURCE", "WRONG_SCOPE", "STALE_REQUEST")
EXPECTED = FAULTS + ("COMMITTED", "DUPLICATE")


def _sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _bytes(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


@dataclass(frozen=True)
class Request:
    request_id: str
    scope_id: str
    key: str
    domain: str
    schema: str
    operations: tuple[str, ...]
    source_sha256: str
    index_fingerprint: str
    source_path: str
    request_epoch: int = 1
    provider_generation: int = 1


@dataclass(frozen=True)
class Delivery:
    request_id: str
    scope_id: str
    request_epoch: int
    provider_generation: int
    evidence: object
    stats: dict


@dataclass(frozen=True)
class Entry:
    request: Request
    value: int


@dataclass(frozen=True)
class State:
    entries: tuple[Entry, ...] = ()
    processed: frozenset[str] = frozenset()


def admit(state: State, request: Request, delivery: Delivery) -> tuple[str, State]:
    """Publish payload/provenance and receipt claim together in one returned value.

    No expected semantic key/value/label input. Callers explicitly adopt the
    returned state. This is an immutable, single-process reference transition.
    """
    if not request.request_id or not request.scope_id:
        raise ValueError("Nonempty request and scope identities required")
    if delivery.request_id != request.request_id:
        return "WRONG_REQUEST", state
    if delivery.scope_id != request.scope_id:
        return "WRONG_SCOPE", state
    if not commit_context_matches(
        verified_request_epoch=delivery.request_epoch, current_request_epoch=request.request_epoch,
        verified_provider_generation=delivery.provider_generation,
        current_provider_generation=request.provider_generation,
    ):
        return "STALE_REQUEST", state
    e, stats = delivery.evidence, delivery.stats
    if e is None:
        return "MISSING", state
    if e.key != request.key:
        return "WRONG_KEY", state
    if (e.domain, e.schema, e.operations) != (request.domain, request.schema, request.operations):
        return "WRONG_METADATA", state
    if (e.source_sha256 != request.source_sha256 or e.index_fingerprint != request.index_fingerprint
            or e.source_path != request.source_path
            or stats.get("source_sha256") != request.source_sha256
            or stats.get("index_fingerprint") != request.index_fingerprint):
        return "WRONG_SOURCE", state
    if not (stats.get("mode") == "exact" and stats.get("vectors_scored") == 64
            and stats.get("bucket_entries_visited") == 64 and stats.get("records") == 64):
        return "WRONG_COST", state
    if type(e.evidence_value) is not int or e.evidence_value not in (0, 1):
        return "INVALID_PAYLOAD", state
    claimed, next_ids = claim_receipt_once(receipt_id=request.request_id, processed_receipt_ids=state.processed)
    if not claimed:
        return "DUPLICATE", state
    entry = Entry(request=request, value=e.evidence_value)
    # No mutation has happened before the caller receives this complete state.
    return "COMMITTED", State(entries=state.entries + (entry,), processed=next_ids)


def _request(request_id, scope_id, handle, snapshot):
    return Request(request_id=request_id, scope_id=scope_id, key=handle["key"], domain=handle["domain"],
                   schema=handle["schema"], operations=tuple(handle["operations"]),
                   source_sha256=snapshot.adapter.source_sha256,
                   index_fingerprint=snapshot.adapter.index_fingerprint,
                   source_path=str(snapshot.corpus_path.resolve()))


def _fetch(request, handle, adapter):
    evidence, stats = adapter.retrieve(handle["structure"], handle["semantics"], schema=handle["schema"],
                                      exact=True, scan_limit=64, probes=1, min_structure=0.999999)
    return Delivery(request.request_id, request.scope_id, request.request_epoch,
                    request.provider_generation, evidence, dict(stats))


def _exercise(state, request, good):
    if good.evidence is None:
        # An unexpected miss is a bridge outcome, not a successful no-evidence test.
        return state, dict(passed=False, statuses=["UNEXPECTED_ACTUAL_MISS"])
    faults = (
        replace(good, evidence=None),
        replace(good, evidence=replace(good.evidence, key="fault-wrong-key")),
        replace(good, evidence=replace(good.evidence, source_sha256="fault-wrong-source")),
        replace(good, scope_id="fault-wrong-scope"),
        replace(good, request_epoch=0),
    )
    statuses = []
    stable = True
    before = state
    for bad in faults:
        status, after = admit(state, request, bad)
        statuses.append(status)
        stable = stable and after is state
        state = after
    status, after = admit(state, request, good)
    statuses.append(status)
    correct_write = (status == "COMMITTED" and after.entries == state.entries + (Entry(request, good.evidence.evidence_value),)
                     and after.processed == state.processed | {request.request_id})
    status, duplicate = admit(after, request, good)
    statuses.append(status)
    duplicate_stable = duplicate is after
    passed = bool(tuple(statuses) == EXPECTED and stable and correct_write and duplicate_stable
                  and len(after.entries) == len(before.entries) + 1)
    return duplicate, dict(passed=passed, statuses=statuses, rejection_state_preserved=stable,
                           correct_state_write=correct_write, duplicate_state_preserved=duplicate_stable)


def _header(data):
    if (data.get("experiment_id") != PRIOR_ID or data.get("commit_sha") != PRIOR_COMMIT
            or data.get("status") != "PASS" or data.get("diagnostic_execution_valid") is not True
            or data.get("production_runtime_modified") is not False or data.get("gate_e_candidate") is not False
            or data.get("C151_summary_sha256") != C151_SHA):
        raise ValueError("Expected accepted full C152 PASS")
    required = dict(loaded_heads=24, fresh_seed_count=0, additional_training_steps=0,
                    full_replay_cases=41472, original12_replay_cases=288, corpus_orders=list(ORDERS),
                    retrieval_calls=82944, candidates_per_call=64, full_replay_match_rate=1.0,
                    catalog_order_selection_match_rate=1.0, frozen_weights_preserved_rate=1.0,
                    evaluation_oov_count=0, persisted_retrieval_exercised=True, provenance_validation_exercised=True,
                    controller_exercised=False, evidence_commit_exercised=False, answer_exercised=False,
                    exact_scan_declared=True, inference_oracle_used=False, persisted_bridge_gate_passed=True)
    if any(data.get("summary", {}).get(k) != v for k, v in required.items()):
        raise ValueError("C152 configuration/control mismatch")
    records = data.get("records")
    identities = [(s, a) for s in range(20261721, 20261733) for a in ARMS]
    if not isinstance(records, list) or [(r["seed"], r["arm"]) for r in records] != identities:
        raise ValueError("Full ordered C152 records required")


def _validate_trace(data, suite, snapshots, c152):
    _header(data)
    if len(suite["queries"]) != 1728 or len(suite["descriptors"]) != 64:
        raise ValueError("Manifest coverage mismatch")
    for r in data["records"]:
        split = f"S{1 + (r['seed'] - 20261721) // 3}"
        if r["split_id"] != split or set(r["modes"]) != set(ORDERS):
            raise ValueError("Source split/order mismatch")
        keys = []
        for order in ORDERS:
            snap, mode = snapshots[order], r["modes"][order]
            if len(mode["cases"]) != 1728:
                raise ValueError("Source case count mismatch")
            selected = []
            for q, c in zip(suite["queries"], mode["cases"], strict=True):
                pos = c["selected_position"]
                if type(pos) is not int or not 0 <= pos < 64 or c["case_id"] != q["case_id"]:
                    raise ValueError("Source case identity/position mismatch")
                key = snap.catalog[pos]["key"]
                truth = c152._key(suite["descriptors"][q["expected_address"]])
                if (c["selected_key"] != key or c["returned_key"] != key
                        or c["evidence_value"] != snap.values[key]
                        or any(c[f] is not True for f in ("accepted", "provenance_valid", "cost_valid", "payload_correct"))
                        or c["semantic_correct"] is not (key == truth) or c["vectors_scored"] != 64 or c["mode"] != "exact"):
                    raise ValueError("Source trace binding/payload/semantics mismatch")
                selected.append(key)
            metrics = c152._metrics(mode["cases"])
            expected_correct = 1719 if r["arm"] == ARMS[0] and r["seed"] == 20261726 else 1728
            if metrics != mode["metrics"] or metrics["semantic_evidence_correct"] != expected_correct:
                raise ValueError("Source model accounting mismatch")
            keys.append(selected)
        if keys[0] != keys[1]:
            raise ValueError("Source order changed identity")
    for arm in ARMS:
        for order in ORDERS:
            flat = [c for r in data["records"] if r["arm"] == arm for c in r["modes"][order]["cases"]]
            if c152._metrics(flat) != data["summary"]["arms"][arm][order]:
                raise ValueError("Source aggregate mismatch")


def _passed(groups):
    for arm in ARMS:
        for order in ORDERS:
            m = groups[arm][order]
            expected_semantic = 20727 if arm == ARMS[0] else 20736
            if (m["cases"] != 20736 or m["passed"] != 20736 or m["committed_entries"] != 20736
                    or m["semantic_correct"] != expected_semantic or m["vectors_scored"] != 20736 * 64
                    or m["status_counts"] != {s:20736 for s in EXPECTED}):
                return False
    return True


def run(*, c152_summary: Path, c151_summary: Path, output_dir: Path):
    from fold_lm.v05.retrieval_adapter import PersistedStructuralRetrievalAdapter
    from fold_lm.v05_benchmarks import gate_e_c152_persisted_bridge as c152
    output_dir.mkdir(parents=True, exist_ok=False)
    results = []
    try:
        protected = {c152_summary:PRIOR_SHA, c151_summary:C151_SHA,
                     c151_summary.parent/"evaluation-manifest.json":c152.MANIFEST_SHA,
                     Path("runs/chatgpt-last-result.json"):c152.C37_SHA,
                     Path("runs/fixtures/v05-c-composition-20260921.pt"):c152.FIXTURE_SHA}
        def check():
            for p, sha in protected.items():
                if _sha(p) != sha: raise ValueError(f"Protected/input hash mismatch: {p}")
        check()
        prior = json.loads(c152_summary.read_text(encoding="utf-8"))
        _header(prior)
        suite = json.loads((c151_summary.parent/"evaluation-manifest.json").read_text(encoding="utf-8"))
        snapshots = {}
        for order in ORDERS:
            root = c152_summary.parent/order.lower()
            meta = prior["snapshots"][order]
            protected[root/"records.json"] = meta["corpus_sha256"]
            protected[root/"catalog.json"] = meta["catalog_sha256"]
            check()
            snap = c152._load_snapshot(root/"catalog.json", root/"records.json", PersistedStructuralRetrievalAdapter)
            if snap.adapter.index_fingerprint != meta["index_fingerprint"] or snap.adapter.record_count != 64:
                raise ValueError("Snapshot index mismatch")
            snapshots[order] = snap
        _validate_trace(prior, suite, snapshots, c152)
        started = time.perf_counter()
        groups = {a:{o:dict(cases=0, passed=0, committed_entries=0, semantic_correct=0,
                          vectors_scored=0, status_counts=Counter()) for o in ORDERS} for a in ARMS}
        for index, source in enumerate(prior["records"], 1):
            for order in ORDERS:
                snap = snapshots[order]
                state = State()
                cases = []
                scope = f"C153|{source['seed']}|{source['arm']}|{order}"
                for j, (q, old) in enumerate(zip(suite["queries"], source["modes"][order]["cases"], strict=True)):
                    handle = snap.catalog[old["selected_position"]]
                    request = _request(f"{scope}|{q['case_id']}", scope, handle, snap)
                    good = _fetch(request, handle, snap.adapter)
                    state, m = _exercise(state, request, good)
                    # Ground truth and stored payload are consulted after admission only.
                    entry = state.entries[-1] if state.entries and state.entries[-1].request.request_id == request.request_id else None
                    stored_ok = entry is not None and entry.value == snap.values[handle["key"]]
                    truth_key = c152._key(suite["descriptors"][q["expected_address"]])
                    semantic = bool(stored_ok and entry.request.key == truth_key)
                    m["passed"] = bool(m["passed"] and stored_ok and semantic == old["semantic_correct"])
                    metric = groups[source["arm"]][order]
                    metric["cases"] += 1; metric["passed"] += m["passed"]
                    metric["committed_entries"] += entry is not None
                    metric["semantic_correct"] += semantic
                    metric["vectors_scored"] += good.stats.get("vectors_scored", 0)
                    metric["status_counts"].update(m["statuses"])
                    cases.append(dict(case_id=q["case_id"], selected_key=handle["key"],
                                      semantic_correct=semantic, **m))
                    if (j+1) % 216 == 0:
                        print(f"[C153] trace {index}/24 arm={source['arm']} order={order} "
                              f"admitted={j+1}/1728 state_entries={len(state.entries)} remaining={1727-j}", flush=True)
                state_path = output_dir/f"state-{source['seed']}-{source['arm'].lower()}-{order.lower()}.json"
                state_path.write_bytes(_bytes(dict(entries=[asdict(e) for e in state.entries], processed=sorted(state.processed))))
                results.append(dict(seed=source["seed"], split_id=source["split_id"], arm=source["arm"], order=order,
                                    cases=cases, state_file=state_path.name, state_sha256=_sha(state_path),
                                    entries=len(state.entries), processed=len(state.processed)))
        check()
        report = dict(experiment_id=EXPERIMENT_ID, stage=STAGE, status="PASS" if _passed(groups) else "FAIL",
                      diagnostic_execution_valid=True, production_runtime_modified=False, gate_e_candidate=False,
                      commit_sha=subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
                      C152_summary_sha256=PRIOR_SHA, C151_summary_sha256=C151_SHA,
                      input_sha256={str(p):s for p,s in protected.items()},
                      summary=dict(source_selection_trace_reused=True, source_trace_heads=24, model_loading=False,
                                   fresh_seed_count=0, training_steps=0, retrieval_calls=82944,
                                   submissions_per_request=7, submissions=580608, expected_rejections=414720,
                                   expected_commits=82944, expected_duplicate_rejections=82944,
                                   inbox_kind="DIAGNOSTIC_IMMUTABLE_IN_PROCESS", production_state_commit=False,
                                   controller_exercised=False, answer_exercised=False, crash_recovery_exercised=False,
                                   groups=groups, evidence_admission_gate_passed=_passed(groups),
                                   wall_clock_seconds=time.perf_counter()-started), records=results,
                      limitations=["Selection trace is reused, not a new encoder/ranking/learning experiment",
                                   "Actual retrieval plus a new diagnostic immutable inbox; not production session integration",
                                   "Sequential state transition/replay suppression only; no concurrency or crash-durability claim",
                                   "Bad deliveries are controlled copies of one real retrieval, not extra provider calls",
                                   "Provenance does not certify semantic relevance or detect arbitrary payload-bit forgery",
                                   "MISSING is an injected delivery here, not learned absent-target detection",
                                   "Expected labels/values are used for scoring only; wrong but authentic control evidence is admitted",
                                   "Full exact scan remains explicit; Gate E NOT PASSED; no ANSWER/controller"])
        path = output_dir/"summary.partial.json"; path.write_bytes(_bytes(report)); path.replace(output_dir/"summary.json")
        return report
    except Exception as exc:
        (output_dir/"invalid.json").write_bytes(_bytes(dict(experiment_id=EXPERIMENT_ID, status="INVALID",
            diagnostic_execution_valid=False, error=str(exc), completed_streams=len(results))))
        raise


def main():
    p = argparse.ArgumentParser(description="C153 validated evidence admission boundary")
    p.add_argument("--c152-summary", type=Path, required=True)
    p.add_argument("--c151-summary", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    args = p.parse_args()
    print("C153 source_trace_heads=24; model_loading=False; fresh_seeds=0; training_steps=0", flush=True)
    print("C153 actual_retrieval_calls=82944; fault_variants=5; deliveries=580608", flush=True)
    print("C153 state=DIAGNOSTIC_IN_PROCESS; controller=False; ANSWER=False; crash_recovery=False", flush=True)
    r = run(c152_summary=args.c152_summary, c151_summary=args.c151_summary, output_dir=args.output_dir)
    print("=== C153 RESULT ===", flush=True)
    print(json.dumps(dict(r, records="omitted; see summary.json and state files"), indent=2, allow_nan=False), flush=True)
    return 0


if __name__ == "__main__": raise SystemExit(main())
