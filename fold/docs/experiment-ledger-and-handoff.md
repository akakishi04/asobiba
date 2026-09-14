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

## Accepted evidence through C127

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
- C125: concurrent atomic receipt claim PASS across 2/4/8 workers, including naive-race negative control.
- C126: serialized pending/completed restart recovery PASS across 1/2/3 restarts.
- C127: post-transition crash recovery PASS on fresh seeds `20261471..73`, 1,442 scenarios per seed across 1/2/3 restarts. APPLIED completed without replay, NOT_APPLIED replayed exactly once with the same key, STILL_UNKNOWN remained pending without replay or completion, and the naive pending-replay negative control exposed duplicate-effect risk. C37/fixture preserved; tracked tree clean.

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
-> completion
```

## Active experiment — C128

Experiment: `C128-v5e-concurrent-recovery-ownership-falsification`.

Question: after restart leaves a receipt pending, can concurrent recovery workers establish exactly one owner so that only one worker may execute the C127 recovery plan?

Production primitive: `fold_lm.v05.recovery_ownership.RecoveryOwnershipRegistry`.

Fresh seeds: `20261481,20261482,20261483`. Worker counts: `2,4,8`.

Coverage per seed:

```text
1,440 concurrent recovery ownership cases
2 confirmed-none controls
1,442 scenarios total
```

Required semantics:

```text
naive ownership race      -> multiple winners detected
production ownership race -> exactly one owner
owner identity            -> exact winner
losing workers            -> zero recovery transition actions
owner release             -> exact owner only
APPLIED                    -> zero replay / complete once / one logical effect
NOT_APPLIED                -> one replay / complete once / one logical effect
STILL_UNKNOWN              -> zero replay / zero completion / pending retained
```

C127 remains a required control gate. All deciding rates are fixed at `1.0`.

Scope: C128 tests in-process Python-thread recovery ownership only. Owner death, lease expiry, takeover, stale-owner fencing and distributed ownership remain separate questions. Gate E remains NOT PASSED.

## Non-claims / separate tracks

- Shared-Basis auto-partition remains separate.
- Context/KV-replacement remains separate.
- Gate C/D and C97-C128 evidence is synthetic/scoped unless explicitly measured otherwise.
- Do not claim broad language quality, general epistemic self-knowledge, real-world tool selection, or general superiority over Transformer/LLM systems.
