# FOLD Experiment Ledger and Handoff

> Current authoritative state. Historical verdicts, code and preregistrations remain immutable.

## Environment / protocol

Repository `akakishi04/asobiba`;branch `feat/sft-target-loss`;local `M:\asobiba\fold`.
Python3.13.15/PyTorch2.10.0+cu130/CUDA13.0/RTX4070 Ti SUPER;`.venv-py31315\Scripts\python.exe`.
Protected C37 `runs/chatgpt-last-result.json`:
`FD4A8DA897BDAEA9D103A252E30212C7FF842D23300D7C837333E146DEE51931`.
Protected fixture `runs/fixtures/v05-c-composition-20260921.pt`:
`A52F8209703149407580F7E2965B61B78653030EE992AF6D759865736741CA9E`.
Read `AGENTS.md`,`docs/experiment-conversation-handoff-protocol.md`,this file,
`docs/experiment-ledger-addendum-c173-c174.md`,**`docs/experiment-ledger-addendum-c174-preregistration.md`**,
**`docs/learned-necessity-probe-v0.1.md`**,C170-C173 contracts,and
`docs/gate-e-evaluation-contract-v0.1.md`.
Judge -> ledger/handoff -> next registration. Valid negatives remain results. Invalid
executions retry identical conditions. Related independent checks may be batched.
Do not repeat unchanged-source diagnostics merely to rediscover an accepted gap.

## Formal state

Gate A/B PASSED;C/D PASSED within measured scope;**Gate E NOT PASSED**.
**C173 ACCEPTED PASS. C174 ACTIVE / NOT YET JUDGED. C175 NOT REGISTERED.**
C173 execution `2cc2b1f40e9c7638e4bc0f72c07feb85d95a9c26`.
Acceptance/handoff commit `f23fcc4ab9ee7548ad8b18e0f2d450b7612cadc6` precedes C174.
Use final C174 registration HEAD as ExpectedHead. No C173 rerun for new docs/code.
C170/C171/C172 remain ACCEPTED PASS;C160/C168/C169 remain ACCEPTED VALID NEGATIVE.

## Accepted history

Full prior index remains in this handoff at C173 execution HEAD,the C173 acceptance-only
commit,and earlier handoffs/chained addenda. C151 per-layout WITHIN_FACTOR20,727/20,736
and GLOBAL_CONCEPT20,736/20,736;nine known errors,ranker tuning closed. C152-C167 component,
recovery,authority and warm claims retain scopes;C154 caveat remains. C160 remains
negative:82,944 cycles but0 ANSWERED. C168's4/8 bound is input collision,not model accuracy.
C169's3 interface gaps/3 boundaries remain accepted negative history;later input/action/
output implementations do not change that old snapshot's readiness verdict.
C170 PASS:809 tests,532 deliveries,40 guards,72 integers+binding;not learned reading.
C171 PASS:845 tests,600 checks,158 verified/442 rejected,0 failures;handwritten proof
checker/fixtures,documented local-rule incompleteness. C172 PASS:885 tests,197 action
calls,27 reservations,147 internal units,46 verifier calls,28 rules;reservation is not fetch.

## Latest accepted C173

921/921 tests;122 scenarios in8 groups,0 failed checks.236 action calls,143 dispatch
calls(including3 nested denied),122 reservations,417 internal units,98 provider callbacks,
95 actual file-read attempts,26434 bytes read,176 successfully validated source records,
24 fact publications,12 supplied-proof derived answers,18 verifier calls,36 proof rules.
Groups:success12/delivery_faults60/pre_dispatch27/source_guards8/staged6/reentrant3/
retry_budget3/replay_delivery3. Three old-response callbacks perform no new read.
0 learned forwards/training/fresh seeds/network/core EvidenceState writes.
54 input paths,36 historical pins,C37/fixture/output/tree/HEAD preserved per runner.
Full console-summary hash independently reconstructed;122-row detail and10 sources
not independently read/replayed on the user's machine. No921-test rerun by reviewer.

Scoped path:reserved intent -> reauthorization -> bounded actual local file read ->
source-witness/binding validation -> selected TaskView fact -> supplied proof -> C171.
Fixed epoch;private witness;no unchosen fact publication. OBSERVE/ASK_USER simulate files,
not Vision/human messages. Single owner is not durable/concurrent receipt ownership.
AcquisitionOwner is opt-in,not production wiring;hash identity does not prove world truth.

## Current artifacts

