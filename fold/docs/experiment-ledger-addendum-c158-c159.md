# C158 verdict -> C159 evidence-bound terminal result

Reviewed/preregistered 2026-09-16 JST. V5-E; diagnostic only, no production change.

## C158 — ACCEPTED PASS

Execution commit: `1b407ef26d6c1f5575482e07f6c8d046a3bff438`.
Evidence: user terminal log `貼り付けられたテキスト（1 点）(20260915-230205).txt`.
Reviewer-computed uploaded-log SHA256: `ec40bd59462f5f974a412f42ead5368dee38113192fae01a054b5ca645e90449`.
Local report: `runs/c158-v5e-live-recovery-0285f65942c14db8997f7c910dd94a4f/summary.json`.
Runner-printed report SHA256: `6c49a3e681313208881743f1c2991325e4826d4970cb65d5df9cfcebd65173c8`.
Episode-plan SHA256: `0f9d0703a28efc5d9e52a11e261fe58c83411fd75994d81428c4f217b3017f8c`.
The reviewer parsed the uploaded console JSON and checked the registered aggregate arithmetic against the plan/source. The full local episode JSONL, checkpoints and NPZ arrays were not uploaded; no independent full replay or formal experiment rerun is claimed. The uploaded-log hash is not the report hash.

| Registered measurement | Observed |
|---|---:|
| Focused regression | 475/475 |
| Frozen routers / new seeds / training | 3 / 0 / 0 |
| Original C157 replay decisions | 1,990,656, all three replays matched |
| Live episodes / failed | 1,920 / 0 |
| Live Controller decisions / internal debits | 3,456 / 3,456 |
| Authorized acquisitions | 768 |
| Newly restored references | 384 |
| Actual adapter calls / vectors | 1,536 / 98,304 |
| Terminal ANSWER_ACTION / STOP_UNRESOLVED | 768 / 1,152 |
| Terminal observed zero / one | 324 / 444 |
| Weight mutations / fully passing routers | 0 / 3 |

Each of five scenarios has 384 episodes and zero failures. WARM_PRESENT uses 384 readbacks and no acquisition. COLD_RECOVER uses 384 acquisitions plus 384 readbacks and restores 384 refs. COLD_MISSING_DELIVERY makes 384 real acquisitions but adopts no reference. Permission-denied and exhausted-budget episodes make zero adapter calls and zero acquisition debits. All reported source/protected/tree/HEAD checks pass and `run_execution_valid=True`. The old C145 scalar-conversion warning is in a passing test, not a C158 failure.

Supported: the actual frozen Controller proposal drove authorized retrieval, sequential admission/projection and live reobservation; successful recovery reaches ANSWER_ACTION, and the registered failure/denial branches reach STOP without stale payload use. This connects previously isolated components into a short bounded reference-recovery loop.

Not supported: generated answer content, live query-to-record selection, semantic relevance recognition, an initially empty world state, changing observation epochs, general recovery planning, production deployment, concurrency or durable atomicity. The 128 bindings repeat 64 records in two layouts; three already-trained routers see the same small logical policy patterns. Runtime permission/budget gates and the one-attempt cap are explicit code, not learned authority. Twenty-three seconds (23.1426086) is total diagnostic time including replay/validation/storage, not production action latency. Gate E remains NOT PASSED.

## C159 — ACTIVE, awaiting user CPU execution

Experiment: `C159-v5e-evidence-bound-terminal-result`.
Stage: `V5-E-EVIDENCE-BOUND-TERMINAL-RESULT`.

**Question:** can the accepted C158 terminal readback be converted into a request/snapshot-bound typed return value without confusing observed zero with unresolved, leaking a fetched-but-not-admitted value, or returning another request's evidence?

The single new boundary is **terminal result -> explicit return schema**. This is a deterministic recorded-output bridge, NOT a new answer model and NOT a new live-loop execution. It deliberately makes the output contract explicit before any later learned answer-content or live-query integration. No C160 is registered here.

```text
hash-pinned C158 episode plan and terminal trace
-> immutable BoundRequest(request, scope, record, source, time, revision)
-> emit_terminal(binding, source_request_id, result)
-> typed TerminalResult -> JSON roundtrip
```

The emitter receives no scenario label, semantic ground truth, expected value, corpus, answer table or model. It copies the validated final working payload, checking it against the final readback and matching OBSERVED ref in the final EvidenceState snapshot. It never uses a raw fetched response as output evidence. Stored source assessments and expected values are used by the separate evaluator only, after emission.

### Return schema and boundaries

Diagnostic schema version: `c159-terminal-result-v1`, not a production/public API commitment.

| Status | Value | Supporting record/source/time/revision |
|---|---|---|
| ANSWERED | observed integer 0 or 1 | present and bound to the request |
| UNRESOLVED | None | all None |
| REJECTED | None | all None |

