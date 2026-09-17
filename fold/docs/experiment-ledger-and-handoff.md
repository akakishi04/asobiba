# FOLD Experiment Ledger and Handoff

> Current authoritative state. Historical verdicts, code and preregistrations remain immutable.

## Environment / protocol

Repository `akakishi04/asobiba`; branch `feat/sft-target-loss`; local `M:\asobiba\fold`.
Python3.13.15/PyTorch2.10.0+cu130/CUDA13.0/RTX4070 Ti SUPER; `.venv-py31315\Scripts\python.exe`.
Protected C37 `runs/chatgpt-last-result.json`: `FD4A8DA897BDAEA9D103A252E30212C7FF842D23300D7C837333E146DEE51931`.
Protected fixture `runs/fixtures/v05-c-composition-20260921.pt`: `A52F8209703149407580F7E2965B61B78653030EE992AF6D759865736741CA9E`.
Read `AGENTS.md`, `docs/experiment-conversation-handoff-protocol.md`, this file,
`docs/experiment-ledger-addendum-c171-c172.md`, `docs/experiment-ledger-addendum-c172-preregistration.md`,
`docs/structured-action-runtime-v0.1.md`, `docs/structured-task-interface-v0.1.md`,
`docs/structured-derived-result-v0.1.md`, and `docs/gate-e-evaluation-contract-v0.1.md`.
Judge -> ledger/handoff -> next registration. Preserve valid negatives. Invalid execution
retries identical registered conditions. Related independent contract checks may be batched.
Do not repeat unchanged-source diagnostics merely to rediscover accepted gaps.

## Formal state

Gate A/B PASSED; C/D PASSED within measured scope; **Gate E NOT PASSED**.
**C171 ACCEPTED PASS. C172 ACTIVE / NOT YET JUDGED. C173 NOT REGISTERED.**
C171 execution HEAD `42bc2b83269a1279e50d51156de11b9d720b17c0`.
C171 acceptance/handoff commit `3b091947451df19fb17474c490d9921916a17bbe` precedes C172.
Use the final C172 registration commit as ExpectedHead. Do not rerun C171 for new docs/code.
C170 remains ACCEPTED PASS; C160/C168/C169 remain ACCEPTED VALID NEGATIVE.

## Accepted history

Detailed prior evidence remains in the handoff at C171 execution HEAD and the C171
acceptance-only commit, plus chained addenda. C151 retains WITHIN_FACTOR20,727/20,736
and GLOBAL_CONCEPT20,736/20,736 per layout; nine known errors and ranker tuning closed.
C152-C167 component/recovery/permission/budget/warm-reference claims retain measured
scopes; C154 caveat remains. C160 stays negative:82,944 cycles,0 ANSWERED. C168 lower
bound4/8 is structural,not model accuracy. C169 found task-input/dispatch/output gaps.
C170 PASS:809 tests;532 roundtrips;40 malformed controls;72 features+binding;4 necessity
classes/0 conflicts;256 resource classes. No learned reader or authenticated live facts.

**C171 PASS:845/845 tests;600 verifier calls;158 verified,442 rejected;0 failed checks.**
Groups reference504/malformed48/unusable14/rebound16/resources8/capacity8/rule_scope2.
Reference false accepts/rejects0;1022 evaluated proof rules.32 declared input paths and24
historical pins plus C37/fixture/output/tree/HEAD protections pass per runner.
No learned forwards/real adapter/evidence writes/training/seeds in the benchmark.
Verifier/proof fixtures are hand-written. Local rules lack case split; expected scope
rejections are not impossibility. Accepted fraction158/600 is not model accuracy.

## C171 evidence identity

