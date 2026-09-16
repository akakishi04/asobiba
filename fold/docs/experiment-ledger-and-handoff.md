# FOLD Experiment Ledger and Handoff

> Current authoritative state. Historical verdicts,source code and preregistrations remain unchanged.

## Environment / protocol

Repository `akakishi04/asobiba`;branch `feat/sft-target-loss`;local `M:\asobiba\fold`.
Python3.13.15/PyTorch2.10.0+cu130/CUDA13.0/RTX4070 Ti SUPER;`.venv-py31315\Scripts\python.exe`.
Protected C37 `runs/chatgpt-last-result.json`: `FD4A8DA897BDAEA9D103A252E30212C7FF842D23300D7C837333E146DEE51931`.
Protected fixture `runs/fixtures/v05-c-composition-20260921.pt`: `A52F8209703149407580F7E2965B61B78653030EE992AF6D759865736741CA9E`.
Read `AGENTS.md`,`docs/experiment-conversation-handoff-protocol.md`,this file,
`docs/experiment-ledger-addendum-c170-c171.md`,`docs/experiment-ledger-addendum-c171-preregistration.md`,
`docs/structured-derived-result-v0.1.md`,`docs/structured-task-interface-v0.1.md`,
and `docs/gate-e-evaluation-contract-v0.1.md`.
Judge -> ledger/handoff -> next registration. Preserve valid negatives;invalid executions
retry identical registered conditions. Independent related contract checks may be batched.
Do not repeat an unchanged-source diagnostic solely to rediscover an accepted gap.

## Formal state

Gate A/B PASSED;C/D PASSED within measured scope;**Gate E NOT PASSED**.
**C170 ACCEPTED PASS. C171 ACTIVE / NOT YET JUDGED. C172 NOT REGISTERED.**
C170 execution HEAD `da09a86e25f12927a9206217b7933609c2fe1b8c`;
acceptance/handoff commit `77bebd715ae18215546c7d4e1cf5414d04f663a6` precedes C171.
Use final C171 registration HEAD as ExpectedHead. No C170 rerun for new code/docs.
C160/C168/C169 remain ACCEPTED VALID NEGATIVE;C167 retains ACCEPTED PASS.

## Accepted evidence / history

Full prior index remains in this file at `da09a86e25f12927a9206217b7933609c2fe1b8c`,
acceptance-only handoff `77bebd715ae18215546c7d4e1cf5414d04f663a6`,and chained addenda.
C151's24 heads:per-layout WITHIN_FACTOR20,727/20,736,GLOBAL_CONCEPT20,736/20,736;
nine known errors,ranker tuning closed. C152-C157 components,C158 selected-record
cycle,C159 observed emitter,C161-C166 diagnosis/recovery/authority,C167 warm path
retain separate accepted scopes. C154 classification caveat remains in its addendum.
C160 remains negative:82,944 completed cycles but0 ANSWERED. Never relabel.
C167 PASS:725 tests,165,888 cold/warm answered executions;one paid warm read/decision;
no reacquisition;known error instances36=9x2 layouts x2 conditions,not36 error types.
C168 VALID NEGATIVE:749 tests;8 extension probes collapse to1 conflicting input class;
error lower bound4/8 is structural,not measured model accuracy.
C169 VALID NEGATIVE:773 tests;6 sections,GAP3,boundaries3,finite violations0. D1 lacks
task route;D2 four-channel mean;D3 unresolved reasons remain runtime-side but collapse
in learned input;D4 authority intact;D5 missing selected-cycle handlers1/3/4;D6 observed-
only output. Scripted fixtures are not learned performance.

**C170 PASS:809/809 tests;532/532 deliveries/roundtrips;0 failures.**
8 necessity development cases ->4 distinct numeric classes,0 conflicts/error lower bound;
252 template assignments,16 status views,256 distinct resource views;40/40 malformed
controls rejected.72 integer features plus opaque binding sidecar. No solver,learned
policy,training,seeds,acquisition,derived proof or action execution in C170.
26 input paths/18 historical pins and outer protections preserved per runner. Reviewer
reconstructed complete report hash and audited metrics/controls/necessity rows;the
separate532-packet artifact was not independently read from the user's machine.

