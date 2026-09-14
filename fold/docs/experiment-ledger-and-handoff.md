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

## Accepted evidence through C117

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
- C117: post-preflight clean-failure fallback PASS on 81 mask pairs / 594 trajectories per seed. First attempt was invalid due helper reference error; valid retry preserved number/seeds/thresholds.

## C118 — UNKNOWN_EFFECT containment: ACCEPTED PASS

Fresh seeds `20261381..83`; 81 mask pairs; 322 scenarios; 160 UNKNOWN_EFFECT cases.

Accepted metrics were all exact:

```text
success control ANSWER                = 1.0
success exactly-one commit            = 1.0
UNKNOWN_EFFECT containment            = 1.0
UNKNOWN_EFFECT exactly-one execution  = 1.0
UNKNOWN_EFFECT zero commit             = 1.0
UNKNOWN_EFFECT zero retry              = 1.0
UNKNOWN_EFFECT zero fallback           = 1.0
confirmed-none STOP                    = 1.0
hidden action-trace invariance         = 1.0
```

Interpretation: an ambiguous post-execution result is not treated as a clean failure. Without authoritative reconciliation, runtime stops without retry, fallback, or evidence commit.

## Active experiment — C119

Experiment: `C119-v5e-idempotency-receipt-reconciliation`.

Question: if the provider supplies authoritative reconciliation tied to the original request key/receipt, can runtime recover from C118 UNKNOWN_EFFECT without duplicate logical effects?

Registered states:

```text
RECONCILED_APPLIED
  -> retry 0
  -> commit once
  -> ANSWER

RECONCILED_NOT_APPLIED
  -> retry once with original request key
  -> commit once
  -> ANSWER

STILL_UNKNOWN
  -> retry 0
  -> fallback 0
  -> commit 0
  -> unresolved
```

Prospective coverage per seed:

```text
fresh seeds          = 20261391,20261392,20261393
mask pairs           = 81
reconciliation cases = 480
empty controls       = 2
scenarios total      = 482
```

All deciding rates are fixed at `1.0`, including one reconciliation, same-key retry only after authoritative NOT_APPLIED, exactly one logical effect on recovered cases, STILL_UNKNOWN containment, confirmed-none STOP, and hidden trace invariance.

C119 assumes authoritative provider reconciliation exists. It remains synthetic and is not a Gate-E passage claim.

## Non-claims / separate tracks

- Shared-Basis auto-partition remains separate.
- Context/KV-replacement remains separate.
- Gate C/D and C97-C119 evidence is synthetic/scoped unless explicitly measured otherwise.
- Do not claim broad language quality, general epistemic self-knowledge, real-world tool selection, or general superiority over Transformer/LLM systems.
