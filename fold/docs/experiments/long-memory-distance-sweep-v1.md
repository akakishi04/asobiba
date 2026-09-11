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

The original exact-distance generator inserts owner-independent neutral filler so the byte distance from the distant fact owner to the answer owner is exactly the requested value for every example. The local attention window remains fixed at 64 bytes. A later audit found that the repeated v1 filler changes the nonlinear capsule readout trajectory, so the v1 distance sweep must not be interpreted as changing only geometric distance. A diverse held-out-filler v2 condition is recorded below as the stronger 2048-byte check.

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

## 2048-byte condition, original repeated filler (v1)

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

This condition reached perfect decisions, but the filler audit below shows that the repeated filler changes the capsule readout trajectory. It remains useful evidence that the recurrent state can preserve and exploit the distant owner signal, but it is not a clean distance-only scaling point.

## Repeated-filler state-drift audit

A diagnostic compared original/counterfactual pairs that differ only in the distant owner while feeding the same filler into both states.

For the 2048-byte v1 checkpoint, the raw owner-specific `W/b` difference stayed essentially unchanged through about 1,918 filler bytes:

- raw owner-signal norm ratio: approximately 1.00 from filler start to filler end
- raw owner-signal cosine to start: approximately 1.00
- common recurrent-state drift norm: 0 at filler start, about 822.66 at filler end

However, after the nonlinear FOLD-R capsule response, the owner-specific readable difference grew monotonically through the same filler:

| Mean filler bytes processed | Capsule-response owner-signal ratio | Cosine to start |
| ---: | ---: | ---: |
| 0.00 | 1.00 | 1.00 |
| 479.77 | 2.79 | 0.96 |
| 959.22 | 3.63 | 0.94 |
| 1438.64 | 4.17 | 0.93 |
| 1918.41 | 4.54 | 0.92 |

The 1024-byte v1 checkpoint showed the same qualitative pattern: raw owner-signal ratio stayed about 1.00 while capsule-response owner-signal ratio reached about 3.07 after about 894 filler bytes.

Because the 1024- and 2048-byte values come from separately trained checkpoints, their endpoint ratios alone do not prove a causal scaling law. The within-2048 trajectory is sufficient, however, to show that the repeated filler is not readout-neutral: increasing filler changes the common `W/b` state and thereby changes sensitivity of the nonlinear capsule response even though the owner-specific raw state difference is preserved.

## 2048-byte diverse held-out filler (v2)

To reduce the repeated-filler shortcut, v2 keeps the same ownership task and exact 2048-byte fact-to-answer distance but varies filler per example. Train and validation use disjoint filler vocabularies and templates, filler generation uses an RNG stream independent from owner/object selection, and exact train/validation filler overlap is zero.

Dataset/preparation:

- benchmark: `fold-r-long-memory-owner-distance-v2-diverse-filler`
- target fact-to-answer distance: exactly 2048 bytes
- filler bytes: 1914-1923
- train rows / unique: 20,000 / 20,000
- validation rows / unique: 2,000 / 2,000
- train/validation example overlap: 0
- exact train/validation filler overlap: 0
- prepared-data fingerprint: `88659867ae743eceee273b4423c1b4f79f1140c61ffb902f81fd49e150c88221`
- sequence length used for training: 2112

### At 5,000 optimizer steps

- best/final validation NLL: 0.2448734588623047
- byte perplexity: 1.277459651778996
- standard accuracy: 0.3335 = 667 / 2000
- standard mean top-1 margin: 0.260434957325459

The model was clearly above the 8.3333% owner chance rate but far from reliable retrieval. Relative to repeated-filler v1, this confirms that the v1 filler materially eased optimization.

### At 5,500 optimizer steps

- best/final validation NLL: 0.02508224278688431
- byte perplexity: 1.0253994487650226
- standard accuracy: 0.989 = 1978 / 2000
- standard mean top-1 margin: 2.90189040088654
- counterfactual accuracy: 0.98848167539267 = 1888 / 1910
- counterfactual original-owner prediction rate: 0.0
- counterfactual mean top-1 margin: 2.88639916699594

