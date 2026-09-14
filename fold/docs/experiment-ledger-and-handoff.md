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

Current action family is expanding from:

```text
ANSWER / ACQUIRE / STOP_UNRESOLVED
```

toward:

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
runtime      -> owns availability, permission, acquisition outcome, validation, and authoritative evidence mutation
```

Do not guess decision-critical missing facts. Do not commit failed/untrusted acquisition as evidence. Do not universally acquire or universally abstain.

## 6. V5-E accepted evidence

### C97-C99

- Oracle information-sufficiency boundary established.
- Production Control Lane learned `ANSWER / ACQUIRE` on unseen base=3 with no hidden/target leakage.
- Learned successful closed loop established: `ACQUIRE -> runtime commit -> reobserve -> ANSWER`.
- Required cases acquired exactly once; answerable cases acquired zero times; final accuracy `1.0`.

### C100-C102

Failure outcomes registered:

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

C102 then passed the actual learned end-to-end trajectory for all three fresh seeds:

- required ACQUIRE recall `1.0`;
- answerable ANSWER rate `1.0`;
- unnecessary acquisition `0.0`;
- SUCCESS commit / ANSWER / final accuracy `1.0`;
- failure STOP / no-commit / no-guess `1.0`;
- premature STOP `0`;
- repeat acquisition `0`;
- budget violation `0`.

### C103

Oracle acquisition-mechanism selection passed exhaustive 512 examples / 16 eligibility masks.

Registered action family:

```text
ANSWER
READ_MEMORY
RETRIEVE
OBSERVE
ASK_USER
STOP_UNRESOLVED
```

Synthetic equal-capability burden order:

```text
READ_MEMORY < RETRIEVE < OBSERVE < ASK_USER
```

Accepted C103 metrics were all perfect, including minimum-burden selection, no direct answer on critical missing evidence, STOP when no mechanism is eligible, ASK_USER avoidance when self-service is eligible, and hidden-counterfactual action invariance.

## 7. Active experiment — C104

Experiment:

`C104-v5e-supervised-acquisition-mechanism-selector`

Question:

> Can production `ControlLaneActionRouter` learn the C103 six-action mechanism policy from visible state plus explicit runtime eligibility bits and generalize to unseen base=3?

Prospective configuration:

```text
fresh seeds      = 20261211,20261212,20261213
train bases      = 0,1,2
validation base  = 3 only
control width    = 4
hidden width     = 8
training steps   = 640
action count     = 6
```

Working control lane:

```text
base
dependency
evidence_present
observed_hidden
```

Context control lane:

```text
memory_eligible
retrieval_eligible
observation_eligible
ask_user_eligible
```

C104 uses class-balanced training. It does not search the minimum hidden width.

Every fresh seed must achieve:

```text
action accuracy                                   = 1.0
minimum recall across all six actions             = 1.0
action flips                                      = 0
answerable ANSWER rate                            = 1.0
critical-missing no-direct-ANSWER rate            = 1.0
minimum-burden eligible mechanism rate            = 1.0
no-eligible STOP_UNRESOLVED rate                  = 1.0
ASK_USER avoided when self-service eligible       = 1.0
ineligible mechanism count                        = 0
hidden-counterfactual action invariance           = 1.0
```

## 8. Separate tracks / non-claims

- Shared-Basis auto-partition remains separate.
- Context/KV-replacement remains separate.
- Gate C/D and C97-C104 evidence is synthetic and scoped.
- Do not claim broad language quality, general epistemic self-knowledge, real-world tool selection, universal control-width sufficiency, or general superiority over Transformer/LLM systems.
