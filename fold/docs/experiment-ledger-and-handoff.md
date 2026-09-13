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

Current training default supported by C66-C69:

```text
factor_lr = common_lr
```

for native shared-basis joint training on the present Gate-B tasks.

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

Vendor-GEMM execution uses:

1. shared `F.linear(x, [W_base; B_shared])`;
2. module-specific `addmm` from shared latent through `A_module.T`.

At the C58 matched-storage rank rule, persistent routed-weight ratio = 0.578125.

`shared_basis / dense` paired median:

- width32 3.12043
- width64 2.94781
- width128 4.86182
- width256 1.63577
- width512 1.29614
- width1024 1.19407

Large widths scale in the desired direction. C58 is synthetic runtime/storage evidence only.

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

Language rank2 reaches dense at its best checkpoint but can overtrain. Rank4/8 finish at 1.0 for all three seeds. Capacity and optimizer/checkpoint policy are distinct dimensions.

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

The remaining condition difference required larger evaluation before any capacity change.

## 11. C68 — exhaustive condition generalization

Accepted run commit: `8f2ee6c0df66f2d7a81072a5b51432ba175e17e5`.

C67 condition training was reproduced and evaluated over all 32,512 held-out trajectories per seed.

| seed | dense exact | direct exact | delta | dense-only | direct-only | net direct |
|---:|---:|---:|---:|---:|---:|---:|
| 20260911 | 0.99569392 | 0.99818528 | +0.00249135 | 28 | 109 | +81 |
| 20260912 | 0.99424827 | 0.98785067 | -0.00639760 | 289 | 81 | -208 |
| 20260913 | 0.97397882 | 0.98056102 | +0.00658220 | 216 | 430 | +214 |

Summary:

- mean delta +0.00089198;
- direct wins 2/3 seeds;
- pooled net direct advantage +87.

Interpretation: rank4 condition is not consistently worse than dense; seed/optimization variance remained the leading explanation.

## 12. C69 — condition 12-seed exhaustive robustness

Accepted run commit: `632469b400e1cf325882d8c7aaf0d8f509357aab`.

Experiment ID:

`C69-shared-basis-condition-12seed-exhaustive-robustness`

Fixed setup:

- condition only;
- rank4;
- dense/direct aligned lr0.01;
- 260 steps, batch32, train size256;
- seeds `20260911..20260922`;
- exhaustive held-out = 32,512 per seed.

C68's first three seeds reproduced exactly.

Primary results:

- direct-win seeds = **6**;
- dense-win seeds = **6**;
- ties = 0;
- two-sided seed sign-test p = **1.0**;
- mean exhaustive exact delta = **-0.00025117894**;
- median delta = **-0.00006151199**;
- min = -0.00639760494;
- max = +0.00658220053;
- pooled dense-only correct = **1,446**;
- pooled direct-only correct = **1,348**;
- pooled net direct advantage = **-98** across 390,144 held-out trajectories.

### C69 interpretation

The sign pattern is exactly balanced and the center is extremely close to zero. The small pooled direct disadvantage is not accompanied by a consistent seed-level direction.

Therefore, on the existing complete synthetic condition domain:

1. there is **no evidence of a systematic rank4 shared-basis quality deficit** large enough to justify increasing rank;
2. the remaining dense/direct difference is best treated primarily as initialization/optimizer variance at this stage;
3. condition rank4 remains the selected point, with routed-weight ratio 0.78125;
4. further rank tuning is lower priority than validating the intended runtime form and recurrence behavior.

This is not broad model equivalence: C69 covers one tiny synthetic task family.

## 13. Current design decision after C69

Shared-basis remains the leading Gate-C representation family.

Current quality/training defaults for the existing tasks:

- composition: rank2, routed ratio0.5703125, aligned native LR;
- language: rank4 for stable fixed-schedule native training, ratio0.640625;
- condition: rank4, ratio0.78125; 12-seed exhaustive evidence is centered near dense with mixed signs;
- native joint training default: `factor_lr = common_lr` unless later evidence overrides it.

Do **not** spend another C-number increasing condition rank on current evidence.

The next Gate-C gap is that quality experiments use a factorized representation whose reference forward materializes effective routed weights, while the intended fast runtime is the C58 GEMM-native form. Before production integration or timing, establish numerical/semantic equivalence under repeated state updates.

Gate C remains **NOT PASSED** because production-like factorized runtime, resident/serialized accounting for the selected task-dependent ranks, and recurrence/runtime validation are not complete.

### Auto-Partition living spec

The implementation-preparation document is:

`fold/docs/shared-basis-auto-module-partition-report.md`

Accepted experiments affecting rank/capacity, co-adaptation, seed robustness, grouping assumptions, runtime reuse, or recurrence must update it. C69 specifically strengthens the multi-seed persistence requirement and argues against structure changes on tiny mean deltas with mixed signs.

## 14. Next experiment — C70

**GEMM-native shared-basis execution equivalence under recurrence.**

Tracked benchmark:

`fold/fold_lm/v05_benchmarks/gate_c_shared_basis_runtime_recurrence_equivalence.py`

Benchmark creation commit:

`9010b62d892f701f3e34c6a0e6db56c60cff8848`

Question: can the C58-style GEMM-native formula replace effective-weight materialization without changing the trained model's observable behavior as recurrent state updates accumulate?

Setup:

- tasks: condition / composition / language;
- seeds: 20260911 / 20260912 / 20260913;
- selected ranks: condition4 / composition2 / language4;
- direct training uses accepted aligned rule `factor_lr = common_lr`;
- reference execution materializes `W_base + A_module @ B_shared`;
- candidate execution stores `[W_base; B_shared]`, runs one shared projection, then coefficient `addmm`; no effective routed weight is materialized;
- complete validation outputs are compared;
- independent core stress uses deterministic contexts and alternating routes for recurrence depths 1,2,4,8,16,32,64;
- declared numerical comparison uses `rtol=5e-4`, `atol=1e-4`.

Primary output:

`summary.all_runtime_formula_equivalent`

Supporting outputs:

- validation output max-abs gap;
- exact validation score equality;
- semantic prediction equality;
- recurrence max-abs and relative-L2 gaps;
- all-depth recurrence allclose.

Interpretation:

- if true, proceed to C71 production-like latency/resident-memory benchmark and then integration;
- if validation is equal but recurrence drift exceeds tolerance, diagnose arithmetic ordering / recurrent numerical stability before production integration;
- if task semantics change immediately, the GEMM-native implementation is incorrect and C70 must be fixed/diagnosed before any timing comparison.

C70 intentionally does **not** modify `fold_lm/v05/modules.py`; it is a pre-integration correctness gate.

## 15. Handoff

On a new session:

1. read this ledger;
2. confirm branch/HEAD and protected hashes;
3. continue at C70;
4. keep one experiment per C number;
5. retry failures under the same number;
6. update this file after every accepted result or Gate decision change;
7. if an accepted result affects Auto-Partition assumptions or implementation defaults, update `fold/docs/shared-basis-auto-module-partition-report.md` in the same maintenance step.
