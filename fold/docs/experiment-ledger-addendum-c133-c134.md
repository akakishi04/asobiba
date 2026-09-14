# FOLD experiment ledger addendum — C133 to C134

## C133 — ACCEPTED PASS

`C133-v5e-real-retrieval-vertical-integration` passed on fresh seeds `20261531..33`.

Focused regression was 76/76. Per seed, eight persisted-corpus retrieval cases passed. All deciding rates were `1.0`: learned `RETRIEVE` selection, exact persisted hit, source/index provenance validation, exactly-one evidence commit, post-commit `ANSWER`, evidence accuracy, exact/full-corpus search accounting, action invariance, and accepted C132 prerequisite. Protected C37 and fixture were preserved and the tracked tree remained clean.

C133 established the first V5-E vertical path through a real repository retrieval component:

```text
learned Control Lane
-> RETRIEVE
-> persisted JSON corpus
-> StructuralIndex exact search
-> provenance validation
-> evidence commit
-> reobserve
-> ANSWER
```

Scope remains controlled signatures/corpus; C133 did not test misses, wrong schema, stale corpus, bounded-LSH recall failure, or learned query formation.

## C134 — ACTIVE

Experiment: `C134-v5e-retrieval-miss-semantics`.

Question: when a real exact retrieval returns zero hits, does runtime treat that as no evidence rather than fabricate/commit a value, disable the exhausted `RETRIEVE` mechanism for the attempt, reobserve, and terminate `STOP_UNRESOLVED` when no other mechanism is available?

Fresh seeds: `20261541,20261542,20261543`.

Per seed: eight corpus records crossed with three case types = 24 cases:

```text
MATCH           -> one evidence commit -> ANSWER
STRUCTURE_MISS  -> zero hit/commit -> STOP_UNRESOLVED
WRONG_SCHEMA    -> zero hit/commit -> STOP_UNRESOLVED
```

All searches use `exact=True` and must report corpus/index provenance plus full-corpus scoring even on zero-hit outcomes. Accepted C133 is a summary-validated prerequisite and is not rerun as a heavy control. All deciding rates are fixed at `1.0`.

C134 changes no production runtime code. Bounded-LSH false-negative behavior, stale corpus, and learned query formation remain outside scope. Gate E remains NOT PASSED.
