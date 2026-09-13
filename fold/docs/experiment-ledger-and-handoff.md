# FOLD Experiment Ledger and Handoff

> Project-wide experiment ledger and handoff checkpoint for FOLD. Update this after every accepted Cxx result, invalid retry that matters, gate decision change, or change to the next experiment.

## 1. Purpose

This file is the minimum state needed to resume FOLD in a new ChatGPT/Codex session without reconstructing the full conversation.

It records:

- repository/environment identity;
- gate progression;
- Cxx execution protocol;
- accepted experiment results and invalid retries;
- protected artifacts and hashes;
- current scientific conclusions;
- explicit stop/pivot conditions;
- next experiment.

This is project-wide and continues through Gate A-I and later architecture work.

---

## 2. Repository / environment

- Repository: `akakishi04/asobiba`
- FOLD path: `fold/`
- Branch: `feat/sft-target-loss`
- HEAD through accepted C56: `69e43996b567f7e0a9ce0998749f19853a76231f`
- Local repo: `M:\asobiba\fold`
- Python: `M:\asobiba\fold\.venv-py31315\Scripts\python.exe`
- Python: 3.13.15
- PyTorch: `2.10.0+cu130`
- CUDA: 13.0
- GPU: NVIDIA GeForce RTX 4070 Ti SUPER
- VS2022 Community Developer PowerShell: 17.14.27

If hardware, driver/toolchain, branch, or timing-critical runtime changes, record it before comparing latency with older runs.

---

## 3. Protected artifacts

### C37 protected result

- `M:\asobiba\fold\runs\chatgpt-last-result.json`
- SHA256: `FD4A8DA897BDAEA9D103A252E30212C7FF842D23300D7C837333E146DEE51931`

### Runtime fixture

- `M:\asobiba\fold\runs\fixtures\v05-c-composition-20260921.pt`
- SHA256: `A52F8209703149407580F7E2965B61B78653030EE992AF6D759865736741CA9E`

Diagnostics must not overwrite these.

---

## 4. Cxx execution protocol

1. Exactly one experiment / verification step per C number.
2. Full output overwrites `M:\asobiba\fold\runs\chatgpt-last.log`.
3. User copies the whole log and pastes it back to ChatGPT.
4. ChatGPT judges the result.
5. Increment C number only after successful completion of that work item.
6. Failed retries keep the same C number.
7. Script `status=PASS` means the experiment executed successfully; it does not mean a Gate passed.
8. Wrong runner, parser failure, wrong experiment ID, missing summary, protected-hash mismatch, or similar invalid execution does not count.
9. Experiment source should live in the repository when practical; avoid transporting large Python payloads through chat.

### PC clipboard

```powershell
$log = "M:\asobiba\fold\runs\chatgpt-last.log"
Get-Content -LiteralPath $log -Raw -Encoding UTF8 -ErrorAction Stop |
    Set-Clipboard
```

### Smartphone clipboard (OSC 52)

```powershell
$log = "M:\asobiba\fold\runs\chatgpt-last.log"
$text = Get-Content -LiteralPath $log -Raw -Encoding UTF8 -ErrorAction Stop
$b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($text))
[Console]::Write("$([char]27)]52;c;$b64$([char]7)")
```

---

## 5. FOLD v0.5 gates

### Gate A — reference computation / accounting

Foundation established. Current work is beyond Gate A.

### Gate B — high-precision core

Foundation established. Current work is beyond Gate B.

### Gate C — compression components + recurrence stability

Keep candidates satisfying either:

- same quality with clearly lower serialized/resident bytes; or
- same capacity with higher task quality than high-precision/simple-quantization baseline.

Also require:

- recurrence error remains bounded/explainable;
- correction `E` remains bounded;
- lower storage must not simply be bought with worse real runtime.

**Current status: NOT PASSED.**

Storage advantage and checked fixture parity exist, but compact runtime decode/gather overhead remains unresolved.

### Gate D — adaptive compute / routing

Not active yet.

### Gate E — unknown / information acquisition

