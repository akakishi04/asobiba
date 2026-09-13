# FOLD Addendum — C85 / C86 / C87

Date: 2026-09-14

## C85 accepted

`C85-v5d-condition-supervised-action-router`: PASS.

- 3/3 seeds action accuracy = 1.0.
- HOLD->ANSWER recall = 1.0.
- UPDATE->COMPUTE recall = 1.0.
- exact delta vs C84 oracle = 0.0.
- compute actions/event ~= 0.5.

This proves supervised routing plumbing, not difficult adaptive reasoning.

## C86 accepted

`C86-v5d-composition-variable-step-oracle`: PASS.

Oracle depth: operand 0/1/2 -> compute depth 0/1/2.

- 3/3 seeds trajectory exact = 1.0.
- sparse vs fixed-max outputs allclose.
- mean compute = 1.0 step/event.
- zero-step rate = 1/3.
- two-step rate = 1/3.
- compute reduction vs fixed two-step = 50%.

This establishes difficulty-dependent variable compute depth at oracle level. It is not yet a wall-clock speedup claim.

## C87 active

Action space: `ANSWER, ADD1, ADD2, SUB1, SUB2`.

Fresh seeds: `20261121, 20261122, 20261123`.

Predeclared gate:

- action accuracy >= 0.995 every seed;
- minimum five-class recall >= 0.99 every seed;
- trajectory exact >= 0.99 every seed;
- mean exact delta vs C86 oracle >= -0.002;
- compute steps/event <= 1.05;
- zero-step and two-step rates >= 0.30;
- compute reduction vs fixed two-step >= 0.45.

Gate D remains NOT PASSED. After C87, actual sparse wall-clock/runtime benefit must be measured separately.
