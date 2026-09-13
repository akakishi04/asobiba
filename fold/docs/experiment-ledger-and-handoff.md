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

C59 benchmark was added after C58; always confirm current branch HEAD before execution.

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
9. Prefer tracked benchmark files in the repository over giant chat-pasted Python payloads.
10. Long-running benchmarks should print progress so the user can see current width/rank/round and total completion.

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

Gate C keeps a candidate only if either:

- quality is preserved with clearly lower serialized/resident bytes; or
- at equal capacity, task quality beats high-precision/simple-quantization baselines.

Additionally:

- recurrence error must remain bounded/explainable;
- correction `E` must remain bounded;
- storage savings that worsen real runtime because of decode overhead do not satisfy Gate C.

**Current Gate C status: NOT PASSED.**

The fine-grained block-codebook candidate demonstrated storage savings and fixture parity, but direct GPU execution does not scale acceptably. Primary Gate-C work has pivoted to GPU-native shared-basis / low-rank module deltas.

### Gate D-I

Not active yet.

## 5. Current lead architecture

FOLD v0.5 lead design:

- shared state-update core;
- small / compressed module-specific processing deltas;
- controller / routing;
- correctable memory later in the roadmap.

Original Gate-C module representation:

```text
W_module = W_base + codebook_delta(module) + sparse bounded E
```

Current alternative under evaluation:

```text
W_module = W_base + A_module @ B_shared
```

Intent:

- preserve a shared base;
- keep module-specific state small;
- use GEMM-native execution rather than per-weight codebook decode/gather;
- retain a storage ratio comparable to the codebook candidate.

## 6. Scientific discipline

Do not claim:

- Cxx PASS == Gate C PASS;
- fixture score 1.0 == broad language quality;
- synthetic scale diagnostics prove production LLM behavior;
- FOLD beats Transformers / existing LLMs from these tests.

Keep runtime feasibility, representation capacity, task quality, recurrence stability, and final Gate decisions separate.

## 7. Accepted experiment history

### C33 — sync-clean tiled base tuning

Best tested custom tiled base path remained slower than dense.

### C35 — Graph-safe validation boundary

Established structural validation so finite-value reductions do not break CUDA Graph capture.

### C37 — serial CPU-ready request + CUDA Graph

Protected result.

Approximate initial timings:

- dense eager: 1.6531 ms
- Triton eager: 2.0269 ms
- dense Graph: 0.4395 ms
- Triton Graph: 0.4630 ms
- paired Graph ratio ~1.069

### C38 — regression

- 415 tests PASS
- compileall PASS
- C37 protected hash preserved.

### C41 — clean fresh-process Graph memory

- Dense registered model: 51,200 B
- compact registered model: 44,800 B
- registered reduction: **12.5%**
- model-only allocation: 55,808 B vs 49,664 B
- Graph-ready saving only 6,144 B because tiny-test runtime overhead dominates.

### C42 — repeated request benchmark

- dense Graph median: 0.4406675 ms
- Triton Graph median: 0.4474035 ms
- paired ratio: **1.028879**

### C44 — non-blocking H2D

Common runtime improvement; queued Triton/dense ~1.0172.

### C45 — GPU-only Graph replay

- dense: 0.289680 ms
- Triton: 0.306309 ms
- paired ratio: **1.05546**

Remaining gap is genuinely in GPU compute / Graph path.

### C46 — Up / Down isolation

- Up Triton / dense: **1.03479**
- Down Triton / dense: **1.00629**
- Full Triton / dense: **1.03246**

Remaining full-model slowdown localized overwhelmingly to Up.

### C47 — Up BLOCK_M sweep

For real Up 32->64, `BLOCK_M=64` was the best tested row-wise mapping.

### C48 — num_warps sweep

At BM64, w1 and w4 were effectively tied; w2 and w8 worse. Retain w4 as robust reference.

### C49 — sparse correction E isolation

- full-E/no-E only ~1.01-1.03
- no-E/dense still ~2.18-2.38x bank-level.

`E` is not the primary runtime problem.

### C50 — existing 16x16 row-reuse tiled kernel

Did not beat tuned row-wise. This rejected that mapping, not row reuse as a concept.