Not active yet.

### Gate F — FOLD-R / memory integration

Not active yet.

### Gate G — variable-length I/O

Not active yet.

### Gate H — vision

Not active yet.

### Gate I — scaling / practical comparison

Not active yet as a formal gate, but C57 will perform a bounded runtime scale sweep because scale behavior is now necessary to decide whether the Gate-C codebook representation is worth further optimization.

---

## 6. Current Gate-C representation

Lead architecture:

- shared state-update core;
- compressed processing modules;
- controller;
- correctable memory later.

Current compressed module representation:

```text
W_module = W_base + codebook_delta(module_codes) + bounded sparse E
```

Current real fixture Up structure:

- activation `[216, 8, 32]`;
- flattened rows 1728;
- input width 32;
- output width 64;
- block rows/cols: 2 x 2;
- grid: 32 x 16;
- codebook count: 3;
- entries/codebook: 8;
- modules: 2.

Important discipline:

- fixture score 1.0 is not broad language-quality proof;
- Cxx PASS is not Gate C PASS;
- no claim that FOLD beats Transformers/LLMs is established by these diagnostics.

---

## 7. Strongest current storage / quality / speed facts

### Storage — C41

- Dense registered model storage: 51,200 B
- Compact registered model storage: 44,800 B
- reduction: **12.5%**
- model-only CUDA allocated: 55,808 B vs 49,664 B
- Graph-ready allocated: 9,641,984 B vs 9,635,840 B
- Graph-ready reserved: identical at 27,262,976 B

Interpretation: model payload is smaller, while tiny-test total VRAM is dominated by runtime/framework/Graph allocations.

### Quality on current fixture

Checked compressed outputs remain equal/near-equal to reference and current synthetic task score remains 1.0. This is fixture parity only.

### Full-model/request speed

The optimized request/Graph path is close to dense, but compact GPU compute is still slower. Later experiments localized the remaining issue primarily to the Up codebook delta/decode execution.

---

## 8. Experiment ledger — accepted/relevant results

### C33 — sync-clean tiled base tuning

- best tested `tf32_32x64x32`
- Down ratio ~1.3788
- Up ratio ~1.3420
- Triton slower.

### C35 — full-model validation boundary

Established Graph-safe structural validation boundary.

### C37 — serial CPU-ready request + CUDA Graph

Protected result.

- dense eager ~1.6531 ms
- compact eager ~2.0269 ms
- dense Graph ~0.4395 ms
- compact Graph ~0.4630 ms
- Graph compact/dense ~1.069

### C38 — regression

- 415 tests PASS
- compileall PASS
- C37 hash preserved.

### C40

Allocator diagnostic superseded for clean memory conclusions by C41.

### C41 — reference-isolated memory

- registered model storage 51,200 B -> 44,800 B
- **12.5% reduction**
- Graph allocated saving only 6,144 B in tiny fixture.

### C42 — repeated request benchmark

- dense eager median 1.75512 ms
- compact eager 2.09557 ms
- dense Graph 0.440668 ms
- compact Graph 0.447404 ms
- paired Graph ratio **1.028879**

### C43 — request phase breakdown

End-to-end request time is strongly diluted by H2D/Graph/D2H/common overhead; use this diagnostically only.

### C44 — non-blocking H2D

- queued compact/dense ~1.0172
- common runtime path improved substantially.

### C45 — GPU-only CUDA Graph replay

- dense 0.289680 ms
- compact 0.306309 ms
- compact/dense **1.05546**

The remaining gap is genuinely GPU compute/Graph-side.

### C46 — Up/Down isolation

- Up/dense **1.03479**
- Down/dense **1.00629**
- Full/dense **1.03246**

Remaining slowdown is overwhelmingly Up-side.

### C47 — Up BLOCK_M sweep

Real Up 32 -> 64.

- BM64/current **0.97698**
- BM64/dense **1.00942**

Retain BM64 as best row-wise geometry found.

### C48 — warps sweep

At BM64:

- w1/dense 1.01096
- w4/dense **1.00696**
- w2/w8 clearly worse

