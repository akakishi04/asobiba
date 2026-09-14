# FOLD Experiment Ledger and Handoff

> Current authoritative handoff. Detailed history is retained in Gate decisions and experiment-ledger addenda.

## Environment / protocol

- Repo: `akakishi04/asobiba`; branch `feat/sft-target-loss`; local `M:\asobiba\fold`.
- Python 3.13.15 / PyTorch 2.10.0+cu130 / CUDA 13.0 / RTX 4070 Ti SUPER.
- Protected C37 SHA256: `FD4A8DA897BDAEA9D103A252E30212C7FF842D23300D7C837333E146DEE51931`.
- Protected fixture SHA256: `A52F8209703149407580F7E2965B61B78653030EE992AF6D759865736741CA9E`.
- One scientific question per C number. Invalid executions retry the same C number.
- Long benchmarks must expose seed/phase/case progress and remaining work.

## Gate status

- Gate A: PASSED
- Gate B: PASSED
- Gate C: PASSED, scoped
- Gate D: PASSED, scoped
- Gate E: NOT PASSED; active

Primary product priority: operational VRAM headroom, then peak/resident VRAM, latency/throughput, artifact size.

## V5-E current architecture

```text
learned Control Lane
-> runtime-authoritative availability / permission
-> learned or runtime-formed acquisition request
-> real acquisition component
-> provenance / outcome validation
-> evidence commit only on validated evidence
-> reobserve
-> answer / further acquisition / unresolved
```

Runtime fault-tolerance hardening through C132 additionally covers receipt binding/authority/scope, commit-context revalidation, replay suppression, atomic claim, crash recovery, concurrent recovery ownership, lease fencing/renewal, SQLite storage fencing, and independent-OS-process fencing.

## Accepted through C135

C97-C123 established the synthetic information-sufficiency and six-action routing baseline plus runtime authority. C124-C132 hardened replay/crash/ownership/fencing/storage/process boundaries. C133 established the first real persisted-corpus retrieval vertical path. C134 established exact-search miss semantics. C135 established bounded-search false-negative recovery through exact escalation.

C135 `C135-v5e-bounded-retrieval-exact-recovery` is ACCEPTED PASS: focused regression 81/81; fresh seeds `20261551..53`; four cases per seed (`BOUNDED_HIT`, `BOUNDED_FALSE_NEGATIVE`, `TRUE_MISS`, `WRONG_SCHEMA`); all deciding rates `1.0`. The real current `StructuralIndex` bounded false negative for `q6` was recovered by exact search with provenance intact, exactly-one evidence commit and `ANSWER`. True misses and wrong-schema cases remained zero-commit unresolved outcomes. C37 and fixture were preserved and the tracked tree remained clean.

Production retrieval adapter: `fold_lm.v05.retrieval_adapter.PersistedStructuralRetrievalAdapter`.

## Active experiment — C136

Experiment: `C136-v5e-learned-retrieval-query-formation`.

Strategic question: can FOLD move beyond a runtime-supplied ready-made retrieval signature and learn the retrieval address from query text itself, while preserving the accepted real retrieval/evidence path?

Production component: `fold_lm.v05.retrieval_query.RetrievalAddressHead` plus deterministic signed hashed-text features.

C136 uses a dedicated eight-record persisted corpus with one-hot structural addresses, neutral shared semantic signatures, and evidence values that are not inputs to the query head. Each address has three training paraphrases and one held-out validation paraphrase.

```text
held-out query text
-> learned RetrievalAddressHead
-> predicted discrete address
-> address_to_structure
-> PersistedStructuralRetrievalAdapter exact search
-> provenance validation
-> evidence commit exactly once
-> Control Lane reobserve
-> ANSWER
```

Fresh seeds: `20261561,20261562,20261563`. Eight held-out validation cases per seed.

Required rates at `1.0`: Control Lane `RETRIEVE`, held-out query-address accuracy, retrieved-key accuracy, provenance validation, exactly-one evidence commit, post-commit `ANSWER`, final evidence accuracy, full-corpus exact scoring, and accepted C135 prerequisite.

Progress output reports router train start/done, query-head train start/done, every validation case and `remaining=N`.

Scope: controlled eight-address language-to-retrieval task. Held-out paraphrases keep the address-specific codeword seen during training. C136 does not establish open-domain semantic query formation, unseen-entity generalization, free continuous-signature generation, or corpus-growth generalization. Gate E remains NOT PASSED.

## Non-claims

- Shared-Basis auto-partition remains separate.
- Context/KV replacement remains separate.
- `fold/fold_memory.py` is a QuadraticMemory numerical reference kernel, not the V5-E persistent memory store.
- Gate C/D and C97-C136 evidence remains scoped unless explicitly measured otherwise.
