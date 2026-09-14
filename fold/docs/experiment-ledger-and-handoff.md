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
-> real acquisition component
-> provenance / outcome validation
-> evidence commit only on validated evidence
-> reobserve
-> answer / further acquisition / unresolved
```

Runtime fault-tolerance hardening through C132 additionally covers receipt binding/authority/scope, commit-context revalidation, replay suppression, atomic claim, crash recovery, concurrent recovery ownership, lease fencing/renewal, SQLite storage fencing, and independent-OS-process fencing.

## Accepted through C134

C97-C123 established the synthetic information-sufficiency and six-action routing baseline plus runtime authority. C124-C132 hardened replay/crash/ownership/fencing/storage/process boundaries. C133 established the first real retrieval vertical path through persisted corpus + `StructuralIndex` + provenance validation + evidence commit + reobserve + `ANSWER`.

C134 `C134-v5e-retrieval-miss-semantics` is ACCEPTED PASS: focused regression 78/78; fresh seeds `20261541..43`; 24 exact-search cases per seed (`MATCH`, `STRUCTURE_MISS`, `WRONG_SCHEMA` across eight records); all deciding rates `1.0`; zero-hit outcomes committed no evidence and ended `STOP_UNRESOLVED` after `RETRIEVE` exhaustion. C37 and fixture were preserved and the tracked tree remained clean. C134 changed no production runtime code.

Production retrieval adapter: `fold_lm.v05.retrieval_adapter.PersistedStructuralRetrievalAdapter`.
Persisted fixture: `fold_lm/v05_benchmarks/fixtures/c133_structural_records.json`.

## Active experiment — C135

Experiment: `C135-v5e-bounded-retrieval-exact-recovery`.

Question: when bounded LSH returns a false-negative zero hit for evidence that exact search can recover, can runtime treat the bounded miss as non-authoritative, escalate to exact search, validate provenance, commit recovered evidence exactly once, reobserve, and `ANSWER`, while true exact misses remain zero-commit unresolved outcomes?

Production extension: `PersistedStructuralRetrievalAdapter.retrieve_with_exact_recovery` and explicit bounded-search parameters on `retrieve`.

Fresh seeds: `20261551,20261552,20261553`.

Per seed four cases:

```text
BOUNDED_HIT            -> bounded hit; exact not attempted; commit once; ANSWER
BOUNDED_FALSE_NEGATIVE -> q6 bounded miss at scan_limit=1/probes=1; exact recovers; commit once; ANSWER
TRUE_MISS              -> bounded miss; exact miss; zero commit; STOP_UNRESOLVED
WRONG_SCHEMA           -> bounded miss; exact miss; zero commit; STOP_UNRESOLVED
```

The false negative comes from the real current `StructuralIndex` LSH layout: `q5` and `q6` collide in the first table; the one-entry scan sees `q5` before `q6`, so bounded retrieval returns zero valid hits for `q6`, while exact search finds it.

Accepted C134 is validated by summary identity/status/gate and is not rerun as a heavy control. Progress reports seed train start/done plus every case and remaining count. All deciding rates are fixed at `1.0`.

Scope: controlled persisted corpus/signatures. C135 does not establish scalable exact fallback, learned retrieval-budget selection, natural-language query formation, stale-corpus handling, or open-domain retrieval quality. Gate E remains NOT PASSED.

## Non-claims

- Shared-Basis auto-partition remains separate.
- Context/KV replacement remains separate.
- `fold/fold_memory.py` is a QuadraticMemory numerical reference kernel, not the V5-E persistent memory store.
- Gate C/D and C97-C135 evidence remains scoped unless explicitly measured otherwise.