Retain w4 as robust reference.

### C49 — correction E isolation

- full-E/no-E ~1.013-1.03
- no-E/dense materialized ~2.18-2.38x bank-level

`E` is not the main runtime problem.

### C50 — existing row-reuse tiled path

- tiled/rowwise **1.02009**
- tiled/dense **2.09932**

Existing 16x16 tiled mapping is not an improvement.

### C51 — base/codebook isolation

- base/dense **1.00944**
- rowwise/dense **2.11740**
- hybrid/dense **3.40778**
- hybrid/rowwise **1.62845**

Shared base GEMM is basically fine. Separate cuBLAS-base + Triton-delta hybrid is rejected.

### C52 — decode-to-dense workspace

- workspace: 8,192 B dense scratch
- rowwise/dense **2.17013**
- decode-workspace/dense **2.96321**
- decode-workspace/rowwise **1.36082**
- decode-only/dense **0.98747**

Rejected: slower and consumes extra resident scratch larger than the current model-storage saving.

### C53 — row-wise component ablation

Real Up 1728 x 32 -> 64, BM64/W4.

Device medians:

- dense 0.0118864 ms
- rowwise base-only 0.0120516 ms
- rowwise delta-only 0.0213311 ms
- rowwise full 0.0182702 ms

Paired:

- base/dense **1.04502**
- delta/dense **1.68804**
- full/dense **1.43449**
- delta/base **1.71970**

Conclusion: codebook delta/decode is the dominant expensive component. Base computation is near dense.

### C54 — full-M row-tile mapping

Accepted output:
`M:\asobiba\fold\runs\c54-fullm-row-tile-d0905230c4d94bbcb6154139299240ce`

Compared rowwise BM64 with full-M kernels that decode the entire 64x32 Up weight once and reuse it across activation rows.

Paired medians:

- fullM N16 / rowwise: **0.82873** (~17.1% faster)
- fullM N32 / rowwise: **0.88681**
- fullM N16 / dense: **1.98064**
- fullM N32 / dense: **2.04591**

Conclusion:

- decode reuse across rows is real and useful;
- N16 is the best tested full-M mapping;
- this does not solve the full dense gap.

### C55 — compact address metadata

Accepted output:
`M:\asobiba\fold\runs\c55-compact-offset-146f0044ade74363a1468ceee8a2f088`

Full-M/N16 fixed. Original codes vs equal-byte uint8 precomputed entry index / block offset.

- entry/codes median **0.98361**
- block-offset/codes median **0.98733**
- metadata stays 3,072 B in every variant
- block-offset/dense median **1.89537**

Conclusion:

- address/index arithmetic is not the main remaining cost;
- precomputing offsets yields only marginal/noisy improvement;
- remaining issue is deeper in gather/reconstruction and/or custom matmul execution.

### C56 — predecoded matmul isolation

Accepted output:
`M:\asobiba\fold\runs\c56-predecoded-matmul-706dc3b70e204bc29ac90092e29f10ed`

Same full-M/N16 shape, comparing:

- dense `F.linear`;
- diagnostic predecoded dense weight through the same Triton full-M matmul mapping;
- compact full-M/N16 decode+matmul.

Device medians:

- dense: **0.0116416 ms**
- predecoded Triton: **0.0134215 ms**
- compact full-M/N16: **0.0225791 ms**

Paired medians:

- predecoded/dense: **1.13357**
- compact/predecoded: **1.65877**
- compact/dense: **1.91422**

All compact/predecoded samples: compact slower 80/80.

Conclusion:

1. The custom full-M Triton matmul itself carries a real but much smaller penalty (~13% median vs dense/cuBLAS).
2. The dominant remaining cost is the compact codebook gather/decode/reconstruction path (~66% over the same predecoded Triton mapping).
3. The current problem is structural, not mostly index arithmetic.

---

## 9. Invalid / retry history

Do not treat these as scientific evidence:

