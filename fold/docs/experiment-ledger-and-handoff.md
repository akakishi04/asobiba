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
7. Predeclare thresholds before deciding data.
8. Preserve protected artifacts and require tracked tree clean.

## 3. Gate status

- Gate A: PASSED.
- Gate B: PASSED.
- Gate C: PASSED, scoped.
- Gate D: PASSED, scoped.
- Gate E: NOT PASSED. Active stage.

Gate C lead:

```text
W_module = W_base + A_module @ B_shared
training  -> materialized
inference -> gemm_native
```

Gate D lead controller:

`fold_lm.v05.controller.ControlLaneActionRouter`

Supported principle:

> Main working-state width and routing-control width are independent capacity axes.

Primary product objective remains operational VRAM headroom.

## 4. V5-E current action / authority contract

Action family:

```text
ANSWER
READ_MEMORY
RETRIEVE
OBSERVE
ASK_USER
STOP_UNRESOLVED
```

Authority:

```text
model/router -> proposes action
runtime      -> owns availability, permission, acquisition outcome, validation, eligibility mutation, and authoritative evidence mutation
```

Do not guess decision-critical missing facts. Do not commit failed/untrusted acquisition as evidence. Under the registered synthetic burden contract, do not ask the user while a lower-burden self-service mechanism remains available.

Production representation boundary now includes explicit schema-aware boolean canonicalization before the router:

```text
raw runtime encoding
-> Control Representation Adapter
-> canonical boolean Control Lane
-> ControlLaneActionRouter
```

## 5. Accepted V5-E capability evidence — C97 to C105

C97-C99 established information sufficiency and the successful `ACQUIRE -> runtime commit -> reobserve -> ANSWER` loop.

C100-C102 established learned handling of `SUCCESS / UNAVAILABLE / DENIED / INVALID`, including no guessed answers, no repeat acquisition, and no budget violations.

C103-C105 expanded the action family to `ANSWER / READ_MEMORY / RETRIEVE / OBSERVE / ASK_USER / STOP_UNRESOLVED` and passed learned mechanism selection plus failure-driven fallback under runtime authority.

## 6. Falsification / representation evidence — C106 to C111

### C106 — unseen mask composition: ACCEPTED PASS

OOD masks never seen in training still passed perfectly on unseen base=3. Finite 16-mask lookup memorization is materially weakened as an explanation.

### C107 — independent evaluator: ACCEPTED PASS

An independently implemented evaluator agreed with canonical semantics and all fresh seeds passed. A shared train/eval generator bug is materially weakened as an explanation.

### C108 — signed feature re-encoding: ACCEPTED VALID NEGATIVE

Anchor remained perfect, but held-out signed codebooks produced OOD accuracy min `0.953125`, minimum class recall `0.0`, two ineligible selections and six action flips.

Interpretation: raw Control-Lane numeric amplitude is part of the effective representation. `false < 0 < true` alone is not a sufficient raw production contract.

### C109 — failure localization: ACCEPTED DIAGNOSTIC PASS

Exactly one condition failed: seed `20261311`, codebook `ood_b (-0.1,+4.0)`, six errors. Acquisition mechanism classes retained recall `1.0`; failures concentrated in `ANSWER` and `STOP_UNRESOLVED`.

### C110 — signed boolean canonicalization: ACCEPTED DIAGNOSTIC PASS

Raw C108 failure reproduced. Changing only schema-known boolean representation to `-1/+1` restored all registered anchor/OOD metrics to `1.0` with zero flips/ineligible selections.

### C111 — production Control Representation Adapter: ACCEPTED PASS

Production primitive: `fold_lm.v05.controller.canonicalize_boolean_channels`.

Contract:

```text
schema specifies boolean channels + decode threshold
value < threshold -> -1
value > threshold -> +1
value == threshold -> reject as ambiguous
non-boolean channels -> preserved unchanged
```

Accepted validation:

- adapter contract smoke passed;
- known C108 failing seed `20261311` recovered;
- fresh seeds `20261321..23` all passed;
- anchor accuracy / minimum six-class recall min `1.0`;
- OOD accuracy / minimum six-class recall / minimum-burden rate min `1.0`;
- OOD ineligible mechanism count `0`;
- OOD action flips `0`.

Interpretation: explicit schema-aware canonicalization repairs the registered amplitude sensitivity without changing router architecture, optimizer, training schedule, or codebooks.

## 7. Active experiment — C112 natural class-frequency falsification

Experiment: `C112-v5e-natural-class-frequency-falsification`

Question:

> Does the six-action production selector still learn the registered mechanism policy when class-balanced training is removed and batches are sampled uniformly from the naturally imbalanced exhaustive training rows?

Keep fixed:

```text
production adapter = canonicalize_boolean_channels
control width       = 4
hidden width        = 8
training steps      = 900
batch size          = 96
train bases         = 0,1,2
validation base     = 3 only
training/OOD codebooks unchanged from C108/C111
```

Fresh seeds:

```text
20261331
20261332
20261333
```

Only sampler changes:

```text
previous -> class-balanced 16 examples/action/step
C112     -> uniform training-row sampling with replacement
```

Natural synthetic class distribution:

```text
ANSWER           75.0000%
READ_MEMORY      12.5000%
RETRIEVE          6.2500%
OBSERVE           3.1250%
ASK_USER          1.5625%
STOP_UNRESOLVED   1.5625%
```

Prospective gate for every seed:

```text
anchor action accuracy               = 1.0
anchor minimum six-class recall      = 1.0
OOD action accuracy                  = 1.0
OOD minimum six-class recall         = 1.0
OOD minimum-burden rate              = 1.0
OOD ineligible mechanism count       = 0
OOD action flip count                = 0
OOD hidden-counterfactual invariance = 1.0
```

A valid negative result completes C112. Do not change steps, batch size, seeds, or thresholds retrospectively under C112.

## 8. Next falsification axes after C112

Continue one question per C number. Priority candidates:

- stale capability state;
- irrelevant/distractor control state;
- changed train/validation construction;
- source/runtime failures around the representation adapter boundary;
- eventually real memory/retrieval/observation/user interaction.

Near-threshold noise should only be tested under an explicit source-confidence/deadband contract; otherwise sign-crossing changes the observed boolean itself and confounds representation robustness with runtime observation error.

## 9. Separate tracks / non-claims

- Shared-Basis auto-partition remains separate.
- Context/KV-replacement remains separate.
- Gate C/D and C97-C112 evidence is synthetic and scoped.
- Do not claim broad language quality, general epistemic self-knowledge, real-world tool selection, universal control-width sufficiency, or general superiority over Transformer/LLM systems.
