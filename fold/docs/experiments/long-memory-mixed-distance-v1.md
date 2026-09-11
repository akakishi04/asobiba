# Long-memory mixed-distance dataset v1

Date: 2026-09-11

Status: completed first-pass experiment. The dataset contract, 5,000-step mixed-distance training run, in-range validation, band-wise validation, and held-out distance extrapolation through 16,384 bytes have been measured.

## Goal

Train one model on many fact-to-answer distances rather than retraining a separate model for each exact distance, then evaluate zero-shot distance extrapolation beyond the training range.

This is not a general language-model benchmark. It remains the synthetic single-owner retrieval task used by the current FOLD-R prototype.

## Training range

Training contains 20,000 examples spanning 256 through 4096 bytes.

Distances are allocated equally across four log2-style bands:

- 256-511 bytes
- 512-1023 bytes
- 1024-2047 bytes
- 2048-4096 bytes

Within each band, the exact distance is sampled uniformly. The resulting schedule is shuffled before row generation. Distance selection uses an RNG stream independent from owner/object selection and independent from filler generation.

With the default 20,000 rows, each band receives exactly 5,000 examples.

## In-range validation

The validation split contains 2,000 independently generated examples in the same 256-4096 byte range with the same balanced-band policy.

As in the diverse-filler exact-distance v2 benchmark, validation uses filler vocabulary and sentence templates that are disjoint from the training filler vocabulary/templates.

## Extrapolation evaluation

The following exact distances are generated as separate evaluation files and never occur in training:

- 6144 bytes
- 8192 bytes
- 12288 bytes
- 16384 bytes

Each contains 500 examples by default.

These files are intended for both standard owner retrieval and counterfactual evaluation. A successful result beyond 4096 bytes is therefore evidence of distance extrapolation by the learned recurrent-memory behavior, rather than direct training at that distance.

## Generated files

The default generator emits:

- `train.jsonl`
- `validation.jsonl`
- `eval-6144.jsonl`
- `eval-8192.jsonl`
- `eval-12288.jsonl`
- `eval-16384.jsonl`
- `generation.json`

Rows retain the normal `prompt` and `target` fields and also include `distance_bytes` for later distance-band analysis. Existing preparation code ignores the extra metadata field, while benchmark evaluation continues to read `prompt` and `target`.

## Reproducibility and leakage controls

- training and validation/extrapolation use split-specific diverse filler vocabulary/templates
- owner/object content RNG is separate from filler RNG
- distance RNG is separate from both content and filler RNGs
- train/held-out full-text overlap is rejected
- extrapolation distances must be strictly greater than 4096 bytes
- generated files are SHA-256 recorded in `generation.json`
- raw datasets remain local/ignored and are deterministically regenerated instead of committed to Git

## Default generation command

```powershell
.\.venv\Scripts\python.exe -m fold_lm.long_memory_mixed `
  --output data/raw/long-memory-mixed-v1
