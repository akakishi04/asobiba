# FOLD Experiment Ledger and Handoff

> Project-wide handoff checkpoint for FOLD. Read this first in a new session. Update after every accepted Cxx result, retry decision, or Gate decision change.

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

1. One experiment / verification question per C number.
2. Full output overwrites `M:\asobiba\fold\runs\chatgpt-last.log`.
3. User pastes the full log back into ChatGPT.
4. ChatGPT judges the result.
5. Increment only after a valid successful run.
6. Failed/invalid retries keep the same C number.
7. `status=PASS` means the experiment executed correctly, not that Gate C passed.
8. Invalid import/parser/hash/experiment-ID runs are not evidence.
9. Prefer tracked benchmark files.
10. Long runs print useful progress.

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

## 4. Gate C status

Current status: **NOT PASSED**.

Lead routed-weight family:

```text
W_module = W_base + A_module @ B_shared
```

Current design conclusions:

- direct fine-grained codebook execution is storage/reference only;
- Shared Basis is the lead representation family;
- one universal rank rule is rejected;
- rank/capacity is adaptive by functional need;
- native joint-training default on current tasks is `factor_lr = common_lr`;
- intended inference form is GEMM-native `[W_base; B_shared]` projection + coefficient `addmm`;
- effective-weight materialization is reference-only;
- Gate C still requires practical runtime/memory and production integration.

Do not claim that fixture success proves broad language quality or that FOLD beats Transformers/LLMs.

## 5. Key accepted history

### C41-C57 — codebook path

- storage reduction exists, but direct codebook GPU decode/gather becomes the blocker;
- C57 width1024 compact/dense `12.88719`, compact/predecoded `2.18005`;
- decision: stop primary optimization of direct fine-grained codebook execution.

### C58 — Shared Basis runtime scale

Synthetic matched-storage diagnostic with `rank=width/16`:

- width256: shared/dense `1.63577`
- width512: `1.29614`
- width1024: `1.19407`

Large widths scale toward Dense. This was runtime feasibility only.

### C59-C61 — task-aware capacity

- post-hoc SVD objective alone is poor;
- task-aware factor learning recovers Composition;
- Composition rank2 / routed ratio `0.5703125` reproduces 3/3 seeds at dense score.

### C62-C64 — task-dependent rank / checkpoint behavior

- Composition rank2 robust;
- Condition rank1 insufficient;
- C63: Condition rank4 is first tested robust recovery point, routed ratio `0.78125`;
- C64: Language rank2 has sufficient capacity but can overtrain; rank4 is stable at fixed final checkpoint, routed ratio `0.640625`.

### C65-C67 — native direct joint training

C65 showed native Shared Basis training works, but Language was unstable with factor lr0.002 vs common lr0.01.

C66 Language rank4 factor-LR sweep:

- 0.002 -> fail
- 0.005 -> one seed fail
- 0.010 -> 3/3 dense match

C67 established the current rule:

```text
factor_lr = common_lr
```

Composition and Language match Dense 3/3; Condition had only tiny validation residuals.

### C68-C69 — Condition exhaustive robustness

C68 exhaustive 32,512 held-out examples over 3 seeds gave mixed signs.

C69 extended to 12 seeds with exact C68 reproduction:

- Direct wins: 6
- Dense wins: 6
- two-sided sign-test p: 1.0
- mean exact delta: `-0.00025117894`
- median delta: `-0.00006151199`
- pooled net Direct advantage: `-98` over 390,144 held-out examples

Decision: no evidence of systematic Condition rank4 deficit large enough to justify more rank. Treat remaining differences primarily as seed/optimizer variance on this tiny task.

### C70 — GEMM-native recurrence equivalence

Accepted run commit: `cd18de18a8d167a1bbdf5eb0cbb863d8737e77f3`.

3 tasks x 3 seeds, selected ranks, aligned native training. Compared materialized effective-weight execution to GEMM-native Shared Basis.

Accepted results:

- all validation scores equal: true
- all validation semantics equal: true
- all validation outputs allclose: true
- all recurrence depths 1/2/4/8/16/32/64 allclose: true
- all runtime formula equivalent: true
- max validation abs gap: `5.245208740234375e-06`
- max recurrence abs gap: `7.62939453125e-05`
- max recurrence relative-L2 gap: `5.212819324264913e-07`

Decision: GEMM-native arithmetic is numerically safe for the tested float32 regime through 64 updates.

## 6. C71 — selected-shape eager runtime / memory

Accepted run commit: `c75ff30fce256ec5795fb922c27bce5e61977282`.

Experiment ID:

`C71-shared-basis-selected-shape-runtime-memory`

Compared semantically identical cores:

