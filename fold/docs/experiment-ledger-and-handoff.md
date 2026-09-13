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
6. Failed / invalid retries keep the same C number.
7. `status=PASS` means the experiment executed correctly, not that Gate C passed.
8. Invalid import / parser / hash / experiment-ID runs are not evidence.
9. Prefer tracked benchmark files.
10. Long-running experiments must print useful progress.

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

Current conclusions:

- direct fine-grained codebook execution is storage/reference only;
- Shared Basis is the lead representation family;
- one universal rank rule is rejected;
- rank/capacity is adaptive by functional need;
- native joint-training default on current tasks is `factor_lr = common_lr`;
- intended inference form is GEMM-native `[W_base; B_shared]` projection + coefficient `addmm`;
- effective-weight materialization is reference-only;
- rank allocation must account for **runtime cost as well as quality/storage**;
- production integration waits until selected rank policy and runtime practicality are sufficiently resolved.

Do not claim that fixture success proves broad language quality or that FOLD beats Transformers / existing LLMs.

## 5. Key accepted history

### C41-C57 — codebook path

Storage reduction exists, but direct codebook GPU decode/gather becomes the runtime blocker. C57 width1024 compact/dense = `12.88719`; compact/predecoded = `2.18005`. Decision: stop primary optimization of direct fine-grained codebook execution.

### C58 — Shared Basis runtime scale

Synthetic `rank=width/16` diagnostic:

- width256: `1.63577x`
- width512: `1.29614x`
- width1024: `1.19407x`

Large widths trend toward Dense. Runtime feasibility only.

### C59-C61 — task-aware capacity

- post-hoc SVD alone is not a useful task objective;
- task-aware factor learning recovers Composition;
- Composition rank2 / routed ratio `0.5703125` reproduces 3/3 seeds at Dense score.

### C62-C64 — task-dependent rank and checkpoint behavior

- Composition rank2 robust;
- Condition rank1 insufficient;
- C63: Condition rank4 is first tested robust recovery point, routed ratio `0.78125`;
- C64: Language rank2 has sufficient functional capacity but can overtrain; rank4 is stable under the fixed final checkpoint, routed ratio `0.640625`.

### C65-C67 — native direct joint training

C65 established that native factorized training is feasible but showed Language instability with factor lr0.002 vs common lr0.01.

C66 Language rank4 factor-LR sweep:

- 0.002 -> fail
- 0.005 -> one seed fail
- 0.010 -> 3/3 Dense match

C67 established the current native rule:

```text
factor_lr = common_lr
```

Composition and Language match Dense 3/3; Condition had only tiny validation residuals.

### C68-C69 — Condition rank4 exhaustive robustness

C69 extended Condition rank4 aligned training to 12 seeds with exhaustive 32,512 held-out trajectories per seed:

- Direct wins: 6
- Dense wins: 6
- two-sided sign-test p: 1.0
- mean exact delta: `-0.00025117894`
- median delta: `-0.00006151199`
- pooled net Direct advantage: `-98` over 390,144 held-out examples

Decision: no evidence of a systematic rank4 Condition quality deficit large enough to justify more rank. Treat remaining difference primarily as seed / optimizer variance on this tiny task.

### C70 — GEMM-native recurrence equivalence

Accepted run commit: `cd18de18a8d167a1bbdf5eb0cbb863d8737e77f3`.

3 tasks x 3 seeds, selected ranks, aligned native training. Materialized effective-weight execution vs GEMM-native Shared Basis:

- validation scores equal: true
- validation semantics equal: true
- validation outputs allclose: true
- recurrence depths 1/2/4/8/16/32/64 allclose: true
- max validation abs gap: `5.245208740234375e-06`
- max recurrence abs gap: `7.62939453125e-05`
- max recurrence relative-L2 gap: `5.212819324264913e-07`

Decision: GEMM-native arithmetic is numerically safe in the tested float32 regime through 64 updates.

### C71 — selected-shape eager runtime / memory

Accepted run commit: `c75ff30fce256ec5795fb922c27bce5e61977282`.

Selected shapes:

