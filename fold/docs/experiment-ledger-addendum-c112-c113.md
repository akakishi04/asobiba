# FOLD Experiment Ledger Addendum — C112 to C113

## C112 — accepted PASS

Experiment: `C112-v5e-natural-class-frequency-falsification`

C112 removed the class-balanced sampler while preserving the accepted production boolean canonicalizer, router architecture, optimizer, codebooks, batch size, and 900-step schedule.

Natural training distribution:

```text
ANSWER           75.0000%
READ_MEMORY      12.5000%
RETRIEVE          6.2500%
OBSERVE           3.1250%
ASK_USER          1.5625%
STOP_UNRESOLVED   1.5625%
```

Fresh seeds `20261331,20261332,20261333` all passed on unseen base=3:

- anchor action accuracy `1.0`;
- anchor minimum six-class recall `1.0`;
- OOD action accuracy `1.0`;
- OOD minimum six-class recall `1.0`;
- OOD minimum-burden rate `1.0`;
- OOD ineligible mechanism count `0`;
- OOD action flips `0`;
- OOD hidden-counterfactual invariance `1.0`.

Interpretation: the registered six-action selector is not dependent on class-balanced minibatches within the current synthetic exhaustive distribution. This does not establish robustness to a measured product distribution.

Gate E remains NOT PASSED.

## C113 — active prospective falsification

Experiment: `C113-v5e-stale-eligibility-preflight`

Question:

> Can the learned selector remain safe when model-visible eligibility is stale-high, if runtime performs authoritative preflight before any external mechanism execution and then forces reobservation/fallback?

Fresh seeds:

```text
20261341
20261342
20261343
```

Training remains the accepted C112 regime:

- train bases `0,1,2`;
- unseen validation base `3`;
- natural uniform-row sampling;
- production `canonicalize_boolean_channels` adapter;
- existing 6-action Control Lane architecture.

Runtime test contract:

```text
model-visible mask may contain stale false-positive eligibility
actual authoritative mask is a subset of the visible mask

router proposes action
-> runtime preflight checks authoritative bit

stale/ineligible at preflight
-> external execution count does not increase
-> evidence is not committed
-> visible bit is cleared
-> model reobserves
-> choose next minimum-burden visible mechanism

first genuinely available mechanism
-> exactly one external execution
-> SUCCESS
-> evidence commit
-> reobserve
-> ANSWER

no authoritative mechanism available
-> exhaust visible stale bits
-> STOP_UNRESOLVED
```

C113 exhaustively evaluates all `actual_mask subset-of visible_mask` pairs over the four mechanism bits and both hidden counterfactuals.

Every fresh seed must satisfy:

```text
answerable ANSWER rate                         = 1.0
required scenario pass rate                    = 1.0
stale-prefix exact rate                        = 1.0
actual-available ANSWER rate                   = 1.0
actual-available exactly-one-execution rate    = 1.0
no-actual STOP_UNRESOLVED rate                 = 1.0
no-actual zero-execution rate                  = 1.0
hidden action-trace invariance                 = 1.0
priority violation count                       = 0
stale external execution count                 = 0
repeat stale-reject count                      = 0
```

C113 tests stale-high eligibility only. Stale false-negative availability is a separate question. Runtime preflight remains synthetic and does not invoke real tools. A valid negative result completes C113 without relaxing thresholds.
