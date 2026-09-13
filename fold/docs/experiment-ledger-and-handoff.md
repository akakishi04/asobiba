# FOLD Experiment Ledger and Handoff

> Project-wide handoff checkpoint for FOLD. Read this first in a new session. Update it after every accepted Cxx experiment, retry decision, or Gate decision change.

## 1. Environment / repository

- Repository: `akakishi04/asobiba`
- FOLD path: `fold/`
- Branch: `feat/sft-target-loss`
- Local repo: `M:\asobiba\fold`
- Python: `M:\asobiba\fold\.venv-py31315\Scripts\python.exe`
- Python 3.13.15
- PyTorch `2.10.0+cu130`
- CUDA 13.0
- GPU: NVIDIA GeForce RTX 4070 Ti SUPER
- VS2022 Developer PowerShell 17.14.27

Always record the exact commit for timing comparisons.

## 2. Protected artifacts

### C37 protected result

- Path: `M:\asobiba\fold\runs\chatgpt-last-result.json`
- SHA256: `FD4A8DA897BDAEA9D103A252E30212C7FF842D23300D7C837333E146DEE51931`

### Runtime fixture

- Path: `M:\asobiba\fold\runs\fixtures\v05-c-composition-20260921.pt`
- SHA256: `A52F8209703149407580F7E2965B61B78653030EE992AF6D759865736741CA9E`

Diagnostics must preserve both.

## 3. Experiment protocol

IDs are `Cxx`.

1. Run one experiment / verification step per C number.
2. Full console output overwrites `M:\asobiba\fold\runs\chatgpt-last.log`.
3. User pastes the log back into ChatGPT.
4. ChatGPT judges the result.
5. Increment only after successful completion.
6. Failed retries keep the same C number.
7. `status=PASS` means the experiment executed correctly, not that Gate C passed.
8. Wrong runner, parser failure, wrong experiment ID, protected-hash mismatch, etc. are invalid runs.
9. Prefer tracked benchmark files over large chat-pasted Python runners.
10. Long-running experiments must print progress.

PC clipboard:

```powershell
$log = "M:\asobiba\fold\runs\chatgpt-last.log"
Get-Content -LiteralPath $log -Raw -Encoding UTF8 -ErrorAction Stop | Set-Clipboard
```

Smartphone / OSC52:

```powershell
$log = "M:\asobiba\fold\runs\chatgpt-last.log"
$text = Get-Content -LiteralPath $log -Raw -Encoding UTF8 -ErrorAction Stop
$b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($text))
[Console]::Write("$([char]27)]52;c;$b64$([char]7)")
```

## 4. Gate status

Gate A/B foundation exists.

### Gate C — compression + recurrence stability

Current status: **NOT PASSED**.

A candidate must preserve quality with materially lower serialized/resident bytes, or beat the reference at equal capacity, while recurrence remains stable and runtime does not become impractical from decode overhead.

The original fine-grained codebook representation remains a storage/reference baseline, but direct GPU execution is no longer the primary candidate.

Current lead Gate-C routed-weight family:

```text
W_module = W_base + A_module @ B_shared
```

with rank scaling roughly as `rank = width / 16` for the current modules=2, hidden_mult=2 setup.

## 5. Scientific discipline

Do not claim:

- Cxx PASS == Gate C PASS;
- fixture score 1.0 == broad language quality;
- synthetic scaling == production LLM scaling proof;
- FOLD beats Transformers / existing LLMs from these diagnostics.

Separate runtime feasibility, storage, representation capacity, task quality, recurrence, and final gate decisions.

## 6. Key accepted results before the shared-basis pivot

- C41: registered model bytes 51,200 B dense vs 44,800 B codebook compact, **12.5% reduction**.
- C42: repeated Graph request compact/dense median **1.028879**.
- C45: GPU-only Graph compact/dense **1.05546**.
- C46: slowdown localized overwhelmingly to Up; Down ~1.006x dense.
- C49: sparse correction E only ~1-3% overhead; not the main problem.
- C51/C53: shared-base GEMM is near dense; codebook delta/decode dominates.
- C54: full-M N16 reuse beats row-wise by ~17.1%.
- C55: precomputed address metadata gives only ~1-2% noisy gain; address arithmetic is not the main cost.
- C56: predecoded Triton/dense **1.13357**, compact/predecoded **1.65877**, compact/dense **1.91422** at the real width32 Up bank.

## 7. C57 — codebook scale sweep, 32 -> 1024

Accepted commit: `c4c5e96980b5671d3d1fbac20cb23dd467e31b78`.

Storage scales well:

- serialized ratio converges near **0.5703**;
- current runtime-resident ratio converges near **0.6875**.

But runtime does not scale:

`compact / dense` paired median:

- 32: 1.34919
- 64: 1.50403
- 128: 3.27688
- 256: 8.88606
- 512: 11.35949
- 1024: 12.88719

The fixed custom Triton tile itself also degrades, but compact gather/decode remains ~2.18-2.34x over the same predecoded Triton execution at large widths.

Decision: stop primary optimization of direct fine-grained block-codebook GPU execution. Keep it as a storage/reference baseline.

## 8. C58 — matched-storage shared-basis runtime scale sweep

Accepted commit: `27077cdda37ca344da8ea5e6f8e491f613dbe1fa`.

Representation:

```text
W_module = W_base + A_module @ B_shared
```

