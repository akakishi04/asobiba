# FOLD Experiment Ledger and Handoff

> Current authoritative handoff. Detailed history remains in Gate decisions and experiment-ledger addenda.

## Environment / protocol

- Repo: `akakishi04/asobiba`; branch `feat/sft-target-loss`; local `M:\asobiba\fold`.
- Python 3.13.15 / PyTorch 2.10.0+cu130 / CUDA 13.0 / RTX 4070 Ti SUPER.
- Protected C37 SHA256: `FD4A8DA897BDAEA9D103A252E30212C7FF842D23300D7C837333E146DEE51931`.
- Protected fixture SHA256: `A52F8209703149407580F7E2965B61B78653030EE992AF6D759865736741CA9E`.
- One scientific question per C number. Invalid executions retry the same number. Valid negatives may complete it. Full output overwrites `runs/chatgpt-last.log`.

## Gate status

- Gate A: PASSED.
- Gate B: PASSED.
- Gate C: PASSED, scoped.
- Gate D: PASSED, scoped.
- Gate E: NOT PASSED; active.

Gate C lead: `W_module = W_base + A_module @ B_shared`, materialized training / GEMM-native inference.
Gate D lead: `fold_lm.v05.controller.ControlLaneActionRouter`.
Primary product priority: operational VRAM headroom, then peak/resident VRAM, latency/throughput, artifact size.

## V5-E production contract

```text
model/router -> proposes action
runtime      -> owns availability, permission, outcome validation,
                reconciliation, eligibility mutation, and evidence mutation
```

Representation boundary:

```text
raw runtime encoding
-> schema-aware Control Representation Adapter
-> canonical boolean Control Lane
-> ControlLaneActionRouter
```

Action family: `ANSWER / READ_MEMORY / RETRIEVE / OBSERVE / ASK_USER / STOP_UNRESOLVED`.

## Accepted evidence through C125

- C97-C105: information sufficiency, acquisition outcomes, six-action learned selection, and runtime-owned fallback established in synthetic scope.
- C106: unseen eligibility-mask composition PASS.
- C107: independent evaluator PASS.
- C108: VALID NEGATIVE; arbitrary signed boolean amplitudes broke the raw Control Lane.
- C109-C111: localized the representation failure and integrated schema-aware boolean canonicalization into production.
- C112: natural class-frequency PASS without class-balanced sampling.
- C113: stale-high eligibility contained by authoritative preflight.
- C114: accepted performance characterization; production hot path about `1.60-1.63 ms/decision`, width 8 vs 5120 ratio about `1.013`, extra warmup operational VRAM at width5120 `0 bytes`.
- C115-C116: stale-low refresh and authoritative minimum-burden preflight PASS.
- C117: post-preflight clean-failure fallback PASS on 594 trajectories per seed.
- C118: UNKNOWN_EFFECT containment PASS; no retry/fallback/commit after ambiguous execution result.
- C119: authoritative receipt reconciliation PASS; APPLIED, NOT_APPLIED and STILL_UNKNOWN separated without duplicate logical effects.
- C120: request-key / mechanism / epoch receipt binding PASS on 1,922 scenarios per seed.
- C121: receipt authority gate PASS on 1,442 scenarios per seed; provider and external verification verdict required.
- C122: verification verdict scope PASS on 1,922 scenarios per seed; verdict must match receipt id, source id and scope epoch.
- C123: commit-context revalidation PASS on 1,922 scenarios per seed; changed request epoch or provider generation caused zero commit/retry/fallback.
- C124: sequential duplicate receipt replay PASS on 1,442 scenarios per seed.
- C125: concurrent atomic receipt claim PASS on fresh seeds `20261451..53`, 1,442 scenarios per seed, 1,440 concurrent cases across 2/4/8 workers. Atomic claims produced exactly one winner; post-race duplicates were rejected; the naive non-atomic negative control exposed multiple winners. C37/fixture preserved; tracked tree clean.

Current reconciliation chain:

```text
UNKNOWN_EFFECT containment
-> request binding
-> receipt authority
-> verdict scope
-> commit-context revalidation
-> sequential replay suppression
-> concurrent atomic claim
-> reconciliation
```

## Active experiment — C126

Experiment: `C126-v5e-restart-recovery-falsification`.

Question: after a claim has been persisted but before downstream transition begins, can restart reconstruction preserve a distinct pending state, reject fresh duplicate claims, resume exactly once, and persist completion?

Production state:

```text
fold_lm.v05.receipt_recovery.ReceiptRecoverySnapshot
fold_lm.v05.receipt_recovery.ReceiptRecoveryRegistry
```

Snapshot states distinguish `pending_receipt_ids` from `completed_receipt_ids`. Snapshot data crosses a JSON-serializable payload boundary before every simulated restart.

Fresh seeds: `20261461,20261462,20261463`.
Restart counts: `1,2,3`.

Coverage per seed:

```text
1,440 restart-recovery cases
2 confirmed-none controls
1,442 scenarios total
```

Required semantics:

```text
C125 control gate                 -> preserved
naive processed-set control       -> loss-of-pending-state flaw detected
initial claim                     -> exactly once
serialized pending snapshot       -> survives restart
fresh duplicate claim on restart  -> rejected
recovery resume                   -> exactly once
completion                        -> pending -> completed
post-completion duplicate claim   -> rejected
APPLIED                            -> total one commit / zero retry
NOT_APPLIED                        -> total one retry / one commit
STILL_UNKNOWN                      -> total zero commit/retry/fallback
```

All deciding rates are fixed at `1.0`.

Scope: C126 models serializable snapshot reconstruction after a crash point strictly between durable claim persistence and the start of downstream transition. It does not prove filesystem fsync durability, does not cover a crash after downstream transition begins, and does not test concurrent recovery ownership. Gate E remains NOT PASSED.

## Non-claims / separate tracks

- Shared-Basis auto-partition remains separate.
- Context/KV-replacement remains separate.
- Gate C/D and C97-C126 evidence is synthetic/scoped unless explicitly measured otherwise.
- Do not claim broad language quality, general epistemic self-knowledge, real-world tool selection, or general superiority over Transformer/LLM systems.
