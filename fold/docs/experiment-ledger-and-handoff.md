# FOLD Experiment Ledger and Handoff

> Current authoritative handoff. Detailed history remains in Gate decisions and `experiment-ledger-addendum-*` files.

## 1. Environment / protected artifacts

- Repository: `akakishi04/asobiba`
- Branch: `feat/sft-target-loss`
- Local repo: `M:\asobiba\fold`
- Python: `M:\asobiba\fold\.venv-py31315\Scripts\python.exe`
- Python 3.13.15 / PyTorch 2.10.0+cu130 / CUDA 13.0
- GPU: RTX 4070 Ti SUPER

Protected artifacts:

- `runs/chatgpt-last-result.json`
- SHA256 `FD4A8DA897BDAEA9D103A252E30212C7FF842D23300D7C837333E146DEE51931`
- `runs/fixtures/v05-c-composition-20260921.pt`
- SHA256 `A52F8209703149407580F7E2965B61B78653030EE992AF6D759865736741CA9E`

## 2. Experiment protocol

1. One scientific question per C number.
2. Full output overwrites `runs/chatgpt-last.log`.
3. User pastes the complete log.
4. Judge execution validity separately from scientific result.
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

Do not guess decision-critical missing facts. Do not commit failed/untrusted acquisition as evidence. Do not universally acquire or abstain. Under the current synthetic equal-capability contract, do not ask the user while a lower-burden self-service mechanism remains available.

## 6. V5-E accepted evidence — C97 to C104

### C97-C99 — information sufficiency and successful acquisition

- Oracle `ANSWER / ACQUIRE` boundary established.
- Production Control Lane learned it on unseen base=3 with no hidden/target leakage.
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

C101 learned the three-action snapshot policy. C102 passed the actual learned trajectory across three fresh seeds with required ACQUIRE, SUCCESS commit/ANSWER/accuracy, failure STOP/no-commit/no-guess all `1.0`, and zero premature STOP, repeat acquisition, or budget violation.

### C103-C104 — acquisition mechanism selection

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

C103 exhaustive oracle: 512 examples / all 16 masks passed.

C104 production Control Lane learned the six-action selector on unseen base=3 across fresh seeds `20261211..13`:

- action accuracy `1.0`;
- minimum six-class recall `1.0`;
- action flips `0`;
- minimum-burden selection `1.0`;
- no-eligible STOP `1.0`;
- ASK_USER avoided while self-service eligible `1.0`;
- ineligible mechanism predictions `0`;
- hidden-counterfactual invariance `1.0`.

## 7. C105 — accepted learned mechanism fallback closed loop

Experiment: `C105-v5e-learned-acquisition-mechanism-closed-loop`

Fresh seeds `20261221..23`, unseen base=3, acquisition budget 4.

Runtime contract:

```text
failure
-> no evidence commit
-> failed mechanism becomes ineligible
-> reobserve
-> choose next least-burden eligible mechanism

SUCCESS
-> commit validated evidence
-> reobserve
-> ANSWER

no eligible fallback remains
-> STOP_UNRESOLVED
```

Accepted across all three seeds:

- answerable ANSWER `1.0`;
- answerable zero acquisition `1.0`;
- required scenario pass `1.0`;
- per-decision minimum burden `1.0`;
- eventual-success ANSWER / final accuracy `1.0`;
- all-fail STOP `1.0`;
- failed-attempt no-commit `1.0`;
- ineligible mechanism `0`;
- repeat failed mechanism `0`;
- budget violations `0`;
- premature ASK_USER `0`;
- hidden action-trace invariance `1.0`.

C105 is still synthetic and uses all 16 masks during training.

## 8. Active experiment — C106 falsification

Experiment: `C106-v5e-unseen-eligibility-mask-generalization`

Purpose: directly test whether C104/C105 merely memorized the finite 16-mask lookup table.

Prospective mask split:

```text
training masks = Hamming weight <= 2  (11 masks)
OOD masks      = Hamming weight >= 3  (5 masks)
```

The sets are disjoint and together cover all 16 masks.

Other conditions:

```text
fresh seeds      = 20261231,20261232,20261233
train bases      = 0,1,2
validation base  = 3 only
control width    = 4
hidden width     = 8
training steps   = 800
```

Two validation sets:

1. Anchor validation on unseen base=3 using the training-mask family; must preserve all six classes.
2. OOD composition validation on unseen base=3 using only never-trained masks.

Every fresh seed must satisfy:

```text
anchor action accuracy              = 1.0
anchor minimum six-class recall     = 1.0
anchor action flips                 = 0
OOD action accuracy                 = 1.0
OOD action flips                    = 0
OOD answerable ANSWER rate          = 1.0
OOD critical no-direct-ANSWER rate  = 1.0
OOD minimum-burden rate             = 1.0
OOD ineligible mechanism count      = 0
OOD hidden-counterfactual invariance= 1.0
```

C106 is a falsification/generalization experiment. A valid failure is useful evidence and still completes C106.

## 9. Next falsification axes if C106 completes

Do not immediately resume feature expansion. Candidate later tests, one per C number:

- independently implemented evaluation generator;
- feature re-encoding / permutation;
- irrelevant distractor features;
- noisy or stale capability state;
- changed train/validation construction;
- eventually real memory/retrieval/observation/user interaction.

## 10. Separate tracks / non-claims

- Shared-Basis auto-partition remains separate.
- Context/KV-replacement remains separate.
- Gate C/D and C97-C106 evidence is synthetic and scoped.
- Do not claim broad language quality, general epistemic self-knowledge, real-world tool selection, universal control-width sufficiency, or general superiority over Transformer/LLM systems.
