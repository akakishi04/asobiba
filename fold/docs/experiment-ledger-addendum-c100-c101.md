# FOLD Experiment Ledger Addendum — C100 to C101

Date: 2026-09-14

## C100 — acquisition failure oracle

Status: accepted valid PASS.

C100 froze one-read acquisition outcome semantics before learning them.

```text
SUCCESS      -> commit validated evidence -> ANSWER
UNAVAILABLE  -> no evidence commit        -> STOP_UNRESOLVED
DENIED       -> no evidence commit        -> STOP_UNRESOLVED
INVALID      -> no evidence commit        -> STOP_UNRESOLVED
```

Accepted authority rule:

```text
model/router -> proposes action
runtime      -> owns acquisition outcome and authoritative evidence mutation
```

Accepted result:

- answerable zero-acquisition rate: 1.0
- SUCCESS post-acquisition ANSWER rate: 1.0
- SUCCESS final accuracy: 1.0
- SUCCESS evidence commit rate: 1.0
- failure STOP_UNRESOLVED rate: 1.0
- failure no-evidence-commit rate: 1.0
- failure no-guessed-answer rate: 1.0
- repeat acquisition count: 0
- budget violations: 0
- C37 and fixture preserved
- tracked tree clean

Interpretation: failed or untrusted acquisition is not evidence. Under the one-read budget, failure terminates unresolved instead of silently retrying or guessing.

C100 is an oracle semantics baseline only and does not establish Gate E.

## C101 — prospective learned acquisition-outcome policy

Question:

Can production `ControlLaneActionRouter` learn the C100 three-action policy from visible evidence plus a runtime-owned outcome token, and generalize to an unseen base without hidden/target leakage?

Prospective conditions:

```text
fresh seeds      = 20261191,20261192,20261193
train bases      = 0,1,2
validation base  = 3 only (unseen)
control width    = 4
hidden width     = 4
training steps   = 480
action count     = 3
```

Visible Control Lane:

```text
base
dependency
evidence_present
observed_hidden
```

Runtime outcome token:

```text
NOT_ATTEMPTED
SUCCESS
UNAVAILABLE
DENIED
INVALID
```

Target answer and oracle action are not router inputs. Whenever evidence is absent, hidden=0/1 counterfactuals must be bit-identical in both the Control Lane and outcome token.

Every fresh seed must satisfy on unseen base=3:

```text
action accuracy                    = 1.0
initial required ACQUIRE recall     = 1.0
initial unnecessary ACQUIRE rate    = 0.0
SUCCESS post-acquisition ANSWER     = 1.0
failure STOP_UNRESOLVED rate        = 1.0
action flips                       = 0
failure guessed-answer count       = 0
```

C101 remains a tiny synthetic policy-learning experiment. It does not select among memory, retrieval, observation, or user-question mechanisms and does not establish Gate E passage.
