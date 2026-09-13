# FOLD Experiment Ledger Addendum — C80 / C81 / C82

Date: 2026-09-14

This addendum supplements `fold/docs/experiment-ledger-and-handoff.md` and the C79/C80 addendum.

## C80 — accepted production execution policy

Experiment: `C80-shared-basis-train-materialized-infer-native-policy`

Status: **PASS**.

Accepted production policy:

```text
training  -> materialized arithmetic
inference -> GEMM-native arithmetic
```

The same `SharedBasisFixedRoutingCore` persistent parameter layout/checkpoint is used for both execution modes. The mode switch is explicit and does not follow `train()` / `eval()` automatically.

Fresh Language seeds: `20261021, 20261022, 20261023`.

Accepted result:

- V5 regression suite: 317 tests pass;
- production materialized-training parameters match the accepted materialized reference exactly;
- production materialized validation outputs match exactly;
- switching the same checkpoint to `gemm_native` preserves score and semantics for all fresh seeds;
- native validation max-abs gap = `1.9073486328125e-06`;
- protected C37 result preserved;
- runtime fixture preserved;
- tracked repository clean;
- `production_policy_gate_passed = true`.

Decision: do not use GEMM-native arithmetic during optimization on the current evidence; use it for inference/deployment execution.

## C81 — accepted production large-shape runtime / resident-memory gate

Experiment: `C81-shared-basis-production-large-shape-runtime`

Status: **PASS**.

Measured the actual production `SharedBasisFixedRoutingCore.forward()` in `gemm_native` mode at widths `1024, 3072, 5120`, batches `1, 8`, and the currently relevant rank fractions:

```text
lean         = 1/16
medium       = 1/8
rank3_bridge = 3/16
```

Predeclared width5120 endpoint ceilings:

```text
full-core persistent ratio <= 0.82
Shared/Dense median latency <= 1.20x
output allclose = true
```

Accepted width5120 results:

| profile | batch | persistent ratio | Shared/Dense median latency |
|---|---:|---:|---:|
| lean 1/16 | 1 | 0.7136162458 | 1.0565275610 |
| lean 1/16 | 8 | 0.7136162458 | 1.0666202685 |
| medium 1/8 | 1 | 0.7604790419 | 1.0648483192 |
| medium 1/8 | 8 | 0.7604790419 | 1.1022543106 |
| 3/16 | 1 | 0.8073418381 | 1.1115048338 |
| 3/16 | 8 | 0.8073418381 | 1.1415956665 |

All production outputs were allclose. Protected artifacts were preserved and the tracked repository remained clean.

Decision: production GEMM-native inference is runtime-practical at the tested large shapes for all currently relevant selected rank fractions.

C81 intentionally excludes dense-to-SVD constructor cost and does not by itself pass Gate C.

## C82 — active production serialized-artifact gate

Experiment: `C82-shared-basis-production-serialized-artifact`

Tracked benchmark:

`fold/fold_lm/v05_benchmarks/gate_c_shared_basis_production_serialized_artifact.py`

Tracked runner:

`fold/scripts/run_c82.ps1`

C82 isolates the last production storage artifact question before the Gate C decision.

Representative shape:

```text
width = 3072
slots = 20
modules = 2
hidden_mult = 2
```

Profiles:

```text
lean         = 1/16
medium       = 1/8
rank3_bridge = 3/16
```

For Dense once and Shared-Basis for each profile, C82 performs:

```text
torch.save(state_dict)
-> real file-size measurement
-> SHA256
-> torch.load(weights_only=True)
-> tensor-by-tensor exact round-trip verification
-> temporary artifact deletion
```

Predeclared gate:

- every Shared/Dense serialized ratio <= `0.83`;
- Dense and every Shared-Basis state_dict round-trip exactly;
- Shared-Basis state_dict contains no materialized/effective routed-weight bank keys;
- protected C37 result remains unchanged.

Primary flag:

`production_serialized_artifact_gate_passed`

If C82 passes, the cumulative V5-C evidence is ready for the formal Gate C decision using the existing quality, capacity, recurrence, production policy, runtime, resident-memory, and serialized-artifact evidence. Any Gate C pass must remain explicitly scoped to the registered V5 synthetic task/runtime regime and must not be presented as broad LLM superiority.

Gate C remains **NOT PASSED** until C82 is judged.
