# FOLD Experiment Ledger Addendum — C97 to C98

Date: 2026-09-14

## C97 — accepted V5-E oracle information-sufficiency baseline

C97 executed validly and the oracle semantic gate passed.

Registered action space:

```text
ANSWER
ACQUIRE
```

Oracle rule:

```text
missing hidden condition AND target can change -> ACQUIRE
otherwise                                  -> ANSWER
```

The exhaustive 32-row synthetic space included both critical missing counterfactual pairs and negative-control pairs where the same hidden condition was absent but irrelevant to the target.

Accepted result:

- critical missing counterfactual pairs: 4;
- irrelevant missing counterfactual pairs: 4;
- required acquisition recall: 1.0;
- unnecessary acquisition rate: 0.0;
- ambiguous direct-answer attempts: 0;
- direct-answerable accuracy: 1.0;
- irrelevant-missing direct accuracy: 1.0;
- post-policy final accuracy: 1.0;
- direct-answer coverage: 0.75.

Interpretation:

C97 establishes the semantic boundary between missing information that matters to the conclusion and missing information that does not. It is an oracle baseline only. It does not establish a learned acquisition controller and does not select an acquisition mechanism.

## C98 — prospective supervised sufficiency router

C98 asks whether the production fixed-width `ControlLaneActionRouter` can learn the C97 `ANSWER / ACQUIRE` policy from visible evidence only.

Fixed prospective conditions:

```text
fresh seeds      = 20261171, 20261172, 20261173
train bases      = 0, 1, 2
validation base  = 3 only (unseen during training)
control width    = 4
hidden width     = 4
training steps   = 320
```

Router-visible features:

```text
base
dependency
evidence_present
observed_hidden
```

When evidence is missing, `observed_hidden` is forced to zero and counterfactual hidden=0/1 rows are verified to have exactly identical router inputs. The hidden truth, target answer, and oracle action are not supplied as router inputs.

C98 passes only if every fresh seed satisfies on the held-out unseen base:

```text
action accuracy                   = 1.0
required acquisition recall       = 1.0
unnecessary acquisition rate      = 0.0
action flips                      = 0
ambiguous direct-answer attempts  = 0
post-policy final accuracy        = 1.0
```

C98 remains a synthetic binary sufficiency-routing experiment. `ACQUIRE` is still abstract; memory/retrieval/observation/user-question mechanism selection is deferred.
