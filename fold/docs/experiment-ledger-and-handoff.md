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

## Accepted evidence through C128

- C97-C105: information sufficiency, acquisition outcomes, six-action learned selection, and runtime-owned fallback established in synthetic scope.
- C106-C107: unseen eligibility composition and independent evaluator PASS.
- C108: VALID NEGATIVE; arbitrary signed boolean amplitudes broke the raw Control Lane.
- C109-C111: localized the representation failure and integrated schema-aware boolean canonicalization into production.
- C112-C116: natural class-frequency, stale eligibility, performance characterization, stale-low refresh and authoritative preflight PASS.
- C117: post-preflight clean-failure fallback PASS.
- C118: UNKNOWN_EFFECT containment PASS.
- C119: authoritative receipt reconciliation PASS.
- C120: request-key / mechanism / epoch receipt binding PASS.
- C121: receipt authority gate PASS.
- C122: verification verdict scope PASS.
- C123: commit-context revalidation PASS.
- C124: sequential duplicate receipt replay PASS.
- C125: concurrent atomic receipt claim PASS across 2/4/8 workers.
- C126: serialized pending/completed restart recovery PASS across 1/2/3 restarts.
- C127: post-transition crash recovery PASS; APPLIED avoids replay, NOT_APPLIED replays once with the same key, STILL_UNKNOWN stays pending.
- C128: concurrent recovery ownership PASS on fresh seeds `20261481..83`, 1,442 scenarios per seed across 2/4/8 workers. Exactly one recovery owner won; losing workers executed no recovery action; the naive race control exposed multiple winners. C37/fixture preserved; tracked tree clean.

Current reconciliation / recovery chain:

```text
UNKNOWN_EFFECT containment
-> request binding
-> receipt authority
-> verdict scope
-> commit-context revalidation
-> sequential replay suppression
-> concurrent atomic claim
-> serialized pending/completed recovery state
-> post-transition authoritative reconciliation
-> concurrent recovery ownership
-> completion
```

## Active experiment — C129

Experiment: `C129-v5e-recovery-fencing-falsification`.

Question: after a recovery owner lease expires, can takeover issue a strictly higher fencing token so that an old owner or old process incarnation cannot drive recovery state after a newer owner has taken over?

Production primitive: `fold_lm.v05.recovery_fencing.RecoveryFencingRegistry`.

Fresh seeds: `20261491,20261492,20261493`. Worker counts: `2,4,8`.

Coverage per seed:

```text
1,440 lease-expiry takeover / fencing cases
2 confirmed-none controls
1,442 scenarios total
```

Required semantics:

```text
active lease              -> takeover denied
expired lease             -> exactly one takeover winner
new fencing token         -> strictly greater than old token
new owner / new token     -> allowed
old owner / old token     -> write rejected
old owner / old token     -> release rejected
losing challengers        -> zero recovery actions
APPLIED                    -> zero replay / complete once / one logical effect
NOT_APPLIED                -> one replay / complete once / one logical effect
STILL_UNKNOWN              -> zero replay / zero completion / pending retained
```

C128 remains a required control gate. A dedicated regression also verifies stale-token rejection when the same worker id is reused by a newer process incarnation. All deciding rates are fixed at `1.0`.

Scope: C129 uses deterministic logical-time leases in one Python process. It does not establish distributed consensus, database-enforced fencing, lease renewal, or clock-skew semantics. Gate E remains NOT PASSED.

## Non-claims / separate tracks

- Shared-Basis auto-partition remains separate.
- Context/KV-replacement remains separate.
- Gate C/D and C97-C129 evidence is synthetic/scoped unless explicitly measured otherwise.
- Do not claim broad language quality, general epistemic self-knowledge, real-world tool selection, or general superiority over Transformer/LLM systems.
