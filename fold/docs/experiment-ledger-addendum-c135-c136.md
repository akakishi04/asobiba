# FOLD experiment ledger addendum — C135 to C136

## C135 — ACCEPTED PASS

`C135-v5e-bounded-retrieval-exact-recovery` passed on fresh seeds `20261551..53`.

Focused regression was 81/81. Per seed, four real retrieval cases passed: `BOUNDED_HIT`, `BOUNDED_FALSE_NEGATIVE`, `TRUE_MISS`, and `WRONG_SCHEMA`. All deciding rates were `1.0`. The real current LSH false negative for `q6` was detected under `scan_limit=1, probes=1`, escalated to exact search, recovered with provenance intact, committed exactly once, and answered. True exact misses and wrong-schema cases remained zero-commit unresolved outcomes. Protected C37 and fixture were preserved and the tracked tree remained clean.

C135 established the correctness policy:

```text
bounded hit -> use it without exact fallback
bounded zero hit -> exact recovery search
exact hit -> validate provenance -> commit -> ANSWER
exact miss -> zero commit -> STOP_UNRESOLVED
```

Scope remains controlled corpus/signatures; C135 did not establish learned query formation or open-domain retrieval quality.

## C136 — ACTIVE

Experiment: `C136-v5e-learned-retrieval-query-formation`.

Question: can a small learned query-address head derive the retrieval address from a held-out natural-language paraphrase, without receiving the evidence value or a ready-made target structure, and then drive the accepted real retrieval path through persisted corpus, provenance validation, evidence commit, reobserve, and `ANSWER`?

Production component: `fold_lm.v05.retrieval_query.RetrievalAddressHead` with deterministic hashed text features.

Fixtures:

- `fold_lm/v05_benchmarks/fixtures/c136_query_records.json`
- `fold_lm/v05_benchmarks/fixtures/c136_query_paraphrases.json`

The C136 corpus uses eight one-hot structural addresses, identical neutral semantic signatures, and evidence values deliberately separated from the query-address head. Each address has three training paraphrases and one held-out validation paraphrase. The validation path uses only the head-predicted address to form the structural signature; the expected address is evaluator-only.

Fresh seeds: `20261561,20261562,20261563`.

Per seed: eight held-out paraphrase cases. Required rates at `1.0`: Control Lane `RETRIEVE`, held-out query-address accuracy, retrieved-key accuracy, provenance validation, exactly-one evidence commit, post-commit `ANSWER`, final evidence accuracy, full exact-corpus scoring, and accepted C135 prerequisite.

Progress output reports router training, query-head training, every validation case, and remaining count.

Scope: controlled eight-address language-to-retrieval task. The held-out paraphrases retain the address-specific codeword seen in training. C136 does not establish open-domain semantic query formation, unseen-entity generalization, free continuous-signature generation, or corpus-growth generalization. Gate E remains NOT PASSED.
