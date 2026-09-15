"""C144: post-hoc factor-mismatch attribution over the accepted C143 audit.

No model loading, scoring, training, or runtime retrieval is performed. This
analyzer consumes only the frozen C143 summary + evaluation manifest and
classifies every ranking error by which canonical factors differ between the
expected and selected descriptors.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import subprocess

EXPERIMENT_ID = "C144-v5e-factor-mismatch-attribution"
STAGE = "V5-E-FACTOR-MISMATCH-ATTRIBUTION"
C143_ID = "C143-v5e-frozen-factorial-ranking-audit"
C143_COMMIT = "52f5a3159c68c7138e2ff568b4276e9cd58e18fe"
C142_SHA = "97878cbea08bbb02a935c37f768fdace6e2e39eb46082c6ae27f2a69f86446aa"
MANIFEST_SHA = "5a19de10d8152ac262846682a79a13bb942eeacd7dca979afb09b70170ebdd65"
ARMS = ("BASELINE", "COLOR_AUX")
AXES = ("COLOR", "SHAPE", "MATERIAL")
EXPECTED_AGGREGATES = {
    "BASELINE": dict(all=(20736,17178), train=(2592,2592), prior=(1296,603), new=(16848,13983), original=(144,115)),
    "COLOR_AUX": dict(all=(20736,19211), train=(2592,2592), prior=(1296,945), new=(16848,15674), original=(144,128)),
}
EXPECTED_PAIRED = dict(rescued_errors=2141, new_errors=108)


def _sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _mask(expected: str, predicted: str) -> str:
    e, p = expected.split(), predicted.split()
    if len(e) != 3 or len(p) != 3:
        raise ValueError("Descriptors must have exactly three canonical factors")
    changed = [name for name, a, b in zip(AXES, e, p, strict=True) if a != b]
    if not changed:
        raise ValueError("Error attribution received an identical descriptor")
    return "+".join(changed)


def _safe_rate(errors: int, cases: int) -> float:
    return errors / cases if cases else 0.0


def _validate_and_flatten(data: dict, manifest: dict) -> dict[str, list[dict]]:
    s = data.get("summary", {})
    if (data.get("experiment_id") != C143_ID or data.get("status") != "FAIL"
            or data.get("diagnostic_execution_valid") is not True
            or data.get("commit_sha") != C143_COMMIT
            or data.get("C142_summary_sha256") != C142_SHA
            or data.get("evaluation_manifest_sha256") != MANIFEST_SHA
            or data.get("production_runtime_modified") is not False
            or data.get("gate_e_candidate") is not False):
        raise ValueError("C144 requires the accepted valid-negative C143 result")
    required = dict(fresh_seed_count=0, additional_training_steps=0, reused_checkpoint_count=24,
                    old_candidate_count=12, candidate_count=64, training_combinations=8,
                    previously_evaluated_heldout_combinations=4, new_combinations=52,
                    aliases_per_factor_value=3, queries_per_combination=27, queries_per_model=1728,
                    total_ranking_cases=41472, original12_replay_cases=288,
                    original12_replay_match_rate=1.0, frozen_weights_preserved_rate=1.0,
                    evaluation_oov_count=0, zero_paired_lexical_overlap_rate=1.0,
                    inference_oracle_used=False, runtime_path_exercised=False,
                    frozen_factorial_ranking_gate_passed=False)
    if any(s.get(k) != v for k, v in required.items()):
        raise ValueError("C143 control/count profile mismatch")
    if s.get("paired") != EXPECTED_PAIRED:
        raise ValueError("C143 paired aggregate mismatch")
    descriptors = manifest.get("descriptors")
    queries = manifest.get("queries")
    if (manifest.get("candidate_count") != 64 or manifest.get("query_count") != 1728
            or not isinstance(descriptors, list) or len(descriptors) != 64
            or not isinstance(queries, list) or len(queries) != 1728):
        raise ValueError("C143 evaluation manifest shape mismatch")
    if len(set(descriptors)) != 64 or len({q.get("case_id") for q in queries}) != 1728:
        raise ValueError("Manifest identities are not unique")
    records = data.get("records")
    if not isinstance(records, list) or len(records) != 12:
        raise ValueError("Full C143 records required")
    flat = {arm: [] for arm in ARMS}
    for record in records:
        seed = record.get("seed")
        for arm in ARMS:
            results = record.get("arms", {}).get(arm, {}).get("results")
            if not isinstance(results, list) or len(results) != 1728:
                raise ValueError("C143 per-model result coverage mismatch")
            for q, r in zip(queries, results, strict=True):
                expected = q.get("expected_address")
                predicted = r.get("predicted_address")
                if type(expected) is not int or type(predicted) is not int or not (0 <= expected < 64 and 0 <= predicted < 64):
                    raise ValueError("Address outside C143 catalog")
                correct = predicted == expected
                if r.get("correct") is not correct or not all(math.isfinite(float(r[k])) for k in ("expected_score","best_other_score","expected_margin")):
                    raise ValueError("C143 result correctness/numeric mismatch")
                flat[arm].append(dict(seed=seed, case_id=q["case_id"], text=q["text"], bucket=q["bucket"],
                                      original_validation_query=bool(q["original_validation_query"]),
                                      expected_address=expected, predicted_address=predicted,
                                      expected_descriptor=descriptors[expected], predicted_descriptor=descriptors[predicted],
                                      correct=correct, expected_margin=float(r["expected_margin"])))
    for arm in ARMS:
        rows = flat[arm]
        groups = {
            "all": rows,
            "train": [r for r in rows if r["bucket"] == "TRAIN_COMBINATION"],
            "prior": [r for r in rows if r["bucket"] == "PRIOR_HELDOUT_COMBINATION"],
            "new": [r for r in rows if r["bucket"] == "NEW_COMBINATION"],
            "original": [r for r in rows if r["original_validation_query"]],
        }
        for name, group in groups.items():
            expected_cases, expected_correct = EXPECTED_AGGREGATES[arm][name]
            if (len(group), sum(r["correct"] for r in group)) != (expected_cases, expected_correct):
                raise ValueError(f"C143 aggregate recomputation mismatch: {arm}/{name}")
    return flat


def _arm_analysis(rows: list[dict]) -> dict:
    errors = [r for r in rows if not r["correct"]]
    masks = Counter(_mask(r["expected_descriptor"], r["predicted_descriptor"]) for r in errors)
    distance = Counter(mask.count("+") + 1 for mask in masks for _ in range(0))  # explicit below
    distance = Counter(len(_mask(r["expected_descriptor"], r["predicted_descriptor"]).split("+")) for r in errors)
    by_bucket = {}
    for bucket in ("TRAIN_COMBINATION", "PRIOR_HELDOUT_COMBINATION", "NEW_COMBINATION"):
        group = [r for r in rows if r["bucket"] == bucket]
        bad = [r for r in group if not r["correct"]]
        by_bucket[bucket] = dict(cases=len(group), errors=len(bad), error_rate=_safe_rate(len(bad), len(group)),
                                 masks=dict(sorted(Counter(_mask(r["expected_descriptor"], r["predicted_descriptor"]) for r in bad).items())))
    axis_values = {axis: defaultdict(lambda: [0,0]) for axis in AXES}
    alias_tokens = {axis: defaultdict(lambda: [0,0]) for axis in AXES}
    for r in rows:
        expected = r["expected_descriptor"].split()
        aliases = r["text"].split()
        if len(aliases) != 3:
            raise ValueError("Generated query must contain exactly three alias fields")
        for i, axis in enumerate(AXES):
            axis_values[axis][expected[i]][0] += 1
            alias_tokens[axis][aliases[i]][0] += 1
            if not r["correct"]:
                axis_values[axis][expected[i]][1] += 1
                alias_tokens[axis][aliases[i]][1] += 1
    def rates(table):
        return {k: dict(cases=v[0], errors=v[1], error_rate=_safe_rate(v[1], v[0])) for k, v in sorted(table.items())}
    return dict(cases=len(rows), errors=len(errors), accuracy=1-_safe_rate(len(errors), len(rows)),
                mismatch_masks=dict(sorted(masks.items())), mismatch_distance=dict(sorted(distance.items())),
                buckets=by_bucket, expected_value_error_rates={a: rates(axis_values[a]) for a in AXES},
                alias_error_rates={a: rates(alias_tokens[a]) for a in AXES})


def analyze(c143_summary_path: Path, manifest_path: Path, output_path: Path) -> dict:
    if _sha(manifest_path) != MANIFEST_SHA:
        raise ValueError("C143 manifest hash mismatch")
    data = json.loads(c143_summary_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    flat = _validate_and_flatten(data, manifest)
    paired = Counter()
    rescue_masks = Counter()
    regression_masks = Counter()
    for b, a in zip(flat["BASELINE"], flat["COLOR_AUX"], strict=True):
        if (b["seed"], b["case_id"]) != (a["seed"], a["case_id"]):
            raise ValueError("Paired C143 result order mismatch")
        state = ("BOTH_CORRECT" if b["correct"] and a["correct"] else
                 "RESCUED" if not b["correct"] and a["correct"] else
                 "REGRESSION" if b["correct"] and not a["correct"] else "BOTH_WRONG")
        paired[state] += 1
        if state == "RESCUED":
            rescue_masks[_mask(b["expected_descriptor"], b["predicted_descriptor"])] += 1
        elif state == "REGRESSION":
            regression_masks[_mask(a["expected_descriptor"], a["predicted_descriptor"])] += 1
    expected_transition = dict(BOTH_CORRECT=17070, RESCUED=2141, REGRESSION=108, BOTH_WRONG=1417)
    if dict(paired) != expected_transition:
        raise ValueError("Paired transition recomputation mismatch")
    report = dict(experiment_id=EXPERIMENT_ID, stage=STAGE, status="PASS", diagnostic_execution_valid=True,
                  production_runtime_modified=False, gate_e_candidate=False,
                  commit_sha=subprocess.check_output(["git","rev-parse","HEAD"], text=True).strip(),
                  C143_summary_sha256=_sha(c143_summary_path), evaluation_manifest_sha256=_sha(manifest_path),
                  summary=dict(analysis_only=True, model_loading=False, additional_scoring=False, additional_training_steps=0,
                               baseline=_arm_analysis(flat["BASELINE"]), color_aux=_arm_analysis(flat["COLOR_AUX"]),
                               paired_transitions=dict(paired), rescued_error_masks=dict(sorted(rescue_masks.items())),
                               regression_error_masks=dict(sorted(regression_masks.items())),
                               attribution_complete=True),
                  limitations=["Descriptive post-hoc attribution over the preregistered C143 suite; not a new causal intervention",
                               "Factor labels come from the synthetic evaluation manifest",
                               "Error concentration does not prove a factor-specific auxiliary objective will fix it",
                               "No model/ranking/runtime path is executed; C143's scoped negative remains unchanged",
                               "Gate E remains NOT PASSED"])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    return report
