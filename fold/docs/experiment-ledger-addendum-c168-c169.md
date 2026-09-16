# C168 verdict and batched diagnostic boundary

Recorded 2026-09-17 JST after the user uploaded the complete C168 console and requested that remaining diagnostics be batched.
Preregistration: `experiment-ledger-addendum-c168-preregistration.md`.

## 1. Formal verdict

**C168 — ACCEPTED VALID NEGATIVE**.
Experiment `C168-v5e-task-necessity-input-observability`.
Stage `V5-E-TASK-NECESSITY-INPUT-OBSERVABILITY`.
Execution HEAD `5c181fe061e494a9ded2ccdfe6a6a94aa56321e2`, branch `feat/sft-target-loss`.
**Gate E NOT PASSED**. C167 remains ACCEPTED PASS; C160 remains ACCEPTED VALID NEGATIVE.
This is a valid extension-interface limitation, not invalid execution and not evidence that supported C167 tasks regressed.

## 2. Execution validity and evidence identity

Uploaded file `貼り付けられたテキスト（1 点）(20260916-184217).txt`: 171,013 bytes.
Reviewer independently computed uploaded-byte SHA256:
`a24e82b5c02d6d77e2759e039772b72fe1a00d917617e4f6e287f462f196ad09`.

Report `runs/c168-v5e-necessity-observability-a3e8dcd5d688480687db367ec28d3a3b/summary.json`.
Report SHA256 `3ef1433d0f2678237f70d1dddf8b3de4783ba676fba15b607281b97f7839124c`.
Unlike the preceding large consoles, this console includes all report records. Parsing the full JSON and encoding it with the registered sorted/indent2/LF format reproduces that exact SHA256. This checks the complete reported contents, not the user's local files independently.
Plan SHA256 `e78f48c98c8d877e8924d08fb41c119bec4bc7730ccbcfecd318d29b80242d25`.
C167 parent SHA256 `5907d4b2dd4e66a9a2d8a6017b68ab8461a9bfca6bd90dd01c1774f5c3e020e9`.

749/749 focused regressions PASS in12.278s. All12 captures completed; diagnostic_execution_valid=true; outer run_execution_valid=True. Protected inputs, tracked tree and execution HEAD preserved. Production runtime unchanged. Existing C145 warning occurs in a passing regression and is not invalidity.
Scientific benchmark:0 neural forwards,0 checkpoint loads,0 retrieval,0 full live cycles,0 training,0 fresh seeds. Helper activity in the regression is separate. Report wall-clock2.94619529999909s includes setup, not a production-latency measurement.
Reviewer checked complete report/captures, prior preregistration and inspected source. No independent user-machine rerun or local source/artifact verification is claimed.

## 3. Deciding metrics

-8 challenge rows =4 semantic cases crossed with stale bit0/1.
-4 source controls;12 pre-forward captures in total.
-Exactly1 complete-input equivalence class for the8 challenges.
-That class contains4 acquisition-required and4 acquisition-unnecessary labels.
-Conflicting classes1; deterministic classification-error lower bound4/8.
-All8 operator-only/known-A-only matched pairs collapse to identical inputs.
-Symbolic full-visible reference:4 classes,0 conflicts.
-Existing availability controls:2 distinct classes,0 conflicts.
-16 Boolean completions used only by the evaluator.

The error lower bound is an information bound on this balanced finite probe using only the captured inputs, not a measured neural-model accuracy or a universal50% accuracy ceiling. There are4 semantic cases, not8 independent task replications. A randomized input-only policy cannot gain information about the hidden class; do not claim a deterministic bound on every random finite realization.

## 4. Scientific interpretation

AND/OR and known A0/1 remain distinct in the audit-side task description but do not reach the inspected post-selection Controller boundary. C160's dependency input stays1; C156 correctly clears stale presence/value. Availability is transmitted, so the capture is not simply constant because it failed to execute.
No amount of retraining the same input-only policy can distinguish exactly equal inputs on these cases. The conclusion concerns the current selected-record composition path, not all possible FOLD architectures or all earlier experiments. No logical raw-query encoder was evaluated, and no derived-answer capability was measured.

## 5. Confound audit

Full crossing of stale0/1 avoids a spurious proxy for A. Permission, budget, selected B, clock and other references are fixed. Labels and case IDs are excluded from the equivalence key; full tensors plus runtime context are compared. No oracle dependency, task encoder, hidden B, checkpoint change, target filtering or threshold relaxation was introduced.
The unsupported logical extension is explicit in preregistration. Keeping operator/A outside the existing helper is the capability under audit, not grounds to invalidate an unfavorable result. Prior C167 warm/cold and C160 negative evidence are preserved.

## 6. Ledger and next work

Accept C168 and update handoff before registering the next experiment.
The user's batching request authorizes one bounded read-only diagnostic suite with separately reported sections. It does not authorize changing the candidate midway, skipping failed cases or replacing independent verdicts by an average. Existing source, checkpoints and past reports stay fixed.
At this acceptance boundary **C169 is NOT REGISTERED**. Next registration may combine independently runnable interface/readiness checks under one source snapshot and one execution command. Valid negative sections must not prevent other independent sections being collected; invalid source/setup must still stop or invalidate the batch. No C170 registration or repair is included here.
