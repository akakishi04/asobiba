# C171 verdict and next boundary

Recorded 2026-09-17 JST from the uploaded C171 console log, before next registration.
Authority: `experiment-ledger-addendum-c171-preregistration.md` and the conversation protocol.

## 1. Formal verdict

**C171 — ACCEPTED PASS.**
Experiment `C171-v5e-bounded-derived-result-contract`.
Stage `V5-E-BOUNDED-DERIVED-RESULT-CONTRACT`.
Execution branch `feat/sft-target-loss`; HEAD `42bc2b83269a1279e50d51156de11b9d720b17c0`.
C170 remains ACCEPTED PASS; C160/C168/C169 remain ACCEPTED VALID NEGATIVE.
**Gate E NOT PASSED. C172 NOT REGISTERED at this acceptance boundary.**
No rule, threshold, checkpoint, candidate or case was changed to accept this run.

## 2. Evidence identity and execution validity

Uploaded file `貼り付けられたテキスト（1 点）(20260917-000605).txt`, 160245 bytes.
Independently computed uploaded-byte SHA256:
`fd52df05aa1086ed99745380d9a64c70a51784b8db1cf38bc06a86c7d207af6e`.
Report `runs/c171-v5e-derived-result-23bd4bdf2838457f9a156bbb902b2b3c/summary.json`.
Report SHA256 `4509a1e9fa5bf2072af18ac633fd2ee95ba2da35af4ab0dc3bc661437fc9853c`.
Reviewer parsed the complete console report and independently re-encoded sorted,
indented JSON with LF and a final newline; its hash matches the runner.
Plan `derived-result-plan.json`, SHA256
`0b190e7afb34326969245c7721a84076624bfef72ef7d935095ec8d3080bfa86`.
Separate records `proof-results.json`: 600 rows, 2106641 bytes, SHA256
`745442826639d147e06ff7d5cb098d1f7e59c8c6767865a766f1e3d5232aca95`.
Parent C170 SHA256 `a1858cd65a56b5cad09b1e339500f7f8a9011c4f1de721300c3a77ee11f1183e`.

845/845 regression PASS in 8.230 seconds; reviewer independently counted 845 test-method
entries. Source precheck passes. Diagnostic validity true; outer run_execution_valid=True.
32 declared input paths, including the newly written plan, and 24 historical source pins
are reported preserved; C37/fixture, output integrity, tracked tree and HEAD checks pass.
The existing C145 tensor-to-scalar warning is inside a passing regression, not invalidity.
Learned forwards, adapter calls, evidence writes, training and fresh seeds are all zero.
Production runtime modified=false; gate_e_candidate=false.

## 3. Deciding metrics

| Group | Calls |
|---|---:|
| reference |504|
| malformed |48|
| unusable |14|
| rebound |16|
| resources |8|
| capacity |8|
| rule_scope |2|

Total verifier calls 600; VERIFIED_DERIVED 158; REJECTED 442.
Failed checks 0; reference false accepts 0; reference false rejects 0.
Actual rule evaluations checked_steps=1022 across all calls; this is not 1022 model
steps or a wall-clock bound. Benchmark time 1.752113599999575 seconds is diagnostic
execution, not neural-model latency.

## 4. Scientific interpretation

Proposed Boolean conclusion + explicit local proof + current trusted TaskView
-> bounded reference verifier -> verified derived result OR empty rejected result.

The registered finite tests support local proof/binding/guard correctness. Deriving
A OR B=1 from observed A=1 does not observe or assign B. Rejected candidates are not
repaired. C159's observed-value contract and C170's input contract remain unchanged.
The 442 rejections include deliberately wrong, unsupported, rebound and capacity/scope
controls; they are not 442 model failures. The overall 158/600 acceptance fraction is
not answer accuracy or useful coverage.

## 5. Confound audit and verification limits

Hand-written test proof producer and verifier are not learned FOLD reasoning. The
reference comparison uses the ten declared development templates, not a fresh holdout.
Trusted TaskView supplies support/status declarations; source authentication, arbitrary
freshness/conflict detection, concurrent publication and runtime debit are not tested.
Local rules intentionally do not prove unknown-A excluded-middle/contradiction cases;
these two expected rejections are not impossibility claims or complete Boolean solving.

Reviewer checked identity, full-summary hash, counts, aggregation, zero-work scope,
regression/outer protections and records descriptor against the preregistration/code.
**The separate 600-row proof-results.json was not uploaded. No independent row-level
semantic replay, user-machine rerun of 845 tests or disk-source verification is claimed.**
Runner integrity checks are not independent semantic verification. Keep all artifacts.

## 6. Ledger / handoff

This acceptance and authoritative handoff precede any C172 registration. No runtime,
verifier, input schema, historical experiment or learned weight changes in this commit.

## 7. Next design

Next bounded implementation question: typed action proposals under current runtime
identity/permission/budget, with explicit local staging/verified-answer/stop handling
and acquisition-intent reservation. Preserve observation/derived separation and keep
transport, asynchronous replies, actual provider admission and learning as explicit
separate boundaries. Do not advertise reserved intentions as completed retrieval.
Group independent boundary checks into one batch rather than repeating known-source
inventories. Exact next semantics, counts, code and rules must precede its deciding run.
