# FOLD Experiment Ledger and Handoff

> Current authoritative handoff. Detailed history is retained in Gate decisions and experiment-ledger addenda.

## Environment / protocol

- Repo: `akakishi04/asobiba`; branch `feat/sft-target-loss`; local `M:\asobiba\fold`.
- Python 3.13.15 / PyTorch 2.10.0+cu130 / CUDA 13.0 / RTX 4070 Ti SUPER.
- Protected C37 SHA256: `FD4A8DA897BDAEA9D103A252E30212C7FF842D23300D7C837333E146DEE51931`.
- Protected fixture SHA256: `A52F8209703149407580F7E2965B61B78653030EE992AF6D759865736741CA9E`.
- One scientific question per C number. Invalid executions retry the same C number.
- Valid negative results close their C number and may advance.
- Long benchmarks expose seed/phase/case progress and remaining work.
- Conversation, execution-command, formal-verdict, and cross-chat handoff responses for `C###` experiments follow `docs/experiment-conversation-handoff-protocol.md`. A new chat should read `AGENTS.md`, that protocol, and this handoff before continuing the active C number.

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

C133-C135 moved RETRIEVE onto a real persisted corpus and `StructuralIndex`, established safe zero-hit semantics, and added exact recovery after bounded-LSH false negatives. C136 learned fixed-address query formation. C137 replaced fixed output classes with shared content addressing and dynamic candidate-set growth.

## Accepted through C138

C137 `C137-v5e-content-addressed-corpus-growth` is ACCEPTED PASS: focused regression 87/87; fresh seeds `20261571..73`; candidate set expanded from 8 to 12 after training; four entities had zero query-head training examples; all deciding rates were `1.0`.

C138 `C138-v5e-compositional-alias-generalization` is ACCEPTED VALID NEGATIVE: focused regression 90/90; fresh seeds `20261581..83`; eight known combinations remained `1.0`, but four held-out recombinations were only `0.25` accurate on every seed. Overall scenario/retrieval/evidence accuracy was `0.75`. Provenance, exactly-one commit, post-commit `ANSWER`, zero paired lexical overlap, alias-token training coverage, candidate growth, prerequisite identity, protected artifacts and tracked-tree postchecks were all valid. C138 modified no production code.

C138 therefore proves that the current encoded/trained path does not reliably generalize these held-out combinations. It does **not** yet isolate the cause.

Post-result audit found a material front-end confound: `hashed_text_features(feature_dim=128)` uses one signed hash bucket per token, and the C138 training vocabulary has real collisions. Notably `amber` and canonical `red` collide exactly; this is consistent with the repeated `q11 -> q1` error. Other collisions exist as well. This does not invalidate C138, but it blocks a clean claim that the shared content head alone caused the compositional failure.

Production content head: `fold_lm.v05.retrieval_content.SharedRetrievalContentHead`.
Production retrieval adapter: `fold_lm.v05.retrieval_adapter.PersistedStructuralRetrievalAdapter`.

## Active experiment — C139

Experiment: `C139-v5e-hash-collision-composition-diagnostic`.

Question: does the C138 held-out-combination failure persist after removing token hash collisions, with the pooled bag representation, `SharedRetrievalContentHead`, train/evaluation split, and learning objective otherwise preserved?

C139 changes no production runtime code. It constructs a collision-free one-dimension-per-token diagnostic representation from **training vocabulary only**. Validation and all 12 evaluation descriptors must be zero-OOV under that vocabulary. The live retrieval/evidence path remains the same persisted 12-record C137 corpus and exact retrieval.

Fresh seeds: `20261591,20261592,20261593`.

```text
8 TRAIN_COMBINATION controls
4 UNSEEN_COMBINATION recombinations
12 live candidates
same pooled SharedRetrievalContentHead
collision-free training-vocabulary bag features
```

Required at `1.0`: known/unseen combination accuracy, unseen/overall retrieval-key accuracy, provenance, exactly-one commit, post-commit `ANSWER`, final evidence accuracy, collision-free/OOV control, reproduced-C138-collision control, raw-baseline nontriviality, dynamic candidate growth, and accepted valid-negative C138 prerequisite.

Interpretation:

- PASS -> C138 single-bucket hashing was a material causal confound in this controlled task.
- FAIL -> compositional failure persists after collision removal; pooled representation/head structure becomes the stronger suspect.

C139 is diagnostic only; its vocabulary-basis encoder is not a scalable production tokenizer design. Gate E remains NOT PASSED.

## Non-claims

- Shared-Basis auto-partition remains separate.
- Context/KV replacement remains separate.
- `fold/fold_memory.py` is a QuadraticMemory numerical reference kernel, not the V5-E persistent memory store.
- Gate C/D and C97-C139 evidence remains scoped unless explicitly measured otherwise.
