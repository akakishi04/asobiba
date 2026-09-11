# Long-memory exact-distance sweep v1

Date: 2026-09-11

Status: prototype result. This document records exact-distance synthetic owner-retrieval results for the current FOLD-R prototype. It does not establish general language-model superiority or arbitrary long-context capability.

## Purpose

Measure how far the current FOLD-R long-range state can carry a single distant ownership fact beyond a fixed 64-byte local-attention window, and distinguish representational failure from insufficient optimization budget.

## Shared model conditions

- width: 128
- layers: 2
- heads: 4
- local attention window: 64 byte tokens
- chunk: 32
- ff_mult: 2
- capsules: 2
- latent: 16
- rank: 8
- reads: 8
- parameters: 383,796
- tokenizer: `utf8-byte-v1`
- target-only SFT supervision
- learning rate: 3e-4
- seed: 20260909
- candidate owners: 12
- chance owner accuracy: 8.3333%

The exact-distance generator inserts owner-independent neutral filler so the byte distance from the distant fact owner to the answer owner is exactly the requested value for every example. The local attention window remains fixed at 64 bytes.

## 256-byte condition

Dataset:

- target fact-to-answer distance: exactly 256 bytes
- example size: 299-304 bytes
- train rows: 20,000
- train unique after prepare: 18,010
- validation unique: 2,000
- train/validation exact overlap: 0
- prepared-data fingerprint: `39de583c2aa21d114ecef1b78bce7f6d927439cbf12b9b36bcde4ce236bd7ce1`
- sequence length used for training: 320

Training result at 2,000 optimizer steps:

- best validation NLL: 0.023033669931377343
- byte perplexity: 1.0233009934414117
- elapsed training time: 116.024 s
- CUDA peak allocated: 63,734,784 bytes

Owner retrieval:

- standard accuracy: 1.0 = 2000 / 2000
- standard mean top-1 margin: 3.29678756964207
- counterfactual accuracy: 1.0 = 1905 / 1905
- counterfactual original-owner prediction rate: 0.0
- counterfactual mean top-1 margin: 3.2904011318377

Conclusion for this condition: the current FOLD-R prototype successfully transports and uses the distant fact at exactly 256 bytes, four times the 64-byte local-attention window, under this synthetic task.

## 512-byte condition

Dataset:

- target fact-to-answer distance: exactly 512 bytes
- example size: 555-560 bytes
- train rows: 20,000
- train unique after prepare: 18,010
- validation unique: 2,000
- train/validation exact overlap: 0
- prepared-data fingerprint: `e53f4e85b2ff00d2a0683adeb4d052aafb366c7442aac2d0a57c3ee6ef35a3e1`
- sequence length used for training: 576

### At 2,000 optimizer steps

- validation NLL: 0.3690288998559864
- byte perplexity: 1.4463294017821775
- standard accuracy: 0.1535 = 307 / 2000
- standard mean top-1 margin: 0.370231022775173
- counterfactual accuracy: 0.11758530183727 = 224 / 1905
- counterfactual original-owner prediction rate: 0.0346456692913386
- counterfactual mean top-1 margin: 0.335929671203683

At this point the model remained close to chance and did not reliably use the distant fact.

### After resuming to 5,000 optimizer steps

- best validation NLL: 0.0008226920979355045
- byte perplexity: 1.0008230306019013
- elapsed time recorded in the resumed run summary: 331.123 s
- CUDA peak allocated: 96,986,112 bytes
- standard accuracy: 1.0 = 2000 / 2000
- counterfactual accuracy: 1.0 = 1905 / 1905
- counterfactual original-owner prediction rate: 0.0
- standard mean top-1 margin: 6.68217334532738
- counterfactual mean top-1 margin: 6.67445400067828

Conclusion for this condition: 512 bytes is not an observed representational capacity limit for this prototype. The same model that was near chance at 2,000 steps reached perfect standard and counterfactual owner retrieval after additional optimization to 5,000 steps.

## 1024-byte condition

Dataset:

- target fact-to-answer distance: exactly 1024 bytes
- example size: 1067-1072 bytes
- train rows: 20,000
- train unique after prepare: 18,010
- validation unique: 2,000
- train/validation exact overlap: 0
- prepared-data fingerprint: `27559ad4a738c27c1342e2a185dc6d4d0026a0771dee4bf1fd8a1b5c255f6439`
- sequence length used for training: 1088

### At 5,000 optimizer steps

- best validation NLL: 0.13691584715145624
- byte perplexity: 1.1467316437255437
- standard accuracy: 0.6495 = 1299 / 2000
- standard mean top-1 margin: 0.96516227388382
- counterfactual accuracy: 0.645669291338583 = 1230 / 1905
- counterfactual original-owner prediction rate: 0.0283464566929134
- counterfactual mean top-1 margin: 0.955965711344571

The nearly equal standard and counterfactual accuracies show that the model was already tracking the distant rewritten fact substantially at 5,000 steps, but had not yet reached reliable retrieval.

