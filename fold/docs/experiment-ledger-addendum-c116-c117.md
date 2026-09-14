# FOLD experiment ledger addendum — C116 to C117

## C116 — ACCEPTED PASS

Experiment: `C116-v5e-authoritative-preflight-priority-refresh`.

Valid execution on fresh seeds `20261361,20261362,20261363`; protected C37 and fixture preserved; tracked tree clean.

Accepted result:

- 81 visible<=authoritative mask pairs / 162 required cases;
- 50 priority-upgrade cases and 30 terminal-recovery cases;
- required scenario pass `1.0`;
- exactly-one preflight refresh `1.0`;
- priority-upgrade recovery `1.0`;
- non-minimal proposal suppression exact `1.0`;
- terminal recovery `1.0`;
- unchanged-authoritative execution `1.0`;
- confirmed-unavailable STOP `1.0`;
- priority violations `0`;
- premature STOP accepts `0`;
- hidden action-trace invariance `1.0`.

Interpretation: under the registered synthetic availability contract, the runtime can refresh authoritative availability immediately before an external action or terminal STOP, suppress a stale higher-burden proposal, update visible state, and force reobservation before execution.

Gate E remains NOT PASSED.

## C117 — ACTIVE

Experiment: `C117-v5e-post-preflight-execution-failure-fallback`.

Question: does the registered learned fallback remain correct when composed with C116 authoritative preflight, including cases where a selected mechanism subsequently fails and runtime must remove it, avoid evidence commit, reobserve, and continue to the next eligible mechanism?

Implementation deliberately composes the already-tested C116 preflight semantics with the already-tested C105 failure-fallback evaluator, while routing through the current production prediction path (`c113._predict` + production boolean canonicalization).

Prospective conditions:

```text
fresh seeds      = 20261371,20261372,20261373
validation base  = 3 only
mask pairs       = all 81 visible<=authoritative pairs
hidden           = 0,1 counterfactuals
fallback cases   = success at each eligible position + all-fail
expected trajectories = 594
```

Every fresh seed must satisfy:

```text
trajectory pass rate                 = 1.0
preflight correct rate               = 1.0
failure fallback recovery rate       = 1.0
hidden action-trace invariance       = 1.0
ineligible mechanism count           = 0
repeat failed mechanism count        = 0
budget violation count               = 0
```

The inherited C105 scenario gate additionally requires minimum-burden fallback, no evidence commit on failed attempts, exactly one commit on success, correct final answer on eventual success, and STOP_UNRESOLVED after all mechanisms fail.

C117 remains synthetic and does not invoke real tools or model partial/non-idempotent external effects. A valid negative result completes C117 without relaxing thresholds.
