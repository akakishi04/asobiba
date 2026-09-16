# C168 preregistration — Task-necessity input observability

Registered 2026-09-17 JST after C167 acceptance and the user's instruction to proceed.
Basis: `experiment-ledger-addendum-c167-c168.md`, `gate-e-acceptance-gap-audit-after-c167.md`,
`gate-e-evaluation-contract-v0.1.md`. The audit's earlier unregistered draft is historical;
this document is the registration. No earlier verdict or scientific threshold is changed.

## Formal state

**C168 ACTIVE / NOT YET JUDGED.**
`C168-v5e-task-necessity-input-observability`.
`V5-E-TASK-NECESSITY-INPUT-OBSERVABILITY`.
Branch `feat/sft-target-loss`; parent documentation HEAD `2f1f3a06e9c4499db34ad1e9aea8b4225fc8e095`.
Use the registration commit containing code/tests/runner/docs/handoff as ExpectedHead.
C167 ACCEPTED PASS; C160 ACCEPTED VALID NEGATIVE; Gate E NOT PASSED. C169 unregistered.
Diagnostic-only; no production modification, training, new seeds or new weights.

## Scientific question and interpretation

Can the **existing post-selection Controller input boundary**, without an externally
correct dependency label or a new expression encoder, distinguish answer-critical and
irrelevant missing information in the following finite logical extension probe?

This is an interface-readiness audit, NOT a benchmark of supported logical raw queries.
C151 is not asked to rank `A OR B`; ranking is not run. All probes bind the same selected
record B. Operator and known A are explicit audit-side visible task fields for a proposed
extension; the inspected current helper has no route for them. That absence is recorded,
not hidden behind an invented encoder. Existing C167 source fixes dependency=1. The
likely limitation is already suspected from source review, not an unseen-model forecast.

We classify **requires acquisition / does not require acquisition**, not ANSWER versus
COMPUTE. An irrelevant B does not prove the existing emitter can return the expression's
computed result. C159 still only represents observed bits; derived answers are separate.

## Changed / held constant

Probe-visible operator AND/OR and known A0/1 change in the task manifest. Every task has
B unobserved and acquisition available. Full crossing with nuisance stale_bit0/1 prevents
known A being accidentally supplied via the legacy stale-payload slot. No input field is
retuned or repurposed to rescue separability after measurement.

Hold current C160 initialization, C156 reobservation/canonicalization, C158 _decision
context/operation construction and core state/controller code fixed. PermissionTrue,
initial budget(3,1), evidence time/revision1, internal step7, fixed selected B, scope and
request IDs, and63 other reference identities are fixed. The fixture is64 synthetic
unread references with no payload store. It is not a C167 persisted-corpus replay.

## Exact plan / counts

- Challenges:2 operators x2 known A values x2 stale bits = **8 rows / 4 semantic cases**.
- Source controls: selected B missing x availableFalse/True x stale_bit0/1 = **4 rows**.
  AvailabilityFalse is a declared source-control context, not a new permission trial.
- **12 pre-forward input captures**;12 actual C156 reobservations;0 resolver calls.
- **0 neural forwards,0 model/checkpoint loads,0 ranker executions,0 retrieval/acquisition,
  0 complete live cycles,0 terminal emissions,0 training steps,0 fresh seeds** in benchmark.
- Evaluator enumerates16 Boolean completions for the8 challenges; no actual hidden B is
  instantiated or supplied to runtime. Source controls have evaluator labels after capture.
- Four operator-only matched pairs plus four known-A-only pairs; retain all8.

Capture uses unchanged `C160.execute_selected` with an explicit cycle callback. That
callback invokes actual `C156.reobserve` on the received63-reference state and actual
`C158._decision` with a capture callable. The callable saves working/context/operation
arguments and raises a private capture-complete exception **before any learned forward**.
It is not a fake predicted action, a full cycle, or a global monkeypatch. Resolver/emitter
callbacks fail closed if unexpectedly invoked. The real core states, internal-step debit,
missing-value clearing and original context tensor construction are exercised.

Capture accepts only stale_bit and availability; no operator, A, hidden B or label. This
explicit projection tests what the existing supported boundary conveys, not an invented
claim that a logical task encoder already exists. A/operator fields stay in the audit
manifest and are used only after all captures have been constructed.

The label-free manifest SHA256 is
`35824233cdc5061e004ddbb1633fc260fcbc5a35ebbeb67793f7705059e2fbfd`; the runner
checks it before capture. Full task-plan hash additionally includes source pins.

