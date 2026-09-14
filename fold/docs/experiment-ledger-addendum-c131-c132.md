# FOLD experiment ledger addendum — C131 to C132

## C131 — ACCEPTED PASS

`C131-v5e-sqlite-storage-fencing-falsification` passed on the valid retry with fresh seeds `20261511..13`.

Per seed: 1,442 scenarios including 1,440 SQLite storage-fencing cases across 2/4/8 workers. Focused regression was 71/71. All deciding rates were `1.0`: single storage-authoritative takeover, higher fencing token, zero accepted stale writes, resolved current-token write/state, STILL_UNKNOWN zero-write/empty-storage behavior, worker-specific takeover/stale-reject rates, and C130 control preservation. SQLite reported version `3.50.4`, using WAL journal mode and FULL synchronous mode. Protected C37 and fixture were preserved and the tracked tree remained clean.

The first C131 attempt was invalid before scientific evaluation because Windows could not delete temporary SQLite files while initialization connections remained open, and the benchmark runner contained an import-path typo. The retry preserved the same seeds and scientific thresholds.

## C132 — ACTIVE

Experiment: `C132-v5e-os-process-sqlite-fencing-falsification`.

Question: does the accepted C131 SQLite fencing contract still hold when takeover and fenced writes are issued by independent OS processes rather than Python threads in one process?

C132 reuses the C131 production primitive unchanged. No new production runtime primitive is introduced.

Fresh seeds: `20261521,20261522,20261523`.

Process-race matrix per seed:

```text
worker counts  -> 2,4,8
modes          -> RESOLVED, UNKNOWN
repetitions    -> 3 per worker/mode
cases          -> 18 OS-process race cases
```

Each case launches independent Python subprocesses for both the lease-takeover phase and the fenced-write phase. Every worker must have a distinct PID from the parent and from its competitors.

Required semantics: C131 fresh-seed control preserved; exactly one process wins takeover; token advances from 1 to 2; every stale-token process write is rejected by SQLite; RESOLVED accepts exactly one current-token write and stores token 2; UNKNOWN accepts no write and stores no effect row; worker-specific rates are all `1.0`.

Scope: one Windows host and one local SQLite file. Network partitions, distributed consensus, power-loss durability, filesystem corruption, and real-clock lease semantics remain outside C132. Gate E remains NOT PASSED.
