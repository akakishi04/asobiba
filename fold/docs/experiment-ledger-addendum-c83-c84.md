# FOLD Experiment Ledger Addendum — C83 / C84

Date: 2026-09-14

## C83 — accepted operational VRAM/headroom gate

Experiment: `C83-shared-basis-production-vram-headroom`

Status: **PASS**.

Primary metric:

```text
incremental_device_vram_consumed
= baseline_free_vram_after_cuda_context
- inference_ready_free_vram
```

Fresh-process width5120 results, 3 repeats/point:

| profile | batch | Dense ready | Shared ready | headroom gain |
|---|---:|---:|---:|---:|
| 1/16 | 1 | 1.2421875 GiB | 0.9140625 GiB | 0.328125 GiB |
| 1/8 | 1 | 1.2421875 GiB | 0.966796875 GiB | 0.275390625 GiB |
| 3/16 | 1 | 1.2421875 GiB | 1.021484375 GiB | 0.220703125 GiB |
| 1/16 | 8 | 1.26171875 GiB | 0.951171875 GiB | 0.310546875 GiB |
| 1/8 | 8 | 1.26171875 GiB | 1.00390625 GiB | 0.2578125 GiB |
| 3/16 | 8 | 1.26171875 GiB | 1.05859375 GiB | 0.203125 GiB |

Every point exceeded the predeclared `0.15 GiB` headroom-gain threshold. Peak allocated and peak reserved VRAM were below Dense for every Shared profile/batch.

Decision: operational VRAM/headroom objective is satisfied in the tested V5-C production regime.

## Gate C closure

After C83, cumulative C76-C83 evidence satisfies the V5-C roadmap gate in the registered scope.

**Gate C: PASSED (scoped).**

Formal decision:

`fold/docs/gate-c-decision-2026-09-14.md`

The main handoff has been refreshed to mark V5-C closed and V5-D active.

## C84 — active first V5-D oracle action baseline

Experiment:

`C84-v5d-condition-answer-noop-oracle-baseline`

Purpose: register the minimal V5-D action semantics before training any controller.

Condition currently has authoritative HOLD/UPDATE operations. C84 tests the minimal semantic policy:

```text
HOLD   -> ANSWER / no-op
UPDATE -> COMPUTE(update_module, 1)
```

This asks whether HOLD can consume zero core updates without materially degrading exhaustive task quality.

Fresh seeds:

```text
20261031, 20261032, 20261033
```

Production core:

- `SharedBasisFixedRoutingCore`;
- rank3;
- training execution mode `materialized`;
- inference execution mode `gemm_native`.

Predeclared C84 gate:

- mean exhaustive trajectory-exact delta vs current teacher-routed reference >= `-0.002`;
- logical compute actions per event <= `0.55`;
- logical ANSWER/no-op rate >= `0.45`.

Important: C84 reports logical action/computation savings only. It does not yet claim sparse GPU wall-clock speedup and does not train a routing controller.

If C84 passes, the next V5-D step can build the first supervised routing target/interface around the accepted ANSWER vs COMPUTE semantics. If it fails, HOLD must remain a compute action or the action semantics must be redesigned before controller learning.