### C51 — base / codebook isolation

- base/dense: **1.00944**
- row-wise/dense: **2.11740**
- hybrid/dense: **3.40778**
- hybrid/row-wise: **1.62845**

Shared-base GEMM is fine. Codebook delta/decode is expensive. Separate cuBLAS-base + Triton-delta hybrid rejected.

### C52 — decode-to-dense workspace

- extra dense scratch: 8,192 B
- decode-workspace/dense: **2.96321**
- decode-workspace/row-wise: **1.36082**
- slower in 80/80 paired samples.

Rejected: slower and larger resident scratch.

### C53 — row-wise component ablation

Real Up 1728x32->64, BM64/W4:

- dense no-E median: 0.0118864 ms
- base-only: 0.0120516 ms
- delta-only: 0.0213311 ms
- full no-E: 0.0182702 ms

Paired:

- base/dense: **1.04502**
- delta/dense: **1.68804**
- full/dense: **1.43449**
- delta/base: **1.71970**

Codebook delta/decode dominates.

### C54 — full-M row-tile

One program owns all 64 output channels and reuses decoded weight across activation rows.

- N16 / row-wise median: **0.82873** (~17.1% faster)
- N32 / row-wise: **0.88681**
- outputs exact in checked cases.

Conclusion: decode/reconstruction reuse across rows is valid. Best C54 mapping: N16.

### C55 — compact address metadata

Full-M/N16 fixed. Equal-byte precomputed address metadata produced only small/noisy gains:

- entry/codes median: **0.98361**
- block-offset/codes: **0.98733**

Address arithmetic is not the main remaining cost.

### C56 — predecoded matmul isolation

Real Up full-M/N16:

- dense median: 0.0116416 ms
- same Triton matmul on predecoded weight: 0.0134215 ms
- compact full-M: 0.0225791 ms

Paired:

- predecoded/dense: **1.13357**
- compact/predecoded: **1.65877**
- compact/dense: **1.91422**

Interpretation:

- custom Triton matmul has ~13% disadvantage at width32;
- larger residual is codebook gather/decode/reconstruction.

### C57 — 32 -> 1024 codebook runtime scale sweep

Accepted run commit:

`c4c5e96980b5671d3d1fbac20cb23dd467e31b78`

Widths: 32, 64, 128, 256, 512, 1024. Rows: 1728. Up-like shape `K=W`, `M=2W`. Fixed tile N16/M64/K32, w4. No-E runtime diagnostic.

#### C57 storage curve

Estimated serialized payload ratio:

- 32: 0.59375
- 64: 0.57617
- 128: 0.57178
- 256: 0.57068
- 512: 0.57040
- 1024: 0.57034

Compact runtime resident ratio:

- 32: 0.71094
- 64: 0.69336
- 128: 0.68896
- 256: 0.68787
- 512: 0.68759
- 1024: 0.68752

Storage scales well, converging near **57.0% serialized** and **68.75% resident** versus two independent dense module weights.

#### C57 runtime curve

`compact / dense` paired median:

- 32: **1.34919**
- 64: **1.50403**
- 128: **3.27688**
- 256: **8.88606**
- 512: **11.35949**
- 1024: **12.88719**

`predecoded Triton / dense` paired median:

- 32: 1.10433
- 64: 1.16912
- 128: 1.93274
- 256: 3.85293
- 512: 4.82387
- 1024: 5.88088

`compact / predecoded Triton` paired median:

- 32: 1.22805
- 64: 1.26849
- 128: 1.81908
- 256: 2.29477
- 512: 2.34078
- 1024: 2.18005

Interpretation:

- the fixed custom Triton tile itself becomes noncompetitive at large width;
- codebook gather/decode also fails to amortize, remaining ~2.18-2.34x over the same predecoded Triton execution at large widths.

**Pivot decision:** stop primary optimization of direct fine-grained block-codebook GPU execution. Keep it as storage/reference baseline only.

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

Widths: 32, 64, 128, 256, 512, 1024. Rows: 1728. Rank = width/16.

