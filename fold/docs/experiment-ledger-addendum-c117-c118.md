# FOLD experiment ledger addendum — C117 to C118

## C117 — ACCEPTED PASS

Experiment: `C117-v5e-post-preflight-execution-failure-fallback`.

The first C117 attempt was invalid because the helper referenced a nonexistent `c105._target`. The retry kept the same experiment number, seeds, thresholds, and scientific question. The helper was corrected to construct the post-acquisition target through the existing direct-answer semantics, and import preflight added a target-construction smoke check.

Valid retry:

```text
fresh seeds       = 20261371,20261372,20261373
mask pairs        = 81
trajectories      = 594 per seed
```

Accepted result across all three seeds:

```text
trajectory pass rate            = 1.0
preflight correct rate          = 1.0
failure fallback recovery rate  = 1.0
hidden action-trace invariance  = 1.0
ineligible mechanism count      = 0
repeat failed mechanism count   = 0
budget violation count          = 0
```

Protected C37 and fixture hashes were preserved and the tracked tree was clean.

Interpretation: under the registered synthetic contract, authoritative availability preflight composes correctly with post-preflight clean failure handling: failed mechanisms do not commit evidence, are removed from eligibility, and fallback proceeds in minimum-burden order until success or STOP_UNRESOLVED.

Gate E remains NOT PASSED.

## C118 — ACTIVE

Experiment: `C118-v5e-unknown-effect-containment`.

Question: if a mechanism passes authoritative preflight and executes, but the runtime cannot determine whether a potentially non-idempotent external effect occurred, can runtime contain the ambiguity without false evidence commit, duplicate execution, or automatic fallback?

Registered UNKNOWN_EFFECT policy:

```text
exactly one external execution has occurred
-> evidence commit = 0
-> retry same mechanism = 0
-> automatic fallback execution = 0
-> terminal runtime state = UNRESOLVED_UNKNOWN_EFFECT
```

SUCCESS remains a control path and must still commit exactly once and reobserve to ANSWER.

Prospective conditions:

```text
fresh seeds       = 20261381,20261382,20261383
validation base   = 3
mask pairs        = all 81 visible<=authoritative pairs
hidden            = 0,1
non-empty actual  -> SUCCESS and UNKNOWN_EFFECT controls
empty actual      -> confirmed unavailable STOP control
```

Every fresh seed must satisfy:

```text
scenario pass rate                              = 1.0
success control ANSWER rate                     = 1.0
success exactly-one commit rate                 = 1.0
unknown-effect containment rate                 = 1.0
unknown-effect exactly-one execution rate       = 1.0
unknown-effect zero evidence-commit rate        = 1.0
unknown-effect zero retry rate                  = 1.0
unknown-effect zero fallback-execution rate     = 1.0
confirmed-none STOP rate                        = 1.0
hidden action-trace invariance                  = 1.0
```

C118 is deliberately conservative. It does not yet implement reconciliation or idempotency-key recovery, and it still uses synthetic providers. A valid negative result completes C118 without relaxing thresholds.
