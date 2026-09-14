# FOLD Experiment Ledger and Handoff

> Current authoritative handoff for FOLD. Read this first in a new session. Update after every accepted Cxx result, retry decision, or Gate decision change.

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
7. `status=PASS` means the experiment executed correctly, not automatically that a stage gate passed.
8. Invalid import/parser/hash/experiment-ID runs are not evidence.
9. Prefer tracked benchmark files and short tracked runners over large pasted scripts.
10. If a scientific acceptance margin is needed, define it before collecting deciding data.

PC clipboard:

```powershell
$log = "M:\asobiba\fold\runs\chatgpt-last.log"
Get-Content -LiteralPath $log -Raw -Encoding UTF8 -ErrorAction Stop | Set-Clipboard
```

Smartphone / Termius OSC52:

```powershell
$log = "M:\asobiba\fold\runs\chatgpt-last.log"
$text = Get-Content -LiteralPath $log -Raw -Encoding UTF8 -ErrorAction Stop
$b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($text))
[Console]::Write("$([char]27)]52;c;$b64$([char]7)")
```

## 4. Gate status

### Gate A

Passed previously: reference math/accounting/causality established.

### Gate B

Passed previously: uncompressed shared-core + fixed/teacher-routed modules learn the registered tiny tasks reproducibly.

### Gate C

**PASSED on 2026-09-14, scoped to the registered V5 synthetic task/runtime regime.**

Formal decision:

`fold/docs/gate-c-decision-2026-09-14.md`

Accepted lead routed-weight family:

```text
W_module = W_base + A_module @ B_shared
```

Selected tiny-task capacities:

```text
Condition   rank3
Composition rank2
Language    rank4
```

Accepted production execution policy:

```text
training  -> materialized arithmetic
inference -> GEMM-native arithmetic
```

### Gate D

**PASSED on 2026-09-14, scoped to the registered V5 synthetic adaptive-routing/runtime regime.**

Formal decision:

`fold/docs/gate-d-decision-2026-09-14.md`

Accepted production controller candidate:

```text
ControlLaneActionRouter
```

Current registered synthetic configuration:

```text
control_width = 4
hidden_width  = 4
action space  = ANSWER / ADD1 / ADD2 / SUB1 / SUB2
```

Supported design principle:

> Main working-state width and routing-control width should be independent capacity axes.

This is not a claim that control width 4 or hidden width 4 is universally sufficient.

## 5. Model-lightness priority

Primary product objective:

> Minimize operational VRAM occupied by FOLD so other applications retain usable GPU-memory headroom.

Priority order:

1. incremental operational device VRAM consumed / remaining headroom;
2. peak allocated and peak reserved VRAM;
3. resident model VRAM;
4. latency / throughput practicality;
5. serialized artifact size as supporting deployment/storage evidence.

Do not use parameter count alone as the authoritative model-weight metric.

## 6. Gate C accepted evidence summary

### C41-C57 — codebook path rejected as lead runtime

Direct fine-grained codebook execution reduced storage but decode/gather overhead scaled badly. C57 width1024 compact/dense latency reached `12.88719x`. Codebook remains a storage/reference baseline, not the lead execution family.

### C58-C67 — Shared Basis established

Task-aware/native factorized training recovered registered task quality. Aligned training rule:

```text
factor_lr = common_lr
```

### C68-C76 — Condition robustness and rank3 selection

- rank4 12-seed exhaustive: 6 wins / 6 losses vs Dense, sign-test p `1.0`, mean delta near zero;
- C75 established a material operational benefit for rank3;
- C76 prospectively accepted rank3 with 24 fresh seeds and non-inferiority margin `-0.002`;
- one-sided bootstrap lower bound `-0.000512627388` > required `-0.002`.

### C77 — selected-rank recurrence equivalence

Condition3 / Composition2 / Language4:

- validation semantics/scores equal;
- tensors allclose;
- recurrence depths through 64 updates allclose.

### C78-C80 — production arithmetic policy

C78 was a valid negative direct-native-training result. C79 localized the drift to arithmetic order. C80 accepted:

```text
training  -> materialized
inference -> gemm_native
```

### C81-C83 — production runtime/storage/VRAM

C81 established practical large-shape production runtime/resident behavior.

C82 established serialized Shared-Basis artifacts without stored materialized routed-weight banks.

C83 made operational VRAM headroom the authoritative model-lightness metric. At width5120, tested profiles gained roughly `0.20-0.33 GiB` free VRAM versus Dense, with lower peak allocated/reserved memory at every point.

