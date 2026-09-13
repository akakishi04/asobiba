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
11. When a scientific acceptance margin is needed, define it before running the new data.

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
- Shared Basis remains the lead representation family;
- one universal rank rule is rejected;
- rank/capacity is adaptive by functional need;
- native joint-training default on current tasks is `factor_lr = common_lr`;
- intended inference form is GEMM-native `[W_base; B_shared]` projection + coefficient `addmm`;
- effective-weight materialization is reference-only;
- rank allocation must account for runtime cost as well as quality/storage;
- Condition rank4 remains the accepted safe point until C76 decides whether rank3 can be declared prospectively non-inferior;
- production integration waits until rank policy and representative runtime practicality are sufficiently resolved.

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

### C59-C64 — quality/capacity

- post-hoc SVD alone is not a useful task objective;
- task-aware factor learning recovers Composition;
- Composition rank2 / routed ratio `0.5703125` reproduces 3/3 seeds at Dense score;
- Condition rank1 insufficient;
- C63: Condition rank4 is first tested robust recovery point, routed ratio `0.78125`;
- C64: Language rank2 has functional capacity but can overtrain; rank4 is stable under the fixed final checkpoint, routed ratio `0.640625`.

### C65-C67 — native direct joint training

C65 showed native Shared Basis training is feasible but Language was unstable with factor lr0.002 vs common lr0.01.

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

### C71-C72 — selected-shape runtime

C71 selected small task shapes saved persistent bytes but paid eager latency. Across batches 1/8/32, median Shared/Dense latency ratio = `1.3765237679`; forward peak-delta ratio median = `1.1212121212`.

C72 CUDA Graph replay did not remove the penalty:

- graph median latency ratio: `1.4057762261`
- C71 eager median: `1.3765237679`
- graph better than eager at only 3/9 points

Decision: small-shape runtime tax is not primarily Python / launch overhead; extra arithmetic, shape efficiency, and memory traffic dominate.

## 6. C73 — extended full-core width / rank scaling

Accepted run commit: `136690b027ebc4ef512e0766d947cd18e77d59f0`.

Widths:

```text
32, 64, 128, 256, 512, 1024, 1536, 2048, 3072, 4096, 5120
```

Fixed full-core shape: slots20, modules2, hidden_mult2, eager CUDA, batches1/8.

Rank profiles:

```text
lean   = width / 16   routed ratio 0.5703125
medium = width / 8    routed ratio 0.640625
high   = width / 4    routed ratio 0.78125
```

At width5120:

| profile | full-core persistent ratio | batch1 latency | batch8 latency |
|---|---:|---:|---:|
| lean | ~0.7136 | 1.05725 | 1.06427 |
| medium | ~0.7605 | 1.07800 | 1.11564 |
| high | ~0.8542 | 1.23527 | 1.21851 |

Decision:

1. lean is strongly runtime-viable at large width;
2. medium is plausible and approaches ~1.1x;
3. high retains a material ~20%+ runtime penalty at large width;
4. rank allocation must include runtime cost in the objective.

## 7. C74 — Condition rank3 12-seed exhaustive viability

Accepted run commit: `15d380a59f8a0940272b6ff95c229567fdf9d309`.

Experiment ID:

`C74-shared-basis-condition-rank3-12seed-exhaustive`

Setup: rank3 candidate vs accepted rank4 and Dense, aligned lr0.01, 260 steps, batch32, train256, seeds `20260911..20260922`, exhaustive held-out 32,512/seed.

Storage:

- rank3 routed-weight ratio: `0.7109375`
- rank4 routed-weight ratio: `0.78125`
- rank3 uses 91% of rank4 routed-weight bytes

Rank3 vs Dense:

- mean: `-0.00117391348`
- median: `-0.00072279572`
- min: `-0.00922733545`
- max: `+0.00661295652`
- rank3 wins 4, Dense wins 8
- sign-test p = `0.3876953125`
- pooled net rank3 advantage = `-458`

Rank3 vs rank4:

- mean delta: `-0.00092273454`
- median delta: `-0.00016915798`
- rank3 better 6, rank4 better 6

Decision after C74:

- retain rank4 as accepted safe Condition point;
- keep rank3 as optimization candidate;
- do not call rank3 equivalent because C74 had no predeclared equivalence margin;
- measure runtime benefit before spending more quality experiments.

## 8. C75 — Condition rank3-vs-rank4 runtime/storage bridge

Accepted run commit: `cc78d3462788efd43772a4e2d53794ed987b846a`.

Experiment ID:

`C75-shared-basis-condition-rank3-rank4-runtime-bridge`

Profiles:

```text
rank3_bridge = 3 * width / 16
rank4_high   = width / 4
```

Widths `16..5120`; width16 includes real Condition-like slots1 plus slots20; larger widths use slots20; batches1/8; eager CUDA.

### Actual Condition-like width16 / slots1