Persistent module-weight representation ratio is exactly **0.578125** at every width. This is very close to C57 codebook serialized ratio (~0.5703 at scale) and better than current codebook runtime-resident ratio (~0.6875).

Theoretical matmul FLOP overhead versus one dense module GEMM: **9.375%**.

`shared_basis / dense` paired median runtime:

- 32: **3.12043**
- 64: **2.94781**
- 128: **4.86182**
- 256: **1.63577**
- 512: **1.29614**
- 1024: **1.19407**

Interpretation:

- small widths are dominated by two-GEMM launch/shape inefficiency;
- large widths show the intended scaling behavior;
- by width512 the ratio is ~1.30x, and by width1024 ~1.19x, while persistent weight storage stays ~57.8%;
- unlike direct codebook execution, the shared-basis runtime ratio improves sharply with scale once GEMMs are large enough;
- C58 establishes runtime/storage feasibility only. Random synthetic factors do **not** establish approximation capacity or task quality.

C58 is therefore a **promising alternative execution/storage family**, not yet a Gate-C candidate.

## 8. Invalid / retry history

- C46 first failure: diagnostic core construction issue.
- C46 second failure: finite-value validation broke CUDA Graph capture.
- C49 first command did not actually start.
- C51 first attempt accidentally ran C49 payload.
- C52 first attempt detected wrong runner hash before Python executed.
- C53 first attempt had PowerShell parser error before experiment start.
- valid retries retain the same C number.

## 9. Current design decision after C58

The desired Gate-C representation should satisfy all three:

1. compact persistent storage;
2. enough module-specific capacity to preserve task quality;
3. GPU-native execution with no fine-grained runtime decode/gather.

The shared-basis family now passes the **runtime/storage feasibility** screen strongly enough to justify a real-fixture capacity test.

Do not optimize shared-basis runtime further yet. The next risk is representational capacity.

At the current trusted width-32 composition fixture:

- Up role: 32 -> 64;
- Down role: 64 -> 32;
- modules: 2.

For a common rank `r` applied independently to Up and Down shared-basis representations, combined Up+Down routed-weight storage ratio is:

```text
ratio = 0.5 + 0.03515625 * r
```

Therefore:

- rank 2 -> **0.5703125** (matched to the ~57% storage target);
- rank 4 -> 0.640625;
- rank 8 -> 0.78125;
- rank 12 -> 0.921875;
- rank 14 -> 0.9921875 (largest tested rank still below dense routed-weight bytes);
- rank >=16 exceeds dense routed-weight storage, but is diagnostically useful to locate capacity recovery;
- rank 32 can represent both two-module Up/Down differences exactly in principle and serves as a sanity check.

## 10. Next experiment

### Next ID: C59

**Real-fixture shared-basis representation / quality frontier.**

Tracked benchmark:

`fold/fold_lm/v05_benchmarks/gate_c_shared_basis_quality_frontier.py`

Use the trusted composition runtime fixture. No training in C59.

For each rank:

- 2
- 4
- 8
- 12
- 14
- 16
- 24
- 32

fit each role independently with:

```text
W_base = mean(module weights)
centered residuals = W_module - W_base
B_shared = leading right singular vectors of stacked residuals
A_module = projection coefficients onto B_shared
```

Then materialize the reconstructed routed weights into a copy of the trained dense model and evaluate the trusted validation task.

C59 records:

- task score versus dense;
- Up / Down reconstruction MSE, RMSE, max error;
- exact routed-weight storage bytes and ratio;
- smallest sub-dense rank that preserves dense task score, if one exists;
- rank32 exact-reconstruction / score sanity check.

C59 answers representation capacity and task-quality feasibility only. It does not measure factorized runtime; C58 already covers runtime/storage feasibility on the synthetic scale sweep.

Decision after C59:

- if rank2 preserves task quality, shared-basis becomes the clear primary Gate-C candidate and should next be integrated into the real runtime/full-model path;
- if a higher but still sub-dense rank preserves quality, evaluate its large-width runtime/storage curve before integration;
- if no sub-dense rank preserves quality, do not immediately reject shared-basis: next test task-aware joint training/tuning before abandoning the family;
- rank32 must recover the dense reference closely or C59 is invalid.

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
