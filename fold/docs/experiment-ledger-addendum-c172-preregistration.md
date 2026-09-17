# C172 preregistration — Typed action runtime boundary

Registered 2026-09-17 JST after C171 acceptance commit
`3b091947451df19fb17474c490d9921916a17bbe`.
Read `structured-action-runtime-v0.1.md` for exact transition and cost semantics.

## Formal state / question

**C172 ACTIVE / NOT YET JUDGED**.
`C172-v5e-typed-action-runtime-boundary`; `V5-E-TYPED-ACTION-RUNTIME-BOUNDARY`.
Branch `feat/sft-target-loss`; use the final registration commit as ExpectedHead.
C171/C170 remain ACCEPTED PASS; C160/C168/C169 remain ACCEPTED VALID NEGATIVE.
**Gate E NOT PASSED. C173 NOT REGISTERED.**

Can one typed action boundary enforce current task/runtime identity, stage and validate
proposed derived conclusions, and reserve external requests without duplicate spend,
unauthorized reservation, or promotion of an intent to observed evidence?
This is implementation/reference validation, not learned policy efficacy.

Change: add opt-in structured_action_runtime. Hold C170 input, C171 verifier, all old
Controller/retrieval/emitter code, checkpoints, previous results and Gate E scope fixed.
No legacy-index remapping, learned reader, training, fresh seed, hidden answer/necessity
label, actual acquisition, external messaging, provider response or evidence write.
Production runtime is not wired to the module. Scripted named proposals are test inputs.

## Exact finite batch

197 calls to step, collected in eight groups in fixed order. Every case includes
before-state, proposal, actual transition and fixed expected outcome/accounting. No
outcome-dependent repairs or case removal. Dependent program probes use actual returned
states; a failed step does not silently get replaced with an expected state.

| Group | Calls | Fixed coverage |
|---|---:|---|
| external_grid |48|3 tools x availabilityFalse/True x permissionFalse/True x acquisition0/1 x internal0/1; selected B unknown.|
| local |10|Each bit0/1: stage, ANSWER, closed ANSWER; separate unprepared ANSWER and zero-budget STOP.|
| malformed |24|Fixed proposal/schema/type/target/candidate/payload corruptions; unchanged-state rejection.|
| stale |12|Changed request,scope,time,revision,expression,fact ID,support ID,value,availability,permission,allowance,transition; original proposal must not execute.|
| pending |15|Each tool: reserve, exact replay, fresh duplicate, cross-tool request, STOP. No second reservation/refund.|
| proof_rejection |24|Each bit x six corruptions x stage/ANSWER; well-shaped incorrect candidates stage but must reject at verifier.|
| proof_budget |40|Each bit x initial internal0/1/2/3/4 x configured proof capacity0/1/2/7; two-step proofs.|
| fact_status |24|3 tools x8 supplied fact statuses; already observed denies, all other statuses may reserve but do not become observations.|

The six proof corruptions are conclusion, support identity, expression digest, support
for unobserved B, rule name and reversed proof. The24 malformed names and12 stale changes
are in the label-free manifest and source. Main fixture has observed A0/1 and unknown B;
AND for controlling0/OR for controlling1, two-step supplied proof, internal budget8 and
acquisition1 except declared grids. All sources/statuses are trusted in-memory fixtures.
No C151 ranking, C158 live recovery or C171600-row reexecution.

Required aggregate accounting:197 calls,27 acquisition reservations,147 internal units,
46 C171 verifier calls,28 evaluated proof rules,0 finite check failures. Predicted status
counts from the registered program are PENDING27,STAGED14,VERIFIED_DERIVED10,
UNRESOLVED5,DENIED62,REJECTED79; the per-case checks, not acceptance fraction, decide.
These are dependent fixture transitions, not197 independent task samples or accuracy.
Actual provider calls/acquisitions/evidence writes/learned forwards/training/seeds=0.

