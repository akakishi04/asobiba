# FOLD Experiment Ledger and Handoff

> Current authoritative state. Historical verdicts, code and preregistrations remain immutable.

## Environment / protocol

Repository `akakishi04/asobiba`; branch `feat/sft-target-loss`; local `M:\asobiba\fold`.
Python3.13.15/PyTorch2.10.0+cu130/CUDA13.0/RTX4070 Ti SUPER; `.venv-py31315\Scripts\python.exe`.
Protected C37 `runs/chatgpt-last-result.json`: `FD4A8DA897BDAEA9D103A252E30212C7FF842D23300D7C837333E146DEE51931`.
Protected fixture `runs/fixtures/v05-c-composition-20260921.pt`: `A52F8209703149407580F7E2965B61B78653030EE992AF6D759865736741CA9E`.
Read `AGENTS.md`, `docs/experiment-conversation-handoff-protocol.md`, this file,
`docs/experiment-ledger-addendum-c172-c173.md`, `docs/experiment-ledger-addendum-c173-preregistration.md`,
`docs/structured-acquisition-lifecycle-v0.1.md`, `docs/structured-action-runtime-v0.1.md`,
`docs/structured-task-interface-v0.1.md`, `docs/structured-derived-result-v0.1.md`,
and `docs/gate-e-evaluation-contract-v0.1.md`.
Judge -> ledger/handoff -> next registration. Preserve valid negatives. Invalid executions
retry identical conditions. Related independent checks may be batched; do not repeat
unchanged-source diagnostics merely to rediscover an accepted gap.

## Formal state

Gate A/B PASSED; C/D PASSED within measured scope; **Gate E NOT PASSED**.
**C172 ACCEPTED PASS. C173 ACTIVE / NOT YET JUDGED. C174 NOT REGISTERED.**
C172 execution HEAD `e38ca796acd51dc54d6041ae69988f57592573e4`.
Acceptance/handoff commit `544f6adceae37481cb414f0db8abce9929ec31da` precedes C173.
Use final C173 registration HEAD as ExpectedHead. Do not rerun C172 for new code/docs.
C170/C171 remain ACCEPTED PASS; C160/C168/C169 remain ACCEPTED VALID NEGATIVE.

## Accepted history

Full earlier index remains in this handoff at C172 execution HEAD and the acceptance-only
commit, earlier handoffs and chained addenda; it is not invalidated by this active index.
C151 retains per-layout WITHIN_FACTOR20,727/20,736 and GLOBAL_CONCEPT20,736/20,736;
nine known errors, ranker tuning closed. C152-C167 component/recovery/authority/warm
claims retain measured scope; C154 caveat remains. C160 stays negative:82,944 cycles,
0 ANSWERED. C168 lower bound4/8 is structural, not model accuracy. C169 found task-input,
dispatch and output gaps. C170 PASS:809 tests,532 roundtrips,40 guards,72 features plus
binding; no learned reader. C171 PASS:845 tests,600 verifier calls,158 verified/442
rejected,0 failures,1022 rule evaluations; handwritten verifier and proof fixtures,
not learned reasoning. Known local-rule incompleteness remains explicitly documented.

## Latest accepted C172

885/885 regression PASS;197 action calls in8 groups,0 failed checks.
Groups external_grid48/local10/malformed24/stale12/pending15/proof_rejection24/
proof_budget40/fact_status24. Reservations27,internal units147,verifier calls46,
proof rules28. Statuses PENDING27/STAGED14/VERIFIED_DERIVED10/UNRESOLVED5/DENIED62/
REJECTED79. These are dependent fixture transitions, not independent task accuracy.
Actual provider calls,acquisitions,evidence writes,learned forwards,training,seeds=0.
38 input paths/30 historical pins,C37/fixture/output/tree/HEAD preserved per runner.
Full console-summary hash independently reconstructed;197-row action-results were not
uploaded or independently replayed. No user-machine regression rerun is claimed.

C172 action boundary binds named proposals to current immutable runtime state.
COMPUTE stages supplied candidates; ANSWER pays dispatch plus actual C171 rule work;
STOP closes unresolved without refund;external actions only reserve pending intent.
Digest is not authorization or concurrency. C173 adds a separate owner/lifecycle,not
retroactive transport capability to C172 or changed interpretation of its reservations.

## Latest artifact identity

