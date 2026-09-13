# FOLD Experiment Ledger Addendum — C85 / C86

Date: 2026-09-14

## C85 accepted supervised-router plumbing gate

Experiment: `C85-v5d-condition-supervised-action-router`

Status: **PASS**.

Fresh seeds: `20261101, 20261102, 20261103`.

Action space:

```text
ANSWER
COMPUTE(update,1)
```

Controller observations:

- current working state;
- candidate event context;
- explicit observable operation token.

The oracle action/target is not passed as a separate controller input.

Accepted result:

- action accuracy: `1.0` on every seed;
- HOLD->ANSWER recall: `1.0` on every seed;
- UPDATE->COMPUTE recall: `1.0` on every seed;
- exhaustive exact delta vs C84 oracle: `0.0` on every seed;
- mean logical compute actions/event: `0.4999213965`;
- mean logical ANSWER rate: `0.5000786035`;
- protected C37 result and runtime fixture preserved;
- tracked repository clean;
- `supervised_router_gate_passed = true`.

Interpretation:

C85 verifies supervised action-router plumbing and dynamic ANSWER/COMPUTE execution on the tiny Condition task. It is intentionally easy because the observable operation token almost directly determines the oracle action. It does not yet demonstrate difficulty-dependent compute depth or Gate D passage.

## C86 active variable-step oracle baseline

Experiment: `C86-v5d-composition-variable-step-oracle`

Tracked files:

- `fold/fold_lm/v05_benchmarks/gate_d_c86_variable_step_helpers.py`
- `fold/fold_lm/v05_benchmarks/gate_d_composition_variable_step_oracle.py`
- `fold/scripts/run_c86.ps1`

C86 moves from binary ANSWER/COMPUTE to variable compute depth on the existing Composition task.

Observable operand magnitude defines the first explicit difficulty axis:

```text
operand 0 -> ANSWER/no-op              -> 0 unit steps
operand 1 -> COMPUTE(operation, 1)     -> 1 unit step
operand 2 -> COMPUTE(operation, 2)     -> 2 unit steps
```

The core is trained to apply one signed unit transition per step. Evaluation compares:

1. fixed-max execution: always evaluate two substeps/event and mask inactive results;
2. sparse oracle execution: gather only active rows and execute exactly the operand-count steps.

The deterministic Composition validation split contains operand 0/1/2 exactly equally, so the oracle target is exactly `1.0` logical step/event versus a fixed maximum of `2.0`, corresponding to 50% logical compute reduction.

Fresh seeds:

`20261111, 20261112, 20261113`.

Predeclared C86 gate:

- every seed sparse-oracle trajectory exact accuracy >= `0.99`;
- all sparse-oracle outputs allclose to fixed-max masked outputs;
- logical compute steps/event <= `1.05`;
- zero-step event rate >= `0.30`;
- two-step event rate >= `0.30`;
- compute reduction vs fixed two-step execution >= `0.45`.

C86 remains an oracle baseline. Expanded-action supervised routing is deferred to the next experiment if C86 passes. Gate D remains unpassed.
