# Long-memory counterfactual experiment v1

Date: 2026-09-10

Status: prototype result. This document records the observed result and its limits; it is not a claim of general language-model superiority.

## Purpose

Test whether the current FOLD-R memory path can transport information beyond the model's local-attention window and use it at a later answer position.

The key comparison is memory enabled versus local-only controls that do not have a long-range state path.

## Model / training conditions

Shared settings:

- width: 128
- layers: 2
- heads: 4
- local attention window: 64 byte tokens
- chunk: 32
- sequence length: 256 byte tokens
- batch size: 4
- optimizer steps: 2000
- learning rate: 3e-4
- seed: 20260909
- tokenizer: `utf8-byte-v1`
- target-only SFT supervision: prompt tokens are masked from loss; target bytes plus EOS are supervised
- prepared-data fingerprint: `622c0a486ecec7d2772846b8e951b4674c6c4df2d6e26aab109c71136e0ce8c7`

Memory ON:

- parameters: 383,796
- checkpoint: `runs/long-memory-sft-on-2k/best.pt`
- best checkpoint step: 2000

Original memory OFF control:

- parameters: 362,112
- checkpoint: `runs/long-memory-sft-off-2k/best.pt`
- best checkpoint step: 2000

Parameter-matched local-only control:

- parameters: 383,796
- checkpoint: `runs/long-memory-sft-matched-off-2k/best.pt`
- memory: false
- local control adapter: true
- best checkpoint step: 2000
- no FOLD-R `W` / `b` long-range state
- local-attention window remains 64 bytes

The matched control adds trainable local residual capacity rather than unused dummy parameters. Its total trainable parameter count exactly matches the memory-enabled model while preserving the same local receptive field.

## Dataset

Synthetic ownership-retrieval examples were used. A representative form is:

```text
Important fact: the blue key belongs to Alice. Bob walked through the garden. Dave looked at the clouds. Jack opened a window. Question: who owns the blue key? Answer: Alice.
```

For target-only SFT this is stored as:

```json
{"prompt":"Important fact: ... Question: who owns the blue key? Answer: ","target":"Alice."}
```

Prepared split:

- train: 18,010 unique documents
- validation: 2,000 unique documents
- train duplicates removed: 1,990
- train/validation exact overlap: 0
- candidate owners: 12
- chance accuracy: 1/12 = 8.3333%
- fact-to-answer owner distance: approximately 125-134 bytes

The fact therefore lies well beyond the 64-byte local-attention window at the answer position.

## Why target-only loss was required

An earlier full-sequence-loss run reached a low general validation NLL while owner retrieval stayed near chance: 175/2000 = 8.75%.

Most bytes in the template are predictable without retrieving the distant owner, so full-sequence NLL was a misleading metric for the actual memory task. Schema 2 target-only supervision was added so only the answer target plus EOS contributes to loss.

## Standard validation result

After target-only training:

| Condition | Parameters | Owner accuracy | Correct | Answer NLL | Mean top-1 margin |
| --- | ---: | ---: | ---: | ---: | ---: |
| FOLD-R memory ON | 383,796 | 100.0% | 2000 / 2000 | 0.0062013194 | 4.7627403361 |
| Parameter-matched local-only | 383,796 | 11.8% | 236 / 2000 | 0.3939000762 | 0.1537821162 |
| Original memory OFF | 362,112 | 12.8% | 256 / 2000 | 0.3907754913 | 0.2033765608 |
| Chance | — | 8.3333% | — | — | — |

The parameter-matched control remains near chance despite having exactly the same total trainable parameter count as the memory-enabled model. The extra local capacity therefore does not explain the memory model's 100% retrieval accuracy on this task.

The original smaller OFF model and the matched OFF model both converge to approximately the same answer-NLL floor near 0.39-0.40. This is consistent with learning the local answer format and name spelling without reliably recovering the distant owner.

## Counterfactual test

A stronger causal-style control was then applied.

For each usable validation example, only the distant fact owner was changed, for example:

```text
Important fact: ... belongs to Alice.
```

became:

```text
Important fact: ... belongs to Frank.
```

Controls:

- replacement owner had the same byte length as the original owner
- prompt byte length therefore remained unchanged
- the final 64 bytes before the answer were byte-identical
- distractors were unchanged
- question was unchanged
- only the distant owner fact changed
- replacement names already appearing elsewhere in the prompt were excluded

This yielded 1,905 counterfactual examples.