## 7. Production state after Gate C

`fold_lm.v05.modules.SharedBasisFixedRoutingCore` is the accepted V5-C candidate implementation.

Properties:

- Dense `HighPrecisionFixedRoutingCore` remains available;
- Shared Basis is explicit/opt-in;
- execution mode is explicit;
- train with `materialized` arithmetic;
- infer with `gemm_native` arithmetic;
- state_dict stores canonical Shared-Basis parameters only.

## 8. Gate D accepted evidence summary

### C84-C85 — zero-compute ANSWER semantics and learned two-action routing

Condition HOLD can be represented as `ANSWER/no-op`; UPDATE as `COMPUTE(update,1)`.

- approximately half the events require no core compute;
- no quality loss;
- supervised router reproduced the oracle policy with action/class accuracy `1.0`.

### C86-C87 — learned variable-depth routing

Composition difficulty axis:

```text
operand 0 -> 0 steps
operand 1 -> 1 step
operand 2 -> 2 steps
```

C86 oracle and C87 learned routing both achieved:

- exact trajectory quality `1.0`;
- mean compute `1.0 step/event` vs fixed `2.0`;
- logical compute reduction `50%`.

C87 five-action learned router had action accuracy and minimum class recall `1.0`.

### C88-C89 — runtime reality and crossover

C88 valid negative result at width32:

- 50% logical compute reduction did **not** produce a speedup;
- eager sparse path was slower because routing/gather/index overhead dominated.

C89 width sweep found a router-inclusive runtime crossover at width3072. At width5120, router-cost-plus-sparse diagnosis reached about `0.61x` device and `0.64x` wall latency vs fixed-max.

### C90-C95 — compact router failure, diagnosis, and Control Lane

C90 selected hidden4 as the smallest tiny-task quality-passing router point.

C91 valid negative result: hidden4 full-width router collapsed at width3072/5120. Its apparent speedups were rejected because routing quality failed.

C92-C94 showed:

- the problem was not explained by training duration alone;
- coupling controller input dimension to full core width caused severe optimization difficulty;
- a fixed Control Lane largely removed width dependence;
- by 480 steps, reused diagnostic seeds converged identically across width3072/5120.

C95 prospective fresh-seed held-out validation:

- six width/seed conditions;
- held-out action accuracy `1.0` in all conditions;
- minimum class recall `1.0` in all conditions;
- action flips `0`;
- Control-Lane diagnostic router persistent bytes `436`.

### C96 — production Control Lane learned-action runtime/VRAM gate

Production `ControlLaneActionRouter`, widths 3072/5120, three fresh seeds each.

All six conditions passed all predeclared gates.

Quality/routing:

- held-out action accuracy minimum `1.0`;
- held-out minimum class recall `1.0`;
- runtime action accuracy minimum `1.0`;
- runtime minimum class recall `1.0`;
- outputs vs fixed-max allclose.

Adaptive compute:

- logical compute reduction `50%` in every condition.

Runtime:

- learned/fixed device ratio mean `0.581919`;
- device ratio maximum `0.649631`;
- learned/fixed wall ratio mean `0.587959`;
- wall ratio maximum `0.653782`.

Controller footprint:

- router/core persistent ratio maximum `1.3481e-06`;
- measured router incremental device-free-VRAM cost `0.0 GiB` at measurement resolution.

C96 therefore establishes a production learned-action adaptive path that is both correct and materially faster in the registered large-width regime.

## 9. Production state after Gate D

Lead adaptive-routing candidate:

`fold_lm.v05.controller.ControlLaneActionRouter`

Current design rule:

```text
large semantic / working state
+
small explicit control state
+
router capacity independent of core width
+
sparse execution of selected compute
```

Keep `SupervisedActionRouter` as a comparison/backward-compatible full-width baseline.

Important negative evidence remains binding:

- tiny widths can lose to sparse-dispatch overhead;
- lower logical compute is not automatically lower latency;
- controller representation failures can masquerade as controller capacity failures;
- speed measurements are invalid if routing quality fails.

## 10. Current stage — V5-E

V5-D is closed under the formal scoped decision.

Proceed to **V5-E — information acquisition / knowing when internal compute is insufficient**.

Roadmap action-space expansion candidates:

```text
PARTIAL_ANSWER
READ_MEMORY
RETRIEVE
OBSERVE
ASK_USER
STOP_UNRESOLVED
```

