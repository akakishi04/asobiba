# FOLD Addendum — C88 / C89

Date: 2026-09-14

## C88 accepted negative runtime result

`C88-v5d-composition-learned-sparse-wallclock-runtime`: valid execution PASS, runtime gate FAIL.

C87 logical compute reduction remained exactly 50%, and adaptive/fixed outputs were allclose, but the current eager learned sparse path was slower than fixed-max at Composition width 32:

- adaptive/fixed CUDA-device latency: mean `1.50084x`, range `1.41341x..1.60290x`;
- adaptive/fixed wall latency: mean `1.38403x`, range `1.27357x..1.58413x`;
- predeclared maximum ratio was `0.95x`.

Interpretation: logical compute reduction does not currently translate into runtime speedup at the tiny shape. Router work plus eager `nonzero/index_select/index_copy` overhead dominates. This does not invalidate C87 routing quality or the 50% logical-step reduction.

Gate D remains NOT PASSED.

## C89 active width-crossover diagnosis

Experiment: `C89-v5d-sparse-runtime-width-crossover`.

Widths:

`32, 128, 512, 1024, 3072, 5120`

Balanced batch: `216`; logical 0/1/2-step distribution remains one third each, so logical compute reduction remains 50% vs fixed two-step.

C89 separates three runtime paths:

1. fixed-max two-step execution;
2. oracle sparse execution without controller cost;
3. production-controller forward/argmax cost plus oracle sparse execution.

The third path intentionally pays the current production controller cost but executes oracle actions so routing quality cannot confound the runtime mechanism measurement. C87 already established learned routing quality at the tiny registered task shape.

Crossover threshold is prospectively fixed at both median CUDA-device and wall ratios <= `0.95x` fixed-max. C89 reports the first width meeting that threshold for oracle sparse and controller-inclusive sparse separately. If no crossover is found through width 5120, the current eager sparse architecture is not runtime-practical in the tested range and needs execution/controller redesign before Gate D can pass.

C89 also records controller persistent bytes relative to Shared-Basis core bytes because VRAM headroom remains the primary model-lightness objective.
