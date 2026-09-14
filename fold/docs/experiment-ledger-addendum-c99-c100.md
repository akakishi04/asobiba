# FOLD Experiment Ledger Addendum — C99 to C100

Date: 2026-09-14
Stage: V5-E

## C99 — accepted learned acquisition closed loop

Experiment: `C99-v5e-acquire-reobserve-answer-cycle`

Accepted result across fresh seeds `20261181..20261183`, with train bases `0/1/2` and unseen validation base `3`:

- required acquisition recall: `1.0`;
- unnecessary acquisition rate: `0.0`;
- required cases acquired exactly once: `1.0`;
- answerable cases acquired zero times: `1.0`;
- post-acquisition ANSWER rate: `1.0`;
- repeat acquisition count: `0`;
- budget violation count: `0`;
- ambiguous direct-answer attempts: `0`;
- post-cycle final accuracy: `1.0`.

Authority boundary accepted for this synthetic scope:

```text
model proposes ACQUIRE
-> runtime performs the acquisition and mutates authoritative evidence state
-> model re-observes updated state
-> model chooses ANSWER
```

C99 does not establish Gate E passage. Acquisition success was deterministic and acquisition failure/permission denial were not tested.

## C100 — active oracle acquisition-failure gate

Experiment: `C100-v5e-acquisition-failure-oracle`

Question:

> When required acquisition does not yield trusted evidence, can the reference policy terminate safely without committing false evidence, retrying past budget, or inventing an answer?

Registered outcomes:

```text
SUCCESS
UNAVAILABLE
DENIED
INVALID
```

Registered action space:

```text
ANSWER
ACQUIRE
STOP_UNRESOLVED
```

Semantics:

```text
SUCCESS
-> runtime commits validated evidence
-> reobserve
-> ANSWER

UNAVAILABLE / DENIED / INVALID
-> runtime does not commit evidence
-> reobserve acquisition outcome
-> STOP_UNRESOLVED
```

Budget: exactly one acquisition attempt for a missing critical fact.

Prospective C100 gate:

- answerable rows acquire zero times: `1.0`;
- SUCCESS post-acquisition ANSWER rate: `1.0`;
- SUCCESS final accuracy: `1.0`;
- SUCCESS evidence commit rate: `1.0`;
- failure STOP_UNRESOLVED rate: `1.0`;
- failure no-evidence-commit rate: `1.0`;
- failure no-guessed-answer rate: `1.0`;
- repeat acquisition count: `0`;
- budget violation count: `0`.

C100 is an oracle semantics baseline only. Learned STOP_UNRESOLVED behavior belongs to a later experiment.