C173 `runs/c173-v5e-acquisition-lifecycle-4507b2745ec8499982006b960a469bd3/summary.json`.
SHA256 `3c4759bbc14b4ab9849d482d2f330cbf1038c1473e2deab2aaf40f9637e635aa`.
Plan `4a604a5c461f60eb04d881a63849248f9c873915fdc225ddc9b560a26c68b67b`.
`acquisition-results.json`:122 rows,2063202 bytes,
SHA256 `254eba8b6d90fdbd096adae1938f018d703850be27b9354ff157f6adaee538c2`.
Uploaded log176824 bytes,SHA256 `03a707019601259609a5fb288c4789d03bcb800be9fde71d4bfab175a05afc73`.
C172 `runs/c172-v5e-action-runtime-dd06f1dd06d84fe8a0e215c04c76fac4/summary.json`,
SHA256 `b1698509fa5ab384b86731662092568e9348fe907ab9f4707ed0ea802709e943`.
Keep all prior proof/input/trace/source artifacts;identities remain in earlier addenda.

## Active C174 — offline learned necessity pilot

`C174-v5e-learned-necessity-syntax-ablation`;`V5-E-LEARNED-NECESSITY-SYNTAX-ABLATION`.
Opt-in MLP72->128->128->2,26114 parameters,not the FOLD shared core or a new main architecture.
TASK_VISIBLE versus same-model SYNTAX_ABLATED(node fields4..45 zero). Fixed C170 task input,
identical facts/resources,paired initialization and minibatch schedules. Raw binary
SUFFICIENT/NEEDS_OBSERVATION classification;not ANSWER/RETRIEVE execution. No inference
solver,proof checker,teacher dependency,hidden values,semantic group IDs or action masks.

640 ordered four-variable read-once templates x81 partial assignments=51840 rows.
Group equal Boolean functions up to variable permutation AND whole-output complement;
no group crosses train/eval. Formula and NOT formula have identical necessity labels.
C170/C171's two4-variable development-template groups forced to TRAIN;other groups use
fixed salted hash partition without post-count balancing. TRAIN36 groups/524 templates/
42444 rows(27816 sufficient,14628 needs);PILOT_EVAL4 groups/116 templates/9396 rows
(6744 sufficient,2652 needs). 40 necessity-equivalence groups total. Pilot development
holdout,NOT final nine-family Gate E data;9396 rows are not9396 independent replicates.
Only4 held-out groups limits interpretation;no statistical significance claim.

Seeds174001/174002/174003,2 arms each;6 new models. CPU float32,2 threads,deterministic;
2000 Adam updates/model,batch256,lr0.001,unweighted CE,final checkpoint only.12000 updates,
3072000 sampled train examples. Save all6 final checkpoints before any pilot evaluation.
56376 pilot predictions;254664 train-resubstitution predictions,separately reported;
312 postfit inference batches. No actual acquisition,evidence write,network or live action.

Primary endpoint=macro mean balanced accuracy over4 eval groups. PASS requires EACH seed's
full input to strictly exceed BOTH its paired ablation and any-missing=>needs rule,and
both aggregate class recalls>0.5. Ties/any failed seed => VALID NEGATIVE if execution valid.
Not a significance test,final Gate margin,heldout language claim or practical-use threshold.
Final-training fit is diagnostic,not selection. These classifier controls do not replace
Gate E's episode-level internal-only/fixed-acquisition comparisons.

Canonical data hash `eaae9aef5f64a204fe4d249bccbd437cd42f90172cd6f0eeb91be834b9450c65`.
Manifest hash `6b06991409954a6a97340a2fd93dcf22bd4622e9b90e9968a670f337c830f1a4`.
Pin C173 parent and42 historical source/doc files,own6 files at registration HEAD;C37 and
fixture outer protection. New UUID plan/templates/dataNPZ/6 checkpoints/pilot predictions/
training predictions/full summary;hash/size protection is not independent semantic replay.
Paired initialization/schedule mismatch,source/data/hash drift,incomplete/nonfinite or
outer protection failure is INVALID;retry unchanged. No retuning to turn a negative PASS.

**953 focused tests expected=921+32**,58 modules,once.32 actual-code unit tests passed with
blob-identical C170 dependency;includes4 tiny2-update fits on8 artificial numeric rows.
No registered2000-step model fit or pilot prediction was executed before registration.
Data counts/hash generation froze the manifest without choosing on learned outcomes.
Pre-publication split review added complement grouping;unpublished draft Git objects
are not authoritative experiments. Three Python files compiled;3 embedded commands parsed.
Full953,WindowsPowerShell,source-guarded CLI and all6 deciding fits unexecuted by reviewer.
Runner `tools/run_c174.ps1 -C173Summary ... -ExpectedHead ...`;CPU training pilot.
**Judge C174/update ledger before C175 or final Gate E.**

## Gate / independent limits

Nine-family Gate E scope unchanged;final numerical registration remains BLOCKED pending
candidate/splits/baselines/margins/full evaluation. Necessary observation is not which
fact/tool to choose;proof generation,live learned control and other evidence families
remain separate. No language,Vision,durable memory,long-context or production rollout.
Multi-Axis/MA-1 and PC-ALM/FHLC remain separate;shared-core/compression is not replaced.
Operational VRAM/latency/artifact size remain priorities,not claims from parameter count.
