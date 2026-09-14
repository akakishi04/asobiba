# FOLD Experiment Ledger and Handoff

> Current authoritative handoff. Detailed history is retained in Gate decisions and experiment-ledger addenda.

## Environment / protocol

- Repo: `akakishi04/asobiba`
- Branch: `feat/sft-target-loss`
- Local: `M:\asobiba\fold`
- Python 3.13.15 / PyTorch 2.10.0+cu130 / CUDA 13.0 / RTX 4070 Ti SUPER
- Protected C37 SHA256: `FD4A8DA897BDAEA9D103A252E30212C7FF842D23300D7C837333E146DEE51931`
- Protected fixture SHA256: `A52F8209703149407580F7E2965B61B78653030EE992AF6D759865736741CA9E`
- One scientific question per C number. Invalid execution retries keep the same C number.

## Gate status

- Gate A: PASSED
- Gate B: PASSED
- Gate C: PASSED, scoped
- Gate D: PASSED, scoped
- Gate E: NOT PASSED; active

Gate C lead: `W_module = W_base + A_module @ B_shared`.
Gate D lead: `fold_lm.v05.controller.ControlLaneActionRouter`.
Primary product priority: operational VRAM headroom, then peak/resident VRAM, latency/throughput, artifact size.

## V5-E runtime chain

```text
model/router proposal
-> authoritative availability / permission
-> outcome validation
-> receipt binding / authority / scope
-> commit-context revalidation
-> replay suppression / atomic claim
-> pending/completed recovery state
-> post-transition reconciliation
-> concurrent recovery ownership
-> lease takeover + fencing token
-> lease renewal / expiry boundary
-> storage-enforced fenced mutation
-> completion
```

## Accepted through C130

C97-C107 established the synthetic information-sufficiency and routing baseline. C108 was a valid negative on arbitrary signed boolean amplitudes; C109-C111 repaired it with schema-aware canonicalization. C112-C123 hardened sampling, eligibility, preflight, failure handling, reconciliation, receipt authority/scope and commit-context revalidation. C124-C130 progressively established replay suppression, atomic receipt claim, restart recovery, post-transition crash recovery, recovery ownership, lease fencing and lease-renewal boundary semantics.

C130: fresh seeds `20261501..03`; 1,442 scenarios per seed; renewal ticks `1,3,4`; all deciding rates `1.0`; focused regression 67/67; C37 and fixture preserved; tracked tree clean.

## Active experiment — C131

Experiment: `C131-v5e-sqlite-storage-fencing-falsification`.

Question: after lease takeover, can persistent SQLite storage reject every stale fencing token and allow only the current owner/token to mutate recovery state across independent database connections?

Production primitive: `fold_lm.v05.sqlite_recovery_fencing.SqliteRecoveryFencingStore`.

Storage semantics:

```text
journal mode       -> WAL
synchronous        -> FULL
acquire/takeover   -> BEGIN IMMEDIATE transaction
fenced mutation    -> conditional SQL against current owner/token/expiry
connection model   -> independent connection per operation
```

Fresh seeds: `20261511,20261512,20261513`. Worker counts: `2,4,8`.
Coverage per seed: 1,440 storage-fencing cases + 2 confirmed-none controls = 1,442 scenarios.

Required rates at `1.0`: C130 control preservation, single storage-authoritative takeover, higher fencing token, stale-write rejection, current-write acceptance/state for resolved outcomes, zero write / empty effect state for STILL_UNKNOWN, worker-specific takeover/stale-reject rates, confirmed-none STOP and hidden trace invariance.

Scope: one local SQLite file with independent transactions. Distributed databases, separate OS processes, power-loss durability and filesystem corruption remain outside C131. Lease expiry remains deterministic logical time. Gate E remains NOT PASSED.

## Non-claims

- Shared-Basis auto-partition remains separate.
- Context/KV replacement remains separate.
- Gate C/D and C97-C131 evidence remains synthetic/scoped unless explicitly measured otherwise.
