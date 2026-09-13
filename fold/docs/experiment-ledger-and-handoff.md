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

1. Run exactly one experiment / verification step per C number.
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

The original universal rule `rank=max(1,width//16)` is rejected as a task-independent policy. Rank/capacity is treated as an adaptive design/training variable.

## 5. Scientific discipline

Do not claim:

- Cxx PASS == Gate C PASS;
- fixture score 1.0 == broad language quality;
- synthetic scaling == production LLM scaling proof;
- FOLD beats Transformers / existing LLMs from these diagnostics.

Keep runtime, storage, representation capacity, optimizer policy, task quality, recurrence, and final Gate decisions separate.

## 6. Codebook path — key accepted findings

- C41: registered model bytes 51,200 B dense vs 44,800 B compact, **12.5% reduction**.
- C42: repeated Graph request compact/dense median **1.028879**.
- C45: GPU-only Graph compact/dense **1.05546**.
- C46: remaining full-model slowdown localized overwhelmingly to Up; Down ~1.006x dense.
- C49: sparse correction E only ~1-3% overhead.
- C51/C53: shared-base GEMM near dense; codebook delta/decode dominates.
- C54: full-M N16 reuse improves row-wise codebook path by ~17.1%.
- C55: address precomputation gives only ~1-2% noisy gain.
- C56: width32 real Up bank: predecoded Triton/dense **1.13357**, compact/predecoded **1.65877**, compact/dense **1.91422**.
- C57: codebook serialized ratio converges near **0.5703**, but direct execution does not scale. At width1024: compact/dense **12.88719**, predecoded/dense **5.88088**, compact/predecoded **2.18005**.

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

## 8. C59-C61 — post-hoc fitting vs task-aware recovery

### C59

Accepted commit: `32f07a9abd5fd566c041134940a5a543bd11cd44`.

Post-hoc mean-base + truncated-SVD fitting fails badly at low rank on the trusted composition fixture. Rank2 ratio 0.5703125 scores 0.050926; rank32 reproduces dense but uses 1.625x routed-weight bytes.

Conclusion: weight reconstruction is not the right task objective.

### C60

Accepted commit: `a713fe66101a0f99a38100117340286cd7ed5afe`.

Task-aware factor tuning with all non-factor parameters frozen recovers dense composition score 1.0 for every tested rank 2/4/8/12/14. Rank2 recovers 0.050926 -> 1.0 at ratio 0.5703125.

### C61

Accepted commit: `6c74fa738721824268c2d2e8003f80ea21195f9e`.

Rank2 composition recovery reproduces across seeds 20260911/12/13: all dense and post-recovery scores 1.0 at routed-weight ratio 0.5703125.

## 9. C62 — cross-task multi-seed recovery

Accepted commit: `514f1a4d6ef4f455af586f195de3add4b372ad15`.

Initial equal-ratio rule:

- condition width16 -> rank1
- composition width32 -> rank2
- language width32 -> rank2

All had routed-weight ratio 0.5703125.

Results:

- composition: 3/3 recover exactly to dense;
- condition: all improve strongly but remain below dense at rank1;
- language: two seeds are already 1.0 after SVD initialization; seed20260911 degrades 0.909091 -> 0.818182 during factor tuning despite decreasing training loss.

Decision: split condition capacity and language optimization/checkpoint questions.

## 10. C63 — condition rank frontier

Accepted valid retry commit: `76011ee9108408d2275e39f3cab45518ea0a3b7b`.

First attempt at `a01cff8e1e9751546ec5da77c13221cf28580b51` was invalid before experiment execution due an import path typo. Retry retained C63.

Condition, 3 seeds, factor lr0.002:

| rank | ratio | all final meet dense | all best checkpoints meet dense |
|---:|---:|:---:|:---:|
| 1 | 0.5703125 | false | false |
| 2 | 0.6406250 | false | false |
| 4 | 0.7812500 | **true** | **true** |
| 6 | 0.9218750 | true | true |
| 7 | 0.9921875 | true | true |

Primary result: minimum robust tested rank = **4**.

## 11. C64 — language rank/checkpoint frontier

Accepted commit: `cd7de1cf7724e25526cba88eced89cc7cf4f4c43`.

Language, 3 seeds, ranks2/4/8, factor lr0.002, validation every50 steps.

Rank2 ratio 0.5703125:

- all best checkpoints meet dense;
- final checkpoints do not all meet dense;
- seed20260911: 0.909091 at step0 -> **1.0 at step50** -> 0.909091 at step100 -> 0.818182 from step200 onward.

Therefore rank2 has sufficient functional capacity; failure is optimization/checkpoint policy.

Rank4 ratio 0.640625 and rank8 ratio 0.78125 both finish at 1.0 for all three seeds.

## 12. C65 — direct joint training from initialization

