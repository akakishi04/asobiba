# FOLD v0.5 Gate B — High-Precision Learned Core

Date: 2026-09-11

Status: **PASS**

This record closes V5-B from `docs/development-roadmap-v0.5.md`.

Gate B asks whether the new core can learn reliably **before compression is introduced**. It does not require broad superiority over Transformer-like or other production architectures, and it does not permit compression to hide a basic trainability failure.

## Scope

The tested V5-B core is the uncompressed high-precision path:

- shared learned state-update core,
- small route-specific module set,
- working slots,
- fixed / teacher routing,
- learned residual gate,
- no weight compression,
- no adaptive controller,
- no FOLD-R integration,
- no information acquisition,
- no vision.

For the short bilingual byte task, the input path includes the causal local byte encoder anticipated by architecture v0.5. This was added after the first language smoke test exposed that the slot-wise core alone had no mechanism for combining information across byte positions.

## Task coverage

Held-out trainability was established on the following task families:

1. exact copy / exact symbol sequence,
2. condition hold and update,
3. three-way comparison (LESS / EQUAL / GREATER),
4. exact bounded addition on unseen operand pairs,
5. three-step ADD / SUB composition with intermediate trajectory supervision,
6. short English and Japanese UTF-8 byte tasks covering NEXT-BYTE and INSTRUCTION-RESPONSE.

The language task deliberately remains a small Gate-B smoke task. It is not evidence of general language understanding.

## Multi-seed reproducibility

Seeds:

- 20260911
- 20260912
- 20260913

Six task families were trained independently at all three seeds: **18 / 18 runs**.

Observed aggregate result:

- all runs improved their held-out loss,
- all 18 runs passed the pre-established task reference bar,
- copy: mean final exact score 1.0, minimum 1.0,
- condition: mean final trajectory-exact score 0.9947916667, minimum 0.984375,
- comparison: mean final score 1.0, minimum 1.0,
- addition: mean final exact score 1.0, minimum 1.0,
- composition: mean final trajectory-exact score 1.0, minimum 1.0,
- language: mean final accuracy 1.0, minimum 1.0.

Therefore the observed trainability is not dependent on one successful initialization seed.

## Controlled baseline comparison

Representative tasks:

- condition,
- composition,
- language.

Architectures:

- `v5b`: shared core + selected module,
- `dense`: route-specific Dense MLP matched to V5-B active Linear MACs per slot / step,
- `shared`: one shared/recurrent transform plus route embedding, parameter-matched to V5-B core.

The comparison keeps the dataset split, non-core model initialization, encoder / decoder, loss, optimizer, training steps, batch size, and seed schedule fixed. Only the core implementation changes.

### Composition

| Architecture | Core parameters | Active Linear MACs / slot / step | Mean score | Minimum score | Mean elapsed s |
|---|---:|---:|---:|---:|---:|
| V5-B | 12,800 | 8,192 | 1.0000 | 1.0000 | 2.9659 |
| Dense | 16,864 | 8,192 | 1.0000 | 1.0000 | 2.1676 |
| Shared | 12,802 | 12,416 | 0.780864 | 0.657407 | 2.1166 |

### Condition

| Architecture | Core parameters | Active Linear MACs / slot / step | Mean score | Minimum score | Mean elapsed s |
|---|---:|---:|---:|---:|---:|
| V5-B | 3,328 | 2,048 | 0.994792 | 0.984375 | 2.0564 |
| Dense | 4,336 | 2,048 | 0.994792 | 0.984375 | 1.1798 |
| Shared | 3,330 | 3,136 | 1.0000 | 1.0000 | 1.6974 |

### Language

| Architecture | Core parameters | Active Linear MACs / slot / step | Mean score | Minimum score | Mean elapsed s |
|---|---:|---:|---:|---:|---:|
| V5-B | 12,800 | 8,192 | 1.0000 | 1.0000 | 11.7561 |
| Dense | 16,864 | 8,192 | 1.0000 | 1.0000 | 9.8926 |
| Shared | 12,802 | 12,416 | 0.969697 | 0.909091 | 10.3542 |

## Interpretation

### What the comparison supports

At the tested sizes:

- V5-B matches the Dense baseline's held-out quality on all three representative tasks.
- At the same active Linear MAC count, V5-B uses fewer independent core parameters than Dense:
  - about **23.25% fewer** for the width-16 condition core,
  - about **24.10% fewer** for the width-32 composition / language core.
- The parameter-matched Shared/Recurrent baseline uses almost the same number of core parameters as V5-B, but requires about **51.6–53.1% more active Linear MACs** in these matched configurations.
- The Shared/Recurrent baseline remains strong on condition, but is materially weaker on composition and language.

This supports keeping the V5-B structure as a viable candidate for V5-C compression experiments.

### What the comparison does not support

The current V5-B implementation is **not faster** than Dense in wall-clock time. In these small CPU runs V5-B is roughly:

- 1.37x Dense time on composition,
- 1.74x Dense time on condition,
- 1.19x Dense time on language.

That overhead is expected from evaluating separate shared and routed MLPs in ordinary PyTorch instead of one wider fused Dense MLP, but it is still a real measured cost and must not be ignored.

Therefore this result is **not** a speed superiority claim.

It also does not establish:

- broad language understanding,
- large-scale training behavior,
- Transformer / SSM superiority,
- adaptive routing quality,
- compressed-model quality,
- memory integration quality,
- production GPU-kernel efficiency.

## Gate B decision

**PASS.**

Rationale:

1. The uncompressed V5-B core reliably learns all required basic task families.
2. Held-out loss and task quality improve across multiple independent seeds.
3. The result is reproducible across 18 / 18 multi-seed runs.
4. Dense and shared/recurrent baselines were tested under explicit matching contracts.
5. V5-B preserves Dense-level task quality in the representative comparison while using fewer independent core parameters at equal active Linear MACs.
6. Known runtime overhead is recorded rather than hidden.

The next canonical stage is **V5-C — compression components and recurrence stability**.

V5-C must retain the high-precision V5-B model as the reference. Compression may proceed only if it produces a measurable storage / quality advantage without unexplained recurrence instability or an unbounded correction term.
