# FOLD Experiment Ledger and Handoff

> Current authoritative handoff. Detailed history remains in Gate decisions and experiment-ledger addenda.

## Environment / protocol

- Repo: `akakishi04/asobiba`; branch `feat/sft-target-loss`; local `M:\asobiba\fold`.
- Python 3.13.15 / PyTorch 2.10.0+cu130 / CUDA 13.0 / RTX 4070 Ti SUPER.
- Protected C37 SHA256: `FD4A8DA897BDAEA9D103A252E30212C7FF842D23300D7C837333E146DEE51931`.
- Protected fixture SHA256: `A52F8209703149407580F7E2965B61B78653030EE992AF6D759865736741CA9E`.
- One scientific question per C number. Invalid execution retries keep the same number. Valid negative results may complete it. Full output overwrites `runs/chatgpt-last.log`.

## Gate status

- Gate A: PASSED.
- Gate B: PASSED.
- Gate C: PASSED, scoped.
- Gate D: PASSED, scoped.
- Gate E: NOT PASSED; active.

Gate C lead: `W_module = W_base + A_module @ B_shared`, materialized training / GEMM-native inference.

Gate D lead: `fold_lm.v05.controller.ControlLaneActionRouter`. Main working-state width and routing-control width are independent capacity axes.

Primary product priority: operational VRAM headroom, then peak/resident VRAM, latency/throughput, artifact size.

## V5-E production contract

Action family:

```text
ANSWER / READ_MEMORY / RETRIEVE / OBSERVE / ASK_USER / STOP_UNRESOLVED
```

Authority:

```text
model/router -> proposes action
runtime      -> owns availability, permission, outcome validation,
                eligibility mutation, and authoritative evidence mutation
```

Representation:

```text
raw runtime encoding
-> schema-aware Control Representation Adapter
-> canonical boolean Control Lane
-> ControlLaneActionRouter
```

Production adapter: `fold_lm.v05.controller.canonicalize_boolean_channels`.

## Accepted evidence through C118

- C97-C105: information sufficiency, acquisition outcomes, six-action learned selection, and runtime-owned fallback established in synthetic scope.
- C106: unseen eligibility-mask composition PASS.
- C107: independent evaluator PASS.
- C108: VALID NEGATIVE; arbitrary signed boolean amplitudes broke the raw Control Lane.
- C109: localized C108 to seed `20261311`, codebook `ood_b`, boundary actions.
- C110: diagnostic `-1/+1` canonicalization removed the failure.
- C111: production adapter integration PASS on known regression plus fresh seeds.
- C112: natural class-frequency PASS without class-balanced sampling.
- C113: stale-high eligibility contained by authoritative preflight.
- C114: accepted performance characterization; production hot path about `1.60-1.63 ms/decision`, width 8 vs 5120 ratio about `1.013`, extra warmup operational VRAM at width5120 `0 bytes`.
- C115: stale-low terminal refresh PASS.
- C116: authoritative preflight priority refresh PASS.
- C117: post-preflight clean-failure fallback PASS on 81 mask pairs / 594 trajectories per seed. First attempt invalid; valid retry preserved number/seeds/thresholds.
- C118: UNKNOWN_EFFECT containment PASS on 322 scenarios / 160 ambiguous cases per seed, with zero retry, fallback, or commit after ambiguity.

## C119 — idempotency receipt reconciliation: ACCEPTED PASS

Fresh seeds `20261391..93`; 81 mask pairs; 482 scenarios; 480 reconciliation cases.

All deciding rates were `1.0`:

```text
RECONCILED_APPLIED     -> zero retry, one commit, ANSWER
RECONCILED_NOT_APPLIED -> one same-key retry, one commit, ANSWER
STILL_UNKNOWN          -> zero retry/fallback/commit, unresolved
recovered logical effect count -> exactly one
confirmed-none STOP -> correct
hidden trace invariance -> 1.0
```

Protected C37 and fixture were preserved; tracked tree was clean. C119 assumes authoritative provider reconciliation exists.

## Active experiment — C120

Experiment: `C120-v5e-receipt-binding-falsification`.

Question: can a reconciliation receipt affect runtime state only when it is bound to the exact current request identity?

Production primitive added: `fold_lm.v05.reconciliation.receipt_matches_request`.

Binding fields:

```text
request key
mechanism id
request epoch
```

C120 crosses four receipt bindings with the three C119 reconciliation outcomes:

```text
VALID
WRONG_KEY
WRONG_MECHANISM
STALE_EPOCH

x

APPLIED
NOT_APPLIED
STILL_UNKNOWN
```

Coverage per fresh seed `20261401..03`:

```text
81 mask pairs
1,922 scenarios
480 valid receipt cases
1,440 invalid-binding cases
2 confirmed-none STOP controls
```

Prospective gate requires every deciding rate to equal `1.0`: C119 valid controls, exact-binding acceptance, invalid-binding rejection and containment, zero commit/retry/fallback after invalid receipts, confirmed-none STOP, and hidden trace invariance.

C120 changes a production reconciliation primitive but remains synthetic. Gate E remains NOT PASSED.

## Non-claims / separate tracks

- Shared-Basis auto-partition remains separate.
- Context/KV-replacement remains separate.
- Gate C/D and C97-C120 evidence is synthetic/scoped unless explicitly measured otherwise.
- Do not claim broad language quality, general epistemic self-knowledge, real-world tool selection, or general superiority over Transformer/LLM systems.
