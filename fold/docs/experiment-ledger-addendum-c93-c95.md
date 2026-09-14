# FOLD Addendum — C93 / C94 / C95

Date: 2026-09-14

## C93 accepted diagnosis

`C93-v5d-router-control-lane-diagnosis`: valid PASS execution.

- Full-width hidden4 router: 0/6 large-width conditions passed.
- Fixed 4-channel control lane: 4/6 passed at 240 steps.
- Residual failures were both seed `20261142`, with identical metrics at width3072 and width5120: action accuracy `0.944444`, minimum class recall `0.666667`.
- Control-lane persistent bytes were `436`, versus `245876` to `409716` bytes for the width-coupled router.
- The prospectively strong C93 hypothesis (`control_lane_all_pass`) was not met, so C93 alone did not justify production adoption.

## C94 accepted diagnosis

`C94-v5d-control-lane-convergence-diagnosis`: PASS.

The same diagnostic failure seeds were followed at 240/480/960 steps.

First passing checkpoint by seed was identical across width3072 and width5120:

- `20261141`: `240 / 240`
- `20261142`: `480 / 480`
- `20261143`: `240 / 240`

All six conditions passed by 480 steps. This strongly supports width-independent convergence for the fixed control lane within the registered synthetic routing regime.

## C95 active prospective validation

C95 uses fresh seeds `20261151, 20261152, 20261153`, widths `3072, 5120`, control width `4`, hidden width `4`, and a fixed 480-step schedule.

Unlike C93/C94, C95 introduces a row-level holdout (`row_index % 5 == 0`) and evaluates only held-out routing examples for the deciding gate.

Predeclared gate:

- held-out action accuracy >= `0.995` for every width/seed;
- held-out five-class minimum recall >= `0.99` for every width/seed;
- all six width/seed conditions must pass.

If C95 passes, the control-lane design becomes eligible for production implementation and a subsequent learned-action runtime/VRAM revalidation. Gate D remains NOT PASSED until that production revalidation succeeds.
