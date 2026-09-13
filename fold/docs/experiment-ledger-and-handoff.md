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
- GPU: RTX 4070 Ti SUPER
- VS2022 Developer PowerShell 17.14.27

## 2. Protected artifacts

- C37 result: `M:\asobiba\fold\runs\chatgpt-last-result.json`
- SHA256: `FD4A8DA897BDAEA9D103A252E30212C7FF842D23300D7C837333E146DEE51931`
- runtime fixture: `M:\asobiba\fold\runs\fixtures\v05-c-composition-20260921.pt`
- SHA256: `A52F8209703149407580F7E2965B61B78653030EE992AF6D759865736741CA9E`

Diagnostics must preserve both.

## 3. Experiment protocol

1. One experiment / verification question per C number.
2. Full output overwrites `M:\asobiba\fold\runs\chatgpt-last.log`.
3. User pastes the complete log back into ChatGPT.
4. ChatGPT judges the result.
5. Increment only after a valid successful run.
6. Failed / invalid retries keep the same C number.
7. `status=PASS` means execution succeeded, not that Gate C passed.
8. Invalid import/parser/hash/experiment-ID runs are not evidence.
9. Prefer tracked benchmark files and short tracked runners over large pasted scripts.
10. Long runs print useful progress.
11. If a scientific acceptance margin is needed, define it before collecting the deciding data.

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

Current selected task points:

```text
Condition   rank3
Composition rank2
Language    rank4
```

Current training rule on accepted tiny tasks:

```text
factor_lr = common_lr
```

Current runtime formula:

```text
single projection [W_base; B_shared]
+
module coefficient addmm
```

Current integration state:

- direct fine-grained codebook execution is storage/reference only;
- one universal rank rule is rejected;
- rank/capacity is adaptive by functional need;
- runtime cost is a first-class rank-allocation cost;
- effective-weight materialization is reference/diagnostic only;
- Condition rank3 replaced rank4 only after prospective non-inferiority passed;
- final selected-rank GEMM-native recurrence equivalence passed in C77;
- production `modules.py` now contains an **opt-in** `SharedBasisFixedRoutingCore` candidate;
- default `HighPrecisionFixedRoutingCore` construction is unchanged;
- production integration is not accepted until C78 passes.

Do not claim fixture success proves broad language quality or that FOLD beats Transformers / existing LLMs.

## 5. Key accepted history

### C41-C57 — codebook path

Storage reduction existed, but direct codebook GPU decode/gather became the runtime blocker. C57 width1024 compact/dense = `12.88719`. Decision: stop primary optimization of direct fine-grained codebook execution.

### C58 — Shared Basis scale

Synthetic `rank=width/16` Shared/Dense latency:

- width256: 1.63577x
- width512: 1.29614x
- width1024: 1.19407x

Large width trends toward Dense.

### C59-C67 — quality / native factorized training

- post-hoc SVD alone is not an adequate task objective;
- Composition rank2 recovers and reproduces 3/3 seeds;
- Condition rank1 insufficient; rank4 was first robust tested point before rank3 was later examined;
- Language rank2 has capacity but unstable final checkpoint; rank4 stable;
- aligned rule `factor_lr = common_lr` succeeds across current task families.

### C68-C69 — Condition rank4 exhaustive robustness

C69, 12 seeds x 32,512 exhaustive held-out trajectories:

- rank4 wins 6 / Dense wins 6
- sign-test p = 1.0
- mean exact delta = -0.00025117894
- pooled net Direct advantage = -98 / 390,144

No systematic rank4 deficit was established.

### C70 — GEMM-native recurrence equivalence

Selected then: Condition4 / Composition2 / Language4, 3 seeds each.

- all validation scores equal
- all semantics equal
- all validation outputs allclose
- recurrence depths 1/2/4/8/16/32/64 allclose
- max validation abs gap = `5.245208740234375e-06`
- max recurrence abs gap = `7.62939453125e-05`

GEMM-native arithmetic is numerically safe in the tested float32 regime.

### C71-C72 — selected-shape runtime

