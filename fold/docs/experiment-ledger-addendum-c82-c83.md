# FOLD Experiment Ledger Addendum — C82 / C83

Date: 2026-09-14

## C82 — accepted serialized-artifact gate

Experiment: `C82-shared-basis-production-serialized-artifact`

Status: **PASS**.

Representative width3072 results:

- lean 1/16 serialized ratio: `0.7136684395`;
- medium 1/8 serialized ratio: `0.7605224490`;
- rank3_bridge 3/16 serialized ratio: `0.8073766615`;
- all ratios <= predeclared `0.83` ceiling;
- all state_dict round-trips exact;
- no materialized/effective routed-weight bank stored in Shared-Basis state_dict;
- protected C37 result and runtime fixture preserved;
- tracked repository clean.

C82 is accepted as the storage-artifact result.

## Model-weight priority clarification

The primary practical objective is explicit:

> Minimize operational VRAM occupied by FOLD so other applications retain usable GPU-memory headroom.

Therefore references to model "lightness" should prioritize operational VRAM/headroom over checkpoint file size. Serialized artifact size remains a supporting deployment/storage metric.

Primary operational measurements:

1. incremental device VRAM consumed after CUDA context initialization;
2. remaining free device VRAM / headroom;
3. peak PyTorch allocated memory;
4. peak PyTorch reserved memory;
5. resident model allocation;
6. latency as a secondary practicality constraint.

## C83 — accepted VRAM/headroom priority gate

Experiment: `C83-shared-basis-production-vram-headroom`

Status: **PASS**.

Shape:

- width `5120`;
- slots `20`;
- modules `2`;
- hidden_mult `2`;
- batches `1, 8`;
- profiles `1/16`, `1/8`, `3/16`.

Each Dense/Shared point ran in a fresh Python process. CUDA context was initialized before the baseline was captured. Each point used 3 repeats and median comparison.

Primary metric:

```text
incremental_device_vram_consumed
= baseline_free_vram_after_cuda_context
- inference_ready_free_vram
```

Predeclared gate for every Shared profile and both batches:

- output finite;
- median incremental device VRAM consumption lower than Dense;
- median headroom gain versus Dense at least `0.15 GiB`;
- median peak allocated VRAM lower than Dense;
- median peak reserved VRAM lower than Dense.

Accepted results:

| profile | batch | Dense ready VRAM | Shared ready VRAM | headroom gain |
|---|---:|---:|---:|---:|
| lean 1/16 | 1 | 1.2421875 GiB | 0.9140625 GiB | **0.328125 GiB** |
| medium 1/8 | 1 | 1.2421875 GiB | 0.966796875 GiB | **0.275390625 GiB** |
| 3/16 | 1 | 1.2421875 GiB | 1.021484375 GiB | **0.220703125 GiB** |
| lean 1/16 | 8 | 1.26171875 GiB | 0.951171875 GiB | **0.310546875 GiB** |
| medium 1/8 | 8 | 1.26171875 GiB | 1.00390625 GiB | **0.2578125 GiB** |
| 3/16 | 8 | 1.26171875 GiB | 1.05859375 GiB | **0.203125 GiB** |

Additional accepted facts:

- all outputs finite;
- all Shared headroom gains exceeded the `0.15 GiB` threshold;
- all Shared peak allocated values were below Dense;
- all Shared peak reserved values were below Dense;
- protected C37 result preserved;
- runtime fixture preserved;
- tracked repository clean;
- `production_vram_headroom_gate_passed = true`.

Inference-ready VRAM reduction relative to Dense is approximately 16% to 26% over the tested profiles/batches.

## Gate C decision

After C83, the cumulative accepted evidence satisfies the V5-C roadmap gate for the registered synthetic scope:

- quality/capacity evidence accepted;
- final selected-rank recurrence and numerical equivalence accepted;
- production training/inference execution policy accepted;
- production large-shape runtime practical;
- resident and serialized storage clearly lower;
- operational VRAM/headroom clearly improved under the project's primary lightness objective.

**Gate C: PASSED, scoped to the registered V5 synthetic task/runtime regime.**

Formal decision record:

`fold/docs/gate-c-decision-2026-09-14.md`

This is not a claim of broad LLM or Transformer superiority.

## Next stage

Proceed to **V5-D — adaptive computation and routing**.
