# Experiment Ledger Addendum — C113 to C114

## C113 — ACCEPTED PASS

Experiment: `C113-v5e-stale-eligibility-preflight`

Stage: `V5-E-RUNTIME-AUTHORITY-FALSIFICATION`

Fresh seeds: `20261341, 20261342, 20261343`.

Registered result across all seeds:

- 81 visible/authoritative eligibility-mask pairs;
- 162 required cases;
- 80 stale cases;
- answerable ANSWER rate `1.0`;
- required scenario pass rate `1.0`;
- stale-prefix exact rate `1.0`;
- actual-available ANSWER rate `1.0`;
- actual-available exactly-one external execution rate `1.0`;
- no-actual STOP_UNRESOLVED rate `1.0`;
- no-actual zero-execution rate `1.0`;
- hidden action-trace invariance `1.0`;
- priority violations `0`;
- stale external executions `0`;
- repeat stale rejects `0`.

Interpretation: within the registered synthetic scope, model-visible stale-high eligibility is safely handled when runtime performs authoritative preflight before external execution, clears rejected visible eligibility, and forces reobservation/fallback. C113 does not test stale false-negative availability or real tool execution.

Gate E remains NOT PASSED.

## C114 — ACTIVE PERFORMANCE DIAGNOSTIC

Experiment: `C114-v5e-production-control-hot-path-profile`

Question:

> What latency and operational-VRAM cost does the production Control Representation Adapter add to the batch-1 Control Lane decision hot path, and does that cost grow with full core width despite the fixed-width router?

Profiles:

```text
router_only
adapter_only
production = adapter + router
```

Widths:

```text
8
5120
```

Fixed conditions:

```text
batch         = 1
slots         = 1
control width = 4
hidden width  = 8
action count  = 6
warmup        = 200
iterations    = 2000 per sample
samples       = 5
```

Each `(path,width)` condition runs in a fresh CUDA process to isolate allocator state.

Measurements:

- synchronized wall microseconds per decision;
- CUDA-event device microseconds per decision;
- warmup operational free-VRAM consumption;
- post-profile free-VRAM consumption;
- single-decision peak allocated/reserved deltas;
- router parameter count;
- functional equivalence between pre-canonicalized router input and production adapter path.

Derived comparisons:

- production width5120 / width8 wall and device ratios;
- adapter width5120 / width8 wall and device ratios;
- width5120 production / router-only wall and device ratios;
- width5120 extra warmup operational VRAM versus router-only.

C114 is a characterization, not a post-hoc pass/fail performance gate. Its execution is valid if the benchmark completes, protected artifacts remain unchanged, the tracked tree is clean, and functional equivalence checks hold. Performance design decisions are made only after observing the registered measurements.

No Gate E passage claim is attached to C114.
