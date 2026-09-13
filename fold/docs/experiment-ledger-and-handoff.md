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

Timing comparisons must record the exact commit used. C57 executed at:

`c4c5e96980b5671d3d1fbac20cb23dd467e31b78`

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

Storage savings and fixture parity are established for the current block-codebook candidate, but its direct GPU consumption path does not scale acceptably. Gate C now moves into an alternative module-delta representation comparison rather than continuing unbounded codebook kernel tuning.

### Gate D-I

Not active yet.

## 5. Current lead architecture

FOLD v0.5 lead design:

- shared state-update core;
- small / compressed module-specific processing deltas;
- controller / routing;
- correctable memory later in the roadmap.

The original Gate-C representation under test was:

```text
W_module = W_base + codebook_delta(module) + sparse bounded E
```

Positive property: compact persistent representation.

Current problem: the fine-grained block-codebook delta is expensive to reconstruct/consume directly on GPU.

## 6. Scientific discipline

Do not claim:

- Cxx PASS == Gate C PASS;
- fixture score 1.0 == broad language quality;
- synthetic scale diagnostics prove production LLM behavior;
- FOLD beats Transformers / existing LLMs from these tests.

Current strongest claims are architectural/runtime localization claims only.

## 7. Accepted experiment history

### C33 — sync-clean tiled base tuning

- best tested tiled config still slower than dense;
- Down paired ratio ~1.3788;
- Up ~1.3420.

### C35 — Graph-safe validation boundary

Established structural validation path so finite-value checks do not break CUDA Graph capture.

### C37 — serial CPU-ready request + CUDA Graph

Protected result.

Approximate initial timings:

- dense eager: 1.6531 ms
- Triton eager: 2.0269 ms
- dense Graph: 0.4395 ms
- Triton Graph: 0.4630 ms
- paired Graph ratio ~1.069

CUDA Graph removes a large amount of dispatch overhead but compressed remains slower.

### C38 — regression

- 415 tests PASS
- compileall PASS
- C37 protected hash preserved.

### C41 — clean fresh-process Graph memory

- Dense registered model: 51,200 B
- compact registered model: 44,800 B
- registered reduction: **12.5%**
- model-only allocation: 55,808 B vs 49,664 B
- Graph-ready allocated saving only 6,144 B because tiny-test runtime overhead dominates
- reserved memory identical.

### C42 — repeated request benchmark

- dense Graph median: 0.4406675 ms
- Triton Graph median: 0.4474035 ms
- paired ratio: **1.028879**

### C43 — request phase breakdown

GPU/request path dominates; phase instrumentation is diagnostic only.

### C44 — non-blocking H2D

Common runtime improvement. Queued Triton/dense ~1.0172.

### C45 — GPU-only Graph replay

- dense: 0.289680 ms
- Triton: 0.306309 ms
- paired ratio: **1.05546**

Remaining gap is genuinely GPU compute / Graph path.

### C46 — Up / Down isolation

- Up Triton / dense: **1.03479**
- Down Triton / dense: **1.00629**
- Full Triton / dense: **1.03246**

Remaining full-model slowdown localized overwhelmingly to Up.

### C47 — Up BLOCK_M sweep

For real Up 32->64, `BLOCK_M=64` was the clear best tested mapping.

- BM64/current ~0.97698
- BM64/dense ~1.00942

### C48 — num_warps sweep

At BM64:

- w1 and w4 effectively tied;
- w2 and w8 worse;
- retain w4 as robust reference.

### C49 — sparse correction E isolation

- full-E/no-E only ~1.01-1.03
- no-E/dense still ~2.18-2.38x at bank level.

`E` is not the primary runtime problem.

### C50 — existing row-reuse tiled kernel

Existing 16x16 tiled mapping did not beat row-wise:

- tiled/row-wise ~1.02009

This rejected that mapping, not row reuse as a concept.

### C51 — base / codebook isolation

- base/dense: **1.00944**
- row-wise/dense: **2.11740**
- hybrid/dense: **3.40778**
- hybrid/row-wise: **1.62845**

Shared-base GEMM is fine. The expensive component is codebook delta/decode. Separate cuBLAS-base + Triton-delta hybrid is rejected.

### C52 — decode-to-dense workspace

- workspace: 8,192 B extra resident dense scratch
- decode-workspace/dense: **2.96321**
- decode-workspace/row-wise: **1.36082**
- slower in 80/80 paired samples.

Rejected: worse runtime and additional resident scratch.

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

Codebook delta/decode is dominant.

### C54 — full-M row-tile

One program owns all 64 output channels and reuses decoded weight across rows.

- full-M N16 / row-wise median: **0.82873** (~17.1% faster)
- full-M N32 / row-wise: **0.88681**
- N16 won 57/80 samples
- outputs exact in checked cases.

