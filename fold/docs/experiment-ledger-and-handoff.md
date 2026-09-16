# FOLD Experiment Ledger and Handoff

> Current authoritative state. Historical verdicts, thresholds, code and artifacts remain unchanged.

## Environment / protocol

Repository `akakishi04/asobiba`; branch `feat/sft-target-loss`; local `M:\asobiba\fold`.
Python3.13.15 / PyTorch2.10.0+cu130 / CUDA13.0 / RTX4070 Ti SUPER; `.venv-py31315\Scripts\python.exe`.
Protected C37 `runs/chatgpt-last-result.json`: `FD4A8DA897BDAEA9D103A252E30212C7FF842D23300D7C837333E146DEE51931`.
Protected fixture `runs/fixtures/v05-c-composition-20260921.pt`: `A52F8209703149407580F7E2965B61B78653030EE992AF6D759865736741CA9E`.
Read `AGENTS.md`, `docs/experiment-conversation-handoff-protocol.md`, this file,
`docs/experiment-ledger-addendum-c169-c170.md`, **`docs/structured-task-interface-v0.1.md`**,
**`docs/experiment-ledger-addendum-c170-preregistration.md`**, and `docs/gate-e-evaluation-contract-v0.1.md`.
Judge -> ledger/handoff -> next C. Preserve valid negatives; invalid executions retry the same conditions/number.
User authorized batching independent diagnostics. C169 completed that finite inventory; do not repeat known gaps in more unchanged-source diagnostics. C170 batches all new input-contract checks, not multiple learned-model interventions.

## Formal state

Gate A/B PASSED; C/D PASSED within measured scope; **Gate E NOT PASSED**.
**C169 ACCEPTED VALID NEGATIVE; C168/C160 retain ACCEPTED VALID NEGATIVE; C167 retains ACCEPTED PASS.**
**C170 ACTIVE / NOT YET JUDGED. C171 NOT REGISTERED.**
C169 execution `c227e93c3c6f73dbf30fcfd457da88d3f01c1355`; acceptance/handoff commit
`8658cd7a9468413fa3ee68696e72d1c0fe02c7ff` precedes C170 registration. Use the final
C170 registration HEAD as ExpectedHead. Do not rerun C169 merely due to new code/docs.

## Accepted evidence / artifacts

The acceptance-only handoff at `8658cd7a9468413fa3ee68696e72d1c0fe02c7ff` and earlier
handoffs/chained addenda retain all prior evidence and identities. They remain authoritative.
C151's24 paired heads retain per-layout semantic WITHIN_FACTOR20,727/20,736,
GLOBAL_CONCEPT20,736/20,736,nine known errors; no ranker tuning. C152-C157 claims are
separate;C154 caveat remains. C158 preselected cycle,C159 recorded observed emitter,
C161 localization,C162 offline differential,C163 live tuple/list bridge,C164 missing,
C165 denied,C166 exhausted,C167 warm all retain accepted scoped results. C160 remains
negative,82,944 cycles with0 ANSWERED; never relabel. C167:725 tests,165,888 answered
cold/warm executions,one paid warm read/decision,no reacquisition;known errors36=9x2x2.
C168:749 tests,12 captures,8 challenges/four semantic cases collapse to one conflicting
class,minimum classification errors4/8. Not measured learned accuracy or a global bound.

**C169:773/773 regression;6 sections completed;GAP3,OBSERVED_BOUNDARY3,finite violations0.**
D1 inherits task-input gap. D2 feature prefix uses working/context0..3,not4..7,and averages
slots. D3 preserves state/clock/budget and zero/unknown separation;four runtime unresolved
reasons become one learned working tensor but runtime reasons remain. D4 availability
reaches current policy;permission/allowance do not separately;8 authority checks correct.
D5 selected-record dispatch has no handlers for1/3/4;scripted0/2/5 exercised safely.
D6 observed0/1 and mismatch guards work;no explicit derived-expression/proof result.
19 feature captures,8 observation probes,8 decision captures,8 authority probes,8 scripted
cycles/9 scripted calls,17 reobservations,6 fixture resolver calls,4 emissions;0 learned
parameterized forwards/checkpoints/real adapters/training/seeds.20 declared input paths,
source/tree/HEAD preserved per runner. Full uploaded JSON reconstructs matching hash;
17 reviewer consistency groups agree. No independent user-machine rerun claimed.