Report `runs/c171-v5e-derived-result-23bd4bdf2838457f9a156bbb902b2b3c/summary.json`.
SHA256 `4509a1e9fa5bf2072af18ac633fd2ee95ba2da35af4ab0dc3bc661437fc9853c`.
Plan SHA256 `0b190e7afb34326969245c7721a84076624bfef72ef7d935095ec8d3080bfa86`.
`proof-results.json`:600 rows,2106641 bytes,SHA256
`745442826639d147e06ff7d5cb098d1f7e59c8c6767865a766f1e3d5232aca95`.
Uploaded log160245 bytes,SHA256 `fd52df05aa1086ed99745380d9a64c70a51784b8db1cf38bc06a86c7d207af6e`.
Reviewer independently reconstructed the complete console-summary hash and checked
summary/source/preregistration consistency. Separate600-row records were not uploaded;
no independent user-side row replay or845-test rerun is claimed. Preserve all artifacts.
C170 parent SHA256 `a1858cd65a56b5cad09b1e339500f7f8a9011c4f1de721300c3a77ee11f1183e`.
Earlier artifact paths/hashes remain in historical handoffs/addenda.

## Active C172 — typed action runtime boundary

`C172-v5e-typed-action-runtime-boundary`; `V5-E-TYPED-ACTION-RUNTIME-BOUNDARY`.
New opt-in structured_action_runtime adds immutable owner-side runtime state and named,
current-digest-bound ActionProposal. No legacy-index adaptation or old checkpoint reuse.
COMPUTE stages an unverified supplied proof;not a learned/symbolic answer computation.
ANSWER uses unchanged C171 verifier with actual bounded rule-work debit. STOP returns
unresolved,clears local pending/staged state,no reservation refund,and works at0 budget.
RETRIEVE/OBSERVE/ASK_USER check authority and reserve PENDING intent only;no provider
transport,response,admission,observation or user messaging. Future transport must recheck
current authority and match outstanding intent. Pending blocks additional non-STOP work.

197 scripted transitions in8 groups:external_grid48/local10/malformed24/stale12/pending15/
proof_rejection24/proof_budget40/fact_status24. Required27 reservations,147 internal units,
46 verifier calls,28 rule evaluations,0 failed checks. These are dependent fixture steps,
not197 independent questions. Real provider/acquisition/evidence-write/learned-forward/
training/fresh-seed counts0. No deciding C172 run yet.

Malformed/stale/closed/zero-budget rejections return unchanged state;other well-formed
non-STOP attempts charge1 internal unit including denial. ANSWER adds checked proof steps.
The trusted caller must adopt returned state;digest is not authorization,signature,CAS
or protection against concurrent reuse of an old snapshot. Cost units exclude Python
hash/validation overhead and neural inference. Observed facts never change here.

C171 input/verifier/historical runtime,checkpoints and Gate E scope remain unchanged.
Pin accepted C171 summary and30 historical source/doc entries;own6 source/doc files
checked at registration HEAD. C37/fixture outer protection;no recursive old trace replay.
Fresh UUID action-runtime-plan.json/action-results.json/summary.json with full197 records.
PASS requires exact counts and0 failures;finite mismatches are VALID NEGATIVE;source/
setup/nonfinite/unexpected exception/incomplete/outer protection failures retry same C172.

Files:fold_lm/v05/structured_action_runtime.py;fold_lm/v05_benchmarks/gate_e_c172_action_runtime.py;
tests_lm/test_v05_c172_action_runtime.py;tools/run_c172.ps1;two current design/preregistration docs.
**885 focused tests expected=845+40**,56 modules,once. Reviewer passed40 actual-module
unit tests with blob-identical C170/C171 copies and compiled3 new Python files. Four
embedded Python commands parsed;PowerShell itself,full885,source guards and formal197-
case artifact-backed batch unexecuted by reviewer. No model performance claim.
Runner `tools/run_c172.ps1 -C171Summary ... -ExpectedHead ...`;CPU diagnostic.
Return full log even for valid FAIL. **Judge C172/update ledger before C173.**

## Gate / independent limits

Finite nine-family Gate E contract unchanged; final numerical evaluation remains BLOCKED
pending candidate/splits/baselines/margins/full output and execution definitions. Real
acquisition/replies/admission and learned task control remain separate work. No general
language,Vision,durable memory,long-context reuse or production rollout follows.
Multi-Axis/MA-1 and PC-ALM/FHLC are separate tracks. Shared-core/compression is not replaced.
Operational VRAM/latency/artifact size remain priorities,not capabilities measured here.
