"""C156: request-bound readback into the existing WorkingState/control input.

No learned router runs here. Identity bindings are explicit diagnostic metadata,
not relevance judgments. Existing evidence clocks stay fixed during rereading.
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
from types import MappingProxyType

import numpy as np
import torch

from fold_lm.v05.state import EvidenceRef, EvidenceState, WorkingState, BudgetState, advance_internal
from fold_lm.v05.controller import canonicalize_boolean_channels

EXPERIMENT_ID = "C156-v5e-request-bound-reobservation"
STAGE = "V5-E-REQUEST-BOUND-REOBSERVATION"
C155_ID = "C155-v5e-provenance-bound-payload-dereference"
C155_COMMIT = "ab8e29bc1d7fa3a9fa4cb786874aef4f5b881fe4"
C155_SHA = "1ac82ec4c4e60e6c7586058d497096d602a861e191909ca2adfd685f1f2fb4aa"
SCENARIOS = ("MATCHED", "MISSING_REFERENCE", "MISSING_SOURCE", "WRONG_SNAPSHOT")
STATUSES = dict(zip(SCENARIOS, ("RESOLVED", "REFERENCE_UNBOUND", "SOURCE_UNBOUND", "SNAPSHOT_MISMATCH")))
WIDTH = 8  # C108/C113 input schema; this is not a new learned representation.
REQUESTS = 82944


def _bytes(value) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def _sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _source_id(metadata: dict) -> str:
    fields = ("source_sha256", "index_fingerprint", "source_path")
    if any(not isinstance(metadata.get(k), str) or not metadata[k] for k in fields):
        raise ValueError("Complete snapshot binding required")
    body = json.dumps({k: metadata[k] for k in fields}, sort_keys=True, separators=(",", ":")).encode()
    return "persisted-snapshot:" + hashlib.sha256(body).hexdigest()


@dataclass(frozen=True)
class ReadRequest:
    request_id: str
    scope_id: str
    reference: EvidenceRef
    domain: str
    schema: str
    operations: tuple[str, ...]

    def __post_init__(self):
        if any(not isinstance(x, str) or not x for x in
               (self.request_id, self.scope_id, self.domain, self.schema)):
            raise ValueError("Complete request identity/scope required")
        if not self.request_id.startswith(self.scope_id + "|"):
            raise ValueError("Request does not belong to scope")
        if not isinstance(self.reference, EvidenceRef):
            raise TypeError("EvidenceRef required")
        if (type(self.operations) is not tuple or not self.operations
                or any(not isinstance(x, str) or not x for x in self.operations)):
            raise ValueError("Operation scope required")


@dataclass(frozen=True)
class Observation:
    request_id: str
    scope_id: str
    status: str
    value: int | None
    reference: EvidenceRef | None
    evidence_state: EvidenceState
    working: WorkingState
    budget: BudgetState
    retrieval_calls: int
    vectors_scored: int


def reobserve(request: ReadRequest, evidence: EvidenceState, working: WorkingState,
              budget: BudgetState, registry, resolver) -> Observation:
    """Read ONLY the request-bound existing reference, then refresh working slots.

    `resolver` is the unchanged C155 resolver in the formal run. No expected
    payload, query label, old inbox value or semantic correctness input exists.
    The prior slots may contain stale evidence; channels 2/3 are always replaced.
    """
    if not isinstance(request, ReadRequest) or not isinstance(evidence, EvidenceState):
        raise TypeError("Request and EvidenceState required")
    if not isinstance(working, WorkingState) or not isinstance(budget, BudgetState):
        raise TypeError("WorkingState and BudgetState required")
    if working.slots.shape != (1, WIDTH) or working.evidence_time != evidence.evidence_time:
        raise ValueError("Working shape/evidence clock mismatch")
    if budget.internal_steps_remaining < 1:
        raise ValueError("Internal budget exhausted before dereference")
    current = next((r for r in evidence.observations if r.evidence_id == request.reference.evidence_id), None)
    calls = vectors = 0
    value = None
    accepted_ref = None
    if current is None:
        status = "REFERENCE_UNBOUND"
    elif current != request.reference:
        status = "REFERENCE_MISMATCH"
    else:
        result = resolver(current, registry)
        status, calls, vectors = result.status, result.retrieval_calls, result.vectors_scored
        if status == "RESOLVED":
            e = result.evidence
            metadata = {k: getattr(e, k, None) for k in ("source_sha256", "index_fingerprint", "source_path")}
            complete = all(isinstance(v, str) and v for v in metadata.values())
            valid = bool(e is not None and type(result.value) is int and result.value in (0, 1)
                         and type(e.evidence_value) is int and e.evidence_value == result.value
                         and e.key == current.evidence_id and e.domain == request.domain
                         and e.schema == request.schema and e.operations == request.operations
                         and complete and _source_id(metadata) == current.provenance.source_id)
            if valid:
                value, accepted_ref = result.value, current
            else:
                status = "READBACK_MISMATCH"
        # Even an inconsistent unresolved result carrying a payload cannot expose it.
    slots = working.slots.copy()
    slots[0, 2] = float(value is not None)
    slots[0, 3] = 0.0 if value is None else float(value)
    state_out, work_out, budget_out = advance_internal(evidence, working, budget, slots=slots)
    return Observation(request.request_id, request.scope_id, status, value, accepted_ref,
                       state_out, work_out, budget_out, calls, vectors)


def control_inputs(observations: list[Observation]) -> torch.Tensor:
    """Existing router working-tensor format, without running or training a router.

    Channels: base, dependency, evidence_present, value, then untouched data.
    Signed -1 in a missing value channel is masked by evidence_present=-1;
    Observation.value remains None, not an asserted false fact.
    """
    if not observations:
        raise ValueError("Nonempty observations required")
    raw = torch.from_numpy(np.stack([o.working.slots for o in observations])).to(torch.float32)
    return canonicalize_boolean_channels(raw, (1, 2, 3), threshold=0.5)


def _case_pass(o, request, state, before, budget, scenario, expected_value) -> bool:
    """Oracle values are permitted only here, after reobservation."""
    matched = scenario == "MATCHED"
    value = expected_value if matched else None
    slots = before.slots.copy()
    slots[0, 2:4] = (1.0, float(expected_value)) if matched else (0.0, 0.0)
    return bool(o.request_id == request.request_id and o.scope_id == request.scope_id
                and o.status == STATUSES[scenario] and o.value == value
                and (type(o.value) is int if matched else o.value is None)
                and o.reference == (request.reference if matched else None)
                and o.evidence_state is state and o.working.evidence_time == state.evidence_time
                and o.working.internal_step == before.internal_step + 1
                and o.budget.internal_steps_remaining == budget.internal_steps_remaining - 1
                and o.budget.acquisitions_remaining == budget.acquisitions_remaining
                and np.array_equal(o.working.slots, slots) and not o.working.slots.flags.writeable
                and o.retrieval_calls == int(matched) and o.vectors_scored == 64 * int(matched))


def _state_signature(state: EvidenceState) -> tuple:
    return (state.evidence_time, state.revision,
            tuple((r.evidence_id, r.provenance.source_id, r.provenance.kind,
                   r.provenance.revision, r.provenance.evidence_time) for r in state.observations))


def _gate(s: dict) -> bool:
    return bool(s.get("source_requests") == REQUESTS and s.get("reobservation_calls") == 4 * REQUESTS
                and s.get("status_counts") == {v: REQUESTS for v in STATUSES.values()}
                and s.get("failed_cases") == 0 and s.get("control_tensor_failures") == 0
                and s.get("state_mutations") == 0 and s.get("old_working_mutations") == 0
                and s.get("retrieval_calls") == REQUESTS and s.get("vectors_scored") == REQUESTS * 64
                and s.get("internal_steps_consumed") == REQUESTS * 4
                and s.get("acquisition_budget_consumed") == 0
                and s.get("resolved_values", {}).get("0", 0) > 0
                and s.get("resolved_values", {}).get("1", 0) > 0)


def _header(data: dict) -> None:
    if (data.get("experiment_id") != C155_ID or data.get("commit_sha") != C155_COMMIT
            or data.get("status") != "PASS" or data.get("diagnostic_execution_valid") is not True
            or data.get("production_runtime_modified") is not False or data.get("gate_e_candidate") is not False):
        raise ValueError("Expected accepted C155 PASS")
    s = data.get("summary", {})
    required = dict(source_streams=48, references=3072, resolver_calls=12288, failed_cases=0,
                    state_mutations=0, retrieval_calls=3072, vectors_scored=196608,
                    resolved_values={"0": 1296, "1": 1776}, payload_dereference_gate_passed=True,
                    model_loading=False, new_neural_scoring=False, fresh_seed_count=0, training_steps=0,
                    controller_exercised=False, answer_exercised=False, new_observation_committed=False)
    if any(s.get(k) != v for k, v in required.items()):
        raise ValueError("C155 configuration/count mismatch")
    if s.get("status_counts") != {v: 3072 for v in ("RESOLVED", "SOURCE_UNBOUND", "SNAPSHOT_MISMATCH", "RECORD_UNBOUND")}:
        raise ValueError("C155 status profile mismatch")
    if not isinstance(data.get("records"), list) or len(data["records"]) != 48:
        raise ValueError("Full 48 C155 records required, not the console extract")


def _load_sources(c155_path, c154_path, c153_path, protected, c155):
    """Verify actual prior reports, resolution files and state lineage before measurement."""
    prior = json.loads(c155_path.read_text(encoding="utf-8"))
    _header(prior)
    c155._require(prior.get("C154_summary_sha256") == c155.C154_SHA
                  and prior.get("C153_summary_sha256") == c155.C153_SHA, "C155 lineage mismatch")
    streams, metadata, semantic = c155._load_inputs(c154_path, c153_path, protected)
    indexed = c155._index_streams(prior["records"])
    counts, values = Counter(), Counter()
    from fold_lm.v05.retrieval_adapter import RetrievalEvidence
    for record, state, expected_values, _ in streams:
        old = indexed[(record["seed"], record["arm"], record["order"])]
        c155._require(old["split_id"] == record["split_id"] and old["references"] == 64
                      and old["state_preserved"] is True, "C155 stream mismatch")
        path = c155._safe_file(c155_path.parent, old["result_file"])
        c155._require(_sha(path) == old["result_sha256"], "C155 resolution hash mismatch")
        protected[path] = old["result_sha256"]
        payload = json.loads(path.read_text(encoding="utf-8"))
        c155._require(payload.get("source_state_preserved") is True and len(payload["references"]) == 64,
                      "C155 full resolution coverage mismatch")
        for ref, item in zip(state.observations, payload["references"], strict=True):
            c155._require(item["reference"] == asdict(ref)
                          and item["expected_source_value"] == expected_values[ref.evidence_id], "C155 reference mismatch")
            c155._require([o["scenario"] for o in item["outcomes"]] == list(c155.SCENARIOS), "C155 scenario order mismatch")
            for old_result in item["outcomes"]:
                fields = {k: v for k, v in old_result.items() if k not in ("scenario", "passed")}
                if fields["evidence"] is not None:
                    e = dict(fields["evidence"])
                    e["operations"] = tuple(e["operations"])
                    fields["evidence"] = RetrievalEvidence(**e)
                outcome = c155.Resolution(**fields)
                c155._require(old_result["passed"] is True
                              and c155._case_pass(outcome, old_result["scenario"], ref, expected_values[ref.evidence_id], 64),
                              "C155 stored outcome disagrees with accepted result")
                counts[outcome.status] += 1
                if old_result["scenario"] == "MATCHED":
                    values[str(outcome.value)] += 1
    c155._require(dict(counts) == prior["summary"]["status_counts"]
                  and dict(values) == prior["summary"]["resolved_values"]
                  and semantic == prior["summary"]["source_semantic_counts"], "C155 reaggregation mismatch")
    p153 = json.loads(c153_path.read_text(encoding="utf-8"))
    return streams, metadata, semantic, c155._index_streams(p153["records"])


def run(*, c155_summary: Path, c154_summary: Path, c153_summary: Path, output_dir: Path) -> dict:
    from fold_lm.v05_benchmarks import gate_e_c155_payload_dereference as c155
    output_dir.mkdir(parents=True, exist_ok=False)
    records = []
    started = time.perf_counter()
    torch.set_num_threads(2)
    try:
        protected = {c155_summary: C155_SHA, c154_summary: c155.C154_SHA, c153_summary: c155.C153_SHA,
                     Path("runs/chatgpt-last-result.json"): c155.C37_SHA,
                     Path("runs/fixtures/v05-c-composition-20260921.pt"): c155.FIXTURE_SHA}
        def check_files():
            for p, sha in protected.items():
                c155._require(_sha(p) == sha, f"Input/protected hash mismatch: {p}")
        check_files()
        streams, metadata, semantics, requests_by_stream = _load_sources(
            c155_summary, c154_summary, c153_summary, protected, c155)
        registry = MappingProxyType({sid: c155.load_binding(md) for sid, md in metadata.items()})
        for sid, b in registry.items():
            c155._require(b.source_id == sid and b.record_count == 64, "Snapshot identity mismatch")
            protected[Path(b.source_path)] = b.source_sha256
        print("[C156] C155 full resolutions and C154/C153 state lineage verified", flush=True)
        counts, resolved_values = Counter(), Counter({"0": 0, "1": 0})
        failed = mutations = old_mutations = calls = vectors = tensor_failed = steps = acquisitions = total = 0
        for stream_index, (record, state, expected_values, _) in enumerate(streams, 1):
            stream_key = (record["seed"], record["arm"], record["order"])
            old = requests_by_stream[stream_key]
            inbox_path = c155._safe_file(c153_summary.parent, old["state_file"])
            entries = json.loads(inbox_path.read_text(encoding="utf-8"))["entries"]
            state_before = _bytes(asdict(state))
            refs = {r.evidence_id: r for r in state.observations}
            missing_states = {key: replace(state, observations=tuple(r for r in state.observations if r.evidence_id != key))
                              for key in refs}
            views, rows = [], []
            trace_path = output_dir / f"readback-{record['seed']}-{record['arm'].lower()}-{record['order'].lower()}.jsonl"
            for case_index, entry in enumerate(entries):
                raw = entry["request"]
                ref = refs[raw["key"]]  # Retains source-selected key, never query ground truth.
                request = ReadRequest(raw["request_id"], raw["scope_id"], ref,
                                      raw["domain"], raw["schema"], tuple(raw["operations"]))
                c155._require(_source_id(raw) == ref.provenance.source_id, "Request/source binding changed")
                sid = ref.provenance.source_id
                other = next(b for s, b in registry.items() if s != sid)
                # Deliberately stale prior evidence. It is not the expected payload.
                work = WorkingState(1, 7, np.array([[1., 1., 1., float(case_index % 2), .125, -.25, .375, -.5]]))
                before_slots = work.slots.copy()
                budget = BudgetState(3, 2)
                outcomes = []
                conditions = (("MATCHED", state, registry),
                              ("MISSING_REFERENCE", missing_states[ref.evidence_id], registry),
                              ("MISSING_SOURCE", state, MappingProxyType({})),
                              ("WRONG_SNAPSHOT", state, MappingProxyType({sid: other})))
                for scenario, state_in, bindings in conditions:
                    branch_before = _state_signature(state_in)
                    o = reobserve(request, state_in, work, budget, bindings, c155.resolve_reference)
                    mutations += int(_state_signature(state_in) != branch_before)
                    ok = _case_pass(o, request, state_in, work, budget, scenario, expected_values[ref.evidence_id])
                    failed += int(not ok)
                    counts[o.status] += 1
                    calls += o.retrieval_calls
                    vectors += o.vectors_scored
                    steps += budget.internal_steps_remaining - o.budget.internal_steps_remaining
                    acquisitions += budget.acquisitions_remaining - o.budget.acquisitions_remaining
                    if o.value is not None:
                        resolved_values[str(o.value)] += 1
                    total += 1
                    views.append(o)
                    outcomes.append(dict(scenario=scenario, status=o.status, value=o.value, passed=ok,
                                         working_slots=o.working.slots[0].tolist(), internal_step=o.working.internal_step,
                                         internal_remaining=o.budget.internal_steps_remaining,
                                         acquisition_remaining=o.budget.acquisitions_remaining,
                                         retrieval_calls=o.retrieval_calls, vectors_scored=o.vectors_scored))
                old_mutations += int(not np.array_equal(work.slots, before_slots))
                rows.append(dict(request_id=request.request_id, scope_id=request.scope_id,
                                 reference=asdict(ref), outcomes=outcomes))
            canonical = control_inputs(views).cpu().numpy()
            for i, (row, entry) in enumerate(zip(rows, entries, strict=True)):
                expected_value = entry["value"]  # Evaluator only, AFTER inputs have been built.
                for j, outcome in enumerate(row["outcomes"]):
                    expected = np.array([1., 1., 1. if j == 0 else -1.,
                                         (1. if expected_value else -1.) if j == 0 else -1., .125, -.25, .375, -.5], dtype=np.float32)
                    ok = np.array_equal(canonical[4*i+j, 0], expected)
                    tensor_failed += int(not ok)
                    outcome["control_channels"] = canonical[4*i+j, 0, :4].tolist()
                    outcome["control_input_passed"] = bool(ok)
            with trace_path.open("w", encoding="utf-8", newline="\n") as f:
                for row in rows:
                    f.write(json.dumps(row, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n")
            mutated = state_before != _bytes(asdict(state))
            mutations += int(mutated)
            records.append(dict(seed=record["seed"], split_id=record["split_id"], arm=record["arm"], order=record["order"],
                                source_requests=len(entries), observations=len(views), state_preserved=not mutated,
                                result_file=trace_path.name, result_sha256=_sha(trace_path), serialized_bytes=trace_path.stat().st_size))
            print(f"[C156] stream {stream_index}/48 requests={len(entries)} views={len(views)} "
                  f"failed_so_far={failed+tensor_failed} remaining={48-stream_index}", flush=True)
        check_files()
        summary = dict(source_streams=len(records), source_requests=sum(r["source_requests"] for r in records),
                       reobservation_calls=total, status_counts=dict(counts), resolved_values=dict(resolved_values),
                       failed_cases=failed, control_tensor_failures=tensor_failed, state_mutations=mutations,
                       old_working_mutations=old_mutations, retrieval_calls=calls, vectors_scored=vectors,
                       internal_steps_consumed=steps, acquisition_budget_consumed=acquisitions,
                       source_semantic_counts=semantics, fresh_seed_count=0, training_steps=0, model_loading=False,
                       actual_working_state_exercised=True, advance_internal_exercised=True,
                       control_input_canonicalizer_exercised=True, controller_exercised=False, answer_exercised=False,
                       production_state_commit=False, new_observation_committed=False, crash_recovery_exercised=False,
                       wall_clock_seconds=time.perf_counter()-started)
        passed = _gate(summary)
        summary["request_reobservation_gate_passed"] = passed
        report = dict(experiment_id=EXPERIMENT_ID, stage=STAGE, status="PASS" if passed else "FAIL",
                      diagnostic_execution_valid=True, production_runtime_modified=False, gate_e_candidate=False,
                      commit_sha=subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
                      C155_summary_sha256=C155_SHA, C154_summary_sha256=c155.C154_SHA, C153_summary_sha256=c155.C153_SHA,
                      input_sha256={str(p): v for p, v in protected.items()}, summary=summary, records=records,
                      limitations=[
                          "Request bindings come from accepted C153 selection traces; no new selection or semantic repair",
                          "Working slots/control inputs are constructed but no learned Controller or ANSWER executes",
                          "Source semantic totals are bookkeeping, not new task or answer accuracy",
                          "Missing-reference controls remove only the selected ref in a diagnostic state branch; source artifacts stay unchanged",
                          "Readback consumes one explicitly budgeted internal step; no new observation/evidence clock increment",
                          "Acquisition budget is unchanged; exact64 read costs are recorded separately, not free or bounded production retrieval",
                          "Fixed trusted snapshots, single source per stream and diagnostic clock mapping; no concurrent freshness, durable commit or restore",
                          "Gate E remains NOT PASSED; PC-ALM and Multi-Axis are separate research tracks"])
        tmp = output_dir / "summary.partial.json"
        tmp.write_bytes(_bytes(report)); tmp.replace(output_dir / "summary.json")
        return report
    except Exception as exc:
        (output_dir / "invalid.json").write_bytes(_bytes(dict(experiment_id=EXPERIMENT_ID, status="INVALID",
            diagnostic_execution_valid=False, error=str(exc), completed_streams=len(records))))
        raise


def main() -> int:
    p = argparse.ArgumentParser(description="C156 request-bound WorkingState reobservation")
    p.add_argument("--c155-summary", type=Path, required=True)
    p.add_argument("--c154-summary", type=Path, required=True)
    p.add_argument("--c153-summary", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    args = p.parse_args()
    print("C156 source_requests=82944; conditions=4; reobservation_calls=331776", flush=True)
    print("C156 exact_reads=82944; vectors=5308416; training=0; learned_controller=False; ANSWER=False", flush=True)
    print("C156 actual_WorkingState=True; canonical_control_input=True; evidence_clock_advanced=False", flush=True)
    report = run(c155_summary=args.c155_summary, c154_summary=args.c154_summary,
                 c153_summary=args.c153_summary, output_dir=args.output_dir)
    print("=== C156 RESULT ===", flush=True)
    print(json.dumps(dict(report, records="omitted; see summary.json"), indent=2, allow_nan=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
