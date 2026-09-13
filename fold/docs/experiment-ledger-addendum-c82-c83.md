# FOLD Experiment Ledger Addendum — C82 / C83

Date: 2026-09-14

## C82 accepted serialized-artifact gate

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

The primary practical objective is now explicit:

> Minimize operational VRAM occupied by FOLD so other applications retain usable GPU-memory headroom.

Therefore future references to model "lightness" should prioritize operational VRAM/headroom over checkpoint file size. Serialized artifact size remains a supporting deployment/storage metric.

Primary operational measurements:

1. incremental device VRAM consumed after CUDA context initialization;
2. remaining free device VRAM / headroom;
3. peak PyTorch allocated memory;
4. peak PyTorch reserved memory;
5. resident model allocation;
6. latency as a secondary practicality constraint.

## C83 active VRAM/headroom gate

Experiment: `C83-shared-basis-production-vram-headroom`

Tracked files:

- `fold/fold_lm/v05_benchmarks/gate_c_shared_basis_c83_vram_helpers.py`
- `fold/fold_lm/v05_benchmarks/gate_c_shared_basis_production_vram_headroom.py`
- `fold/scripts/run_c83.ps1`

Shape:

- width `5120`;
- slots `20`;
- modules `2`;
- hidden_mult `2`;
- batches `1, 8`;
- profiles `1/16`, `1/8`, `3/16`.

Each Dense/Shared point runs in a fresh Python process. CUDA context is initialized before the baseline is captured.

Primary metric:

```text
incremental_device_vram_consumed
= baseline_free_vram_after_cuda_context
- inference_ready_free_vram
```

This measures how much additional device VRAM the model/runtime removes from the pool available to other applications.

Each point is repeated three times; medians are used for comparison.

Predeclared C83 gate for every Shared profile and both batches:

- output remains finite;
- median incremental device VRAM consumption is lower than Dense;
- median headroom gain versus Dense is at least `0.15 GiB`;
- median peak allocated VRAM is lower than Dense;
- median peak reserved VRAM is lower than Dense.

C83 is the new authoritative lightness gate because VRAM headroom is the primary product objective. Gate C remains not formally passed until C83 is judged together with the accepted quality/runtime/storage evidence.
