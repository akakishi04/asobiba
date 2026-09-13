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

C60 benchmark added after C59. Confirm current branch HEAD before execution.

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

Keep a candidate only if either:

- quality is preserved with clearly lower serialized/resident bytes; or
- at equal capacity, task quality beats high-precision/simple-quantization baselines.

Additionally:

- recurrence error must remain bounded/explainable;
- correction `E` must remain bounded;
- storage savings that worsen real runtime because of decode overhead do not satisfy Gate C.

**Current Gate C status: NOT PASSED.**

The fine-grained block-codebook candidate demonstrated storage savings and fixture parity but direct GPU execution did not scale acceptably. Primary Gate-C work pivoted to GPU-native shared-basis / low-rank module deltas.

### Gate D-I

Not active yet.

## 5. Current lead architecture / candidate family

FOLD v0.5 lead design:

- shared state-update core;
- small / compressed module-specific processing deltas;
- controller / routing;
- correctable memory later in the roadmap.

Original Gate-C routed-weight representation:

```text
W_module = W_base + codebook_delta(module) + sparse bounded E
```

Current alternative under evaluation:

```text
W_module = W_base + A_module @ B_shared
```

Intent:

- preserve shared structure;
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

### C33-C48 — localization / runtime foundation

Key results:

- custom tiled base paths were initially slower than dense;
- Graph-safe validation boundary established;
- C37 Graph request: dense ~0.4395 ms, compact ~0.4630 ms;
- C38 regression: 415 tests PASS + compileall PASS;
- C41 registered model bytes: Dense 51,200 B vs compact 44,800 B, **12.5% reduction**;
- C42 repeated Graph ratio: **1.028879** compact/dense;
- C45 GPU-only Graph ratio: **1.05546**;
- C46 localized remaining full-model slowdown overwhelmingly to Up;
- C47 found Up `BLOCK_M=64` best tested row-wise mapping;
- C48 found warps 1 and 4 effectively tied, with w4 retained as robust reference.

### C49 — sparse correction E isolation

- full-E/no-E only ~1.01-1.03;
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

Accepted run commit: `c4c5e96980b5671d3d1fbac20cb23dd467e31b78`

Widths: 32, 64, 128, 256, 512, 1024. Rows: 1728. Up-like shape `K=W`, `M=2W`. Fixed tile N16/M64/K32, w4. No-E runtime diagnostic.

Estimated serialized payload ratio converges near **57.0%**. Runtime resident ratio converges near **68.75%**.

`compact / dense` paired median:

- 32: **1.34919**
- 64: **1.50403**
- 128: **3.27688**
- 256: **8.88606**
- 512: **11.35949**
- 1024: **12.88719**

`predecoded Triton / dense`:

- 32: 1.10433
- 64: 1.16912
- 128: 1.93274
- 256: 3.85293
- 512: 4.82387
- 1024: 5.88088

`compact / predecoded Triton`:

- 32: 1.22805
- 64: 1.26849
- 128: 1.81908
- 256: 2.29477
- 512: 2.34078
- 1024: 2.18005

Interpretation:

- fixed custom Triton tile becomes noncompetitive at large width;
- codebook gather/decode also fails to amortize, remaining ~2.18-2.34x over the same predecoded execution at large widths.

**Pivot decision:** stop primary optimization of direct fine-grained block-codebook GPU execution. Keep it as storage/reference baseline only.

### C58 — matched-storage shared-basis runtime scale sweep

Accepted run commit: `27077cdda37ca344da8ea5e6f8e491f613dbe1fa`

Representation:

```text
W_module = W_base + A_module @ B_shared
```

Execution:

1. one shared `F.linear(x, [W_base; B_shared])`;
2. one module-specific `addmm(latent, A_module.T)` added to base output.

Rank = width/16. Persistent routed-weight representation ratio exactly **0.578125** at every width. Theoretical matmul FLOP overhead ~9.375%.