Every output retains request ID and scope ID. ANSWERED requires terminal action 0, RESOLVED readback, presence=1, matching final/last working slots and payload, the same observed reference and fixed evidence clocks. A zero is valid and not tested by truthiness. STOP_UNRESOLVED/action 5 requires absent payload/reference and cleared working presence/value. Its reason comes from the recorded runtime authority/admission/read status: MISSING_DELIVERY, PERMISSION_DENIED or BUDGET_EXHAUSTED for the registered source cases. A miss is not a claim of real-world absence.

No wrong action is relabeled as a successful learned STOP. REJECTED is an explicit output-validation result; the original action remains in the source trace. These guards assume trusted hash-pinned local artifacts; identity comparison is not cryptographic provenance authentication or semantic relevance checking. ANSWERED means an observed bit was safely copied, not that a model reasoned out an answer or generated natural language.

### Source integrity and unchanged variables

Require the accepted C158 report, its episode plan and all three 640-row episode JSONL files, including declared hashes and sizes. Hash every upstream input listed by C158 (including older checkpoints, arrays and snapshots) without loading a model. Reaggregate all 1,920 source episodes, action sequences/margins, state references, values, clocks, budgets, acquisition/publication counts, read costs and scenario totals. No missing file may be reconstructed or silently rebound. This is artifact validation, not rerunning the old Controller/adapter.

Reuse all three source router identities and both layouts; do not select successful traces. No model load, neural forward, new retrieval, live reobservation, training, fresh seed, new observation, state mutation or production change occurs. The C158 path and all previous experiments remain unchanged.

### Registered base cases and output-fault controls

Base: all 1,920 terminal records -> **768 ANSWERED** (324 zero / 444 one) and **1,152 UNRESOLVED** (384 each missing delivery / permission denial / exhausted budget).

Controls are independent deep copies, not modifications of source files or observed model failures:

| Control | Cases | Intervention | Required output |
|---|---:|---|---|
| WRONG_REQUEST | 1,920 | Change presented source request ID only | REJECTED / REQUEST_MISMATCH |
| WRONG_PROVENANCE | 768 answered | Change final ref's source ID only | REJECTED / REFERENCE_MISMATCH |
| PAYLOAD_DISAGREEMENT | 768 answered | Flip final_value, retain working/last value | REJECTED / PAYLOAD_MISMATCH |
| FORCED_UNGROUNDED_ANSWER | 1,152 unresolved | Replace terminal/action with ANSWER/action 0, keep absent evidence | REJECTED / ANSWER_NOT_GROUNDED |

Total controls **4,608**; total emitter calls **6,528**. No base emission or control mutates its input. JSON serialization preserves integer 0/1 and None/null. Injected terminal controls do not rerun or alter a learned Controller, and their unchanged old logits are not interpreted as new model outputs.

Save actual outputs/reasons, post-emission expected-status checks and each control's output in per-router JSONL bound to original episode filename/hash and row index. The output artifacts are diagnostic records, not durable publication or a network response. No performance advantage is claimed from these counts/timings.

### PASS / FAIL / INVALID

**PASS:** exact base status/value counts, all 4,608 controls rejected with registered reasons and no usable value/supporting evidence, zero measured input mutation, zero JSON roundtrip failures, preserved protected files.

**VALID NEGATIVE / FAIL:** valid source/setup but a wrong base value/status/ref, missed rejection, wrong rejection reason, value leakage, measured mutation or serialization mismatch. Save outputs and return a scientific FAIL with CLI exit 0. Do not change guard thresholds, source cases or expectations after seeing the run.

**INVALID:** wrong/missing source/hash/plan/lineage, malformed input source, source reaggregation mismatch, unexpected exception or outer guard failure. Preserve invalid output and retry the same C159 after fixing execution validity. Original C158 remains accepted within its scope.

Gate E remains NOT PASSED. Live query ranking, learned/semantic answer content, changing-world observations, relevance-based abstention, multiple acquisition planning and durable/crash recovery remain separate. PC-ALM/FHLC and Multi-Axis remain independent tracks.

## Reviewer verification

New benchmark, CLI, 33-test helper file and runner, this addendum and handoff.
**33/33 new CPU tests passed** using only standard-library code; Python compilation passed. They cover zero/one/unresolved outputs, request/source/ref/clock/payload mismatches, hypothesis/duplicate refs, output immutability, full-shaped source-row checks, strict gate counts and JSON roundtrip. They do not use real user episode files.

A separate fabricated full-size 128-binding/3-router/5-scenario integration passed source reaggregation and all 6,528 emissions. An intentionally broken emitter produced a **valid FAIL** with 768 failed base cases; tampered input produced **INVALID**. Test-only source-hash substitutions were confined to this synthetic reviewer process, not added to the executable or CLI. The actual uploaded console header was parsed and checked, but user's complete C158 JSONL and older artifacts were not available locally.

Full **508-test suite = 475 + 33**, actual artifact-chain integration and PowerShell execution have **not** been reviewer-executed. No formal C159 result is claimed.
