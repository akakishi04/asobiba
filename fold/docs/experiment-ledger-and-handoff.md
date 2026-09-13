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
8. Invalid runner/parser/hash/experiment-ID runs are not evidence.
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

A candidate must preserve quality with materially lower serialized/resident bytes, or beat the reference at equal capacity, while recurrence remains stable and runtime does not become impractical.

Original direct codebook execution is retained as a storage/reference baseline but is no longer the primary execution candidate.

Current lead routed-weight family:

```text
W_module = W_base + A_module @ B_shared
```

The initial rank rule under test was:

```text
rank = max(1, width // 16)
```

For modules=2, hidden_mult=2 this gives routed Up+Down weight ratio `0.5703125` at widths 16/32.

## 5. Scientific discipline

Do not claim:

- Cxx PASS == Gate C PASS;
- fixture score 1.0 == broad language quality;
- synthetic scaling == production LLM scaling proof;
- FOLD beats Transformers / existing LLMs from these diagnostics.

Separate runtime, storage, capacity, task quality, recurrence, and final gate decisions.

## 6. Key codebook findings — C41 to C57

- C41: registered model bytes 51,200 B dense vs 44,800 B compact, 12.5% reduction.
- C42: repeated Graph compact/dense median `1.028879`.
- C45: GPU-only Graph compact/dense `1.05546`.
- C46: remaining slowdown localized overwhelmingly to Up; Down ~1.006x dense.
- C49: sparse correction E only ~1-3% overhead.
- C51/C53: shared-base GEMM near dense; codebook delta/decode dominates.
- C54: full-M N16 reuse beats row-wise by ~17.1%.
- C55: address precomputation gives only ~1-2% noisy gain.
- C56: width32 Up bank: predecoded Triton/dense `1.13357`, compact/predecoded `1.65877`, compact/dense `1.91422`.
- C57: codebook serialized ratio converges ~0.5703, but direct execution fails to scale; at width1024 fixed-tile compact/dense `12.88719`, predecoded/dense `5.88088`, compact/predecoded `2.18005`.

Decision after C57: stop primary optimization of direct fine-grained codebook GPU execution. Keep it as storage/reference baseline.

## 7. C58 — shared-basis runtime/storage scale

Accepted commit: `27077cdda37ca344da8ea5e6f8e491f613dbe1fa`.

Representation:

```text
W_module = W_base + A_module @ B_shared
```

Vendor-GEMM execution:

1. `F.linear(x, [W_base; B_shared])`
2. module-specific `addmm` from latent to output

Rank = width/16. Persistent routed-weight ratio exactly `0.578125` in the scale diagnostic.

`shared_basis / dense` median:

- 32: 3.12043
- 64: 2.94781
- 128: 4.86182
- 256: 1.63577
- 512: 1.29614
- 1024: **1.19407**

Interpretation: small sizes are launch/shape dominated; large sizes scale in the desired direction.

## 8. C59 — post-hoc quality frontier

Accepted commit: `32f07a9abd5fd566c041134940a5a543bd11cd44`.

Trusted composition fixture, width32, hidden64, modules2, dense score 1.0. Post-hoc SVD only.

| rank | routed-weight ratio | score |
|---:|---:|---:|
| 2 | 0.5703125 | 0.050926 |
| 4 | 0.640625 | 0.115741 |
| 8 | 0.781250 | 0.125000 |
| 12 | 0.921875 | 0.166667 |
| 14 | 0.9921875 | 0.300926 |
| 32 | 1.625000 | 1.000000 |

Conclusion: post-hoc SVD is not an adequate objective; weight reconstruction error and task score are not interchangeable.

## 9. C60 — task-aware shared-basis recovery

Accepted commit: `a713fe66101a0f99a38100117340286cd7ed5afe`.

Only shared-basis factors trained; all non-factor parameters frozen.

Every tested composition rank recovered score 1.0.

Most important:

- rank2 routed-weight ratio `0.5703125`
- pre `0.050926`
- post `1.000000`

Interpretation: low-rank capacity is sufficient on this fixture when optimized for task loss.

## 10. C61 — composition multi-seed robustness

Accepted commit: `6c74fa738721824268c2d2e8003f80ea21195f9e`.

