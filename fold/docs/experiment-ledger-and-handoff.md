# FOLD Experiment Ledger and Handoff

> Current authoritative handoff. Detailed history is retained in Gate decisions and experiment-ledger addenda.

## Environment / protocol

- Repo: `akakishi04/asobiba`; branch `feat/sft-target-loss`; local `M:\asobiba\fold`.
- Python 3.13.15 / PyTorch 2.10.0+cu130 / CUDA 13.0 / RTX 4070 Ti SUPER.
- Protected C37 SHA256: `FD4A8DA897BDAEA9D103A252E30212C7FF842D23300D7C837333E146DEE51931`.
- Protected fixture SHA256: `A52F8209703149407580F7E2965B61B78653030EE992AF6D759865736741CA9E`.
- One scientific question per C number. Invalid executions retry the same C number.
- Long benchmarks expose seed/phase/case progress and remaining work.

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
-> learned acquisition request
-> real acquisition component
-> provenance / outcome validation
-> evidence commit only on validated evidence
-> reobserve
-> answer / further acquisition / unresolved
```

Runtime fault-tolerance hardening through C132 covers receipt binding/authority/scope, commit-context revalidation, replay suppression, atomic claim, crash recovery, concurrent recovery ownership, lease fencing/renewal, SQLite storage fencing, and independent-OS-process fencing.

C133-C135 moved RETRIEVE onto a real persisted corpus and `StructuralIndex`, established safe zero-hit semantics, and added exact recovery after bounded-LSH false negatives. C136 learned a fixed eight-address query head. C137 replaced the fixed address classes with shared content addressing and dynamic candidate-set growth.

## Accepted through C137

C137 `C137-v5e-content-addressed-corpus-growth` is ACCEPTED PASS: focused regression 87/87; fresh seeds `20261571..73`; training candidate count 8; evaluation candidate count 12; four entities had zero query-head training examples. All deciding rates were `1.0`, including known/unseen candidate selection, unseen/overall retrieval-key accuracy, provenance, exactly-one commit, post-commit `ANSWER`, final evidence accuracy, dynamic candidate growth, and accepted C136 prerequisite. Protected C37 and fixture were preserved and the tracked tree remained clean.

Scientific scope: C137 established dynamic content-addressed candidate selection, but every unseen validation query shared its unseen entity token with the matching record descriptor. It therefore did not establish semantic alias or compositional generalization.

Production content head: `fold_lm.v05.retrieval_content.SharedRetrievalContentHead`.
Production retrieval adapter: `fold_lm.v05.retrieval_adapter.PersistedStructuralRetrievalAdapter`.

## Active experiment — C138

Experiment: `C138-v5e-compositional-alias-generalization`.

Question: can the accepted C137 shared content head recombine learned query/descriptor attribute correspondences into held-out combinations when each validation query and matching record descriptor have zero lexical-token overlap?

C138 changes no production runtime code. It reuses the C137 content head and 12-record persisted corpus.

Training uses eight known three-attribute combinations. Query-side aliases and descriptor-side canonical terms are lexically disjoint. Four held-out evaluation records are new combinations of attribute values seen during training; every alias token used by those four queries appears somewhere in training, so only the combination is OOD.

```text
8 TRAIN_COMBINATION controls
4 UNSEEN_COMBINATION recombinations
12 live candidates
fresh seeds -> 20261581,20261582,20261583
```

Required at `1.0`: known-combination accuracy, unseen-combination accuracy, unseen/overall retrieval-key accuracy, provenance, exactly-one evidence commit, post-commit `ANSWER`, final evidence accuracy, zero lexical overlap, unseen-alias training coverage, negative-control nontriviality, dynamic candidate growth, and accepted C137 prerequisite.

The raw hashed-feature negative control must not solve all unseen combinations. A formally valid C138 FAIL is an accepted scientific negative result, not an execution failure; it would indicate that the current shared content head does not compositionally recombine learned alias correspondences under this controlled OOD split.

Progress reports router/content-head training, all twelve validation cases, and `remaining=N`. Gate E remains NOT PASSED.

## Non-claims

- Shared-Basis auto-partition remains separate.
- Context/KV replacement remains separate.
- `fold/fold_memory.py` is a QuadraticMemory numerical reference kernel, not the V5-E persistent memory store.
- Gate C/D and C97-C138 evidence remains scoped unless explicitly measured otherwise.
