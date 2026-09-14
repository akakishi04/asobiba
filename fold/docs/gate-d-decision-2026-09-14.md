# FOLD Gate D Decision — 2026-09-14

Status: **PASSED, scoped to the registered V5 synthetic adaptive-routing/runtime regime.**

This decision does **not** claim general LLM routing superiority, broad language reasoning quality, or universal speedup over Transformer systems.

## 1. Roadmap contract

`development-roadmap-v0.5.md` defines Gate D by four requirements:

1. harder cases use additional compute steps meaningfully;
2. easy cases use less average compute than a fixed maximum-step baseline;
3. the router does not merely stop early by sacrificing quality;
4. routing-head compression/action flips are measured and unacceptable flips are avoided.

The initial training plan also mentions supervised routing followed later by on-policy recovery. On-policy recovery remains desirable robustness work, but it is not listed as an additional Gate-D acceptance bullet. This decision therefore records it as deferred rather than silently claiming it was completed.

## 2. Accepted evidence chain

### C84 — ANSWER/no-op oracle semantics

Condition HOLD was mapped to `ANSWER/no-op`, UPDATE to `COMPUTE(update,1)`.

Accepted result:

- mean exhaustive exact delta vs teacher-routed baseline: `+0.00206078`;
- logical compute actions/event: `0.499894`;
- ANSWER/no-op rate: `0.500106`;
- no quality loss established.

This established zero-compute semantics for an easy/no-op case.

### C85 — supervised ANSWER/COMPUTE wiring

A learned controller reproduced the two-action oracle policy.

Accepted result:

- action accuracy: `1.0` across all registered seeds;
- class recalls: `1.0`;
- exact delta vs C84 oracle: `0.0`;
- compute/event remained approximately `0.5`.

### C86 — oracle variable-depth compute

Composition operand magnitude defined a controlled difficulty axis:

```text
operand 0 -> 0 steps
operand 1 -> 1 step
operand 2 -> 2 steps
```

Accepted result:

- trajectory exact: `1.0` across all seeds;
- sparse vs fixed-max outputs allclose;
- mean compute: `1.0 step/event`;
- fixed-max baseline: `2.0 steps/event`;
- logical compute reduction: `50%`.

### C87 — learned five-action variable-depth routing

Action space:

```text
ANSWER
ADD1
ADD2
SUB1
SUB2
```

Accepted result:

- action accuracy: `1.0`;
- minimum five-class recall: `1.0`;
- trajectory exact: `1.0`;
- exact delta vs C86 oracle: `0.0`;
- learned vs oracle outputs allclose;
- mean compute: `1.0 step/event`;
- fixed-max reduction: `50%`.

This established learned difficulty-dependent 0/1/2-step routing on the registered synthetic task.

### C88 — valid negative tiny-width runtime result

At Composition width `32`, the eager learned sparse path was slower despite 50% logical compute reduction:

- adaptive/fixed device latency mean: `1.50084x`;
- adaptive/fixed wall latency mean: `1.38403x`;
- outputs allclose.

This prevented a false claim that lower logical compute automatically means lower wall-clock time.

### C89 — runtime crossover diagnosis

A width sweep found the current eager sparse execution becomes practically beneficial at larger widths.

Router-inclusive crossover under the predeclared `<=0.95x` device-and-wall rule occurred at width `3072`.

At width `5120`:

- router-inclusive device ratio: approximately `0.6127x`;
- router-inclusive wall ratio: approximately `0.6359x`.

C89 used oracle execution actions after paying controller cost, so it was mechanism evidence, not the final learned-action runtime gate.

### C90-C95 — controller capacity and Control Lane

C90 found hidden width `4` was the smallest tiny-task quality-passing controller point, using about `18.98%` of the default hidden-32 router bytes.

C91 was a valid negative result: the width-coupled full-state hidden-4 controller collapsed at width `3072/5120`. Its apparent speedups were rejected because routing quality failed.

C92-C94 diagnosed the failure. A fixed-width Control Lane decoupled router learning from core width:

- all reused diagnostic conditions recovered by at most 480 steps;
- for each seed, first passing checkpoint matched exactly between width 3072 and width 5120.

C95 then used fresh seeds and held-out rows prospectively:

- six width/seed conditions;
- held-out action accuracy: `1.0` in every condition;
- minimum class recall: `1.0` in every condition;
- total held-out action flips: `0`;
- diagnostic Control-Lane router persistent bytes: `436`.

