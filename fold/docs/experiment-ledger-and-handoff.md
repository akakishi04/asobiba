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

Production representation boundary includes explicit schema-aware boolean canonicalization before the router:

```text
raw runtime encoding
-> Control Representation Adapter
-> canonical boolean Control Lane
-> ControlLaneActionRouter
```

Production primitive: `fold_lm.v05.controller.canonicalize_boolean_channels`.

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

Production `canonicalize_boolean_channels` recovered the known C108 failing seed and fresh seeds `20261321..23`; anchor/OOD action accuracy, minimum class recall and minimum-burden rate were all `1.0`, with zero ineligible selections or flips.

Interpretation: explicit schema-aware canonicalization repairs the registered amplitude sensitivity without changing router architecture, optimizer, training schedule, or codebooks.

## 7. C112 — natural class-frequency falsification: ACCEPTED PASS

Experiment: `C112-v5e-natural-class-frequency-falsification`

C112 removed class-balanced minibatches and sampled training rows uniformly with replacement while keeping the production adapter, router architecture, optimizer, batch size, 900-step schedule and codebooks fixed.

Natural synthetic training distribution:

```text
ANSWER           75.0000%
READ_MEMORY      12.5000%
RETRIEVE          6.2500%
OBSERVE           3.1250%
ASK_USER          1.5625%
STOP_UNRESOLVED   1.5625%
```

Fresh seeds `20261331..33` all passed on unseen base=3:

- anchor action accuracy `1.0`;
- anchor minimum six-class recall `1.0`;
- OOD action accuracy `1.0`;
- OOD minimum six-class recall `1.0`;
- OOD minimum-burden rate `1.0`;
- OOD ineligible mechanism count `0`;
- OOD action flips `0`;
- OOD hidden-counterfactual invariance `1.0`.

Interpretation: the registered six-action selector is not dependent on class-balanced sampling within the current exhaustive synthetic distribution. This is not a claim about a measured product distribution.

## 8. Active experiment — C113 stale eligibility preflight falsification

Experiment: `C113-v5e-stale-eligibility-preflight`

Question:

> Can the learned selector remain safe when model-visible eligibility is stale-high, if runtime performs authoritative preflight before any external mechanism execution and then forces reobservation/fallback?

Prospective configuration:

```text
fresh seeds      = 20261341,20261342,20261343
train bases      = 0,1,2
validation base  = 3 only
sampling         = natural uniform-row sampling
production adapter = canonicalize_boolean_channels
```

Runtime contract:

```text
model-visible mask may contain stale false-positive eligibility
actual authoritative mask is a subset of the visible mask

router proposes action
-> runtime preflight checks authoritative availability

stale at preflight
-> no external mechanism execution
-> no evidence commit
-> clear that visible eligibility bit
-> reobserve
-> choose next minimum-burden visible mechanism

first genuinely available mechanism
-> exactly one external execution
-> SUCCESS
-> evidence commit
-> reobserve
-> ANSWER

no authoritative mechanism available
-> exhaust visible stale bits
-> STOP_UNRESOLVED
```

C113 exhaustively evaluates all authoritative-mask subsets of all model-visible masks across the four mechanism bits and both hidden counterfactuals.

Every fresh seed must satisfy:

```text
answerable ANSWER rate                         = 1.0
required scenario pass rate                    = 1.0
stale-prefix exact rate                        = 1.0
actual-available ANSWER rate                   = 1.0
actual-available exactly-one-execution rate    = 1.0
no-actual STOP_UNRESOLVED rate                 = 1.0
no-actual zero-execution rate                  = 1.0
hidden action-trace invariance                 = 1.0
priority violation count                       = 0
stale external execution count                 = 0
repeat stale-reject count                      = 0
```

C113 tests stale-high eligibility only. Stale false-negative availability is a separate problem. Runtime preflight is still synthetic and does not invoke real memory, retrieval, observation, or user interaction. A valid negative result completes C113 without relaxing thresholds.

## 9. Next falsification / integration axes after C113

Continue one question per C number. Priority candidates:

- stale false-negative availability / freshness refresh semantics;
- irrelevant or spuriously correlated runtime metadata;
- changed train/validation construction;
- actual source/runtime failures at the adapter boundary;
- eventually real memory/retrieval/observation/user interaction.

Near-threshold noise should only be tested under an explicit source-confidence/deadband contract; otherwise sign-crossing changes the observed boolean itself and confounds representation robustness with runtime observation error.

## 10. Separate tracks / non-claims

- Shared-Basis auto-partition remains separate.
- Context/KV-replacement remains separate.
- Gate C/D and C97-C113 evidence is synthetic and scoped.
- Do not claim broad language quality, general epistemic self-knowledge, real-world tool selection, universal control-width sufficiency, or general superiority over Transformer/LLM systems.
