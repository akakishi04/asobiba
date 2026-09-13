# FOLD Experiment Ledger and Handoff

> Project-wide handoff checkpoint for FOLD. Read this first in a new session. Update it after every accepted Cxx result, retry decision, or Gate decision change.

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

## 2. Protected artifacts

### C37 protected result

- Path: `M:\asobiba\fold\runs\chatgpt-last-result.json`
- SHA256: `FD4A8DA897BDAEA9D103A252E30212C7FF842D23300D7C837333E146DEE51931`

### Runtime fixture

- Path: `M:\asobiba\fold\runs\fixtures\v05-c-composition-20260921.pt`
- SHA256: `A52F8209703149407580F7E2965B61B78653030EE992AF6D759865736741CA9E`

Diagnostics must preserve both.

## 3. Experiment protocol

Experiment IDs are `Cxx`.

1. Run one experiment / verification step per C number.
2. Full console output overwrites `M:\asobiba\fold\runs\chatgpt-last.log`.
3. User pastes the full log back into ChatGPT.
4. ChatGPT judges the result.
5. Increment only after successful completion.
6. Failed retries keep the same C number.
7. `status=PASS` means the experiment executed correctly, not that Gate C passed.
8. Invalid runner/import/parser/hash/experiment-ID runs are not evidence.
9. Prefer tracked benchmark files over giant chat-pasted Python payloads.
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

A candidate must preserve quality with materially lower serialized/resident bytes, or beat the reference at equal capacity, while recurrence remains bounded/explainable and runtime remains practical.

Original direct block-codebook execution is retained only as a storage/reference baseline. Current lead routed-weight family:

```text
W_module = W_base + A_module @ B_shared
```

The initial universal rule `rank=max(1,width//16)` is rejected as a task-independent policy. Rank/capacity is now treated as a learned/design allocation variable.

## 5. Scientific discipline

Do not claim:

- Cxx PASS == Gate C PASS;
- fixture score 1.0 == broad language quality;
- synthetic scaling == production LLM scaling proof;
- FOLD beats Transformers / existing LLMs from these diagnostics.

Keep runtime, storage, representation capacity, optimization policy, task quality, recurrence, and final Gate decisions separate.

## 6. Codebook path — key accepted findings

- C41: registered model bytes 51,200 B dense vs 44,800 B compact, **12.5% reduction**.
- C42: repeated Graph request compact/dense median **1.028879**.
- C45: GPU-only Graph compact/dense **1.05546**.
- C46: remaining full-model slowdown localized overwhelmingly to Up; Down ~1.006x dense.
- C49: sparse correction E only ~1-3% overhead; not the main blocker.
- C51/C53: shared-base GEMM near dense; codebook delta/decode dominates.
- C54: full-M N16 reuse improves the row-wise codebook path by ~17.1%.
- C55: address precomputation gives only ~1-2% noisy gain.
- C56: width32 real Up bank: predecoded Triton/dense **1.13357**, compact/predecoded **1.65877**, compact/dense **1.91422**.
- C57 scale sweep: codebook serialized ratio converges near **0.5703**, but direct execution does not scale. At width1024: compact/dense **12.88719**, predecoded/dense **5.88088**, compact/predecoded **2.18005**.

Decision after C57: stop primary optimization of direct fine-grained codebook GPU execution.

## 7. C58 — shared-basis runtime/storage scaling

Accepted commit: `27077cdda37ca344da8ea5e6f8e491f613dbe1fa`.

Representation:

```text
W_module = W_base + A_module @ B_shared
```

Runtime uses vendor GEMM-family operations:

1. shared `F.linear(x, [W_base; B_shared])`;
2. module-specific `addmm` from latent to output.

Rank = width/16 in this diagnostic. Persistent routed-weight ratio: **0.578125**.

`shared_basis / dense` paired median:

- width32: 3.12043
- width64: 2.94781
- width128: 4.86182
- width256: 1.63577
- width512: 1.29614
- width1024: **1.19407**

Interpretation: small sizes are launch/shape dominated; large widths scale in the desired direction.