COMPUTE stages an explicitly proposed unverified proof; it does not execute a solver.
ANSWER pays1 dispatch unit plus actual rule evaluations and consumes no external budget.
External PENDING reserves1 unit but performs no IO; reservation is not completed fetch.
STOP cancels only local pending intent with no refund; no asynchronous cancellation claim.
Source binding includes resource snapshots, so changing authority after proposal makes
it stale. A fresh denied proposal charges the declared dispatch unit but never reserves
an acquisition. No zero-cost neural-computation claim follows from this bookkeeping.

Label-free manifest SHA256:
`c706b3dd02677b7c6e1ad00a813fa99cb6f2a318f5850c9b35271b0bb1e64c76`.
Save the manifest plus all source pins before measurement.

## Decision rules

**PASS:** complete197 cases and exact group/accounting totals;zero per-case failures;
correct statuses/typed values/bindings, no extra intent, no changed observations;
rejected/denied results expose no successful derived payload;staged candidates are not
silently solved;all source/artifact/tree/HEAD protections preserved. Scoped action-
boundary correctness only, not learned decisions, real transport, or full Gate E.

**ACCEPTED VALID NEGATIVE / FAIL:** finite wrong status,binding,mutation,budget,duplicate
reservation,proof result or guard behavior under valid setup. Save all independent cases
and remaining declared programs. Do not repair the module/cases/cost policy mid-run to
obtain PASS. A complete finite negative exits0 for log collection.

**INVALID / RETRY C172:** bad source/parent/hash/manifest, malformed trusted configuration,
unexpected exception, incomplete attempted coverage, or outer source/output/tree/HEAD
failure. Preserve invalid.json when output directory exists;restore execution validity
and retry unchanged C172. Listed malformed untrusted proposals are finite guard tests,
not malformed trusted setup. No rule/threshold/checkpoint changes to relabel old results.

## Artifacts / source protection

Parent C171 `runs/c171-v5e-derived-result-23bd4bdf2838457f9a156bbb902b2b3c/summary.json`.
SHA256 `4509a1e9fa5bf2072af18ac633fd2ee95ba2da35af4ab0dc3bc661437fc9853c`.
Execution `42bc2b83269a1279e50d51156de11b9d720b17c0`.
Pin its24 historical entries plus C171's6 own files at that execution HEAD. New module,
benchmark,test,runner,design and this preregistration are checked against registration
HEAD. Exact bytes or LF/CRLF-equivalent checkouts only. Source precheck precedes tests.
No recursive old record or checkpoint replay;preserve prior proof/input/trace artifacts.
C37 and composition fixture remain protected outer files,not loaded model inputs.

Fresh UUID directory:action-runtime-plan.json before probes;action-results.json with
all197 transitions;full summary.json with hashes/sizes/counts/source/commit/limits.
Python and PowerShell recheck inputs/source/tree/HEAD;runner checks output hashes/sizes.
This is file integrity,not independent semantic replay. No pending intent is transmitted.

## Verification / execution / stop

New files: `fold_lm/v05/structured_action_runtime.py`,
`fold_lm/v05_benchmarks/gate_e_c172_action_runtime.py`,
`tests_lm/test_v05_c172_action_runtime.py`, `tools/run_c172.ps1`, and the two new docs.
Focused regression **885 expected=845+40**,56 modules,run once before the batch.

Reviewer compiled all3 new Python files and passed40/40 new unit tests using the actual
new modules and exact C170/C171 dependency copies (Git blobs b874b6ab... and56709025...).
No substitute dependency implementation. Four embedded Python commands in the runner
were parsed as Python;this is NOT Windows PowerShell execution. Full885,actual Windows
runner,source guards and artifact-backed197-case batch were not run by the reviewer.
No formal C172 deciding run was executed before registration. Development unit fixtures
are not heldout evidence. No GPU is needed by the diagnostic itself.

Runner `.venv-py31315/Scripts/python.exe`;`tools/run_c172.ps1 -C171Summary ... -ExpectedHead ...`.
Progress `[C172] plan fixed;197...`, `checked=197/197 failed=... reserved=...`, RESULT,
POSTCHECK and `run_execution_valid=True`. Collect valid FAIL without changing conditions.
**Judge C172 -> ledger/handoff -> next design. No C173,transport or learner experiment
before judgment.** Remaining transport,reply/admission and policy-learning work is real,
not concealed by naming an intention an executed action.
