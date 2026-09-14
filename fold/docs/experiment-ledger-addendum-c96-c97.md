# FOLD Addendum — C96 / Gate D / C97

Date: 2026-09-14

## C96 accepted

`C96-v5d-production-control-lane-runtime-vram`: PASS.

Production `ControlLaneActionRouter`, widths 3072/5120, three fresh seeds each:

- held-out action accuracy = 1.0 in all conditions;
- held-out minimum class recall = 1.0;
- runtime action accuracy = 1.0;
- runtime minimum class recall = 1.0;
- logical compute reduction vs fixed-max = 50%;
- learned/fixed device ratio maximum = 0.649631;
- learned/fixed wall ratio maximum = 0.653782;
- router/core persistent ratio maximum = 1.3481e-06;
- measured router incremental device-free-VRAM cost = 0.0 GiB at measurement resolution;
- outputs allclose.

## Gate D decision

Gate D is formally PASSED, scoped to the registered V5 synthetic adaptive-routing/runtime regime.

Decision document:

`fold/docs/gate-d-decision-2026-09-14.md`

The pass does not claim broad language-routing quality, universal control width 4, universal speedup, or on-policy recovery.

## C97 active

Stage moves to V5-E.

Scientific question:

> Can an oracle information-sufficiency policy answer directly when visible evidence is sufficient, acquire only when a missing hidden condition can change the conclusion, and avoid both guessing missing critical facts and asking for irrelevant missing facts?

Minimal action space:

```text
ANSWER
ACQUIRE
```

C97 is exhaustive and synthetic. It does not train a controller and does not integrate memory, retrieval, external tools, or Vision.

Acceptance requires:

- at least one same-visible-input counterfactual pair whose hidden condition changes the target;
- at least one missing-but-irrelevant counterfactual pair whose target is unchanged;
- required acquisition recall = 1.0;
- unnecessary acquisition rate = 0.0;
- no direct-answer attempt on ambiguous missing-critical rows;
- direct-answerable accuracy = 1.0;
- irrelevant-missing direct accuracy = 1.0;
- post-policy final accuracy after abstract acquisition = 1.0.
