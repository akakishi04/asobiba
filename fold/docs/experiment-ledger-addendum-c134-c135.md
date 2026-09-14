# FOLD experiment ledger addendum — C134 to C135

## C134 — ACCEPTED PASS

`C134-v5e-retrieval-miss-semantics` passed on fresh seeds `20261541..43`.

Focused regression was 78/78. Per seed, 24 exact-search cases passed: eight `MATCH`, eight `STRUCTURE_MISS`, and eight `WRONG_SCHEMA`. All deciding rates were `1.0`: learned `RETRIEVE` selection, match control, zero hit and zero evidence commit on misses, `STOP_UNRESOLVED` after retrieval exhaustion, safe structure-miss/wrong-schema handling, retrieval provenance stats, and accepted C133 prerequisite. Protected C37 and fixture were preserved and the tracked tree remained clean.

C134 established that a real exact-search zero hit is not converted into evidence.

## C135 — ACTIVE

Experiment: `C135-v5e-bounded-retrieval-exact-recovery`.

Question: when bounded LSH returns a false-negative zero hit for evidence that exact search can recover, can runtime treat that bounded miss as non-authoritative, escalate to exact search, validate provenance, commit recovered evidence exactly once, reobserve, and answer; while true exact misses still remain zero-commit unresolved outcomes?

Production extension: `PersistedStructuralRetrievalAdapter.retrieve_with_exact_recovery` plus bounded search parameters on `retrieve`.

Fresh seeds: `20261551,20261552,20261553`.

Per seed four cases:

```text
BOUNDED_HIT            -> bounded result accepted; exact not attempted
BOUNDED_FALSE_NEGATIVE -> bounded zero hit; exact recovers q6; commit once; ANSWER
TRUE_MISS              -> bounded zero hit; exact zero hit; zero commit; STOP_UNRESOLVED
WRONG_SCHEMA           -> bounded zero hit; exact zero hit; zero commit; STOP_UNRESOLVED
```

The false negative is produced by the existing `StructuralIndex` behavior, not by deleting a result: with the persisted eight-record corpus, `q5` and `q6` collide in the first LSH table; `q6` with `scan_limit=1, probes=1` scores only `q5` in the bounded pass, yielding zero valid hits, while exact search recovers `q6`.

Accepted C134 is validated by summary identity/status/gate and is not rerun as a heavy control. Progress reports train start/done and every case with remaining count.

All deciding rates are fixed at `1.0`. C135 does not claim scalable exact fallback, learned retrieval-budget selection, natural-language query formation, or open-domain retrieval quality. Gate E remains NOT PASSED.
