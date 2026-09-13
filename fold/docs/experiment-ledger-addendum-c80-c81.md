# FOLD Experiment Ledger Addendum — C80 / C81

Date: 2026-09-14

## C80 accepted production policy

Experiment: `C80-shared-basis-train-materialized-infer-native-policy`

Status: **PASS**.

Production policy gate: **PASS**.

Fresh Language seeds: `20261021, 20261022, 20261023`.

Accepted results:

- V5 regression suite: 317 tests pass;
- training execution mode: `materialized`;
- inference execution mode: `gemm_native`;
- production materialized-training parameters match the accepted materialized reference exactly for all seeds;
- production materialized validation outputs match exactly for all seeds;
- after switching the same checkpoint to GEMM-native, all validation outputs are allclose;
- all GEMM-native scores equal the reference;
- all GEMM-native semantics equal the reference;
- maximum GEMM-native validation tensor gap: `1.9073486328125e-06`;
- protected C37 result preserved;
- protected runtime fixture preserved;
- tracked repository clean;
- default Dense runtime remains unchanged.

Decision:

```text
Shared-Basis training  -> materialized arithmetic
Shared-Basis inference -> GEMM-native arithmetic
```

Execution mode is explicit and does not automatically follow `train()` / `eval()`. The same persistent Shared-Basis parameters/checkpoint are used in both modes; no checkpoint conversion is required.

C80 closes the production training-policy issue exposed by C78 and diagnosed by C79. It does not itself pass Gate C.

Gate C remains **NOT PASSED**.

## C81 active — actual production large-shape runtime / resident-memory gate

C81 must use the actual production `fold_lm.v05.modules.SharedBasisFixedRoutingCore` forward path in `gemm_native` mode rather than the older benchmark-only runtime class.

Scientific/engineering question:

> Does the production Shared-Basis implementation preserve the expected large-width runtime/storage Pareto behavior at the three currently selected rank fractions?

Selected rank-fraction profiles:

```text
lean          = 1/16   # Composition-like selected fraction
medium        = 1/8    # Language-like selected fraction
rank3_bridge  = 3/16   # Condition-like selected fraction
```

Widths:

```text
1024, 3072, 5120
```

Batches:

```text
1, 8
```

Fixed structure:

- slots = 20;
- modules = 2;
- hidden_mult = 2;
- float32 CUDA;
- eager execution;
- production execution mode = `gemm_native`;
- semantically identical Dense materialized reference for each point.

Measurements:

- actual unique production parameter/storage bytes;
- actual Dense parameter/storage bytes;
- full-core persistent ratio;
- CUDA live-allocation diagnostic;
- paired CUDA-event latency ratio;
- output allclose against the Dense materialized reference.

### Prospectively declared C81 production-runtime practicality gate

At the width5120 endpoint, for **every selected rank-fraction profile** and for both batch1 and batch8:

1. output comparison must be allclose;
2. full-core Shared-Basis persistent-byte ratio must be `<= 0.82` relative to Dense;
3. median Shared/Dense latency ratio must be `<= 1.20`.

Rationale:

- C73/C75 already predict width5120 full-core ratios of roughly 0.714 / 0.760 / 0.807 for the three selected fractions;
- C73/C75 predict endpoint latency ratios below roughly 1.18 for these selected fractions;
- `0.82` therefore requires a clear persistent-memory win even at the highest currently selected fraction;
- `1.20x` defines a prospective engineering ceiling for deployment practicality without changing the criterion after observing C81.

C81 is a production implementation/runtime gate, not a fresh quality experiment. Quality/rank acceptance remains grounded in C60-C80. C81 does not switch the Dense default and does not by itself establish broad-model superiority.