Execution uses vendor GEMM-family operations:

1. shared `F.linear(x, [W_base; B_shared])`;
2. module-specific `addmm` from latent to output.

Rank = width/16. Persistent routed-weight ratio: **0.578125** at every tested width. Theoretical matmul FLOP overhead ~9.375%.

`shared_basis / dense` median:

- 32: 3.12043
- 64: 2.94781
- 128: 4.86182
- 256: 1.63577
- 512: 1.29614
- 1024: **1.19407**

Interpretation: small sizes are launch/shape dominated; large sizes scale in the desired direction. Runtime/storage feasibility is promising.

## 9. C59 — post-hoc shared-basis quality frontier

Accepted commit: `32f07a9abd5fd566c041134940a5a543bd11cd44`.

Trusted composition fixture, width32, hidden64, modules2, dense score 1.0. Post-hoc mean-base + truncated-SVD fit only; no task-aware training.

| rank | routed-weight ratio | score |
|---:|---:|---:|
| 2 | 0.5703125 | 0.050926 |
| 4 | 0.640625 | 0.115741 |
| 8 | 0.781250 | 0.125000 |
| 12 | 0.921875 | 0.166667 |
| 14 | 0.9921875 | 0.300926 |
| 32 | 1.625000 | 1.000000 |

Conclusion: post-hoc SVD is not an adequate objective. Weight reconstruction error and task score are not interchangeable.

## 10. C60 — task-aware shared-basis recovery

Accepted commit: `a713fe66101a0f99a38100117340286cd7ed5afe`.

Trusted composition fixture. Ranks 2,4,8,12,14. Only shared-basis routed-weight factors trained; all non-factor parameters frozen. 300 steps per rank, AdamW lr 0.002.

Every tested rank recovered dense trajectory score 1.0.

Most important result:

- rank 2 routed-weight ratio: **0.5703125**;
- pre score: **0.050926**;
- post task-aware score: **1.000000**.

Interpretation: low-rank shared-basis capacity is sufficient for this fixture when optimized for task loss. C59 failed because post-hoc SVD was the wrong objective, not because rank2 was inherently incapable.

## 11. C61 — rank2 multi-seed composition robustness

Accepted commit: `6c74fa738721824268c2d2e8003f80ea21195f9e`.

Seeds:

- 20260911
- 20260912
- 20260913

For each seed:

1. train dense composition model from scratch for 300 steps;
2. initialize rank2 shared-basis from that dense model;
3. freeze all non-factor parameters;
4. task-aware factor recovery for 300 steps.

Results:

| seed | dense | pre | post | routed-weight ratio |
|---:|---:|---:|---:|---:|
| 20260911 | 1.0 | 0.060185 | 1.0 | 0.5703125 |
| 20260912 | 1.0 | 0.087963 | 1.0 | 0.5703125 |
| 20260913 | 1.0 | 0.027778 | 1.0 | 0.5703125 |

Summary:

- `all_dense_scores_one = true`
- `all_rank2_post_scores_match_dense = true`

Composition robustness is therefore reproduced across 3/3 independent seeds.

This is strong evidence for the family, but still not broad task generalization and not Gate C PASS.

## 12. Current decision after C61

Shared-basis is now the leading Gate-C candidate because it has shown:

1. ~57% routed-weight storage at the selected rank scaling;
2. improving large-width runtime scaling, reaching ~1.19x dense at width1024 in C58;
3. full task-aware recovery on the trusted composition fixture;
4. 3/3 independent composition seed recovery at the same storage ratio.

The next risk is **task-family generalization**. Do not integrate the production runtime yet; first verify that the result is not composition-specific.

Use rank rule:

```text
rank = max(1, width // 16)
```

For the current Gate-B tasks this yields:

- condition width16 -> rank1;
- composition width32 -> rank2;
- language width32 -> rank2.

With modules=2 and hidden_mult=2 this keeps combined routed Up+Down weight ratio at **0.5703125** for all three tasks.

## 13. Next experiment — C62

**Cross-task multi-seed shared-basis recovery.**

Tracked benchmark:

`fold/fold_lm/v05_benchmarks/gate_c_shared_basis_cross_task_multiseed.py`

Tasks:

- condition
- composition
- language

Seeds:

- 20260911
- 20260912
- 20260913

Per task/seed:

1. train independent dense V5-B model from scratch using the original Gate-B schedule;
2. rank = max(1, width//16);
3. initialize shared-basis from the dense routed weights;
4. freeze all non-factor parameters;
5. recover factors using task-native loss with lr 0.002;
6. compare recovered validation score against that seed's dense reference.

Dense / recovery schedules:

- condition: 260 / 260 steps, batch 32;
- composition: 300 / 300 steps, batch 64;
- language: 600 / 600 steps, batch 24.

Progress is printed at 25/50/75/100% of both dense and factor phases.

Primary decision field:

`summary.all_tasks_all_seeds_match_dense`

If true, shared-basis has passed a much stronger quality robustness screen and the next work should move to real factorized full-model runtime / memory integration and recurrence checks.

If false, inspect which task/seed fails before changing representation; a bounded task-specific recovery schedule adjustment may still be justified.

## 14. Handoff

On a new session:

1. read this ledger;
2. confirm branch/HEAD and protected hashes;
3. continue at the Next ID above;
4. keep one experiment per C number;
5. retry failures under the same number;
6. update this file after every accepted result or Gate decision change.
