"""C155: provenance-bound payload dereference from accepted EvidenceState refs.

Diagnostic read-only integration. No learning, new neural ranking, publication,
controller, ANSWER, or crash-recovery claim. Unknown binding is not a zero value.
"""
from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Mapping
from dataclasses import asdict, dataclass, replace
import hashlib
import json
from pathlib import Path, PureWindowsPath
import subprocess
import time
from types import MappingProxyType

from fold_lm.v05.state import EvidenceRef, EvidenceState, Provenance, ProvenanceKind
from fold_lm.v05.retrieval_adapter import PersistedStructuralRetrievalAdapter

EXPERIMENT_ID = "C155-v5e-provenance-bound-payload-dereference"
STAGE = "V5-E-PROVENANCE-BOUND-PAYLOAD-DEREFERENCE"
C154_SHA = "4814c9489b76bfb124e7134336611a3f513eb922083b0eca251be533820c4284"
C153_SHA = "cddf360fc2211302d1dab0abd8d96038bb3d39ab273f9dea336da348d70d3a78"
C37_SHA = "fd4a8da897bdaea9d103a252e30212c7ff842d23300d7c837333e146dee51931"
FIXTURE_SHA = "a52f8209703149407580f7e2965b61b78653030ee992af6d759865736741ca9e"
SEEDS = tuple(range(20261721, 20261733))  # Source identities, NOT fresh runs.
ARMS = ("WITHIN_FACTOR", "GLOBAL_CONCEPT")
ORDERS = ("CANONICAL", "PERMUTED")
EXPECTED_REFS = 3072
SCENARIOS = ("MATCHED", "MISSING_SOURCE", "WRONG_SNAPSHOT", "MISSING_RECORD")


class InvalidInput(ValueError):
    """Prerequisite/setup failure, separate from measured resolver behavior."""


def _sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _bytes(value) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise InvalidInput(message)


def _source_id(metadata: Mapping) -> str:
    """Exactly the C154 three-field digest; not a new source identity contract."""
    fields = ("source_sha256", "index_fingerprint", "source_path")
    _require(all(isinstance(metadata.get(k), str) and metadata[k] for k in fields), "Incomplete snapshot binding")
    payload = {k: metadata[k] for k in fields}
    return "persisted-snapshot:" + hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True)
class Handle:
    key: str
    domain: str
    schema: str
    operations: tuple[str, ...]
    structure: tuple[float, ...]
    semantics: tuple[float, ...]


@dataclass(frozen=True)
class SnapshotBinding:
    source_sha256: str
    index_fingerprint: str
    source_path: str
    evidence_time: int
    revision: int
    record_count: int
    handles: Mapping[str, Handle]
    adapter: object

    @property
    def source_id(self) -> str:
        return _source_id(dict(source_sha256=self.source_sha256,
                               index_fingerprint=self.index_fingerprint, source_path=self.source_path))


def load_binding(metadata: Mapping) -> SnapshotBinding:
    """Load only a source pinned by the accepted C153 artifacts, once per snapshot.

    Cached handles contain no payload. The adapter owns the stored payloads;
    no request-level expected value is passed to it or to resolve_reference.
    """
    _source_id(metadata)
    for k in ("request_epoch", "provider_generation"):
        _require(type(metadata.get(k)) is int and metadata[k] >= 0, "Invalid source clock")
    path = Path(metadata["source_path"])
    _require(str(path.resolve()) == metadata["source_path"], "Noncanonical source path")
    _require(_sha(path) == metadata["source_sha256"], "Pinned source file hash mismatch")
    raw = json.loads(path.read_text(encoding="utf-8"))
    adapter = PersistedStructuralRetrievalAdapter(path)
    _require(adapter.source_sha256 == metadata["source_sha256"]
             and adapter.index_fingerprint == metadata["index_fingerprint"], "Pinned adapter identity mismatch")
    handles = {r["key"]: Handle(r["key"], r["domain"], r["schema"], tuple(r["operations"]),
                               tuple(r["structure"]), tuple(r["semantics"])) for r in raw["records"]}
    _require(len(handles) == adapter.record_count, "Handle coverage mismatch")
    return SnapshotBinding(metadata["source_sha256"], metadata["index_fingerprint"],
                           metadata["source_path"], metadata["request_epoch"], metadata["provider_generation"],
                           adapter.record_count, MappingProxyType(handles), adapter)


@dataclass(frozen=True)
class Resolution:
    status: str
    value: int | None = None
    evidence: object | None = None
    retrieval_calls: int = 0
    vectors_scored: int = 0