`shared_basis / dense` paired median:

- 32: **3.12043**
- 64: **2.94781**
- 128: **4.86182**
- 256: **1.63577**
- 512: **1.29614**
- 1024: **1.19407**

Interpretation:

- small widths are dominated by two-GEMM launch/shape inefficiency;
- large widths show the intended scaling behavior;
- by width512 ratio ~1.30x and width1024 ~1.19x while storage stays ~57.8%;
- unlike direct codebook execution, this family improves sharply with scale.

C58 establishes runtime/storage feasibility only.

### C59 — real-fixture shared-basis post-hoc quality frontier

Accepted run commit: `32f07a9abd5fd566c041134940a5a543bd11cd44`

Trusted composition fixture:

- width: 32
- hidden: 64
- modules: 2
- dense score: **1.0** trajectory exact accuracy.

C59 fit each role post-hoc using mean shared base + truncated SVD of stacked module residuals. No training.

Results:

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

No sub-dense post-hoc rank preserved dense score. Rank32 reconstructed Up/Down to floating-point noise and recovered score 1.0, validating the fitting/evaluation path.

Important interpretation:

- post-hoc low-rank approximation is **not sufficient** for this trained composition fixture;
- reconstruction error decreases monotonically but task score is non-monotonic, so weight MSE alone is not a reliable task-quality objective;
- this does **not yet reject the shared-basis family**, because C59 never optimized the factors for task loss;
- next bounded question is whether task-aware factor tuning can recover functionality at fixed sub-dense ranks.

## 8. Invalid / retry history

- C46 first failure: diagnostic core construction issue.
- C46 second failure: finite-value validation broke CUDA Graph capture.
- C49 first command did not actually start.
- C51 first attempt accidentally ran C49 payload.
- C52 first attempt detected wrong runner hash before Python executed.
- C53 first attempt had PowerShell parser error before experiment start.
- valid retries retain the same C number.

## 9. Current design decision after C59

Shared-basis currently has opposite strengths/weaknesses to the original direct codebook path:

- runtime/storage scaling: promising;
- post-hoc approximation capacity at low rank: poor on the trusted composition fixture.

Do not abandon the family yet. C10-era codebook work already demonstrated that task-aware optimization can recover quality that reconstruction-oriented fitting misses. The analogous test is required here.

C60 keeps the representation and storage fixed and changes only the optimization objective.

For each sub-dense rank `r` in `2,4,8,12,14`:

- initialize `W_base`, `B_shared`, `A_module` from the same C59 SVD fit;
- freeze shared core, module norms, biases, gate, and surrounding task model;
- tune only Up/Down shared-basis factors using composition task MSE;
- 300 steps, batch size 64, AdamW lr 0.002, no weight decay;
- report pre/post trajectory exact accuracy and training loss;
- storage ratio remains fixed by rank and cannot grow.

Decision after C60:

- if rank2 recovers dense score, it becomes the leading Gate-C representation candidate;
- if a higher sub-dense rank recovers dense score, benchmark that rank's scale/runtime curve before integration;
- if no sub-dense rank recovers dense score after bounded task-aware tuning, shared-basis in this simple form is not adequate and the next representation should add structured capacity rather than more post-hoc SVD tuning.

## 10. Next experiment

### Next ID: C60

**Task-aware shared-basis recovery at fixed sub-dense ranks.**

Tracked benchmark:

`fold/fold_lm/v05_benchmarks/gate_c_shared_basis_task_aware_recovery.py`

Ranks:

- 2
- 4
- 8
- 12
- 14

Training:

- trusted composition fixture;
- SVD initialization from the learned dense routed weights;
- 300 steps per rank;
- batch size 64;
- AdamW lr 0.002;
- only factor parameters trainable;
- all non-factor parameters frozen;
- progress output at steps 75/150/225/300.

C60 is a quality/capacity diagnostic. C58 already established the large-width runtime/storage feasibility of the family.

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
