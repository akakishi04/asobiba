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

## Current interpretation

The observed pattern is:

| Distance | Training budget | Standard accuracy | Counterfactual accuracy | Best/final validation NLL |
| ---: | ---: | ---: | ---: | ---: |
| ~125-134 bytes | 2,000 | 100% | 100% | 0.0062013194 |
| 256 bytes | 2,000 | 100% | 100% | 0.0230336699 |
| 512 bytes | 2,000 | 15.35% | 11.7585% | 0.3690288999 |
| 512 bytes | 5,000 | 100% | 100% | 0.0008226921 |

This shows that a failed result at a fixed optimizer-step budget cannot by itself be interpreted as a hard memory-capacity limit. At least between 256 and 512 bytes, optimization difficulty increases sharply before successful retrieval emerges.

The stronger supported statement is therefore:

> On this synthetic single-fact task, the current 383,796-parameter FOLD-R prototype can learn to carry and use information at least 512 bytes across a fixed 64-byte local-attention window. The 512-byte condition requires materially more optimization than the 256-byte condition under the tested setup.

## What this does not establish

- arbitrary or unbounded memory distance
- generalization to unseen distances without retraining
- multiple-fact capacity
- robustness to interference or noisy relevant facts
- correction / overwrite behavior at long distance
- natural-language long-context competence
- superiority over Transformer or other recurrent/state-space baselines
- that 5,000 steps is the minimal budget required at 512 bytes
- a scaling law between distance and required optimizer steps

## Next experimental priority

Continue the exact-distance sweep with FOLD-R ON while avoiding a matched-OFF run at every point. The next useful target is 1,024 bytes. If learning is weak at the initial budget, resume the same checkpoint before classifying the distance as a capacity limit. Key control comparisons should be repeated only at selected milestones or when architecture/data conditions change.
