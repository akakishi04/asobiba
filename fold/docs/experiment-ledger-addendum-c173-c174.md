# C173 verdict and next boundary

Recorded 2026-09-17 JST from the uploaded C173 execution log.
Preregistration: `experiment-ledger-addendum-c173-preregistration.md`.
Acceptance and handoff update precede any C174 registration or implementation.

## 1. Formal verdict

**C173 — ACCEPTED PASS.**
`C173-v5e-bounded-acquisition-lifecycle`; `V5-E-BOUNDED-ACQUISITION-LIFECYCLE`.
Execution branch `feat/sft-target-loss`, HEAD `2cc2b1f40e9c7638e4bc0f72c07feb85d95a9c26`.
C170/C171/C172 and all earlier scoped results remain unchanged.
C160/C168/C169 retain ACCEPTED VALID NEGATIVE. **Gate E NOT PASSED.**
C174 is not registered at this acceptance boundary.

## 2. Execution validity and identity

Uploaded log `貼り付けられたテキスト（1 点）(20260917-063609).txt`, 176824 bytes.
Independently calculated uploaded-byte SHA256:
`03a707019601259609a5fb288c4789d03bcb800be9fde71d4bfab175a05afc73`.
Report `runs/c173-v5e-acquisition-lifecycle-4507b2745ec8499982006b960a469bd3/summary.json`.
SHA256 `3c4759bbc14b4ab9849d482d2f330cbf1038c1473e2deab2aaf40f9637e635aa`.
The complete console summary was parsed and re-encoded as sorted, indented UTF-8 JSON
with LF and a final newline; its hash independently matches the runner report.
Plan SHA256 `4a604a5c461f60eb04d881a63849248f9c873915fdc225ddc9b560a26c68b67b`.
Detailed `acquisition-results.json`:122 scenario rows,2063202 bytes,
SHA256 `254eba8b6d90fdbd096adae1938f018d703850be27b9354ff157f6adaee538c2`.
Parent C172 SHA256 `b1698509fa5ab384b86731662092568e9348fe907ab9f4707ed0ea802709e943`.

921/921 focused regression PASS in8.216 seconds;921 test-method lines independently counted.
Source precheck PASS;all8 progress groups completed;diagnostic_execution_valid=true;
outer run_execution_valid=True.54 declared input paths (including plan and10 fixture
source files),36 historical source pins,C37,composition fixture,outputs,tree and HEAD
preserved per runner. production_runtime_modified=false;gate_e_candidate=false.
The existing C145 tensor-to-scalar warning is inside a passing historical regression,
not C173 invalidity. No new training,seed,learned forward,network or core evidence write.

## 3. Metrics

| Metric | Observed |
|---|---:|
| Scenarios / failed checks |122 /0|
| C172 action calls / owner dispatch calls |236 /143|
| Acquisition reservations / internal units |122 /417|
| Provider callback calls / file-read attempts |98 /95|
| Actual source bytes read |26434|
| Successfully validated source-record count |176|
| Fact publications / derived answers |24 /12|
| C171 verifier calls / evaluated proof rules |18 /36|

Groups:success12,delivery_faults60,pre_dispatch27,source_guards8,staged6,
reentrant3,retry_budget3,replay_delivery3. All exact deciding counts match registration.
Three old-delivery callbacks perform no new file read.143 dispatch calls include3
nested denied calls.95 reads,98 callbacks and24 publications are not interchangeable.
176 is the provider's successfully validated-record counter,not all validation operations.
The2.374300499999663-second benchmark wall time is not neural inference latency.

## 4. Scientific interpretation

scripted named proposal -> reservation -> current-authority recheck -> bounded real
local file read -> source/binding/payload validation -> selected TaskView fact publication
-> supplied proof using admitted facts -> unchanged C171 verifier -> derived answer.

The declared finite integration path and adversarial lifecycle controls satisfy their
contract. Failed deliveries do not publish facts;staged old proofs are invalidated;
replayed other-target responses and reentrant dispatch do not create extra observations.
The selected value is matched to the pinned source witness,not just a claimed source ID.
This advances C172's reservation-only evidence without relabeling C172 as actual fetch.

## 5. Confound audit and limits

Actions and proof producers are scripted,not a learned necessity/answer policy. OBSERVE
and ASK_USER are local-file simulations,not sensors,human conversations or messages.
The provider is a tiny exact reference,not C151 ranking or the historical vector adapter.
Source truth is caller-owned;hash identity does not establish real-world truth.
Private source witnesses contain unchosen records for validation;the policy-facing
TaskView exposes only admitted target facts. This is API separation,not a process sandbox.
Snapshot epoch is fixed;there is no general freshness/conflict resolution claim.
Single-owner synchronous/reentrancy handling is not crash durability or cross-process CAS.
TaskView publication is not production EvidenceState or long-term memory integration.

Reviewer checked the full summary against preregistration,source gate/accounting,identity
and outer postchecks,and independently reconstructed the summary and uploaded-log hashes.
The122-row acquisition-results file and10 source files were not separately uploaded;
no independent per-scenario replay,user-machine source inspection or921-test rerun is claimed.
All old outputs and conditions are retained;no repair or C173 rerun is needed.

## 6. Next design boundary

The remaining central scientific question is learned task necessity,not another unchanged-
source inventory. Design an explicitly bounded offline learned probe using the accepted
C170 input:can it distinguish sufficient visible facts from cases requiring additional
observation,without evaluator-supplied dependency or hidden values? Compare to a matched
syntax-ablated reader and a transparent missing-fact rule;freeze splits,training,metrics
and criteria before any deciding training. Keep this pilot distinct from full Gate E,
FOLD-core integration,proof generation and autonomous live action choice.
Do not use a shared symbolic proof builder to claim learned answer quality. No final
Gate E holdout or final threshold is fixed or evaluated by this acceptance document.
