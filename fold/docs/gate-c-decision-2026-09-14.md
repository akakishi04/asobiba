# FOLD V5-C Gate Decision — 2026-09-14

## Decision

**Gate C: PASSED, scoped to the registered V5 synthetic task/runtime regime.**

This is not evidence that FOLD broadly outperforms Transformer LLMs. It means the current Shared-Basis candidate satisfies the V5-C gate under the tested tasks, ranks, hardware, precision, and runtime conditions.

## Accepted candidate

```text
W_module = W_base + A_module @ B_shared
```

Selected task capacities:

```text
Condition   rank3
Composition rank2
Language    rank4
```

Accepted production execution policy:

```text
training  -> materialized arithmetic
inference -> GEMM-native arithmetic
```

The same persistent Shared-Basis parameters/checkpoint are used in both modes.

## Gate C evidence chain

### Quality / capacity

- Composition rank2 recovered the accepted task quality across repeated seeds.
- Language rank4 is the accepted stable capacity point under aligned training.
- Condition rank3 passed the prospectively declared independent-seed non-inferiority gate against accepted rank4 in C76:
  - 24 fresh seeds;
  - mean rank3-rank4 exact delta `-0.0000794604421`;
  - one-sided 95% bootstrap lower bound `-0.000512627388`;
  - prospective margin `-0.002`;
  - non-inferiority PASS.

### Numerical / recurrent stability

C77 final selected-rank refresh:

- validation scores equal for all 9 runs;
- validation semantics equal;
- validation tensors allclose;
- recurrence depths 1/2/4/8/16/32/64 allclose;
- max recurrence absolute gap `9.72747802734375e-05`;
- max recurrence relative-L2 gap `2.7345954560493825e-06`.

### Production training/inference policy

C78 showed that direct GEMM-native arithmetic during optimization accumulates small float-order drift over long training, despite matching initial weights/gradients and preserving scores/semantics.

C79 localized that drift to GEMM-native arithmetic order rather than the production parameter layout or AdamW policy.

C80 then validated the explicit production policy on fresh Language seeds:

- materialized training parameters exactly match the accepted materialized reference;
- materialized validation outputs exactly match;
- switching the same checkpoint to GEMM-native preserves score and semantics;
- native validation max-abs gap `1.9073486328125e-06`;
- V5 regression suite passed.

### Production runtime practicality

C81 measured the actual production `SharedBasisFixedRoutingCore` at widths 1024/3072/5120.

At width5120:

| profile | persistent ratio | batch1 latency | batch8 latency |
|---|---:|---:|---:|
| 1/16 | 0.713616 | 1.05653x | 1.06662x |
| 1/8 | 0.760479 | 1.06485x | 1.10225x |
| 3/16 | 0.807342 | 1.11150x | 1.14160x |

All production outputs were allclose. The predeclared production runtime/storage ceilings passed.

### Serialized production artifact

C82 width3072 state_dict measurements:

| profile | serialized ratio | resident ratio |
|---|---:|---:|
| 1/16 | 0.713668 | 0.713666 |
| 1/8 | 0.760522 | 0.760521 |
| 3/16 | 0.807377 | 0.807375 |

All state_dict round-trips were exact and no materialized effective-weight bank was serialized.

### Primary lightness objective: VRAM headroom

The project priority was clarified before C83: model lightness is primarily the operational VRAM consumed by FOLD, so other applications retain usable VRAM headroom.

C83 measured Dense and Shared-Basis in separate fresh processes after CUDA context initialization, using 3 repeats and medians.

Width5120 results:

| profile | batch | Dense ready VRAM | Shared ready VRAM | headroom gain |
|---|---:|---:|---:|---:|
| 1/16 | 1 | 1.2422 GiB | 0.9141 GiB | 0.3281 GiB |
| 1/8 | 1 | 1.2422 GiB | 0.9668 GiB | 0.2754 GiB |
| 3/16 | 1 | 1.2422 GiB | 1.0215 GiB | 0.2207 GiB |
| 1/16 | 8 | 1.2617 GiB | 0.9512 GiB | 0.3105 GiB |
| 1/8 | 8 | 1.2617 GiB | 1.0039 GiB | 0.2578 GiB |
| 3/16 | 8 | 1.2617 GiB | 1.0586 GiB | 0.2031 GiB |

Every Shared profile passed the predeclared minimum `0.15 GiB` headroom-gain threshold. Peak allocated and peak reserved VRAM were also lower than Dense in every comparison.

Approximate inference-ready VRAM reduction relative to Dense is about 16% to 26% across the tested selected rank fractions and batches.

## Why Gate C passes

The V5-C roadmap requires a candidate to retain task quality while clearly reducing serialized/resident bytes, with bounded recurrence behavior and practical real runtime. The accepted Shared-Basis candidate now additionally satisfies the project's stronger operational objective of leaving more device VRAM available to other applications.

Therefore the current candidate is retained and V5-C is closed as **PASSED** for the registered scope.

## Scope / non-claims

This pass is limited to:

- current V5 synthetic task families;
- current selected ranks and rank-fraction diagnostics;
- float32 execution;
- the tested Windows/CUDA/PyTorch environment;
- RTX 4070 Ti SUPER for the operational VRAM/runtime measurements;
- current two-module routed-core shapes.

Do not infer from this decision that:

- broad language quality is solved;
- Shared Basis universally beats Dense or Transformers;
- the same VRAM/runtime ratios hold on all hardware or large production LLMs;
- routing, information acquisition, memory integration, variable-length I/O, or Vision are solved.

## Next stage

Proceed to **V5-D — adaptive computation and routing**. Keep `SharedBasisFixedRoutingCore` opt-in until Gate-D integration justifies changing broader defaults.
