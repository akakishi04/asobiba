# Experiment Ledger Addendum — C110 to C111

## C110 — accepted PASS

Experiment: `C110-v5e-signed-control-canonicalization-diagnostic`

C110 replayed the accepted C108 negative result and compared the same training/architecture/codebooks against an explicit schema-aware sign canonicalizer.

Accepted findings:

- raw C108 negative reproduced: `true`;
- canonical anchor action accuracy min: `1.0`;
- canonical anchor minimum class recall min: `1.0`;
- canonical OOD action accuracy min: `1.0`;
- canonical OOD minimum class recall min: `1.0`;
- canonical OOD minimum-burden rate min: `1.0`;
- canonical OOD ineligible mechanism count sum: `0`;
- canonical OOD action flip count sum: `0`;
- all canonical validation passed.

Interpretation:

> The C108 failure is consistent with raw numeric representation sensitivity, not a failure of the registered six-action policy itself. Explicit schema-known boolean canonicalization is a supported repair hypothesis.

C110 remained diagnostic only and did not modify production runtime.

## C111 — active production integration

Experiment: `C111-v5e-production-control-canonicalization-integration`

Question:

> Does an explicit production boolean Control Representation Adapter recover the known C108 failing seed and generalize across fresh seeds without changing the Control Lane router architecture, optimizer, training schedule, or codebooks?

Production primitive added to `fold_lm.v05.controller`:

`canonicalize_boolean_channels`

Contract:

- caller supplies schema-known boolean channel indices;
- caller supplies an explicit decode threshold;
- values below threshold map to `-1`;
- values above threshold map to `+1`;
- a value exactly on the threshold is rejected as ambiguous;
- channels not listed by the schema are preserved unchanged;
- router architecture and parameter count remain unchanged.

Compatibility examples:

- signed encoding: threshold `0.0`;
- zero/one encoding: threshold `0.5`.

Prospective C111 validation seeds:

- known regression seed: `20261311`;
- fresh seeds: `20261321`, `20261322`, `20261323`.

The C108 training and OOD codebooks remain unchanged.

C111 requires:

```text
adapter contract smoke                         = pass
known C108 failure recovered                   = true
all fresh seeds                                = pass
anchor action accuracy min                     = 1.0
anchor minimum six-class recall min            = 1.0
OOD action accuracy min                        = 1.0
OOD minimum six-class recall min               = 1.0
OOD minimum-burden rate min                    = 1.0
OOD ineligible mechanism count sum             = 0
OOD action flip count sum                      = 0
```

C111 changes the production representation primitive, not the router architecture. It is not a Gate E passage claim.

Remaining falsification axes after C111 include near-threshold/noisy boolean metadata, stale capability state, irrelevant distractors, and real acquisition mechanisms.