def resolve_reference(ref: EvidenceRef, registry: Mapping[str, SnapshotBinding]) -> Resolution:
    """No expected value, query, semantic label, or answer input. Never mutates state."""
    if not isinstance(ref, EvidenceRef):
        raise TypeError("EvidenceRef required")
    if ref.provenance.kind is not ProvenanceKind.OBSERVED:
        return Resolution("NOT_OBSERVED")
    binding = registry.get(ref.provenance.source_id)
    if binding is None:
        return Resolution("SOURCE_UNBOUND")
    if (binding.source_id != ref.provenance.source_id
            or binding.evidence_time != ref.provenance.evidence_time
            or binding.revision != ref.provenance.revision
            or binding.adapter.source_sha256 != binding.source_sha256
            or binding.adapter.index_fingerprint != binding.index_fingerprint
            or binding.adapter.record_count != binding.record_count):
        return Resolution("SNAPSHOT_MISMATCH")
    handle = binding.handles.get(ref.evidence_id)
    if handle is None:
        return Resolution("RECORD_UNBOUND")
    if handle.key != ref.evidence_id:
        return Resolution("IDENTITY_MISMATCH")
    evidence, stats = binding.adapter.retrieve(
        handle.structure, handle.semantics, schema=handle.schema,
        exact=True, scan_limit=binding.record_count, probes=1, min_structure=0.999999)
    scanned = stats.get("vectors_scored")
    count = scanned if type(scanned) is int and scanned >= 0 else 0
    def rejected(reason: str) -> Resolution:
        return Resolution(reason, retrieval_calls=1, vectors_scored=count)
    if (stats.get("mode") != "exact" or type(scanned) is not int or scanned != binding.record_count
            or stats.get("records") != binding.record_count
            or stats.get("bucket_entries_visited") != binding.record_count):
        return rejected("COST_MISMATCH")
    if evidence is None:
        return rejected("RECORD_NOT_FOUND")
    if (evidence.key != ref.evidence_id or evidence.domain != handle.domain
            or evidence.schema != handle.schema or evidence.operations != handle.operations):
        return rejected("IDENTITY_MISMATCH")
    if (evidence.source_sha256 != binding.source_sha256
            or evidence.index_fingerprint != binding.index_fingerprint
            or evidence.source_path != binding.source_path
            or stats.get("source_sha256") != binding.source_sha256
            or stats.get("index_fingerprint") != binding.index_fingerprint):
        return rejected("PROVENANCE_MISMATCH")
    if type(evidence.evidence_value) is not int or evidence.evidence_value not in (0, 1):
        return rejected("PAYLOAD_INVALID")
    return Resolution("RESOLVED", evidence.evidence_value, evidence, 1, count)


def _case_pass(result: Resolution, scenario: str, ref: EvidenceRef, expected_value: int, count: int) -> bool:
    """Post-read evaluator only. Bad measured outcomes become FAIL, not INVALID."""
    if scenario == "MATCHED":
        evidence = result.evidence
        if evidence is None:
            return False
        metadata = {k: getattr(evidence, k, None) for k in
                    ("source_sha256", "index_fingerprint", "source_path")}
        if any(not isinstance(v, str) or not v for v in metadata.values()):
            return False
        return bool(result.status == "RESOLVED" and type(result.value) is int
                    and result.value == expected_value and type(evidence.evidence_value) is int
                    and evidence.evidence_value == expected_value and evidence.key == ref.evidence_id
                    and _source_id(metadata) == ref.provenance.source_id
                    and result.retrieval_calls == 1 and result.vectors_scored == count)
    statuses = {"MISSING_SOURCE": "SOURCE_UNBOUND", "WRONG_SNAPSHOT": "SNAPSHOT_MISMATCH",
                "MISSING_RECORD": "RECORD_UNBOUND"}
    if scenario not in statuses:
        raise ValueError("Unknown test scenario")
    return bool(result.status == statuses[scenario] and result.value is None and result.evidence is None
                and result.retrieval_calls == 0 and result.vectors_scored == 0)


def _safe_file(root: Path, name: str) -> Path:
    _require(isinstance(name, str) and name not in ("", ".", "..")
             and Path(name).name == name and PureWindowsPath(name).name == name, "Unsafe artifact filename")
    path = root / name
    _require(path.resolve().parent == root.resolve(), "Artifact escaped run directory")
    return path


