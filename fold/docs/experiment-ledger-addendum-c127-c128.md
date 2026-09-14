# FOLD experiment ledger addendum — C127 to C128

## C127 — ACCEPTED PASS

`C127-v5e-post-transition-crash-falsification` passed on fresh seeds `20261471..73`.

Per seed: 1,442 scenarios, including 1,440 post-transition crash cases across 1/2/3 restarts. APPLIED caused zero replay and one completion with one known logical effect. NOT_APPLIED replayed exactly once with the same key, then completed with one known logical effect. STILL_UNKNOWN performed zero replay and zero completion, preserved pending state, and deliberately left logical effect count unasserted. C126 remained passing, duplicate claims were rejected, hidden traces remained invariant, and a naive pending-replay negative control exposed duplicate-effect risk. Protected C37 and fixture were preserved; tracked tree was clean.

## C128 — ACTIVE

`C128-v5e-concurrent-recovery-ownership-falsification` tests concurrent ownership of one pending recovery after restart.

Fresh seeds: `20261481,20261482,20261483`. Worker counts: `2,4,8`. Expected coverage: 1,442 scenarios per seed, including 1,440 concurrent recovery cases.

Required: naive ownership race detected; production ownership has exactly one winner; loser workers execute no recovery transition; only the exact owner may release ownership; C127 outcome semantics remain exact. All deciding rates are fixed at `1.0`.

Scope is in-process Python-thread ownership. Owner death, takeover, fencing and distributed ownership remain separate questions. Gate E remains NOT PASSED.