- C46 first failure: diagnostic core missing `initial_working_state`.
- C46 second failure: finite-value validation broke CUDA Graph capture.
- C49 first command: PowerShell block did not actually start.
- C51 first attempt accidentally ran C49 payload.
- C52 first attempt detected wrong runner hash before Python executed.
- C53 first attempt had PowerShell parser error before experiment start.
- C53 retry was valid.

Retries do not consume new C numbers.

---

## 10. Scientific conclusion after C56

### Established positives

- compact registered model storage is 12.5% lower in the current small fixture;
- checked fixture quality is preserved;
- Down is essentially near dense;
- full-model Graph/request path is already close to dense;
- block-aware/full-M row reuse is a valid optimization direction.

### Remaining blocker

The current block-codebook representation is expensive to consume directly on GPU.

The measured hierarchy is now:

```text
shared base GEMM                      ~ near dense
custom predecoded full-M Triton GEMM  ~ 1.13x dense
compact decode/gather + same matmul    ~ 1.66x predecoded
compact total                          ~ 1.91x dense (bank-level Up)
```

The main remaining cost is therefore **codebook gather / delta reconstruction**, not sparse correction E, index arithmetic, shared base GEMM, or CPU submission.

---

## 11. Design interpretation / stop conditions

The codebook representation has succeeded as a storage representation but is not yet proven as a GPU-native execution representation.

Do not continue unbounded Triton micro-tuning.

The remaining bounded questions are:

1. Does the compact/dense runtime ratio improve materially as width/model scale grows, allowing decode cost to amortize?
2. If it does not, pivot the module-delta representation toward GPU-native forms such as low-rank/shared-basis deltas.

### Pivot condition

After a width/scale sweep using the best current compact execution family:

- if compact/dense ratio trends clearly toward 1.0 as width grows, keep codebook as a viable candidate and optimize the scalable block mapping;
- if the ratio stays roughly flat well above 1.0 or worsens, stop primary optimization of this direct codebook execution path and begin low-rank/shared-basis comparison;
- do not claim Gate C from a microbenchmark alone.

### Candidate alternative representations after pivot

Examples to evaluate without committing yet:

```text
W_module = W_base + A_module @ B_module
```

or a shared-basis form:

```text
W_module = W_base + sum_i alpha[module,i] * B_i
```

These trade some compression structure for GPU-native GEMM execution and no runtime codebook decode.

---

## 12. Scale warning

Current absolute ratios come from a very small real fixture (width 32, Up 32 -> 64, only two modules). They must not be extrapolated directly to LLM scale.

Scaling can change:

- cuBLAS/Tensor Core efficiency;
- codebook decode amortization;
- row reuse;
- register pressure;
- best tile geometry;
- shared-storage amortization across modules;
- relative framework overhead.

Therefore the next experiment measures the **curve**, not just another point at width 32.

---

## 13. Next experiment

### Next ID: C57

**Runtime scale sweep for the current best compact family.**

Goal:

Determine whether direct block-codebook execution becomes relatively better, stays flat, or gets worse as the Linear width grows.

Minimum sweep:

- widths: 32, 64, 128, 256;
- Up-like shape: `K = width`, `M = 2 * width`;
- keep a fixed rows workload appropriate for comparable utilization;
- preserve 2x2 blocks, Q=3, entries=8, no-E for runtime isolation;
- compare vendor dense baseline, predecoded Triton execution, and direct compact execution;
- report bytes and runtime ratio at every width;
- do not modify production runtime;
- do not claim quality from synthetic scale fixtures.

Decision after C57:

- improving compact/dense trend -> continue scalable codebook execution research;
- flat/worsening trend -> pivot to low-rank/shared-basis module-delta experiments.

---

## 14. Handoff instructions

On a new chat/session:

1. Read this file first.
2. Confirm branch/HEAD and protected hashes.
3. Read only files needed for the next experiment.
4. Continue at the Next ID above.
5. Keep one experiment per C number.
6. Retry failures under the same C number.
7. After accepting a result, update this file before moving on.
8. Record exact evidence whenever a Gate decision changes.
