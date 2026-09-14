# FOLD Experiment Ledger and Handoff

> Current authoritative handoff. Detailed history remains in Gate decisions and `experiment-ledger-addendum-*` files.

## 1. Environment / protected artifacts

- Repository: `akakishi04/asobiba`
- Branch: `feat/sft-target-loss`
- Local repo: `M:\asobiba\fold`
- Python: `M:\asobiba\fold\.venv-py31315\Scripts\python.exe`
- Python 3.13.15 / PyTorch 2.10.0+cu130 / CUDA 13.0
- GPU: RTX 4070 Ti SUPER

Protected:

- `runs/chatgpt-last-result.json`
- SHA256 `FD4A8DA897BDAEA9D103A252E30212C7FF842D23300D7C837333E146DEE51931`
- `runs/fixtures/v05-c-composition-20260921.pt`
- SHA256 `A52F8209703149407580F7E2965B61B78653030EE992AF6D759865736741CA9E`

## 2. Experiment protocol

1. One scientific question per C number.
2. Full output overwrites `runs/chatgpt-last.log`.
3. User pastes the complete log.
4. Judge execution validity separately from scientific gate result.
5. Invalid retries keep the same C number.
6. Valid negative results may complete the C number.
7. Predeclare deciding thresholds before collecting deciding data.
8. Preserve both protected artifacts and require tracked tree clean.

## 3. Gate status

- Gate A: PASSED.
- Gate B: PASSED.
- Gate C: PASSED, scoped. See `gate-c-decision-2026-09-14.md`.
- Gate D: PASSED, scoped. See `gate-d-decision-2026-09-14.md`.
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

Primary product objective remains operational VRAM headroom.

## 4. Binding Gate C/D evidence

- Fine-grained codebook execution was rejected as lead runtime because decode/gather overhead scaled badly.
- Shared Basis preserved registered task quality and reduced operational VRAM.
- C83 width5120 gained roughly `0.20-0.33 GiB` free VRAM versus Dense in tested profiles.
- C88 showed lower logical compute is not automatically lower latency.
- C91 showed compact routing can fail when controller representation remains coupled to full core width.
- C92-C95 established the fixed Control Lane alternative.
- C96 preserved routing/output quality with 50% logical compute reduction; maximum learned/fixed ratios were `0.649631` device and `0.653782` wall in the registered large-width regime.

## 5. V5-E design rules

Current action family:

```text
ANSWER
READ_MEMORY
RETRIEVE
OBSERVE
ASK_USER
STOP_UNRESOLVED
```

Authority rule:

```text
model/router -> proposes action
runtime      -> owns availability, permission, acquisition outcome, validation, eligibility mutation, and authoritative evidence mutation
```

Do not guess decision-critical missing facts. Do not commit failed/untrusted acquisition as evidence. Do not universally acquire or universally abstain. Do not ask the user while a lower-burden equally capable self-service mechanism remains available under the current synthetic cost contract.

## 6. V5-E accepted evidence

### C97-C99 — information sufficiency and successful acquisition

- Oracle information-sufficiency boundary established.
- Production Control Lane learned `ANSWER / ACQUIRE` on unseen base=3 with no hidden/target leakage.
- Learned successful closed loop established: `ACQUIRE -> runtime commit -> reobserve -> ANSWER`.
- Required cases acquired exactly once; answerable cases acquired zero times; final accuracy `1.0`.

### C100-C102 — acquisition outcome handling

Runtime outcome classes:

```text
SUCCESS
UNAVAILABLE
DENIED
INVALID
```

Accepted semantics:

```text
SUCCESS -> validated evidence commit -> ANSWER
failure -> no evidence commit -> STOP_UNRESOLVED
```

C101 learned the three-action snapshot policy on unseen base=3 with action accuracy `1.0`, failure STOP rate `1.0`, and zero guessed answers.

