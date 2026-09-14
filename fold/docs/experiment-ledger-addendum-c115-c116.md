# Experiment Ledger Addendum — C115 to C116

## C115 — ACCEPTED PASS

Experiment: `C115-v5e-stale-low-terminal-refresh`.

Execution validity:

- branch `feat/sft-target-loss`;
- commit `474922a230eaa0a1caefb72bfd48cca165cb7ce3`;
- focused controller regression 10/10;
- protected C37 and fixture preserved;
- tracked tree clean;
- no script error.

Scientific result across fresh seeds `20261351,20261352,20261353`:

```text
mask pairs                         = 81
required cases                     = 162
false-negative cases               = 30
required scenario pass min         = 1.0
false-negative recovery min        = 1.0
exactly-one refresh min            = 1.0
confirmed-unavailable STOP min     = 1.0
confirmed-unavailable zero-exec    = 1.0
visible-available zero-refresh     = 1.0
priority violations sum            = 0
premature STOP accepts sum         = 0
hidden trace invariance min        = 1.0
```

Accepted interpretation:

> When critical evidence is missing and the learned selector proposes `STOP_UNRESOLVED`, one authoritative availability refresh before accepting the terminal action is sufficient to recover stale-low false negatives in the registered synthetic scope. If the refresh confirms no mechanisms are available, STOP remains valid.

C115 does not test a newly available lower-burden mechanism while another visible higher-burden mechanism is already executable.

Gate E remains NOT PASSED.

## C116 — ACTIVE

Experiment: `C116-v5e-authoritative-preflight-priority-refresh`.

Question:

> If model-visible eligibility is stale-low but still contains an executable higher-burden mechanism, can authoritative preflight before external execution discover a newly available lower-burden mechanism, suppress the current proposal, force reobservation, and execute only the authoritative minimum-burden mechanism?

Fresh seeds:

```text
20261361
20261362
20261363
```

Registered runtime semantics:

```text
router proposes from model-visible mask
-> runtime refreshes authoritative availability once before external execution or terminal STOP

if authoritative minimum-burden action differs from proposal
-> do not externally execute current proposal
-> replace visible mask with authoritative mask
-> reobserve
-> router must choose authoritative minimum-burden action

if authoritative mask is empty
-> STOP_UNRESOLVED

if authoritative mechanism exists
-> exactly one external execution
-> SUCCESS commit
-> reobserve
-> ANSWER
```

The experiment exhaustively evaluates all 81 `visible subset-of actual` mask pairs across hidden counterfactuals.

Prospective gate for every fresh seed:

```text
required scenario pass rate                       = 1.0
exactly-one preflight refresh rate                = 1.0
priority-upgrade recovery rate                    = 1.0
priority-upgrade suppression exact rate           = 1.0
terminal recovery rate                            = 1.0
unchanged-authoritative execution rate            = 1.0
confirmed-unavailable STOP rate                   = 1.0
confirmed-unavailable zero-execution rate         = 1.0
priority violation count                          = 0
premature STOP accept count                       = 0
hidden action-trace invariance                    = 1.0
```

A valid negative result completes C116. Do not relax thresholds retrospectively.

Limitations:

- availability refresh remains synthetic;
- authoritative refresh is assumed available before every proposed external execution;
- freshness cost/value is not modeled;
- real memory/retrieval/observation/user interaction remains untested;
- C116 is not a Gate E passage claim.
