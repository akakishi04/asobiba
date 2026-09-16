# C161 verdict -> C162 evidence-container differential

Reviewed/preregistered 2026-09-16 JST. V5-E diagnostic work only.

## C161 — ACCEPTED PASS

Experiment `C161-v5e-c160-failure-boundary-localization`.
Stage `V5-E-C160-FAILURE-BOUNDARY-LOCALIZATION`.
Execution branch `feat/sft-target-loss`; commit `97e26b5dfa71ac7998138050942bbfd107f3c46e`.
Preregistration: `experiment-ledger-addendum-c160-c161.md` at that commit, unchanged.

Evidence: uploaded console log `貼り付けられたテキスト（1 点）(20260916-010814).txt` (115122 bytes).
Reviewer-computed uploaded-log SHA256:
`097ed3aeefc2fc5fa92fcd431efd20a4f168b0ca768b455a6fc7b9f62c871574`.

Local report:
`runs/c161-v5e-c160-failure-localization-794f97af76da46c3b7b919f0f278f214/summary.json`.
Runner-printed report SHA256:
`2cb356e36dde0e9d8ef87146b3e3d31eacc1afbb2743bee17815f1eb11958f38`.
The reviewer also parsed the complete console JSON and reproduced this report hash using C161's sorted/indented JSON encoding. This does not constitute independent access to the local report file or 48 source traces. The log hash is a different identity.

### Execution validity

558/558 focused regression PASS (7.308 seconds). The registered 48 trace files and all 82944 stored episodes were read. C160 summary hash is `1c99ab5395e67c859a7730e1a9111d4595e2668b85cb56d0a31dfff79aea4bbd`; the report lists all 48 checked trace hashes. `diagnostic_execution_valid=true`, `run_execution_valid=True`; protected C160 summary, tracked tree and execution HEAD checks pass. No production runtime changes. Benchmark training, fresh seeds, model/retrieval/live-cycle execution are all zero. Regression tests are separate from that benchmark execution scope.

The older C145 scalar-conversion warning occurred inside a passing regression test; it is not C161 invalidity.

### Metrics

| Measurement | Observed |
|---|---:|
| Source trace files / stored episodes | 48 / 82944 |
| Stored cycle assessment PASS / FAIL | 82944 / 0 |
| False cycle-check names/counts | none |
| Terminal REJECTED | 82944 |
| MALFORMED_EVIDENCE | 82944 |
| POST_CYCLE_TERMINAL_REJECTION | 82944 |
| Output bound / unbound | 0 / 82944 |
| Serialization valid / invalid | 82944 / 0 |
| Episodes per Controller | 27648 each |
| Episodes per arm/layout | 20736 each |

The registered single-boundary hypothesis passes exactly. Representative row: seed 20261721, WITHIN_FACTOR, CANONICAL, case `00-00`, router 20261741; actions `[2,0]`, statuses `[REFERENCE_UNBOUND,RESOLVED]`, terminal `ANSWER_ACTION`, no false cycle checks, emitter rejection `MALFORMED_EVIDENCE`.

### Scientific interpretation

All preserved C160 cycle assessments passed; all terminal outputs were rejected at one common reason. This localizes the recorded composition failure after the accepted cycle assessment and inside the C159 terminal boundary. It is not a newly executed live cycle and is not independent revalidation of every assertion made by C158's evaluator. C161's diagnostic wall-clock 2.1868693 seconds is file analysis time, not model inference performance.

**C160 remains ACCEPTED VALID NEGATIVE.** Its typed ANSWERED count remains zero. C161 does not retroactively repair it or establish the intended terminal semantic accuracy. The existing nine WITHIN_FACTOR ranker errors per layout (18 repeated instances over two layouts) are unchanged, not 82944 new ranking failures. Gate E remains NOT PASSED.

### Confound audit and source inspection

The recorded split between cycle and emitter is now resolved: no recorded cycle failure, multiple-reason mixture, arm/layout-specific terminal reason or router coverage imbalance was found. The remaining question is the precise invariant behind MALFORMED_EVIDENCE, not model capacity or training.

Pinned source inspection identifies a specific representation mismatch:

- `fold_lm/v05/state.py`: `EvidenceState.observations` must be a tuple.
- C158 `cycle`: returns `final_evidence=asdict(state)`.
- C160 `execute_selected`: passes that native result directly to C159 `emit_terminal`.
- C159 `emit_terminal`: rejects unless `final_evidence` is a dict and `observations` is a list.
- C159's accepted experiment read JSON terminal traces; C160's new path passes native objects. The recorded JSON form cannot itself preserve the original tuple/list distinction.

A reviewer helper reproduction using the inspected core state and emitter definitions confirms native tuple -> MALFORMED_EVIDENCE, list-only copy -> ANSWERED, for both 0 and 1. This is source-level/helper evidence, not an independent replay of the real 82944 results. A one-field differential is preregistered below to test whether this mismatch accounts for every recorded failure, including later guards and the known semantic boundary.

C161 validates trace hashes before reading and aggregates stored flags; its runner does not independently rehash every trace at the final postcheck. No concurrent mutation was observed or claimed. C162 will rehash every consumed source at the end as well. This limitation does not change C161's registered verdict.

## C162 — ACTIVE / NOT YET JUDGED

Experiment `C162-v5e-evidence-container-differential`.
Stage `V5-E-EVIDENCE-CONTAINER-DIFFERENTIAL`.

### One scientific question

Does changing only `final_evidence.observations` from a native tuple to a list explain all 82944 C160 terminal rejections under the **unchanged C159 emitter**, without changing evidence content, bindings, observed values or rejection guards?