The transition from 5,000 to 5,500 steps is sharp: the model moved from 33.35% to about 99% standard retrieval while counterfactual accuracy rose to the same level.

### After resuming to 6,000 optimizer steps

Validation NLL continued to improve overall, with the best checkpoint occurring at step 5,900:

- step 5,600: validation NLL 0.0544572405
- step 5,700: 0.0284802387
- step 5,800: 0.0148750048
- step 5,900: **0.0072223412**
- step 6,000: 0.0099323848
- best validation NLL: **0.00722234120965004**

Evaluation of the best checkpoint after the 6,000-step run:

- standard accuracy: **0.9995 = 1999 / 2000**
- standard mean top-1 margin: **4.04975413948297**
- counterfactual accuracy: **0.998429319371728 = 1907 / 1910**
- counterfactual original-owner prediction rate: **0.0**
- counterfactual mean top-1 margin: **4.04040266506335**

Conclusion for v2: repeated filler made the original 2048-byte task easier to optimize, but it was not necessary for the current FOLD-R prototype to learn long-range owner transport. With diverse validation filler patterns held out from training, the same 383,796-parameter architecture reached 99.95% standard and 99.84% counterfactual retrieval at thirty-two times the 64-byte local-attention window, with zero reversion to the original owner on counterfactual examples.

## Current interpretation

The observed results are:

| Condition | Training budget | Standard accuracy | Counterfactual accuracy | Best validation NLL |
| --- | ---: | ---: | ---: | ---: |
| ~125-134 bytes, original benchmark | 2,000 | 100% | 100% | 0.0062013194 |
| 256 bytes, v1 repeated filler | 2,000 | 100% | 100% | 0.0230336699 |
| 512 bytes, v1 repeated filler | 2,000 | 15.35% | 11.7585% | 0.3690288999 |
| 512 bytes, v1 repeated filler | 5,000 | 100% | 100% | 0.0008226921 |
| 1024 bytes, v1 repeated filler | 5,000 | 64.95% | 64.5669% | 0.1369158472 |
| 1024 bytes, v1 repeated filler | 7,500 | 100% | 100% | 0.0013520829 |
| 2048 bytes, v1 repeated filler | 5,000 | 100% | 100% | 0.0532526469 |
| 2048 bytes, v2 diverse held-out filler | 5,000 | 33.35% | not measured | 0.2448734589 |
| 2048 bytes, v2 diverse held-out filler | 5,500 | 98.90% | 98.8482% | 0.0250822428 |
| 2048 bytes, v2 diverse held-out filler | 6,000 run / best checkpoint at 5,900 | 99.95% | 99.8429% | 0.0072223412 |

Two distinct findings now matter:

1. The recurrent FOLD-R `W/b` owner-specific difference can remain stable across long intervening input even while the common state moves substantially.
2. The original repeated filler is not a neutral distance spacer: it changes the nonlinear capsule readout and materially eases optimization. The diverse held-out-filler v2 result is therefore the stronger 2048-byte evidence.

The stronger supported statement is now:

> On this synthetic single-fact task, the current 383,796-parameter FOLD-R prototype can learn to carry and use a distant ownership fact at least 2048 bytes across a fixed 64-byte local-attention window. Under a diverse-filler validation distribution withheld from the filler patterns used for training, the model reached 99.95% standard and 99.84% counterfactual owner retrieval, with zero original-owner reversions. No representational capacity failure has yet been demonstrated through 2048 bytes, but the original repeated-filler sweep contains a readout-amplification confound and should not be used by itself to infer distance scaling.

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
- that all possible filler distributions are readout-neutral

## Next experimental priority

Use the diverse held-out-filler v2 benchmark, not repeated-filler v1, for new longer-distance points. The next useful target is 4096 bytes. For longer distances, evaluate staged checkpoints in 500-step increments once the initial run approaches its transition region rather than committing to a large blind extension. The simple single-fact distance sweep should stop around 16 KiB if no capacity failure appears; after that, multiple facts, interference, correction, overwrite, and mixed-distance generalization become higher-value tests than merely increasing empty distance.
