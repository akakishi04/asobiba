# FOLD Experiment Ledger and Handoff

> Project-wide experiment ledger and handoff checkpoint for FOLD. Read this file first when continuing in a new chat/session. Update it after every accepted Cxx experiment, retry decision, or Gate decision change.

## 1. Project / environment identity

- Repository: `akakishi04/asobiba`
- FOLD path: `fold/`
- Active branch: `feat/sft-target-loss`
- Local repository: `M:\asobiba\fold`
- Python: `M:\asobiba\fold\.venv-py31315\Scripts\python.exe`
- Python: 3.13.15
- PyTorch: `2.10.0+cu130`
- CUDA: 13.0
- GPU: NVIDIA GeForce RTX 4070 Ti SUPER
- Visual Studio: VS2022 Community Developer PowerShell 17.14.27

Recent accepted experiment commits:

- C57: `c4c5e96980b5671d3d1fbac20cb23dd467e31b78`
- C58: `27077cdda37ca344da8ea5e6f8e491f613dbe1fa`
- C59: `32f07a9abd5fd566c041134940a5a543bd11cd44`
- C60: `a713fe66101a0f99a38100117340286cd7ed5afe`

C61 benchmark was added at commit:

`9a3d59f189de1d4ef695e4a4514d4efda489f031`

Always confirm current branch HEAD before executing the next experiment.

## 2. Protected artifacts

### C37 protected result

- Path: `M:\asobiba\fold\runs\chatgpt-last-result.json`
- SHA256: `FD4A8DA897BDAEA9D103A252E30212C7FF842D23300D7C837333E146DEE51931`

### Runtime fixture

- Path: `M:\asobiba\fold\runs\fixtures\v05-c-composition-20260921.pt`
- SHA256: `A52F8209703149407580F7E2965B61B78653030EE992AF6D759865736741CA9E`

Diagnostics must not overwrite either artifact.

## 3. Experiment protocol

Experiment/work IDs are `Cxx`.

1. Run exactly one experiment / verification step per C number.
2. Full console output overwrites `M:\asobiba\fold\runs\chatgpt-last.log`.
3. User pastes the full log back into ChatGPT.
4. ChatGPT judges the result.
5. Increment only after successful completion.
6. Failed retries keep the same C number.
7. `status=PASS` means the experiment executed successfully, not that a Gate passed.
8. Wrong runner, wrong experiment ID, parser failure, protected-hash mismatch, etc. are invalid runs, not evidence.
9. Prefer tracked benchmark files over large chat-pasted Python payloads.
10. Long-running benchmarks must print useful progress so current seed/rank/step/round and total completion are visible.

### PC clipboard

```powershell
$log = "M:\asobiba\fold\runs\chatgpt-last.log"
Get-Content -LiteralPath $log -Raw -Encoding UTF8 -ErrorAction Stop |
    Set-Clipboard
```

### Smartphone clipboard (OSC 52 / Termius)

```powershell
$log = "M:\asobiba\fold\runs\chatgpt-last.log"
$text = Get-Content -LiteralPath $log -Raw -Encoding UTF8 -ErrorAction Stop
$b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($text))
[Console]::Write("$([char]27)]52;c;$b64$([char]7)")
```

## 4. FOLD v0.5 gates

### Gate A — reference computation / accounting

Foundation exists. Current work is beyond Gate A.

### Gate B — high-precision core

Foundation exists. Current work is beyond Gate B.

### Gate C — compression components + recurrence stability

Keep a candidate only if either:

- quality is preserved with clearly lower serialized/resident bytes; or
- at equal capacity, task quality beats high-precision/simple-quantization baselines.

Additionally:

- recurrence error must remain bounded/explainable;
- any correction mechanism must remain bounded;
- storage savings that cause unacceptable real runtime overhead do not satisfy Gate C.

**Current Gate C status: NOT PASSED.**

The original fine-grained block-codebook path remains a useful storage/reference baseline but direct GPU execution failed to scale acceptably. Primary Gate-C work has pivoted to a GPU-native shared-basis routed-weight family.

### Gate D-I

Not active yet.

## 5. Current lead architecture / Gate-C candidate family

FOLD v0.5 lead design:

- shared state-update core;
- small / compressed module-specific processing deltas;
- controller / routing;
- correctable memory later in the roadmap.

Original routed-weight representation:

```text
W_module = W_base + codebook_delta(module) + sparse bounded E
```

Current leading alternative:

```text
W_module = W_base + A_module @ B_shared
```

Intent:

