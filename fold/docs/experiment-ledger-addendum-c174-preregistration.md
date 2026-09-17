# C174 preregistration — Learned necessity with paired syntax ablation

Registered 2026-09-17 JST after C173 acceptance/handoff commit
`f23fcc4ab9ee7548ad8b18e0f2d450b7612cadc6`.
Read `learned-necessity-probe-v0.1.md`,C170 input contract and the unchanged
`gate-e-evaluation-contract-v0.1.md`.

## Formal state and single question

**C174 ACTIVE / NOT YET JUDGED.**
`C174-v5e-learned-necessity-syntax-ablation`; `V5-E-LEARNED-NECESSITY-SYNTAX-ABLATION`.
Branch `feat/sft-target-loss`;use final registration HEAD as ExpectedHead.
C173/C172/C171/C170 remain ACCEPTED PASS;C160/C168/C169 remain ACCEPTED VALID NEGATIVE.
**Gate E NOT PASSED. C175 NOT REGISTERED.**

Does a small learned reader of the structured task input discriminate logically
sufficient evidence from additional-observation need on held-out function groups better
than its paired syntax-blind control and a transparent missing-fact rule?
This is the first learned probe for this new structured boundary,not the first learned
component in FOLD,and not a FOLD shared-core benchmark or a live action experiment.

Changed scientific variable:visible ordered syntax versus zeroed syntax fields4..45.
Hold architecture,train labels/rows,per-seed initialization,minibatches,optimizer,number
of updates,features outside the AST and evaluator fixed. No old checkpoint reuse or
changes to C170-C173 or earlier code/data/results. No proof solver/guard in predictions.
No actual acquisition,tool execution,network,evidence write or production wiring.

## Frozen dataset and split

All5 ordered four-leaf tree shapes x2^3 AND/OR operators x2^4 leaf negations =640 templates.
A/B/C/D each appear once;each template has all3^4 visible assignments =51840 total rows.
Labels0 SUFFICIENT /1 NEEDS_OBSERVATION are completion-enumeration teachers,not hidden
world values or automatically supplied dependency features. Input packets are delivered
and captured before their labels are calculated. Formula truth/group metadata is excluded
from the72 numeric model inputs and opaque binding fields.

Grouping merges complete Boolean functions under the24 variable permutations AND whole-
output complementation. The latter prevents identical necessity targets crossing folds.
All equivalent templates and all their partial assignments stay in one fold. The two
four-variable C170/C171 template groups are forced to TRAIN. Other groups are partitioned
by the literal salted hash rule in design/code,without label-balancing or resampling.

| Split | Function groups | Templates | Rows | SUFFICIENT | NEEDS_OBSERVATION |
|---|---:|---:|---:|---:|---:|
| TRAIN |36|524|42444|27816|14628|
| PILOT_EVAL |4|116|9396|6744|2652|

40 necessity-equivalence groups total;no group intersection.9396 rows are NOT9396 independent semantic
replicates. This is a development pilot;the later nine-family Gate E holdout is neither
fixed nor evaluated. Repeated/signed/reordered syntax is not falsely counted as new tasks.
Dataset canonical metadata + little-endian raw feature/label/index/split/group array hash:
`eaae9aef5f64a204fe4d249bccbd437cd42f90172cd6f0eeb91be834b9450c65`.
Schema field72,exact C170 decoder;no mean pooling,learned tokenizer or symbolic preprocessing.

## Model / training / timing of evaluation

Three paired initialization seeds:174001,174002,174003. Six separately trained models.
MLP72->128 ReLU->128 ReLU->2;26114 parameters each,CPU float32,2 threads,deterministic algorithms.
TASK_VISIBLE versus SYNTAX_ABLATED. Fixed schema scaling is identical in both arms.
Adam lr0.001,betas(0.9,0.999),eps1e-8,weight_decay0,amsgradFalse,foreachFalse;
unweighted cross entropy;2000 updates per model;batch256 sampled with replacement.
Minibatch RNG seed is initialization seed+1000000 and is private to each fit.
No evaluation input/label/metric enters fit;no early stopping,selection,search or retry
for improved quality. Final2000-update checkpoints only. All6 are saved and reloaded
before the first pilot score. Initial-parameter and minibatch-schedule hashes must match
within each pair. Historical checkpoints are never loaded or altered.

Registered totals:12000 optimizer/training-forward calls,3072000 train examples drawn;
56376 pilot predictions(6x9396);254664 training-resubstitution predictions(6x42444).
Postfit inference batching1024 produces312 forward calls:60 pilot +252 resubstitution.
Train-resubstitution results diagnose fitting only and never decide the verdict.
No candidate runtime actions/acquisitions/proof-checker calls/evidence writes/network calls.
Regression activity and its tiny toy training checks are outside these benchmark counts.

