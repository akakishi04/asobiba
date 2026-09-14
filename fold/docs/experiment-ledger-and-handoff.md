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

## Accepted through C136

C97-C123 established the synthetic information-sufficiency and six-action routing baseline plus runtime authority. C124-C132 hardened replay/crash/ownership/fencing/storage/process boundaries. C133 established the first real persisted-corpus retrieval vertical path. C134 established exact-search miss semantics. C135 established bounded-search false-negative recovery through exact escalation.

C136 `C136-v5e-learned-retrieval-query-formation` is ACCEPTED PASS: focused regression 84/84; fresh seeds `20261561..63`; eight held-out paraphrases per seed; all deciding rates `1.0`. The learned fixed-size query-address head mapped held-out query text to the correct one of eight addresses, then real persisted retrieval, provenance validation, exactly-one evidence commit and post-commit `ANSWER` all succeeded. C37 and fixture were preserved and the tracked tree remained clean.

C136 remains scoped: validation retained each address-specific codeword, the head has eight fixed output classes, and corpus growth / unseen entities were not established.

## Active experiment — C137

Experiment: `C137-v5e-content-addressed-corpus-growth`.

Question: can retrieval query formation move from a fixed eight-class address head to shared content addressing, so a head trained on eight entities can select correctly after the catalog grows to twelve records, including four entity labels never seen during head training?

Production component: `fold_lm.v05.retrieval_content.SharedRetrievalContentHead`.

```text
query text
-> hashed text features
-> shared residual content encoder
-> score current record descriptors
-> select candidate index from current catalog
-> dynamic one-hot retrieval structure
-> PersistedStructuralRetrievalAdapter exact search
-> provenance validation
-> evidence commit
-> Control Lane reobserve
-> ANSWER
```

Training catalog: `q0..q7` (8 entities, 3 query paraphrases each). Evaluation catalog: `q0..q11` (12 entities). New `q8..q11` entities have zero training paraphrases. Fresh seeds: `20261571,20261572,20261573`.

Required rates at `1.0`: Control Lane `RETRIEVE`, known-entity address accuracy, unseen-entity address accuracy, unseen-entity retrieval-key accuracy, overall retrieval-key accuracy, provenance validation, exactly-one evidence commit, post-commit `ANSWER`, final evidence accuracy, dynamic candidate-growth contract, and accepted C136 prerequisite.

Progress reports router train start/done, content-head train start/done, the 8->12 catalog-growth boundary, every evaluation case and `remaining=N`.

Scope: unseen entity labels share the same lexical token between query and record descriptor. C137 does not establish unseen semantic aliases, open-domain retrieval or general semantic embedding quality. Exact evidence retrieval remains the post-selection validation path. Gate E remains NOT PASSED.

## Non-claims

- Shared-Basis auto-partition remains separate.
- Context/KV replacement remains separate.
- `fold/fold_memory.py` is a QuadraticMemory numerical reference kernel, not the V5-E persistent memory store.
- Gate C/D and C97-C137 evidence remains scoped unless explicitly measured otherwise.
