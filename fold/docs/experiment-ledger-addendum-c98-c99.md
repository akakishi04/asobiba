# FOLD Experiment Ledger Addendum — C98 to C99

Date: 2026-09-14

## C98 — accepted supervised information-sufficiency routing

C98 validly executed on commit `72d797459aca035068be8a4e577546ea1cf877b4` and passed its predeclared scientific gate.

Fresh seeds:

```text
20261171
20261172
20261173
```

Training used visible `base` values 0/1/2; validation held out `base=3`.
The production `ControlLaneActionRouter` received only:

```text
base
dependency
evidence_present
observed_hidden
```

When evidence was missing, hidden=0 and hidden=1 counterfactuals were bit-identical at the router input. Target values and oracle actions were not inputs.

Accepted validation result across all three fresh seeds:

- action accuracy: `1.0`;
- required ACQUIRE recall: `1.0`;
- unnecessary ACQUIRE rate: `0.0`;
- action flips: `0`;
- post-policy final accuracy: `1.0`.

Interpretation:

> The production fixed-width Control Lane can learn the C97 ANSWER/ACQUIRE information-sufficiency boundary and generalize it to an unseen visible base in this synthetic task.

C98 does not yet establish that acquisition itself works. Its evaluation treated ACQUIRE as an abstract successful information operation.

## C99 — active closed-loop acquisition gate

C99 asks one question only:

> Can the learned policy execute `ACQUIRE -> runtime evidence update -> reobserve -> ANSWER` without repeated acquisition, unnecessary acquisition, or model-side authority over evidence state?

Fixed conditions:

```text
fresh seeds = 20261181,20261182,20261183
train bases = 0,1,2
validation base = 3 (unseen)
action space = ANSWER / ACQUIRE
acquisition budget = 1
```

Authority boundary:

```text
model/router -> proposes ANSWER or ACQUIRE
runtime      -> alone may reveal/update evidence state
model/router -> re-observes committed visible evidence
```

Prospective acceptance requires every seed to satisfy:

- required acquisition recall = `1.0`;
- unnecessary acquisition rate = `0.0`;
- every required case acquires exactly once;
- every answerable case acquires zero times;
- every acquired case chooses ANSWER after re-observation;
- repeated ACQUIRE count = `0`;
- acquisition-budget violations = `0`;
- ambiguous direct-answer attempts = `0`;
- final post-cycle accuracy = `1.0`.

C99 deliberately keeps the acquisition mechanism abstract and deterministic. Memory/retrieval/observation/user-question mechanism selection and acquisition failure are deferred.