### After resuming to 7,500 optimizer steps

- best validation NLL: 0.0013520829304903446
- byte perplexity: 1.0013529974067186
- CUDA peak allocated: 163,488,768 bytes
- standard accuracy: 1.0 = 2000 / 2000
- counterfactual accuracy: 1.0 = 1905 / 1905
- counterfactual original-owner prediction rate: 0.0
- standard mean top-1 margin: 5.73802565264702
- counterfactual mean top-1 margin: 5.74949707021238

The resumed validation curve fell rapidly after step 5,000: 0.13584 at 5,100, 0.06218 at 5,500, 0.01465 at 6,000, 0.00510 at 6,500, 0.00234 at 7,000, and 0.00135 at 7,500. This suggests the 5,000-step result was an optimization-budget boundary rather than a representational capacity boundary. A checkpoint around 6,000-6,500 steps would have been a useful earlier evaluation point.

Conclusion for this condition: 1024 bytes is also not an observed representational capacity limit for this prototype. With additional optimization, the same 383,796-parameter model reached perfect standard and counterfactual owner retrieval at sixteen times the 64-byte local-attention window.

## 2048-byte condition

Dataset:

- target fact-to-answer distance: exactly 2048 bytes
- example size: 2091-2096 bytes
- train rows: 20,000
- train unique after prepare: 18,010
- validation unique: 2,000
- train/validation exact overlap: 0
- prepared-data fingerprint: `aabfe0ea182911fe5d81e5078e3bf7d122cdc357443662af20d78641da1af543`
- sequence length used for training: 2112

Training result at 5,000 optimizer steps:

- best validation NLL: 0.05325264694217689
- byte perplexity: 1.054696077200144
- elapsed training time: 1609.244 s
- CUDA peak allocated: 296,494,080 bytes

Owner retrieval:

- standard accuracy: 1.0 = 2000 / 2000
- standard mean top-1 margin: 2.36040964430571
- counterfactual accuracy: 1.0 = 1905 / 1905
- counterfactual original-owner prediction rate: 0.0
- counterfactual mean top-1 margin: 2.34759567950967

Conclusion for this condition: the current FOLD-R prototype reaches perfect standard and counterfactual owner retrieval at exactly 2048 bytes, thirty-two times the 64-byte local-attention window, after 5,000 optimizer steps. The answer NLL and margins are weaker than the fully converged 512/1024 runs, but the owner decision itself is correct on every evaluated example and tracks every distant counterfactual rewrite.

## Current interpretation

The observed pattern is:

| Distance | Training budget | Standard accuracy | Counterfactual accuracy | Best/final validation NLL |
| ---: | ---: | ---: | ---: | ---: |
| ~125-134 bytes | 2,000 | 100% | 100% | 0.0062013194 |
| 256 bytes | 2,000 | 100% | 100% | 0.0230336699 |
| 512 bytes | 2,000 | 15.35% | 11.7585% | 0.3690288999 |
| 512 bytes | 5,000 | 100% | 100% | 0.0008226921 |
| 1024 bytes | 5,000 | 64.95% | 64.5669% | 0.1369158472 |
| 1024 bytes | 7,500 | 100% | 100% | 0.0013520829 |
| 2048 bytes | 5,000 | 100% | 100% | 0.0532526469 |

This shows that a failed or partial result at a fixed optimizer-step budget cannot by itself be interpreted as a hard memory-capacity limit. Optimization difficulty is not monotonic in the currently observed runs: 1024 bytes required additional optimization beyond 5,000 steps, while the 2048-byte run already achieved perfect owner decisions at 5,000 steps. Therefore these points are not sufficient to infer a scaling law between distance and training budget.

The stronger supported statement is therefore:

> On this synthetic single-fact task, the current 383,796-parameter FOLD-R prototype can learn to carry and use information at least 2048 bytes across a fixed 64-byte local-attention window. Perfect standard and counterfactual owner retrieval has now been observed at thirty-two times the local window, with no representational capacity failure yet demonstrated.

## What this does not establish

- arbitrary or unbounded memory distance
- generalization to unseen distances without retraining
- multiple-fact capacity
- robustness to interference or noisy relevant facts
- correction / overwrite behavior at long distance
- natural-language long-context competence
- superiority over Transformer or other recurrent/state-space baselines
- the minimal optimizer-step budget required at 512, 1024, or 2048 bytes
- a scaling law between distance and required optimizer steps

## Next experimental priority

Continue the exact-distance sweep with FOLD-R ON while avoiding a matched-OFF run at every point. The next useful target is 4096 bytes. For longer distances, use staged checkpoints rather than committing to a large fixed budget: run an initial budget, evaluate owner accuracy, and extend in roughly 1,000-step increments only when needed. The simple single-fact distance sweep should stop around 16 KiB if no capacity failure appears, after which multiple facts, interference, correction, and overwrite behavior become higher-value tests than merely increasing empty distance.