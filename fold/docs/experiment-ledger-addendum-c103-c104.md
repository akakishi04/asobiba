# FOLD Experiment Ledger Addendum — C103 to C104

Date: 2026-09-14

## C103 — ACCEPTED

Experiment: `C103-v5e-acquisition-mechanism-oracle`

C103 fixed the acquisition-mechanism selection semantics after C102 established the abstract learned acquisition closed loop.

Action family:

```text
ANSWER
READ_MEMORY
RETRIEVE
OBSERVE
ASK_USER
STOP_UNRESOLVED
```

For this synthetic oracle only, the deterministic equal-capability burden order is:

```text
READ_MEMORY < RETRIEVE < OBSERVE < ASK_USER
```

This is a test contract, not a universal ranking of real-world mechanisms.

The runtime owns mechanism eligibility/permission. Hidden truth and target are not mechanism-selection inputs.

Accepted exhaustive result:

- 512 evaluated examples;
- all 16 eligibility masks;
- answerable ANSWER rate `1.0`;
- required no-direct-ANSWER rate `1.0`;
- minimum-burden eligible mechanism rate `1.0`;
- no-eligible-mechanism STOP_UNRESOLVED rate `1.0`;
- ASK_USER avoided when self-service is eligible rate `1.0`;
- hidden counterfactual action invariance `1.0`;
- C37 and runtime fixture preserved;
- tracked tree clean.

C103 is oracle evidence only. It does not establish learned mechanism selection or real tool execution.

## C104 — ACTIVE

Experiment: `C104-v5e-supervised-acquisition-mechanism-selector`

Question:

> Can production `ControlLaneActionRouter` learn the C103 six-action mechanism policy from visible state plus explicit runtime eligibility bits, while generalizing to unseen `base=3` without hidden/target leakage?

Prospective configuration:

```text
fresh seeds      = 20261211, 20261212, 20261213
train bases      = 0,1,2
validation base  = 3 only
control width    = 4
hidden width     = 8
training steps   = 640
action count     = 6
```

C104 deliberately does not search for minimum hidden width. The action space has expanded from three to six actions, so hidden width 8 is used to test semantic learnability before a later capacity frontier.

Router inputs:

```text
working control lane:
  base
  dependency
  evidence_present
  observed_hidden

context control lane:
  memory_eligible
  retrieval_eligible
  observation_eligible
  ask_user_eligible
```

The eligibility mask is represented compositionally as four bits rather than one categorical 16-way ID. Operation token is constant. Target and missing hidden truth are never router inputs.

Training uses class-balanced batches because the fixed burden order makes `ASK_USER` and `STOP_UNRESOLVED` naturally rare under exhaustive masks.

Every fresh seed must satisfy on unseen base=3:

```text
action accuracy                                      = 1.0
minimum recall across all six actions                = 1.0
action flips vs oracle                               = 0
answerable ANSWER rate                               = 1.0
required no-direct-ANSWER rate                       = 1.0
minimum-burden eligible mechanism rate               = 1.0
no-eligible-mechanism STOP_UNRESOLVED rate           = 1.0
ASK_USER avoided when self-service eligible rate     = 1.0
ineligible predicted mechanism count                 = 0
missing-evidence hidden counterfactual invariance    = 1.0
```

C104 does not invoke real memory, retrieval, observation, or user interaction. Gate E remains NOT PASSED regardless of C104 result.
