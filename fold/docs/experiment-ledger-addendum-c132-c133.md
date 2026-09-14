# FOLD experiment ledger addendum — C132 to C133

## C132 — ACCEPTED PASS

`C132-v5e-os-process-sqlite-fencing-falsification` passed on fresh seeds `20261521..23`.

Focused regression was 73/73. Per seed, 18 independent-OS-process race cases covered worker counts `2/4/8`, modes `RESOLVED/UNKNOWN`, and three repetitions per worker/mode. All deciding rates were `1.0`: distinct process identity, exactly one takeover winner, higher fencing token, stale-process write rejection, resolved current-token mutation/state, unknown zero-write/empty-storage behavior, worker-specific rates, and C131 control preservation. Protected C37 and fixture were preserved and the tracked tree remained clean. No production runtime code was changed by C132.

## C133 — ACTIVE

Experiment: `C133-v5e-real-retrieval-vertical-integration`.

Question: when `READ_MEMORY` is unavailable and `RETRIEVE` is the least-burden available acquisition mechanism, can the learned V5-E Control Lane select `RETRIEVE`, invoke the repository's real `fold_reasoning.index.StructuralIndex` through a thin persisted-corpus runtime adapter, validate provenance, commit the retrieved evidence exactly once, reobserve, and select `ANSWER`?

Production adapter: `fold_lm.v05.retrieval_adapter.PersistedStructuralRetrievalAdapter`.

Persisted corpus fixture: `fold_lm/v05_benchmarks/fixtures/c133_structural_records.json`.

C133 deliberately uses `StructuralIndex.search(..., exact=True)` so the experiment isolates vertical wiring from approximate-LSH recall. Query signatures are supplied by task/runtime state; C133 does not claim learned query formation.

Fresh seeds: `20261531,20261532,20261533`. Eight persisted retrieval cases per seed. C132 is an accepted prerequisite checked by summary identity/status/gate rather than rerunning the expensive C132/C131 control stack.

Required rates at `1.0`: router RETRIEVE selection, persisted exact hit, source/index provenance validation, one evidence commit, post-commit ANSWER, final evidence accuracy, exact-search mode, full-corpus scoring, pre-retrieval action invariance, and accepted C132 prerequisite.

Progress output is required for each seed (`train start/done`) and each retrieval case (`case X/8`, `remaining=N`).

Scope: controlled persisted retrieval corpus and supplied signatures. Retrieval miss, wrong schema, stale corpus, bounded-LSH recall failure, natural-language query formation, and broad retrieval quality remain separate questions. Gate E remains NOT PASSED.
