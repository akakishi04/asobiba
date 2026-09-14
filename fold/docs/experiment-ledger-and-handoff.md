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

## 4. V5-E current action / authority contract

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

Do not guess decision-critical missing facts. Do not commit failed/untrusted acquisition as evidence. Under the current synthetic equal-capability contract, do not ask the user while a lower-burden self-service mechanism remains available.

## 5. V5-E accepted evidence — C97 to C105

C97-C99 established and learned the information-sufficiency boundary and the successful `ACQUIRE -> runtime commit -> reobserve -> ANSWER` loop on unseen base=3.

C100-C102 established acquisition outcomes:

```text
SUCCESS -> validated evidence commit -> ANSWER
UNAVAILABLE / DENIED / INVALID -> no commit -> STOP_UNRESOLVED
```

The production Control Lane learned and executed these outcomes with zero guessed answers, repeat acquisition, or budget violations in the registered synthetic tests.

C103-C105 expanded acquisition into:

```text
ANSWER
READ_MEMORY
RETRIEVE
OBSERVE
ASK_USER
STOP_UNRESOLVED
```

with synthetic equal-capability burden order:

```text
READ_MEMORY < RETRIEVE < OBSERVE < ASK_USER
```

C105 passed the learned mechanism fallback loop across fresh seeds `20261221..23`, including failure-driven eligibility removal, next-mechanism fallback, SUCCESS-only evidence commit, all-fail STOP, zero repeated failed mechanisms, zero ineligible selections, and hidden action-trace invariance `1.0`.

## 6. Falsification evidence

### C106 — unseen eligibility-mask composition: ACCEPTED PASS

Training used only the 11 masks with Hamming weight <= 2. OOD validation used only the five never-trained masks with Hamming weight >= 3, together with unseen base=3.

Across fresh seeds `20261231..33`:

- anchor action accuracy `1.0`;
- anchor minimum six-class recall `1.0`;
- OOD action accuracy `1.0`;
- OOD minimum-burden rate `1.0`;
- ineligible mechanism count `0`;
- action flips `0`;
- hidden-counterfactual action invariance `1.0`.

Interpretation: memorization of all 16 finite masks is materially weakened as an explanation.

### C107 — independent evaluator: ACCEPTED PASS

Training remained on the C106 canonical family. Evaluation used `gate_e_c107_independent_eval_fixture.py`, which independently reconstructs visible rows and expected actions and imports none of the forbidden C97-C106 oracle/generator modules.

Across fresh seeds `20261301..03`:

- independent/canonical label agreement `1.0`;
- key coverage complete;
- independent action accuracy `1.0`;
- independent minimum six-class recall `1.0`;
- independent minimum-burden rate `1.0`;
- ineligible mechanism count `0`;
- action flips `0`;
- hidden-counterfactual invariance `1.0`.

Interpretation: a shared train/eval generator implementation bug is materially weakened as an explanation.

## 7. Active experiment — C108 feature re-encoding falsification

Experiment: `C108-v5e-feature-reencoding-falsification`

Question:

> Does the learned mechanism policy depend on exact numeric boolean encodings, or generalize across unseen signed codebooks preserving only `false < 0 < true`?

Training codebooks:

```text
train_a: false=-0.5, true=+0.75
train_b: false=-2.0, true=+1.25
```

Held-out OOD codebooks:

```text
ood_a: false=-3.5, true=+0.20
ood_b: false=-0.10, true=+4.0
ood_c: false=-7.0, true=+9.0
```

OOD scalar values are disjoint from training scalar values. Base remains canonical because it is policy-irrelevant.

Prospective configuration:

```text
fresh seeds      = 20261311,20261312,20261313
train bases      = 0,1,2
validation base  = 3 only
control width    = 4
hidden width     = 8
training steps   = 900
```

Every fresh seed and every OOD codebook must satisfy:

```text
anchor action accuracy               = 1.0
anchor minimum six-class recall      = 1.0
anchor action flips                  = 0
OOD action accuracy                  = 1.0
OOD minimum six-class recall         = 1.0
OOD action flips                     = 0
OOD answerable ANSWER rate           = 1.0
OOD critical no-direct-ANSWER rate   = 1.0
OOD minimum-burden rate              = 1.0
OOD no-eligible STOP rate            = 1.0
OOD ineligible mechanism count       = 0
OOD hidden-counterfactual invariance = 1.0
```

C108 is a falsification/generalization experiment. A valid failure is useful evidence and still completes C108.

## 8. Planned falsification axes after C108

Continue one question per C number rather than resuming feature expansion immediately:

- irrelevant distractor features;
- noisy or stale capability state;
- changed train/validation construction;
- eventually real memory/retrieval/observation/user interaction.

Arbitrary channel permutation or unknown semantic remapping is not a required invariant unless an explicit schema/adapter is provided.

## 9. Separate tracks / non-claims

- Shared-Basis auto-partition remains separate.
- Context/KV-replacement remains separate.
- Gate C/D and C97-C108 evidence is synthetic and scoped.
- Do not claim broad language quality, general epistemic self-knowledge, real-world tool selection, universal control-width sufficiency, or general superiority over Transformer/LLM systems.