Three independent dense seeds, rank2 recovery:

| seed | dense | pre | post | ratio |
|---:|---:|---:|---:|---:|
| 20260911 | 1.0 | 0.060185 | 1.0 | 0.5703125 |
| 20260912 | 1.0 | 0.087963 | 1.0 | 0.5703125 |
| 20260913 | 1.0 | 0.027778 | 1.0 | 0.5703125 |

Composition robustness reproduced 3/3.

## 11. C62 — cross-task multi-seed shared-basis recovery

Accepted commit: `514f1a4d6ef4f455af586f195de3add4b372ad15`.

Tasks / ranks from the original rule:

- condition width16 -> rank1
- composition width32 -> rank2
- language width32 -> rank2

All use routed-weight ratio `0.5703125`.

### Condition

Dense vs final recovered:

| seed | dense | pre | post |
|---:|---:|---:|---:|
| 20260911 | 1.000000 | 0.398438 | 0.859375 |
| 20260912 | 1.000000 | 0.492188 | 0.945312 |
| 20260913 | 0.984375 | 0.468750 | 0.921875 |

All three improve strongly but all remain below their dense reference.

Conclusion: width16/rank1 is not sufficient under the bounded C62 recovery schedule. This is a systematic failure, so rank capacity must be tested before changing representation.

### Composition

All three seeds again recover exactly to dense score 1.0 at rank2.

Conclusion: C61 reproduced inside the cross-task experiment.

### Language

| seed | dense | pre | post |
|---:|---:|---:|---:|
| 20260911 | 1.000000 | 0.909091 | 0.818182 |
| 20260912 | 1.000000 | 1.000000 | 1.000000 |
| 20260913 | 1.000000 | 1.000000 | 1.000000 |

One seed degrades during task-aware factor tuning even though training loss decreases. Two seeds need no recovery at all after SVD initialization.

Conclusion: language failure is not clean evidence of rank2 capacity failure. It may reflect checkpoint/overfitting/schedule behavior. Diagnose separately from condition.

Primary C62 decision field:

`all_tasks_all_seeds_match_dense = false`

Therefore Gate C remains NOT PASSED.

## 12. Decision after C62

Shared-basis remains the leading candidate. Do not discard it and do not broaden the representation yet.

The failures separate into two questions:

1. **Condition capacity frontier:** does a slightly larger but still sub-dense rank recover all three condition seeds?
2. **Language optimization/checkpoint behavior:** did the failing seed ever match dense during tuning, and does a bounded rank/schedule adjustment solve it?

Keep these as separate numbered experiments.

## 13. Next experiment — C63

**Condition shared-basis sub-dense rank/checkpoint frontier.**

Tracked benchmark:

`fold/fold_lm/v05_benchmarks/gate_c_shared_basis_condition_rank_frontier.py`

Seeds:

- 20260911
- 20260912
- 20260913

Ranks:

- 1 -> ratio 0.5703125
- 2 -> ratio 0.640625
- 4 -> ratio 0.78125
- 6 -> ratio 0.921875
- 7 -> ratio 0.9921875

For each seed:

1. reproduce the C62 dense condition model with the original 260-step schedule;
2. verify its dense validation score matches the accepted C62 reference;
3. initialize each shared-basis rank from that dense model;
4. freeze every non-factor parameter;
5. tune factors for 260 steps, lr 0.002, batch 32;
6. record validation at step 0 and steps 65/130/195/260.

Primary outputs:

- `summary.minimum_rank_all_final_meet_dense`
- `summary.minimum_rank_all_best_checkpoints_meet_dense`

Interpretation:

- if rank2/4/... recovers all seeds, condition needs more capacity than the initial width/16 rule but the family remains viable;
- if only intermediate checkpoints recover, optimization/checkpoint policy is implicated;
- if even rank7 (< dense bytes) cannot recover, simple shared-basis is inadequate for condition under this bounded schedule.

Language checkpoint/rank diagnosis is deferred to C64 so each C number answers one question.

## 14. Handoff

On a new session:

1. read this ledger;
2. confirm branch/HEAD and protected hashes;
3. continue at the Next ID above;
4. keep one experiment per C number;
5. retry failures under the same number;
6. update this file after every accepted result or Gate decision change.
