"""C169: frozen Gate-E interface-readiness inventory, collected in one batch.

No candidate repair or learned weights. Prefix probes stop before neural layers;
scripted policies/resolvers are explicit fixtures, not learned performance.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from dataclasses import asdict, fields, replace
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import time

from fold_lm.v05_benchmarks import gate_e_c168_necessity_observability as prior

EXPERIMENT_ID = "C169-v5e-frozen-interface-readiness-batch"
STAGE = "V5-E-FROZEN-INTERFACE-READINESS-BATCH"
BASE = "5c181fe061e494a9ded2ccdfe6a6a94aa56321e2"
C168_SHA = "3ef1433d0f2678237f70d1dddf8b3de4783ba676fba15b607281b97f7839124c"
SECTIONS = ("D1_TASK_INPUT", "D2_CONTROL_LANE", "D3_REOBSERVATION",
            "D4_RUNTIME_CONTEXT", "D5_ACTION_DISPATCH", "D6_OUTPUT_CONTRACT")
OWN = ("fold_lm/v05_benchmarks/gate_e_c169_interface_batch.py",
       "tests_lm/test_v05_c169_interface_batch.py", "tools/run_c169.ps1",
       "docs/experiment-ledger-addendum-c169-preregistration.md")
PIN_MORE = ("fold_lm/v05_benchmarks/gate_e_c168_necessity_observability.py",
            "tests_lm/test_v05_c168_necessity_observability.py", "tools/run_c168.ps1",
            "fold_lm/v05_benchmarks/gate_e_c159_terminal_result.py",
            "docs/gate-e-evaluation-contract-v0.1.md")
EXPECTED_COUNTS = dict(feature_prefix_captures=19, observation_probes=8,
    decision_input_captures=8, authority_probes=8, scripted_cycles=8,
    scripted_policy_calls=9, reobservations=17, fixture_resolver_calls=6,
    terminal_emissions=4)
require, blob, sha = prior.require, prior.blob, prior.sha


def manifest():
    return dict(schema_version=1, experiment_id=EXPERIMENT_ID, sections=list(SECTIONS),
        parent_sha256=C168_SHA, historical_base=BASE, source_more=list(PIN_MORE),
        control_width=4, width=8, operation_vocab_size=1,
        feature_probe="baseline + 16 single-coordinate changes + 2 slot permutations",
        observation_cases=["missing-old0", "missing-old1", "dependency-off",
            "reference-mismatch", "source-unbound", "snapshot-mismatch", "zero", "one"],
        context_grid="availability x permission x acquisition_allowance; each Boolean",
        authority_grid="attempted x permission x acquisition_allowance; each Boolean",
        dispatch_actions=list(range(6)), output_bits=[0, 1],
        counts=dict(EXPECTED_COUNTS), learned_forward_calls=0, checkpoint_loads=0,
        adapter_calls=0, training_steps=0, fresh_seed_count=0,
        policy="scripted logits for dispatch only; not trained Controller behavior",
        resolver="controlled in-memory results; not persisted retrieval validation",
        decision="all sections collected; gaps/finite violations => valid negative; invalid setup => INVALID",
        scope="interface inventory, NOT full Gate E or new logical solver")


def section(name, evidence, *, gaps=(), violations=()):
    return dict(section_id=name, status="FAIL" if violations else "GAP" if gaps else "OBSERVED_BOUNDARY",
                gaps=list(gaps), violations=list(violations), evidence=evidence)


def aggregate(items):
    require([x.get("section_id") for x in items] == list(SECTIONS), "Missing/reordered section")
    require(all(isinstance(x.get("gaps"), list) and isinstance(x.get("violations"), list)
                for x in items), "Malformed section result")
    return dict(sections_completed=len(items), gap_sections=sum(bool(x["gaps"]) for x in items),
        finite_violation_sections=sum(bool(x["violations"]) for x in items),
        interface_ready=all(not x["gaps"] and not x["violations"] for x in items))


def validate_parent(path):
    require(sha(path) == C168_SHA, "C168 hash mismatch")
    p = json.loads(Path(path).read_text(encoding="utf-8"))
    require(p.get("experiment_id") == prior.EXPERIMENT_ID and p.get("stage") == prior.STAGE
        and p.get("commit_sha") == BASE and p.get("status") == "FAIL"
        and p.get("diagnostic_execution_valid") is True and p.get("passed") is False
        and p.get("production_runtime_modified") is False and p.get("gate_e_candidate") is False,
        "Expected accepted C168 valid negative")
    require(len(p.get("records", [])) == 8 and len(p.get("source_controls", [])) == 4,
            "Full C168 report required")
    return p


def inherited_input_audit(p):
    result = prior.analyze(p["records"])
    require(all(p["summary"].get(k) == v for k, v in result.items()), "C168 reaggregation mismatch")
    for row in p["records"]:
        require(all(row[k] == v for k, v in prior.necessity(row["operator"], row["known_a"]).items()),
                "C168 evaluator mismatch")
    return section(SECTIONS[0], dict(inherited_reaggregation=result,
        new_c168_captures=0, inherited_field_pairs=p["field_pairs"]),
        gaps=["current task/operator/known-fact route absent"] if result["conflicting_classes"] else [])


class Captured(Exception):
    def __init__(self, value):
        self.value = value


def feature_prefix(w, c, op, meter):
    """Execute actual router feature construction, with no parameterized layer.

    The operation embedding is an explicit all-zero fixture for fixed operation0.
    The norm callback captures and aborts BEFORE normalization or learned layers.
    """
    import torch
    from fold_lm.v05.controller import ControlLaneActionRouter, ControlLaneRouterConfig
    def stop(x):
        raise Captured(prior.tensor_record(x))
    def forbidden(*args):
        raise prior.InvalidExecution("Parameterized layer unexpectedly reached")
    proxy = SimpleNamespace(config=ControlLaneRouterConfig(width=8, control_width=4,
        operation_vocab_size=1, hidden_width=8, action_count=6),
        operation_embedding=lambda ids: torch.zeros((len(ids), 4), dtype=w.dtype, device=w.device),
        norm=stop, hidden=forbidden, activation=forbidden, action_head=forbidden)
    try:
        ControlLaneActionRouter.forward(proxy, w, c, op)
    except Captured as event:
        meter["feature_prefix_captures"] += 1
        return event.value
    raise prior.InvalidExecution("Feature capture not reached")


def lane_audit(p, meter):
    import torch
    t = p["records"][0]["capture"]["tensors"]
    w, c = [torch.tensor(t[k]["values"], dtype=torch.float32) for k in ("working", "context")]
    op = torch.tensor(t["operation_ids"]["values"], dtype=torch.int64)
    base = feature_prefix(w, c, op, meter); rows = []
    for side in ("working", "context"):
        for channel in range(8):
            a, b = w.clone(), c.clone()
            (a if side == "working" else b)[0, 0, channel] += .25
            got = feature_prefix(a, b, op, meter)
            rows.append(dict(side=side, channel=channel, changed=got != base, feature=got))
    d = torch.zeros_like(w); d[0, 0, 0] = .25
    slots = torch.cat((w+d, w-d), dim=1); contexts = c.repeat(1, 2, 1)
    left = feature_prefix(slots, contexts, op, meter)
    right = feature_prefix(slots.flip(1), contexts.flip(1), op, meter)
    return section(SECTIONS[1], dict(baseline=base, coordinate_probes=rows,
        slot_permutation_equal=left == right, balanced_two_slots_equal_baseline=left == base,
        input_shapes=[list(slots.shape), list(contexts.shape)],
        note="Intentional four-channel mean pooling; tail storage alone is not a task interface."))


def fixture(meter):
    import numpy as np
    from fold_lm.v05 import state as core
    from fold_lm.v05_benchmarks import gate_e_c153_evidence_admission as admit
    from fold_lm.v05_benchmarks import gate_e_c156_request_reobservation as obs
    from fold_lm.v05_benchmarks import gate_e_c158_live_recovery as rec
    from fold_lm.v05_benchmarks import gate_e_c159_terminal_result as term
    md = dict(source_sha256=hashlib.sha256(b"C169:fixture-only").hexdigest(),
              index_fingerprint="C169:no-index", source_path="C169_NO_FILE")
    sid = "persisted-snapshot:" + hashlib.sha256(json.dumps(md, sort_keys=True,
                                                  separators=(",", ":")).encode()).hexdigest()
    ref = core.EvidenceRef("B", core.Provenance(sid, core.ProvenanceKind.OBSERVED, 1, 1))
    read = obs.ReadRequest("C169|request", "C169", ref, "synthetic", "bit", ("read",))
    req = admit.Request("C169|request", "C169", "B", "synthetic", "bit", ("read",), **md)
    def forbidden(*args, **kwargs):
        raise prior.InvalidExecution("Unexpected fetch/admission/publication")
    def working(dependency=1, old=1):
        return core.WorkingState(1, 7, np.array([[1., dependency, 1., old, .125, -.25, .375, -.5]]))
    def reobserve(*args):
        meter["reobservations"] += 1
        return obs.reobserve(*args)
    def resolver(status, value=None):
        def resolve(*args):
            meter["fixture_resolver_calls"] += 1
            e = None if value is None else SimpleNamespace(key="B", domain="synthetic", schema="bit",
                operations=("read",), evidence_value=value, **md)
            return SimpleNamespace(status=status, value=value, evidence=e, retrieval_calls=0, vectors_scored=0)
        return resolve
    def ops(resolve):
        return SimpleNamespace(reobserve=reobserve, control_inputs=obs.control_inputs,
            resolver=resolve, empty_inbox=admit.State, fetch=forbidden, admit=forbidden,
            entry_ref=forbidden, project=forbidden)
    return SimpleNamespace(core=core, observe=obs, recovery=rec, terminal=term, ref=ref,
        read=read, request=req, working=working, resolver=resolver, ops=ops, reobserve=reobserve,
        missing=core.EvidenceState(1, 1, ()), full=core.EvidenceState(1, 1, (ref,)),
        budget=core.BudgetState(3, 1), forbidden=forbidden)


def observation_audit(f, meter):
    other = replace(f.ref, provenance=replace(f.ref.provenance, source_id="C169:other"))
    wrong = replace(f.full, observations=(other,))
    cases = [("missing-old0", f.missing, 1, 0, "unused", None),
        ("missing-old1", f.missing, 1, 1, "unused", None),
        ("dependency-off", f.missing, 0, 1, "unused", None),
        ("reference-mismatch", wrong, 1, 1, "unused", None),
        ("source-unbound", f.full, 1, 1, "SOURCE_UNBOUND", None),
        ("snapshot-mismatch", f.full, 1, 1, "SNAPSHOT_MISMATCH", None),
        ("zero", f.full, 1, 1, "RESOLVED", 0), ("one", f.full, 1, 0, "RESOLVED", 1)]
    rows = []; observations = []
    for name, state, dependency, old, status, value in cases:
        working = f.working(dependency, old); before = working.slots.copy()
        got = f.reobserve(f.read, state, working, f.budget, {}, f.resolver(status, value))
        observations.append(got); meter["observation_probes"] += 1
        rows.append(dict(case_id=name, status=got.status, value=got.value,
            prior_working=before.tolist(), new_working=got.working.slots.tolist(),
            controller_working=prior.tensor_record(f.observe.control_inputs([got])),
            budget=asdict(got.budget), internal_step=got.working.internal_step,
            state_same=got.evidence_state is state, input_preserved=(before == working.slots).all().item()))
    expected_status = ["REFERENCE_UNBOUND"]*3 + ["REFERENCE_MISMATCH", "SOURCE_UNBOUND",
                       "SNAPSHOT_MISMATCH", "RESOLVED", "RESOLVED"]
    healthy = all(r["status"] == status and r["value"] == (None if i < 6 else i-6)
        and r["state_same"] and r["input_preserved"] and r["internal_step"] == 8
        and r["budget"] == dict(internal_steps_remaining=2, acquisitions_remaining=1)
        and r["new_working"][0][0:2] == r["prior_working"][0][0:2]
        and r["new_working"][0][4:] == r["prior_working"][0][4:]
        for i, (r, status) in enumerate(zip(rows, expected_status, strict=True)))
    return section(SECTIONS[2], dict(probes=rows,
        reason_identity_in_controller_tensor=len({blob(rows[i]["controller_working"])
                                                  for i in (0, 3, 4, 5)}),
        note="Resolver outcomes are controlled fixtures; zero/one is not tested via disk IO."),
        violations=[] if healthy else ["reobservation identity/payload/immutability/accounting mismatch"]), observations[0]


def context_audit(f, observation, meter):
    rows = []; authority = []
    for available in (False, True):
        for permission in (False, True):
            for allowance in (0, 1):
                o = replace(observation, budget=replace(observation.budget, acquisitions_remaining=allowance))
                def stop(w, c, op):
                    raise Captured(dict(working=prior.tensor_record(w), context=prior.tensor_record(c),
                                        operation_ids=prior.tensor_record(op)))
                try:
                    f.recovery._decision(stop, o, available, f.ops(f.forbidden))
                except Captured as event:
                    rows.append(dict(available=available, permission=permission, acquisition_allowance=allowance,
                                     tensors=event.value)); meter["decision_input_captures"] += 1
                else:
                    raise prior.InvalidExecution("Decision capture not reached")
    for attempted in (False, True):
        for permission in (False, True):
            for allowance in (0, 1):
                result = f.recovery._authorize(f.recovery.Permission(permission),
                    replace(f.budget, acquisitions_remaining=allowance), attempted)
                expected = ("ATTEMPT_LIMIT" if attempted else "PERMISSION_DENIED" if not permission
                            else "BUDGET_EXHAUSTED" if allowance == 0 else "AUTHORIZED")
                authority.append(dict(attempted=attempted, permission=permission, allowance=allowance,
                                      result=result, correct=result == expected))
                meter["authority_probes"] += 1
    return section(SECTIONS[3], dict(contexts=rows, distinct_tensor_classes=len({blob(x["tensors"]) for x in rows}),
        authority=authority, note="Permission is runtime-side; not passed to _decision. No learned policy tested."),
        violations=["runtime authority mismatch"] if not all(r["correct"] for r in authority) else [])


def scripted_cycle(f, actions, state, resolve, meter):
    import torch
    pending = iter(actions)
    def policy(*args):
        try:
            action = next(pending)
        except StopIteration as exc:
            raise prior.InvalidExecution("Unexpected extra policy request") from exc
        meter["scripted_policy_calls"] += 1
        logits = torch.zeros((1, 6), dtype=torch.float32); logits[0, action] = 1
        return logits
    meter["scripted_cycles"] += 1
    return f.recovery.cycle(policy, f.read, f.request, state, f.working(), f.budget,
        {}, f.recovery.Permission(False), f.ops(resolve), lambda x: x)


def dispatch_audit(f, meter):
    rows = []
    for action in range(6):
        r = scripted_cycle(f, [action, 5] if action == 2 else [action], f.missing, f.forbidden, meter)
        rows.append(dict(action=action, terminal=r["terminal"], steps=r["steps"],
            acquisitions=r["acquisitions"], publications=r["publications"], final_budget=r["final_budget"]))
    unsupported = [r["action"] for r in rows if r["terminal"] == "UNEXPECTED_ACTION"]
    return section(SECTIONS[4], dict(probes=rows, unsupported_indices=unsupported,
        note="Scripted dispatch coverage. This is not frozen Controller action accuracy or an end-to-end answer."),
        gaps=["selected-record cycle lacks handlers for indices " + str(unsupported)] if unsupported else [],
        violations=["fixture denial escaped"] if any(r["acquisitions"] or r["publications"] for r in rows) else [])


def output_audit(f, meter):
    rows = []
    bound = f.terminal.BoundRequest(f.read.request_id, f.read.scope_id, "B", f.ref.provenance.source_id, 1, 1)
    for value in (0, 1):
        native = scripted_cycle(f, [0], f.full, f.resolver("RESOLVED", value), meter)
        # The already-accepted observations-only representation bridge, not a new repair.
        adapted = deepcopy(native); adapted["final_evidence"]["observations"] = list(adapted["final_evidence"]["observations"])
        before = blob(adapted)
        out = f.terminal.emit_terminal(bound, bound.request_id, adapted); meter["terminal_emissions"] += 1
        corrupt = deepcopy(adapted); corrupt["final_value"] = 1-value
        rejected = f.terminal.emit_terminal(bound, bound.request_id, corrupt); meter["terminal_emissions"] += 1
        rows.append(dict(observed_value=value, output=asdict(out), mismatch_output=asdict(rejected),
                         input_preserved=blob(adapted) == before))
    schema_fields = [x.name for x in fields(f.terminal.TerminalResult)]
    has_derived_contract = all(x in schema_fields for x in ("expression_id", "supporting_references", "derivation_kind"))
    guards = all(r["output"]["status"] == "ANSWERED" and r["output"]["reason"] == "OBSERVED_VALUE"
        and r["output"]["value"] == r["observed_value"] and r["mismatch_output"]["status"] == "REJECTED"
        and r["mismatch_output"]["value"] is None and r["input_preserved"] for r in rows)
    return section(SECTIONS[5], dict(probes=rows, terminal_schema=f.terminal.SCHEMA, fields=schema_fields,
        required_extension_fields=["expression_id", "supporting_references", "derivation_kind"],
        note="Field names specify this extension proposal, not universal requirements. Source schema is observed-bit-only."),
        gaps=[] if has_derived_contract else ["no explicit derived-expression/proof result in inspected C159 schema"],
        violations=[] if guards else ["observed-bit or mismatch guard failed"])


def check_sources(root):
    pinned, hashes = prior.check_sources(root)
    for name in PIN_MORE:
        wanted = prior.git(root, "rev-parse", BASE+":fold/"+name).decode().strip()
        require(prior.git(root, "rev-parse", "HEAD:fold/"+name).decode().strip() == wanted, "Source drift: "+name)
        canonical = prior.git(root, "show", BASE+":fold/"+name); raw = (root/name).read_bytes()
        require(raw == canonical or raw == canonical.replace(b"\n", b"\r\n"), "Working source drift: "+name)
        pinned[name] = wanted; hashes[str((root/name).resolve())] = hashlib.sha256(raw).hexdigest()
    for name in OWN:
        canonical = prior.git(root, "show", "HEAD:fold/"+name); raw = (root/name).read_bytes()
        require(raw == canonical or raw == canonical.replace(b"\n", b"\r\n"), "Uncommitted own source: "+name)
        hashes[str((root/name).resolve())] = hashlib.sha256(raw).hexdigest()
    return pinned, hashes


def regression_modules(root):
    return prior.regression_modules(root) + ["tests_lm.test_v05_c169_interface_batch"]


def run(*, c168_summary, output_dir, expected_head):
    root = Path(__file__).resolve().parents[2]
    def guard():
        require(prior.git(root, "rev-parse", "HEAD").decode().strip() == expected_head, "HEAD mismatch")
        require(prior.git(root, "branch", "--show-current").decode().strip() == "feat/sft-target-loss", "Branch mismatch")
        require(not prior.git(root, "status", "--porcelain", "--untracked-files=no").strip(), "Tracked tree dirty")
    guard(); pins, protected = check_sources(root); p = validate_parent(c168_summary)
    protected[str(Path(c168_summary).resolve())] = C168_SHA
    out = Path(output_dir); out.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter(); items = []; meter = Counter()
    plan_file = out/"diagnostic-plan.json"
    plan_file.write_bytes(blob(dict(manifest(), source_blobs=pins))); plan_hash = sha(plan_file)
    protected[str(plan_file.resolve())] = plan_hash
    try:
        print("[C169] plan fixed; 6 independent sections; no training or learned weights", flush=True)
        f = fixture(meter)
        items.append(inherited_input_audit(p))
        print("[C169] 1/6 D1_TASK_INPUT collected", flush=True)
        items.append(lane_audit(p, meter)); print("[C169] 2/6 D2_CONTROL_LANE collected", flush=True)
        item, observation = observation_audit(f, meter)
        items.append(item); print("[C169] 3/6 D3_REOBSERVATION collected", flush=True)
        items.append(context_audit(f, observation, meter)); print("[C169] 4/6 D4_RUNTIME_CONTEXT collected", flush=True)
        items.append(dispatch_audit(f, meter)); print("[C169] 5/6 D5_ACTION_DISPATCH collected", flush=True)
        items.append(output_audit(f, meter)); print("[C169] 6/6 D6_OUTPUT_CONTRACT collected", flush=True)
        require(dict(meter) == EXPECTED_COUNTS, "Incomplete/unexpected fixture accounting: "+str(dict(meter)))
        summary = aggregate(items)
        for path, expected in protected.items():
            require(sha(path) == expected, "Protected input changed: "+path)
        guard(); check_sources(root)
        report = dict(experiment_id=EXPERIMENT_ID, stage=STAGE, commit_sha=expected_head,
            status="PASS" if summary["interface_ready"] else "FAIL", diagnostic_execution_valid=True,
            production_runtime_modified=False, gate_e_candidate=False, C168_summary_sha256=C168_SHA,
            summary=summary, sections=items, measured_counts=dict(meter), source_blobs=pins,
            input_sha256=protected, plan=dict(file=plan_file.name, sha256=plan_hash),
            learned_forward_calls=0, checkpoint_loads=0, adapter_calls=0, training_steps=0, fresh_seed_count=0,
            wall_clock_seconds=time.perf_counter()-started,
            limitations=["frozen inspected path only, not all FOLD modules or full Gate E",
                "D1 reuses accepted C168 captures, not fresh live ranking",
                "D2 embedding is a zero fixture and captures before norm/learned layers",
                "D3/D6 resolver outcomes and D5/D6 policy logits are controlled fixtures",
                "gaps are extension readiness findings, not regressions of accepted tasks",
                "no candidate repair, necessity learning, logical answer solver or new holdout"])
        (out/"summary.json").write_bytes(blob(report))
        print("=== C169 RESULT ===", flush=True); print(blob(report).decode(), flush=True)
        return report
    except Exception as exc:
        (out/"invalid.json").write_bytes(blob(dict(experiment_id=EXPERIMENT_ID, status="INVALID",
            diagnostic_execution_valid=False, error=str(exc), sections=items, measured_counts=dict(meter))))
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--c168-summary", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-head", required=True)
    run(**vars(parser.parse_args()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
