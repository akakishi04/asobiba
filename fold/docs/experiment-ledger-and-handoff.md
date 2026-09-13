# FOLD Experiment Ledger and Handoff

> This file is the project-wide experiment ledger and handoff checkpoint for FOLD.
> It is intentionally broader than any single gate. Update it whenever a numbered experiment (Cxx) is accepted, rejected, retried, or changes the next action.

## 1. Purpose

This file exists so a new ChatGPT/Codex session can resume FOLD without reconstructing the entire conversation history.

It records:

- current repository / environment identity;
- FOLD v0.5 gate progression and current active gate;
- experiment numbering and execution protocol;
- accepted Cxx results and invalid/retried runs;
- protected artifacts / hashes that must not silently change;
- current scientific conclusions;
- next experiment to run;
- claims that are explicitly *not* established yet.

This is a project-wide ledger. It must continue through Gate D, E, F, G, H, I and any later architecture work, not only Gate C.

---

## 2. Current repository identity

- Repository: `akakishi04/asobiba`
- FOLD path: `fold/`
- Active branch: `feat/sft-target-loss`
- Verified HEAD used by C33-C53: `377c8507216ed4b15319588303d0980d7888c5c9`
- Local repository: `M:\asobiba\fold`
- Python: `M:\asobiba\fold\.venv-py31315\Scripts\python.exe`
- Python: 3.13.15
- PyTorch: `2.10.0+cu130`
- CUDA: 13.0
- GPU: NVIDIA GeForce RTX 4070 Ti SUPER
- Visual Studio: VS2022 Community Developer PowerShell 17.14.27

If any of the above changes, record the new identity before comparing timings with the older runs.

---

## 3. Protected experiment artifacts

### C37 protected result

- Path: `M:\asobiba\fold\runs\chatgpt-last-result.json`
- SHA256: `FD4A8DA897BDAEA9D103A252E30212C7FF842D23300D7C837333E146DEE51931`

### Runtime fixture

- Path: `M:\asobiba\fold\runs\fixtures\v05-c-composition-20260921.pt`
- SHA256: `a52f8209703149407580f7e2965b61b78653030ee992af6d759865736741ca9e`

Do not overwrite these during diagnostics. New experiments should verify preservation when relevant.

---

## 4. Experiment numbering protocol

The experiment/work ID is `Cxx`.

Rules:

1. Run exactly one experiment / verification step per numbered operation.
2. Save full console output by overwriting:
   `M:\asobiba\fold\runs\chatgpt-last.log`
3. User copies the full log to clipboard and pastes it back into ChatGPT.
4. ChatGPT judges the result.
5. Increment the C number only after that work item is successfully completed.
6. Failed retries of the same work item keep the same C number.
7. A script-level `status=PASS` does **not** imply a Gate passed unless the gate decision explicitly says so.
8. Invalid runs (wrong runner, parser failure, wrong experiment ID, protected hash mismatch, etc.) do not count as completed experiments.

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
$b64 = [Convert]::ToBase64String(
    [Text.Encoding]::UTF8.GetBytes($text)
)