- preserve a shared base;
- keep module-specific state small;
- use GEMM-native execution rather than per-weight decode/gather;
- retain storage near the ~57% codebook target;
- optimize the factors for task loss rather than dense-weight reconstruction MSE.

## 6. Scientific discipline

Do not claim:

- Cxx PASS == Gate C PASS;
- fixture score 1.0 == broad language quality;
- synthetic scale diagnostics prove production LLM behavior;
- one task/seed proves generalization;
- FOLD beats Transformers / existing LLMs from these diagnostics.

Keep runtime feasibility, representation capacity, task quality, recurrence stability, multi-seed robustness, and final Gate decisions separate.

## 7. Accepted experiment history

### C33-C48 — localization / runtime foundation

Key results:

- custom tiled paths were initially slower than dense;
- Graph-safe validation boundary established;
- C37 Graph request: dense ~0.4395 ms, compact ~0.4630 ms;
- C38 regression: 415 tests PASS + compileall PASS;
- C41 registered model bytes: Dense 51,200 B vs compact 44,800 B, **12.5% reduction**;
- C42 repeated Graph ratio: **1.028879** compact/dense;
- C45 GPU-only Graph ratio: **1.05546**;
- C46 localized remaining full-model slowdown overwhelmingly to Up;
- C47 found Up `BLOCK_M=64` best tested row-wise mapping;
- C48 retained `num_warps=4` as robust reference.

### C49-C56 — codebook runtime localization

- C49: correction `E` only ~1-3% of remaining cost; not primary bottleneck.
- C50: existing 16x16 row-reuse tiled mapping did not beat tuned row-wise.
- C51: shared-base GEMM was near dense; codebook delta/decode was expensive; split hybrid rejected.
- C52: decode-to-dense workspace slower and added dense scratch; rejected.
- C53: row-wise codebook delta/decode isolated as dominant component.
- C54: full-M/N16 reuse beat row-wise by ~17.1%, validating decode reuse across activation rows.
- C55: equal-byte precomputed address metadata improved little; address arithmetic not the main cost.
- C56: predecoded custom Triton ~1.13x dense, compact ~1.66x predecoded and ~1.91x dense at the real width-32 Up shape.

Conclusion: fine-grained codebook gather/reconstruction is expensive in addition to custom matmul overhead.

### C57 — 32 -> 1024 codebook runtime scale sweep

Accepted run commit:

`c4c5e96980b5671d3d1fbac20cb23dd467e31b78`

Storage scaled well:

- estimated serialized ratio -> ~**57.0%**;
- runtime resident ratio -> ~**68.75%**.

But direct runtime did not scale:

`compact / dense` paired median:

- width32: **1.34919**
- 64: **1.50403**
- 128: **3.27688**
- 256: **8.88606**
- 512: **11.35949**
- 1024: **12.88719**

The fixed custom Triton tile itself also degraded badly, but codebook decode/gather remained ~2.18-2.34x over the same predecoded custom path at large widths.

**Pivot decision:** stop primary optimization of direct fine-grained block-codebook GPU execution. Keep codebook as storage/reference baseline only.

### C58 — matched-storage shared-basis runtime scale sweep

Accepted run commit:

`27077cdda37ca344da8ea5e6f8e491f613dbe1fa`

Representation:

```text
W_module = W_base + A_module @ B_shared
```

Execution:

1. one shared `F.linear(x, [W_base; B_shared])`;
2. one module-specific `addmm(latent, A_module.T)` added to base output.

Rank = width/16. Persistent routed-weight ratio exactly **0.578125** at every width.

`shared_basis / dense` paired median runtime:

- 32: **3.12043**
- 64: **2.94781**
- 128: **4.86182**
- 256: **1.63577**
- 512: **1.29614**
- 1024: **1.19407**

Interpretation:

- small widths suffer from two-GEMM launch/shape inefficiency;
- large widths show the desired scaling;
- width1024 is ~1.19x dense while routed-weight storage remains ~57.8%.

C58 established runtime/storage feasibility only.

### C59 — real-fixture shared-basis post-hoc quality frontier

Accepted run commit:

`32f07a9abd5fd566c041134940a5a543bd11cd44`

Trusted composition fixture dense score: **1.0**.

Post-hoc SVD results:

| rank | routed-weight ratio | score |
|---:|---:|---:|
| 2 | 0.5703125 | 0.050926 |
| 4 | 0.640625 | 0.115741 |
| 8 | 0.781250 | 0.125000 |
| 12 | 0.921875 | 0.166667 |
| 14 | 0.9921875 | 0.300926 |
| 16 | 1.062500 | 0.023148 |
| 24 | 1.343750 | 0.305556 |
| 32 | 1.625000 | **1.000000** |

