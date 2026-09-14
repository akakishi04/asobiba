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
7. Predeclare thresholds before collecting deciding data.
8. Preserve protected artifacts and require tracked tree clean.

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

Gate D lead controller:

`fold_lm.v05.controller.ControlLaneActionRouter`

Supported principle:

> Main working-state width and routing-control width are independent capacity axes.

Primary product objective remains operational VRAM headroom.

## 4. V5-E current contract

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

Do not guess decision-critical missing facts. Do not commit failed/untrusted acquisition as evidence. Under the current synthetic equal-capability contract, do not ask the user while a lower-burden self-service mechanism remains available.

## 5. Accepted V5-E capability evidence — C97 to C105

C97-C99 established information sufficiency and the successful `ACQUIRE -> runtime commit -> reobserve -> ANSWER` loop.

C100-C102 established learned handling of `SUCCESS / UNAVAILABLE / DENIED / INVALID`, including no guessed answers, no repeat acquisition, and no budget violations.

C103-C105 expanded the action family to `ANSWER / READ_MEMORY / RETRIEVE / OBSERVE / ASK_USER / STOP_UNRESOLVED` with synthetic burden order `READ_MEMORY < RETRIEVE < OBSERVE < ASK_USER` and passed the learned mechanism fallback closed loop.

## 6. Falsification evidence

### C106 — unseen mask composition: ACCEPTED PASS

Training used only Hamming-weight <=2 masks; OOD validation used never-trained Hamming-weight >=3 masks on unseen base=3. All fresh seeds passed with OOD accuracy and minimum-burden rate `1.0`, zero flips and zero ineligible selections.

Interpretation: finite 16-mask memorization is materially weakened as an explanation.

### C107 — independent evaluator: ACCEPTED PASS

Training stayed on the canonical generator family; evaluation used an independently written fixture. Label agreement and key coverage were complete, and all fresh seeds achieved action accuracy / minimum class recall / minimum-burden rate `1.0` with zero flips or ineligible selections.

Interpretation: a shared train/eval generator implementation bug is materially weakened as an explanation.

### C108 — signed feature re-encoding: ACCEPTED VALID NEGATIVE

Training codebooks:

```text
train_a: false=-0.5, true=+0.75
train_b: false=-2.0, true=+1.25
```

OOD codebooks:

```text
ood_a: false=-3.5, true=+0.20
ood_b: false=-0.10, true=+4.0
ood_c: false=-7.0, true=+9.0
```

Anchor remained perfect. OOD failed prospectively:

- OOD accuracy min `0.953125`;
- OOD minimum class recall min `0.0`;
- ineligible mechanism count sum `2`;
- action flips sum `6`.

Interpretation: the raw Control Lane is not fully invariant to arbitrary signed boolean amplitude changes; `false < 0 < true` alone is not a sufficient representation contract.

### C109 — failure localization: ACCEPTED DIAGNOSTIC PASS

C109 replayed C108 without changing training, architecture, codebooks, seeds, or thresholds.

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

All other seed/codebook pairs were perfect.

Interpretation: C108 is not broad policy collapse. Failure is localized to one asymmetric amplitude condition and boundary actions (`ANSWER`, `STOP_UNRESOLVED`). Do not claim LayerNorm is the confirmed cause yet.

## 7. Active experiment — C110 signed-control canonicalization diagnostic

Experiment: `C110-v5e-signed-control-canonicalization-diagnostic`

Question:

> If schema-known signed boolean Control-Lane values are canonicalized to `-1/+1` before the production router, does the registered C108 failure disappear while the raw path still reproduces the negative result?

C110 is paired and diagnostic only.

Unchanged:

```text
router architecture
training steps
optimizer
training codebooks
OOD codebooks
replay seeds = 20261311,20261312,20261313
```

Only adapter:

```text
schema-known boolean signed value
-> sign(value)
-> {-1,+1}
```

Base remains untouched.

Prospective gate:

```text
raw C108 negative reproduced                  = true
canonical anchor action accuracy min          = 1.0
canonical anchor minimum class recall min     = 1.0
canonical OOD action accuracy min             = 1.0
canonical OOD minimum class recall min        = 1.0
canonical OOD minimum-burden rate min         = 1.0
canonical OOD ineligible mechanism count sum  = 0
canonical OOD action flip count sum           = 0
canonical all validation passed               = true
```

If C110 passes, only conclude that explicit schema-aware boolean canonicalization is sufficient to remove the registered C108 amplitude sensitivity. This does not make the raw router encoding-invariant and does not yet justify production integration.

## 8. Next falsification axes

After C110, continue one question per C number. Candidate tests:

- near-zero / noisy boolean metadata;
- stale capability state;
- irrelevant distractor features;
- changed train/validation construction;
- eventually real memory/retrieval/observation/user interaction.

## 9. Separate tracks / non-claims

- Shared-Basis auto-partition remains separate.
- Context/KV-replacement remains separate.
- Gate C/D and C97-C110 evidence is synthetic and scoped.
- Do not claim broad language quality, general epistemic self-knowledge, real-world tool selection, universal control-width sufficiency, or general superiority over Transformer/LLM systems.