C102 passed the actual learned end-to-end trajectory across all fresh seeds:

- required ACQUIRE recall `1.0`;
- answerable ANSWER rate `1.0`;
- unnecessary acquisition `0.0`;
- SUCCESS commit / ANSWER / final accuracy `1.0`;
- failure STOP / no-commit / no-guess `1.0`;
- premature STOP `0`;
- repeat acquisition `0`;
- budget violation `0`.

### C103 — mechanism-selection oracle

Exhaustive 512 examples / 16 eligibility masks passed.

Synthetic equal-capability burden order:

```text
READ_MEMORY < RETRIEVE < OBSERVE < ASK_USER
```

Accepted C103 metrics were all `1.0` with zero violations, including minimum-burden selection, STOP when no mechanism is eligible, ASK_USER avoidance when self-service is eligible, and hidden-counterfactual action invariance.

### C104 — learned six-action mechanism selector

Production `ControlLaneActionRouter`, train bases `0,1,2`, unseen validation base `3`, fresh seeds `20261211..13`.

Configuration:

```text
control width  = 4
hidden width   = 8
training steps = 640
```

Accepted across all three seeds:

- action accuracy `1.0`;
- minimum six-class recall `1.0`;
- action flips `0`;
- answerable ANSWER `1.0`;
- no direct answer on critical missing evidence `1.0`;
- minimum-burden eligible mechanism selection `1.0`;
- no-eligible STOP_UNRESOLVED `1.0`;
- ASK_USER avoided while self-service was eligible `1.0`;
- ineligible mechanism predictions `0`;
- hidden-counterfactual action invariance `1.0`;
- hidden/target leakage false.

C104 is snapshot mechanism selection only. It does not yet establish mechanism execution or fallback.

## 7. Active experiment — C105

Experiment:

`C105-v5e-learned-acquisition-mechanism-closed-loop`

Question:

> Can the learned six-action selector execute runtime-owned mechanism outcomes and fall back to the next least-burden eligible mechanism after failure, while committing evidence only on SUCCESS and stopping unresolved only after all eligible fallbacks are exhausted?

Prospective configuration:

```text
fresh seeds        = 20261221,20261222,20261223
train bases        = 0,1,2
validation base    = 3 only
acquisition budget = 4
burden order       = READ_MEMORY < RETRIEVE < OBSERVE < ASK_USER
```

Runtime contract:

```text
SUCCESS
-> commit validated evidence
-> reobserve
-> ANSWER

failure
-> no evidence commit
-> failed mechanism becomes ineligible
-> reobserve updated eligibility
-> choose next least-burden eligible mechanism

no eligible mechanism remains
-> STOP_UNRESOLVED
```

C105 evaluates success at every eligible mechanism position after its failure prefix, plus all-fail exhaustion and answerable zero-acquisition controls.

Every fresh seed must satisfy:

```text
answerable ANSWER rate                         = 1.0
answerable zero-acquisition rate               = 1.0
required scenario pass rate                    = 1.0
per-decision minimum-burden rate               = 1.0
eventual-success ANSWER rate                   = 1.0
eventual-success final accuracy                = 1.0
all-fail STOP_UNRESOLVED rate                  = 1.0
failed-attempt no-evidence-commit rate         = 1.0
ineligible mechanism count                     = 0
repeat failed mechanism count                  = 0
budget violation count                         = 0
ASK_USER before self-service exhaustion count  = 0
hidden counterfactual action-trace invariance  = 1.0
```

Strict rule: STOP_UNRESOLVED is a failure while any eligible fallback remains.

## 8. Separate tracks / non-claims

- Shared-Basis auto-partition remains separate.
- Context/KV-replacement remains separate.
- Gate C/D and C97-C105 evidence is synthetic and scoped.
- Do not claim broad language quality, general epistemic self-knowledge, real-world tool selection, universal control-width sufficiency, or general superiority over Transformer/LLM systems.
