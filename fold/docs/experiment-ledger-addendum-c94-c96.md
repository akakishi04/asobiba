# FOLD Addendum — C94 / C95 / C96

Date: 2026-09-14

## C94 accepted diagnosis

`C94-v5d-control-lane-convergence-diagnosis`: PASS.

At widths 3072 and 5120 the fixed four-channel control-lane router recovered all reused diagnostic seeds by 480 steps.  The first passing checkpoint matched across widths for every seed: `240/240`, `480/480`, `240/240`.

Interpretation: within this diagnostic scope, control-lane learning behavior is strongly decoupled from core width.

## C95 accepted prospective gate

`C95-v5d-control-lane-fresh-seed-validation`: PASS.

Fresh seeds `20261151,20261152,20261153`, widths 3072/5120, held-out rows `row_index % 5 == 0`:

- held-out action accuracy = 1.0 for all 6 conditions;
- held-out minimum five-class recall = 1.0 for all 6 conditions;
- action flips = 0;
- diagnostic router persistent bytes = 436.

Decision: fixed control lane becomes the selected production-router candidate.

## C96 active production gate

Production `fold_lm.v05.controller.ControlLaneActionRouter` is now explicit opt-in.  It consumes full working/context tensors but its parameter dimensions depend only on fixed `control_width`, not core width.  Existing `SupervisedActionRouter` remains available for compatibility/comparison.

C96 uses fresh seeds `20261161,20261162,20261163`, widths 3072/5120, `control_width=4`, `hidden_width=4`, 480 training steps.

Predeclared gate for every condition:

- held-out action accuracy >= 0.995;
- held-out minimum class recall >= 0.99;
- runtime action accuracy >= 0.995;
- runtime minimum class recall >= 0.99;
- logical compute reduction vs fixed two-step >= 0.45;
- learned/fixed median CUDA-device ratio <= 0.80;
- learned/fixed median wall ratio <= 0.80;
- router/core persistent ratio <= 0.001;
- router device-free VRAM cost <= 0.05 GiB;
- learned-action sparse output allclose with fixed-max output.

If C96 passes, proceed to a separate formal Gate D decision.  Do not infer Gate D passage from `status=PASS` alone.