This satisfied the routing-head/control-path compression robustness requirement in the registered scope.

### C96 — production Control Lane learned-action runtime/VRAM gate

Production `ControlLaneActionRouter` was evaluated at widths `3072` and `5120`, three fresh seeds each, using actual predicted actions for sparse execution.

All six conditions passed the prospectively declared gates.

Quality and routing:

- held-out action accuracy minimum: `1.0`;
- held-out minimum class recall: `1.0`;
- runtime action accuracy minimum: `1.0`;
- runtime minimum class recall: `1.0`;
- outputs vs fixed-max: allclose.

Adaptive compute:

- logical compute reduction vs fixed-max: `50%` in every condition.

Runtime:

- learned/fixed device ratio mean: `0.581919`;
- learned/fixed device ratio maximum: `0.649631`;
- learned/fixed wall ratio mean: `0.587959`;
- learned/fixed wall ratio maximum: `0.653782`.

Thus the production adaptive path was roughly 35% to 48% faster than fixed-max in the tested large-width regime while preserving the registered output semantics.

Controller footprint:

- router/core persistent ratio maximum: `1.3481e-06`;
- measured incremental device-free-VRAM cost of adding the router: `0.0 GiB` at the measurement resolution;
- production router parameter count is independent of core width under the selected fixed Control Lane configuration.

## 3. Gate-D requirement mapping

| Gate-D requirement | Evidence | Decision |
|---|---|---|
| Harder cases use more steps | C86 oracle and C87 learned 0/1/2-step policy | PASS |
| Easy cases reduce average compute vs fixed max | C86/C87/C96: 1.0 vs 2.0 steps/event, 50% reduction | PASS |
| No premature-stop quality sacrifice | C87 exact quality; C95/C96 fresh held-out/runtime routing = 1.0; C96 outputs allclose | PASS |
| Routing-head compression/action flips controlled | C90 capacity frontier; C95 fresh held-out action flips = 0; C96 compact production Control Lane | PASS |

## 4. Production candidate after Gate D

Lead V5-D controller candidate:

```text
ControlLaneActionRouter
```

Current registered synthetic configuration:

```text
control_width = 4
hidden_width  = 4
action space  = ANSWER / ADD1 / ADD2 / SUB1 / SUB2
```

Design principle supported by C91-C96:

> Main working-state width and routing-control width should be independent capacity axes.

The current first-four-channel Control Lane is a validated production prototype for the registered task, not a claim that `control_width=4` is universally sufficient. Future tasks may require a larger or explicitly learned semantic control state.

## 5. Important negative evidence retained

Gate D is not recorded as a clean sequence of only positive experiments.

- C88 showed tiny-width sparse execution can be slower than fixed-max.
- C91 showed aggressively compact routing can become invalid if the controller representation remains coupled to the full core width.
- C92-C94 showed that representation/optimization failure can masquerade as a pure capacity problem.

These negative results remain part of the accepted design evidence and constrain future routing changes.

## 6. Scope and non-claims

Gate D PASS is limited to:

- registered synthetic Condition/Composition routing tasks;
- the tested 0/1/2-step adaptive-compute semantics;
- the current five-action Composition routing table;
- float32/current Shared-Basis execution family;
- production Control Lane configuration tested at widths 3072 and 5120;
- balanced runtime batch 216;
- current eager sparse `nonzero/index_select/index_copy` execution;
- current Windows/CUDA/PyTorch/RTX 4070 Ti SUPER environment.

It does not establish:

- broad language or reasoning routing quality;
- generalization to large action spaces;
- on-policy recovery after self-induced routing errors;
- universal optimality of control width 4 or hidden width 4;
- universal speedup at tiny widths or arbitrary batch sizes;
- superiority over Transformer routing/MoE/adaptive-compute systems.

## 7. Next stage

V5-D is closed under the scope above.

Proceed to **V5-E — information acquisition / knowing when internal compute is insufficient**.

The roadmap next expands the action space with candidates such as:

```text
PARTIAL_ANSWER
READ_MEMORY
RETRIEVE
OBSERVE
ASK_USER
STOP_UNRESOLVED
```

Initial V5-E work should preserve the new separation:

```text
large semantic/working state
+
small explicit control state / Control Lane
+
bounded action selection
```

Do not mix FOLD-R memory integration or Vision into the first V5-E experiment.
