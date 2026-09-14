# FOLD Experiment Ledger Addendum — C104 to C105

Date: 2026-09-14

## C104 — accepted

Experiment:

`C104-v5e-supervised-acquisition-mechanism-selector`

Question:

Can production `ControlLaneActionRouter` learn the C103 six-action mechanism-selection policy from visible evidence plus runtime-provided eligibility bits and generalize to unseen base=3?

Fixed conditions:

```text
fresh seeds      = 20261211,20261212,20261213
train bases      = 0,1,2
validation base  = 3 only
control width    = 4
hidden width     = 8
training steps   = 640
```

Action space:

```text
ANSWER
READ_MEMORY
RETRIEVE
OBSERVE
ASK_USER
STOP_UNRESOLVED
```

Accepted result across all three fresh seeds:

- validation action accuracy `1.0`;
- minimum six-class recall `1.0`;
- action flips `0`;
- answerable ANSWER rate `1.0`;
- decision-critical missing evidence never answered directly `1.0`;
- least-burden eligible mechanism selection `1.0`;
- no eligible mechanism -> STOP_UNRESOLVED `1.0`;
- ASK_USER avoided when self-service remained available `1.0`;
- ineligible mechanism predictions `0`;
- hidden counterfactual action invariance `1.0`;
- hidden/target input leakage false;
- C37 and fixture preserved;
- tracked tree clean.

Decision:

C104 is accepted. The current synthetic evidence supports learned six-action mechanism selection under a runtime-owned binary eligibility mask. It does not yet show that the selected mechanism can be executed and recovered from end-to-end.

## C105 — active prospective gate

Experiment:

`C105-v5e-learned-acquisition-mechanism-closed-loop`

Question:

Can the learned six-action selector execute a runtime-owned fallback chain on unseen base=3, using the next least-burden eligible mechanism after failure, committing evidence only on SUCCESS, and stopping unresolved only after all eligible fallbacks are exhausted?

Fixed conditions:

```text
fresh seeds       = 20261221,20261222,20261223
train bases       = 0,1,2
validation base   = 3 only
acquisition budget= 4
burden order      = READ_MEMORY < RETRIEVE < OBSERVE < ASK_USER
```

Runtime contract:

```text
selected mechanism SUCCESS
-> runtime commits validated hidden evidence
-> router re-observes
-> ANSWER

selected mechanism failure
-> runtime commits no evidence
-> failed mechanism becomes ineligible
-> router re-observes updated eligibility
-> choose next least-burden eligible mechanism

no eligible mechanism remains
-> STOP_UNRESOLVED
```

C105 evaluates, for every required validation mask:

- success at every possible eligible mechanism position after the corresponding failure prefix;
- all eligible mechanisms fail;
- answerable rows with zero acquisition.

Predeclared requirements for every fresh seed:

```text
answerable ANSWER rate                         = 1.0
answerable zero-acquisition rate               = 1.0
required scenario pass rate                    = 1.0
per-decision minimum-burden selection rate     = 1.0
eventual-success ANSWER rate                   = 1.0
eventual-success final accuracy                = 1.0
all-fail STOP_UNRESOLVED rate                  = 1.0
failed-attempt no-evidence-commit rate         = 1.0
ineligible mechanism count                     = 0
repeat failed mechanism count                  = 0
budget violation count                         = 0
ASK_USER before self-service exhaustion count  = 0
hidden counterfactual action-trace invariance  = 1.0
```

Additional strict rule:

A STOP_UNRESOLVED action is invalid while any eligible fallback mechanism remains. The execution wrapper converts such premature stopping into a scientific gate failure.

C105 remains synthetic. It does not invoke real memory, retrieval, observation, or user interaction and does not establish Gate E passage by itself.
