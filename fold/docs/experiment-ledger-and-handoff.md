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

## 6. V5-E accepted evidence — C97 to C105

### C97-C99 — information sufficiency and successful acquisition

- Oracle `ANSWER / ACQUIRE` boundary established.
- Production Control Lane learned it on unseen base=3 with no hidden/target leakage.
- Learned successful closed loop established: `ACQUIRE -> runtime commit -> reobserve -> ANSWER`.
- Required cases acquired exactly once; answerable cases acquired zero times; final accuracy `1.0`.

### C100-C102 — acquisition outcome handling

Accepted semantics:

```text
SUCCESS -> validated evidence commit -> ANSWER
UNAVAILABLE / DENIED / INVALID -> no commit -> STOP_UNRESOLVED
```

C101 learned the snapshot policy. C102 passed the actual learned end-to-end trajectory across three fresh seeds with required ACQUIRE, SUCCESS commit/ANSWER/accuracy, failure STOP/no-commit/no-guess all `1.0`, and zero premature STOP, repeat acquisition, or budget violation.

### C103-C105 — mechanism selection and fallback

Registered mechanism family:

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

C103 exhaustive oracle passed all 512 examples / 16 eligibility masks.

C104 learned the six-action selector on unseen base=3 across fresh seeds `20261211..13` with action accuracy and minimum six-class recall `1.0`, zero flips/ineligible actions, perfect minimum-burden selection, and hidden-counterfactual invariance `1.0`.

C105 learned the runtime fallback closed loop across fresh seeds `20261221..23`:

- answerable ANSWER / zero-acquisition `1.0`;
- required scenario pass `1.0`;
- per-decision minimum-burden rate `1.0`;
- eventual-success ANSWER / final accuracy `1.0`;
- all-fail STOP `1.0`;
- failure no-commit `1.0`;
- zero ineligible mechanisms, repeated failed mechanisms, budget violations, or premature ASK_USER;
- hidden action-trace invariance `1.0`.

## 7. C106 — accepted falsification: unseen eligibility masks

Experiment: `C106-v5e-unseen-eligibility-mask-generalization`

Purpose: falsify the explanation that C104/C105 simply memorized all 16 mask-to-action combinations.

Split:

```text
training masks = Hamming weight <= 2  (11 masks)
OOD masks      = Hamming weight >= 3  (5 masks)
train bases    = 0,1,2
validation     = base 3 only
fresh seeds    = 20261231,20261232,20261233
```

Accepted across all seeds:

- OOD masks never seen in training;
- anchor action accuracy `1.0`;
- anchor minimum six-class recall `1.0`;
- OOD action accuracy `1.0`;
- OOD minimum-burden selection `1.0`;
- OOD ineligible mechanism predictions `0`;
- OOD action flips `0`;
- OOD hidden-counterfactual action invariance `1.0`.

Interpretation: finite 16-mask memorization is materially weakened as an explanation. C106 still shares the same generator/oracle implementation family between training and evaluation.

## 8. Active experiment — C107 independent-evaluator falsification

Experiment: `C107-v5e-independent-evaluator-falsification`

Question:

> Does the C106 training path still pass when evaluation rows, visible-state construction, row ordering, and expected actions come from an independently written evaluator that imports none of the C97-C106 oracle/generator modules?

Design:

- training remains the accepted C106 training family;
- fresh seeds `20261301,20261302,20261303`;
- independent evaluation uses all 16 masks on unseen base=3;
- independent fixture reconstructs action truth using separate direct conditionals;
- independent fixture uses a deliberately different stable row order;
- independent expected labels are compared against canonical labels as a separate semantic-agreement diagnostic;
- the production router implementation itself is unchanged.

Prospective C107 gate:

```text
independent fixture forbidden canonical imports    = 0
independent/canonical label agreement               = 1.0
independent/canonical key coverage complete         = true
independent action accuracy                         = 1.0
independent minimum six-class recall                = 1.0
independent action flips                            = 0
independent minimum-burden mechanism rate           = 1.0
independent ineligible mechanism count              = 0
independent hidden-counterfactual invariance        = 1.0
```

A valid negative result completes C107. Do not loosen thresholds retrospectively.

## 9. Planned falsification axes after C107

Continue one question per C number rather than adding V5-E features immediately:

- feature re-encoding / channel permutation;
- irrelevant distractor features;
- noisy or stale capability state;
- changed train/validation construction;
- eventually real memory/retrieval/observation/user interaction.

## 10. Separate tracks / non-claims

- Shared-Basis auto-partition remains separate.
- Context/KV-replacement remains separate.
- Gate C/D and C97-C107 evidence is synthetic and scoped.
- Do not claim broad language quality, general epistemic self-knowledge, real-world tool selection, universal control-width sufficiency, or general superiority over Transformer/LLM systems.
