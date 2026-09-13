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
9. Prefer tracked benchmark files over large chat-pasted runners.
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

The original universal rule `rank=max(1,width//16)` is rejected as a task-independent policy. Rank/capacity is adaptive by functional need.

## 5. Scientific discipline

Do not claim:

- Cxx PASS == Gate C PASS;
- fixture score 1.0 == broad language quality;
- synthetic scaling == production LLM scaling proof;
- FOLD beats Transformers / existing LLMs from these diagnostics.

Keep runtime, storage, representation capacity, optimizer policy, task quality, recurrence, and final Gate decisions separate.

## 6. Codebook path — C41 to C57

Key accepted findings:

- C41: dense registered bytes 51,200 vs compact 44,800, 12.5% reduction.
- C42: repeated Graph compact/dense median 1.028879.
- C45: GPU-only Graph compact/dense 1.05546.
- C46: remaining slowdown localized overwhelmingly to Up; Down ~1.006x dense.
- C49: sparse correction E only ~1-3% overhead.
- C51/C53: shared-base GEMM near dense; codebook delta/decode dominates.
- C54: full-M N16 reuse improves row-wise codebook path ~17.1%.
- C55: address precomputation only ~1-2% noisy gain.
- C56: width32 Up bank predecoded/dense 1.13357, compact/predecoded 1.65877, compact/dense 1.91422.
- C57: serialized ratio converges near 0.5703, but direct codebook execution fails to scale; width1024 compact/dense 12.88719, predecoded/dense 5.88088, compact/predecoded 2.18005.

Decision after C57: stop primary optimization of direct fine-grained codebook GPU execution.

## 7. C58 — shared-basis runtime/storage scaling

Accepted commit: `27077cdda37ca344da8ea5e6f8e491f613dbe1fa`.

Representation:

```text
W_module = W_base + A_module @ B_shared
```

Vendor-GEMM execution uses shared `F.linear` plus module-specific `addmm`.

At the scale diagnostic rank rule, persistent routed-weight ratio = 0.578125.

`shared_basis / dense` paired median:

- width32 3.12043
- width64 2.94781
- width128 4.86182
- width256 1.63577
- width512 1.29614
- width1024 1.19407

Large widths scale in the desired direction.

## 8. C59-C61 — quality recovery

- C59: post-hoc SVD is not an adequate task objective. Composition rank2 ratio0.5703125 scored only 0.050926.
- C60: task-aware factor tuning recovers composition rank2 from 0.050926 to 1.0 with non-factors frozen.
- C61: composition rank2 recovery reproduces 3/3 seeds at score1.0 and ratio0.5703125.

## 9. C62-C64 — task-dependent capacity and checkpoint behavior

### C62

Cross-task recovery showed:

- composition rank2: 3/3 dense match;
- condition rank1: systematically insufficient;
- language rank2: capacity exists, but one seed degrades during continued tuning.

### C63

Accepted valid retry commit: `76011ee9108408d2275e39f3cab45518ea0a3b7b`.

Condition post-hoc recovery frontier:

| rank | routed-weight ratio | all final meet dense |
|---:|---:|:---:|
| 1 | 0.5703125 | false |
| 2 | 0.6406250 | false |
| 4 | 0.7812500 | true |
| 6 | 0.9218750 | true |
| 7 | 0.9921875 | true |

Minimum robust tested condition rank = 4.

### C64

Accepted commit: `cd7de1cf7724e25526cba88eced89cc7cf4f4c43`.

Language rank2 reaches dense at the best checkpoint but can overtrain; rank4 and rank8 finish at 1.0 for all three seeds. Capacity and optimizer/checkpoint policy are distinct dimensions.

## 10. C65-C67 — native joint training

### C65

Accepted commit: `1196cb369eb90d0d15394aa1ffce0c31a7e950a7`.

Native shared-basis training from untrained initialization:

- condition rank4 ratio0.78125: almost dense;
- composition rank2 ratio0.5703125: 3/3 dense match;
- language rank4 ratio0.640625: unstable when factor lr0.002 and common lr0.01.

### C66

Accepted commit: `ab84b6c15d0b959c120904898e35d0ce89950698`.

Language rank4, common lr0.01, factor LR sweep:

| factor LR | final mean | min final | all final meet dense |
|---:|---:|---:|:---:|
| 0.002 | 0.787879 | 0.545455 | false |
| 0.005 | 0.939394 | 0.818182 | false |
| 0.010 | 1.000000 | 1.000000 | true |

Conclusion: from-scratch joint training requires factor/common co-adaptation; a post-hoc recovery LR does not transfer automatically.

### C67

Accepted commit: `c5bda0b605837903a29dbe2b7ae08820bee80a69`.

Cross-task rule:

```text
factor_lr = common_lr
```

- composition rank2/lr0.005: 3/3 dense match;
- language rank4/lr0.01: 3/3 dense match;
- condition rank4/lr0.01: validation deltas 0, -1/128, -1/128.

The condition residual was too small to justify changing capacity before a full-domain check.

