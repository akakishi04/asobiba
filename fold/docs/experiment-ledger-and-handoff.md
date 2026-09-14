# FOLD Experiment Ledger and Handoff

> Current authoritative handoff for FOLD. Read this first in a new session. Detailed historical evidence remains in Gate decision documents and `experiment-ledger-addendum-*` files.

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
- C37 SHA256: `FD4A8DA897BDAEA9D103A252E30212C7FF842D23300D7C837333E146DEE51931`
- runtime fixture: `M:\asobiba\fold\runs\fixtures\v05-c-composition-20260921.pt`
- fixture SHA256: `A52F8209703149407580F7E2965B61B78653030EE992AF6D759865736741CA9E`

Every Cxx diagnostic must preserve both.

## 3. Experiment protocol

1. One experiment / verification question per C number.
2. Full output overwrites `M:\asobiba\fold\runs\chatgpt-last.log`.
3. User pastes the complete log back into ChatGPT.
4. ChatGPT judges the result.
5. Increment only after a valid completed run.
6. Failed/invalid retries keep the same C number.
7. A valid negative scientific result may complete the C number and advance.
8. `status=PASS` means valid execution, not automatically that a stage gate passed.
9. Invalid import/parser/hash/experiment-ID runs are not evidence.
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

PASSED previously: reference math/accounting/causality established.

### Gate B

PASSED previously: uncompressed shared-core + fixed/teacher-routed modules learn the registered tiny tasks reproducibly.

### Gate C

**PASSED on 2026-09-14, scoped to the registered V5 synthetic task/runtime regime.**

Formal decision:

`fold/docs/gate-c-decision-2026-09-14.md`

Accepted routed-weight family:

```text
W_module = W_base + A_module @ B_shared
```

Selected registered capacities:

```text
Condition   rank3
Composition rank2
Language    rank4
```

Production arithmetic policy:

```text
training  -> materialized
inference -> gemm_native
```

### Gate D

**PASSED on 2026-09-14, scoped to the registered V5 synthetic adaptive-routing/runtime regime.**

Formal decision:

`fold/docs/gate-d-decision-2026-09-14.md`

Lead production controller:

`fold_lm.v05.controller.ControlLaneActionRouter`

Supported design principle:

> Main working-state width and routing-control width should be independent capacity axes.

Registered synthetic configuration:

```text
control_width = 4
hidden_width  = 4
```

This is not a claim that width 4 is universally sufficient.

### Gate E

**NOT PASSED. Current active stage.**

V5-E is establishing when internal information is insufficient, when acquisition is justified, how acquisition results become authoritative evidence, and how failures terminate safely.

## 5. Model-lightness priority

Primary product objective:

> Minimize operational VRAM occupied by FOLD so other applications retain usable GPU-memory headroom.

Priority order:

1. incremental operational device VRAM consumed / remaining headroom;
2. peak allocated and peak reserved VRAM;
3. resident model VRAM;
4. latency / throughput practicality;
5. serialized artifact size as supporting evidence.

Do not use parameter count alone as the authoritative lightness metric.

## 6. Gate C accepted state

Lead production core:

`fold_lm.v05.modules.SharedBasisFixedRoutingCore`

Important accepted evidence:

- fine-grained codebook path is not the lead runtime because decode/gather overhead scaled badly;
- Shared Basis preserved registered tiny-task quality with task-specific rank selection;
- Condition rank3 prospectively passed non-inferiority against rank4;
- selected ranks preserve recurrence semantics through 64 updates in the registered tests;
- direct GEMM-native optimization caused small arithmetic-order drift, so training remains materialized;
- production inference uses GEMM-native arithmetic;
- serialized state stores canonical Shared-Basis parameters only;
- C83 established operational VRAM headroom as the primary lightness metric;
- width5120 Shared-Basis profiles gained roughly `0.20-0.33 GiB` free VRAM versus Dense in the accepted C83 measurements.

## 7. Gate D accepted state

### C84-C87 — adaptive-compute semantics

Accepted behavior includes:

```text
ANSWER / no-op
0-step / 1-step / 2-step compute
```

Composition variable-depth routing achieved:

- learned five-action routing accuracy `1.0` in the registered task;
- trajectory exact `1.0`;
- mean compute `1.0 step/event` versus fixed-max `2.0`;
- logical compute reduction `50%`.

### C88-C89 — runtime crossover

C88 was a valid negative result: at tiny width32, 50% lower logical compute was slower in wall/device time because sparse-dispatch overhead dominated.

C89 found practical router-inclusive sparse crossover at width3072 and strong benefit by width5120.

### C90-C96 — Control Lane

C91 was a valid negative result: compact hidden4 routing collapsed when controller representation remained coupled to full width3072/5120.

C92-C94 diagnosed representation/optimization rather than a simple training-duration explanation.

A fixed-width Control Lane decoupled controller capacity from core width.

C95 fresh-seed held-out validation:

- six width/seed conditions;
- action accuracy `1.0`;
- minimum class recall `1.0`;
- action flips `0`.

C96 production learned-action runtime/VRAM gate:

- held-out action accuracy minimum `1.0`;
- runtime action accuracy minimum `1.0`;
- outputs vs fixed-max allclose;
- logical compute reduction `50%`;
- learned/fixed device ratio maximum `0.649631`;
- learned/fixed wall ratio maximum `0.653782`;
- router/core persistent ratio maximum `1.3481e-06`;
- measured router incremental device-free-VRAM cost `0.0 GiB` at measurement resolution.

