"""C159: pinned C158 terminal records -> evidence-bound typed results.

Recorded-output bridge only. Deterministic copy/serialization, not a learned
answer head, language generation, a live-cycle replay, or a production API.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path, PureWindowsPath
import subprocess
import time

EXPERIMENT_ID = "C159-v5e-evidence-bound-terminal-result"
STAGE = "V5-E-EVIDENCE-BOUND-TERMINAL-RESULT"
SOURCE_ID = "C158-v5e-bounded-controller-reference-recovery"
SOURCE_COMMIT = "1b407ef26d6c1f5575482e07f6c8d046a3bff438"
SOURCE_SHA = "6c49a3e681313208881743f1c2991325e4826d4970cb65d5df9cfcebd65173c8"
PLAN_SHA = "0f9d0703a28efc5d9e52a11e261fe58c83411fd75994d81428c4f217b3017f8c"
C37_SHA = "fd4a8da897bdaea9d103a252e30212c7ff842d23300d7c837333e146dee51931"
FIXTURE_SHA = "a52f8209703149407580f7e2965b61b78653030ee992af6d759865736741ca9e"
SEEDS = (20261741, 20261742, 20261743)  # Source identities; no new model execution.
ORDERS = ("CANONICAL", "PERMUTED")
SCENARIOS = ("WARM_PRESENT", "COLD_RECOVER", "COLD_MISSING_DELIVERY", "COLD_PERMISSION_DENIED", "COLD_BUDGET_EXHAUSTED")
REJECTION_COUNTS = {"WRONG_REQUEST": 1920, "WRONG_PROVENANCE": 768,
                    "PAYLOAD_DISAGREEMENT": 768, "FORCED_UNGROUNDED_ANSWER": 1152}
SCHEMA = "c159-terminal-result-v1"


class InvalidInput(ValueError):
    """Invalid prerequisite, distinct from measured emitter behavior."""


def _require(ok: bool, message: str) -> None:
    if not ok:
        raise InvalidInput(message)


def _bytes(data) -> bytes:
    return (json.dumps(data, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def _sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _safe_file(root: Path, name: str) -> Path:
    _require(isinstance(name, str) and name not in ("", ".", "..")
             and Path(name).name == PureWindowsPath(name).name == name, "Unsafe artifact filename")
    result = root / name
    _require(result.resolve().parent == root.resolve(), "Artifact escaped source run")
    return result


def _is_bit(value) -> bool:
    return type(value) is int and value in (0, 1)


def _working(values) -> bool:
    return (isinstance(values, list) and len(values) == 8
            and all(type(x) in (int, float) and math.isfinite(x) for x in values))


@dataclass(frozen=True)
class BoundRequest:
    request_id: str
    scope_id: str
    record_key: str
    source_id: str
    evidence_time: int
    revision: int

    def __post_init__(self):
        if (any(not isinstance(x, str) or not x for x in
                (self.request_id, self.scope_id, self.record_key, self.source_id))
                or not self.request_id.startswith(self.scope_id + "|")
                or not self.source_id.startswith("persisted-snapshot:")
                or any(type(x) is not int or x < 0 for x in (self.evidence_time, self.revision))):
            raise ValueError("Complete request/snapshot binding required")

    def reference(self) -> dict:
        return dict(evidence_id=self.record_key, provenance=dict(source_id=self.source_id,
                    kind="observed", evidence_time=self.evidence_time, revision=self.revision))


@dataclass(frozen=True)
class TerminalResult:
    schema_version: str
    request_id: str
    scope_id: str
    status: str
    reason: str
    value: int | None = None
    record_key: str | None = None
    source_id: str | None = None
    evidence_time: int | None = None
    revision: int | None = None


def emit_terminal(binding: BoundRequest, source_request_id: str, result: dict) -> TerminalResult:
    """Copy only a request-bound final readback. No scenario, expected value or corpus.

    Rejection is not a successful learned STOP. The original action stays in the
    source trace; this output guard does not repair model accuracy.
    """
    if not isinstance(binding, BoundRequest):
        raise TypeError("BoundRequest required")
    def output(status: str, reason: str, value=None):
        if status == "ANSWERED":
            return TerminalResult(SCHEMA, binding.request_id, binding.scope_id, status, reason,
                value, binding.record_key, binding.source_id, binding.evidence_time, binding.revision)
        return TerminalResult(SCHEMA, binding.request_id, binding.scope_id, status, reason)
    if source_request_id != binding.request_id:
        return output("REJECTED", "REQUEST_MISMATCH")
    if not isinstance(result, dict) or not isinstance(result.get("steps"), list) or not result["steps"]:
        return output("REJECTED", "MALFORMED_TERMINAL")
    last = result["steps"][-1]
    if not isinstance(last, dict):
        return output("REJECTED", "MALFORMED_TERMINAL")
    terminal, action = result.get("terminal"), last.get("action")
    if type(action) is not int or (terminal, action) not in (("ANSWER_ACTION", 0), ("STOP_UNRESOLVED", 5)):
        return output("REJECTED", "TERMINAL_ACTION_MISMATCH")
    slots = result.get("final_working")
    if not _working(slots) or slots != last.get("working"):
        return output("REJECTED", "WORKING_MISMATCH")
    state = result.get("final_evidence")
    if not isinstance(state, dict) or not isinstance(state.get("observations"), list):
        return output("REJECTED", "MALFORMED_EVIDENCE")
    if (state.get("evidence_time") != binding.evidence_time or state.get("revision") != binding.revision
            or last.get("evidence_time") != binding.evidence_time or last.get("revision") != binding.revision
            or last.get("working_evidence_time") != binding.evidence_time):
        return output("REJECTED", "CLOCK_MISMATCH")
    if terminal == "STOP_UNRESOLVED":
        if (last.get("status") not in ("REFERENCE_UNBOUND", "SOURCE_UNBOUND", "SNAPSHOT_MISMATCH", "RECORD_UNBOUND")
                or result.get("final_value") is not None or last.get("value") is not None
                or result.get("final_reference") is not None or last.get("reference") is not None
                or slots[2:4] != [0., 0.]):
            return output("REJECTED", "UNRESOLVED_PAYLOAD_LEAK")
        first = result["steps"][0]
        reason = first.get("authority")
        if reason not in ("PERMISSION_DENIED", "BUDGET_EXHAUSTED", "ATTEMPT_LIMIT"):
            reason = "MISSING_DELIVERY" if first.get("admission") == "MISSING" else last["status"]
        return output("UNRESOLVED", reason)
    if last.get("status") != "RESOLVED" or slots[2] != 1.:
        return output("REJECTED", "ANSWER_NOT_GROUNDED")
    reference = binding.reference()
    observations = state["observations"]
    if (result.get("final_reference") != reference or last.get("reference") != reference
            or any(not isinstance(r, dict) or not isinstance(r.get("evidence_id"), str) for r in observations)
            or len({r["evidence_id"] for r in observations}) != len(observations)
            or [r for r in observations if r["evidence_id"] == binding.record_key] != [reference]):
        return output("REJECTED", "REFERENCE_MISMATCH")
    value = result.get("final_value")
    if not _is_bit(value) or not _is_bit(last.get("value")) or last["value"] != value or slots[3] != value:
        return output("REJECTED", "PAYLOAD_MISMATCH")
    # Copy the validated final working payload, not the raw fetched response.
    return output("ANSWERED", "OBSERVED_VALUE", int(slots[3]))


def _binding(plan_row: dict) -> BoundRequest:
    request = plan_row["request"]
    fields = {k: request[k] for k in ("source_sha256", "index_fingerprint", "source_path")}
    _require(all(isinstance(v, str) and v for v in fields.values()), "Incomplete snapshot metadata")
    sid = "persisted-snapshot:" + hashlib.sha256(json.dumps(fields, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    result = BoundRequest(request["request_id"], request["scope_id"], request["key"], sid,
                          request["request_epoch"], request["provider_generation"])
    _require(plan_row["key"] == result.record_key and plan_row["reference"] == result.reference()
             and result.evidence_time == result.revision == 1, "Plan request/reference mismatch")
    return result


def _header(prior: dict) -> None:
    _require(prior.get("experiment_id") == SOURCE_ID and prior.get("commit_sha") == SOURCE_COMMIT
             and prior.get("status") == "PASS" and prior.get("diagnostic_execution_valid") is True
             and prior.get("production_runtime_modified") is False and prior.get("gate_e_candidate") is False,
             "Expected accepted C158 PASS")
    expected = dict(episodes=1920, failed_episodes=0, controller_decisions=3456, retrieval_calls=1536,
        vectors_scored=98304, executed_acquisitions=768, published_references=384, internal_steps_consumed=3456,
        terminal_counts={"ANSWER_ACTION":768,"STOP_UNRESOLVED":1152}, resolved_values={"0":324,"1":444},
        weight_mutations=0, full_router_pass_count=3, replay_decisions=1990656, unique_records=64,
        snapshot_record_bindings=128, fresh_seed_count=0, training_steps=0, answer_generation_exercised=False,
        production_state_commit=False, new_evidence_epoch=False, bounded_recovery_gate_passed=True)
    _require(all(prior.get("summary", {}).get(k) == v for k,v in expected.items()), "C158 aggregate mismatch")
    records = prior.get("records")
    _require(isinstance(records, list) and [r.get("router_seed") for r in records] == list(SEEDS), "Full C158 router records required")
    for r in records:
        _require(r.get("episodes") == 640 and r.get("failed") == 0 and r.get("weights_preserved") is True
                 and r.get("file") == f"episodes-{r['router_seed']}.jsonl", "C158 router profile mismatch")


def _validate_row(row: dict, plan_row: dict, seed: int, scenario: str, refs: dict, known_values: dict) -> None:
    """Reaggregate pinned source behavior. Not the new measured output function."""
    binding = _binding(plan_row)
    _require((row["router_seed"], row["order"], row["key"], row["source_request_id"], row["scenario"]) ==
             (seed, plan_row["order"], binding.record_key, binding.request_id, scenario), "Episode identity/order mismatch")
    r, assessment = row["result"], row["assessment"]
    warm, recovered = scenario == SCENARIOS[0], scenario == SCENARIOS[1]
    success = warm or recovered
    actions = [0] if warm else [2, 0 if recovered else 5]
    statuses = ["RESOLVED"] if warm else ["REFERENCE_UNBOUND", "RESOLVED" if recovered else "REFERENCE_UNBOUND"]
    _require(assessment["passed"] is True and assessment["checks"] and all(v is True for v in assessment["checks"].values())
             and assessment["expected_actions"] == actions, "Source assessment is not accepted")
    steps = r["steps"]
    _require([s["action"] for s in steps] == actions and [s["status"] for s in steps] == statuses, "Source action/status mismatch")
    value = r["final_value"]
    if success:
        _require(_is_bit(value), "Source bit invalid")
        identity = (row["order"], row["key"])
        _require(identity not in known_values or known_values[identity] == value, "Repeated source value changed")
        known_values[identity] = value
    else:
        _require(value is None, "Unresolved source value is not None")
    _require(r["terminal"] == ("ANSWER_ACTION" if success else "STOP_UNRESOLVED")
             and r["final_reference"] == (binding.reference() if success else None), "Source terminal mismatch")
    wanted = dict(refs)
    if not success:
        del wanted[binding.record_key]
    state = r["final_evidence"]
    _require(state["evidence_time"] == state["revision"] == 1
             and len(state["observations"]) == len(wanted)
             and {ref["evidence_id"]:ref for ref in state["observations"]} == wanted, "Source final EvidenceState mismatch")
    acq = int(scenario in (SCENARIOS[1], SCENARIOS[2]))
    initial_acq = int(scenario != SCENARIOS[4])
    reads = (1,2,1,0,0)[SCENARIOS.index(scenario)]
    _require(r["final_budget"] == dict(internal_steps_remaining=3-len(actions), acquisitions_remaining=initial_acq-acq)
             and r["final_internal_step"] == 7+len(actions) and r["acquisitions"] == acq
             and r["publications"] == r["inbox_entries"] == int(recovered)
             and r["input_mutations"] == 0 and r["original_state_preserved"] is True and r["original_working_preserved"] is True
             and r["retrieval_calls"] == reads and r["vectors_scored"] == reads*64, "Source budget/cost/immutability mismatch")
    margins = []
    for i, (step, action) in enumerate(zip(steps, actions, strict=True)):
        present = warm or (recovered and i == 1)
        v = value if present else None
        raw = [1.,1.,float(present),float(v) if present else 0.,.125,-.25,.375,-.5]
        _require(step["value"] == v and step["reference"] == (binding.reference() if present else None)
                 and step["working"] == raw and step["available"] == (i == 0)
                 and step["evidence_time"] == step["revision"] == step["working_evidence_time"] == 1
                 and step["internal_step"] == 8+i and step["internal_remaining"] == 2-i
                 and step["acquisition_remaining"] == initial_acq-(acq if i else 0), "Source live step mismatch")
        logits = step["logits"]
        _require(isinstance(logits,list) and len(logits) == 6 and all(type(x) in (float,int) and math.isfinite(x) for x in logits), "Invalid source logits")
        margin = logits[action]-max(x for j,x in enumerate(logits) if j != action)
        _require(margin > 0, "Source action has nonpositive margin")
        margins.append(margin)
    _require(assessment["margins"] == margins and r["final_working"] == steps[-1]["working"], "Source margin/final working mismatch")
    if not warm:
        authority = "PERMISSION_DENIED" if scenario == SCENARIOS[3] else "BUDGET_EXHAUSTED" if scenario == SCENARIOS[4] else "AUTHORIZED"
        admit = "COMMITTED" if recovered else "MISSING" if scenario == SCENARIOS[2] else None
        _require(steps[0]["authority"] == authority and steps[0]["admission"] == admit, "Source authority/admission mismatch")
    if acq:
        fetched = steps[0]["fetched"]
        _require(isinstance(fetched,dict) and fetched["key"] == binding.record_key and _is_bit(fetched["evidence_value"]), "Missing real source fetch")
        _require(fetched["evidence_value"] == known_values[(row["order"], row["key"])], "Fetched source value mismatch")
    else:
        _require(all(s["fetched"] is None for s in steps), "Source has unpermitted fetch")


def _load_source(source: Path):
    protected = {source:SOURCE_SHA, Path("runs/chatgpt-last-result.json"):C37_SHA,
                 Path("runs/fixtures/v05-c-composition-20260921.pt"):FIXTURE_SHA}
    def check_files():
        for p,h in protected.items():
            _require(_sha(p) == h, f"Protected file changed/missing: {p}")
    check_files()
    prior = json.loads(source.read_text(encoding="utf-8")); _header(prior)
    for name,h in prior["input_sha256"].items():
        p = Path(name)
        _require(p not in protected or protected[p] == h, "Conflicting source hash")
        protected[p] = h
    check_files()
    plan_path = _safe_file(source.parent, prior["episode_plan"]["file"])
    _require(prior["episode_plan"]["sha256"] == PLAN_SHA == _sha(plan_path), "Plan hash mismatch")
    protected[plan_path] = PLAN_SHA
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    _require(plan["scenarios"] == list(SCENARIOS) and plan["routers"] == list(SEEDS) and len(plan["records"]) == 128, "Plan coverage mismatch")
    identities = [(p["order"],p["key"]) for p in plan["records"]]
    _require(identities == sorted(identities) and len(set(identities)) == 128
             and Counter(o for o,k in identities) == {o:64 for o in ORDERS}, "Plan identity mismatch")
    refs = {order:{p["key"]:_binding(p).reference() for p in plan["records"] if p["order"] == order} for order in ORDERS}
    data, values, totals, terminals, bits = [], {}, Counter(), Counter(), Counter()
    scenarios = {s:Counter() for s in SCENARIOS}
    for record in prior["records"]:
        p = _safe_file(source.parent, record["file"])
        _require(_sha(p) == record["sha256"] and p.stat().st_size == record["serialized_bytes"], "Episode trace hash/size mismatch")
        protected[p] = record["sha256"]
        with p.open(encoding="utf-8") as f:
            rows = [json.loads(line) for line in f]
        _require(len(rows) == 640, "Full 640 source episodes required")
        for i,row in enumerate(rows):
            q = plan["records"][i//5]; scenario=SCENARIOS[i%5]
            _validate_row(row,q,record["router_seed"],scenario,refs[q["order"]],values)
            r=row["result"]; terminals[r["terminal"]]+=1
            if r["final_value"] is not None: bits[str(r["final_value"])]+=1
            totals.update(episodes=1,controller_decisions=len(r["steps"]),retrieval_calls=r["retrieval_calls"],vectors_scored=r["vectors_scored"],
                          executed_acquisitions=r["acquisitions"],published_references=r["publications"],internal_steps_consumed=3-r["final_budget"]["internal_steps_remaining"])
            scenarios[scenario].update(episodes=1,failed=0,retrieval_calls=r["retrieval_calls"],vectors_scored=r["vectors_scored"],acquisitions=r["acquisitions"],publications=r["publications"])
        data.append((record,rows))
    s=prior["summary"]
    _require(all(s[k] == v for k,v in totals.items()) and dict(terminals) == s["terminal_counts"] and dict(bits) == s["resolved_values"]
             and {k:dict(v) for k,v in scenarios.items()} == s["by_scenario"] and len(values) == 128, "C158 full trace reaggregation mismatch")
    return prior,plan,data,protected,check_files


def _variants(row: dict):
    result = row["result"]
    yield "WRONG_REQUEST", row["source_request_id"]+"|wrong", deepcopy(result), "REQUEST_MISMATCH"
    if result["terminal"] == "ANSWER_ACTION":
        wrong = deepcopy(result)
        wrong["final_reference"]["provenance"]["source_id"] = "persisted-snapshot:wrong"
        yield "WRONG_PROVENANCE", row["source_request_id"], wrong, "REFERENCE_MISMATCH"
        wrong = deepcopy(result); wrong["final_value"] = 1-wrong["final_value"]
        yield "PAYLOAD_DISAGREEMENT", row["source_request_id"], wrong, "PAYLOAD_MISMATCH"
    else:
        wrong = deepcopy(result); wrong["terminal"] = "ANSWER_ACTION"; wrong["steps"][-1]["action"] = 0
        yield "FORCED_UNGROUNDED_ANSWER", row["source_request_id"], wrong, "ANSWER_NOT_GROUNDED"


def _no_payload(output: TerminalResult) -> bool:
    return all(getattr(output,k) is None for k in ("value","record_key","source_id","evidence_time","revision"))


def _gate(s: dict) -> bool:
    return bool(s.get("source_episodes") == 1920 and s.get("emitter_calls") == 6528
        and s.get("base_status_counts") == {"ANSWERED":768,"UNRESOLVED":1152}
        and s.get("answer_values") == {"0":324,"1":444} and s.get("rejected_controls") == REJECTION_COUNTS
        and s.get("failed_cases") == 0 and s.get("input_mutations") == 0 and s.get("serialization_failures") == 0)


def run(*, c158_summary: Path, output_dir: Path) -> dict:
    output_dir.mkdir(parents=True,exist_ok=False)
    started=time.perf_counter(); records=[]
    try:
        prior,plan,data,protected,check_files=_load_source(c158_summary)
        print("[C159] all 1920 C158 episodes reaggregated; no model/retrieval/live replay",flush=True)
        calls=failed=mutations=serial_failed=0; bases=Counter(); bits=Counter(); rejected=Counter(); reasons=Counter()
        for ri,(record,rows) in enumerate(data,1):
            path=output_dir/f"terminal-results-{record['router_seed']}.jsonl"
            with path.open("w",encoding="utf-8",newline="\n") as f:
                for i,row in enumerate(rows):
                    binding=_binding(plan["records"][i//5]); original=_bytes(row)
                    out=emit_terminal(binding,row["source_request_id"],row["result"]); calls+=1
                    bases[out.status]+=1; reasons[out.reason]+=1
                    expected_status="ANSWERED" if row["result"]["terminal"] == "ANSWER_ACTION" else "UNRESOLVED"
                    good=(out.status == expected_status and out.request_id == binding.request_id and out.scope_id == binding.scope_id)
                    if expected_status == "ANSWERED":
                        good=good and _is_bit(out.value) and out.value == row["result"]["final_value"] and out.record_key == binding.record_key and out.source_id == binding.source_id and out.evidence_time == binding.evidence_time and out.revision == binding.revision
                        if out.value is not None: bits[str(out.value)]+=1
                    else:
                        reason={SCENARIOS[2]:"MISSING_DELIVERY",SCENARIOS[3]:"PERMISSION_DENIED",SCENARIOS[4]:"BUDGET_EXHAUSTED"}[row["scenario"]]
                        good=good and _no_payload(out) and out.reason == reason
                    failed+=int(not good)
                    outputs=[out]; controls=[]
                    for name,rid,result,reason in _variants(row):
                        before=_bytes(result); observed=emit_terminal(binding,rid,result); calls+=1; outputs.append(observed)
                        ok=observed.status == "REJECTED" and observed.reason == reason and _no_payload(observed)
                        if ok: rejected[name]+=1
                        failed+=int(not ok); mutations+=int(_bytes(result)!=before)
                        controls.append(dict(condition=name,output=asdict(observed),passed=ok))
                    for output in outputs:
                        recovered=json.loads(_bytes(asdict(output)))
                        serial_failed+=int(recovered != asdict(output) or (output.value is not None and type(recovered["value"]) is not int))
                    mutations+=int(_bytes(row)!=original)
                    f.write(json.dumps(dict(source_row=i,source_request_id=row["source_request_id"],scenario=row["scenario"],
                        output=asdict(out),passed=good,controls=controls),sort_keys=True,separators=(",",":"),allow_nan=False)+"\n")
            records.append(dict(router_seed=record["router_seed"],source_file=record["file"],source_sha256=record["sha256"],
                file=path.name,sha256=_sha(path),serialized_bytes=path.stat().st_size))
            print(f"[C159] source_router {ri}/3 episodes=640/640 emitter_calls={calls} failed={failed} remaining={3-ri}",flush=True)
        check_files()
        summary=dict(source_episodes=1920,emitter_calls=calls,base_status_counts=dict(bases),base_reasons=dict(reasons),
            answer_values=dict(bits),rejected_controls=dict(rejected),failed_cases=failed,input_mutations=mutations,
            serialization_failures=serial_failed,model_loading=False,training_steps=0,fresh_seed_count=0,
            controller_exercised=False,retrieval_exercised=False,live_cycle_replayed=False,
            structured_result_exercised=True,answer_generation_exercised=False,production_state_commit=False,
            wall_clock_seconds=time.perf_counter()-started)
        passed=_gate(summary); summary["terminal_result_gate_passed"]=passed
        report=dict(experiment_id=EXPERIMENT_ID,stage=STAGE,status="PASS" if passed else "FAIL",
            diagnostic_execution_valid=True,production_runtime_modified=False,gate_e_candidate=False,
            commit_sha=subprocess.check_output(["git","rev-parse","HEAD"],text=True).strip(),C158_summary_sha256=SOURCE_SHA,
            input_sha256={str(p):h for p,h in protected.items()},summary=summary,records=records,
            limitations=["Recorded-terminal output projection; no live cycle, Controller or retrieval rerun",
                "Deterministic copy of a previously observed Boolean payload, not a learned answer head or language generation",
                "Request/snapshot binding cannot establish semantic relevance or cryptographic authenticity",
                "Injected output faults are not observed model failures; rejected outputs do not count as correct learned STOP",
                "Trusted immutable source traces; no concurrent freshness, production API, durable result publication or recovery",
                "No query-ranker integration or independent task generalization; Gate E remains NOT PASSED"])
        tmp=output_dir/"summary.partial.json";tmp.write_bytes(_bytes(report));tmp.replace(output_dir/"summary.json")
        return report
    except Exception as exc:
        (output_dir/"invalid.json").write_bytes(_bytes(dict(experiment_id=EXPERIMENT_ID,status="INVALID",
            diagnostic_execution_valid=False,error=str(exc),completed_routers=len(records))))
        raise


def main() -> int:
    p=argparse.ArgumentParser(description="C159 evidence-bound typed terminal output")
    p.add_argument("--c158-summary",type=Path,required=True);p.add_argument("--output-dir",type=Path,required=True)
    a=p.parse_args()
    print("C159 source_episodes=1920; controls=4608; emitter_calls=6528; model=False; training=0",flush=True)
    print("C159 structured_result=True; learned_answer=False; live_cycle_replay=False",flush=True)
    report=run(**vars(a)); print("=== C159 RESULT ===",flush=True)
    print(json.dumps(report,indent=2,allow_nan=False),flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