No sub-dense post-hoc rank preserved dense score. Rank32 reconstructed the routed weights to floating-point noise and recovered score 1.0, validating the fitting path.

Interpretation:

- dense-weight reconstruction is not the correct final objective;
- low-rank post-hoc SVD alone is inadequate;
- the shared-basis family still required task-aware factor optimization before being rejected.

### C60 — task-aware shared-basis recovery

Accepted run commit:

`a713fe66101a0f99a38100117340286cd7ed5afe`

Trusted composition fixture seed: `20260921`.

Only routed shared-basis factors were trainable. Shared core, module norms, biases, gate, and all surrounding model parameters were frozen. Each rank used 300 task-aware steps, batch 64, AdamW lr 0.002.

Results:

| rank | routed-weight ratio | pre score | post score |
|---:|---:|---:|---:|
| 2 | **0.5703125** | 0.050926 | **1.000000** |
| 4 | 0.640625 | 0.115741 | **1.000000** |
| 8 | 0.781250 | 0.125000 | **1.000000** |
| 12 | 0.921875 | 0.166667 | **1.000000** |
| 14 | 0.9921875 | 0.300926 | **1.000000** |

Rank2 recovered from ~5.1% trajectory exact accuracy to the dense score of **1.0** while retaining only **57.03125%** of dense routed-weight bytes.

Rank2 training loss fell from ~0.01240 to ~1.52e-5. All tested ranks recovered exactly on the trusted validation fixture.

Interpretation:

- the poor C59 result was not evidence that low-rank shared-basis lacked functional capacity;
- task-aware optimization can find a rank2 factorization that preserves the trusted composition behavior;
- rank2 now combines the strongest storage result in this family with the C58 large-width runtime scaling behavior;
- this is the **leading Gate-C routed-weight representation candidate**;
- C60 still covers only one trusted composition fixture/seed and does not establish Gate C.

## 8. Invalid / retry history

- C46 first failure: diagnostic core construction issue.
- C46 second failure: finite-value validation broke CUDA Graph capture.
- C49 first command did not actually start.
- C51 first attempt accidentally ran C49 payload.
- C52 first attempt detected wrong runner hash before Python executed.
- C53 first attempt had PowerShell parser error before experiment start.
- valid retries retain the same C number.

## 9. Current design decision after C60

The current strongest candidate is:

```text
W_module = W_base + A_module @ B_shared
```

with the smallest tested rank at the trusted width-32 composition model:

```text
rank = 2
```

Evidence so far:

- routed-weight storage ratio: **0.5703125** on the real width-32 composition model;
- analogous width/16 shared-basis runtime family scales to ~1.19x dense at width1024 while using ~57.8% routed-weight storage;
- post-hoc SVD alone fails, but 300 bounded task-aware factor steps recover dense task score exactly at rank2;
- non-factor parameters do not need to move during recovery.

Remaining immediate risk: **seed robustness**. One successful frozen fixture is not enough to declare the representation reliable.

Do not broaden to language/condition or full production runtime integration until rank2 recovery is shown to reproduce across independently trained composition models.

## 10. Next experiment

### Next ID: C61

**Rank-2 shared-basis multi-seed task-aware recovery.**

Tracked benchmark:

`fold/fold_lm/v05_benchmarks/gate_c_shared_basis_rank2_multiseed.py`

Seeds:

- 20260911
- 20260912
- 20260913

For each seed:

1. train an independent high-precision V5-B composition model from scratch for 300 steps using the Gate-B schedule;
2. initialize rank2 shared-basis factors from that seed's trained dense routed weights;
3. freeze all non-factor parameters;
4. tune only rank2 Up/Down shared-basis factors for 300 task-aware steps;
5. evaluate held-out trajectory exact accuracy before and after recovery;
6. keep routed-weight storage fixed at ratio **0.5703125**.

Progress must print at dense steps 75/150/225/300 and factor steps 75/150/225/300 for each seed.

Decision after C61:

- if every seed recovers its dense validation score, rank2 passes the immediate robustness screen and should proceed to broader task coverage / real factorized runtime integration;
- if recovery is seed-sensitive, characterize the failing seeds before changing the representation or increasing rank;
- C61 alone still cannot establish Gate C.

## 11. Handoff instructions

On a new chat/session:

1. Read this file first.
2. Confirm branch/HEAD and protected hashes.
3. Read only files needed for the next experiment.
4. Continue at the Next ID above.
5. Keep one experiment per C number.
6. Retry failures under the same C number.
7. After accepting a result, update this file before moving on.
8. Record exact evidence whenever a Gate decision changes.