Important negative evidence remains binding:

- lower logical compute is not automatically lower latency;
- controller representation failure can masquerade as capacity failure;
- speed measurements are invalid if routing quality fails.

## 8. Current stage — V5-E

Roadmap action-space expansion eventually includes:

```text
PARTIAL_ANSWER
READ_MEMORY
RETRIEVE
OBSERVE
ASK_USER
STOP_UNRESOLVED
```

Current principles:

1. preserve Control-Lane separation;
2. model proposes actions, runtime owns permissions/outcomes/authoritative evidence mutation;
3. distinguish missing decision-critical information from irrelevant missing information;
4. do not reward universal acquisition or universal abstention;
5. do not silently invent missing evidence;
6. failed/untrusted acquisition must not be committed as evidence;
7. keep memory/retrieval/observation/user-question mechanism selection out until the abstract semantics are stable.

## 9. V5-E accepted evidence

### C97 — oracle information-sufficiency semantics

Action space:

```text
ANSWER
ACQUIRE
```

Boundary:

```text
missing hidden condition that can change target -> ACQUIRE
missing hidden condition irrelevant to target    -> ANSWER
```

Accepted exhaustive 32-row result:

- required acquisition recall `1.0`;
- unnecessary acquisition rate `0.0`;
- ambiguous direct-answer attempts `0`;
- direct-answerable accuracy `1.0`;
- irrelevant-missing direct accuracy `1.0`;
- post-policy final accuracy `1.0`.

### C98 — learned information-sufficiency routing

Production `ControlLaneActionRouter` learned the C97 boundary using visible evidence only.

Split:

```text
train bases      = 0,1,2
validation base  = 3 only (unseen)
fresh seeds      = 20261171,20261172,20261173
```

Accepted across all fresh seeds:

- validation action accuracy `1.0`;
- required ACQUIRE recall `1.0`;
- unnecessary ACQUIRE rate `0.0`;
- action flips `0`;
- post-policy final accuracy `1.0`;
- hidden/target input leakage false.

### C99 — learned acquire/reobserve/answer cycle

Fresh seeds:

```text
20261181
20261182
20261183
```

Authority path:

```text
model proposes ACQUIRE
-> runtime reveals/commits evidence
-> model re-observes updated evidence
-> model chooses ANSWER
```

Accepted result across all fresh seeds:

- required acquisition recall `1.0`;
- unnecessary acquisition rate `0.0`;
- required exactly-one acquisition rate `1.0`;
- answerable zero-acquisition rate `1.0`;
- post-acquisition ANSWER rate `1.0`;
- repeat acquisition count `0`;
- budget violation count `0`;
- ambiguous direct-answer attempts `0`;
- post-cycle final accuracy `1.0`.

C99 establishes the first learned successful acquisition closed loop in the registered synthetic scope. It does not cover failed, denied, or invalid acquisition outcomes.

## 10. Active experiment — C100

Experiment:

`C100-v5e-acquisition-failure-oracle`

Question:

> When a required acquisition does not yield trusted evidence, can the reference policy terminate safely without committing false evidence, retrying past budget, or inventing an answer?

Action space:

```text
ANSWER
ACQUIRE
STOP_UNRESOLVED
```

Runtime outcome classes:

```text
SUCCESS
UNAVAILABLE
DENIED
INVALID
```

Authority semantics:

```text
SUCCESS
-> runtime commits validated evidence
-> reobserve
-> ANSWER

UNAVAILABLE / DENIED / INVALID
-> runtime does not commit evidence
-> outcome is observed
-> STOP_UNRESOLVED
```

Budget:

```text
1 acquisition attempt for one missing critical fact
```

Prospective C100 gate:

- answerable rows acquire zero times `1.0`;
- SUCCESS post-acquisition ANSWER rate `1.0`;
- SUCCESS final accuracy `1.0`;
- SUCCESS evidence commit rate `1.0`;
- failure STOP_UNRESOLVED rate `1.0`;
- failure no-evidence-commit rate `1.0`;
- failure no-guessed-answer rate `1.0`;
- repeat acquisition count `0`;
- budget violation count `0`.

C100 is an oracle semantics baseline. Learned STOP_UNRESOLVED behavior comes later.

## 11. Hypothesis documents / future tracks

Shared-Basis auto-partition remains a separate future track. Current rule is quality-first and should include representation/optimization checks before structural split decisions.

Context/KV-replacement work remains a separate track. Do not mix it into active C100 unless explicitly pivoting.

## 12. Scope / non-claims

Gate C PASS is limited to registered V5 synthetic tasks and tested runtime shapes/environment.

Gate D PASS is limited to registered synthetic Condition/Composition routing, tested 0/1/2-step semantics, current action table, widths3072/5120, balanced batch216 runtime regime, current eager sparse execution, and tested Control-Lane configuration.

C97-C100 V5-E work is a tiny synthetic information-sufficiency/acquisition study. Do not claim broad uncertainty calibration, general epistemic self-knowledge, or real-world tool-selection capability.

Do not claim broad language quality, universal adaptive-compute superiority, universal control-width sufficiency, or general superiority over Transformers/LLMs from these diagnostics.
