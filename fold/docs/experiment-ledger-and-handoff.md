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

## Accepted through C133

C97-C123 established the synthetic information-sufficiency and six-action routing baseline plus runtime authority. C124-C132 hardened replay/crash/ownership/fencing/storage/process boundaries.

C133 `C133-v5e-real-retrieval-vertical-integration` is ACCEPTED PASS: focused regression 76/76; fresh seeds `20261531..33`; eight persisted-corpus retrieval cases per seed; all deciding rates `1.0`; C37 and fixture preserved; tracked tree clean.

C133 established the first real retrieval vertical path:

```text
Control Lane chooses RETRIEVE
-> persisted JSON corpus
-> fold_reasoning.index.StructuralIndex exact search
-> source SHA + index fingerprint validation
-> evidence commit exactly once
-> reobserve
-> ANSWER
```

Production adapter: `fold_lm.v05.retrieval_adapter.PersistedStructuralRetrievalAdapter`.

## Active experiment — C134

Experiment: `C134-v5e-retrieval-miss-semantics`.

Question: when the real exact retrieval component returns zero hits, does runtime preserve the distinction between “no evidence found” and evidence, commit nothing, disable the exhausted `RETRIEVE` mechanism for the attempt, reobserve, and stop unresolved when no other acquisition mechanism is available?

Fresh seeds: `20261541,20261542,20261543`.

Per seed: 24 real retrieval cases from eight persisted records crossed with:

```text
MATCH           -> exactly one commit -> ANSWER
STRUCTURE_MISS  -> zero hit / zero commit -> STOP_UNRESOLVED
WRONG_SCHEMA    -> zero hit / zero commit -> STOP_UNRESOLVED
```

All searches use `StructuralIndex.search(..., exact=True)` so C134 isolates zero-hit semantics from approximate-retrieval recall. Search stats must retain source SHA/index fingerprint and full-corpus scoring even on zero-hit outcomes. Accepted C133 is validated by summary identity/status/gate and is not rerun as an expensive control.

Progress output: each seed reports train start/done; every case reports `case X/24`, case type, key, pass/fail and `remaining=N`.

C134 modifies no production runtime code. Bounded-LSH false negatives, stale corpus, natural-language retrieval quality and learned query formation remain outside C134. Gate E remains NOT PASSED.

## Non-claims

- Shared-Basis auto-partition remains separate.
- Context/KV replacement remains separate.
- `fold/fold_memory.py` is a QuadraticMemory numerical reference kernel, not the V5-E persistent memory store.
- Gate C/D and C97-C134 evidence remains scoped unless explicitly measured otherwise.
