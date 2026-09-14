# FOLD V5-E Addendum — C101 to C102

Date: 2026-09-14

## C101 — accepted

`C101-v5e-supervised-acquisition-outcome-policy` is accepted as a valid positive result.

Production `ControlLaneActionRouter` learned the three-action policy:

```text
ANSWER
ACQUIRE
STOP_UNRESOLVED
```

Runtime outcome token classes:

```text
NOT_ATTEMPTED
SUCCESS
UNAVAILABLE
DENIED
INVALID
```

Fresh seeds:

```text
20261191
20261192
20261193
```

Train/validation split:

```text
train bases      = 0,1,2
validation base  = 3 only (unseen)
```

Accepted validation result across every seed:

- action accuracy `1.0`;
- initial required ACQUIRE recall `1.0`;
- initial unnecessary ACQUIRE rate `0.0`;
- SUCCESS post-acquisition ANSWER rate `1.0`;
- failure STOP_UNRESOLVED rate `1.0`;
- action flips `0`;
- failure guessed-answer count `0`;
- hidden/target input leakage false.

Interpretation:

C101 establishes learned snapshot-state handling of acquisition success and failure in the registered synthetic task. It does not yet establish that the predicted actions remain correct when executed as one runtime trajectory.

Gate E remains **NOT PASSED**.

## C102 — prospective gate

Experiment:

`C102-v5e-learned-acquisition-outcome-closed-loop`

Question:

> Can the learned three-action policy execute the full runtime trajectory on unseen base=3 across SUCCESS and all registered failure outcomes while preserving the model/runtime authority boundary?

Fresh seeds:

```text
20261201
20261202
20261203
```

Fixed conditions:

```text
train bases        = 0,1,2
validation base    = 3 only (unseen)
action space       = ANSWER / ACQUIRE / STOP_UNRESOLVED
outcomes           = SUCCESS / UNAVAILABLE / DENIED / INVALID
acquisition budget = 1
```

Authority:

```text
model/router -> proposes action
runtime      -> owns acquisition outcome and evidence mutation
model/router -> re-observes authoritative visible state + outcome token
```

Required success trajectory:

```text
ACQUIRE
-> SUCCESS
-> validated evidence commit
-> reobserve
-> ANSWER
-> correct final answer
```

Required failure trajectory:

```text
ACQUIRE
-> UNAVAILABLE / DENIED / INVALID
-> no evidence commit
-> reobserve
-> STOP_UNRESOLVED
```

Every seed must satisfy:

```text
initial required ACQUIRE recall       = 1.0
initial answerable ANSWER rate        = 1.0
initial unnecessary ACQUIRE rate      = 0.0
SUCCESS evidence commit rate          = 1.0
SUCCESS post-acquisition ANSWER rate  = 1.0
SUCCESS final accuracy                = 1.0
failure STOP_UNRESOLVED rate          = 1.0
failure no-evidence-commit rate       = 1.0
failure no-guessed-answer rate        = 1.0
premature STOP count                  = 0
repeat ACQUIRE count                  = 0
budget violation count                = 0
```

## Scope

C101/C102 remain tiny synthetic acquisition-control experiments. They do not establish real-world tool selection, broad uncertainty calibration, or Gate E passage.