## Controls and deciding metrics

Group exact complete captured working/context/operation tensors AND runtime availability,
permission, budget, clock and reference-count data. Group before reading labels; exclude
audit case IDs, labels and unsupported task fields. Store actual tensor values/dtypes/shapes,
not merely hashes. For each equivalence class record all cases, label counts, conflict and
`class size - largest label count`, an unavoidable classification-error lower bound for
any deterministic policy using only those inputs on this finite probe.

Use truth-table enumeration as evaluator; check it against the independent controlling-
value formula. A symbolic full-visible-input reference must yield four nonconflicting
semantic classes. This is a task-validity control, not a learned model or candidate repair.
The4 original selected-bit availability controls must encode two nonconflicting classes.
Compare all8 operator/A-only pairs. Preserve every collision and concrete counterexample.

## Formal decision rules (fixed before benchmark)

**PASS:** all coverage/source/task-validity controls valid; zero conflicting necessity
classes and zero collapsed operator/A pairs. This is only finite input separability,
not learned correctness, useful acquisition, generated answers or full Gate E success.
Absence of complete-input collisions also does not prove that the ControlLane router
uses all carried fields; its current learned path reads a fixed four-channel lane.

**ACCEPTED VALID NEGATIVE / FAIL:** valid execution with one or more incompatible
necessity labels sharing exact inputs or a required visible distinction lost at this
boundary. Save the entire result. Do not supply the correct dependency bit, insert a
logical encoder, enlarge a model, remove tasks, choose a checkpoint or relax the rule
inside C168 to obtain PASS. CLI exits0 for a valid finite negative.

**INVALID / RETRY C168:** malformed plan, leaked evaluator data, source/parent/hash drift,
failed source-control accounting, unexpected callback/exception, nonfinite input,
incomplete capture or outer artifact/tree/HEAD failure. Restore execution validity and
retry the same specification. The private capture-complete exception is intended control
flow and not invalidity. Never relabel C160 or C167 based on this extension diagnostic.

## Source lineage / artifacts

C167 parent `runs/c167-v5e-live-warm-reference-c9c6b3da430a408f9032690e76ec232a/summary.json`.
SHA256 `5907d4b2dd4e66a9a2d8a6017b68ab8461a9bfca6bd90dd01c1774f5c3e020e9`;
execution `a3eb2dba7c3c74de90d228f1c6d2648ef1cee8d1`.
Validate its hash/full-summary identity. C168 does not consume its48 traces or historical
weights; do not rehash the entire698-path chain or claim a replay. Keep those artifacts.
C37/composition fixture remain outer protected artifacts, not benchmark model inputs.

Historical source blobs are pinned in the module, with transitive definitions resolved
at fixed BASE; accept only exact checked-out bytes or their LF/CRLF equivalent. Source
code is unchanged. New output uses a fresh UUID directory; save input-plan.json before
measurement, then full summary.json including all12 captures/classes/matched pairs.
Record source/plan/input hashes, commit, timing, limitations and valid scientific status.
Both Python and PowerShell recheck protected inputs, tracked tree and HEAD.

## Tests / execution / stop

Files: `fold_lm/v05_benchmarks/gate_e_c168_necessity_observability.py`,
`tests_lm/test_v05_c168_necessity_observability.py`, `tools/run_c168.ps1`.
Focused regression **749 expected =725 accepted historical tests +24 new tests**.
The51 prior test module names are read as text from the pinned C167 runner, not executed
as a script; append only the new C168 test module and enforce the749 count.
Historical regression helper training/forwards are separate from the zero-forward
scientific benchmark. No GPU is required by the C168 diagnostic itself.

Reviewer compiled the new Python files and ran20 dependency-free unit tests successfully.
The4 actual-repository integration tests, full749 tests, artifact-backed CLI and Windows
PowerShell execution were not run in the reviewer environment. No formal C168 benchmark
was run while designing this registration; unit fixtures are not deciding evidence.

Runner uses `.venv-py31315/Scripts/python.exe`, arguments `-C167Summary -ExpectedHead`.
Progress: `[C168] plan fixed; 8 challenge cases + 4 controls`, then `captured=12/12`,
`=== C168 RESULT ===`, `=== C168 POSTCHECK ===`, `run_execution_valid=True`.
Return and review the complete log even if scientific_status=FAIL and validity=True.
**Judge C168 -> update ledger/handoff -> design next C. No C169 yet.**
