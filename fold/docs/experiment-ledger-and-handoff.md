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
- rank allocation must now account for **runtime cost as well as quality/storage**;
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

### C68-C69 — Condition exhaustive robustness

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

Thresholds:

- batch1 <=1.10 first at width3072
- batch8 <=1.10 first at width1536

Interpretation: lean Shared Basis becomes close to Dense runtime while retaining ~28.6% full-core persistent-byte reduction.

#### Medium — rank fraction 1/8

Full-core persistent ratio converges near `0.7605`.

At width5120:

- batch1: **1.07800**
- batch8: **1.11564**

Thresholds:

- batch1 <=1.15 first at width3072; <=1.10 at width5120
- batch8 <=1.15 first at width3072; <=1.10 not reached by width5120

Interpretation: medium rank remains operationally plausible at large width, with ~24.0% full-core persistent-byte reduction and roughly 8-12% endpoint latency tax.

#### High — rank fraction 1/4

Full-core persistent ratio converges near `0.8542`.

At width5120:

- batch1: **1.23527**
- batch8: **1.21851**

At widths3072-5120 the high profile remains roughly in the `1.18-1.24x` range. Low-width threshold crossings are noisy/non-monotonic and must not be interpreted as stable large-width convergence.

Interpretation: the high rank fraction carries a persistent runtime tax even at width5120, while saving only ~14.6% full-core persistent bytes.

### C73 design decision

C73 confirms that Shared Basis runtime viability is **rank-dependent**:

1. lean is strongly runtime-viable at large width;
2. medium is plausible and approaches ~1.1x;
3. high retains a material ~20%+ runtime penalty at large width.

Therefore rank cannot be selected from quality/storage alone. Adaptive capacity / Auto-Partition must include runtime cost in the objective.

This also changes the priority for Condition. Condition currently uses width16/rank4 = rank fraction 1/4, but C63 skipped rank3. Because C73 shows that reducing rank fraction has material runtime value, the next quality question is whether rank3 can replace rank4 under the already accepted 12-seed exhaustive Condition protocol.

Gate C remains **NOT PASSED**. Do not production-integrate the high-rank policy before resolving whether Condition can use a smaller rank and before final representative-shape integration checks.

## 7. Auto-Partition / adaptive-capacity consequence

Main living document:

`fold/docs/shared-basis-auto-module-partition-report.md`

Current rule additions from C71-C73:

- runtime reuse is secondary to quality, but runtime cost is now a first-class rank-allocation cost;
- do not interpret high rank as free merely because persistent storage remains below Dense;
- when two ranks both satisfy quality, prefer the lower rank if the runtime/storage Pareto point is materially better;
- high-rank groups may justify Split / private capacity / alternate execution only after lower-rank quality is ruled out;
- C73 gives evidence that large-width lean/medium profiles are substantially more attractive than high rank.

The connector previously rejected one large living-spec rewrite; preserve these accepted conclusions here until that document can be safely refreshed without truncation.

## 8. Next experiment — C74

**Condition rank3 12-seed exhaustive viability.**

Tracked benchmark:

`fold/fold_lm/v05_benchmarks/gate_c_shared_basis_condition_rank3_12seed_exhaustive.py`

Benchmark creation commit:

`6ffe2793621281c4635e491f523c7345d77f337f`

Question: can Condition rank3 replace accepted rank4 under the same aligned native-training and exhaustive robustness protocol, motivated by C73's rank-dependent runtime tax?

Fixed setup:

- Condition only;
- rank3 candidate;
- accepted rank4 C69 as comparison;
- dense and factor lr0.01;
- 260 steps;
- batch32;
- train size256;
- seeds `20260911..20260922`;
- exhaustive held-out 32,512 per seed;
- Dense references must reproduce C69 exactly;
- rank3 direct score is compared both to Dense and accepted rank4 for each seed.

Primary outputs:

- rank3 routed-weight storage ratio vs rank4;
- rank3 - Dense exhaustive exact delta distribution;
- rank3 / Dense seed win counts and sign-test diagnostic;
- pooled paired Dense-only / rank3-only counts;
- rank3 - rank4 exhaustive exact delta distribution and seed win counts.

Interpretation:

- if rank3 is again mixed-sign and centered near Dense/rank4, adopt rank3 as the new Condition candidate and benchmark its runtime profile next;
- if Dense/rank4 consistently beat rank3, retain rank4 despite its runtime tax and investigate alternate execution / structure instead;
- no formal equivalence margin is declared inside C74, so final adoption remains evidence-based rather than a predeclared statistical equivalence test.

## 9. Handoff

On a new session:

1. read this ledger;
2. confirm branch/HEAD and protected hashes;
3. continue at C74;
4. keep one experiment per C number;
5. retry failures under the same number;
6. update this file after every accepted result or Gate decision change.
