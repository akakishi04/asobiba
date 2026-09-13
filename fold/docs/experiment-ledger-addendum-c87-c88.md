# FOLD Addendum — C87 / C88

Date: 2026-09-14

## C87 accepted

`C87-v5d-composition-supervised-variable-step-router`: PASS.

- 3/3 seeds action accuracy = 1.0.
- Minimum five-class recall = 1.0.
- Learned trajectory exact = 1.0.
- Exact delta vs C86 oracle = 0.0.
- Learned vs oracle outputs allclose.
- Mean compute = 1.0 step/event.
- Zero-step rate = 1/3.
- Two-step rate = 1/3.
- Logical compute reduction vs fixed two-step = 50%.

Interpretation: the learned router reproduces the 0/1/2-step oracle policy exactly on the registered tiny Composition task. This is still a logical-compute result, not yet a wall-clock speedup claim.

## C88 active

Question: does C87's learned 50% logical compute reduction produce an end-to-end GPU runtime benefit in the current eager sparse implementation?

Comparison:

```text
fixed-max: two unit steps/event, no router
adaptive: learned router + action grouping + sparse gather/core/index_copy execution
```

C88 deliberately includes router and sparse indexing overhead.

It reuses the accepted C87 seeds because this is a runtime mechanism measurement, not a fresh quality/generalization estimate.

Predeclared runtime gate for all three seeds:

- adaptive/fixed median CUDA-event latency <= 0.95;
- adaptive/fixed median synchronized wall latency <= 0.95;
- outputs remain allclose.

A negative C88 result is still valid evidence. It would mean logical compute reduction has not yet translated into runtime speedup for the current tiny width-32 eager implementation; the next step would be a width/batch crossover or sparse-runtime optimization study rather than weakening the criterion.

Gate D remains NOT PASSED until runtime practicality and the remaining routing criteria are accepted.