## 8. C59 — post-hoc quality frontier

Accepted commit: `32f07a9abd5fd566c041134940a5a543bd11cd44`.

Trusted composition fixture, width32, hidden64, modules2, dense score 1.0. Post-hoc mean-base + truncated-SVD fit only.

| rank | routed-weight ratio | score |
|---:|---:|---:|
| 2 | 0.5703125 | 0.050926 |
| 4 | 0.640625 | 0.115741 |
| 8 | 0.781250 | 0.125000 |
| 12 | 0.921875 | 0.166667 |
| 14 | 0.9921875 | 0.300926 |
| 32 | 1.625000 | 1.000000 |

Conclusion: post-hoc SVD is not an adequate task objective; weight reconstruction error and functional quality are not interchangeable.

## 9. C60 — task-aware shared-basis recovery

Accepted commit: `a713fe66101a0f99a38100117340286cd7ed5afe`.

Only shared-basis routed-weight factors trained; all non-factor parameters frozen. Composition fixture.

Every tested rank 2/4/8/12/14 recovered dense score 1.0. Most important:

- rank2 ratio **0.5703125**
- pre score **0.050926**
- post task-aware score **1.000000**

Conclusion: low-rank capacity is sufficient on this task when optimized for task loss.

## 10. C61 — composition multi-seed robustness

Accepted commit: `6c74fa738721824268c2d2e8003f80ea21195f9e`.

Rank2, three independently trained dense seeds:

| seed | dense | pre | post | ratio |
|---:|---:|---:|---:|---:|
| 20260911 | 1.0 | 0.060185 | 1.0 | 0.5703125 |
| 20260912 | 1.0 | 0.087963 | 1.0 | 0.5703125 |
| 20260913 | 1.0 | 0.027778 | 1.0 | 0.5703125 |

Composition rank2 recovery reproduced 3/3.

## 11. C62 — cross-task multi-seed recovery

Accepted commit: `514f1a4d6ef4f455af586f195de3add4b372ad15`.

Initial uniform ratio rule:

- condition width16 -> rank1
- composition width32 -> rank2
- language width32 -> rank2

All had routed-weight ratio 0.5703125.

Results:

- composition: 3/3 seeds recover exactly to dense.
- condition: all three improve strongly but all remain below dense at rank1.
- language: two seeds are already 1.0 after SVD initialization; seed 20260911 degrades from pre 0.909091 to final 0.818182 despite training loss decreasing.

`all_tasks_all_seeds_match_dense = false`.

Decision: split condition capacity and language optimization/checkpoint questions.

## 12. C63 — condition rank frontier

Accepted valid retry commit: `76011ee9108408d2275e39f3cab45518ea0a3b7b`.

First attempt at `a01cff8e1e9751546ec5da77c13221cf28580b51` was invalid before experiment execution due an import path typo. Protected artifacts remained unchanged and C63 was retried under the same ID.

Condition, 3 seeds, 260 factor steps, lr 0.002:

| rank | ratio | all final meet dense | all best checkpoints meet dense |
|---:|---:|:---:|:---:|
| 1 | 0.5703125 | false | false |
| 2 | 0.6406250 | false | false |
| 4 | 0.7812500 | **true** | **true** |
| 6 | 0.9218750 | true | true |
| 7 | 0.9921875 | true | true |

Primary result:

- `minimum_rank_all_final_meet_dense = 4`
- `minimum_rank_all_best_checkpoints_meet_dense = 4`

Interpretation: condition is genuinely more capacity-demanding in this setup. Rank4 is the first tested robust point and remains 21.875% below independent dense routed-weight bytes.

## 13. C64 — language rank/checkpoint frontier

Accepted commit: `cd7de1cf7724e25526cba88eced89cc7cf4f4c43`.

Language, 3 seeds, ranks 2/4/8, 600 factor steps, lr 0.002, validation every 50 steps.

### Rank2 — ratio 0.5703125

- all **best checkpoints** meet dense.
- all **final checkpoints** do not meet dense because seed 20260911 overtrains.
- seed 20260911:
  - step0: 0.909091
  - step50: **1.000000**
  - step100: 0.909091
  - step200 onward: 0.818182
  - step600 final: 0.818182