| task | width | slots | rank | routed ratio | full-core persistent ratio |
|---|---:|---:|---:|---:|---:|
| condition | 16 | 1 | 4 | 0.78125 | 0.8653846154 |
| composition | 32 | 1 | 2 | 0.5703125 | 0.725 |
| language | 32 | 20 | 4 | 0.640625 | 0.77 |

Across batches 1/8/32, median eager latency ratio = `1.3765237679`; best = `1.2975680667`; worst = `1.4211179436`. Forward peak-delta ratio median = `1.1212121212`.

Storage savings survive at full-core level, but current tiny shapes pay ~30-42% latency overhead.

### C72 — selected-shape CUDA Graph replay

Accepted run commit: `028f406747bf585d6778852355138c4901df535f`.

- all graph outputs allclose: true
- graph median latency ratio: `1.4057762261`
- C71 eager median: `1.3765237679`
- graph better than eager at only 3/9 points

Decision: CUDA Graph does not remove the small-shape penalty. Extra arithmetic / shape efficiency / memory traffic dominate more than Python or launch overhead.

## 6. C73 — extended full-core width / rank scaling

Accepted run commit: `136690b027ebc4ef512e0766d947cd18e77d59f0`.

Experiment ID:

`C73-shared-basis-full-core-width-rank-scaling`

Widths:

```text
32, 64, 128, 256, 512, 1024, 1536, 2048, 3072, 4096, 5120
```

Fixed full-core shape:

- slots=20
- modules=2
- hidden_mult=2
- eager CUDA
- batches 1 / 8

Rank profiles:

```text
lean   = width / 16   routed ratio 0.5703125
medium = width / 8    routed ratio 0.640625
high   = width / 4    routed ratio 0.78125
```

### C73 large-width endpoint results

#### Lean — rank fraction 1/16

Full-core persistent ratio converges near `0.7136`.

At width5120:

- batch1 latency ratio: **1.05725**
- batch8 latency ratio: **1.06427**

Interpretation: lean Shared Basis becomes close to Dense runtime while retaining ~28.6% full-core persistent-byte reduction.

#### Medium — rank fraction 1/8

Full-core persistent ratio converges near `0.7605`.

At width5120:

- batch1: **1.07800**
- batch8: **1.11564**

Interpretation: medium rank remains operationally plausible at large width, with ~24.0% full-core persistent-byte reduction and roughly 8-12% endpoint latency tax.

#### High — rank fraction 1/4

Full-core persistent ratio converges near `0.8542`.

At width5120:

- batch1: **1.23527**
- batch8: **1.21851**

At widths3072-5120 the high profile remains roughly in the `1.18-1.24x` range.

Interpretation: the high rank fraction carries a persistent runtime tax even at width5120, while saving only ~14.6% full-core persistent bytes.

### C73 design decision

C73 confirms that Shared Basis runtime viability is **rank-dependent**:

1. lean is strongly runtime-viable at large width;
2. medium is plausible and approaches ~1.1x;
3. high retains a material ~20%+ runtime penalty at large width.

Therefore rank cannot be selected from quality/storage alone. Adaptive capacity / Auto-Partition must include runtime cost in the objective.

## 7. C74 — Condition rank3 12-seed exhaustive viability

Accepted run commit: `15d380a59f8a0940272b6ff95c229567fdf9d309`.

Experiment ID:

`C74-shared-basis-condition-rank3-12seed-exhaustive`

Fixed setup:

- Condition only;
- rank3 candidate vs accepted rank4 and Dense;
- aligned lr0.01;
- 260 steps, batch32, train size256;
- seeds `20260911..20260922`;
- exhaustive held-out 32,512 per seed;
- Dense references reproduced C69 exactly.

Storage:

- rank3 routed-weight ratio: **0.7109375**;
- rank4 routed-weight ratio: **0.78125**;
- rank3 uses **91%** of rank4 routed-weight bytes, i.e. a further 9% reduction vs rank4.

Rank3 vs Dense exhaustive exact delta:

