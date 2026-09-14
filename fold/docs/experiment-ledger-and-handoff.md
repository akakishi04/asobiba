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

## Accepted evidence through C124

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
- C124: sequential duplicate receipt replay PASS on 1,442 scenarios per seed. The first delivery claimed exactly once; repeated deliveries added no commit/retry/fallback. APPLIED totaled one commit, NOT_APPLIED one retry plus one commit, and STILL_UNKNOWN zero side effects. C37/fixture preserved; tracked tree clean.

Current reconciliation chain:

```text
UNKNOWN_EFFECT containment
-> request binding
-> receipt authority
-> verdict scope
-> commit-context revalidation
-> receipt replay suppression
-> reconciliation
```

## Active experiment — C125

Experiment: `C125-v5e-atomic-receipt-claim-falsification`.

Question: can concurrent duplicate deliveries of the same valid receipt be atomically claimed so that exactly one worker wins and only that winner may drive the downstream reconciliation transition?

Production primitive: `fold_lm.v05.receipt_atomic_claim.AtomicReceiptClaimRegistry`.

Fresh seeds: `20261451,20261452,20261453`.
Worker counts: `2,4,8`.

Coverage per seed:

```text
1,440 concurrent duplicate-claim cases
2 confirmed-none controls
1,442 scenarios total
```

Required semantics:

```text
naive non-atomic negative control -> race detected
atomic registry                  -> exactly one winner
post-race duplicate claim        -> rejected
registry snapshot                -> exactly one receipt id
APPLIED                           -> total one commit / zero retry
NOT_APPLIED                       -> total one retry / one commit
STILL_UNKNOWN                     -> total zero commit/retry/fallback
```

C124 remains a required control gate and hidden counterfactual traces must remain invariant. All deciding rates are fixed at `1.0`.

C125 tests in-process Python-thread atomicity only. Cross-process/distributed storage atomicity and crash durability remain separate questions. Gate E remains NOT PASSED.

## Non-claims / separate tracks

- Shared-Basis auto-partition remains separate.
- Context/KV-replacement remains separate.
- Gate C/D and C97-C125 evidence is synthetic/scoped unless explicitly measured otherwise.
- Do not claim broad language quality, general epistemic self-knowledge, real-world tool selection, or general superiority over Transformer/LLM systems.
