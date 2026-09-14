# FOLD Experiment Ledger Addendum — C105 to C106

## C105 — ACCEPTED PASS

Experiment: `C105-v5e-learned-acquisition-mechanism-closed-loop`

C105 evaluated the learned six-action mechanism selector as a runtime-owned fallback trajectory on unseen `base=3` with fresh seeds `20261221..23`.

Accepted results across all seeds:

- answerable ANSWER rate `1.0`;
- answerable zero-acquisition rate `1.0`;
- required scenario pass rate `1.0`;
- per-decision minimum-burden rate `1.0`;
- eventual-success ANSWER rate `1.0`;
- eventual-success final accuracy `1.0`;
- all-fail STOP_UNRESOLVED rate `1.0`;
- failed-attempt no-evidence-commit rate `1.0`;
- ineligible mechanism count `0`;
- repeat failed mechanism count `0`;
- budget violations `0`;
- ASK_USER before self-service exhaustion `0`;
- hidden-counterfactual action-trace invariance `1.0`.

Authority contract retained:

```text
model/router -> proposes mechanism
runtime      -> owns permission, outcome, failed-mechanism removal, and evidence commit
```

C105 remains synthetic. It does not establish Gate E passage or real tool/memory/user interaction quality.

## Why C106 is a falsification experiment

C104/C105 trained with all 16 eligibility masks. Therefore a remaining alternative explanation is that the router memorized the finite mask-to-action table rather than learning the compositional minimum-burden rule.

C106 stops feature expansion and directly attacks that explanation.

## C106 — active experiment

Experiment: `C106-v5e-unseen-eligibility-mask-generalization`

Single question:

> Does the learned mechanism selector generalize to eligibility-mask compositions that were never present in training?

Mask partition is fixed prospectively:

```text
training masks:   Hamming weight <= 2
OOD masks:        Hamming weight >= 3
```

This yields:

```text
train masks = 11
OOD masks   = 5
```

The two sets are disjoint and together cover all 16 masks.

Other conditions:

```text
fresh seeds      = 20261231,20261232,20261233
train bases      = 0,1,2
validation base  = 3 only
control width    = 4
hidden width     = 8
training steps   = 800
```

Two validation sets are used:

1. **Anchor validation** — unseen `base=3` with training-mask family. This must retain all six action classes.
2. **OOD composition validation** — unseen `base=3` with only never-trained masks of Hamming weight >= 3.

Prospective gate for every fresh seed:

```text
anchor action accuracy              = 1.0
anchor minimum six-class recall     = 1.0
anchor action flips                 = 0
OOD action accuracy                 = 1.0
OOD action flips                    = 0
OOD answerable ANSWER rate          = 1.0
OOD critical no-direct-ANSWER rate  = 1.0
OOD minimum-burden rate             = 1.0
OOD ineligible mechanism count      = 0
OOD hidden-counterfactual invariance= 1.0
```

C106 is intentionally a falsification/generalization test. A valid failure is useful evidence and still completes C106.

C106 does not yet test an independently implemented evaluation generator, feature re-encoding, distractor features, noisy capability state, or real mechanisms. Those remain later falsification axes.
