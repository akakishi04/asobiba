# C170 preregistration — Structured task input contract

Registered 2026-09-17 JST after C169 ACCEPTED VALID NEGATIVE was saved at
`8658cd7a9468413fa3ee68696e72d1c0fe02c7ff`.
Read `structured-task-interface-v0.1.md` for the consolidated input/action/output design.

## Formal state / one question

**C170 ACTIVE / NOT YET JUDGED.**
`C170-v5e-structured-task-input-contract`; `V5-E-STRUCTURED-TASK-INPUT-CONTRACT`.
Branch `feat/sft-target-loss`. Use the final registration commit containing the new
module, benchmark, tests, runner, design, this document and handoff as ExpectedHead.
C169/C168/C160 remain ACCEPTED VALID NEGATIVE. C167 remains ACCEPTED PASS.
**Gate E NOT PASSED. C171 NOT REGISTERED.**

Question: does a new explicit bounded task-input contract preserve visible syntax,
usable facts, read-status and runtime-resource distinctions all the way to an opt-in
policy-consumption boundary, without externally correct necessity labels or hidden values?
This is an interface implementation/reference-validation experiment, not learned policy
efficacy. Its structural behavior is intentionally specified, not an unseen-model forecast.

## Changed and fixed

Change the task-to-policy interface by adding `fold_lm.v05.structured_task_input`.
Do not modify C158-C169, core state, historical Controller, emitter, C151 rankers,
checkpoints, accepted results or Gate E final-evaluation scope. No implicit old-schema
adapter or checkpoint reuse. No learned weight, optimizer, ranker, acquisition, full
live cycle, action execution, proof checker, terminal answer, evidence write or fresh seed.
New namespace code is opt-in; production runtime is not wired to it.

New input has at most4 fact slots,7 ordered AST nodes/3 binary operators, eight explicit
fact-read statuses and separate runtime resource fields. Encode72 exact integer fields
plus opaque binding metadata. Preserve left/right and repeated fact occurrences; no mean
pooling or tail truncation. Unusable values areNone; no Boolean expression solver is called
by the encoder. Upstream authentication and source read semantics are not implemented here.

The consumer is a schema-declaring capture callback. It receives the actual packet from
`deliver`; it is not C157, a trained classifier, or a substitute claimed as model behavior.
No other hidden label, task-specific expected action or value enters the encoder/consumer.

## Fixed finite batch

1. **8 necessity cases:** AND/OR x known A0/1 x audit-only stale0/1;B is unobserved.
   The nuisance bit is deliberately not a field of the new input. All input packets are
   captured before truth-table scoring. Require four numeric input classes with no
   conflicting necessity labels and error lower bound0. This repairs distinguishability
   of C168's development examples, not measured learned accuracy or independent holdout.
2. **252 roundtrips:** ten expression templates in the label-free manifest, crossed with
   every UNOBSERVED/observed0/observed1 assignment for their1..4 fact variables.
   Templates include leaf negation, repeated fact occurrences and distinct ordered
   nesting. Three1-fact,three2-fact,two3-fact,two4-fact templates =>9+27+54+162=252.
   This is not exhaustive over every possible four-variable expression.
3. **16 read-status roundtrips:** eight declared statuses in each of two fact positions;
   other fact remains known. No actual disk retrieval, freshness inference or semantic
   conflict detection is measured.
4. **256 resource roundtrips:** all8 availability masks x8 permission masks x4 budget
   pairs(0,0),(0,1),(3,0),(3,1). All256 numeric inputs must remain distinct. These are
   policy-view representation checks, not new runtime-authority executions.
5. **40 malformed controls:**28 prohibited payload injections(2 positions x7 unusable
   statuses xbits0/1) and12 malformed packet/schema/padding/mask/binding/range probes.

Total **532 capture attempts and532 consumer calls expected**, plus40 malformed controls.
Every successful packet must decode to the exact typed input including binding and leave
its source unchanged. Exact input layout and manifest are fixed before benchmark.
Label-free manifest SHA256:
`012efdd6e6ad2656929d034a95c93fdfda256b39df1c6788e0a5ecceb9ec5450`.
Policy-inputs file records all532 packets and any finite input rejection/error.
No output bit accuracy, hallucination reduction, acquisition benefit or Gate E pass is
inferred from input roundtrip/separability. Truth-table labels are evaluator-only.

## Source / artifact protection

Accepted parent C169:
`runs/c169-v5e-interface-batch-1aea40532e3f4a068bbea6603ebf74e6/summary.json`.
SHA256 `1a509646a01c26306f6a41b0dfaca968be39500d12e21bef7d04b98b82fd2ae6`.
Execution HEAD `c227e93c3c6f73dbf30fcfd457da88d3f01c1355`.
Validate full parent identity and six-section profile. Recheck its14 source pins plus
C169 module/test/runner/preregistration at the parent execution HEAD, and exact local
new source bytes at current registration HEAD (LF/CRLF equivalence only).
No recursive historical trace replay or old model loading. Keep all old artifacts.
C37 and composition fixture remain protected outer files, not model inputs.

Write input-contract-plan.json before new measurement; save policy-inputs.json and full
summary.json in a fresh UUID directory. Record source/input/plan/capture hashes and
size/count. Recheck inputs/code/tree/HEAD in Python and PowerShell. Runner checks output
hashes/sizes; that is integrity checking, not independent semantic replay.

## Formal rules

**PASS:** complete registered attempts/counts;532 unchanged roundtrips/consumer deliveries;
all40 malformed probes rejected;four necessity input classes/zero conflicts/zero lower
bound;256 distinct resource inputs;72-feature schema;all source/artifact protections pass.
This is a scoped input-contract PASS, not closure of C169's dispatch/output gaps.

**ACCEPTED VALID NEGATIVE / FAIL:** well-formed declared inputs rejected, finite loss or
mismatch, counterexample collision, mutated input, or a malformed packet admitted. Collect
other independent cases and preserve raw failures. Do not tune the schema/fixture/threshold
inside C170 to reclassify this result. Rejected valid packets are failures, not extra data
to silently remove. CLI exits0 for a complete finite negative.

**INVALID / RETRY C170:** source/parent/hash/manifest drift, malformed task generator,
nonfinite/unexpected execution exception, incomplete attempted coverage, or outer source/
artifact/tree/HEAD failure. Restore execution validity without changing scientific scope.

## Tests / command / verification

Files: `fold_lm/v05/structured_task_input.py`,
`fold_lm/v05_benchmarks/gate_e_c170_structured_task_input.py`,
`tests_lm/test_v05_c170_structured_task_input.py`, `tools/run_c170.ps1`.
Focused regression **809 expected=773 historical+36 new**,54 modules,run once.
All36 new tests passed against the actual new Python modules in the reviewer environment,
without AST substitutes, replacement dependency definitions or a trained model. Compiled
all three new Python files. Unit fixtures exercise development contract examples; no
hash-pinned artifact-backed formal C170 run has been executed before registration.
Full809 repository regression, authoritative Windows environment, PowerShell and formal
CLI/source guards remain unexecuted by the reviewer. No GPU is needed by the diagnostic.

Runner `.venv-py31315/Scripts/python.exe`;args `-C169Summary -ExpectedHead`.
Progress `[C170] plan fixed`, `captures=532/532 conflicts=... guards=.../40`,
`=== C170 RESULT ===`, `=== C170 POSTCHECK ===`, `run_execution_valid=True`.
Return the complete log including valid FAIL. Judge and update ledger before C171.