1. `dense_materialized`: independent effective Up/Down routed matrices;
2. `shared_basis_gemm`: GEMM-native shared projection + coefficient addmm.

Current selected shapes:

| task | width | slots | rank | routed ratio | full-core persistent ratio |
|---|---:|---:|---:|---:|---:|
| condition | 16 | 1 | 4 | 0.78125 | 0.8653846154 |
| composition | 32 | 1 | 2 | 0.5703125 | 0.725 |
| language | 32 | 20 | 4 | 0.640625 | 0.77 |

Batches 1/8/32, both routes, 20 paired rounds, 200 CUDA-event iterations/sample.

Eager latency `shared_basis_gemm / dense_materialized` median by point:

- condition b1: `1.41907`
- condition b8: `1.33537`
- condition b32: `1.34775`
- composition b1: `1.41822`
- composition b8: `1.41989`
- composition b32: `1.36129`
- language b1: `1.37652`
- language b8: `1.42112`
- language b32: `1.29757`

Aggregate selected-shape latency ratio:

- median: **1.3765237679**
- best point: **1.2975680667**
- worst point: **1.4211179436**

Allocator-observed forward peak-delta ratio:

- aggregate median: **1.1212121212**
- maximum point: about **1.1397**

### C71 interpretation

Storage savings survive at full-core level:

- Condition ~13.5% persistent-core reduction;
- Composition ~27.5% reduction;
- Language ~23.0% reduction.

However, current tiny eager shapes pay a material runtime cost:

- roughly 30-42% median latency overhead;
- roughly 0-14% extra forward temporary allocation depending on point.

This does not yet reject Shared Basis because:

1. C58 already showed latency overhead falling strongly with width;
2. C71 is eager CUDA and the candidate introduces extra GEMM-family launches;
3. the current task shapes are intentionally tiny compared with intended model scale.

Do **not** production-integrate yet. First isolate launch overhead with CUDA Graph at the exact same selected shapes. If Graph materially closes the gap, integration becomes more plausible; if not, run a full-core width/rank scaling frontier before deciding runtime viability.

Gate C remains **NOT PASSED**.

## 7. Auto-Partition living spec

Main document:

`fold/docs/shared-basis-auto-module-partition-report.md`

Relevant current rules:

- max-share inside hard bucket;
- diagnose optimizer/co-adaptation before Split;
- diagnose rank insufficiency before Split;
- require directional multi-seed persistence, not merely multiple nonzero differences;
- C69's mixed-sign 6/6 result is KEEP / no rank-grow evidence;
- runtime reuse is secondary to quality and training stability;
- C70 supports GEMM-native recurrence safety in the tested regime;
- C71 shows grouping/runtime reuse must account for extra-launch and temporary-memory costs on small shapes.

The connector rejected one earlier large-file maintenance write; if direct update remains blocked, keep the scientific decision here until the living spec can be safely refreshed without losing its detailed content.

## 8. Next experiment — C72

**Selected-shape CUDA Graph replay latency diagnostic.**

Tracked benchmark:

`fold/fold_lm/v05_benchmarks/gate_c_shared_basis_selected_shape_cuda_graph.py`

Benchmark creation commit:

`66b09ed3d08d3076e106635a5e71359a80063099`

Question: how much of C71's ~1.38x eager penalty is fixed launch/shape overhead that CUDA Graph replay can remove?

Fixed setup:

- same tasks: condition / composition / language;
- same ranks: 4 / 2 / 4;
- same batches: 1 / 8 / 32;
- same semantically identical materialized vs GEMM-native cores;
- both routes;
- one CUDA Graph per variant/route with static inputs;
- 20 paired rounds;
- 500 graph replays per latency sample;
- C71 eager median for the same `(task,batch)` point is carried into the result.

Primary outputs:

- `summary.graph_latency_median_ratio_across_task_batch_points`
- `summary.graph_over_eager_ratio_of_ratios`
- `summary.points_graph_ratio_below_eager_ratio`
- `summary.all_graph_outputs_allclose`

Interpretation:

- Graph ratio much closer to 1 than eager -> launch overhead is a major part of C71 penalty; proceed toward integration / graph residency accounting;
- Graph ratio remains near ~1.3-1.4 -> extra arithmetic/memory traffic dominates at these shapes; next run full-core width/rank scale before integration;
- semantic/allclose failure -> C72 invalidates Graph execution for this candidate until diagnosed.

C72 does not modify production runtime and cannot establish Gate C passage alone.

## 9. Handoff

On a new session:

1. read this ledger;
2. confirm branch/HEAD and protected hashes;
3. continue at C72;
4. keep one experiment per C number;
5. retry failures under the same number;
6. update this file after every accepted result or Gate decision change.