## 11. C68 — exhaustive condition generalization

Accepted run commit: `8f2ee6c0df66f2d7a81072a5b51432ba175e17e5`.

Experiment ID: `C68-shared-basis-condition-exhaustive-generalization`.

C67 condition training is reproduced exactly, then each model is evaluated on every condition trajectory not used for training. Domain size = 32,768; training = 256; exhaustive held-out = **32,512 per seed**.

Results:

| seed | dense exact | direct exact | delta | dense-only | direct-only | net direct |
|---:|---:|---:|---:|---:|---:|---:|
| 20260911 | 0.99569392 | 0.99818528 | +0.00249135 | 28 | 109 | +81 |
| 20260912 | 0.99424827 | 0.98785067 | -0.00639760 | 289 | 81 | -208 |
| 20260913 | 0.97397882 | 0.98056102 | +0.00658220 | 216 | 430 | +214 |

Summary:

- mean exact delta = **+0.00089198**;
- median exact delta = **+0.00249135**;
- min = -0.00639760;
- max = +0.00658220;
- direct-only correct total = **620**;
- dense-only correct total = **533**;
- pooled net direct advantage = **+87**;
- `all_exhaustive_direct_match_or_exceed_dense = false` because seed20260912 favors dense.

### C68 interpretation

The 128-example residual was not purely sampling noise: seed20260912 retains a real full-domain dense advantage. However, there is **no consistent directional deficit** for rank4 shared-basis condition training:

- direct wins 2/3 seeds;
- dense wins 1/3 seeds;
- the three-seed mean and pooled paired count favor direct.

Therefore the current evidence points more strongly to **initialization/optimizer seed variance** than to a systematic rank4 capacity deficit. Do not increase rank yet. First quantify seed robustness under the exact same training rule.

## 12. Current design decision after C68

Shared-basis remains the leading Gate-C representation family.

Current evidence supports:

1. **adaptive capacity/rank** by functional need;
2. **co-adaptation-aware training**, with `factor_lr = common_lr` a strong default for current tasks;
3. composition and language native training are robust across the accepted 3 seeds at materially lower routed-weight storage;
4. condition rank4 is not consistently worse than dense, but has material seed-to-seed variance even under exhaustive evaluation;
5. increasing rank before quantifying this variance would confound capacity with optimization robustness.

Gate C remains **NOT PASSED**. Production runtime integration and recurrence validation are still pending.

### Auto-Partition living spec

The implementation-preparation document is:

`fold/docs/shared-basis-auto-module-partition-report.md`

This is a **living design document**, not a frozen hypothesis report. Accepted experiments that materially affect any of the following must also update that document:

```text
rank / capacity allocation
native shared-basis training
factor/common co-adaptation
seed / validation robustness
shared grouping compatibility
residual / gradient diagnostics
runtime reuse
recurrence / structure-change safety
```

At minimum, update its:

```text
Evidence Ledger
Current Decision / Decision Table
Implementation Defaults
Open Questions / Next Validation
```

Invalid Cxx runs must not be used to revise its scientific conclusions.

## 13. Next experiment — C69

**Condition rank4 aligned-lr 12-seed exhaustive robustness.**

Tracked benchmark:

`fold/fold_lm/v05_benchmarks/gate_c_shared_basis_condition_12seed_exhaustive_robustness.py`

Benchmark creation commit: `691df35bd768f2c24932168d3c1ac5fd8ec07cfe`.

Question: does C68's mixed sign persist across more initializations, or is there a systematic dense/direct bias?

Fixed setup:

- condition only;
- rank4;
- dense and direct lr0.01;
- 260 steps;
- batch32;
- training size256;
- exhaustive held-out size32,512;
- seeds `20260911..20260922` (12 total).

The first three seeds must exactly reproduce accepted C68 metrics. No rank, optimizer, architecture, or initialization rule is changed.

Primary outputs:

- mean/median/min/max exhaustive exact delta;
- direct-win / dense-win / tie seed counts;
- simple two-sided seed sign-test diagnostic;
- pooled dense-only / direct-only correct counts and net advantage;
- first-three-seed C68 reproduction assertion.

Interpretation:

- if deltas center near zero with mixed signs, treat remaining condition difference primarily as seed/optimization variance and proceed to runtime/recurrence work without spending extra rank yet;
- if dense wins most seeds with negative mean/median and pooled disadvantage, then direct condition training has a real robustness deficit and C70 should diagnose rank or training schedule;
- if direct wins most seeds, rank4 native shared-basis is at least competitive on this complete synthetic condition domain despite individual seed reversals.

C69 does not define a formal equivalence margin and cannot establish Gate C passage alone.

## 14. Handoff

On a new session:

1. read this ledger;
2. confirm branch/HEAD and protected hashes;
3. continue at C69;
4. keep one experiment per C number;
5. retry failures under the same number;
6. update this file after every accepted result or Gate decision change;
7. if an accepted result affects Auto-Partition assumptions or implementation defaults, also update `fold/docs/shared-basis-auto-module-partition-report.md` in the same repo-maintenance step.