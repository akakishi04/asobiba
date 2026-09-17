# Learned necessity probe v0.1

2026-09-17 JST. V5-E development pilot after accepted C173.
This is a small diagnostic reader, NOT the shared FOLD core, a replacement architecture,
a production policy, a proof generator or the final nine-family Gate E evaluation.
Historical C170 input and C171-C173 proof/action/acquisition code remain unchanged.

## One missing ability, isolated

C173 completed the registered scripted acquisition lifecycle. It did not learn when
acquisition is needed. The next comparison holds data, initialization, optimizer,
architecture and workload fixed while withholding only the visible expression from
one arm. The question is whether a learned reader uses that expression to distinguish:

- SUFFICIENT: every completion consistent with visible observed facts has the same result.
- NEEDS_OBSERVATION: both Boolean results are possible under those completions.

These names are NOT ANSWER/RETRIEVE runtime actions. SUFFICIENT does not assert that a
limited proof generator has found a proof. NEEDS_OBSERVATION does not select a specific
fact or tool, quantify optimal information gain, or grant permission. No action is sent.

## Candidate and matched control

`structured_necessity_probe.py` contains an opt-in MLP72->128->128->2, ReLU after each
hidden layer,26114 independently trained float32 scalars. No shared basis/compression
or frozen C157 checkpoint is used;do not attribute this probe's success/failure to the
full FOLD architecture. It tests learnability of the task-facing input boundary.

TASK_VISIBLE uses all72 canonical C170 integer fields after fixed elementwise scaling.
SYNTAX_ABLATED zeros only node fields4..45 after identical scaling. Fact views and runtime
fields are identical. Counts are constant7 nodes/4 facts in this pilot. Binding strings,
truth tables,semantic group IDs,expected labels and proof outputs never enter inference.
The model only receives an N-by72 tensor;no symbolic solver or output mask follows it.

Both arms start from deep copies of the same initial model per seed. The two optimizers
use the same minibatch-index schedule, train rows, labels, unweighted cross entropy,
Adam settings and2000 updates. The ablated reader still has the same26114 parameters;
its zeroed-input connections naturally carry no task signal. This is deliberate input
ablation, not a claim that effective feature information is equal.

CPU float32,2 threads,deterministic PyTorch algorithms;seeds174001/174002/174003.
Adam lr0.001,betas0.9/0.999,eps1e-8,weight_decay0,amsgradFalse,foreachFalse.
Batch256 sampled with replacement by a private CPU generator seeded with seed+1000000.
No validation-based checkpoint choice,early stopping,hyperparameter search or warm start.
All six final checkpoints are written and safely reloaded before any pilot evaluation.

## Data / grouping / separation

640 syntactic templates:all5 ordered four-leaf binary tree shapes x8 AND/OR assignments
x16 leaf-negation masks. A/B/C/D each occur once,in that leaf order. Each template has
all81 UNOBSERVED/observed0/observed1 fact assignments:51840 rows in total. Only those two
read statuses occur here;noise/stale/conflict/resource-denial tasks belong to later work.
The declared current resources are identical and permit enough acquisition;no hidden
world value is supplied. Labels enumerate all possible completions,not the current secret bit.

Before labels reach training,actual C170 deliver/strict decode produces canonical numeric
features. Metadata and labels are distinct arrays. Training receives only its selected
feature rows and teacher labels. `fit` has no evaluation-data or evaluator interface.
`predict` has no labels/semantic checker/hidden state interface.

Split by necessity-equivalence:take the lexicographically smallest16-output truth table
over24 variable permutations AND whole-output complementation. A formula and its whole
negation have identical necessity labels and therefore must not cross folds. Input-sign
flips alone are not declared equivalence. Keep all
partial assignments and syntax variants of a group together. No hidden-completion sampling
is used;completions only define evaluator labels. Duplicate syntax/semantics is not
counted as independent evidence;report per-group and macro-group scores.

The two four-variable C170/C171 development-template groups are forced into TRAIN.
All other groups use SHA256('C174:function-permutation-split:v1|'+group),first8 bytes as
big-endian integer,mod5==0 -> PILOT_EVAL,else TRAIN. Do not rebalance after seeing counts.
The frozen result is36 training groups/524 templates/42444 rows and4 evaluation groups/
116 templates/9396 rows. This is a public,finite development-pilot holdout,not the final
Gate E holdout. Generalization beyond four held-out necessity-equivalence groups is not established.

## Metrics and stopping

Raw argmax0/1 is scored before any runtime or proof guard. Record confusion matrices,
class recalls,accuracy,balanced accuracy and per-semantic-group balanced accuracy.
The primary pilot endpoint is the unweighted mean of balanced accuracy over the4 eval
groups. This avoids allowing frequent equivalent templates to dominate that endpoint.

Controls:the matched syntax-ablated learned reader, a rule predicting NEEDS_OBSERVATION
whenever ANY of the four facts is unobserved, and both constant-class controls. The rule
is not a learned policy and neither it nor the constants receives formula-derived labels.
These are offline classifier controls,NOT substitutes for Gate E's required episode-level
internal-only and fixed-acquisition baselines. Those final comparisons remain unmeasured.

Pilot PASS requires each of3 seeds to beat BOTH the matched ablation and missing-fact
rule on the primary endpoint,with both aggregate class recalls strictly greater than0.5.
Ties fail. This is a fixed directional pilot question,not an arbitrary97/99% Gate threshold
and not a significance test. No p-value,independent-row sample-size or confidence guarantee
is claimed. A small positive difference must be reported at its actual size,not overstated.
Report final-training resubstitution metrics separately to diagnose fit versus pilot-transfer
failure. They are not holdout evidence and do not affect checkpoint selection or PASS.

A finite valid negative is retained without changing seeds,training,splits,capacity or
thresholds. Inspect its per-group errors and training/evaluation contrast before designing
any intervention. Existing contract results are not relabeled. No implicit live integration
or final Gate E promotion follows even from a PASS.
