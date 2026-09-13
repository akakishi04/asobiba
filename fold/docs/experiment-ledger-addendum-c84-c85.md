# FOLD Experiment Ledger Addendum — C84 / C85

Date: 2026-09-14

## C84 accepted V5-D oracle baseline

Experiment: `C84-v5d-condition-answer-noop-oracle-baseline`

Status: **PASS**.

Fresh seeds: `20261031, 20261032, 20261033`.

Oracle action semantics:

```text
HOLD   -> ANSWER / no-op
UPDATE -> COMPUTE(update, 1)
```

Accepted exhaustive results:

- mean exact delta vs current dual-route baseline: `+0.002060777559055118`;
- mean logical compute actions/event: `0.4998940562117235`;
- mean ANSWER/no-op rate: `0.5001059437882764`;
- all protected artifacts preserved;
- tracked repository clean;
- `answer_noop_oracle_gate_passed = true`.

Interpretation:

The Condition task can skip core computation on HOLD events and compute only on UPDATE events without quality loss. On this tiny task the oracle policy actually improves exhaustive exact accuracy slightly. This is a logical-compute result only; it is not yet sparse GPU wall-clock speedup.

## C85 active supervised-router gate

A minimal production-facing controller now exists at:

`fold/fold_lm/v05/controller.py`

Controller action space:

```text
ANSWER
COMPUTE(update, 1)
```

The controller observes:

- current working state;
- candidate event context;
- explicit observable operation token.

The oracle action/target is not passed as a separate input. The operation token is intentionally explicit because the existing Condition core context does not encode HOLD/UPDATE semantics; without an observable operation signal, the routing decision would be unidentifiable from the current task representation.

C85 uses fresh seeds:

`20261101, 20261102, 20261103`.

Predeclared gate:

- every seed action accuracy >= `0.995`;
- HOLD->ANSWER recall >= `0.995`;
- UPDATE->COMPUTE recall >= `0.995`;
- mean exhaustive exact delta vs C84 oracle >= `-0.002`;
- logical compute actions/event <= `0.55`;
- logical ANSWER rate >= `0.45`.

C85 is a supervised routing-plumbing gate, not a claim of difficult adaptive reasoning. Gate D remains unpassed until later experiments show useful difficulty-dependent computation, reduced average compute against fixed maximum-step baselines, and no quality collapse.
