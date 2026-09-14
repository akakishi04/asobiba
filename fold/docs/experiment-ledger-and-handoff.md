# FOLD Experiment Ledger and Handoff

> Current authoritative handoff. Detailed history remains in Gate decisions and `experiment-ledger-addendum-*` files.

## 1. Environment

- Repository: `akakishi04/asobiba`
- FOLD path: `fold/`
- Branch: `feat/sft-target-loss`
- Local repo: `M:\asobiba\fold`
- Python: `M:\asobiba\fold\.venv-py31315\Scripts\python.exe`
- Python 3.13.15
- PyTorch `2.10.0+cu130`
- CUDA 13.0
- GPU: RTX 4070 Ti SUPER

Protected artifacts:

- C37: `M:\asobiba\fold\runs\chatgpt-last-result.json`
- SHA256: `FD4A8DA897BDAEA9D103A252E30212C7FF842D23300D7C837333E146DEE51931`
- fixture: `M:\asobiba\fold\runs\fixtures\v05-c-composition-20260921.pt`
- SHA256: `A52F8209703149407580F7E2965B61B78653030EE992AF6D759865736741CA9E`

## 2. Experiment protocol

1. One scientific question per C number.
2. Full output overwrites `runs/chatgpt-last.log`.
3. User pastes the complete log.
4. Judge execution validity separately from scientific gate result.
5. Invalid retries keep the same C number.
6. Valid negative results may complete the C number.
7. Predeclare deciding margins before collecting deciding data.
8. Preserve C37 and the fixture.

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

## 3. Gate status

- Gate A: PASSED.
- Gate B: PASSED.
- Gate C: PASSED, scoped. Formal decision: `fold/docs/gate-c-decision-2026-09-14.md`.
- Gate D: PASSED, scoped. Formal decision: `fold/docs/gate-d-decision-2026-09-14.md`.
- Gate E: NOT PASSED. Active stage.

Gate C lead:

```text
W_module = W_base + A_module @ B_shared
training  -> materialized
inference -> gemm_native
```

Selected registered capacities:

```text
Condition rank3
Composition rank2
Language rank4
```

Gate D lead controller:

`fold_lm.v05.controller.ControlLaneActionRouter`

Supported principle:

> Main working-state width and routing-control width are independent capacity axes.

## 4. Product priority

Primary objective: preserve operational VRAM headroom for other applications.

Priority:

1. incremental device VRAM / remaining headroom;
2. peak allocated/reserved VRAM;
3. resident model VRAM;
4. latency/throughput practicality;
5. serialized artifact size.

## 5. Binding Gate C/D evidence

- Fine-grained codebook runtime was rejected as lead due decode/gather overhead.
- Shared Basis preserved registered task quality with materially lower VRAM.
- C83 width5120 gained roughly `0.20-0.33 GiB` free VRAM versus Dense in tested profiles.
- C88 showed 50% lower logical compute can still be slower at tiny width.
- C91 showed compact routing can fail when controller representation remains coupled to full core width.
- C92-C95 established the fixed Control Lane alternative.
- C96 preserved routing/output quality while reducing logical compute by 50% and reaching maximum learned/fixed ratios `0.649631` device and `0.653782` wall in the registered large-width regime.

Do not treat logical savings as runtime savings unless measured with correct routing.

## 6. V5-E design rules

Current abstract action family:

```text
ANSWER
ACQUIRE
STOP_UNRESOLVED
```

Future expansion may include:

```text
PARTIAL_ANSWER
READ_MEMORY
RETRIEVE
OBSERVE
ASK_USER
```

Authority rules:

```text
model/router -> proposes actions
runtime      -> owns permissions, acquisition outcome, validation, and authoritative evidence mutation
```

Never commit failed/untrusted acquisition as evidence. Do not guess missing decision-critical facts. Do not universally acquire or universally abstain.

## 7. V5-E accepted evidence

### C97 — oracle information sufficiency

- required acquisition recall `1.0`;
- unnecessary acquisition rate `0.0`;
- direct-answerable and final accuracy `1.0`.

### C98 — learned ANSWER/ACQUIRE policy

Production Control Lane, train bases `0,1,2`, unseen validation base `3`, three fresh seeds:

- action accuracy `1.0`;
- required ACQUIRE recall `1.0`;
- unnecessary ACQUIRE `0.0`;
- action flips `0`;
- hidden/target leakage false.

### C99 — learned successful acquisition loop

```text
ACQUIRE
-> runtime commits evidence
-> reobserve
-> ANSWER
```

Across all fresh seeds:

- required exactly-one acquisition `1.0`;
- answerable zero acquisition `1.0`;
- post-acquisition ANSWER `1.0`;
- repeat acquisition `0`;
- budget violations `0`;
- final accuracy `1.0`.

### C100 — acquisition failure oracle

Runtime outcomes:

```text
SUCCESS
UNAVAILABLE
DENIED
INVALID
```

Accepted semantics:

```text
SUCCESS
-> commit validated evidence
-> ANSWER

UNAVAILABLE / DENIED / INVALID
-> no evidence commit
-> STOP_UNRESOLVED
```

Accepted result:

- answerable zero-acquisition rate `1.0`;
- SUCCESS answer/final-accuracy/evidence-commit rates `1.0`;
- failure STOP_UNRESOLVED/no-commit/no-guess rates `1.0`;
- repeat acquisition `0`;
- budget violations `0`.

C100 is oracle evidence, not learned failure handling.

## 8. Active experiment — C101

Experiment:

`C101-v5e-supervised-acquisition-outcome-policy`

Question:

> Can production `ControlLaneActionRouter` learn `ANSWER / ACQUIRE / STOP_UNRESOLVED` from visible evidence plus a runtime-owned outcome token and generalize to unseen base=3 without hidden/target leakage?

Fixed prospective conditions:

```text
fresh seeds      = 20261191,20261192,20261193
train bases      = 0,1,2
validation base  = 3 only
control width    = 4
hidden width     = 4
training steps   = 480
```

Control Lane:

```text
base
dependency
evidence_present
observed_hidden
```

Outcome token:

```text
NOT_ATTEMPTED
SUCCESS
UNAVAILABLE
DENIED
INVALID
```

When evidence is absent, hidden=0/1 counterfactuals must be bit-identical to the router. Target and oracle action are never router inputs.

Every fresh seed must satisfy:

```text
action accuracy                    = 1.0
initial required ACQUIRE recall     = 1.0
initial unnecessary ACQUIRE rate    = 0.0
SUCCESS post-acquisition ANSWER     = 1.0
failure STOP_UNRESOLVED rate        = 1.0
action flips                       = 0
failure guessed-answer count       = 0
```

## 9. Separate hypothesis tracks

- Shared-Basis auto-partition remains separate. Check representation/optimization before capacity/split decisions.
- Context/KV-replacement remains separate. Do not mix it into active V5-E unless explicitly pivoting.

## 10. Scope / non-claims

Gate C/D and C97-C101 evidence is synthetic and scoped. Do not claim broad language quality, general epistemic self-knowledge, real-world tool selection, universal control-width sufficiency, or general superiority over Transformer/LLM systems.
