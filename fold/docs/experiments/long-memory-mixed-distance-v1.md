# Long-memory mixed-distance dataset v1

Date: 2026-09-11

Status: experimental dataset contract for testing whether one FOLD-R model can generalize beyond the maximum distance observed during training.

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

## Interpretation gate

The key question is not merely whether the mixed model performs well inside 256-4096 bytes. The stronger result would be retention of high standard and counterfactual accuracy at 6144, 8192, 12288, or 16384 bytes without any training examples beyond 4096 bytes.

Failure beyond 4096 bytes would also be informative: it would indicate that the learned state dynamics do not yet extrapolate indefinitely even if separately trained exact-distance models can solve longer distances.