- mean: **-0.00117391348**;
- median: **-0.00072279572**;
- min: -0.00922733545;
- max: +0.00661295652;
- rank3 wins: 4 seeds;
- Dense wins: 8 seeds;
- sign-test two-sided p = **0.3876953125**;
- pooled Dense-only correct: 1,782;
- pooled rank3-only correct: 1,324;
- pooled net rank3 advantage: **-458**.

Rank3 vs accepted rank4:

- mean delta: **-0.00092273454**;
- median delta: **-0.00016915798**;
- rank3 better: 6 seeds;
- rank4 better: 6 seeds.

### C74 interpretation

Rank3 is not catastrophically capacity-limited, but it does not earn automatic adoption either.

Evidence is mixed:

1. rank3-vs-rank4 seed direction is exactly balanced 6/6;
2. rank3-vs-Dense direction tilts 4/8 and pooled counts favor Dense;
3. the mean deficits are small in absolute terms, but some individual seeds lose close to 1 percentage point;
4. there was no predeclared equivalence margin, so C74 cannot honestly certify rank3 as quality-equivalent;
5. rank3 buys only a 9% routed-weight reduction relative to rank4, so its runtime benefit must be measured before spending more quality experiments.

Decision after C74:

- **retain rank4 as the accepted safe Condition point for now**;
- keep rank3 as an optimization candidate, not an accepted replacement;
- next quantify the actual runtime/storage benefit of the 3/16 rank fraction versus 1/4;
- only if that benefit is material should a stricter prospectively-defined quality-equivalence experiment be considered.

Gate C remains **NOT PASSED**.

## 8. Auto-Partition / adaptive-capacity consequence

Main living document:

`fold/docs/shared-basis-auto-module-partition-report.md`

Current rule additions from C71-C74:

- runtime cost is a first-class rank-allocation cost;
- lower rank is preferred only when the quality margin remains acceptable;
- do not convert a small average quality deficit into an automatic rejection without considering seed variance, but do not call it equivalent without a declared margin either;
- high-rank groups carry a measurable runtime tax at large width;
- C74 shows why rank reduction needs a Pareto decision: 9% extra routed-byte saving is accompanied by a small but nonzero quality-risk signal.

The connector previously rejected one large living-spec rewrite; preserve these accepted conclusions here until that document can be refreshed safely without truncation.

## 9. Next experiment — C75

**Condition rank3-vs-rank4 runtime/storage bridge.**

Tracked benchmark:

`fold/fold_lm/v05_benchmarks/gate_c_shared_basis_condition_rank3_rank4_runtime_bridge.py`

Benchmark creation commit:

`a9cb67fc9ca5a3f7ab590862b443f9e791b5e813`

Question: before spending more quality trials on rank3, how much real runtime/storage benefit does the 3/16 rank fraction provide over the accepted 1/4 rank fraction?

Profiles:

```text
rank3_bridge = 3 * width / 16
rank4_high   = width / 4
```

Widths:

```text
16, 32, 64, 128, 256, 512, 1024, 2048, 3072, 4096, 5120
```

Execution:

- modules=2, hidden_mult=2;
- width16 includes the real Condition-like slots=1 point plus slots=20;
- larger widths use slots=20;
- batches 1 / 8;
- eager CUDA;
- both routes;
- 10 paired rounds;
- 50 CUDA-event iterations per sample;
- persistent bytes and forward peak delta measured;
- each profile is compared to a semantically identical materialized Dense effective-weight reference.

Primary outputs:

- actual width16 rank3 vs rank4 latency-tax ratios;
- large-width rank3-vs-rank4 latency-tax difference;
- rank3 vs rank4 full-core persistent bytes at width5120;
- routed and temporary-memory ratios.

Interpretation:

- if rank3 materially reduces the runtime tax, then the 9% routed-byte saving plus runtime benefit may justify a stronger prospectively-defined quality-equivalence test;
- if runtime improvement is small, retain rank4 and avoid trading quality margin for little operational gain;
- C75 itself does not change the accepted quality rank.

## 10. Handoff

On a new session:

1. read this ledger;
2. confirm branch/HEAD and protected hashes;
3. continue at C75;
4. keep one experiment per C number;
5. retry failures under the same number;
6. update this file after every accepted result or Gate decision change.
