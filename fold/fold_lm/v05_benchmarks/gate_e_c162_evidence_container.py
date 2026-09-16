"""C162: tuple/list-only differential at the unchanged C159 emitter boundary.

Offline reconstruction, not a live C160 rerun or a production repair. Preserved
trace digests bind reconstructed final EvidenceStates, including reference order.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from dataclasses import asdict, replace
import gzip
import hashlib
import json
from pathlib import Path, PureWindowsPath
import subprocess
import time

from fold_lm.v05.state import EvidenceRef, EvidenceState, Provenance, ProvenanceKind
from fold_lm.v05_benchmarks import gate_e_c159_terminal_result as terminal

EXPERIMENT_ID = "C162-v5e-evidence-container-differential"
STAGE = "V5-E-EVIDENCE-CONTAINER-DIFFERENTIAL"
C161_SHA = "2cb356e36dde0e9d8ef87146b3e3d31eacc1afbb2743bee17815f1eb11958f38"
C160_SHA = "1c99ab5395e67c859a7730e1a9111d4595e2668b85cb56d0a31dfff79aea4bbd"
C154_SHA = "4814c9489b76bfb124e7134336611a3f513eb922083b0eca251be533820c4284"
C151_SHA = "d2b48acb36d28f0422d09067cc23af882c812d020a00ccfc8c6e8286fd896afa"
MANIFEST_SHA = "5a19de10d8152ac262846682a79a13bb942eeacd7dca979afb09b70170ebdd65"
CORPUS_SHAS = {
    "CANONICAL": "6a915ad70091867f3813b01226578b53ef9041546f00e40105408256da133b93",
    "PERMUTED": "8bf566057365babddf8e49a67658272832e97469685daafbad2e8d774387877f",
}
C160_COMMIT = "d2c1468a19e9a13a8fa47fafe3aad5fa01597aec"
C161_COMMIT = "97e26b5dfa71ac7998138050942bbfd107f3c46e"
ARMS = ("WITHIN_FACTOR", "GLOBAL_CONCEPT")
ORDERS = ("CANONICAL", "PERMUTED")
HEAD_SEEDS = tuple(range(20261721, 20261733))
ROUTERS = (20261741, 20261742, 20261743)
EPISODES = 82944
ROWS = 1728
FAULT_REASONS = {
    "WRONG_REQUEST": "REQUEST_MISMATCH",
    "WRONG_PROVENANCE": "REFERENCE_MISMATCH",
    "WRONG_PAYLOAD": "PAYLOAD_MISMATCH",
    "UNGROUNDED": "ANSWER_NOT_GROUNDED",
    "WRONG_CLOCK": "CLOCK_MISMATCH",
    "DUPLICATE_REFERENCE": "REFERENCE_MISMATCH",
}
# Git blob identities are independent of checkout newline conversion.
SOURCE_BLOBS = {
    "fold/fold_lm/v05/state.py": "aa3f4938f6b5d403d8ee05c4220f686695cef3f0",
    "fold/fold_lm/v05_benchmarks/gate_e_c158_live_recovery.py": "2ca63e6dfe8f827d9c85db03b3f13c82c39143ec",
    "fold/fold_lm/v05_benchmarks/gate_e_c159_terminal_result.py": "7d4bb60c5b59b151699740274bffbc839c7954c3",
    "fold/fold_lm/v05_benchmarks/gate_e_c160_live_query_result.py": "a2ed2c1be6f55dc068fb734e1a38ac216f06f002",
}


class InvalidInput(ValueError):
    """Cannot faithfully reconstruct the pinned source; retry the same C number."""


def require(ok, message):
    if not ok:
        raise InvalidInput(message)


def blob(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def sha(path):
    with Path(path).open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def safe_child(root, name):
    require(isinstance(name, str) and name not in ("", ".", "..")
            and Path(name).name == PureWindowsPath(name).name == name, "Unsafe filename")
    result = (Path(root) / name).resolve()
    require(result.parent == Path(root).resolve(), "File escaped source directory")
    return result


def locate(inputs, digest, filename):
    found = {Path(p).resolve() for p, h in inputs.items()
             if h == digest and Path(p).name == filename}
    require(len(found) == 1, "Missing/ambiguous pinned source: " + filename)
    return found.pop()


def protect(path, digest, inputs):
    path = Path(path).resolve()
    require(path not in inputs or inputs[path] == digest, "Conflicting input hash")
    require(sha(path) == digest, "Input bytes changed: " + str(path))
    inputs[path] = digest
    return path


def check_inputs(inputs):
    for path, digest in inputs.items():
        require(sha(path) == digest, "Input changed during diagnostic: " + str(path))


def stream_index(records):
    require(isinstance(records, list) and len(records) == 48, "Expected 48 streams")
    result = {}
    for r in records:
        key = (r["seed"], r["arm"], r["order"])
        require(key not in result, "Duplicate stream")
        result[key] = r
    require(set(result) == {(s, a, o) for s in HEAD_SEEDS for a in ARMS for o in ORDERS},
            "Stream identity coverage mismatch")
    return result


def decode_state(data):
    require(isinstance(data, dict) and set(data) == {"evidence_time", "revision", "observations"}
            and isinstance(data["observations"], list), "Malformed source EvidenceState")
    refs = []
    for row in data["observations"]:
        require(set(row) == {"evidence_id", "provenance"}, "Malformed source reference")
        p = dict(row["provenance"])
        require(set(p) == {"source_id", "kind", "revision", "evidence_time"}, "Malformed provenance")
        p["kind"] = ProvenanceKind(p["kind"])
        refs.append(EvidenceRef(row["evidence_id"], Provenance(**p)))
    return EvidenceState(data["evidence_time"], data["revision"], tuple(refs))


def final_state_for(full_state, selected_key):
    """Mirror C160 removal followed by C154 append; never sort reference order."""
    refs = [r for r in full_state.observations if r.evidence_id == selected_key]
    require(len(refs) == 1, "Selected reference absent/ambiguous")
    rest = tuple(r for r in full_state.observations if r.evidence_id != selected_key)
    return replace(full_state, observations=rest + (refs[0],))


def reconstruct_cycle(compact, state):
    raw = asdict(state)
    digest = hashlib.sha256(blob(raw)).hexdigest()
    require(compact.get("final_evidence_sha256") == digest
            and compact.get("final_reference_count") == len(state.observations),
            "Final EvidenceState reconstruction digest/count mismatch")
    result = deepcopy(compact)
    result.pop("final_evidence_sha256")
    result.pop("final_reference_count")
    result["final_evidence"] = raw
    return result


def list_only(native):
    """Diagnostic intervention: change exactly one container, not emitter guards."""
    state = native["final_evidence"]
    require(type(state["observations"]) is tuple, "Native observations must be tuple")
    return {**native, "final_evidence": {**state, "observations": list(state["observations"])}}


def bound_output(output, binding, observed_value):
    return (type(observed_value) is int and observed_value in (0, 1)
            and type(output.value) is int
            and asdict(output) == asdict(terminal.TerminalResult(
                terminal.SCHEMA, binding.request_id, binding.scope_id, "ANSWERED", "OBSERVED_VALUE",
                observed_value, binding.record_key, binding.source_id, binding.evidence_time, binding.revision)))


def measure_pair(binding, native, saved_output, emit=None):
    """No query target/expected semantic label is supplied to either emitter call."""
    emit = terminal.emit_terminal if emit is None else emit
    original = blob(native)
    converted = list_only(native)
    same_content = blob(converted) == original
    observed_value = native.get("final_value")
    a = emit(binding, binding.request_id, native)
    b = emit(binding, binding.request_id, converted)
    checks = {
        "native_reproduced": asdict(a) == saved_output,
        "native_malformed_evidence": (a.status, a.reason) == ("REJECTED", "MALFORMED_EVIDENCE"),
        "list_bound": bound_output(b, binding, observed_value),
        "content_unchanged": same_content,
        "input_preserved": (blob(native) == original and blob(converted) == original
            and type(native["final_evidence"]["observations"]) is tuple
            and type(converted["final_evidence"]["observations"]) is list),
        "serialization_ok": json.loads(blob(asdict(b))) == asdict(b),
    }
    return a, b, checks


def fault_controls(binding, converted):
    """Six adversarial probes; copies only, no mutation of accepted artifacts."""
    outcomes = {}
    for name, expected_reason in FAULT_REASONS.items():
        r = deepcopy(converted)
        rid = binding.request_id
        if name == "WRONG_REQUEST":
            rid += "|wrong"
        elif name == "WRONG_PROVENANCE":
            r["final_reference"]["provenance"]["source_id"] += "|wrong"
        elif name == "WRONG_PAYLOAD":
            r["final_value"] = 1 - r["final_value"]
        elif name == "UNGROUNDED":
            r["steps"][-1]["status"] = "REFERENCE_UNBOUND"
        elif name == "WRONG_CLOCK":
            r["final_evidence"]["revision"] += 1
        elif name == "DUPLICATE_REFERENCE":
            r["final_evidence"]["observations"].append(deepcopy(r["final_reference"]))
        out = terminal.emit_terminal(binding, rid, r)
        no_payload = all(getattr(out, k) is None for k in
                         ("value", "record_key", "source_id", "evidence_time", "revision"))
        outcomes[name] = dict(output=asdict(out), passed=bool(
            out.status == "REJECTED" and out.reason == expected_reason and no_payload))
    return outcomes


def validate_prior(p161, p160):
    require(p161.get("experiment_id") == "C161-v5e-c160-failure-boundary-localization"
            and p161.get("stage") == "V5-E-C160-FAILURE-BOUNDARY-LOCALIZATION"
            and p161.get("commit_sha") == C161_COMMIT and p161.get("status") == "PASS"
            and p161.get("diagnostic_execution_valid") is True
            and p161.get("C160_summary_sha256") == C160_SHA, "Expected accepted C161")
    s = p161.get("summary", {})
    expected = dict(episodes=EPISODES, cycle_passed=EPISODES, cycle_failed=0,
        output_bound=0, output_unbound=EPISODES, serialization_ok=EPISODES, serialization_bad=0,
        output_status_counts={"REJECTED": EPISODES}, output_reason_counts={"MALFORMED_EVIDENCE": EPISODES},
        cycle_false_check_counts={}, boundary_counts={"POST_CYCLE_TERMINAL_REJECTION": EPISODES},
        single_post_cycle_rejection=True, localized_reason="MALFORMED_EVIDENCE", trace_files=48)
    require(all(s.get(k) == v for k, v in expected.items()), "C161 localization profile mismatch")
    require(p160.get("experiment_id") == "C160-v5e-live-query-to-terminal-result"
            and p160.get("commit_sha") == C160_COMMIT and p160.get("status") == "FAIL"
            and p160.get("diagnostic_execution_valid") is True, "Expected accepted C160 negative")
    for p in (p161, p160):
        require(p.get("production_runtime_modified") is False and p.get("gate_e_candidate") is False,
                "Prerequisite scope mismatch")
    require(p160["summary"]["episodes"] == p160["summary"]["failed_episodes"] == EPISODES
            and p160["summary"]["answered"] == 0, "C160 coverage/profile mismatch")
    stream_index(p160["records"])


def gate(s):
    required = dict(episodes=EPISODES, pair_passed=EPISODES, pair_failed=0,
        native_reproduced=EPISODES, native_malformed_evidence=EPISODES, list_bound=EPISODES,
        selected_payload_correct=EPISODES,
        content_unchanged=EPISODES, input_preserved=EPISODES, serialization_ok=EPISODES,
        reconstructed_state_matches=EPISODES, source_state_files=48, source_trace_files=48,
        pair_emitter_calls=2*EPISODES, guard_control_cases=768, guard_control_passed=768,
        guard_control_failed=0, guard_record_bindings=128,
        router_episodes={str(r):EPISODES//3 for r in ROUTERS})
    return (all(s.get(k) == v for k, v in required.items())
        and s.get("false_pair_checks") == {}
        and all(s.get("arms", {}).get(a, {}).get(o) == dict(cases=20736, list_bound=20736,
                    semantic_correct=20727 if a == ARMS[0] else 20736)
                for a in ARMS for o in ORDERS)
        and set(s.get("list_values", {})) == {"0", "1"}
        and all(type(s["list_values"][k]) is int and s["list_values"][k] > 0 for k in ("0", "1"))
        and sum(s["list_values"].values()) == EPISODES)


def run(*, c161_summary, c160_summary, output_dir):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    inputs, completed = {}, []
    started = time.perf_counter()
    try:
        source_blobs = {}
        for path, wanted in SOURCE_BLOBS.items():
            actual = subprocess.check_output(["git", "rev-parse", "HEAD:" + path], text=True).strip()
            require(actual == wanted, "Historical source code changed: " + path)
            source_blobs[path] = actual
        c161_summary = protect(c161_summary, C161_SHA, inputs)
        c160_summary = protect(c160_summary, C160_SHA, inputs)
        p161 = json.loads(c161_summary.read_text(encoding="utf-8"))
        p160 = json.loads(c160_summary.read_text(encoding="utf-8"))
        validate_prior(p161, p160)
        pinned = {Path(p).resolve(): h for p, h in p160["input_sha256"].items()}
        pinned161 = {Path(p).resolve(): h for p, h in p161["input_sha256"].items()}
        p154_path = protect(locate(pinned, C154_SHA, "summary.json"), C154_SHA, inputs)
        p154 = json.loads(p154_path.read_text(encoding="utf-8"))
        states, state_records = {}, stream_index(p154["records"])
        for (_, _, order), r in state_records.items():
            path = safe_child(p154_path.parent, r["state_file"])
            require(pinned.get(path) == r["state_sha256"], "C154 state not pinned by C160")
            protect(path, r["state_sha256"], inputs)
            state = decode_state(json.loads(path.read_text(encoding="utf-8")))
            require(state.evidence_time == state.revision == 1 and len(state.observations) == 64,
                    "Source state size/clock mismatch")
            if order in states:
                require({r.evidence_id:r for r in states[order].observations} ==
                        {r.evidence_id:r for r in state.observations}, "Source state maps disagree")
            # Exactly C160's last-state-per-layout rule, preserving report iteration order.
            states[order] = state
        manifest_path = protect(locate(pinned, MANIFEST_SHA, "evaluation-manifest.json"), MANIFEST_SHA, inputs)
        suite = json.loads(manifest_path.read_text(encoding="utf-8"))
        require(len(suite["queries"]) == ROWS and len(suite["descriptors"]) == 64, "Manifest shape mismatch")
        p151_path = protect(locate(pinned, C151_SHA, "summary.json"), C151_SHA, inputs)
        p151 = json.loads(p151_path.read_text(encoding="utf-8"))
        prior_ranking = {r["seed"]: r for r in p151["records"]}
        values_by_order = {}
        for order, digest in CORPUS_SHAS.items():
            corpus_path = protect(locate(pinned, digest, "records.json"), digest, inputs)
            corpus = json.loads(corpus_path.read_text(encoding="utf-8"))["records"]
            require(len(corpus) == 64 and len({r["key"] for r in corpus}) == 64
                    and all(type(r["evidence_value"]) is int and r["evidence_value"] in (0, 1) for r in corpus),
                    "Malformed evaluator-only corpus")
            values_by_order[order] = {r["key"]:r["evidence_value"] for r in corpus}
        plan = dict(experiment_id=EXPERIMENT_ID, C160_summary_sha256=C160_SHA, C161_summary_sha256=C161_SHA,
            changed_variable="final_evidence.observations tuple -> list only", episodes=EPISODES,
            pair_emitter_calls=2*EPISODES, guard_record_bindings=128, guard_control_cases=768,
            source_blobs=source_blobs, fresh_seeds=0, training_steps=0,
            native_form="source-driven reconstruction; not a captured in-memory object")
        plan_path = output_dir / "container-plan.json"
        plan_path.write_bytes(blob(plan)); protect(plan_path, sha(plan_path), inputs)
        totals, false_checks, routers, values = Counter(), Counter(), Counter(), Counter()
        arms = {a:{o:Counter() for o in ORDERS} for a in ARMS}
        controls, guarded = [], set()
        print("[C162] sources verified; tuple/list-only plan fixed; unchanged emitter", flush=True)
        for i, record in enumerate(p160["records"], 1):
            seed, arm, order = record["seed"], record["arm"], record["order"]
            path = safe_child(c160_summary.parent, record["file"])
            require(pinned161.get(path) == record["sha256"] and path.stat().st_size == record["serialized_bytes"],
                    "C160/C161 trace identity/size mismatch")
            protect(path, record["sha256"], inputs)
            trace = output_dir / ("pairs-" + record["file"].removeprefix("queries-"))
            scope = f"C160|{seed}|{arm}|{order}"
            rows = 0; seen = set()
            with gzip.open(path, "rt", encoding="utf-8") as src, gzip.open(trace, "wt", encoding="utf-8", newline="\n") as dst:
                for j, line in enumerate(src):
                    require(j < ROWS and line.strip(), "Extra/blank source row")
                    row = json.loads(line); query = suite["queries"][j]
                    require(row["case_id"] == query["case_id"] and row["text"] == query["text"]
                            and row["case_id"] not in seen and row["router_seed"] == ROUTERS[j % 3],
                            "Source query identity/router schedule drift")
                    seen.add(row["case_id"]); rows += 1
                    ca, oa, saved = row["cycle_assessment"], row["output_assessment"], row["output"]
                    require(ca["passed"] is True and ca["checks"] and all(v is True for v in ca["checks"].values())
                            and row["passed"] is False and oa["bound"] is False and oa["semantic_correct"] is False
                            and oa["serialization_ok"] is True and saved["status"] == "REJECTED"
                            and saved["reason"] == "MALFORMED_EVIDENCE", "Row contradicts pinned C161 localization")
                    final = final_state_for(states[order], row["selected_key"])
                    native = reconstruct_cycle(row["cycle"], final)
                    ref = final.observations[-1]; p = ref.provenance
                    binding = terminal.BoundRequest(scope + "|" + row["case_id"], scope, ref.evidence_id,
                                                   p.source_id, p.evidence_time, p.revision)
                    require(saved["request_id"] == binding.request_id and saved["scope_id"] == scope,
                            "Recorded request identity mismatch")
                    a, b, checks = measure_pair(binding, native, saved)
                    # Evaluation only: targets and C151 predictions never enter either emitter call.
                    target = "c152-" + hashlib.sha256(suite["descriptors"][query["expected_address"]].encode()).hexdigest()
                    prediction = prior_ranking[seed]["arms"][arm]["results"][j]["predicted_address"]
                    prior_key = "c152-" + hashlib.sha256(suite["descriptors"][prediction].encode()).hexdigest()
                    require(row["selected_key"] == prior_key, "Preserved selection disagrees with accepted C151 replay")
                    checks["selected_payload_correct"] = (checks["list_bound"]
                        and b.value == values_by_order[order][ref.evidence_id])
                    semantic = (checks["selected_payload_correct"] and b.record_key == target
                                and b.value == values_by_order[order][target])
                    passed = all(checks.values())
                    totals.update(episodes=1, pair_passed=int(passed), pair_failed=int(not passed),
                                  reconstructed_state_matches=1, pair_emitter_calls=2)
                    totals.update({k:int(v) for k,v in checks.items()})
                    false_checks.update(k for k,v in checks.items() if not v)
                    routers[str(row["router_seed"])] += 1
                    if checks["list_bound"]: values[str(b.value)] += 1
                    arms[arm][order].update(cases=1, list_bound=int(checks["list_bound"]), semantic_correct=int(semantic))
                    dst.write(json.dumps(dict(case_id=row["case_id"], selected_key=ref.evidence_id,
                        native_output=asdict(a), list_output=asdict(b), checks=checks,
                        semantic_correct=bool(semantic), passed=passed), sort_keys=True, allow_nan=False) + "\n")
                    identity = (order, ref.evidence_id)
                    if identity not in guarded:
                        guarded.add(identity)
                        probes = fault_controls(binding, list_only(native))
                        controls.append(dict(order=order, key=ref.evidence_id, probes=probes))
                        for probe in probes.values():
                            totals.update(guard_control_cases=1, guard_control_passed=int(probe["passed"]),
                                          guard_control_failed=int(not probe["passed"]))
            require(rows == ROWS and len(seen) == ROWS, "Incomplete source stream")
            completed.append(dict(seed=seed, arm=arm, order=order, file=trace.name,
                                  sha256=sha(trace), serialized_bytes=trace.stat().st_size))
            print(f"[C162] stream {i}/48 rows={rows} pair_failed={totals['pair_failed']} remaining_streams={48-i}", flush=True)
        control_path = output_dir / "guard-controls.json"
        control_path.write_bytes(blob(controls))
        check_inputs(inputs)
        summary = dict(totals, source_state_files=len(state_records), source_trace_files=len(completed),
            guard_record_bindings=len(guarded), false_pair_checks=dict(false_checks),
            router_episodes=dict(routers), list_values=dict(values),
            arms={a:{o:dict(c) for o,c in group.items()} for a,group in arms.items()})
        passed = gate(summary); summary["container_differential_gate_passed"] = passed
        report = dict(experiment_id=EXPERIMENT_ID, stage=STAGE, status="PASS" if passed else "FAIL",
            diagnostic_execution_valid=True, production_runtime_modified=False, gate_e_candidate=False,
            commit_sha=subprocess.check_output(["git","rev-parse","HEAD"],text=True).strip(),
            C160_summary_sha256=C160_SHA, C161_summary_sha256=C161_SHA,
            input_sha256={str(p):h for p,h in inputs.items()}, source_blobs=source_blobs,
            plan=dict(file=plan_path.name, sha256=sha(plan_path)), summary=summary, records=completed,
            controls=dict(file=control_path.name, sha256=sha(control_path)), training_steps=0, fresh_seed_count=0,
            model_execution=False, retrieval_execution=False, live_cycle_execution=False, emitter_execution=True,
            wall_clock_seconds=time.perf_counter()-started,
            limitations=["Reconstructed native object, not capture of original in-memory C160 result",
                "Only observations container changes; emitter and C158/C160 remain untouched",
                "C161 stored cycle checks are reaggregated, not independently live-rerun",
                "Semantic identity is scored after emission; observed bits copied, not generated",
                "PASS supports offline container causality, not repaired live integration or Gate E"])
        tmp = output_dir / "summary.partial.json"; tmp.write_bytes(blob(report)); tmp.replace(output_dir / "summary.json")
        return report
    except Exception as exc:
        (output_dir / "invalid.json").write_bytes(blob(dict(experiment_id=EXPERIMENT_ID, status="INVALID",
            diagnostic_execution_valid=False, error=str(exc), completed_streams=len(completed))))
        raise


def main():
    p = argparse.ArgumentParser(description="C162 unchanged-emitter tuple/list-only diagnostic")
    for name in ("c161-summary", "c160-summary", "output-dir"):
        p.add_argument("--" + name, type=Path, required=True)
    print("C162 offline reconstruction; episodes=82944; pair_emitter_calls=165888; guard_calls=768", flush=True)
    print("C162 training/model/retrieval/live-cycle=0; historical emitter unchanged", flush=True)
    r = run(**vars(p.parse_args()))
    print("=== C162 RESULT ===", flush=True)
    print(json.dumps(dict(r, records="omitted; see summary.json"), indent=2, allow_nan=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
