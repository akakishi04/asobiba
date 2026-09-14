# FOLD Experiment Ledger Addendum — C107 to C108

## C107 — ACCEPTED PASS

Experiment: `C107-v5e-independent-evaluator-falsification`

Accepted evidence:

- fresh seeds `20261301,20261302,20261303`;
- independent fixture forbidden canonical imports: none;
- independent/canonical label agreement `1.0`;
- key coverage complete;
- independent action accuracy minimum `1.0`;
- independent minimum six-class recall minimum `1.0`;
- independent minimum-burden rate minimum `1.0`;
- ineligible mechanism count `0`;
- action flips `0`;
- hidden-counterfactual action invariance minimum `1.0`;
- C37 and runtime fixture preserved;
- tracked tree clean.

Interpretation: a shared train/eval generator implementation bug is materially weakened as an explanation for C103-C106. Gate E remains NOT PASSED.

## C108 — ACTIVE falsification

Experiment: `C108-v5e-feature-reencoding-falsification`

Question: does the mechanism policy depend on exact numeric boolean encodings, or generalize across unseen signed codebooks preserving only `false < 0 < true`?

Training codebooks:

```text
train_a: false=-0.5, true=+0.75
train_b: false=-2.0, true=+1.25
```

Held-out OOD codebooks:

```text
ood_a: false=-3.5, true=+0.20
ood_b: false=-0.10, true=+4.0
ood_c: false=-7.0, true=+9.0
```

OOD scalar values are disjoint from all training scalar values. Base remains canonical because it is policy-irrelevant.

Prospective conditions:

```text
fresh seeds      = 20261311,20261312,20261313
train bases      = 0,1,2
validation base  = 3 only
control width    = 4
hidden width     = 8
training steps   = 900
```

Every fresh seed and every OOD codebook must satisfy:

```text
anchor action accuracy               = 1.0
anchor minimum six-class recall      = 1.0
anchor action flips                  = 0
OOD action accuracy                  = 1.0
OOD minimum six-class recall         = 1.0
OOD action flips                     = 0
OOD answerable ANSWER rate           = 1.0
OOD critical no-direct-ANSWER rate   = 1.0
OOD minimum-burden rate              = 1.0
OOD no-eligible STOP rate            = 1.0
OOD ineligible mechanism count       = 0
OOD hidden-counterfactual invariance = 1.0
```

This does not require invariance to arbitrary channel permutations or unknown semantic remappings; those would violate the input contract without an explicit schema/adapter.

A valid negative result completes C108; thresholds must not be loosened retrospectively.
