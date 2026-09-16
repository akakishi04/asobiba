# C170 verdict and next boundary

Recorded 2026-09-17 JST from the user-uploaded C170 log, before next registration.
Preregistration: `experiment-ledger-addendum-c170-preregistration.md`.

## 1. Formal verdict

**C170 — ACCEPTED PASS.**
Experiment `C170-v5e-structured-task-input-contract`;
stage `V5-E-STRUCTURED-TASK-INPUT-CONTRACT`.
Execution branch `feat/sft-target-loss`, HEAD `da09a86e25f12927a9206217b7933609c2fe1b8c`.
C160/C168/C169 remain ACCEPTED VALID NEGATIVE; all prior scoped verdicts remain intact.
**Gate E NOT PASSED. C171 not registered at this acceptance boundary.**

## 2. Identity / execution validity

Uploaded file `貼り付けられたテキスト（1 点）(20260916-193427).txt`,160897 bytes.
Independently computed uploaded-byte SHA256:
`cad4ee19eafa563a3226f4fdb479dadb33ea2a3cbb246bc57884e9d062f78eb7`.
Report `runs/c170-v5e-structured-task-input-e999793ff0314b959994ea3ed308aa5e/summary.json`.
Report SHA256 `a1858cd65a56b5cad09b1e339500f7f8a9011c4f1de721300c3a77ee11f1183e`.
Reviewer parsed the complete report printed in the log and re-encoded it using sorted,
indented JSON with LF and a final newline; the hash matches the runner exactly.
Plan SHA256 `a2321edf6689daf1659469dc46808f5f77922a5c0c21c999fe8da836219556ec`.
Capture artifact `policy-inputs.json`,532 rows,687409 bytes,
SHA256 `67aece55863f079d3e38e691519bb1dee8c86b1cefab71720f2a2cddacd02345`.
C169 parent SHA256 `1a509646a01c26306f6a41b0dfaca968be39500d12e21bef7d04b98b82fd2ae6`.

809/809 focused tests PASS in8.347 seconds.809 test-method lines counted independently.
Benchmark completes with diagnostic_execution_valid=true and outer run_execution_valid=True.
26 declared input paths (including newly written plan),18 historical source pins,
protected C37/fixture,output artifacts,tracked tree and execution HEAD preserved per runner.
Historical runtime modified=False;learned forwards/adapter calls/training/fresh seeds=0.
Existing C145 tensor-to-scalar warning is inside a passing regression,not invalidity.

## 3. Metrics

| Metric | Observed |
|---|---:|
| Capture attempts / consumer calls |532 /532|
| Failed roundtrips |0|
| Numeric feature width |72|
| Necessity development cases / numeric classes |8 /4|
| Conflicting classes / unavoidable-error lower bound |0 /0|
| Template roundtrips |252|
| Read-status roundtrips |16|
| Resource roundtrips / distinct numeric classes |256 /256|
| Malformed controls / rejected |40 /40|

Reviewer independently checked all14 summary fields,40 uniquely identified rejected
controls,and the8 necessity rows against Boolean completion enumeration. Four paired
numeric hashes preserve operator/known-A distinctions and ignore the audit-only stale bit.
Benchmark wall time1.3309182999946643 seconds is diagnostic execution,not model latency.

## 4. Scientific interpretation

visible ordered expression + supplied fact views + resource snapshot
-> explicit structured-v1 encoding -> schema-opted capture consumer -> exact reconstruction.

The new interface preserves the registered task distinctions,where C168's legacy selected-
record path collapsed them. This is an implementation-level development contrast,not a
heldout learned-model comparison. The consumer is not a trained reader;no necessity
classification accuracy,logical solving,acquisition benefit or hallucination improvement
was measured. Binding sidecars preserve opaque IDs separately from72 numeric fields.
C170 does not change or relabel C168/C169 negatives.

## 5. Confound audit / verification limits

No hidden B,correct dependency,expected output or solver is supplied to the encoder.
Statuses/provenance are fixture declarations,not authenticated observations or automatic
staleness/conflict detection.252 rows cover10 declared templates,not every bounded formula.
The complete summary hash was independently reconstructed,but the532 packets are stored
in a separate unuploaded file. Its declared hash/size and runner verification are recorded;
no independent user-side packet replay,809-test rerun or source-disk inspection is claimed.
The eight development cases and numeric separability are not language/generalization evidence.

## 6. Ledger and next work

Acceptance/handoff precedes any next registration. Keep all historical artifacts and
C170 code/preregistration unchanged. No repair is needed to accept this run.
The next implementation question is the missing **derived-result validation boundary**:
can an explicitly proposed bounded derivation return a task conclusion using current
usable support,without asserting the value of an unobserved fact or rewriting observations?
The verifier must remain hand-written infrastructure,not be called a learned solver.
Action dispatch and learning remain separate pending work;do not rediscover known gaps
with another unchanged-source inventory. Exact next counts and rules must be registered
before its deciding run. No C170 rerun is required for documentation changes.
