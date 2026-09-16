"""C168: source-bound, pre-forward necessity observability diagnostic.

This is NOT a logical-query encoder or a learned necessity benchmark. Logical
operator/known-A are audit-side visible task fields for a proposed extension;
this experiment measures what the existing selected-record interface carries.
The capture uses original C160/C156/C158 functions and stops before weights run.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import re
import subprocess
import time
from types import SimpleNamespace

EXPERIMENT_ID = "C168-v5e-task-necessity-input-observability"
STAGE = "V5-E-TASK-NECESSITY-INPUT-OBSERVABILITY"
BASE = "2f1f3a06e9c4499db34ad1e9aea8b4225fc8e095"
C167_SHA = "5907d4b2dd4e66a9a2d8a6017b68ab8461a9bfca6bd90dd01c1774f5c3e020e9"
MANIFEST_SHA = "35824233cdc5061e004ddbb1633fc260fcbc5a35ebbeb67793f7705059e2fbfd"
C167_COMMIT = "a3eb2dba7c3c74de90d228f1c6d2648ef1cee8d1"
SOURCE_BLOBS = {
    "fold_lm/v05/state.py": "aa3f4938f6b5d403d8ee05c4220f686695cef3f0",
    "fold_lm/v05/controller.py": "e726bdb05cb0b99b409448f8f56832078658dd04",
    "fold_lm/v05_benchmarks/gate_e_c153_evidence_admission.py": "c8c27ec1622274c5407f722d8224fd11caf3f289",
    "fold_lm/v05_benchmarks/gate_e_c156_request_reobservation.py": "4aa260b35fb5acc8d2cfd90a9f6addb96f5fba31",
    "fold_lm/v05_benchmarks/gate_e_c160_live_query_result.py": "a2ed2c1be6f55dc068fb734e1a38ac216f06f002",
    "fold_lm/v05_benchmarks/gate_e_c158_live_recovery.py": "2ca63e6dfe8f827d9c85db03b3f13c82c39143ec",
    "tools/run_c167.ps1": "7c5d6e9838d4ce7bd2bfec0e43458eb749fd1789",
}
# Transitive definitions are also pinned to BASE before importing.
EXTRA_PINNED = ("fold_lm/v05/commit_context.py", "fold_lm/v05/receipt_replay.py")
OWN_FILES = ("fold_lm/v05_benchmarks/gate_e_c168_necessity_observability.py",
             "tests_lm/test_v05_c168_necessity_observability.py", "tools/run_c168.ps1")


class InvalidExecution(ValueError):
    """Malformed setup or provenance; not a valid representational collision."""


def require(ok, message):
    if not ok:
        raise InvalidExecution(message)


def blob(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def bit(value):
    if type(value) is not int or value not in (0, 1):
        raise ValueError("An integer bit, not bool, is required")
    return value


def truth(operator, a, b):
    a, b = bit(a), bit(b)
    if operator == "OR":
        return a | b
    if operator == "AND":
        return a & b
    raise ValueError("Only AND/OR are registered")


def necessity(operator, a):
    """Evaluator only: quantify both completions, never consult the actual hidden b."""
    outputs = [truth(operator, a, b) for b in (0, 1)]
    return dict(possible_outputs=sorted(set(outputs)),
                requires_acquisition=(outputs[0] != outputs[1]))


def manifest():
    # Eight challenge rows = four visible semantic cases x two nuisance stale bits.
    rows = [dict(case_id=f"{op}-{a}-stale{s}", operator=op, known_a=a,
                 b_observed=False, stale_bit=s)
            for op in ("AND", "OR") for a in (0, 1) for s in (0, 1)]
    controls = [dict(case_id=f"selected-bit-available{int(v)}-stale{s}",
                     available=v, stale_bit=s)
                for v in (False, True) for s in (0, 1)]
    return dict(schema_version=1, experiment_id=EXPERIMENT_ID, cases=rows,
                source_controls=controls, hidden_b="not instantiated; evaluator enumerates 0/1",
                capture_scope="post-selection boundary, NOT logical text through C151",
                source_fixture="synthetic unread references; not C167 persisted corpus")


def input_key(capture):
    """Compare complete received tensors plus availability/budget, not task labels/IDs."""
    return blob(dict(tensors=capture["tensors"], runtime=capture["runtime"]))


def analyze(rows):
    if not rows or len({r["case_id"] for r in rows}) != len(rows):
        raise ValueError("Nonempty uniquely identified rows required")
    groups = defaultdict(list)
    # Group BEFORE labels are consulted. Exact serialized values, not a hash alone.
    for row in rows:
        groups[input_key(row["capture"])].append(row)
    classes = []
    errors = 0
    for key, members in sorted(groups.items(), key=lambda x: x[0]):
        labels = [r["requires_acquisition"] for r in members]
        if any(type(v) is not bool for v in labels):
            raise ValueError("Boolean necessity labels required after grouping")
        counts = Counter(labels)
        unavoidable = len(members) - max(counts.values())
        errors += unavoidable
        classes.append(dict(input_sha256=hashlib.sha256(key).hexdigest(),
            case_ids=sorted(r["case_id"] for r in members), conflicting=len(counts) > 1,
            require_count=counts[True], unnecessary_count=counts[False],
            minimum_classification_errors=unavoidable))
    return dict(cases=len(rows), equivalence_classes=len(classes),
                conflicting_classes=sum(g["conflicting"] for g in classes),
                classification_error_lower_bound=errors, classes=classes)


def tensor_record(t):
    return dict(shape=list(t.shape), dtype=str(t.dtype), values=t.detach().cpu().tolist())


def capture_current_inputs(stale_bit, available=True):
    """Capture at the original _decision model call, without a model/encoder repair.

    Deliberately accepts no task/operator/known_a/hidden_b/expected label. The
    missing route is an observed limitation, not an invented semantic encoder.
    """
    bit(stale_bit)
    if type(available) is not bool:
        raise ValueError("Availability must be Boolean")
    import numpy as np
    from fold_lm.v05 import state as core
    from fold_lm.v05_benchmarks import gate_e_c153_evidence_admission as admission
    from fold_lm.v05_benchmarks import gate_e_c156_request_reobservation as observe
    from fold_lm.v05_benchmarks import gate_e_c158_live_recovery as recovery
    from fold_lm.v05_benchmarks import gate_e_c160_live_query_result as old

    class Captured(Exception):
        def __init__(self, payload):
            self.payload = payload

    def forbidden(*args, **kwargs):
        raise InvalidExecution("Unexpected resolver/retrieval/emitter operation in capture")

    provenance = core.Provenance("C168:UNREAD:synthetic", core.ProvenanceKind.OBSERVED, 1, 1)
    full = core.EvidenceState(1, 1, tuple(core.EvidenceRef(k, provenance)
        for k in ["B"] + [f"unused-{i:02d}" for i in range(63)]))
    meter = SimpleNamespace(calls=0, vectors=0)
    binding = SimpleNamespace(source_id=provenance.source_id, evidence_time=1, revision=1,
        source_sha256=hashlib.sha256(b"C168:not-a-persisted-corpus").hexdigest(),
        index_fingerprint="C168:UNREAD:synthetic", source_path="C168_UNREAD_NO_FILE",
        adapter=meter)
    ops = SimpleNamespace(reobserve=observe.reobserve, control_inputs=observe.control_inputs,
                          resolver=forbidden)

    def intercept(model, request, admission_request, state, working, budget,
                  registry, permission, forwarded_ops, deliver):
        require(len(state.observations) == 63 and request.reference not in state.observations,
                "Capture must receive the original selected-reference-absent state")
        require(asdict(budget) == dict(internal_steps_remaining=3, acquisitions_remaining=1)
                and permission.allowed is True, "Base runtime context drift")
        before_state, before_slots = blob(asdict(state)), working.slots.copy()
        observation = observe.reobserve(request, state, working, budget, registry, ops.resolver)
        require(observation.status == "REFERENCE_UNBOUND" and observation.value is None,
                "Source control did not observe missing reference")
        require(observation.retrieval_calls == observation.vectors_scored == 0,
                "Missing reference unexpectedly retrieved evidence")
        require(blob(asdict(state)) == before_state and np.array_equal(working.slots, before_slots),
                "Capture mutated source state")
        require(observation.working.internal_step == 8
                and asdict(observation.budget) == dict(internal_steps_remaining=2, acquisitions_remaining=1),
                "Source internal-step accounting mismatch")
        def spy(w, c, op):
            payload = dict(tensors=dict(working=tensor_record(w), context=tensor_record(c),
                                       operation_ids=tensor_record(op)),
                runtime=dict(permission=True, acquisition_available=available,
                    budget=asdict(observation.budget), evidence_time=1, revision=1,
                    reference_count=63, status=observation.status),
                observation=dict(value=observation.value, internal_step=observation.working.internal_step,
                    working=observation.working.slots.tolist()),
                model_forward_calls=0, capture_callbacks=1, retrieval_calls=0,
                initial_state_sha256=hashlib.sha256(before_state).hexdigest())
            raise Captured(payload)
        # Uses the original context canonicalization and operation-id construction.
        recovery._decision(spy, observation, available, forwarded_ops)
        raise InvalidExecution("Capture callback was not reached")

    api = SimpleNamespace(Request=admission.Request, EvidenceRef=core.EvidenceRef,
        Provenance=core.Provenance, OBSERVED=core.ProvenanceKind.OBSERVED,
        ReadRequest=observe.ReadRequest, WorkingState=core.WorkingState,
        BudgetState=core.BudgetState, Permission=recovery.Permission, cycle=intercept,
        BoundRequest=forbidden, emit=forbidden)
    try:
        old.execute_selected("C168-CAPTURE", "fixed-request", dict(key="B", domain="synthetic",
            schema="bit", operations=("read",)), None, full, binding, {}, api, ops, stale_bit)
    except Captured as event:
        require(meter.calls == meter.vectors == 0, "Unexpected adapter call")
        return event.payload
    raise InvalidExecution("Unintercepted terminal output")


def audit(capture_fn=capture_current_inputs):
    plan = manifest()
    # Build and freeze ALL captured inputs before invoking the truth-table evaluator.
    captured = [dict(row, capture=capture_fn(row["stale_bit"], True)) for row in plan["cases"]]
    control_rows = [dict(row, capture=capture_fn(row["stale_bit"], row["available"]))
                    for row in plan["source_controls"]]
    frozen = blob(captured)
    rows = [dict(row, **necessity(row["operator"], row["known_a"])) for row in captured]
    require(blob(captured) == frozen, "Evaluator changed inputs")
    # Independent symbolic reference: direct Boolean controlling-value rule.
    for row in rows:
        closed = (row["known_a"] == (1 if row["operator"] == "AND" else 0))
        require(row["requires_acquisition"] is closed, "Truth-table task control mismatch")
    control_scored = [dict(case_id=r["case_id"], capture=r["capture"],
                           requires_acquisition=r["available"]) for r in control_rows]
    control_analysis = analyze(control_scored)
    require(control_analysis["conflicting_classes"] == 0
            and control_analysis["equivalence_classes"] == 2, "Original availability control failed")
    visible_groups = defaultdict(set)
    for row in rows:
        visible_groups[(row["operator"], row["known_a"])].add(row["requires_acquisition"])
    require(len(visible_groups) == 4 and all(len(g) == 1 for g in visible_groups.values()),
            "Full-visible symbolic reference failed")
    all_captures = [r["capture"] for r in captured + control_rows]
    require(all(c["model_forward_calls"] == c["retrieval_calls"] == 0
                and c["capture_callbacks"] == 1 for c in all_captures), "Unexpected capture accounting")
    summary = analyze(rows)
    pairs = []
    for i, left in enumerate(rows):
        for right in rows[i+1:]:
            same_nuisance = left["stale_bit"] == right["stale_bit"]
            delta = [k for k in ("operator", "known_a") if left[k] != right[k]]
            if same_nuisance and len(delta) == 1:
                pairs.append(dict(left=left["case_id"], right=right["case_id"], changed=delta[0],
                                  same_input=input_key(left["capture"]) == input_key(right["capture"])))
    require(len(rows) == 8 and len(control_rows) == 4 and len(pairs) == 8,
            "Registered case/pair coverage mismatch")
    summary.update(source_control_cases=4, source_control_classes=control_analysis["equivalence_classes"],
        visible_reference_classes=len(visible_groups),
        visible_reference_conflicts=sum(len(g) > 1 for g in visible_groups.values()),
        lost_visible_field_pairs=sum(p["same_input"] for p in pairs),
        capture_callbacks=sum(c["capture_callbacks"] for c in all_captures),
        model_forward_calls=sum(c["model_forward_calls"] for c in all_captures),
        model_loads=0, retrieval_calls=sum(c["retrieval_calls"] for c in all_captures),
        live_cycle_executions=0, training_steps=0, fresh_seed_count=0,
        truth_table_completions=16, task_semantic_cases=4,
        supported_logical_query_encoder=False)
    passed = summary["conflicting_classes"] == 0 and summary["lost_visible_field_pairs"] == 0
    return dict(passed=passed, summary=summary, records=rows,
                source_controls=control_rows, field_pairs=pairs)


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args])


def check_sources(root):
    pinned = dict(SOURCE_BLOBS)
    for name in EXTRA_PINNED:
        pinned[name] = git(root, "rev-parse", BASE+":fold/"+name).decode().strip()
    hashes = {}
    for name, wanted in pinned.items():
        require(git(root, "rev-parse", "HEAD:fold/"+name).decode().strip() == wanted,
                "Historical source changed: " + name)
        canonical = git(root, "show", "HEAD:fold/"+name)
        raw = (root/name).read_bytes()
        require(raw == canonical or raw == canonical.replace(b"\n", b"\r\n"),
                "Working source differs beyond LF/CRLF: " + name)
        hashes[str((root/name).resolve())] = hashlib.sha256(raw).hexdigest()
    for name in OWN_FILES:
        hashes[str((root/name).resolve())] = sha(root/name)
    return pinned, hashes


def validate_parent(path):
    require(sha(path) == C167_SHA, "C167 summary SHA256 mismatch")
    p = json.loads(Path(path).read_text(encoding="utf-8"))
    require(p.get("experiment_id") == "C167-v5e-live-query-warm-reference"
            and p.get("stage") == "V5-E-LIVE-QUERY-WARM-REFERENCE"
            and p.get("commit_sha") == C167_COMMIT and p.get("status") == "PASS"
            and p.get("diagnostic_execution_valid") is True, "Expected accepted C167")
    require(isinstance(p.get("records"), list) and len(p["records"]) == 48,
            "Full C167 summary required; not a console extract")
    require(p["summary"].get("episodes") == 165888
            and p["summary"].get("warm_reference_gate_passed") is True, "C167 profile mismatch")
    return p


def regression_modules(root):
    text = (Path(root)/"tools/run_c167.ps1").read_text(encoding="utf-8")
    names = re.findall(r'^\s*"(tests_lm\.[a-zA-Z0-9_]+)"\s*$', text, re.M)
    require(len(names) == 51 and len(set(names)) == 51, "Pinned C167 module list drift")
    return names + ["tests_lm.test_v05_c168_necessity_observability"]


def run(*, c167_summary, output_dir, expected_head):
    root = Path(__file__).resolve().parents[2]
    require(git(root, "rev-parse", "HEAD").decode().strip() == expected_head, "HEAD mismatch")
    require(git(root, "branch", "--show-current").decode().strip() == "feat/sft-target-loss", "Branch mismatch")
    require(not git(root, "status", "--porcelain", "--untracked-files=no").strip(), "Tracked tree dirty")
    pinned, protected = check_sources(root)
    validate_parent(c167_summary)
    protected[str(Path(c167_summary).resolve())] = C167_SHA
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    try:
        plan = manifest()
        require(hashlib.sha256(blob(plan)).hexdigest() == MANIFEST_SHA, "Case manifest drift")
        plan_path = out/"input-plan.json"
        plan_path.write_bytes(blob(dict(plan, source_blobs=pinned, C167_summary_sha256=C167_SHA)))
        plan_hash = sha(plan_path)
        print("[C168] plan fixed; 8 challenge cases + 4 controls; model/training/retrieval=0", flush=True)
        result = audit()
        print(f"[C168] captured=12/12 conflicting_classes={result['summary']['conflicting_classes']} "
              f"minimum_errors={result['summary']['classification_error_lower_bound']}", flush=True)
        for path, wanted in protected.items():
            require(sha(path) == wanted, "Protected input changed: " + path)
        check_sources(root)
        require(sha(plan_path) == plan_hash, "Plan changed")
        require(git(root, "rev-parse", "HEAD").decode().strip() == expected_head, "HEAD drift")
        require(not git(root, "status", "--porcelain", "--untracked-files=no").strip(), "Tracked tree changed")
        report = dict(experiment_id=EXPERIMENT_ID, stage=STAGE,
            status="PASS" if result["passed"] else "FAIL", diagnostic_execution_valid=True,
            production_runtime_modified=False, gate_e_candidate=False, commit_sha=expected_head,
            C167_summary_sha256=C167_SHA, source_blobs=pinned, input_sha256=protected,
            plan=dict(file=plan_path.name, sha256=plan_hash), **result,
            wall_clock_seconds=time.perf_counter()-started,
            limitations=["post-selection interface readiness, not raw logical query support",
                "operator and known_a are not routed by existing helper; no invented encoder",
                "capture callback aborts before learned forward; no Controller actions measured",
                "synthetic unread64-reference fixture; no persisted-corpus or old-trace replay",
                "eight rows are four semantic cases crossed with nuisance stale_bit",
                "source availability controls are not a claim about logical necessity learning",
                "Gate E remains NOT PASSED"])
        (out/"summary.json").write_bytes(blob(report))
        print("=== C168 RESULT ===", flush=True)
        print(blob(report).decode(), flush=True)
        return report
    except Exception as exc:
        (out/"invalid.json").write_bytes(blob(dict(experiment_id=EXPERIMENT_ID,
            status="INVALID", diagnostic_execution_valid=False, error=str(exc))))
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--c167-summary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-head", required=True)
    run(**vars(parser.parse_args()))
    return 0  # Finite scientific negatives must still save/return a report.


if __name__ == "__main__":
    raise SystemExit(main())