Initial V5-E principles:

1. preserve the Control-Lane separation rather than routing directly from the full working-state width;
2. separate model action proposal from runtime permission/authority;
3. start with a tiny synthetic information-sufficiency task;
4. compare internal-compute-only vs acquire/clarify actions;
5. do not integrate FOLD-R memory or Vision into the first V5-E experiment;
6. do not reward universal abstention or universal acquisition.

On-policy recovery after self-induced routing errors remains deferred robustness work; it was not a listed Gate-D acceptance bullet and is not claimed complete.

## 11. V5-E accepted evidence summary

### C97 — oracle information-sufficiency semantics

Registered minimal action space:

```text
ANSWER
ACQUIRE
```

Oracle boundary:

```text
missing hidden condition that can change target -> ACQUIRE
missing hidden condition irrelevant to target    -> ANSWER
```

Accepted exhaustive 32-row result:

- critical missing counterfactual pairs: `4`;
- irrelevant missing counterfactual pairs: `4`;
- required acquisition recall: `1.0`;
- unnecessary acquisition rate: `0.0`;
- ambiguous direct-answer attempts: `0`;
- direct-answerable accuracy: `1.0`;
- irrelevant-missing direct accuracy: `1.0`;
- post-policy final accuracy: `1.0`;
- direct-answer coverage: `0.75`.

C97 is an oracle baseline only. `ACQUIRE` remains abstract and no memory/retrieval/tool/Vision mechanism is selected yet.

### C98 — supervised information-sufficiency routing

Production `ControlLaneActionRouter` learned the C97 `ANSWER / ACQUIRE` boundary from visible evidence only.

Fixed split:

```text
train bases      = 0,1,2
validation base  = 3 only (unseen)
fresh seeds      = 20261171,20261172,20261173
```

The router received only:

```text
base
dependency
evidence_present
observed_hidden
```

Missing-evidence hidden=0/1 counterfactuals were bit-identical at router input; hidden truth, target answer, and oracle action were not inputs.

Accepted result across all three fresh seeds:

- validation action accuracy: `1.0`;
- required ACQUIRE recall: `1.0`;
- unnecessary ACQUIRE rate: `0.0`;
- action flips: `0`;
- post-policy final accuracy: `1.0`.

C98 establishes learned information-sufficiency routing on this tiny synthetic task. It does not yet establish acquisition execution because `ACQUIRE` was treated as an abstract successful operation.

## 12. Immediate next work — C99

C99 is the active experiment.

Question:

> Can the learned policy close an actual `ACQUIRE -> runtime evidence update -> reobserve -> ANSWER` loop while preserving the model/runtime authority boundary?

Prospective conditions:

```text
fresh seeds        = 20261181,20261182,20261183
train bases        = 0,1,2
validation base    = 3 only (unseen)
action space       = ANSWER / ACQUIRE
acquisition budget = 1
```

Authority rule:

```text
model/router -> proposes ANSWER or ACQUIRE
runtime      -> alone mutates/reveals evidence state
model/router -> re-observes the committed visible evidence
```

C99 requires every fresh seed to satisfy:

```text
required acquisition recall           = 1.0
unnecessary acquisition rate           = 0.0
required exactly-one acquisition rate  = 1.0
answerable zero-acquisition rate        = 1.0
post-acquisition ANSWER rate            = 1.0
repeat acquisition count                = 0
budget violation count                  = 0
ambiguous direct-answer attempts        = 0
post-cycle final accuracy               = 1.0
```

Keep C99 to one deterministic abstract acquisition mechanism. Do not add memory/retrieval/observation/user-question mechanism selection or acquisition failure yet.

## 13. Scope / non-claims

Gate C PASS is limited to the registered V5 synthetic tasks, current selected ranks/fractions, float32 execution, current Windows/CUDA/PyTorch environment, and tested two-module routed-core shapes.

Gate D PASS is limited to the registered synthetic Condition/Composition routing tasks, tested 0/1/2-step semantics, current five-action routing table, widths 3072/5120, balanced batch216 runtime regime, current eager sparse execution, and the tested Control-Lane configuration.

C97-C99 V5-E work is a tiny synthetic information-sufficiency/acquisition study. Do not claim broad uncertainty calibration, general epistemic self-knowledge, or real-world tool-selection capability from it.

Do not claim broad language quality, universal adaptive-compute superiority, universal control-width sufficiency, or general superiority over Transformers/LLMs from these diagnostics.