def _index_streams(records: list) -> dict:
    _require(isinstance(records, list) and len(records) == 48, "Expected 48 full source streams")
    result = {}
    for r in records:
        k = (r["seed"], r["arm"], r["order"])
        _require(k not in result, "Duplicate stream identity")
        result[k] = r
    _require(set(result) == {(s, a, o) for s in SEEDS for a in ARMS for o in ORDERS}, "Stream coverage mismatch")
    return result


def _decode_state(data: dict) -> EvidenceState:
    _require(set(data) == {"evidence_time", "revision", "observations"}, "Unexpected EvidenceState fields")
    refs = []
    for row in data["observations"]:
        _require(set(row) == {"evidence_id", "provenance"}, "Unexpected EvidenceRef fields")
        p = dict(row["provenance"])
        _require(set(p) == {"source_id", "kind", "revision", "evidence_time"}, "Unexpected provenance fields")
        p["kind"] = ProvenanceKind(p["kind"])
        refs.append(EvidenceRef(row["evidence_id"], Provenance(**p)))
    return EvidenceState(data["evidence_time"], data["revision"], tuple(refs))


def _load_inputs(c154_path: Path, c153_path: Path, protected: dict) -> tuple:
    p154 = json.loads(c154_path.read_text(encoding="utf-8"))
    p153 = json.loads(c153_path.read_text(encoding="utf-8"))
    for data, ident, commit in (
        (p154, "C154-v5e-evidence-state-projection", "8768303869d6ee24d72cc98a9690219a4205a495"),
        (p153, "C153-v5e-validated-evidence-admission", "dc5f5d8bf72bc04692411c05213c824eb8c8c918"),
    ):
        _require(data.get("experiment_id") == ident and data.get("commit_sha") == commit
                 and data.get("status") == "PASS" and data.get("diagnostic_execution_valid") is True
                 and data.get("production_runtime_modified") is False and data.get("gate_e_candidate") is False,
                 "Wrong accepted prerequisite identity")
    _require(p154.get("C153_summary_sha256") == C153_SHA, "C154/C153 lineage mismatch")
    s = p154["summary"]
    required = dict(streams=48, source_entries=82944, added=3072, already_present=79872,
                    conflict_rejections=3072, final_observations=3072,
                    evidence_state_projection_gate_passed=True, actual_v5_evidence_state_exercised=True)
    _require(all(s.get(k) == v for k, v in required.items()), "C154 totals mismatch")
    by154, by153 = _index_streams(p154["records"]), _index_streams(p153["records"])
    streams, metadata = [], {}
    semantics = {a: {o: dict(cases=0, semantic_correct=0) for o in ORDERS} for a in ARMS}
    for key, r154 in by154.items():
        r153 = by153[key]
        _require(r154["split_id"] == r153["split_id"], "Source split mismatch")
        paths = []
        for root, record in ((c154_path.parent, r154), (c153_path.parent, r153)):
            path = _safe_file(root, record["state_file"])
            _require(_sha(path) == record["state_sha256"], "Pinned state artifact hash mismatch")
            protected[path] = record["state_sha256"]
            paths.append(path)
        state = _decode_state(json.loads(paths[0].read_text(encoding="utf-8")))
        payload = json.loads(paths[1].read_text(encoding="utf-8"))
        _require(set(payload) == {"entries", "processed"}, "Unexpected inbox shape")
        entries, claims, cases = payload["entries"], payload["processed"], r153["cases"]
        _require(len(entries) == len(cases) == len(claims) == len(set(claims)) == 1728, "Inbox coverage mismatch")
        claims_set, seen, expected_refs, values, requests = set(claims), set(), {}, {}, {}
        scope = f"C153|{key[0]}|{key[1]}|{key[2]}"
        for entry, case in zip(entries, cases, strict=True):
            _require(set(entry) == {"request", "value"}, "Unexpected inbox entry")
            req, value = entry["request"], entry["value"]
            rid = req["request_id"]
            _require(rid not in seen and rid in claims_set and req["scope_id"] == scope
                     and rid.startswith(scope + "|"), "Inbox request/scope binding mismatch")
            seen.add(rid)
            _require(type(value) is int and value in (0, 1), "Invalid source value")
            _require(req["key"] == case["selected_key"], "Source selected identity mismatch")
            _require(type(req["request_epoch"]) is int and req["request_epoch"] == 1
                     and type(req["provider_generation"]) is int and req["provider_generation"] == 1,
                     "C154 diagnostic clock mapping changed")
            source_id = _source_id(req)
            md = {k: req[k] for k in ("source_sha256", "index_fingerprint", "source_path", "request_epoch", "provider_generation")}
            _require(source_id not in metadata or metadata[source_id] == md, "Snapshot binding conflict")
            metadata[source_id] = md
            ref = EvidenceRef(req["key"], Provenance(source_id, ProvenanceKind.OBSERVED, 1, 1))
            if ref.evidence_id in expected_refs:
                _require(expected_refs[ref.evidence_id] == ref and values[ref.evidence_id] == value,
                         "Inconsistent repeated record evidence")
            else:
                expected_refs[ref.evidence_id], values[ref.evidence_id], requests[ref.evidence_id] = ref, value, req
        _require(state == EvidenceState(1, 1, tuple(expected_refs.values()))
                 and len(state.observations) == 64, "C154 projection/source correspondence mismatch")
        group = semantics[key[1]][key[2]]
        group["cases"] += len(cases)
        group["semantic_correct"] += sum(c["semantic_correct"] is True for c in cases)
        streams.append((r154, state, values, requests))
    expected_semantics = {a: {o: dict(cases=20736, semantic_correct=20727 if a == ARMS[0] else 20736)
                              for o in ORDERS} for a in ARMS}
    _require(semantics == expected_semantics == s["semantic_source_counts"], "Source semantic accounting mismatch")
    _require(len(metadata) == 2, "Expected exactly two trusted persisted snapshots")
    return streams, metadata, semantics


