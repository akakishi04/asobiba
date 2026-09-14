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
-> acquisition execution
-> provenance / outcome validation
-> evidence commit
-> reobserve
-> answer / further acquisition / unresolved
```

Runtime fault-tolerance hardening through C132 additionally covers receipt binding/authority/scope, commit-context revalidation, replay suppression, atomic claim, crash recovery, concurrent recovery ownership, lease fencing/renewal, SQLite storage fencing, and independent-OS-process fencing.

## Accepted through C132

C97-C123 established the synthetic information-sufficiency and six-action routing baseline plus runtime authority. C124-C130 hardened replay, crash recovery, ownership, fencing and lease semantics. C131 established SQLite storage-enforced fencing across independent connections.

C132 `C132-v5e-os-process-sqlite-fencing-falsification` is ACCEPTED PASS: fresh seeds `20261521..23`; focused regression 73/73; 18 OS-process race cases per seed across workers `2/4/8`, modes `RESOLVED/UNKNOWN`, three repetitions; all deciding rates `1.0`; distinct worker PIDs confirmed; SQLite accepted only current fencing-token writes and rejected stale-process writes. C131 control passed. C37 and fixture were preserved and the tracked tree was clean. C132 changed no production runtime code.

## Active experiment — C133

Experiment: `C133-v5e-real-retrieval-vertical-integration`.

Strategic pivot: stop extending synthetic/runtime fault-tolerance depth for now and connect an actual repository retrieval component to the learned Control Lane.

Question: when `READ_MEMORY` is unavailable and `RETRIEVE` is the least-burden available mechanism, can the learned Control Lane select `RETRIEVE`, invoke the real `fold_reasoning.index.StructuralIndex` through a persisted-corpus adapter, validate provenance, commit evidence exactly once, reobserve, and select `ANSWER`?

Production adapter: `fold_lm.v05.retrieval_adapter.PersistedStructuralRetrievalAdapter`.
Persisted fixture: `fold_lm/v05_benchmarks/fixtures/c133_structural_records.json`.

Fresh seeds: `20261531,20261532,20261533`. Eight retrieval cases per seed = 24 total actual retrieval cases. C132 is validated as an accepted prerequisite by summary identity/status/gate; its expensive control stack is not rerun.

C133 uses `StructuralIndex.search(..., exact=True)` to isolate vertical integration from approximate-LSH recall. Required rates at `1.0`: RETRIEVE selection, persisted exact hit, source/index provenance validation, exactly-one evidence commit, post-commit ANSWER, evidence accuracy, exact-mode/full-corpus scoring, pre-retrieval action invariance, and accepted C132 prerequisite.

Progress output: each seed reports `train start/done`; every retrieval case reports `case X/8` and `remaining=N`.

Scope: controlled persisted corpus with supplied structural/semantic signatures. C133 does not establish learned query formation, natural-language retrieval quality, bounded-LSH recall, retrieval miss handling, wrong-schema handling, or stale-corpus handling. Gate E remains NOT PASSED.

## Non-claims

- Shared-Basis auto-partition remains separate.
- Context/KV replacement remains separate.
- `fold/fold_memory.py` is a QuadraticMemory numerical reference kernel, not the V5-E persistent memory store.
- Gate C/D and C97-C133 evidence remains scoped unless explicitly measured otherwise.
