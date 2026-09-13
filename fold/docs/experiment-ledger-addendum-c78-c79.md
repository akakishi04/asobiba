# FOLD Experiment Ledger Addendum — C78 / C79

Date: 2026-09-14

This addendum supplements `fold/docs/experiment-ledger-and-handoff.md`.

## C78 — opt-in production Shared-Basis integration

Experiment ID:

`C78-shared-basis-production-optin-integration`

Valid execution result: **PASS**.

Production integration scientific gate: **FAIL**.

The first C78 attempt had a focused unit-test bug: route 1 only was backpropagated while the test incorrectly required gradients for every route-specific parameter. That attempt was invalid for the integration decision and was retried under C78 after correcting the test to include both routes.

The valid C78 run then established:

- compileall: pass;
- focused Shared-Basis unit tests: 9/9 pass;
- all `test_v05_*.py` regressions: 314 pass;
- initial effective weights: exact match, max gap `0.0`;
- initial gradient comparison: allclose, max absolute gap `1.862645149230957e-09`;
- validation scores: equal for all 9 task/seed runs;
- validation semantics: equal for all 9 runs;
- production native-vs-materialized recurrence through 64 updates: allclose;
- state_dict round-trip: exact;
- protected C37 result and runtime fixture preserved;
- tracked repository clean;
- default `HighPrecisionFixedRoutingCore` path unchanged.

The failed flag was:

`all_validation_outputs_allclose = false`

After full direct training, the maximum materialized-reference vs production-GEMM validation tensor gap was:

`0.0009396076202392578`

The largest gaps occurred on Language after 600 steps. Condition and Composition stayed much closer. The production integration gate had been defined in advance to require validation tensor allclose, so the criterion must not be relaxed after observing this result.

C78 is therefore a valid negative scientific result: the opt-in production class is not yet accepted as the authoritative training path.

Important interpretation:

- this is not evidence that the production inference algebra is wrong;
- C77 already established post-training GEMM-native inference equivalence through recurrence;
- C78's initial effective weights and gradients were essentially identical;
- scores and semantics stayed equal;
- the observed failure is consistent with tiny floating-point arithmetic-order differences accumulating through long AdamW training, but C78 alone does not prove that mechanism.

Gate C remains **NOT PASSED**.

## C79 — training arithmetic drift diagnosis

Experiment ID:

`C79-shared-basis-training-arithmetic-drift-diagnosis`

Tracked benchmark:

`fold/fold_lm/v05_benchmarks/gate_c_shared_basis_training_arithmetic_drift_diagnosis.py`

Tracked runner:

`fold/scripts/run_c79.ps1`

C79 does **not** change production code.

It reuses the exact three C78 Language seeds (`20261011`, `20261012`, `20261013`) because this is a mechanism diagnosis, not a fresh quality/generalization estimate.

From identical factorized initialization and identical batches it trains three paths:

1. benchmark materialized Shared-Basis reference;
2. production GEMM-native `SharedBasisFixedRoutingCore`;
3. production parameter layout with materialized effective-weight arithmetic during forward.

Checkpoints:

`1, 10, 50, 150, 300, 450, 600`

At each checkpoint C79 records:

- validation output gap;
- validation semantic equality;
- validation score;
- parameter gap to reference;
- production-native vs production-materialized-layout parameter gap.

Primary diagnostic:

`training_arithmetic_order_drift_supported`

The hypothesis is supported only if the production-layout/materialized-arithmetic path tracks the accepted reference while the production GEMM-native training path reproduces the long-training drift.

Interpretation after C79:

- if supported, decide the production training policy explicitly rather than weakening C78's gate retrospectively;
- if not supported, investigate parameter layout / optimizer execution as an additional cause;
- do not switch the default Dense core;
- do not call Gate C passed from this diagnosis.