[Console]::Write("$([char]27)]52;c;$b64$([char]7)")
```

---

## 5. FOLD v0.5 development gates

### Gate A — reference computation / accounting

Goal:

- reproducible mathematical reference implementation;
- byte accounting;
- causal/provenance invariants;
- direct decode vs materialized consistency.

Status: prior foundation exists; current active work is beyond Gate A.

### Gate B — high-precision core

Goal:

- prove the uncompressed shared-core architecture can learn before compression is introduced.

Status: prior foundation exists; current active work is beyond Gate B.

### Gate C — compression components + recurrence stability

Goal:

Keep candidates satisfying either:

- same quality with clearly lower serialized/resident bytes; or
- same capacity with higher task quality than high-precision/simple-quantization baseline.

Additionally:

- recurrence errors must remain bounded / explainable;
- correction `E` must remain bounded;
- if lower storage causes decode overhead that worsens real wall-clock/runtime, Gate C is unmet.

**Current status: NOT PASSED.**

Storage advantage exists, fixture quality is preserved, but the compact runtime still has unresolved decode/runtime overhead.

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

Not active yet.

---

## 6. Current V5-C architecture facts

Lead design:

- shared state-update core;
- compressed processing modules;
- controller;
- correctable memory later in the roadmap.

Compression candidate:

- shared `W_base`;
- multiple codebooks;
- discrete per-module codes;
- bounded sparse correction `E`;
- compact persistent representation;
- no full dense module weight materialization during the main compact forward path.

Current real fixture scope used by many C37+ diagnostics:

- width: 32
- validation batch: 216
- Up shape (flattened diagnostic): `1728 x 32 -> 64`
- modules: 2

Important discipline:

- synthetic fixture score `1.0` is not proof of language quality;
- Cxx PASS is not Gate C PASS;
- no claim that FOLD beats Transformers / LLMs is established by these diagnostics.

---

## 7. Current strongest storage / quality / speed result

### Storage

C41 reference-isolated memory measurement:

- Dense registered model storage: 51,200 B
- Triton compact registered storage: 44,800 B
- reduction: **12.5%**

Model-only CUDA allocated:

- Dense: 55,808 B
- Triton: 49,664 B

Graph-ready allocated:

- Dense: 9,641,984 B
- Triton: 9,635,840 B

Graph-ready reserved:

- both: 27,262,976 B

Interpretation:

- the model payload itself is smaller;
- total tiny-test CUDA Graph VRAM barely changes because framework/graph/runtime allocations dominate.

### Quality on current fixture

For the full compressed candidate, checked outputs remain equal / near-equal to reference and task score remains 1.0 in the current synthetic fixture.

This is fixture parity, not broad language-quality evidence.

### Speed

The original optimized Graph request path was close to dense but still slower. Subsequent diagnostics localized most of the remaining gap to the compressed Up Linear execution path and then to codebook-delta/decode work rather than shared-base GEMM.

---

## 8. Experiment ledger — accepted / relevant Cxx results

### C33 — sync-clean tiled base tuning

Result:

- best tested config: `tf32_32x64x32`
- Down paired device ratio approximately 1.3788
- Up approximately 1.3420
- Triton still slower than dense.

Conclusion:

- no speed win;
- do not treat earlier sync-contaminated timing as pure kernel comparison.

### C34

Completed earlier in Gate C. Preserve as historical context. Exact details should be reconstructed from its run artifact if needed rather than guessed here.

### C35 — full-model validation-boundary diagnostic

Established a Graph-safe diagnostic boundary using structural validation rather than `torch.isfinite(...).all()` inside capture.

Important class pattern:

```python
class BoundaryBank(_StructuralValidationMixin, TritonCompressedLinearBank):
    pass