```text
pinned C154 state + preserved C160 selected key
-> remove selected ref, append restored ref using actual EvidenceState
-> verify exact C160 final-state digest and reference count
-> reconstruct terminal result from preserved C160 cycle trace
    A: native tuple -> unchanged C159 emitter
    B: list-only copy -> same unchanged C159 emitter
-> compare native replay / bound observed value / post-emission semantics
```

This is offline reconstruction, NOT a live C160 rerun and NOT a production fix. There is no threshold relaxation, model/seed selection, training, new ranker forward, retrieval dispatch or new observation epoch. C158, C159, C160 and core state source files remain unchanged and their Git blob identities are checked.

### Held constant and source reconstruction

Pin C161 and C160 report hashes above, all 48 C160 trace hashes/sizes, the C154 report and its 48 state files, the C151 report/manifest and both original C152 corpus files. Consume only hash-bound ancestors, never regenerate missing artifacts or follow an arbitrary replacement catalog.

Reproduce C160's exact source-state iteration rule: original C154 report order, all same-layout reference maps must agree, last state per layout retained. For each selected key, remove that reference and append its restoration. Construct an actual EvidenceState and apply `asdict`. The resulting serialized state hash AND reference count must match the preserved C160 compact trace. Preserve reference ordering; no sorting, deduplication, target substitution or invented references.

The native object is reconstructed from pinned code and sources, not a captured original Python heap object. Other recorded cycle fields remain unchanged. Variant B changes only the observations container; both variants must have identical canonical JSON bytes. The emitter's request/provenance/clock/presence/value checks are not edited or bypassed. Target labels and original corpus values are consulted only after emission for evaluation.

Every selected key must still agree with the accepted C151 prediction; native rejection must exactly match the saved C160 output. Source states, stored flags, byte/schema/hash lineage and reconstruction failures are prerequisite validity checks, not a reason to manufacture passing outputs.

### Registered coverage, controls and measurements

- 48 source streams x 1728 queries = **82944 differential pairs**.
- **165888 pair emitter calls**, no model/retrieval/live-cycle calls.
- All 24 rankers' stored selections and the original modulo-three router assignments remain represented. No ranker is newly executed.
- All 48 source states are validated; 64 records x 2 layouts = 128 distinct snapshot/record control bindings.
- Six guard controls per binding = **768 additional emitter calls**. Select the first occurrence in the original trace order, independent of payload/correctness.
- Guard controls: wrong request, wrong provenance, wrong payload, ungrounded ANSWER, wrong clock, duplicate reference. Each must retain its existing C159 rejection reason and expose no usable value/source payload.
- Pair-only and control emitter counts stay separate (total **166656**). They are offline diagnostic counts, not new live episodes/acquisitions.

Save a plan before differential measurements, all pairs (including failures) in 48 new gzip JSONL files, guard controls in a separate JSON artifact, hashes/sizes and aggregate measurements. Never rewrite C160/C161 artifacts. Rehash all consumed inputs before final publication; the PowerShell runner independently repeats those postchecks.

For each arm/layout, require all 20736 list-form outputs to preserve selected binding and observed payload. Post-emission semantic correctness remains **WITHIN_FACTOR 20727/20736; GLOBAL_CONCEPT 20736/20736** per layout. No incidental same-bit match from the wrong record is semantic success. The 18 known control-error instances remain present and are not fixed.

### PASS / VALID NEGATIVE / INVALID

**PASS:** exact full coverage, 82944 digest-verified reconstructions, all native outputs reproduce saved MALFORMED_EVIDENCE, all list-only outputs are bound/serialization-stable/content-preserving observed bits, no input mutations or failed pairs, all 768 guards reject correctly, all source protections and semantic counts pass. Supports a container-representation explanation on reconstructed records only. Does not repair the live integration or pass Gate E.

**VALID NEGATIVE / FAIL:** valid complete sources/reconstruction but a finite output discrepancy, later rejection, wrong bound value, representation/content mutation, remaining semantic error beyond the fixed boundary, or weakened guard. Save exact outputs; CLI returns zero for a valid scientific FAIL. Do not adjust thresholds, checkpoints or coverage to obtain PASS.

**INVALID:** source hash/schema/identity/coverage mismatch, absent ancestors, changed historical code, state reconstruction digest/count mismatch, corrupted/nonfinite source, unexpected execution exception or outer postcheck failure. Restore input/execution validity and retry C162, never regenerate C160 artifacts.

### Reviewer checks and user execution

Files: `fold_lm/v05_benchmarks/gate_e_c162_evidence_container.py`, `tests_lm/test_v05_c162_evidence_container.py`, `tools/run_c162.ps1`.

**30/30 new helper tests passed** in the reviewer environment (Python 3.13.5; PyTorch 2.10.0+cpu available). They cover native tuple/list behavior with the inspected actual core/emitter definitions, exact reconstruction order/digest, zero/one, strict bit and binding checks, unchanged guard controls, input preservation, source hash/path checks, gate counts and a 48-stream x 3-row synthetic loader/writer exercise that correctly remains a scientific FAIL for insufficient formal coverage.

The reviewer lacked a full local repository checkout and real user artifacts. Tests used local excerpts of the inspected state/emitter definitions, not the full historical module implementations; no complete dependency-suite equivalence is claimed. **588 = 558 prior + 30 new** is the expected user regression count. The full 588-test run, real 82944-pair differential and Windows PowerShell script are NOT reviewer-executed. Python compilation passed. Formal C162 has no result yet.

After C162, judge first, then update ledger/handoff. No C163 is registered. C160 remains ACCEPTED VALID NEGATIVE; C161 ACCEPTED PASS; Gate E NOT PASSED. Multi-Axis and PC-ALM/FHLC remain separate tracks.