Accepted commit: `1196cb369eb90d0d15394aa1ffce0c31a7e950a7`.

Purpose: test native factorized training instead of training a dense routed bank first.

Candidate uses selected stable-final ranks:

- condition: rank4, ratio **0.78125**;
- composition: rank2, ratio **0.5703125**;
- language: rank4, ratio **0.640625**.

All ordinary/shared/core/surrounding parameters train. Factors use lr0.002; ordinary/common parameters use each task's original LR.

Results:

### Condition

- seed20260911: dense1.0, direct0.992188
- seed20260912: dense1.0, direct1.0
- seed20260913: dense0.984375, direct1.0

### Composition

3/3 direct score 1.0, exactly matching dense. Direct trainable parameter ratio = **0.725**.

### Language

- seed20260911: dense1.0, direct0.818182
- seed20260912: dense1.0, direct0.545455
- seed20260913: dense1.0, direct1.0

Primary field: `all_tasks_all_seeds_direct_match_or_exceed_dense = false`.

Interpretation: native shared-basis training is possible, but language co-adaptation is unstable under the lr split. Do not change representation before testing optimizer balance.

## 13. C66 — direct-joint language factor-LR frontier

Accepted commit: `ab84b6c15d0b959c120904898e35d0ce89950698`.

Fixed:

- language rank4;
- common/non-factor lr = **0.01**;
- 3 seeds;
- 600 steps;
- same initialization and batch sequence as C65.

Only factor LR changed:

- 0.002
- 0.005
- 0.01

### Results

| factor LR | final score mean | min final | all final meet dense | all best meet dense |
|---:|---:|---:|:---:|:---:|
| 0.002 | 0.787879 | 0.545455 | false | false |
| 0.005 | 0.939394 | 0.818182 | false | false |
| **0.010** | **1.000000** | **1.000000** | **true** | **true** |

Critical seed20260912 progression at factor_lr0.01:

- step50: 0.818182
- step100: 0.909091
- step400: **1.0**
- step600: **1.0**

Primary results:

- `minimum_tested_factor_lr_all_final_meet_dense = 0.01`
- `minimum_tested_factor_lr_all_best_checkpoints_meet_dense = 0.01`

### C66 interpretation

C65 language instability was primarily caused by **factor/common co-adaptation imbalance**, not rank4 capacity. When factors use the same lr as the common/shared parameters, all 3 seeds reach and retain dense validation quality.

This materially strengthens the training hypothesis:

```text
native shared-basis training needs coordinated adaptation rates
```

A factor LR inherited from post-hoc recovery (`0.002`) is not automatically appropriate for from-scratch joint training. At least on the current language task, the factor side must move at roughly the same rate as the surrounding/shared side.

## 14. Current design decision after C66

Shared-basis remains the leading Gate-C representation family.

Current evidence supports two separate adaptive dimensions:

1. **capacity allocation** — rank depends on functional/task need;
2. **training-rate allocation** — factor/shared learning rates must permit co-adaptation.

The next bounded question is whether one simple rule works across the three existing task families:

```text
factor_lr = common_lr
```

Do not move to production runtime integration until this direct-training rule is checked cross-task. Condition's C65 one-sample miss may also disappear under aligned lr.

## 15. Next experiment — C67

**Aligned factor/common LR direct joint training across all Gate-B task families.**

Tracked benchmark:

`fold/fold_lm/v05_benchmarks/gate_c_shared_basis_aligned_joint_training.py`

Tasks / ranks / aligned learning rates:

- condition: rank4, common=factor lr **0.01**;
- composition: rank2, common=factor lr **0.005**;
- language: rank4, common=factor lr **0.01**.

Seeds:

- 20260911
- 20260912
- 20260913

Everything else matches C65:

1. build one seeded untrained dense model;
2. clone to dense reference and shared-basis candidate;
3. factorize candidate before any task training;
4. train both from initialization with the same task-native batch schedule;
5. compare final validation score and parameter/storage accounting.

Only changed training rule relative to C65:

```text
factor_lr = common_lr
```

Primary field:

`summary.all_tasks_all_seeds_direct_match_or_exceed_dense`

Interpretation:

- if true, native shared-basis training has a simple cross-task co-adaptation rule on the current benchmark family, and the project can move toward real factorized runtime/memory integration plus recurrence validation;
- if only condition or composition regresses, diagnose task-specific optimizer ratio rather than changing the representation;
- if language regresses despite C66, C67 is invalid or non-equivalent and must be investigated before proceeding.

C67 cannot establish Gate C pass by itself.

## 16. Handoff

On a new session:

1. read this ledger;
2. confirm branch/HEAD and protected hashes;
3. continue at the Next ID above;
4. keep one experiment per C number;
5. retry failures under the same number;
6. update this file after every accepted result or Gate decision change.
