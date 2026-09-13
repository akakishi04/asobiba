# FOLD Experiment Ledger Addendum — C79 / C80

Date: 2026-09-14

## C79 accepted mechanism diagnosis

Experiment: `C79-shared-basis-training-arithmetic-drift-diagnosis`

Status: **PASS**.

C79 reused the exact Language seeds that exposed the valid C78 integration-gate failure. It compared:

1. accepted materialized Shared-Basis training;
2. production GEMM-native training;
3. production parameter layout with materialized arithmetic.

Accepted result:

- all production-native final outputs allclose: false;
- all production-layout/materialized final outputs allclose: true;
- production-layout/materialized final output gap: exactly `0.0` for all three seeds;
- production-layout/materialized final parameter gap: exactly `0.0` for all three seeds;
- production-native final output max-abs gap: mean `0.0007891654968`, max `0.0009396076202`;
- production-native final parameter max-abs gap: mean `3.4805387e-05`, max `3.7543476e-05`;
- native drift is visible from the first optimization step and grows over training;
- `training_arithmetic_order_drift_supported = true`.

Decision:

The C78 training drift is localized to floating-point arithmetic-order differences from GEMM-native execution during optimization. The concatenated production parameter layout and AdamW update policy are not implicated by the current evidence.

Therefore the first production-policy candidate is:

```text
training  -> materialized arithmetic
inference -> GEMM-native arithmetic
```

The same Shared-Basis persistent parameters/checkpoint are used in both modes. No checkpoint conversion is required.

Gate C remains **NOT PASSED**.

## C80 active production-policy gate

Production `SharedBasisFixedRoutingCore` now supports explicit execution modes:

- `gemm_native` — default, deployment-oriented path;
- `materialized` — accepted-training-semantics path.

The mode is explicit execution policy and is not stored as model parameter state. It does not change automatically with `train()` or `eval()`.

Tracked files:

- `fold/fold_lm/v05/modules.py`
- `fold/tests_lm/test_v05_shared_basis_execution_mode.py`
- `fold/fold_lm/v05_benchmarks/gate_c_shared_basis_c80_helpers.py`
- `fold/fold_lm/v05_benchmarks/gate_c_shared_basis_train_materialized_infer_native_policy.py`

C80 is focused on the Language path because:

- C77 already established selected-rank GEMM-native inference equivalence across Condition / Composition / Language;
- C78's only integration failure was long-training tensor drift;
- C79 localized that drift using the Language 600-step path.

C80 uses fresh Language seeds `20261021, 20261022, 20261023` and requires:

1. production materialized training to preserve reference parameters exactly;
2. production materialized validation outputs to match the accepted reference exactly;
3. switching the same trained checkpoint to GEMM-native to preserve validation score;
4. GEMM-native validation semantics to remain equal;
5. GEMM-native validation tensors to satisfy the existing C77/C78 allclose tolerance.

Primary flag:

`production_policy_gate_passed`

C80 does not switch the Dense default and does not pass Gate C by itself.