## Endpoints and exact decision rule

Primary endpoint:macro mean of balanced accuracy across the4 PILOT_EVAL function groups.
Also save per-group/aggregate confusion,accuracy,SUFFICIENT recall,NEEDS_OBSERVATION recall,
raw logits/predictions,train loss samples,train-resubstitution scores and checkpoint hashes.
Controls:paired ablation;missing-fact rule(any missing =>1);always0 and always1.
No labels,truth rules,proof results or action masks can repair a raw argmax prediction.

**PASS:** all6 fixed fits and data/source/output checks complete;for EACH of3 seeds,
TASK_VISIBLE primary endpoint is strictly greater than BOTH its paired SYNTAX_ABLATED
endpoint and the missing-fact-rule endpoint,and both aggregate class recalls are>0.5.
No averaging across seeds to hide a failed seed. Ties fail. This is a directional pilot
criterion,not a statistical-significance claim,final Gate margin or practical-use guarantee.

**ACCEPTED VALID NEGATIVE / FAIL:** valid complete training/evaluation misses any scientific
criterion. Save every seed/arm/group/error and do not change hidden width,training steps,
learning rate,seeds,split,cases or threshold to seek a PASS under the same number.
A finite negative exits0 so its report/postchecks can be collected. No automatic C175.

**INVALID / RETRY C174:** parent/source/hash/manifest/data drift,paired initialization or
minibatch mismatch,malformed setup,nonfinite numerical state,unexpected exception,
incomplete workload or outer protection failure. Save completed fits/pairs in invalid.json;
restore validity and retry the same specification. Do not change scientific settings to
resolve an invalid run;deterministic persistent numerical failure requires explicit review.

Plan manifest SHA256:
`6b06991409954a6a97340a2fd93dcf22bd4622e9b90e9968a670f337c830f1a4`.

## Artifact / source identity

Parent C173 `runs/c173-v5e-acquisition-lifecycle-4507b2745ec8499982006b960a469bd3/summary.json`.
SHA256 `3c4759bbc14b4ab9849d482d2f330cbf1038c1473e2deab2aaf40f9637e635aa`.
Execution HEAD `2cc2b1f40e9c7638e4bc0f72c07feb85d95a9c26`.
Pin parent's36 historical entries plus C173's6 own files;check own6 new source/doc files
against registration HEAD. Exact bytes or LF/CRLF-equivalent checkout only.
C37/composition fixture remain protected outer files. No replay of122/197/600 old records,
large-query loops or recursive old model chain. Preserve all previous outputs.

Fresh UUID directory:necessity-plan.json BEFORE training;templates-and-splits.json;
non-pickle compressed pilot-data.npz;6 final checkpoints;pilot-predictions.json;
training-predictions.npz;full summary.json. Hash,size and canonical data fingerprint
checks preserve identities. Torch checkpoints load with weights_only=True and matching
parameter fingerprints;no downloaded pretrained model. Log every500 training updates and
all3 per-seed final comparisons. Actual serialized sizes and elapsed time are reported,
not inferred from the parameter count. No GPU-memory or production-latency claim.

## Pre-publication review

Before branch publication and before any deciding training,the split audit added whole-
output complementation to grouping. Merely withholding f while training on NOT f would
not withhold its necessity mapping. The hash-partition rule was not rebalanced after the
new counts were seen;only4 evaluation groups result. Draft Git objects were not installed
as the active experiment. This review is not a post-result scope/threshold change.

## Verification / execution / stop

New module/benchmark/test compiled.32/32 new tests passed on actual code plus a byte-
identical C170 input copy(blob b874b6abf17fb938a5cc873ff2090c6493f00010),PyTorch2.10 CPU.
Those tests include4 tiny two-update fits on8 artificial numeric rows;no registered
2000-step fit or trained pilot evaluation ran before registration. Dataset/split counts
and hashes were generated to freeze the plan,not used to tune a learned result.
Three embedded runner Python commands parsed. Full953 regression,actual WindowsPowerShell,
full source/artifact-backed CLI and all6 deciding fits are NOT run by reviewer.

**953 focused tests expected=921+32**,58 modules,once.
Runner `.venv-py31315/Scripts/python.exe`;`tools/run_c174.ps1 -C173Summary ... -ExpectedHead ...`.
Progress `[C174] plan fixed`;seed/arm/step500..2000;then3 paired final metrics;RESULT/POSTCHECK.
Collect complete log even if statusFAIL and run_execution_valid=True.
**Judge C174 -> ledger/handoff -> next design. No C175 or final Gate E run before judgment.**