C172 `runs/c172-v5e-action-runtime-dd06f1dd06d84fe8a0e215c04c76fac4/summary.json`.
SHA256 `b1698509fa5ab384b86731662092568e9348fe907ab9f4707ed0ea802709e943`.
Plan SHA256 `31a56cfab6aef948085d503d6bbbe80092bc7cbfd0b3704d11460add8c32c10c`.
`action-results.json`:197 rows,971804 bytes,
SHA256 `b9e08da4b713e4bf6859e4a3ce6f84f16a92341b06347e79e5d26ec4b5500fb7`.
Uploaded log167362 bytes,SHA256 `5d391b4c08a40e41be0cdfd2d1a5cf47953decb11dea95afcbbcd650c8eaa708`.
C171 `runs/c171-v5e-derived-result-23bd4bdf2838457f9a156bbb902b2b3c/summary.json`,
SHA256 `4509a1e9fa5bf2072af18ac633fd2ee95ba2da35af4ab0dc3bc661437fc9853c`.
Keep all earlier proof/input/trace artifacts. Earlier identities remain in addenda.

## Active C173 — bounded local acquisition lifecycle

`C173-v5e-bounded-acquisition-lifecycle`; `V5-E-BOUNDED-ACQUISITION-LIFECYCLE`.
New opt-in AcquisitionOwner adopts C172 states,reauthorizes pending dispatch,executes a
registered bounded FileSnapshotProvider,validates response identity and source-document
witness,then updates only the requested usable Fact in TaskView. No production wiring.
All C170/C171/C172 and earlier code/checkpoints/criteria remain unchanged.

122 scenarios in8 groups:success12/delivery_faults60/pre_dispatch27/source_guards8/
staged6/reentrant3/retry_budget3/replay_delivery3. Fixed expected counts:236 action calls,
143 dispatch calls(includes3 nested denied),122 reservations,417 internal units,98 provider
callbacks,95 file read attempts,24 fact publications,12 supplied-proof answers,18 verifier
calls,36 proof rules. Three old-delivery callbacks perform no new read. No outcome ratio
is model accuracy. Keep each scenario's checks and transitions;no mid-batch repairs.

Local source max4096 bytes/4 records;oversize detection reads4097. Runtime-private witness
must match pinned hash and selected payload,not merely a claimed source ID. Receipt strips
raw source data;unchosen values do not enter C170 policy facts. Snapshot epoch fixed;fact
and state digests update. Core EvidenceState/durable writes0. Failed completion retains old
facts,clears pending/staged work and never refunds reservation. Early wrong/no-pending or
insufficient-internal-budget rejection preserves legitimate state. See full cost contract.

OBSERVE/ASK_USER are LOCAL-FILE SIMULATIONS,not Vision or human messaging. Scripted named
proposals and visible-only handwritten proof fixtures;0 learned forwards/training/seeds/
network calls. Single-owner synchronous/reentrancy guard,not concurrent or crash-durable
execution. Trusted refresh is a scheduler-side fault-control hook,not policy data editing.

Pin C172 parent and36 historical source/doc entries;own6 files checked at registration HEAD.
New UUID plan,10 fixed source files,122-row acquisition-results and full summary. Preserve
old outputs/C37/composition fixture. File hashes/count checks are not independent replay.
PASS means all registered lifecycle checks;finite wrong behavior is VALID NEGATIVE;
source/setup/unexpected/incomplete/protection failures are INVALID and retry unchanged.

**921 focused tests expected=885+36**,57 modules,once. Reviewer compiled3 new Python files
and passed36 actual-module tests with Git-blob-identical C170/C171/C172 dependencies;no
substitutes. Four embedded runner Python commands parsed. Full921,Windows PowerShell,
source guards and complete artifact-backed122-scenario CLI unexecuted by reviewer.
No formal C173 result yet. New code/test/runner blobs match reviewed local files.
Runner `tools/run_c173.ps1 -C172Summary ... -ExpectedHead ...`;CPU batch.
**Judge C173/update ledger before C174 or another implementation/learner experiment.**

## Gate / independent limits

Nine-family Gate E scope unchanged; final numerical registration remains BLOCKED pending
candidate/splits/baselines/margins/full evaluation definitions. Learned task control and
proof generation are not supplied by contract correctness. No general language,Vision,
durable memory,long-context reuse,OS isolation or production rollout follows.
Multi-Axis/MA-1 and PC-ALM/FHLC remain separate; shared-core/compression is not replaced.
Operational VRAM/latency/artifact size remain priorities,not measured model capabilities here.