```

## Training run

The first mixed-distance run used the same small memory-on model and training configuration as the 4096-byte v2 run so that the principal changed variable was the training-distance distribution.

- parameters: 383,796
- local attention window: 64 bytes
- maximum training distance: 4096 bytes
- optimizer steps: 5000
- prepared-data fingerprint: `0b471345ef26b3a48e09da9749c30ecb6f66c21e07804bc3537dfa9eb1f7297c`
- best validation NLL: 0.013050930374292525
- byte perplexity: 1.0131364654652382
- CUDA peak allocated: 562,504,704 bytes
- training wall-clock: 2532.710131599997 seconds

Validation NLL remained near 0.41 for a long plateau, then improved sharply late in training. Selected checkpoints:

| step | validation NLL |
|---:|---:|
| 3200 | 0.4087832414 |
| 3800 | 0.4084755741 |
| 4000 | 0.3434736376 |
| 4200 | 0.2116089312 |
| 4300 | 0.1418779540 |
| 4400 | 0.0986629751 |
| 4500 | 0.0745288100 |
| 4700 | 0.0563151203 |
| 4800 | 0.0365796089 |
| 4900 | 0.0276467469 |
| 5000 | 0.0130509304 |

The best validation checkpoint was therefore still improving at the 5000-step boundary. No claim is made here that 5000 steps is globally optimal.

## In-range result: 256-4096 bytes

Full 2,000-example standard evaluation:

- accuracy: 99.6% (`1992/2000`)
- mean top-1 margin: 3.73786997282505

Counterfactual evaluation changes only the distant owner fact while preserving the local-attention-visible suffix:

- accuracy: 99.6335% (`1903/1910`)
- original-owner prediction rate: 0%
- mean top-1 margin: 3.83560036938852

This indicates that the aggregate in-range score is not explained by simply reproducing the original owner after the distant fact is changed.

## In-range result by distance band

The balanced validation split was also evaluated separately by band.

| band | standard | standard margin | counterfactual | CF original-owner rate | CF margin |
|---|---:|---:|---:|---:|---:|
| 256-511 | `500/500` (100.0%) | 3.78 | `472/473` (99.79%) | 0% | 3.85 |
| 512-1023 | `498/500` (99.6%) | 3.78 | `470/471` (99.79%) | 0% | 3.99 |
| 1024-2047 | `497/500` (99.4%) | 3.78 | `477/478` (99.79%) | 0% | 3.89 |
| 2048-4096 | `497/500` (99.4%) | 3.61 | `486/488` (99.59%) | 0% | 3.65 |

The longest in-range band therefore remains near-perfect; the 99.6% aggregate accuracy is not being carried only by the short-distance bands.

## Zero-shot distance extrapolation

No training example exceeds 4096 bytes. Evaluation above that boundary produced:

| exact distance | standard | standard margin | counterfactual | CF original-owner rate | CF margin |
|---:|---:|---:|---:|---:|---:|
| 6144 | `482/500` (96.4%) | 3.10 | `470/483` (97.31%) | 0% | 3.20 |
| 8192 | `488/500` (97.6%) | 3.09 | `466/484` (96.28%) | 0% | 3.00 |
| 12288 | `449/500` (89.8%) | 2.85 | `434/485` (89.48%) | 0% | 2.87 |
| 16384 | `440/500` (88.0%) | 2.56 | `438/481` (91.06%) | 0% | 2.74 |

The 16,384-byte point is 4x the maximum mixed training distance and 256x the 64-byte local-attention window. Accuracy degrades with distance but remains far above the 12-candidate chance level of 8.33%.

## Evaluator note

Long extrapolation evaluation initially used the simple reference candidate scorer, which recomputed the full prompt for every owner candidate. At 12,288 bytes that path took 9487.9 seconds for 500 standard examples.

A shared-prefix evaluator was added that computes each long prompt once, branches the resulting recurrent/KV state across the fixed owner candidates, and evaluates only the short candidate suffixes. On the same 12,288-byte standard evaluation it returned the same `394/500` result for the earlier 2048-trained checkpoint in 17.0 seconds, a measured 556.6x speedup. A dedicated parity test also checks the optimized scorer against the reference implementation on small inputs.

The optimized evaluator changes benchmark execution cost, not the underlying model or task.

## Interpretation

The first-pass mixed-distance experiment passes its original interpretation gate:

1. one model trained over 256-4096 bytes solves the full in-range validation set at near-perfect accuracy;
2. all four in-range distance bands remain near-perfect independently;
3. counterfactual owner replacement is followed with near-perfect in-range accuracy and zero observed fallback to the original owner;
4. strong zero-shot retrieval and counterfactual performance persists at 6144, 8192, 12288, and 16384 bytes, all beyond the maximum training distance.

Together with the earlier 4096-from-scratch failure, these results support the hypothesis that the failed dedicated 4096 run was an optimization/learned-geometry failure rather than a hard distance wall in the current FOLD-R vertical slice. Mixed-distance training provides a route to a much better learned memory/readout solution.

This result does **not** establish arbitrary-context or general language-model capability. The experiment is still limited to a synthetic single-fact owner-retrieval task family with controlled filler. It does not test multi-fact capacity, interference, correction/overwrite semantics, natural-language diversity, bounded retrieval over many memories, or a complete H0/H1/H2 runtime.

## Decision after this experiment

Do not continue extending exact distance merely to obtain larger byte counts as the immediate priority. Preserve this vertical slice as a long-memory reference and move the main development path to the v0.5 staged roadmap.

The next canonical implementation stage is **V5-A: reference computation and accounting**, followed by **V5-B: the high-precision uncompressed new core**. Multi-fact/interference/correction/natural-language memory tests remain useful future memory gates, but they should not block construction of the v0.5 state/runtime/accounting foundation.
