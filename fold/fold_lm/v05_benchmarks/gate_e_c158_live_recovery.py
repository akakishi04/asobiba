"""C158: frozen Controller -> bounded live reference-recovery cycle.

The source record is already selected and belongs to a fixed trusted snapshot.
No query ranker, new training, language answer, durable commit, or new epoch.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict, dataclass, replace
import hashlib
import json
import math
from pathlib import Path, PureWindowsPath
import subprocess
import time
from types import MappingProxyType, SimpleNamespace

import numpy as np
import torch

from fold_lm.v05.controller import ControlLaneActionRouter, ControlLaneRouterConfig, canonicalize_boolean_channels
from fold_lm.v05.state import EvidenceState, WorkingState, BudgetState

EXPERIMENT_ID = "C158-v5e-bounded-controller-reference-recovery"
STAGE = "V5-E-BOUNDED-CONTROLLER-REFERENCE-RECOVERY"
C157_SHA = "b521eafc61fedaf3b9d2f78fb9c591de654b95cfa6689938c8c042fbc200b934"
C157_COMMIT = "40f63b46c67d5c71a8e8bc75ac6ba07ddd3ef05a"
C156_SHA = "b2c43401a6731400de8e18697f82f5e220aeb3f2368737d9dee5847f7ca1f84f"
ROUTER_SEEDS = (20261741, 20261742, 20261743)
CONFIG = dict(width=8, control_width=4, operation_vocab_size=1, hidden_width=8, action_count=6)
SCENARIOS = ("WARM_PRESENT", "COLD_RECOVER", "COLD_MISSING_DELIVERY", "COLD_PERMISSION_DENIED", "COLD_BUDGET_EXHAUSTED")
MAX_DECISIONS = 3
REPLAY_ATOL = 1e-5


class InvalidInput(ValueError):
    pass


def _require(ok, message):
    if not ok:
        raise InvalidInput(message)


def _sha(path):
    with Path(path).open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def _bytes(data):
    return (json.dumps(data, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def _safe_file(root, name):
    _require(isinstance(name, str) and name not in ("", ".", "..")
             and Path(name).name == PureWindowsPath(name).name == name, "Unsafe artifact filename")
    path = Path(root) / name
    _require(path.resolve().parent == Path(root).resolve(), "Artifact escaped run directory")
    return path


def _fingerprint(model):
    h = hashlib.sha256()
    for name, tensor in sorted(model.state_dict().items()):
        h.update(name.encode()); h.update(str(tuple(tensor.shape)).encode()); h.update(str(tensor.dtype).encode())
        h.update(tensor.detach().cpu().contiguous().numpy().tobytes())
    return h.hexdigest()


def _header(data):
    _require(data.get("experiment_id") == "C157-v5e-learned-controller-readback-bridge"
             and data.get("commit_sha") == C157_COMMIT and data.get("status") == "PASS"
             and data.get("diagnostic_execution_valid") is True
             and data.get("production_runtime_modified") is False and data.get("gate_e_candidate") is False
             and data.get("C156_summary_sha256") == C156_SHA and data.get("config") == CONFIG,
             "Expected accepted full C157 report")
    s = data.get("summary", {})
    expected = dict(source_requests=82944, source_views=331776, unique_working_inputs=3,
        unique_working_context_inputs=6, routers=3, fresh_router_seeds=list(ROUTER_SEEDS),
        router_train_steps_each=900, decisions=1990656, forward_batches=576, action_errors=0,
        nonpositive_margins=0, input_mutations=0, weight_mutations=0, matched_zero_correct=209952,
        matched_one_correct=287712, actual_action_counts={"0":497664,"2":746496,"5":746496},
        full_router_pass_count=3, controller_bridge_gate_passed=True,
        learned_controller_exercised=True, answer_generation_exercised=False,
        live_reobservation_exercised=False, retrieval_exercised=False, action_execution_exercised=False,
        production_state_commit=False)
    _require(all(s.get(k) == v for k,v in expected.items()), "C157 registered profile mismatch")
    _require(math.isfinite(s.get("minimum_expected_margin", math.nan))
             and s["minimum_expected_margin"] > 0, "C157 margin invalid")
    rows = data.get("records")
    _require(isinstance(rows, list) and [r.get("seed") for r in rows] == list(ROUTER_SEEDS),
             "Three ordered full router records required, not console extract")
    for r in rows:
        _require(r.get("weights_preserved") is True and r.get("errors") == r.get("nonpositive_margins") == 0
                 and r.get("optimizer_steps") == 900 and len(r.get("streams", [])) == 48,
                 "C157 router record mismatch")


def _load_router(root, row):
    c = row["checkpoint"]
    _require(c["file"] == f"controller-{row['seed']}.pt", "Wrong router checkpoint filename")
    path = _safe_file(root, c["file"])
    _require(_sha(path) == c["sha256"] and path.stat().st_size == c["serialized_bytes"], "Checkpoint hash/size mismatch")
    saved = torch.load(path, map_location="cpu", weights_only=True)
    _require(saved.get("config") == CONFIG and saved.get("seed") == row["seed"]
             and saved.get("recipe") == "C113._train_router", "Checkpoint metadata mismatch")
    model = ControlLaneActionRouter(ControlLaneRouterConfig(**saved["config"]))
    model.load_state_dict(saved["state_dict"], strict=True)
    model.eval(); model.requires_grad_(False)
    _require(all(torch.isfinite(t).all() for t in model.state_dict().values())
             and _fingerprint(model) == c["state_sha256"], "Checkpoint weights mismatch")
    return model, path


def _replay(models, prior, p156, c156_path, root, protected, bridge):
    """All original rows, not just six cached patterns; no re-training."""
    n = 0; minimum = math.inf; counts = Counter()
    for mi, (model, record) in enumerate(zip(models, prior["records"], strict=True), 1):
        start_hash = _fingerprint(model)
        for source, old in zip(p156["records"], record["streams"], strict=True):
            _require((old["source_seed"], old["source_arm"], old["source_order"], old["split_id"],
                      old["source_trace_file"], old["source_trace_sha256"]) ==
                     (source["seed"], source["arm"], source["order"], source["split_id"],
                      source["result_file"], source["result_sha256"]), "Replay trace binding mismatch")
            w, values, _, _, _ = bridge._load_stream(c156_path.parent, source)
            protected[_safe_file(c156_path.parent, source["result_file"])] = source["result_sha256"]
            path = _safe_file(root, old["file"])
            _require(_sha(path) == old["sha256"] and path.stat().st_size == old["serialized_bytes"], "Decision array hash/size mismatch")
            protected[path] = old["sha256"]
            with np.load(path, allow_pickle=False) as arrays:
                _require(set(arrays.files) == {m+"_"+k for m in bridge.MODES for k in ("logits","actions","expected","margins")}, "Wrong replay array fields")
                for mode in bridge.MODES:
                    inputs = bridge.router_inputs(w, mode); before = tuple(x.clone() for x in inputs)
                    logits, _ = bridge.score_router(model, inputs)
                    scored = bridge._assess(logits, values, mode)
                    _require(all(torch.equal(a,b) for a,b in zip(before, inputs)), "Replay input mutation")
                    saved_logits = arrays[mode+"_logits"]
                    _require(saved_logits.shape == logits.shape and np.isfinite(saved_logits).all()
                             and np.allclose(logits, saved_logits, atol=REPLAY_ATOL, rtol=0), "C157 logit replay drift")
                    for key in ("actions", "expected", "margins"):
                        a, b = scored[key], arrays[mode+"_"+key]
                        _require(a.shape == b.shape and np.isfinite(b).all() and
                                 (np.allclose(a,b,atol=REPLAY_ATOL,rtol=0) if key == "margins" else np.array_equal(a,b)), "C157 decision/margin replay drift")
                    _require(bool(scored["strict"].all()), "Accepted C157 action profile not reproduced")
                    n += len(values); counts.update(map(str, scored["actions"].tolist()))
                    minimum = min(minimum, float(scored["margins"].min()))
        _require(_fingerprint(model) == start_hash, "Replay weight mutation")
        print(f"[C158] router {mi}/3 full_C157_replay_match=True remaining_routers={3-mi}", flush=True)
    _require(n == 1990656 and dict(counts) == prior["summary"]["actual_action_counts"]
             and abs(minimum-prior["summary"]["minimum_expected_margin"]) <= REPLAY_ATOL, "Replay reaggregation mismatch")
    return n


class MeteredAdapter:
    """Count actual underlying calls independently of episode status labels."""
    def __init__(self, adapter):
        self.adapter = adapter
        self.calls = self.vectors = 0

    def __getattr__(self, name):
        return getattr(self.adapter, name)

    def retrieve(self, *args, **kwargs):
        self.calls += 1
        evidence, stats = self.adapter.retrieve(*args, **kwargs)
        vectors = stats.get("vectors_scored")
        if type(vectors) is not int or vectors < 0:
            raise RuntimeError("Non-numeric measured scan cost")
        self.vectors += vectors
        return evidence, stats


@dataclass(frozen=True)
class Permission:
    allowed: bool
    def __post_init__(self):
        if type(self.allowed) is not bool:
            raise TypeError("Permission must be Boolean")


def _authorize(permission, budget, already_attempted):
    if already_attempted:
        return "ATTEMPT_LIMIT"
    if not permission.allowed:
        return "PERMISSION_DENIED"
    if budget.acquisitions_remaining == 0:
        return "BUDGET_EXHAUSTED"
    return "AUTHORIZED"


def _decision(model, observation, available, ops):
    w = ops.control_inputs([observation])
    context = torch.zeros_like(w)
    context[0,0,:4] = torch.tensor((0,int(available),0,0), dtype=torch.float32)
    context = canonicalize_boolean_channels(context, (0,1,2,3), threshold=.5)
    op = torch.zeros(1, dtype=torch.int64)
    before = (w.clone(), context.clone(), op.clone())
    with torch.inference_mode():
        logits = model(w, context, op)
    if logits.shape != (1,6) or not torch.isfinite(logits).all():
        raise RuntimeError("Invalid Controller output")
    mutated = any(not torch.equal(a,b) for a,b in zip(before,(w,context,op)))
    return int(logits.argmax(1).item()), logits[0].tolist(), mutated


def cycle(model, request, admission_request, state, working, budget, registry, permission, ops, deliver):
    """Run at most one acquisition attempt; never replace the model's raw action.

    No scenario, expected action, expected payload or semantic label is accepted.
    `deliver` is the explicit transport fixture (identity or missing delivery).
    State publication is an in-process pair of immutable objects, not durability.
    """
    if not isinstance(state, EvidenceState) or not isinstance(working, WorkingState) or not isinstance(budget, BudgetState):
        raise TypeError("Actual V5 states required")
    if not isinstance(permission, Permission) or budget.internal_steps_remaining < MAX_DECISIONS:
        raise ValueError("Registered bounded-cycle budget/permission required")
    if (admission_request.request_id, admission_request.scope_id, admission_request.key) != (request.request_id, request.scope_id, request.reference.evidence_id):
        raise ValueError("Request binding mismatch")
    source_bytes = _bytes(asdict(state)); old_slots = working.slots.copy()
    original_work = working; original_state = state
    inbox = ops.empty_inbox()
    visible = True; attempted = False
    steps = []; terminal = "DECISION_LIMIT"; last = None
    input_mutations = 0; acquisitions = 0; publications = 0
    for _ in range(MAX_DECISIONS):
        before_state = _bytes(asdict(state)); before_work = working.slots.copy()
        o = ops.reobserve(request, state, working, budget, registry, ops.resolver)
        input_mutations += int(_bytes(asdict(state)) != before_state or not np.array_equal(working.slots,before_work))
        state, working, budget = o.evidence_state, o.working, o.budget
        action, logits, mutated = _decision(model, o, visible, ops)
        input_mutations += int(mutated); last = o
        trace = dict(status=o.status, value=o.value, reference=asdict(o.reference) if o.reference is not None else None,
            action=action, logits=logits, available=visible, working=working.slots[0].tolist(),
            internal_step=working.internal_step, internal_remaining=budget.internal_steps_remaining,
            acquisition_remaining=budget.acquisitions_remaining, evidence_time=state.evidence_time, revision=state.revision,
            working_evidence_time=working.evidence_time, authority=None, admission=None, projection=None, fetched=None)
        steps.append(trace)
        if action == 0:
            terminal = "ANSWER_ACTION"; break
        if action == 5:
            terminal = "STOP_UNRESOLVED"; break
        if action != 2:
            terminal = "UNEXPECTED_ACTION"; break
        reason = _authorize(permission, budget, attempted)
        trace["authority"] = reason; attempted = True; visible = False
        if reason != "AUTHORIZED":
            continue
        budget = replace(budget, acquisitions_remaining=budget.acquisitions_remaining-1)
        acquisitions += 1
        fetched = ops.fetch(admission_request, registry)
        fe = fetched.evidence
        trace["fetched"] = None if fe is None else {k:getattr(fe,k,None) for k in
            ("key","evidence_value","source_sha256","index_fingerprint","source_path")}
        received = deliver(fetched)
        status, new_inbox = ops.admit(inbox, admission_request, received)
        trace["admission"] = status
        if status != "COMMITTED":
            continue
        ref = ops.entry_ref(new_inbox.entries[-1])
        pstatus, next_state = ops.project(state, ref)
        trace["projection"] = pstatus
        if ref != request.reference or pstatus not in ("ADDED", "ALREADY_PRESENT"):
            trace["projection"] = "BINDING_OR_PROJECTION_FAILURE"
            continue
        inbox, state = new_inbox, next_state
        publications += int(pstatus == "ADDED")
    return dict(terminal=terminal, steps=steps, final_value=last.value if last is not None else None,
        final_reference=asdict(last.reference) if last is not None and last.reference is not None else None,
        final_evidence=asdict(state), final_budget=asdict(budget), final_working=working.slots[0].tolist(),
        final_internal_step=working.internal_step, acquisitions=acquisitions, publications=publications,
        inbox_entries=len(inbox.entries), input_mutations=input_mutations,
        original_state_preserved=_bytes(asdict(original_state)) == source_bytes,
        original_working_preserved=np.array_equal(original_work.slots,old_slots))


def _assess_episode(result, scenario, reference, source_state, expected_value, initial_budget):
    """Only this post-execution evaluator sees scenario labels/expected payloads."""
    if scenario not in SCENARIOS or type(expected_value) is not int or expected_value not in (0,1):
        raise ValueError("Invalid episode evaluator arguments")
    warm = scenario == "WARM_PRESENT"; recovered = scenario == "COLD_RECOVER"
    succeeds = warm or recovered
    actions = [0] if warm else [2, 0 if recovered else 5]
    statuses = ["RESOLVED"] if warm else ["REFERENCE_UNBOUND", "RESOLVED" if recovered else "REFERENCE_UNBOUND"]
    steps = result["steps"]
    margins = []
    for i,step in enumerate(steps):
        target = actions[i] if i < len(actions) else 5
        logits = step["logits"]
        if len(logits) != 6 or not all(math.isfinite(x) for x in logits):
            raise ValueError("Nonfinite/malformed stored action")
        margins.append(logits[target]-max(x for j,x in enumerate(logits) if j != target))
    expected_state = source_state if succeeds else replace(source_state,
        observations=tuple(r for r in source_state.observations if r != reference))
    # Projection appends the restored reference; compare identity maps, not tuple order.
    final = result["final_evidence"]
    expected_refs = {r.evidence_id:asdict(r) for r in expected_state.observations}
    actual_refs = {r["evidence_id"]:r for r in final["observations"]}
    acquisition_count = int(scenario in ("COLD_RECOVER","COLD_MISSING_DELIVERY"))
    reads = {"WARM_PRESENT":1,"COLD_RECOVER":2,"COLD_MISSING_DELIVERY":1,
             "COLD_PERMISSION_DENIED":0,"COLD_BUDGET_EXHAUSTED":0}[scenario]
    checks = dict(
        actions=[s["action"] for s in steps] == actions,
        statuses=[s["status"] for s in steps] == statuses,
        margins=len(margins) == len(actions) and all(m > 0 for m in margins),
        terminal=result["terminal"] == ("ANSWER_ACTION" if succeeds else "STOP_UNRESOLVED"),
        value=(type(result["final_value"]) is int and result["final_value"] == expected_value) if succeeds else result["final_value"] is None,
        reference=result["final_reference"] == (asdict(reference) if succeeds else None),
        evidence=actual_refs == expected_refs and len(final["observations"]) == len(expected_refs),
        clocks=final["evidence_time"] == source_state.evidence_time and final["revision"] == source_state.revision,
        budget=result["final_budget"] == dict(internal_steps_remaining=3-len(actions),
            acquisitions_remaining=initial_budget.acquisitions_remaining-acquisition_count),
        internal_step=result["final_internal_step"] == 7+len(actions),
        attempts=result["acquisitions"] == acquisition_count,
        publication=result["publications"] == int(recovered) and result["inbox_entries"] == int(recovered),
        immutable=result["original_state_preserved"] and result["original_working_preserved"] and result["input_mutations"] == 0,
        cost=result["retrieval_calls"] == reads and result["vectors_scored"] == 64*reads,
    )
    for i,step in enumerate(steps):
        present = warm or (recovered and i == 1)
        raw = [1.,1.,1. if present else 0.,float(expected_value) if present else 0.,.125,-.25,.375,-.5]
        checks[f"working_{i}"] = step["working"] == raw
        checks[f"available_{i}"] = step["available"] == (i == 0)
        checks[f"clock_budget_{i}"] = (step["evidence_time"] == step["working_evidence_time"] == source_state.evidence_time
            and step["revision"] == source_state.revision and step["internal_step"] == 8+i
            and step["internal_remaining"] == 2-i
            and step["acquisition_remaining"] == initial_budget.acquisitions_remaining-(acquisition_count if i else 0))
    if not warm and steps:
        expected_auth = {"COLD_PERMISSION_DENIED":"PERMISSION_DENIED", "COLD_BUDGET_EXHAUSTED":"BUDGET_EXHAUSTED"}.get(scenario,"AUTHORIZED")
        checks["authority"] = steps[0]["authority"] == expected_auth
        checks["admission"] = steps[0]["admission"] == ("COMMITTED" if recovered else "MISSING" if scenario == "COLD_MISSING_DELIVERY" else None)
    if acquisition_count and steps:
        fetched = steps[0]["fetched"]
        checks["actual_lookup_before_delivery"] = (isinstance(fetched,dict) and fetched["key"] == reference.evidence_id
                and type(fetched["evidence_value"]) is int and fetched["evidence_value"] == expected_value)
    if not acquisition_count:
        checks["no_unpermitted_fetch"] = all(s["fetched"] is None for s in steps)
    return dict(passed=all(checks.values()), checks=checks, expected_actions=actions, margins=margins)


def _plan(streams):
    """One representative per snapshot/key, chosen only by stored identity."""
    selected = {}
    for record, state, values, requests in streams:
        refs = {r.evidence_id:r for r in state.observations}
        for key, req in requests.items():
            identity = (record["order"],key)
            candidate = (req["request_id"],record["seed"],record["arm"])
            old = selected.get(identity)
            if old is not None:
                _require(old[1] == refs[key] and old[3] == values[key], "Conflicting repeated record")
            if old is None or candidate < old[0]:
                selected[identity] = (candidate,refs[key],state,values[key],req)
    _require(len(selected) == 128 and Counter(o for o,k in selected) == {"CANONICAL":64,"PERMUTED":64}, "Reference coverage mismatch")
    return [(order,key,*selected[(order,key)][1:]) for order,key in sorted(selected)]


def _gate(s):
    return bool(s.get("episodes") == 1920 and s.get("failed_episodes") == 0
        and s.get("controller_decisions") == 3456 and s.get("retrieval_calls") == 1536
        and s.get("vectors_scored") == 98304 and s.get("executed_acquisitions") == 768
        and s.get("published_references") == 384 and s.get("internal_steps_consumed") == 3456
        and s.get("terminal_counts") == {"ANSWER_ACTION":768,"STOP_UNRESOLVED":1152}
        and s.get("resolved_values") == {"0":324,"1":444}
        and s.get("full_router_pass_count") == 3 and s.get("weight_mutations") == 0
        and s.get("replay_decisions") == 1990656)


def run(*, c157_summary, c156_summary, c154_summary, c153_summary, output_dir):
    from fold_lm.v05_benchmarks import gate_e_c157_controller_bridge as bridge
    from fold_lm.v05_benchmarks import gate_e_c156_request_reobservation as observe
    from fold_lm.v05_benchmarks import gate_e_c155_payload_dereference as payload
    from fold_lm.v05_benchmarks import gate_e_c154_evidence_state_projection as projection
    from fold_lm.v05_benchmarks import gate_e_c153_evidence_admission as admission
    output_dir.mkdir(parents=True, exist_ok=False)
    started=time.perf_counter(); completed=[]
    torch.set_num_threads(2); torch.set_float32_matmul_precision("highest")
    try:
        protected={c157_summary:C157_SHA,c156_summary:C156_SHA,c154_summary:payload.C154_SHA,
            c153_summary:payload.C153_SHA,Path("runs/chatgpt-last-result.json"):payload.C37_SHA,
            Path("runs/fixtures/v05-c-composition-20260921.pt"):payload.FIXTURE_SHA}
        def check_files():
            for path,sha in protected.items():
                _require(_sha(path)==sha,f"Protected input changed: {path}")
        check_files()
        prior=json.loads(c157_summary.read_text(encoding="utf-8")); _header(prior)
        p156=json.loads(c156_summary.read_text(encoding="utf-8")); bridge._header(p156)
        for name,sha in prior["input_sha256"].items():
            p=Path(name); _require(p not in protected or protected[p]==sha,"Conflicting source hashes"); protected[p]=sha
        check_files()
        streams,metadata,semantics=payload._load_inputs(c154_summary,c153_summary,protected)
        _require(semantics==prior["summary"]["source_semantic_counts"],"Source semantics changed")
        representatives=_plan(streams)
        plan=[dict(order=o,key=k,reference=asdict(ref),request=req) for o,k,ref,state,value,req in representatives]
        plan_path=output_dir/"episode-plan.json"; plan_path.write_bytes(_bytes(dict(scenarios=SCENARIOS,routers=ROUTER_SEEDS,records=plan)))
        models=[]
        for row in prior["records"]:
            model,path=_load_router(c157_summary.parent,row); models.append(model); protected[path]=row["checkpoint"]["sha256"]
        replay_count=_replay(models,prior,p156,c156_summary,c157_summary.parent,protected,bridge)
        bindings={}
        for sid,md in metadata.items():
            b=payload.load_binding(md); bindings[sid]=replace(b,adapter=MeteredAdapter(b.adapter)); protected[Path(b.source_path)]=b.source_sha256
        registry=MappingProxyType(bindings)
        def fetch(req, reg):
            binding=reg[payload._source_id(asdict(req))]
            return admission._fetch(req,asdict(binding.handles[req.key]),binding.adapter)
        def entry_ref(entry):
            raw=asdict(entry); raw["request"]["operations"]=list(raw["request"]["operations"])
            return projection._ref_from_entry(raw)
        ops=SimpleNamespace(reobserve=observe.reobserve,control_inputs=observe.control_inputs,resolver=payload.resolve_reference,
            empty_inbox=admission.State,fetch=fetch,admit=admission.admit,entry_ref=entry_ref,project=projection.project_observation)
        by_scenario={s:Counter() for s in SCENARIOS}; terminals=Counter(); bits=Counter(); total=bad=decisions=acquisitions=pubs=internal=mutations=0
        for mi,model in enumerate(models,1):
            fingerprint=_fingerprint(model); model_failed=0
            path=output_dir/f"episodes-{ROUTER_SEEDS[mi-1]}.jsonl"
            with path.open("w",encoding="utf-8",newline="\n") as f:
                for pi,(order,key,ref,full_state,expected_value,reqdict) in enumerate(representatives):
                    req_args=dict(reqdict); req_args["operations"]=tuple(req_args["operations"])
                    req=admission.Request(**req_args)
                    read_req=observe.ReadRequest(req.request_id,req.scope_id,ref,req.domain,req.schema,req.operations)
                    for scenario in SCENARIOS:
                        state=full_state if scenario=="WARM_PRESENT" else replace(full_state,observations=tuple(r for r in full_state.observations if r.evidence_id!=key))
                        work=WorkingState(1,7,np.array([[1.,1.,1.,float(pi%2),.125,-.25,.375,-.5]]))
                        budget=BudgetState(3,0 if scenario=="COLD_BUDGET_EXHAUSTED" else 1)
                        permission=Permission(scenario!="COLD_PERMISSION_DENIED")
                        deliver=(lambda d:replace(d,evidence=None)) if scenario=="COLD_MISSING_DELIVERY" else (lambda d:d)
                        meter=bindings[ref.provenance.source_id].adapter; before=(meter.calls,meter.vectors)
                        result=cycle(model,read_req,req,state,work,budget,registry,permission,ops,deliver)
                        result.update(retrieval_calls=meter.calls-before[0],vectors_scored=meter.vectors-before[1])
                        judged=_assess_episode(result,scenario,ref,full_state,expected_value,budget)
                        row=dict(router_seed=ROUTER_SEEDS[mi-1],order=order,key=key,source_request_id=req.request_id,scenario=scenario,
                                 result=result,assessment=judged)
                        f.write(json.dumps(row,sort_keys=True,separators=(",",":"),allow_nan=False)+"\n")
                        nbad=int(not judged["passed"]); total+=1;bad+=nbad;model_failed+=nbad;decisions+=len(result["steps"])
                        acquisitions+=result["acquisitions"];pubs+=result["publications"];internal+=3-result["final_budget"]["internal_steps_remaining"]
                        terminals[result["terminal"]]+=1
                        if result["final_value"] is not None: bits[str(result["final_value"])]+=1
                        by_scenario[scenario].update(episodes=1,failed=nbad,retrieval_calls=result["retrieval_calls"],vectors_scored=result["vectors_scored"],
                            acquisitions=result["acquisitions"],publications=result["publications"])
                    if (pi+1)%32==0:
                        print(f"[C158] router {mi}/3 records={pi+1}/128 episodes={(pi+1)*5}/640 failed={model_failed} remaining_records={127-pi}",flush=True)
            unchanged=_fingerprint(model)==fingerprint;mutations+=int(not unchanged)
            completed.append(dict(router_seed=ROUTER_SEEDS[mi-1],episodes=640,failed=model_failed,weights_preserved=unchanged,
                file=path.name,sha256=_sha(path),serialized_bytes=path.stat().st_size,source_checkpoint=prior["records"][mi-1]["checkpoint"]))
        check_files()
        s=dict(episodes=total,failed_episodes=bad,controller_decisions=decisions,
            retrieval_calls=sum(b.adapter.calls for b in bindings.values()),vectors_scored=sum(b.adapter.vectors for b in bindings.values()),
            executed_acquisitions=acquisitions,published_references=pubs,internal_steps_consumed=internal,
            terminal_counts=dict(terminals),resolved_values=dict(bits),by_scenario={k:dict(v) for k,v in by_scenario.items()},
            weight_mutations=mutations,full_router_pass_count=sum(r["failed"]==0 and r["weights_preserved"] for r in completed),
            replay_decisions=replay_count,unique_records=64,snapshot_record_bindings=128,
            fresh_seed_count=0,training_steps=0,model_loading=True,controller_exercised=True,
            action_execution_exercised=True,live_reobservation_exercised=True,answer_action_exercised=True,
            answer_generation_exercised=False,production_state_commit=False,new_evidence_epoch=False,
            wall_clock_seconds=time.perf_counter()-started)
        passed=_gate(s);s["bounded_recovery_gate_passed"]=passed
        report=dict(experiment_id=EXPERIMENT_ID,stage=STAGE,status="PASS" if passed else "FAIL",diagnostic_execution_valid=True,
            production_runtime_modified=False,gate_e_candidate=False,commit_sha=subprocess.check_output(["git","rev-parse","HEAD"],text=True).strip(),
            C157_summary_sha256=C157_SHA,C156_summary_sha256=C156_SHA,input_sha256={str(p):sha for p,sha in protected.items()},
            episode_plan=dict(file=plan_path.name,sha256=_sha(plan_path)),summary=s,records=completed,
            limitations=["Record-level reference recovery within the same pinned observation epoch, not a new world observation",
                "One identity-only representative per snapshot/key, not all original language requests or new relevance scoring",
                "All three C157 routers reused frozen; no new learning or independent tasks",
                "At most one acquisition attempt; permission and budgets are explicit runtime fixtures",
                "Missing delivery discards a real lookup response; not proof of record absence or a network recovery guarantee",
                "ANSWER is a terminal action with readback metadata, not generated language or computed answer content",
                "Diagnostic immutable inbox/state publication only; no crash durability, concurrency or production change",
                "Exact64 acquisition/readback costs include rereads; Gate E remains NOT PASSED"])
        temp=output_dir/"summary.partial.json";temp.write_bytes(_bytes(report));temp.replace(output_dir/"summary.json")
        return report
    except Exception as e:
        (output_dir/"invalid.json").write_bytes(_bytes(dict(experiment_id=EXPERIMENT_ID,status="INVALID",diagnostic_execution_valid=False,
            error=str(e),completed_routers=len(completed))))
        raise


def main():
    p=argparse.ArgumentParser(description="C158 bounded live Controller reference recovery")
    for n in ("c157-summary","c156-summary","c154-summary","c153-summary","output-dir"):
        p.add_argument("--"+n,type=Path,required=True)
    a=p.parse_args()
    print("C158 frozen_routers=3; new_training=0; snapshots=2; records_per_snapshot=64; scenarios=5; episodes=1920",flush=True)
    print("C158 expected_decisions=3456; exact_reads=1536; vectors=98304; max_decisions_per_episode=3",flush=True)
    report=run(**vars(a))
    print("=== C158 RESULT ===",flush=True)
    print(json.dumps(report,indent=2,allow_nan=False),flush=True)
    return 0


if __name__=="__main__":
    raise SystemExit(main())