C71 eager small-shape median Shared/Dense latency = `1.3765237679`; full-core persistent savings remained material.

C72 CUDA Graph median = `1.4057762261`; Graph did not remove the small-shape penalty. Extra arithmetic / shape efficiency / memory traffic dominate more than Python/launch overhead.

### C73 — extended full-core width/rank scaling

Widths 32..5120, slots20, batches1/8.

| profile | rank fraction | width5120 full-core ratio | b1 latency | b8 latency |
|---|---:|---:|---:|---:|
| lean | 1/16 | ~0.7136 | 1.05725 | 1.06427 |
| medium | 1/8 | ~0.7605 | 1.07800 | 1.11564 |
| high | 1/4 | ~0.8542 | 1.23527 | 1.21851 |

Rank fraction materially controls runtime/storage Pareto behavior.

### C74 — Condition rank3 retrospective exhaustive check

12 seeds x 32,512 held-out trajectories.

- rank3 routed ratio = 0.7109375
- rank4 routed ratio = 0.78125
- rank3 vs Dense mean = -0.00117391348
- rank3 wins 4 / Dense wins 8
- rank3 vs rank4 mean = -0.00092273454
- rank3 vs rank4 seed direction = 6 / 6

Because no equivalence margin had been predeclared, rank3 was not adopted from C74 alone.

### C75 — Condition rank3/rank4 runtime bridge

At width5120:

- rank3-equivalent 3/16 full-core ratio vs Dense = 0.80734184
- rank4-equivalent 1/4 full-core ratio vs Dense = 0.85420463
- rank3 / rank4 persistent bytes = 0.94513868 (~5.5% smaller)
- batch1 Shared/Dense: rank3 1.13681493 vs rank4 1.20286584
- batch8 Shared/Dense: rank3 1.17189873 vs rank4 1.20927834

Rank3 offered a real but moderate ~3-5.5% endpoint runtime benefit and ~5.5% full-core byte benefit.

## 6. C76 — prospective independent-seed Condition rank3 non-inferiority

Accepted run commit: `8fd6c3a600d7da91eb1c15e9f768c30988b8b2d4`.

Decision rule fixed before new data:

- seeds `20260923..20260946` (24), disjoint from C74;
- primary delta = rank3 exhaustive exact - rank4 exhaustive exact;
- margin = `-0.002` absolute accuracy;
- bootstrap unit = seed;
- 100,000 deterministic paired bootstrap resamples;
- one-sided 95% lower bound;
- pass iff lower bound > -0.002.

Accepted result:

- mean delta = **-0.0000794604421**
- median = **-0.000199943781**
- bootstrap lower 95% = **-0.000512627388**
- non-inferiority gate = **PASS**
- rank3 wins 10 / rank4 wins 13 / tie 1
- sign-test p = `0.6776394844`
- pooled net rank3 advantage = **-62** / 780,288 held-out trajectories

Decision: Condition rank3 became the selected Condition capacity point on the current synthetic-domain evidence.

## 7. C77 — final selected-rank recurrence equivalence refresh

Accepted run commit: `79a2f1c4f86a6c937010fbe1a94d876fa16398a7`.

Experiment ID:

`C77-shared-basis-final-selected-rank-recurrence-equivalence`

Selected ranks:

```text
Condition   rank3
Composition rank2
Language    rank4
```

Fresh seeds:

```text
20261001, 20261002, 20261003
```

Accepted results across 3 tasks x 3 seeds:

- run_count = 9
- seeds disjoint from C76 = true
- validation max abs gap max = **3.933906555175781e-06**
- recurrence max abs gap max = **9.72747802734375e-05**
- recurrence max relative-L2 gap max = **2.7345954560493825e-06**
- all validation scores equal = true
- all validation semantics equal = true
- all validation outputs allclose = true
- all recurrence depths 1/2/4/8/16/32/64 allclose = true
- all runtime formula equivalent = true
- protected C37 result preserved
- runtime fixture preserved
- tracked repository clean

### C77 decision

The final selected rank set is numerically safe for the tested materialized-reference vs GEMM-native execution comparison through 64 recurrent updates.

