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

## 5. Accepted V5-E capability evidence — C97 to C105

C97-C99 established information sufficiency and the successful `ACQUIRE -> runtime commit -> reobserve -> ANSWER` loop.

C100-C102 established learned handling of `SUCCESS / UNAVAILABLE / DENIED / INVALID`, including no guessed answers, no repeat acquisition, and no budget violations.

C103-C105 expanded the action family to `ANSWER / READ_MEMORY / RETRIEVE / OBSERVE / ASK_USER / STOP_UNRESOLVED` and passed learned mechanism selection plus failure-driven fallback under runtime authority.

## 6. Falsification evidence

### C106 — unseen mask composition: ACCEPTED PASS

OOD masks never seen in training still passed perfectly on unseen base=3. Finite 16-mask lookup memorization is materially weakened as an explanation.

### C107 — independent evaluator: ACCEPTED PASS

An independently implemented evaluator agreed with the canonical semantics and all fresh seeds passed. A shared train/eval generator bug is materially weakened as an explanation.

### C108 — signed feature re-encoding: ACCEPTED VALID NEGATIVE

OOD signed codebooks preserved only `false < 0 < true` while changing amplitudes.

Prospective gate failed:

- anchor action accuracy min `1.0`;
- OOD action accuracy min `0.953125`;
- OOD minimum class recall min `0.0`;
- ineligible mechanism count sum `2`;
- action flips sum `6`.

Interpretation: raw Control-Lane numeric amplitude is part of the effective representation. `false < 0 < true` alone is not a sufficient raw production contract.

### C109 — failure localization: ACCEPTED DIAGNOSTIC PASS

Exactly one condition failed:

```text
seed      = 20261311
codebook  = ood_b (-0.1, +4.0)
accuracy  = 0.953125
errors    = 6
```

Per-class recall:

```text
ANSWER           = 0.9583333333333334
READ_MEMORY      = 1.0
RETRIEVE         = 1.0
OBSERVE          = 1.0
ASK_USER         = 1.0
STOP_UNRESOLVED  = 0.0
```

Failure is localized to boundary actions rather than mechanism-priority collapse.

### C110 — signed boolean canonicalization: ACCEPTED DIAGNOSTIC PASS

C110 replayed the raw C108 negative and then changed only the schema-known boolean representation:

```text
signed boolean raw value
-> sign(value)
-> {-1,+1}
```

Accepted result:

- raw C108 negative reproduced: `true`;
- canonical anchor action accuracy / minimum class recall min `1.0`;
- canonical OOD action accuracy / minimum class recall / minimum-burden rate min `1.0`;
- canonical OOD ineligible mechanism count sum `0`;
- canonical OOD action flips sum `0`;
- all canonical validation passed.

Interpretation:

> Explicit schema-aware boolean canonicalization is sufficient to remove the registered C108 amplitude sensitivity. The raw router itself is not thereby encoding-invariant.

## 7. Active experiment — C111 production Control Representation Adapter integration

Experiment: `C111-v5e-production-control-canonicalization-integration`

Production primitive added to `fold_lm.v05.controller`:

`canonicalize_boolean_channels`

Contract:

```text
schema specifies boolean channels + decode threshold
value < threshold -> -1
value > threshold -> +1
value == threshold -> reject as ambiguous
non-boolean channels -> preserved unchanged
```

Examples:

```text
signed raw encoding -> threshold 0.0
zero/one encoding   -> threshold 0.5
```

The adapter is outside `ControlLaneActionRouter`; router architecture, parameter count, optimizer, training schedule, and C108 codebooks remain unchanged.

Prospective validation:

```text
known regression seed = 20261311
fresh seeds           = 20261321,20261322,20261323
```

Every registered seed/codebook must satisfy:

```text
adapter contract smoke                         = pass
known C108 failure recovered                   = true
all fresh seeds                                = pass
anchor action accuracy min                     = 1.0
anchor minimum six-class recall min            = 1.0
OOD action accuracy min                        = 1.0
OOD minimum six-class recall min               = 1.0
OOD minimum-burden rate min                    = 1.0
OOD ineligible mechanism count sum             = 0
OOD action flip count sum                      = 0
```

C111 modifies a production representation primitive but is not a Gate E passage claim.

## 8. Next falsification axes after C111

Continue one question per C number. Priority candidates:

- near-threshold / noisy boolean metadata;
- stale capability state;
- irrelevant distractor features;
- changed train/validation construction;
- eventually real memory/retrieval/observation/user interaction.

## 9. Separate tracks / non-claims

- Shared-Basis auto-partition remains separate.
- Context/KV-replacement remains separate.
- Gate C/D and C97-C111 evidence is synthetic and scoped.
- Do not claim broad language quality, general epistemic self-knowledge, real-world tool selection, universal control-width sufficiency, or general superiority over Transformer/LLM systems.