Conclusion: decode/reconstruction reuse across activation rows is valid. Best C54 mapping: N16.

### C55 — compact address metadata

Full-M/N16 fixed. Compared original codes vs equal-byte precomputed entry index / block offset.

- entry/codes median: **0.98361**
- block-offset/codes: **0.98733**
- metadata bytes unchanged at 3,072 B.

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
- the larger residual is codebook gather/decode/reconstruction;
- the compact extra cost cannot be explained by address arithmetic alone.

### C57 — 32 -> 1024 runtime scale sweep

Accepted run:

- commit: `c4c5e96980b5671d3d1fbac20cb23dd467e31b78`
- widths: 32, 64, 128, 256, 512, 1024
- rows: 1728
- Up-like shape: `K=width`, `M=2*width`
- fixed tile: N16 / M64 / K32, w4
- no-E synthetic runtime diagnostic

#### Storage curve

Serialized estimated payload ratio:

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

Storage therefore scales well and converges to roughly **57.0% serialized** and **68.75% runtime resident** versus two dense module weights.

#### Runtime curve

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

#### C57 interpretation

Do **not** interpret the 12.89x width-1024 number as intrinsic codebook cost. The fixed Triton tile itself becomes badly noncompetitive with vendor dense as width grows: predecoded Triton is already 5.88x dense at width1024.

However, the codebook layer is also not being amortized by scale: adding compact gather/decode on top of the same custom matmul still costs roughly **2.18x** at width1024 and >2.29x at widths256-512.

Therefore both are true:

1. the fixed custom Triton matmul is non-scalable and would need retuning/replacement at large widths;
2. the fine-grained 2x2 codebook gather/decode also fails the pivot condition because its relative cost does not trend toward 1.0.

### C57 pivot decision

**Primary optimization of direct fine-grained block-codebook GPU execution stops here.**

The codebook representation is not deleted. It remains useful as:

- a compact storage/reference representation;
- a baseline for future alternative layouts;
- a possible representation to revisit if a fundamentally different decode strategy appears.

But the main Gate-C execution candidate now pivots to GPU-native module-delta forms.

## 8. Invalid / retry history

- C46 first failure: diagnostic core construction issue.
- C46 second failure: finite-value validation broke CUDA Graph capture.
- C49 first command did not actually start.
- C51 first attempt accidentally ran C49 payload.
- C52 first attempt detected wrong runner hash before Python executed.
- C53 first attempt had PowerShell parser error before experiment start.
- valid retries retain the same C number.

## 9. Current design decision after C57

The desired Gate-C representation should satisfy all three:

1. compact persistent storage;
2. enough module-specific capacity to preserve task quality;
3. GPU-native execution with no fine-grained runtime decode/gather.

The first alternative to test is a **shared-input low-rank basis**:

```text
W_module = W_base + A_module @ B_shared
```

For Up-like `M=2W`, `K=W`, two modules, choose:

```text
rank = W / 16
```

Store shared `[W_base ; B_shared]` as one projection matrix. Runtime:

```text
projected = F.linear(x, [W_base ; B_shared])
base_output = projected[:M]
latent      = projected[M:]
out = addmm(base_output, latent, A_module.T)
```

This gives:

- two GEMM-family operations;
- no codebook decode/gather;
- module-specific state only in small `A_module` matrices;
- exact persistent weight-storage ratio **0.578125** versus two independent dense module weights;
- theoretical matmul FLOP overhead ~9.375% versus one dense module GEMM.

This storage ratio is close to C57 codebook serialized ratio (~0.5703) and better than its current runtime-resident ratio (~0.6875).

## 10. Next experiment

### Next ID: C58

**Matched-storage shared-basis runtime scale sweep.**

Widths:

- 32
- 64
- 128
- 256
- 512
- 1024

Ranks:

- 2
- 4
- 8
- 16
- 32
- 64

Rows: 1728.

Compare exact materialized dense reference against factorized shared-basis execution using vendor PyTorch/cuBLAS operations.

C58 answers runtime/storage feasibility only. It does not answer task quality.

Decision after C58:

- if shared-basis runtime stays near dense while preserving ~57.8% storage, proceed to real-fixture approximation/task-quality work;
- if runtime is also badly noncompetitive, test a different GPU-native delta representation before any task-quality investment;
- Gate C remains NOT PASSED either way.

## 11. Handoff instructions

On a new chat/session:

1. Read this file first.
2. Confirm branch/HEAD and protected hashes.
3. Read only files needed for the next C number.
4. Continue at the Next ID above.
5. Keep one experiment per C number.
6. Retry failures under the same C number.
7. After accepting a result, update this file before moving on.
8. Record exact evidence whenever a Gate decision changes.
