# FOLD Experiment Ledger and Handoff

> Current authoritative handoff. Detailed history is retained in Gate decisions and experiment-ledger addenda.

## Environment / protocol

- Repo: `akakishi04/asobiba`; branch `feat/sft-target-loss`; local `M:\asobiba\fold`.
- Python 3.13.15 / PyTorch 2.10.0+cu130 / CUDA 13.0 / RTX 4070 Ti SUPER.
- Protected C37 SHA256: `FD4A8DA897BDAEA9D103A252E30212C7FF842D23300D7C837333E146DEE51931`.
- Protected fixture SHA256: `A52F8209703149407580F7E2965B61B78653030EE992AF6D759865736741CA9E`.
- One scientific question per C number. Invalid executions retry the same C number.

## Gate status

- Gate A: PASSED
- Gate B: PASSED
- Gate C: PASSED, scoped
- Gate D: PASSED, scoped
- Gate E: NOT PASSED; active

Primary product priority: operational VRAM headroom, then peak/resident VRAM, latency/throughput, artifact size.

## V5-E runtime / recovery chain

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
-> lease fencing + renewal boundary
-> storage-enforced fenced mutation
-> completion
```

## Accepted through C131

C97-C123 established the synthetic information-sufficiency, learned routing, representation canonicalization, authoritative preflight/failure handling, reconciliation, receipt authority/scope, and commit-context chain. C124-C130 hardened replay suppression, atomic receipt claim, restart recovery, post-transition crash recovery, recovery ownership, fencing tokens, and lease-renewal boundaries.

C131 valid retry: `C131-v5e-sqlite-storage-fencing-falsification`; fresh seeds `20261511..13`; 1,442 scenarios per seed with 1,440 storage-fencing cases across 2/4/8 workers; all deciding rates `1.0`; focused regression 71/71; SQLite `3.50.4`, WAL/FULL; C37 and fixture preserved; tracked tree clean. The first C131 attempt was invalid before scientific evaluation due to a Windows SQLite-handle cleanup bug and a benchmark import typo; the retry kept the same scientific settings.

## Active experiment — C132

Experiment: `C132-v5e-os-process-sqlite-fencing-falsification`.

Question: does the accepted C131 SQLite fencing contract still hold when lease takeover and fenced mutations are issued by independent OS processes instead of threads in one process?

C132 reuses `fold_lm.v05.sqlite_recovery_fencing.SqliteRecoveryFencingStore` unchanged; no new production primitive is introduced.

Fresh seeds: `20261521,20261522,20261523`.

Per-seed OS-process matrix:

```text
workers       -> 2,4,8
modes         -> RESOLVED, UNKNOWN
repetitions   -> 3 per worker/mode
process cases -> 18
```

C131 is re-evaluated as a fresh-seed control. For every C132 case, takeover and write phases launch separate Python subprocesses. Required rates at `1.0`: C131 control, process identity, single takeover, higher token, stale-write rejection, RESOLVED current-write/state, UNKNOWN zero-write/empty-storage, and worker-specific process pass/takeover/stale-reject rates.

Scope: one Windows host and one local SQLite file. Distributed consensus, network partitions, power-loss durability, filesystem corruption, and real-clock lease behavior remain outside C132. Gate E remains NOT PASSED.

## Non-claims

- Shared-Basis auto-partition remains separate.
- Context/KV replacement remains separate.
- Gate C/D and C97-C132 evidence remains scoped unless explicitly measured otherwise.