def _gate(summary: dict) -> bool:
    expected_status = dict(RESOLVED=3072, SOURCE_UNBOUND=3072, SNAPSHOT_MISMATCH=3072, RECORD_UNBOUND=3072)
    return bool(summary["references"] == 3072 and summary["resolver_calls"] == 12288
                and summary["status_counts"] == expected_status and summary["failed_cases"] == 0
                and summary["state_mutations"] == 0 and summary["retrieval_calls"] == 3072
                and summary["vectors_scored"] == 196608 and summary["resolved_values"]["0"] > 0
                and summary["resolved_values"]["1"] > 0)


def run(*, c154_summary: Path, c153_summary: Path, output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=False)
    completed = []
    started = time.perf_counter()
    try:
        protected = {c154_summary: C154_SHA, c153_summary: C153_SHA,
                     Path("runs/chatgpt-last-result.json"): C37_SHA,
                     Path("runs/fixtures/v05-c-composition-20260921.pt"): FIXTURE_SHA}
        def check_files():
            for path, expected in protected.items():
                _require(_sha(path) == expected, f"Protected/input hash mismatch: {path}")
        check_files()
        streams, metadata, semantic = _load_inputs(c154_summary, c153_summary, protected)
        registry = {sid: load_binding(md) for sid, md in metadata.items()}
        for sid, binding in registry.items():
            _require(binding.source_id == sid and binding.record_count == 64, "Registry identity/size mismatch")
            protected[Path(binding.source_path)] = binding.source_sha256
        for _, state, _, requests in streams:
            for ref in state.observations:
                handle = registry[ref.provenance.source_id].handles.get(ref.evidence_id)
                req = requests[ref.evidence_id]
                _require(handle is not None and handle.domain == req["domain"] and handle.schema == req["schema"]
                         and handle.operations == tuple(req["operations"]), "Source scope/handle mismatch")
        registry = MappingProxyType(registry)
        (output_dir / "snapshot-registry.json").write_bytes(_bytes({sid: dict(md, record_count=64) for sid, md in metadata.items()}))
        statuses, value_counts = Counter(), Counter({"0": 0, "1": 0})
        failed = calls = vectors = mutations = 0
        for index, (record, state, values, _) in enumerate(streams, 1):
            before = _bytes(asdict(state))
            ref_results = []
            for ref in state.observations:
                sid = ref.provenance.source_id
                other = next(binding for other_id, binding in registry.items() if other_id != sid)
                missing = replace(ref, evidence_id=ref.evidence_id + "|C155-unbound")
                _require(missing.evidence_id not in registry[sid].handles, "Missing-record control is not missing")
                conditions = (("MATCHED", ref, registry), ("MISSING_SOURCE", ref, MappingProxyType({})),
                              ("WRONG_SNAPSHOT", ref, MappingProxyType({sid: other})),
                              ("MISSING_RECORD", missing, registry))
                observations = []
                for scenario, candidate, bindings in conditions:
                    result = resolve_reference(candidate, bindings)
                    ok = _case_pass(result, scenario, candidate, values[ref.evidence_id], 64)
                    # Recorded behavioral failures stay in the report and produce scientific FAIL.
                    failed += int(not ok)
                    calls += result.retrieval_calls
                    vectors += result.vectors_scored
                    statuses[result.status] += 1
                    if scenario == "MATCHED" and result.status == "RESOLVED":
                        value_counts[str(result.value)] += 1
                    observations.append(dict(scenario=scenario, passed=ok, **asdict(result)))
                ref_results.append(dict(reference=asdict(ref), expected_source_value=values[ref.evidence_id], outcomes=observations))
            mutated = _bytes(asdict(state)) != before
            mutations += int(mutated)
            path = output_dir / f"resolution-{record['seed']}-{record['arm'].lower()}-{record['order'].lower()}.json"
            path.write_bytes(_bytes(dict(references=ref_results, source_state_preserved=not mutated)))
            completed.append(dict(seed=record["seed"], split_id=record["split_id"], arm=record["arm"], order=record["order"],
                                  references=len(ref_results), state_preserved=not mutated,
                                  result_file=path.name, result_sha256=_sha(path)))
            print(f"[C155] stream {index}/48 refs=64 checks=256 failed_so_far={failed} remaining={48-index}", flush=True)
        check_files()
        summary = dict(source_streams=48, references=sum(r["references"] for r in completed),
                       resolver_calls=sum(statuses.values()), status_counts=dict(statuses), failed_cases=failed,
                       state_mutations=mutations, retrieval_calls=calls, vectors_scored=vectors,
                       resolved_values=dict(value_counts), source_semantic_counts=semantic,
                       model_loading=False, new_neural_scoring=False, fresh_seed_count=0, training_steps=0,
                       actual_v5_evidence_state_exercised=True, payload_dereference_exercised=True,
                       retrieval_exercised=True, actual_reference_path="PersistedStructuralRetrievalAdapter exact64",
                       production_state_commit=False, controller_exercised=False, answer_exercised=False,
                       controller_reobservation_exercised=False,
                       new_observation_committed=False, crash_recovery_exercised=False,
                       wall_clock_seconds=time.perf_counter() - started)
        passed = _gate(summary)
        summary["payload_dereference_gate_passed"] = passed
        report = dict(experiment_id=EXPERIMENT_ID, stage=STAGE, status="PASS" if passed else "FAIL",
                      diagnostic_execution_valid=True, production_runtime_modified=False, gate_e_candidate=False,
                      commit_sha=subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
                      C154_summary_sha256=C154_SHA, C153_summary_sha256=C153_SHA,
                      input_sha256={str(p): v for p, v in protected.items()}, summary=summary, records=completed,
                      limitations=[
                          "Reference-level diagnostic; 3072 refs repeat 64 records across 48 separate states",
                          "Source semantic totals are reaggregated, not new query or answer accuracy",
                          "Trusted registry metadata derives from hash-pinned C153 requests; not a learned source resolver",
                          "Missing source/record controls indicate unbound references, not proof of real-world absence",
                          "Wrong-snapshot control swaps bindings before any payload read; not a network-security claim",
                          "Loaded snapshot contents stay fixed; file hashes are checked at setup/end, not concurrent freshness",
                          "Existing exact64 adapter is a measured reference path, not bounded production retrieval",
                          "Reading existing evidence does not advance clocks or commit a new observation",
                          "No Controller, ANSWER, durable state publication, restoration or crash recovery; Gate E NOT PASSED",
                      ])
        temp = output_dir / "summary.partial.json"
        temp.write_bytes(_bytes(report))
        temp.replace(output_dir / "summary.json")
        return report
    except Exception as exc:
        (output_dir / "invalid.json").write_bytes(_bytes(dict(experiment_id=EXPERIMENT_ID, status="INVALID",
            diagnostic_execution_valid=False, error=str(exc), completed_streams=len(completed))))
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description="C155 provenance-bound reference payload dereference")
    parser.add_argument("--c154-summary", type=Path, required=True)
    parser.add_argument("--c153-summary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print("C155 streams=48; references=3072; resolver_calls=12288; exact_retrieval_calls=3072", flush=True)
    print("C155 controls=MISSING_SOURCE,WRONG_SNAPSHOT,MISSING_RECORD; no fallback; zero is valid", flush=True)
    print("C155 model_loading=False; training=0; payload_read=True; new_observation_commit=False; ANSWER=False", flush=True)
    result = run(c154_summary=args.c154_summary, c153_summary=args.c153_summary, output_dir=args.output_dir)
    print("=== C155 RESULT ===", flush=True)
    print(json.dumps(dict(result, records="omitted; see summary.json"), indent=2, allow_nan=False), flush=True)
    return 0  # A measured FAIL is valid execution, not an exception.


if __name__ == "__main__":
    raise SystemExit(main())