- batch1 rank3 Shared/Dense median: `1.49920723`
- batch1 rank4 Shared/Dense median: `1.49294089`
- rank3 is essentially unchanged/slightly worse at batch1 (`~1.0042x` rank3/rank4 tax ratio)
- batch8 rank3: `1.37943576`
- batch8 rank4: `1.49792140`
- batch8 rank3/rank4 tax ratio: `0.92090`

Small-shape results remain noisy and are not the primary scaling decision.

### Width5120 endpoint

- batch1 rank3 Shared/Dense: **1.13681493**
- batch1 rank4 Shared/Dense: **1.20286584**
- rank3/rank4 latency-tax ratio: **0.94509** (~5.5% relative improvement)
- batch8 rank3 Shared/Dense: **1.17189873**
- batch8 rank4 Shared/Dense: **1.20927834**
- rank3/rank4 latency-tax ratio: **0.96909** (~3.1% relative improvement)

Persistent full-core bytes at width5120:

- rank3 full-core ratio vs Dense: `0.80734184`
- rank4 full-core ratio vs Dense: `0.85420463`
- rank3 / rank4 persistent bytes: **0.94513868** (~5.5% smaller)

### C75 interpretation

Rank3 provides a real but moderate operational benefit over rank4 at large width:

- about 5.5% lower full-core persistent bytes;
- about 3-5.5% lower endpoint latency tax in the tested large-width points.

This benefit is large enough to justify one final prospective quality decision, but not large enough to ignore the C74 quality-risk signal.

Therefore:

- rank4 remains the accepted safe Condition point;
- rank3 remains a candidate only;
- the next test must use independent seeds and a quality margin fixed before observing them;
- if rank3 fails that prospective gate, stop rank3 pursuit and retain rank4.

Gate C remains **NOT PASSED**.

## 9. Auto-Partition / adaptive-capacity consequence

Main living document:

`fold/docs/shared-basis-auto-module-partition-report.md`

Current rules from C71-C75:

- runtime cost is a first-class rank-allocation cost;
- lower rank is preferred only when its quality margin is established prospectively;
- high-rank groups carry measurable runtime tax at large width;
- do not call two ranks equivalent from mixed-sign retrospective data alone;
- a modest runtime/storage gain must not justify moving the quality goalposts;
- if two capacities pass the same quality gate, prefer the lower-rank Pareto point.

## 10. Next experiment — C76

**Prospective independent-seed Condition rank3 non-inferiority.**

Tracked benchmark:

`fold/fold_lm/v05_benchmarks/gate_c_shared_basis_condition_rank3_prospective_noninferiority.py`

Benchmark creation commit:

`e0e248a4f2a9395bbbed73b9b404c236ed5635d8`

### Scientific question

Does rank3 remain within a predeclared acceptable average exhaustive-quality loss relative to rank4 on data/initialization seeds not used by C69/C74?

### Fixed before execution

New independent seeds:

```text
20260923..20260946   (24 seeds)
```

No overlap with C74.

Both candidates use:

- same untrained initialization provenance per seed;
- same training data;
- same batch sequence;
- aligned lr0.01;
- 260 steps;
- batch32;
- train size256;
- exhaustive held-out 32,512 per seed.

Primary paired quantity:

```text
rank3 exhaustive trajectory_exact_accuracy
-
rank4 exhaustive trajectory_exact_accuracy
```

### Prospectively declared non-inferiority rule

Engineering margin:

```text
-0.002 absolute accuracy
= -0.20 percentage point
```

Deterministic paired bootstrap:

- 100,000 resamples;
- resample unit = seed, not individual trajectories;
- bootstrap seed = 20260914;
- one-sided 95% lower percentile bound on the mean paired delta.

Scientific gate:

```text
noninferiority_gate_passed =
    lower_95_bound(mean(rank3-rank4)) > -0.002
```

This margin is recorded before C76 runs. It is an engineering tolerance chosen in light of C75's ~3-5.5% latency and ~5.5% persistent-byte benefit; it is not a universal statistical standard and must not be changed after seeing C76 outcomes.

Supporting diagnostics:

- mean / median / min / max paired delta;
- rank3/rank4 seed win counts;
- sign-test diagnostic;
- pooled paired rank3-only / rank4-only counts;
- storage ratios.

Interpretation:

- if the prospective gate passes, rank3 may replace rank4 as the selected Condition candidate for subsequent integration work, with the result limited to this tiny synthetic domain;
- if the gate fails, retain rank4 and stop rank3 optimization on the current evidence;
- C76 `status=PASS` only means execution succeeded; it does not imply the non-inferiority gate passed;
- C76 cannot establish Gate C passage by itself.

## 11. Handoff

On a new session:

1. read this ledger;
2. confirm branch/HEAD and protected hashes;
3. continue at C76;
4. keep one experiment per C number;
5. retry invalid/failing execution under the same number;
6. do not alter the C76 non-inferiority margin after seeing results;
7. update this file after every accepted result or Gate decision change.