- training loss continues decreasing while validation accuracy degrades.

Therefore rank2 has sufficient functional capacity; the failure is optimization/checkpoint policy, not a clean capacity failure.

### Rank4 — ratio 0.640625

All three seeds are 1.0 at the final checkpoint and remain stable through the tested schedule.

### Rank8 — ratio 0.78125

All three seeds are also 1.0 throughout the tested schedule.

Primary results:

- `minimum_rank_all_final_meet_dense = 4`
- `minimum_rank_all_best_checkpoints_meet_dense = 2`
- `seed_20260911_rank2_best_score = 1.0`
- `seed_20260911_rank2_best_step = 50`
- `seed_20260911_rank2_final_score = 0.818181872...`

Interpretation:

1. language rank2 capacity is sufficient;
2. rank2 requires validation-aware training/early stopping or a better optimization schedule on at least one seed;
3. rank4 is the first tested rank robust to the fixed 600-step final-checkpoint policy;
4. capacity allocation and training policy must be treated separately.

## 14. Current design decision after C64

Shared-basis remains the leading Gate-C family.

Current stable-final quality points under the bounded schedules:

- condition: rank4, routed-weight ratio **0.78125**;
- composition: rank2, ratio **0.5703125**;
- language: rank4, ratio **0.640625**.

Current minimum-capacity evidence is subtler:

- composition rank2 is robust;
- condition rank2 is close but not robust, rank4 required in the tested frontier;
- language rank2 is sufficient if checkpoint selection is validation-aware, while rank4 is stable without early stopping.

The universal rank=width/16 rule is rejected. Future FOLD should treat routed capacity/rank as adaptive to learned functional need. This does not yet imply each module can independently have a different physical basis width; the current shared-basis bank uses one rank per routed bank. Per-module effective rank/masking is a future design option, not yet implemented.

The next architectural question is no longer whether a trained dense model can be compressed and recovered. It is whether the factorized/shared-basis representation can be **trained directly from initialization** without first creating a trained dense routed bank.

## 15. Next experiment — C65

**Direct joint training from untrained shared-basis initialization.**

Tracked benchmark:

`fold/fold_lm/v05_benchmarks/gate_c_shared_basis_direct_joint_training.py`

Tasks / selected stable-final ranks:

- condition: rank4
- composition: rank2
- language: rank4

Seeds:

- 20260911
- 20260912
- 20260913

Per task/seed:

1. build one ordinary untrained V5-B model using the normal seeded initialization;
2. clone it into a dense reference and a shared-basis candidate;
3. before any task training, replace the candidate routed Up/Down matrices with the selected shared-basis form, initialized by truncated SVD of the random initial routed weights;
4. train dense and factorized models independently from that common initialization;
5. all shared/core/norm/bias/gate/surrounding parameters are trainable in the factorized candidate;
6. ordinary parameters use the task's original Gate-B learning rate; shared-basis factor parameters use lr 0.002;
7. compare final validation score and trainable-parameter count.

Original task schedules are retained:

- condition: 260 steps, batch32, common lr0.01;
- composition: 300 steps, batch64, common lr0.005;
- language: 600 steps, batch24, common lr0.01.

Primary field:

`summary.all_tasks_all_seeds_direct_match_or_exceed_dense`

Interpretation:

- if true, shared-basis is viable as a native training representation rather than only a post-training compression/recovery format;
- if only one task fails, diagnose its direct-training schedule before changing the representation;
- if broad failure occurs, post-hoc recovery success did not transfer to native joint training and the training architecture needs revision.

C65 is a training-feasibility experiment. Production factorized runtime/memory integration and recurrence validation remain subsequent Gate-C work.

## 16. Handoff

On a new session:

1. read this ledger;
2. confirm branch/HEAD and protected hashes;
3. continue at the Next ID above;
4. keep one experiment per C number;
5. retry failures under the same number;
6. update this file after every accepted result or Gate decision change.
