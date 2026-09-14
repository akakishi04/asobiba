# Experiment Ledger Addendum — C111 to C112

## C111 — accepted production representation integration

Experiment: `C111-v5e-production-control-canonicalization-integration`

Execution was valid on `feat/sft-target-loss` at commit `37c65615a0b04f7bbb22a799b367d0474e6e23f4`.

Accepted results:

- production `canonicalize_boolean_channels` contract smoke passed;
- known C108 failing seed `20261311` recovered;
- fresh seeds `20261321,20261322,20261323` all passed;
- anchor action accuracy min `1.0`;
- anchor minimum class recall min `1.0`;
- OOD action accuracy min `1.0`;
- OOD minimum class recall min `1.0`;
- OOD minimum-burden rate min `1.0`;
- OOD ineligible mechanism count sum `0`;
- OOD action flip count sum `0`;
- protected C37 result and fixture preserved;
- tracked tree clean.

Interpretation:

> The accepted C108 amplitude-sensitivity failure is removed by the explicit production schema-aware boolean Control-Lane canonicalizer, and the repair generalizes to three fresh seeds without changing the router architecture, optimizer, training schedule, or codebooks.

Scope remains synthetic. Gate E is not passed.

## C112 — active falsification: natural class frequency

Experiment: `C112-v5e-natural-class-frequency-falsification`

Question:

> Does the six-action production selector still learn the registered mechanism policy when class-balanced training is removed and batches are sampled uniformly from the naturally imbalanced exhaustive training rows?

C112 isolates training-frequency dependence. Keep fixed:

- production `canonicalize_boolean_channels` adapter;
- router architecture: control width `4`, hidden width `8`;
- optimizer / LR from C108/C111;
- training steps `900`;
- batch size `96`;
- training codebooks and held-out OOD codebooks from C108/C111;
- train bases `0,1,2`;
- unseen validation base `3`.

Fresh seeds:

```text
20261331
20261332
20261333
```

Replace only the sampler:

```text
previous: class-balanced 16 examples per action per step
C112:     uniform training-row sampling with replacement
```

Natural exhaustive training distribution:

```text
ANSWER           75.0000%
READ_MEMORY      12.5000%
RETRIEVE          6.2500%
OBSERVE           3.1250%
ASK_USER          1.5625%
STOP_UNRESOLVED   1.5625%
```

Prospective gate for every fresh seed:

```text
anchor action accuracy               = 1.0
anchor minimum six-class recall      = 1.0
OOD action accuracy                  = 1.0
OOD minimum six-class recall         = 1.0
OOD minimum-burden rate              = 1.0
OOD ineligible mechanism count       = 0
OOD action flip count                = 0
OOD hidden-counterfactual invariance = 1.0
```

`status=PASS` means the experiment executed validly. The scientific gate is `natural_class_frequency_falsification_gate_passed`.

A valid negative result completes C112 and must not be repaired by retroactively changing steps, batch size, thresholds, or seeds under the same C number.

Limitations:

- the natural distribution is the current synthetic exhaustive distribution, not a measured product distribution;
- runtime metadata remains semantically correct/current;
- real memory/retrieval/observation/user interaction remains untested;
- C112 cannot establish Gate E passage.
