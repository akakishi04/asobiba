# FOLD Addendum — C91 / C92 / C93

Date: 2026-09-14

## C91 accepted negative result

`C91-v5d-selected-router-large-width-runtime-vram` executed validly but the scientific gate failed.

At widths 3072 and 5120, selected hidden-width 4 routing quality collapsed: action accuracy was 0.333-0.500, minimum five-class recall was 0, and learned outputs were not allclose to fixed-max. Runtime ratios from C91 are not accepted as speed evidence because the failing router skipped required computation. The compact router itself remained very small relative to the Shared-Basis core.

## C92 accepted mechanism diagnosis

`C92-v5d-router-large-width-convergence-diagnosis`: PASS as a diagnosis.

The C91 failure seeds were reused intentionally. Hidden width 4 never recovered by 1920 steps. Hidden width 32 recovered in five of six width/seed cases, but width 5120 seed 20261143 still failed at 1920 steps. Therefore the evidence does not support simple delayed convergence or a compact-router-only capacity failure. It supports a broader large-width optimization/representation problem in the current full-width controller.

## C93 active

C93 compares the existing hidden-width 4 full-width controller against a diagnostic fixed-width four-channel control-lane controller at widths 3072 and 5120.

Both use the same C92 failure seeds, AdamW, learning rate 0.01, and 240 training steps. The control lane consumes only the first four working/context channels and a four-dimensional operation embedding, so its input and parameter shape do not scale with core width.

The diagnosis is supported if the control-lane variant passes action accuracy >= 0.995 and minimum five-class recall >= 0.99 for all six width/seed cases while the current full-width variant remains unstable.

C93 changes no production controller architecture and does not establish Gate D passage.