### Counterfactual result

| Condition | Parameters | Counterfactual accuracy | Correct | Original-owner prediction rate | Mean top-1 margin |
| --- | ---: | ---: | ---: | ---: | ---: |
| FOLD-R memory ON | 383,796 | 100.0% | 1905 / 1905 | 0.0% | 4.7574161028 |
| Parameter-matched local-only | 383,796 | 9.3963% | 179 / 1905 | 10.2362% | 0.1544560488 |
| Original memory OFF | 362,112 | 10.5512% | 201 / 1905 | 11.3386% | 0.2035182058 |
| Chance | — | 8.3333% | — | — | — |

The memory-enabled model followed every distant fact rewrite and never predicted the original owner. The parameter-matched local-only model remained close to chance and did not reliably track the changed fact.

This matched comparison removes the simplest parameter-count explanation: both models have 383,796 trainable parameters, but only the model with the FOLD-R long-range state path tracks the distant counterfactual fact reliably.

## Reproducibility check

The repository includes `fold_lm.long_memory_benchmark`, which deterministically regenerates the raw prompt/target dataset and evaluates both standard and counterfactual owner retrieval.

A fresh regeneration on 2026-09-10 matched the original experiment data byte-for-byte:

- train SHA-256: `a60e37a8d9deb3f7fd3f21e3bb12802b3d13ff6248b6246c152c335bd75a5f4a`
- validation SHA-256: `0f4615a802a10b883e6bf7c7adef5baca81cf904840ba944c3ed0a8d59c39256`
- train rows: 20,000; train unique: 18,010
- validation rows: 2,000; validation unique: 2,000
- validation generation attempts: 2,498
- cross-split overlap: 0
- fact-to-answer distance: 125-134 bytes
- example size: 168-182 bytes

Running the committed `compare` command on the regenerated validation set exactly reproduced the previously observed memory-ON and original-OFF accuracies:

- standard memory ON: 1.0 (2000 / 2000)
- standard memory OFF: 0.128 (256 / 2000)
- counterfactual memory ON: 1.0 (1905 / 1905)
- counterfactual memory OFF: 0.10551181102362205 (201 / 1905)
- counterfactual memory ON original-owner prediction rate: 0.0
- counterfactual memory OFF original-owner prediction rate: 0.11338582677165354

The parameter-matched control was subsequently evaluated with the same committed evaluator:

- standard matched control: 0.118 (236 / 2000)
- counterfactual matched control: 0.0939632545931759 (179 / 1905)
- counterfactual original-owner prediction rate: 0.102362204724409
- standard mean top-1 margin: 0.153782116234303
- counterfactual mean top-1 margin: 0.154456048750189

The benchmark harness is covered by deterministic-generation, overlap, counterfactual-suffix, overwrite-safety, parser, and CPU-evaluation tests. Parameter-matched control tests also verify exact parameter equality, absence of long-range state, trainability, and mutual exclusion with the memory path. The full LM test suite passed 38/38 after adding the matched control.

## Supported conclusion

For this synthetic task and this prototype configuration, the current FOLD-R memory path can carry information beyond a 64-byte local-attention window and use it approximately 125-134 bytes later at the answer position.

The counterfactual control strengthens this result: changing only the distant fact, while keeping the local answer-visible suffix and absolute answer position unchanged, changes the memory-enabled model's answer with 100% accuracy. A parameter-matched local-only control with the same 383,796 trainable parameters remains near chance.

This is a successful proof of concept for long-range information transport in the current FOLD-R prototype. The data generation and evaluation portions of this experiment are reproducible from the repository; trained checkpoints remain local run artifacts.

## What this result does not establish

This experiment does **not** yet establish:

- superiority over a Transformer or another long-context baseline
- robustness on natural-language corpora
- general reasoning ability
- performance at much longer distances
- resistance to multiple competing facts, corrections, interference, or noisy distractors
- parameter-efficiency superiority in a broad sense; this experiment only controls total parameter count for this local synthetic task
- independently reproducible trained weights from the repository alone, because checkpoints are intentionally excluded from Git

## Next experimental priorities

1. Sweep fact-to-answer distance well beyond 128 bytes.
2. Test multiple facts and interference.
3. Test overwrite/correction cases where the later fact should supersede the earlier one.
4. Add at least one non-FOLD long-context baseline before making architecture-level comparative claims.
5. Repeat key comparisons across multiple random seeds to measure variance.
