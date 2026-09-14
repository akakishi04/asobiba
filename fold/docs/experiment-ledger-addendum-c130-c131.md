# FOLD experiment ledger addendum — C130 to C131

## C130 — ACCEPTED PASS

`C130-v5e-lease-renewal-boundary-falsification` passed on fresh seeds `20261501..03`.

Per seed: 1,442 scenarios including 1,440 renewal-boundary cases at renew ticks `1,3,4`. Focused regression was 67/67. All deciding rates were `1.0`: valid renewal, wrong-owner rejection, token preservation, expiry extension/no shortening, old-expiry takeover block, exact-expiry renewal rejection, exact-expiry takeover acceptance, higher takeover token, stale-token rejection, recovery outcome controls, timing-specific boundary rates, hidden trace invariance, and C129 control preservation. Protected C37 and fixture were preserved and the tracked tree remained clean.

## C131 — ACTIVE

Experiment: `C131-v5e-sqlite-storage-fencing-falsification`.

Question: can persistent storage itself enforce recovery fencing across independent SQLite transactions, so that after lease takeover only the current fencing token can mutate the stored recovery effect while every stale-token write is rejected?

Production primitive: `fold_lm.v05.sqlite_recovery_fencing.SqliteRecoveryFencingStore`.

Storage contract:

```text
SQLite journal mode  -> WAL
SQLite synchronous   -> FULL
lease acquire/takeover -> BEGIN IMMEDIATE transaction
fenced write           -> conditional SQL write against current owner/token/expiry
worker operations       -> independent SQLite connections
```

Fresh seeds: `20261511,20261512,20261513`. Worker counts: `2,4,8`.
Expected coverage per seed: 1,440 storage-fencing cases + 2 confirmed-none controls = 1,442 scenarios.

Required semantics include exactly one storage-authoritative takeover winner, strictly higher token, zero accepted stale writes, exactly one accepted current-token write for resolved outcomes, no stored effect for STILL_UNKNOWN, worker-specific takeover/stale-reject rates, hidden trace invariance, and C130 control preservation. All deciding rates are fixed at `1.0`.

Scope: C131 uses one local SQLite database file with independent transactions. It does not establish distributed-database consensus, independent OS-process behavior, power-loss durability, or filesystem-corruption tolerance. Lease expiry remains deterministic logical time. Gate E remains NOT PASSED.
