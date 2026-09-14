# FOLD Experiment Ledger Addendum — C102 to C103

Date: 2026-09-14

## C102 — ACCEPTED

Experiment: `C102-v5e-learned-acquisition-outcome-closed-loop`

C102 completed validly on commit `343fcc647b91cb58ba2407147aa3e61a35b54063`.

Fresh seeds: `20261201..20261203`. Training bases: `0,1,2`. Validation base: unseen `3`.

All three seeds achieved:

- initial required acquisition recall `1.0`;
- initial answerable ANSWER rate `1.0`;
- unnecessary acquisition rate `0.0`;
- SUCCESS evidence commit rate `1.0`;
- SUCCESS post-acquisition ANSWER rate `1.0`;
- SUCCESS final accuracy `1.0`;
- failure STOP_UNRESOLVED rate `1.0`;
- failure no-evidence-commit rate `1.0`;
- failure no-guessed-answer rate `1.0`;
- premature STOP count `0`;
- repeat acquisition count `0`;
- budget violation count `0`.

C37 and the runtime fixture were preserved and the tracked repository remained clean.

Interpretation: the abstract learned V5-E policy now closes the full success/failure trajectory:

```text
critical missing evidence
-> predicted ACQUIRE
-> runtime owns outcome and authoritative mutation
-> SUCCESS: commit + reobserve + predicted ANSWER
-> failure: no commit + reobserve + predicted STOP_UNRESOLVED
```

C102 does not establish Gate E passage because the acquisition mechanism is still abstract.

## C103 — ACTIVE

Experiment: `C103-v5e-acquisition-mechanism-oracle`

Question:

> When decision-critical evidence is missing, can a reference policy choose the least-burden runtime-eligible acquisition mechanism, avoid unnecessary user questions, and stop unresolved when no mechanism is eligible?

Action family:

```text
ANSWER
READ_MEMORY
RETRIEVE
OBSERVE
ASK_USER
STOP_UNRESOLVED
```

C103 synthetic burden order:

```text
READ_MEMORY < RETRIEVE < OBSERVE < ASK_USER
```

This ordering is only a deterministic oracle contract for C103; it is not a universal product ranking.

Runtime owns the eligibility/permission mask. Hidden truth and target are not used for mechanism selection.

C103 enumerates all 16 eligibility masks. Required gate:

- answerable rows choose ANSWER at rate `1.0`;
- decision-critical missing rows never direct-answer: `1.0`;
- least-burden eligible mechanism selected: `1.0`;
- no eligible mechanism -> STOP_UNRESOLVED: `1.0`;
- ASK_USER avoided whenever an eligible self-service mechanism exists: `1.0`;
- hidden=0/1 missing-evidence counterfactuals produce identical mechanism actions: `1.0`.

C103 is an oracle semantics baseline only. No real memory, retrieval, observation, or user interaction is invoked.
