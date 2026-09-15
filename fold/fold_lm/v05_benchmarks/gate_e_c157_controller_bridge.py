"""C157: accepted C156 working inputs -> actual learned Control Lane decisions.

This is a recorded-input bridge, not a live acquisition/answer loop. Train three
reference routers with the unchanged C113 recipe, freeze all three, then score
all source rows. Expected actions never enter the network or checkpoint choice.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path, PureWindowsPath
import subprocess
import time

import numpy as np
import torch

from fold_lm.v05.controller import (
    ControlLaneActionRouter, ControlLaneRouterConfig, canonicalize_boolean_channels,
)

EXPERIMENT_ID = "C157-v5e-learned-controller-readback-bridge"
STAGE = "V5-E-LEARNED-CONTROLLER-READBACK-BRIDGE"
SOURCE_ID = "C156-v5e-request-bound-reobservation"
SOURCE_COMMIT = "fe2b277341b62abf04bb51d284ce7fd288f15581"
SOURCE_SHA = "b2c43401a6731400de8e18697f82f5e220aeb3f2368737d9dee5847f7ca1f84f"
C37_SHA = "fd4a8da897bdaea9d103a252e30212c7ff842d23300d7c837333e146dee51931"
FIXTURE_SHA = "a52f8209703149407580f7e2965b61b78653030ee992af6d759865736741ca9e"
SOURCE_SEEDS = tuple(range(20261721, 20261733))
ROUTER_SEEDS = (20261741, 20261742, 20261743)
ARMS = ("WITHIN_FACTOR", "GLOBAL_CONCEPT")
ORDERS = ("CANONICAL", "PERMUTED")
SCENARIOS = ("MATCHED", "MISSING_REFERENCE", "MISSING_SOURCE", "WRONG_SNAPSHOT")
STATUSES = ("RESOLVED", "REFERENCE_UNBOUND", "SOURCE_UNBOUND", "SNAPSHOT_MISMATCH")
MODES = ("RETRIEVE_AVAILABLE", "NO_ACQUISITION")
MASKS = ((0, 1, 0, 0), (0, 0, 0, 0))
CONFIG = dict(width=8, control_width=4, operation_vocab_size=1, hidden_width=8, action_count=6)
CHUNK = 4096
SOURCE_VIEWS = 331776


class InvalidInput(ValueError):
    """Invalid source/setup, not an incorrect finite learned decision."""


def _require(ok: bool, message: str) -> None:
    if not ok:
        raise InvalidInput(message)


def _sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _bytes(data) -> bytes:
    return (json.dumps(data, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def _safe_file(root: Path, name: str) -> Path:
    _require(isinstance(name, str) and name not in ("", ".", "..")
             and Path(name).name == name and PureWindowsPath(name).name == name,
             "Unsafe source filename")
    path = root / name
    _require(path.resolve().parent == root.resolve(), "Source escaped its run directory")
    return path


def _header(data: dict) -> None:
    _require(data.get("experiment_id") == SOURCE_ID and data.get("commit_sha") == SOURCE_COMMIT
             and data.get("status") == "PASS" and data.get("diagnostic_execution_valid") is True
             and data.get("production_runtime_modified") is False and data.get("gate_e_candidate") is False,
             "Expected accepted C156 PASS")
    s = data.get("summary", {})
    expected = dict(source_streams=48, source_requests=82944, reobservation_calls=SOURCE_VIEWS,
                    status_counts={k:82944 for k in STATUSES}, resolved_values={"0":34992,"1":47952},
                    failed_cases=0, control_tensor_failures=0, state_mutations=0, old_working_mutations=0,
                    retrieval_calls=82944, vectors_scored=5308416, internal_steps_consumed=SOURCE_VIEWS,
                    acquisition_budget_consumed=0, fresh_seed_count=0, training_steps=0, model_loading=False,
                    actual_working_state_exercised=True, advance_internal_exercised=True,
                    control_input_canonicalizer_exercised=True, controller_exercised=False,
                    answer_exercised=False, production_state_commit=False, new_observation_committed=False,
                    crash_recovery_exercised=False, request_reobservation_gate_passed=True)
    _require(all(s.get(k) == v for k,v in expected.items()), "C156 profile mismatch")
    records = data.get("records")
    _require(isinstance(records, list) and len(records) == 48, "Full C156 records required")
    keys = [(r["seed"], r["arm"], r["order"]) for r in records]
    _require(len(set(keys)) == 48 and set(keys) == {(s,a,o) for s in SOURCE_SEEDS for a in ARMS for o in ORDERS},
             "C156 stream identity coverage mismatch")
    for r in records:
        _require(r["split_id"] == f"S{(r['seed']-20261721)//3+1}"
                 and r["source_requests"] == 1728 and r["observations"] == 6912
                 and r["state_preserved"] is True, "C156 stream profile mismatch")


def _decode_rows(rows: list[dict], stream: dict):
    """Validate pinned recorded inputs; never recreate a missing trace or payload."""
    _require(len(rows) == 1728, "Expected 1728 source requests")
    scope = f"C153|{stream['seed']}|{stream['arm']}|{stream['order']}"
    seen, raw, values, scenario_indices = set(), [], [], []
    counts, bits = Counter(), Counter()
    for row in rows:
        rid = row["request_id"]
        _require(isinstance(rid, str) and rid.startswith(scope + "|")
                 and row["scope_id"] == scope and rid not in seen, "Request identity/scope mismatch")
        seen.add(rid)
        ref = row["reference"]
        p = ref["provenance"]
        _require(isinstance(ref["evidence_id"], str) and bool(ref["evidence_id"])
                 and isinstance(p["source_id"], str) and p["source_id"].startswith("persisted-snapshot:")
                 and p["kind"] == "observed" and p["revision"] == p["evidence_time"] == 1,
                 "Reference identity/clock mismatch")
        outcomes = row["outcomes"]
        _require([o["scenario"] for o in outcomes] == list(SCENARIOS), "Scenario order mismatch")
        for j, o in enumerate(outcomes):
            v = o["value"]
            _require((type(v) is int and v in (0,1)) if j == 0 else v is None, "Invalid stored value")
            expected_raw = [1.,1.,1. if j == 0 else 0.,float(v) if j == 0 else 0.,.125,-.25,.375,-.5]
            _require(o["status"] == STATUSES[j] and o["passed"] is True and o["control_input_passed"] is True
                     and o["internal_step"] == 8 and o["internal_remaining"] == 2
                     and o["acquisition_remaining"] == 2 and o["retrieval_calls"] == int(j == 0)
                     and o["vectors_scored"] == 64*int(j == 0)
                     and o["working_slots"] == expected_raw, "Stored reobservation inconsistency")
            signed = [1.,1.,1. if j == 0 else -1.,(1. if v else -1.) if j == 0 else -1.]
            _require(o["control_channels"] == signed, "Recorded signed channels mismatch")
            raw.append(o["working_slots"])
            values.append(v)
            scenario_indices.append(j)
            counts[o["status"]] += 1
            if v is not None:
                bits[str(v)] += 1
    working = canonicalize_boolean_channels(torch.tensor(raw, dtype=torch.float32).unsqueeze(1), (1,2,3), threshold=.5)
    recorded = torch.tensor([o["control_channels"] for r in rows for o in r["outcomes"]], dtype=torch.float32)
    _require(torch.equal(working[:,0,:4], recorded), "Canonicalizer/record disagreement")
    return working, values, np.asarray(scenario_indices, dtype=np.int8), counts, bits


def _load_stream(root: Path, record: dict):
    path = _safe_file(root, record["result_file"])
    _require(_sha(path) == record["result_sha256"] and path.stat().st_size == record["serialized_bytes"],
             "C156 trace hash/size mismatch")
    with path.open(encoding="utf-8") as f:
        rows = [json.loads(line) for line in f]
    return _decode_rows(rows, record)


def router_inputs(working: torch.Tensor, mode: str):
    """Only observed working tensor + explicit availability, no status/label/value table."""
    if mode not in MODES:
        raise ValueError("Unregistered availability mode")
    if (not isinstance(working, torch.Tensor) or working.dtype != torch.float32
            or working.ndim != 3 or tuple(working.shape[1:]) != (1,8) or working.shape[0] < 1
            or working.device.type != "cpu" or not torch.isfinite(working).all()):
        raise ValueError("Finite CPU float32 [batch,1,8] working inputs required")
    context = torch.zeros_like(working)
    context[:,:, :4] = torch.tensor(MASKS[MODES.index(mode)], dtype=torch.float32)
    context = canonicalize_boolean_channels(context, (0,1,2,3), threshold=.5)
    return working.clone(), context, torch.zeros(working.shape[0], dtype=torch.int64)


def score_router(router, inputs, chunk: int = CHUNK) -> tuple[np.ndarray, int]:
    """Raw learned logits only. No action mask, override, or expected-label argument."""
    if type(chunk) is not int or chunk < 1:
        raise ValueError("Positive batch chunk required")
    w,c,op = inputs
    outputs = []
    with torch.inference_mode():
        for start in range(0, len(w), chunk):
            logits = router(w[start:start+chunk], c[start:start+chunk], op[start:start+chunk])
            if logits.shape != (len(w[start:start+chunk]), 6) or not torch.isfinite(logits).all():
                raise RuntimeError("Malformed/nonfinite controller output")
            outputs.append(logits.detach().cpu())
    return torch.cat(outputs).numpy().copy(), len(outputs)


def _assess(logits: np.ndarray, values: list, mode: str) -> dict:
    """Post-forward evaluator. Zero is present; None is not a negative fact."""
    if mode not in MODES or any(v is not None and (type(v) is not int or v not in (0,1)) for v in values):
        raise ValueError("Invalid evaluator arguments")
    if logits.shape != (len(values),6) or not values or not np.isfinite(logits).all():
        raise ValueError("Invalid evaluator logits")
    expected = np.array([0 if v is not None else (2 if mode == MODES[0] else 5) for v in values], dtype=np.int64)
    actions = logits.argmax(axis=1)
    rivals = logits.copy()
    rivals[np.arange(len(values)), expected] = -np.inf
    margins = logits[np.arange(len(values)), expected] - rivals.max(axis=1)
    correct = actions == expected
    strict = correct & (margins > 0)
    return dict(actions=actions, expected=expected, margins=margins, correct=correct, strict=strict)


def _fingerprint(router) -> str:
    h = hashlib.sha256()
    for name,t in sorted(router.state_dict().items()):
        h.update(name.encode()); h.update(str(tuple(t.shape)).encode()); h.update(str(t.dtype).encode())
        h.update(t.detach().cpu().contiguous().numpy().tobytes())
    return h.hexdigest()


def _save_router(path: Path, router, seed: int) -> dict:
    torch.save(dict(state_dict={k:v.detach().cpu().clone() for k,v in router.state_dict().items()},
                    config=asdict(router.config), seed=seed, recipe="C113._train_router"), path)
    saved = torch.load(path, map_location="cpu", weights_only=True)
    clone = ControlLaneActionRouter(ControlLaneRouterConfig(**saved["config"]))
    clone.load_state_dict(saved["state_dict"], strict=True)
    _require(_fingerprint(clone) == _fingerprint(router), "Checkpoint roundtrip mismatch")
    return dict(file=path.name, sha256=_sha(path), state_sha256=_fingerprint(router), serialized_bytes=path.stat().st_size)


def _train_reference(seed: int, trainer):
    """No validation data or checkpoint-selection input. Last fixed-schedule weights."""
    model, loss = trainer(seed, torch.device("cpu"))
    _require(isinstance(model, ControlLaneActionRouter) and asdict(model.config) == CONFIG, "Wrong router configuration")
    if not math.isfinite(loss) or any(not torch.isfinite(t).all() for t in model.state_dict().values()):
        raise RuntimeError("Nonfinite router training result")
    model.eval()
    model.requires_grad_(False)
    return model, float(loss)


def _gate(s: dict) -> bool:
    return bool(s.get("source_views") == SOURCE_VIEWS and s.get("routers") == 3
                and s.get("decisions") == SOURCE_VIEWS*6 and s.get("action_errors") == 0
                and s.get("nonpositive_margins") == 0 and s.get("input_mutations") == 0
                and s.get("weight_mutations") == 0 and s.get("full_router_pass_count") == 3
                and s.get("actual_action_counts") == {"0":497664,"2":746496,"5":746496}
                and s.get("matched_zero_correct") == 209952 and s.get("matched_one_correct") == 287712
                and math.isfinite(s.get("minimum_expected_margin", float("nan")))
                and s["minimum_expected_margin"] > 0)


def run(*, c156_summary: Path, output_dir: Path) -> dict:
    from fold_lm.v05_benchmarks import gate_e_c113_stale_eligibility_preflight as c113
    output_dir.mkdir(parents=True, exist_ok=False)
    completed = []
    started = time.perf_counter()
    torch.set_num_threads(2)
    torch.set_float32_matmul_precision("highest")
    try:
        protected = {c156_summary:SOURCE_SHA, Path("runs/chatgpt-last-result.json"):C37_SHA,
                     Path("runs/fixtures/v05-c-composition-20260921.pt"):FIXTURE_SHA}
        def check_files():
            for path, expected in protected.items():
                _require(_sha(path) == expected, f"Protected input changed: {path}")
        check_files()
        prior = json.loads(c156_summary.read_text(encoding="utf-8"))
        _header(prior)
        for name, sha in prior["input_sha256"].items():
            path = Path(name)
            _require(path not in protected or protected[path] == sha, "Conflicting source hashes")
            protected[path] = sha
        check_files()
        counts, bits, unique = Counter(), Counter(), set()
        for r in prior["records"]:
            w, _, _, c, b = _load_stream(c156_summary.parent, r)
            counts.update(c); bits.update(b)
            unique.update(tuple(x) for x in w[:,0].tolist())
            protected[_safe_file(c156_summary.parent,r["result_file"])] = r["result_sha256"]
        _require(dict(counts) == prior["summary"]["status_counts"] and dict(bits) == prior["summary"]["resolved_values"]
                 and len(unique) == 3, "Full C156 trace reaggregation mismatch")
        print("[C157] all 48 C156 traces verified; unique_working_inputs=3; no retrieval replay", flush=True)
        c108 = c113.c108
        _require((c108.WIDTH,c108.CONTROL_WIDTH,c108.HIDDEN_WIDTH,c108.ACTION_COUNT,c108.TRAIN_STEPS,c108.LR)
                 == (8,4,8,6,900,.01) and tuple(c108.TRAIN_BASES) == (0,1,2), "Reference recipe drift")
        recipe_sources = {str(Path(m.__file__).resolve()):_sha(Path(m.__file__))
                          for m in (c113,c108,c113.c111,c113.c112)}
        protected.update({Path(p):h for p,h in recipe_sources.items()})
        models, training = [], []
        # Prepare every registered router before any bridge evaluation; never select a winning seed.
        for seed in ROUTER_SEEDS:
            print(f"[C157] router seed={seed} fixed C113 training start steps=900 device=cpu", flush=True)
            model, loss = _train_reference(seed, c113._train_router)
            ckpt = _save_router(output_dir / f"controller-{seed}.pt", model, seed)
            models.append(model)
            training.append(dict(seed=seed, final_loss=loss, optimizer_steps=900, checkpoint=ckpt))
            print(f"[C157] router seed={seed} train done loss={loss:.8f}; frozen=True", flush=True)
        errors = nonpositive = input_mutations = weight_mutations = forwards = zero_ok = one_ok = 0
        actions_total = Counter()
        global_min = math.inf
        for model_index, (model, t) in enumerate(zip(models, training, strict=True), 1):
            fingerprint = _fingerprint(model)
            model_errors = model_nonpositive = 0
            model_min = math.inf
            stream_results = []
            for index, record in enumerate(prior["records"], 1):
                w, values, scenarios, _, _ = _load_stream(c156_summary.parent,record)
                working_before = w.clone()
                arrays, mode_results = {}, {}
                for mode in MODES:
                    inputs = router_inputs(w,mode)
                    before = [x.clone() for x in inputs]
                    logits, batches = score_router(model,inputs)
                    forwards += batches
                    input_mutations += sum(not torch.equal(a,b) for a,b in zip(before,inputs))
                    result = _assess(logits,values,mode)
                    err = int((~result["correct"]).sum()); npmargin = int((result["margins"] <= 0).sum())
                    errors += err; nonpositive += npmargin; model_errors += err; model_nonpositive += npmargin
                    minimum = float(result["margins"].min()); model_min = min(model_min,minimum)
                    actions_total.update(str(int(x)) for x in result["actions"])
                    zero_ok += sum(bool(ok) for v,ok in zip(values,result["correct"]) if v == 0)
                    one_ok += sum(bool(ok) for v,ok in zip(values,result["correct"]) if v == 1)
                    groups = {name:dict(cases=int((scenarios==j).sum()),
                              errors=int((~result["correct"][scenarios==j]).sum()),
                              minimum_expected_margin=float(result["margins"][scenarios==j].min()))
                              for j,name in enumerate(SCENARIOS)}
                    mode_results[mode] = dict(decisions=len(values), errors=err, nonpositive_margins=npmargin,
                                             minimum_expected_margin=minimum, by_scenario=groups)
                    for name,array in dict(logits=logits, actions=result["actions"], expected=result["expected"],
                                           margins=result["margins"]).items():
                        arrays[mode + "_" + name] = array
                input_mutations += int(not torch.equal(w,working_before))
                artifact = output_dir / f"decisions-{t['seed']}-{index:02}.npz"
                np.savez_compressed(artifact, **arrays)
                stream_results.append(dict(source_seed=record["seed"], source_arm=record["arm"],
                    source_order=record["order"], split_id=record["split_id"], source_trace_file=record["result_file"],
                    source_trace_sha256=record["result_sha256"], modes=mode_results,
                    file=artifact.name, sha256=_sha(artifact), serialized_bytes=artifact.stat().st_size))
                if index == 1 or index % 8 == 0:
                    print(f"[C157] router {model_index}/3 stream {index}/48 decisions={index*13824} "
                          f"errors={model_errors} remaining_streams={48-index}", flush=True)
            unchanged = _fingerprint(model) == fingerprint
            weight_mutations += int(not unchanged)
            global_min = min(global_min,model_min)
            completed.append(dict(**t, errors=model_errors, nonpositive_margins=model_nonpositive,
                                  minimum_expected_margin=model_min, weights_preserved=unchanged, streams=stream_results))
        check_files()
        summary = dict(source_requests=82944, source_views=SOURCE_VIEWS, unique_working_inputs=3,
                       unique_working_context_inputs=6, routers=3, fresh_router_seeds=list(ROUTER_SEEDS),
                       router_train_steps_each=900, router_training_recipe="C113._train_router unchanged; CPU",
                       decisions=SOURCE_VIEWS*6, forward_batches=forwards, action_errors=errors,
                       nonpositive_margins=nonpositive, minimum_expected_margin=global_min,
                       input_mutations=input_mutations, weight_mutations=weight_mutations,
                       matched_zero_correct=zero_ok, matched_one_correct=one_ok,
                       actual_action_counts=dict(actions_total),
                       full_router_pass_count=sum(r["errors"] == r["nonpositive_margins"] == 0 for r in completed),
                       source_semantic_counts=prior["summary"]["source_semantic_counts"],
                       learned_controller_exercised=True, action_selection_exercised=True,
                       answer_action_selection_exercised=True, answer_generation_exercised=False,
                       live_reobservation_exercised=False, retrieval_exercised=False,
                       action_execution_exercised=False, production_state_commit=False,
                       wall_clock_seconds=time.perf_counter()-started)
        passed = _gate(summary)
        summary["controller_bridge_gate_passed"] = passed
        report = dict(experiment_id=EXPERIMENT_ID,stage=STAGE,status="PASS" if passed else "FAIL",
                      diagnostic_execution_valid=True,production_runtime_modified=False,gate_e_candidate=False,
                      commit_sha=subprocess.check_output(["git","rev-parse","HEAD"],text=True).strip(),
                      C156_summary_sha256=SOURCE_SHA,input_sha256={str(p):h for p,h in protected.items()},
                      config=CONFIG,eligibility_modes=dict(zip(MODES,MASKS)),summary=summary,records=completed,
                      environment=dict(torch=str(torch.__version__),device="cpu",precision="float32/highest",threads=2),
                      limitations=["Recorded-input bridge, not live retrieval/reobservation/Controller integration",
                        "Six distinct input patterns repeated across request traces, not 1990656 independent reasoning tasks",
                        "Reference controller training is new; no reuse/replay of old router checkpoints is claimed",
                        "Availability masks are explicit fixtures, not learned availability or runtime authority revalidation",
                        "ANSWER is action 0 only; no text/value answer generation or external action executes",
                        "Source relevance errors cannot be detected from a presence bit; source semantics are bookkeeping",
                        "No ranker retraining, durable commit, crash recovery or Gate E completion"])
        temp = output_dir / "summary.partial.json"; temp.write_bytes(_bytes(report)); temp.replace(output_dir/"summary.json")
        return report
    except Exception as exc:
        (output_dir/"invalid.json").write_bytes(_bytes(dict(experiment_id=EXPERIMENT_ID,status="INVALID",
            diagnostic_execution_valid=False,error=str(exc),completed_routers=len(completed))))
        raise


def main() -> int:
    p = argparse.ArgumentParser(description="C157 learned Controller on recorded C156 readback inputs")
    p.add_argument("--c156-summary",type=Path,required=True)
    p.add_argument("--output-dir",type=Path,required=True)
    args = p.parse_args()
    print("C157 fresh_router_seeds=20261741,20261742,20261743; training=900 steps/router; CPU",flush=True)
    print("C157 recorded_views=331776; availability_modes=2; decisions=1990656; distinct_inputs=6",flush=True)
    print("C157 Controller=True; ANSWER_action=True; answer_generation=False; live_retrieval=False",flush=True)
    report = run(c156_summary=args.c156_summary,output_dir=args.output_dir)
    print("=== C157 RESULT ===",flush=True)
    print(json.dumps(dict(report,records="omitted; see summary.json"),indent=2,allow_nan=False),flush=True)
    return 0  # Finite wrong decisions remain scientific FAIL, not retryable execution exceptions.


if __name__ == "__main__":
    raise SystemExit(main())