## Current artifacts

C170 `runs/c170-v5e-structured-task-input-e999793ff0314b959994ea3ed308aa5e/summary.json`.
SHA256 `a1858cd65a56b5cad09b1e339500f7f8a9011c4f1de721300c3a77ee11f1183e`.
Plan `a2321edf6689daf1659469dc46808f5f77922a5c0c21c999fe8da836219556ec`.
Captures `policy-inputs.json`,532 rows/687409 bytes,
SHA256 `67aece55863f079d3e38e691519bb1dee8c86b1cefab71720f2a2cddacd02345`.
Uploaded log160897 bytes,SHA256 `cad4ee19eafa563a3226f4fdb479dadb33ea2a3cbb246bc57884e9d062f78eb7`.
C169 `runs/c169-v5e-interface-batch-1aea40532e3f4a068bbea6603ebf74e6/summary.json`,
SHA256 `1a509646a01c26306f6a41b0dfaca968be39500d12e21bef7d04b98b82fd2ae6`.
C168/C167/earlier identities remain in prior handoffs/addenda. Preserve all outputs.

## Active C171 — bounded derived result contract

`C171-v5e-bounded-derived-result-contract`;`V5-E-BOUNDED-DERIVED-RESULT-CONTRACT`.
Opt-in `fold_lm/v05/structured_derived_result.py` validates explicit proposed proofs against
trusted current TaskView. Request/scope/expression/evidence digest,time/revision binding;
OBSERVED-only exact supports;max7 local proof steps,ordered direct-child premises.
Result VERIFIED_DERIVED or REJECTED;rejection has no value/support/proof and never repairs
a candidate. No missing B observation is written. C159 and C170 are unchanged.

One batch:600 checks =504 reference claims(252 existing development views x0/1) +48 malformed
+14 unusable support +16 changed-current-view bindings +8 resource-only views +8 capacities
+2 declared rule-scope limitations. Symbolic test proof generator is benchmark-only;
independent exhaustive evaluator scores proposed conclusions. Neither is learned reasoning.
All finite failures collected;source/setup/incomplete/outer protection failures INVALID.
PASS requires zero registered check failures and no reference false accept/reject. A valid
negative is retained unchanged. Full Gate E is not passed by this contract.

The local rules do not prove A OR NOT A/A AND NOT A with A unknown;the2 scope controls
retain rejection despite semantic entailment. Rejected proof is not logical impossibility.
No claim of complete Boolean reasoning. Future candidate must generate its own proof;
common guard must not mask pre-guard errors or supply solutions to the learner.
Trusted status/support authenticity,concurrency,actual action dispatch and runtime budget
debit are not implemented by this read-only checker. Resource-only changes preserve
static proof validity without authorizing any acquisition. Rule counts exclude other
validation/hash work and do not imply free compute.

Pinned C170 parent and24 historical source/doc entries;own6 files checked at registration
HEAD. No recursive old trace/532-packet replay. New UUID plan/proof-results/summary artifacts.
Preserve C37/fixture and all historical results. Python/runner guards source/input/output/tree/HEAD.
**845 focused tests expected=809+36**,55 modules,once.36 actual new-module unit tests passed;
exact C170 input module copy matches its Git blob;three new Python files compiled.
Full845,WindowsPowerShell,artifact-backed600-case CLI unexecuted by reviewer. No formal
C171 deciding result yet. Uploaded code/test/runner blobs match locally reviewed files.
Runner `tools/run_c171.ps1 -C170Summary ... -ExpectedHead ...`;CPU benchmark.
Return full log including valid FAIL. **Judge C171 and update ledger before C172.**

## Gate / independent limits

Finite nine-family Gate E contract unchanged;final numerical registration remains BLOCKED
pending candidate/split/baseline/threshold/output completeness. No general language,Vision,
long-context reuse,durable memory or production rollout. Multi-Axis/MA-1 and PC-ALM/FHLC
remain independent. Shared-core/compression architecture is not replaced. Operational
VRAM,latency and artifact size remain priorities,not measured model capabilities here.