C169 `runs/c169-v5e-interface-batch-1aea40532e3f4a068bbea6603ebf74e6/summary.json`.
SHA256 `1a509646a01c26306f6a41b0dfaca968be39500d12e21bef7d04b98b82fd2ae6`.
Plan `08a329ce06f1878d518a1da90f612a6d0f216cd8e06642e6626bb82f3c45ab73`.
Log200,252 bytes, SHA256 `298fe22e4fe716e8cb89f6817f767a18080647b5ca1155781abc7f0c5519629d`.
C168 report `runs/c168-v5e-necessity-observability-a3e8dcd5d688480687db367ec28d3a3b/summary.json`,
SHA256 `3ef1433d0f2678237f70d1dddf8b3de4783ba676fba15b607281b97f7839124c`.
C167 report `runs/c167-v5e-live-warm-reference-c9c6b3da430a408f9032690e76ec232a/summary.json`,
SHA256 `5907d4b2dd4e66a9a2d8a6017b68ab8461a9bfca6bd90dd01c1774f5c3e020e9`.
Keep old outputs/traces; no recursive full-chain replay required for C170.

## Active C170 — Structured task input contract

`C170-v5e-structured-task-input-contract`; `V5-E-STRUCTURED-TASK-INPUT-CONTRACT`.
New opt-in `fold_lm/v05/structured_task_input.py` implements immutable bounded TaskView,
ordered AST/fact references,explicit read status/value mask and Resources snapshot.
72 exact integer features plus opaque binding sidecar;explicit schema acceptance by
consumer. No legacy four-lane adapter or old checkpoint under reinterpreted channels.
Encoder does not evaluate expressions or receive necessity/answer labels/hidden values.
Source statuses/supports are supplied views,not authenticated by this module.

532 packet deliveries/roundtrips:8 necessity-development examples,252 assignments over
10 templates,16 read-status views,256 availability/permission/budget views.40 malformed
controls. Require unchanged roundtrips,4 necessity classes/0 conflicts,256 distinct
resource inputs,all controls rejected. All collected as one batch. Consumer is a capture
callback,not a trained policy;no model,training,seeds,acquisition,action execution,
solver,derived-answer checking or evidence commit. Historical source/outputs unchanged.

Design `structured-task-interface-v0.1.md` also fixes boundaries for future named action
proposals/runtime revalidation and separate derived claims/proofs. **Those action/output
parts are DESIGN ONLY in C170;D5/D6 are not fixed by an input-contract PASS.**
Observed evidence stays distinct from task syntax and derived working state.

Use pinned C169 parent;write fresh UUID input-contract-plan.json,policy-inputs.json,
summary.json. Recheck source/input/output/tree/HEAD;preserve C37/composition fixture.
PASS is finite contract correctness only. Finite rejection/loss/collision/guard/mutation
failure is retained as VALID NEGATIVE;source/schema/nonfinite/incomplete/protection
invalidity retries C170 unchanged. No threshold/case/checkpoint tuning for PASS.

Focused regression **809 expected=773+36**,54 modules,once. All36 new tests passed against
actual new modules,without dependency substitutes;three Python files compiled. Full809,
authoritative Windows/PowerShell and artifact-backed formal CLI/source guards not run by
reviewer. No formal C170 result yet. Source blob contents match locally reviewed files.
Runner `tools/run_c170.ps1 -C169Summary ... -ExpectedHead ...`;CPU contract benchmark.
Return complete log even for scientific FAIL with execution validity True. Judge/update
ledger before C171 or learner/action/proof implementation experiments.

## Gate / independent track limits

Finite nine-family Gate E contract unchanged;final numerical preregistration remains
BLOCKED pending candidate/split/baseline/threshold/output definitions. Do not claim
learned necessity,answer solving,full Gate E,Vision,general language,long-context reuse,
durable memory,OS isolation or production rollout from interface plumbing.
Multi-Axis/MA-1 and PC-ALM/FHLC remain independent tracks. FOLD shared-core/compression
architecture is not replaced by this bounded input adapter. No fixed remaining-C count.
