# FOLD v0.5 Gate A — Reference Computation and Accounting

Date: 2026-09-11

Status: **PASS**

Scope: V5-A only. This result does not claim language-model quality, compression quality, routing quality, FOLD-R integration, information acquisition, or Vision capability.

## Goal

Gate A establishes a reproducible reference boundary for the later v0.5 implementation before learned-core, compression, routing, memory integration, or Vision work is added.

The gate requires explainable numerical behavior, causal state boundaries, deterministic reference computation, explicit storage/execution accounting, and gradient validation.

## Implemented reference pieces

### A1 — State and provenance boundary

- `EvidenceState`
- `WorkingState`
- `BudgetState`
- `Provenance`
- separation of observed evidence from hypothesis provenance
- evidence time `t` separated from internal step `k`
- internal steps cannot silently advance evidence time or revision
- internal-step budget is a hard limit

### A2 — Float64 materialized state-update core

Reference residual update:

```text
mixed = H + context
delta = mixed @ W.T + b
H_next = H + gate * delta
```

The implementation is intentionally simple and deterministic. It is a numerical reference, not the V5-B learned core.

### A3 — Additive codebook decode reference

Whole-matrix reference encoding:

```text
W = W_base + sum_q codebook[q, code[q]]
```

Verified:

- materialized decoded weight equals manual construction
- direct decoded matmul equals the materialized reference
- arrays are copied/read-only
- invalid shapes, codes, and non-finite values are rejected

This is not the final V5-C block layout, low-bit format, bounded correction design, or optimized kernel.

### A4 — Fixed-code gradient reference

With discrete codes fixed, PyTorch float64 autograd was compared against central finite differences for continuous values.

Verified:

- base-weight gradient matches finite difference
- selected codebook-entry gradient matches finite difference
- unselected codebook entries receive zero gradient
- invalid dtype/shape/code/non-finite inputs are rejected
- tests complete without warning

### A5 — Storage accounting and deterministic serialization

Accounting separates:

```text
independent_continuous_scalars
discrete_code_bits
continuous_payload_bytes
discrete_code_bytes
metadata_bytes
serialized_bytes
```

Codes are bit-packed in the V5-A reference format. The measured serialized blob length must equal the reported `serialized_bytes` exactly.

This reference format is not a claim that float64 is an efficient production representation.

### A6 — Execution accounting

Reference execution accounting records:

- internal-step count
- active-module invocation count
- maximum active modules per step
- wall-clock seconds
- budget exhaustion

A test-injectable clock is used so the accounting contract can be validated deterministically. Non-monotonic clock observations are rejected.

## Gate tests

Validated locally after the V5-A implementation series through `635b25c5a51359c4a286a49e7bbfac0d55aab114`.

### V5-A dedicated suite

```text
python -m unittest discover -s tests_lm -p "test_v05_*.py" -v
Ran 30 tests
OK
```

### Full LM regression

```text
python -m unittest discover -s tests_lm -v
Ran 86 tests
OK
```

The 86 LM tests include the 30 V5-A tests.

### Reasoning regression

```text
python -m unittest discover -s tests_reasoning -v
Ran 40 tests
OK
```

### v0.1 numerical-kernel regression

```text
python -m unittest discover -s tests -v
Ran 28 tests
OK
```

No regression failure was observed in these suites.

## Gate A decision

Gate A passes because the required reference properties are now explicitly testable and reproduced:

1. state/provenance causal boundaries are explicit;
2. internal computation does not advance authoritative evidence time;
3. materialized and direct decoded computations agree;
4. fixed-code autograd agrees with float64 finite differences;
5. serialized byte accounting matches actual serialized length;
6. execution accounting exposes active-module, internal-step, wall-clock, and budget costs;
7. prior LM, reasoning, and v0.1 kernel test suites remain green.

This pass is about **reference correctness and accounting**, not model capability.

## Next stage

The next canonical stage is **V5-B — high-precision learned core**.

V5-B should start without compression and without learned routing. The first target is to show that a `shared core + working slots + small module set` can learn basic tasks under a controlled comparison against simple baselines. Compression, adaptive routing, information acquisition, FOLD-R integration, variable grouping, and Vision remain later-stage work.
