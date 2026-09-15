"""C154: project accepted C153 request entries into V5 EvidenceState identity refs.

This benchmark changes only the state representation boundary.  It does not
retrieve again, load a model, score candidates, persist a production state,
reobserve payloads, exercise concurrency/crash recovery, or answer.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
import subprocess
import time

from fold_lm.v05.state import EvidenceRef, EvidenceState, Provenance, ProvenanceKind

EXPERIMENT_ID = "C154-v5e-evidence-state-projection"
STAGE = "V5-E-EVIDENCE-STATE-PROJECTION"
PRIOR_ID = "C153-v5e-validated-evidence-admission"
PRIOR_COMMIT = "dc5f5d8bf72bc04692411c05213c824eb8c8c918"
PRIOR_SHA = "cddf360fc2211302d1dab0abd8d96038bb3d39ab273f9dea336da348d70d3a78"
ARMS = ("WITHIN_FACTOR", "GLOBAL_CONCEPT")
ORDERS = ("CANONICAL", "PERMUTED")
EXPECTED_STREAMS = 48
ENTRIES_PER_STREAM = 1728
UNIQUE_RECORDS_PER_STREAM = 64
EXPECTED_SOURCE_ENTRIES = EXPECTED_STREAMS * ENTRIES_PER_STREAM
EXPECTED_ADDED = EXPECTED_STREAMS * UNIQUE_RECORDS_PER_STREAM
EXPECTED_EXISTING = EXPECTED_SOURCE_ENTRIES - EXPECTED_ADDED
EXPECTED_CONFLICT_REJECTIONS = EXPECTED_ADDED


def _sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _bytes(value) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def _source_id(request: dict) -> str:
    required = ("source_sha256", "index_fingerprint", "source_path")
    if any(not isinstance(request.get(k), str) or not request[k] for k in required):
        raise ValueError("Complete snapshot provenance required")
    payload = {k: request[k] for k in required}
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return f"persisted-snapshot:{digest}"


def _ref_from_entry(entry: dict) -> EvidenceRef:
    if type(entry) is not dict or set(entry) != {"request", "value"}:
        raise ValueError("C153 entry shape mismatch")
    request = entry["request"]
    if type(request) is not dict:
        raise TypeError("request must be dict")
    for key in ("request_id", "scope_id", "key", "domain", "schema", "source_sha256",
                "index_fingerprint", "source_path"):
        if not isinstance(request.get(key), str) or not request[key]:
            raise ValueError(f"Invalid request field: {key}")
    operations = request.get("operations")
    if type(operations) is not list or not operations or any(not isinstance(x, str) or not x for x in operations):
        raise ValueError("operations must be a nonempty string list")
    for key in ("request_epoch", "provider_generation"):
        if type(request.get(key)) is not int or request[key] < 0:
            raise ValueError(f"Invalid request version: {key}")
    if type(entry["value"]) is not int or entry["value"] not in (0, 1):
        raise ValueError("C153 payload must remain a Boolean-like integer")
    return EvidenceRef(
        evidence_id=request["key"],
        provenance=Provenance(
            source_id=_source_id(request),
            kind=ProvenanceKind.OBSERVED,
            revision=request["provider_generation"],
            evidence_time=request["request_epoch"],
        ),
    )


def project_observation(state: EvidenceState, ref: EvidenceRef) -> tuple[str, EvidenceState]:
    """Idempotently project a validated record identity into EvidenceState.

    Exact duplicates preserve object identity.  A reused evidence_id with a
    different provenance is a conflict and also preserves object identity.
    """
    if not isinstance(state, EvidenceState):
        raise TypeError("state must be EvidenceState")
    if not isinstance(ref, EvidenceRef):
        raise TypeError("ref must be EvidenceRef")
    existing = next((x for x in state.observations if x.evidence_id == ref.evidence_id), None)
    if existing is not None:
        if existing == ref:
            return "ALREADY_PRESENT", state
        return "PROVENANCE_CONFLICT", state
    return "ADDED", EvidenceState(
        evidence_time=state.evidence_time,
        revision=state.revision,
        observations=state.observations + (ref,),
    )


def _header(data: dict) -> None:
    if (data.get("experiment_id") != PRIOR_ID or data.get("commit_sha") != PRIOR_COMMIT
            or data.get("status") != "PASS" or data.get("diagnostic_execution_valid") is not True
            or data.get("production_runtime_modified") is not False or data.get("gate_e_candidate") is not False):
        raise ValueError("Expected accepted full C153 PASS")
    summary = data.get("summary", {})
    required = dict(source_selection_trace_reused=True, source_trace_heads=24, model_loading=False,
                    fresh_seed_count=0, training_steps=0, retrieval_calls=82944,
                    submissions_per_request=7, submissions=580608, expected_rejections=414720,
                    expected_commits=82944, expected_duplicate_rejections=82944,
                    inbox_kind="DIAGNOSTIC_IMMUTABLE_IN_PROCESS", production_state_commit=False,
                    controller_exercised=False, answer_exercised=False, crash_recovery_exercised=False,
                    evidence_admission_gate_passed=True)
    if any(summary.get(k) != v for k, v in required.items()):
        raise ValueError("C153 configuration/control mismatch")
    records = data.get("records")
    if not isinstance(records, list) or len(records) != EXPECTED_STREAMS:
        raise ValueError("Full 48 C153 state streams required")


def _source_group_counts(data: dict) -> dict:
    groups = {a: {o: dict(cases=0, semantic_correct=0) for o in ORDERS} for a in ARMS}
    for record in data["records"]:
        arm, order = record.get("arm"), record.get("order")
        if arm not in ARMS or order not in ORDERS:
            raise ValueError("Unexpected C153 arm/order")
        cases = record.get("cases")
        if not isinstance(cases, list) or len(cases) != ENTRIES_PER_STREAM:
            raise ValueError("C153 case coverage mismatch")
        groups[arm][order]["cases"] += len(cases)
        groups[arm][order]["semantic_correct"] += sum(c.get("semantic_correct") is True for c in cases)
    for arm in ARMS:
        for order in ORDERS:
            expected_semantic = 20727 if arm == "WITHIN_FACTOR" else 20736
            g = groups[arm][order]
            if g != {"cases": 20736, "semantic_correct": expected_semantic}:
                raise ValueError("C153 semantic source accounting mismatch")
    return groups


def _load_state(root: Path, record: dict) -> tuple[Path, dict]:
    name = record.get("state_file")
    declared_sha = record.get("state_sha256")
    if not isinstance(name, str) or not name or Path(name).name != name:
        raise ValueError("Unsafe C153 state filename")
    if not isinstance(declared_sha, str) or len(declared_sha) != 64:
        raise ValueError("Missing C153 state hash")
    path = root / name
    if _sha(path) != declared_sha:
        raise ValueError("C153 state file hash mismatch")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if set(payload) != {"entries", "processed"}:
        raise ValueError("C153 state payload shape mismatch")
    entries, processed = payload["entries"], payload["processed"]
    if not isinstance(entries, list) or len(entries) != ENTRIES_PER_STREAM:
        raise ValueError("C153 entry count mismatch")
    if not isinstance(processed, list) or len(processed) != ENTRIES_PER_STREAM or len(set(processed)) != ENTRIES_PER_STREAM:
        raise ValueError("C153 processed request count mismatch")
    if record.get("entries") != ENTRIES_PER_STREAM or record.get("processed") != ENTRIES_PER_STREAM:
        raise ValueError("C153 record/state count mismatch")
    return path, payload


def _stream_projection(record: dict, payload: dict) -> tuple[dict, dict]:
    state = EvidenceState(evidence_time=1, revision=1, observations=())
    counts = Counter()
    seen_requests = set()
    expected_scope = f"C153|{record['seed']}|{record['arm']}|{record['order']}"
    cases = record["cases"]
    for entry, case in zip(payload["entries"], cases, strict=True):
        request = entry.get("request", {})
        request_id = request.get("request_id")
        if request.get("scope_id") != expected_scope or not isinstance(request_id, str) or not request_id.startswith(expected_scope + "|"):
            raise ValueError("C153 request/scope binding mismatch")
        if request_id in seen_requests or request_id not in payload["processed"]:
            raise ValueError("C153 request claim mismatch")
        seen_requests.add(request_id)
        if request.get("key") != case.get("selected_key"):
            raise ValueError("C153 case/state selected identity mismatch")
        ref = _ref_from_entry(entry)
        first = all(x.evidence_id != ref.evidence_id for x in state.observations)
        status, next_state = project_observation(state, ref)
        if first:
            if status != "ADDED" or next_state is state:
                raise ValueError("New evidence identity was not added")
            # One controlled conflict per newly observed record identity.
            bad = replace(ref, provenance=replace(ref.provenance, source_id=ref.provenance.source_id + ":conflict"))
            conflict_status, conflict_state = project_observation(next_state, bad)
            if conflict_status != "PROVENANCE_CONFLICT" or conflict_state is not next_state:
                raise ValueError("Conflicting provenance was not rejected atomically")
            counts["PROVENANCE_CONFLICT"] += 1
        else:
            if status != "ALREADY_PRESENT" or next_state is not state:
                raise ValueError("Existing evidence identity was not idempotent")
        counts[status] += 1
        state = next_state
    if len(state.observations) != UNIQUE_RECORDS_PER_STREAM:
        raise ValueError("Expected all 64 record identities in final EvidenceState")
    if len({x.evidence_id for x in state.observations}) != UNIQUE_RECORDS_PER_STREAM:
        raise ValueError("Duplicate EvidenceState identity")
    if any(x.provenance.kind is not ProvenanceKind.OBSERVED for x in state.observations):
        raise ValueError("Non-observed provenance entered EvidenceState")
    if counts != Counter({"ADDED": 64, "ALREADY_PRESENT": 1664, "PROVENANCE_CONFLICT": 64}):
        raise ValueError("Projection transition counts mismatch")
    snapshot = dict(
        evidence_time=state.evidence_time,
        revision=state.revision,
        observations=[asdict(x) for x in state.observations],
    )
    return dict(source_entries=ENTRIES_PER_STREAM, added=counts["ADDED"],
                already_present=counts["ALREADY_PRESENT"],
                conflict_rejections=counts["PROVENANCE_CONFLICT"],
                final_observations=len(state.observations)), snapshot


def _gate(metrics: dict) -> bool:
    return bool(
        metrics.get("streams") == EXPECTED_STREAMS
        and metrics.get("source_entries") == EXPECTED_SOURCE_ENTRIES
        and metrics.get("added") == EXPECTED_ADDED
        and metrics.get("already_present") == EXPECTED_EXISTING
        and metrics.get("conflict_rejections") == EXPECTED_CONFLICT_REJECTIONS
        and metrics.get("final_observations") == EXPECTED_ADDED
        and metrics.get("semantic_source_counts") == {
            "WITHIN_FACTOR": {
                "CANONICAL": {"cases": 20736, "semantic_correct": 20727},
                "PERMUTED": {"cases": 20736, "semantic_correct": 20727},
            },
            "GLOBAL_CONCEPT": {
                "CANONICAL": {"cases": 20736, "semantic_correct": 20736},
                "PERMUTED": {"cases": 20736, "semantic_correct": 20736},
            },
        }
    )


def run(*, c153_summary: Path, output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    completed = []
    try:
        protected = {
            c153_summary: PRIOR_SHA,
            Path("runs/chatgpt-last-result.json"): "fd4a8da897bdaea9d103a252e30212c7ff842d23300d7c837333e146dee51931",
            Path("runs/fixtures/v05-c-composition-20260921.pt"): "a52f8209703149407580f7e2965b61b78653030ee992af6d759865736741ca9e",
        }
        def check():
            for path, expected in protected.items():
                if _sha(path) != expected:
                    raise ValueError(f"Protected/input hash mismatch: {path}")
        check()
        prior = json.loads(c153_summary.read_text(encoding="utf-8"))
        _header(prior)
        semantic = _source_group_counts(prior)
        root = c153_summary.parent
        state_inputs = []
        for index, record in enumerate(prior["records"], 1):
            path, payload = _load_state(root, record)
            protected[path] = record["state_sha256"]
            state_inputs.append(path)
            stream_metrics, snapshot = _stream_projection(record, payload)
            output = output_dir / f"evidence-state-{record['seed']}-{record['arm'].lower()}-{record['order'].lower()}.json"
            output.write_bytes(_bytes(snapshot))
            completed.append(dict(seed=record["seed"], split_id=record["split_id"], arm=record["arm"],
                                  order=record["order"], metrics=stream_metrics,
                                  state_file=output.name, state_sha256=_sha(output)))
            print(f"[C154] stream {index}/48 arm={record['arm']} order={record['order']} "
                  f"source=1728 added=64 existing=1664 conflicts=64 remaining={48-index}", flush=True)
        check()
        totals = dict(
            streams=len(completed),
            source_entries=sum(r["metrics"]["source_entries"] for r in completed),
            added=sum(r["metrics"]["added"] for r in completed),
            already_present=sum(r["metrics"]["already_present"] for r in completed),
            conflict_rejections=sum(r["metrics"]["conflict_rejections"] for r in completed),
            final_observations=sum(r["metrics"]["final_observations"] for r in completed),
            semantic_source_counts=semantic,
        )
        passed = _gate(totals)
        report = dict(
            experiment_id=EXPERIMENT_ID,
            stage=STAGE,
            status="PASS" if passed else "FAIL",
            diagnostic_execution_valid=True,
            production_runtime_modified=False,
            gate_e_candidate=False,
            commit_sha=subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
            C153_summary_sha256=PRIOR_SHA,
            input_sha256={str(path): expected for path, expected in protected.items()},
            summary=dict(
                source_state_streams=EXPECTED_STREAMS,
                model_loading=False,
                retrieval_exercised=False,
                new_scoring=False,
                fresh_seed_count=0,
                training_steps=0,
                actual_v5_evidence_state_exercised=True,
                evidence_values_stored_in_evidence_state=False,
                production_state_commit=False,
                reobserve_exercised=False,
                controller_exercised=False,
                answer_exercised=False,
                crash_recovery_exercised=False,
                concurrency_exercised=False,
                **totals,
                evidence_state_projection_gate_passed=passed,
                wall_clock_seconds=time.perf_counter() - started,
            ),
            records=completed,
            limitations=[
                "Uses accepted C153 state artifacts; no new retrieval, encoder, ranking or learning",
                "EvidenceState stores identity/provenance references, not the Boolean payload values",
                "Request-level claims are intentionally collapsed to record identity within each stream",
                "Each layout remains a separate EvidenceState because its persisted snapshot provenance differs",
                "Projection is diagnostic/in-process and not a durable production-state transaction",
                "No re-observation/dereference, concurrency, crash recovery, controller or ANSWER is exercised",
                "Source semantic errors are only reaggregated and must remain unchanged; Gate E remains NOT PASSED",
            ],
        )
        temp = output_dir / "summary.partial.json"
        temp.write_bytes(_bytes(report))
        temp.replace(output_dir / "summary.json")
        return report
    except Exception as exc:
        (output_dir / "invalid.json").write_bytes(_bytes(dict(
            experiment_id=EXPERIMENT_ID,
            status="INVALID",
            diagnostic_execution_valid=False,
            error=str(exc),
            completed_streams=len(completed),
        )))
        raise


def main():
    parser = argparse.ArgumentParser(description="C154 V5 EvidenceState projection boundary")
    parser.add_argument("--c153-summary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print("C154 source_streams=48; source_entries=82944; model_loading=False; retrieval=False; training=0", flush=True)
    print("C154 expected_added=3072; expected_existing=79872; expected_conflict_rejections=3072", flush=True)
    print("C154 actual_v5_EvidenceState=True; payload_in_state=False; reobserve=False; ANSWER=False", flush=True)
    result = run(c153_summary=args.c153_summary, output_dir=args.output_dir)
    print("=== C154 RESULT ===", flush=True)
    print(json.dumps(dict(result, records="omitted; see summary.json"), indent=2, allow_nan=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
