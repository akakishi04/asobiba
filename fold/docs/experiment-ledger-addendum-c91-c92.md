# FOLD Addendum — C91 / C92

Date: 2026-09-14

## C91 accepted negative result

`C91-v5d-selected-router-large-width-runtime-vram`: valid execution PASS, scientific gate FAIL.

The selected `hidden_width=4` router did not transfer from width32 to width3072/5120 under the accepted 240-step router schedule:

- action accuracy ranged from about 0.333 to 0.500;
- minimum five-class recall was 0.0;
- learned outputs were not allclose to the fixed/oracle reference;
- therefore the extremely low runtime ratios observed in C91 are not valid speed evidence, because incorrect routing skipped required compute;
- router persistent/core ratio was already very small (~0.00046-0.00076) and measured router device-free VRAM cost was below the measurement granularity.

Gate D remains NOT PASSED.

## C92 active mechanism diagnosis

C92 asks whether the C91 large-width failure is:

1. delayed optimization/convergence of hidden4;
2. a compact-router capacity-transfer failure;
3. a broader width-scaling problem in the current router representation/optimization.

C92 reuses the C91 failure seeds because this is a mechanism diagnosis.

Widths: `3072, 5120`.

Hidden widths: `4, 32`.

Training checkpoints: `240, 480, 960, 1920`.

Training rule remains AdamW, `lr=0.01`.

Quality thresholds remain action accuracy >= `0.995` and minimum class recall >= `0.99`.

Interpretation:

- if hidden4 recovers by 1920, delayed convergence is supported;
- if hidden4 does not recover but hidden32 does, compact-capacity transfer failure is supported;
- if neither recovers, the current large-width router representation/optimization needs redesign.

C92 changes no production runtime and is not itself a Gate D pass experiment.