C77 closes the pre-production inference-form equivalence refresh. It does **not** prove broad language quality and does not pass Gate C by itself.

## 8. Auto-Partition / adaptive-capacity consequence

See:

- `fold/docs/shared-basis-auto-module-partition-report.md`
- `fold/docs/shared-basis-auto-module-partition-addendum-c73-c76.md`

Current rules:

1. diagnose co-adaptation and seed direction before increasing rank;
2. runtime cost is a first-class capacity cost;
3. when considering a lower rank, estimate operational benefit first;
4. if benefit is material, fix a prospective quality tolerance before deciding data;
5. adopt lower rank only if that gate passes;
6. after selected-rank structural change, refresh execution/recurrence equivalence;
7. among capacities passing the same quality contract, prefer the lower-rank Pareto point unless another measured constraint dominates.

## 9. Production integration state

After C77 acceptance, an opt-in production candidate was added to:

`fold/fold_lm/v05/modules.py`

Class:

`SharedBasisFixedRoutingCore`

Properties:

- existing `HighPrecisionFixedRoutingCore` remains the default and is not replaced;
- constructor explicitly opts in from an existing high-precision routed core plus rank;
- routed weights are initialized with mean + truncated SVD;
- production forward stores concatenated `[W_base; B_shared]` projections plus module coefficients;
- production forward uses GEMM-native projection + `addmm` and does not materialize effective routed weights;
- effective weights can be materialized only through diagnostic tooling;
- class is trainable and supports state_dict save/load;
- production module has no dependency on benchmark modules.

Important remaining gap:

C65-C67 trained the factorized Shared-Basis family using materialized effective weights during forward, while C70/C77 verified GEMM-native inference after that training. Before accepting the production class for training/runtime use, direct training in the production GEMM-native parameterization must be compared against the accepted materialized training path.

## 10. Active experiment — C78

**Opt-in production Shared-Basis direct-training integration gate.**

Tracked benchmark:

`fold/fold_lm/v05_benchmarks/gate_c_shared_basis_production_optin_integration.py`

Tracked unit coverage:

`fold/tests_lm/test_v05_shared_basis_core.py`

Tracked runner:

`fold/scripts/run_c78.ps1`

Scientific/engineering question:

> Starting from the same untrained dense initialization and using the same selected ranks, data, batch order, optimizer family, and aligned learning rate, does the production GEMM-native `SharedBasisFixedRoutingCore` preserve the accepted materialized Shared-Basis training semantics and runtime algebra?

C78 compares:

1. benchmark materialized `JointTrainSharedBasisCore`;
2. production opt-in `SharedBasisFixedRoutingCore`.

Tasks/ranks:

```text
Condition   rank3
Composition rank2
Language    rank4
```

Fresh seeds:

```text
20261011, 20261012, 20261013
```

C78 verification includes:

- compileall of `fold_lm/v05`;
- focused production-core unit tests;
- all `test_v05_*.py` regressions;
- initial effective-weight equivalence;
- autograd gradient equivalence;
- full accepted training schedules with identical batch sequences;
- final validation score equality;
- final semantic equality;
- final validation tensor allclose;
- production native-vs-materialized recurrence through 64 updates;
- exact state_dict round-trip;
- protected artifact preservation;
- tracked repository cleanliness.

Primary scientific flag:

```text
production_integration_gate_passed
```

C78 may be accepted only if all integration flags pass. A benchmark `status=PASS` alone means execution completed and is not sufficient.

If C78 passes, benchmark-only Shared-Basis runtime classes are no longer required as the authoritative implementation path for subsequent experiments. The next step should benchmark the actual production class at representative large shapes / resident memory before any Gate C pass decision or default-path switch.

Gate C remains **NOT PASSED**.

## 11. Handoff

On a new session:

1. read this ledger;
2. confirm branch/HEAD and protected hashes;
3. continue at C78;
4. use `fold/scripts/run_c78.ps1` rather than a pasted multi-block PowerShell script;
5. keep one experiment per C number;
6. retry C78 failures under C78;
7. do not switch the default Dense core until production integration and representative production runtime gates are accepted.