```

### C36

Completed earlier in Gate C. Preserve as historical context. Exact details should be reconstructed from its run artifact if needed rather than guessed here.

### C37 — serial CPU-ready request + CUDA Graph cost

Protected result.

Initial timings approximately:

- dense eager: 1.6531 ms
- Triton eager: 2.0269 ms
- dense Graph: 0.4395 ms
- Triton Graph: 0.4630 ms
- paired Triton/dense Graph median approximately 1.069

Conclusion:

- CUDA Graph removes a large amount of dispatch overhead;
- compressed path remains slower;
- Gate C not passed.

### C38 — regression

- `tests`: 28 PASS
- `tests_lm`: 347 PASS
- `tests_reasoning`: 40 PASS
- total: 415 PASS
- compileall PASS
- C37 result hash preserved.

### C39 — protected result inspection

Read-only verification; C37 hash preserved.

### C40 — allocator memory diagnostic

Produced a useful storage number but GPU baseline was contaminated by earlier allocations. Superseded for clean memory conclusions by C41.

### C41 — reference-isolated fresh-process Graph memory

Accepted clean memory result.

- registered storage: Dense 51,200 B vs Triton 44,800 B
- **12.5% model registered storage reduction**
- total Graph allocated reduction only 6,144 B (~0.064%)
- reserved identical at 26 MiB.

Conclusion:

- real model-payload storage advantage exists;
- tiny-test total VRAM is dominated by runtime overhead.

### C42 — repeated C37 request benchmark

32 rounds x 100 requests.

Medians:

- dense eager: 1.7551205 ms
- Triton eager: 2.0955685 ms
- dense Graph: 0.4406675 ms
- Triton Graph: 0.4474035 ms

Paired median ratios:

- Triton/dense eager: 1.19862
- Triton/dense Graph: 1.028879

Conclusion:

- Graph path narrows gap to ~2.9%;
- still slower.

### C43 — request phase breakdown

Approximate instrumented Dense request shares:

- input validation: 8.3%
- blocking H2D: 27.15%
- Graph + D2H: 57.80%
- output validation: 6.48%

Triton shares were similar.

Conclusion:

- end-to-end request overhead dilutes the kernel difference;
- phase instrumentation itself perturbs timing, so use diagnostically.

### C44 — non-blocking H2D diagnostic

Queued/non-blocking copy improved both variants.

Paired medians:

- Dense queued/blocking: 0.80791
- Triton queued/blocking: 0.81044
- queued Triton/dense: 1.01721

Conclusion:

- common runtime path can improve ~19%;
- compressed path still ~1.7% slower end-to-end in this diagnostic.

### C45 — GPU-only CUDA Graph replay

Transfers and CPU validation excluded.

Device medians:

- dense Graph: 0.289680 ms
- Triton Graph: 0.306309 ms
- paired Triton/dense median: **1.05546**

Conclusion:

- remaining gap is genuinely in GPU compressed compute / Graph path (~5.5%), not CPU/H2D/D2H/Python submission.

### C46 — Up / Down Triton runtime isolation

Accepted after retries fixing diagnostic construction and Graph-safe validation.

Device paired medians:

- Up Triton / Dense: **1.03479**
- Down Triton / Dense: **1.00629**
- Full Triton / Dense: **1.03246**
- Full / Up: ~0.99874

Conclusion:

- the remaining slowdown is overwhelmingly caused by the **Up Linear** path;
- Down is essentially near dense.

### C47 — Up `BLOCK_M` sweep

Real Up geometry:

- input width: 32
- output width: 64

Compared `BLOCK_M=16`, 32, 64 at `num_warps=4`.

Results:

- BM32/current device median ratio: 0.98282
- BM64/current device median ratio: **0.97698**
- BM64/dense device median ratio: **1.00942**
- BM64 faster than current in 27/32 rounds
- output parity exact in checked cases
- score 1.0

Conclusion:

- **Up `BLOCK_M=64` is the current best geometry change**;
- it cuts most of the full-model GPU gap without changing storage or numerics.

### C48 — Up `num_warps` sweep

With `BLOCK_M=64`, tested 1/2/4/8 warps.

Paired device medians vs dense:

- w1: 1.01096
- w2: 1.08942
- w4: **1.00696**
- w8: 1.03270

w1 vs w4: 1.00052 (19 faster / 21 slower).

Conclusion:

- 1 and 4 are effectively tied;
- no evidence to replace w4;
- w2 and w8 are clearly worse;
- retain `BLOCK_M=64, num_warps=4` as the robust diagnostic geometry.

### C49 — Up correction `E` isolation

Real Up bank-level geometry:

- rows: 1728
- input: 32
- output: 64
- correction nnz per module: 64

Paired medians:

- full-E / no-E: **1.01324** (first accepted run) / approximately 1.03 in independent rerun
- no-E / dense materialized: **~2.18-2.38x**

Conclusion:

- correction `E` is **not** the main runtime problem;
- even without E, compressed Up kernel remains much slower than materialized dense at bank level;
- do not spend primary optimization effort on E yet.

### C50 — real-Up row-reuse comparison

Compared:

- dense no-E
- BM64/W4 row-wise no-E
- existing batch-tiled row-reuse no-E kernel using `tl.dot`

Paired medians:

- tiled / row-wise: **1.02009**
- row-wise / dense: **2.06828**
- tiled / dense: **2.09932**

Conclusion:

- existing row-reuse tiled kernel is **not** an improvement for the real Up shape;
- do not add E to this tiled path yet.

### C51 — real-Up base / codebook isolation

Valid accepted run used runner SHA:

`DD705E5EA1C023115E873E894D4117DA245CBE7C5875ED1C4E4A935A223F500C`

Compared:

- dense no-E
- base-only cuBLAS/F.linear
- row-wise no-E
- hybrid: base through F.linear + codebook delta through Triton

Paired medians:

- base / dense: **1.00944**
- row-wise / dense: **2.11740**
- hybrid / dense: **3.40778**
- hybrid / row-wise: **1.62845**
- hybrid / base: **3.39359**

Conclusion:

- shared base GEMM is basically fine;
- the expensive part is codebook-delta/decode execution;
- the current hybrid split is worse than row-wise and is rejected.

Invalid C51 attempt note:

- an earlier C51 wrapper accidentally executed the C49 runner (`CEAC...`).
- it must not be treated as C51 evidence.

### C52 — real-Up decode-workspace

Accepted runner SHA:

`50AD4C9DA0410DA02A5FC3DDCD3B2CD09A3943E14DE4DE070C2470E28405C27B`

Workspace:

- one dense scratch matrix
- 64 x 32 x 4 B = **8,192 B**

Paired medians:

- row-wise / dense: **2.17013**
- decode-workspace / dense: **2.96321**
- decode-workspace / row-wise: **1.36082**
- decode-only / dense: **0.98747**
- decode-only fraction of decode-workspace: **0.33336**

Conclusion:

- decode-workspace is slower than row-wise in **80/80** samples;
- it also adds 8,192 B resident scratch;
- reject as current Gate C candidate.

### C53 — real-Up row-wise component ablation

Accepted runner SHA:

`07351CC9B193CCBB0B96E6FE0E188FD6728A9AC25C01B4DABAAA26C73B88A227`

Output directory:

`M:\asobiba\fold\runs\c53-rowwise-components-01d65fad04e7434ba48e019124d2e384`

Geometry:

- activation: `[216, 8, 32]`
- flattened rows: 1728
- input width: 32
- output width: 64
- `BLOCK_M=64`
- `BLOCK_K=32`
- `num_warps=4`

Device medians:

- dense no-E: 0.0118864 ms
- row-wise base-only: 0.0120516 ms
- row-wise delta-only: 0.0213311 ms
- row-wise full no-E: 0.0182702 ms

Paired medians:

- base / dense: **1.04502**
- delta / dense: **1.68804**
- full / dense: **1.43449**
- full / base: **1.38851**
- delta / base: **1.71970**
- full / delta: **0.82805**

Correctness:

- full vs dense max gap <= 9.54e-7
- base+delta vs dense max gap <= 7.15e-7
- base vs cuBLAS-base max gap <= 4.77e-7
- delta vs cuBLAS-delta max gap <= 5.96e-7

Conclusion:

- **row-wise base computation is near dense** (only ~4.5% median overhead in this component diagnostic);
- **codebook delta/decode is the dominant expensive component** (~1.69x dense, ~1.72x base);
- optimization should now target codebook-delta lookup / reconstruction / application rather than base GEMM, correction E, row reuse, or dense workspace.

---

## 9. Invalid / retry history that must not be mistaken for evidence

- C46 first failure: diagnostic `HybridCore` lacked `initial_working_state`.
- C46 second failure: raw Triton bank inherited finite validation and failed CUDA Graph capture.
- C46 retry 2: valid PASS after Graph-safe boundary bank.
- C49 first command attempt: PowerShell block did not actually start the experiment; empty summary only.
- C51 first attempt: wrapper ran C49 runner by mistake; invalid as C51 evidence.
- C52 first attempt: wrong runner payload detected by SHA mismatch before Python executed; invalid.
- C53 first attempt: PowerShell parser error before experiment start; invalid.
- C53 retry: valid PASS.

Retries do not consume a new C number.

---

## 10. Current scientific conclusion after C53

The current V5-C compact candidate has demonstrated:

### Positive

- model registered storage is **12.5% lower** than dense in the current small fixture;
- full compressed fixture quality remains equal on the checked synthetic task;
- CUDA Graph and runtime-boundary work has reduced end-to-end timing gap substantially;
- Down compressed role is essentially near dense;
- Up geometry tuning (`BLOCK_M=64`) removes most of the earlier full-model GPU gap.

### Remaining blocker

The remaining runtime inefficiency is now localized primarily to **Up codebook-delta/decode execution**.

The following have been tested and are not the main solution:

- correction `E` optimization alone;
- existing row-reuse tiled kernel;
- cuBLAS-base + separate Triton-delta hybrid;
- decode-to-dense-workspace every forward;
- `num_warps` sweep.

The shared base GEMM itself is not the main bottleneck.

Therefore the next work should focus narrowly on reducing the cost of:

- code lookup;
- codebook element loads;
- repeated index arithmetic;
- delta reconstruction / application;
- memory-access layout / reuse for the real `32 -> 64` Up shape;
- potentially alternative compact execution layouts that preserve compact resident storage.

Do not broaden the search again until this component is understood.

---

## 11. Current Gate C decision

**Gate C remains NOT PASSED.**

Reason:

- storage advantage is established in the current small fixture;
- checked fixture quality is preserved;
- but compact runtime still has decode/codebook overhead, and the roadmap explicitly says storage savings that worsen real runtime do not satisfy Gate C.

A future Gate C PASS must be based on the gate definition, not on an individual Cxx script PASS.

---

## 12. Next experiment

### Next ID: C54

Target:

**Real-Up codebook-delta microarchitecture isolation / optimization.**

C53 says the codebook delta path is the dominant expensive component.

C54 should keep the following fixed:

- real fixture shape: flattened 1728 x 32 -> 64;
- no-E for the first microarchitectural diagnostic unless E is specifically required;
- same compact codebook/codes representation;
- `BLOCK_M=64` reference geometry where applicable;
- no production runtime modification;
- protected C37 result and fixture preserved.

The experiment should separate or compare concrete causes inside codebook delta execution, for example bounded alternatives around:

- code-index/address arithmetic;
- codebook gather pattern;
- per-row repeated delta reconstruction;
- precomputed compact offsets / layout transforms that do not create a dense module weight;
- a fused delta application that avoids the rejected two-kernel hybrid overhead.

Do **not** claim a Gate C pass from C54 alone.

---

## 13. Handoff instructions for a new chat/session

When resuming FOLD in a new session:

1. Read this file first.
2. Confirm branch / HEAD and protected hashes.
3. Read only the design/runtime files needed for the next experiment; do not reconstruct all history unnecessarily.
4. Continue at the `Next ID` in section 12.
5. Keep one experiment per C number.
6. On failure, retry the same C number.
7. After accepting a result, update this ledger before moving on.
8. When a Gate decision changes, record the exact evidence and decision here.

The objective is that this file, plus the repository itself, is enough to continue even when the original ChatGPT conversation is unavailable.
