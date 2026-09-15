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

## Accepted through C139

C137 `C137-v5e-content-addressed-corpus-growth` is ACCEPTED PASS: focused regression 87/87; fresh seeds `20261571..73`; candidate set expanded from 8 to 12 after training; four entities had zero query-head training examples; all deciding rates were `1.0`.

C138 `C138-v5e-compositional-alias-generalization` is ACCEPTED VALID NEGATIVE: focused regression 90/90; fresh seeds `20261581..83`; eight known combinations remained `1.0`, but four held-out recombinations were only `0.25` accurate on every seed. Overall scenario/retrieval/evidence accuracy was `0.75`. Postchecks and retrieval/evidence authority controls were valid. A post-result audit identified real token-hash collisions in the 128-dimensional hashed text front end, including `amber` / canonical `red`, so C138 did not isolate the shared content head as the sole cause.

C139 `C139-v5e-hash-collision-composition-diagnostic` is ACCEPTED VALID NEGATIVE: focused regression 93/93; fresh seeds `20261591..93`; 49-dimensional collision-free training-vocabulary features; zero evaluation OOV; six old C138 collision buckets reproduced as a control; known combinations remained `1.0` on every seed. Held-out recombination accuracy was `1.0, 0.5, 1.0` (mean `0.833333`, median `1.0`) versus C138's `0.25` on every seed. Seed `20261592` missed `q10` and `q11`; the other two seeds solved all four held-out recombinations. Overall retrieval/evidence accuracy was `0.944444` mean. Protected artifacts, tracked tree, prerequisite identity, provenance, exactly-one commit and post-commit `ANSWER` remained valid. C139 modified no production code.

C139 fails its preregistered all-seed `1.0` criterion, so collision removal alone is not accepted as a robust solution. However, the two perfect seeds show that the unchanged pooled representation plus `SharedRetrievalContentHead` is not strictly incapable of representing a solution on this finite controlled task. The improvement relative to C138 is consistent with hash collision being a material contributor, but C139 does not establish it as the sole cause.

Production content head: `fold_lm.v05.retrieval_content.SharedRetrievalContentHead`.
Production retrieval adapter: `fold_lm.v05.retrieval_adapter.PersistedStructuralRetrievalAdapter`.

## Active experiment — C140

Experiment: `C140-v5e-collision-free-multiseed-robustness`.

Question: is the unchanged collision-free C139 solution robust across a broader set of fresh initialization seeds?

C140 is diagnostic-only and changes no production runtime code. It repeats the exact C139 collision-free configuration on twelve fresh seeds `20261601..20261612`. It does not change the head architecture, pooling, hidden width, residual scale, train steps, learning rate, objective, candidate set, corpus, retrieval semantics, or evidence path.

```text
12 fresh seeds
same 49-d collision-free training-vocabulary bag features
same pooled SharedRetrievalContentHead
same 8 TRAIN_COMBINATION controls
same 4 UNSEEN_COMBINATION recombinations
same 12 live candidates
same exact persisted retrieval / provenance / commit / ANSWER path
```

C140 additionally records the expected-class score margin against the best competing candidate for every case. Margin instrumentation is observational only and does not affect training or selection.

Required for PASS: all 12 seeds pass all 12 cases, all deciding accuracy/rate metrics are `1.0` on every seed, every held-out recombination has strictly positive expected-class margin, collision-free/OOV and raw-baseline controls remain valid, and the accepted mixed-outcome C139 prerequisite is used.

Interpretation:

- PASS -> the exact C139 collision-free configuration is robust across this 12-seed replication. The isolated C139 seed failure remains observed but is not reproduced in the broader fresh-seed set.
- FAIL -> initialization/training sensitivity is reproduced under the unchanged configuration. Because successful parameterizations already exist, the following diagnostic should localize factor-aligned versus shortcut/non-compositional solutions before changing production architecture.

Gate E remains NOT PASSED.

## Non-claims

- Shared-Basis auto-partition remains separate.
- Context/KV replacement remains separate.
- `fold/fold_memory.py` is a QuadraticMemory numerical reference kernel, not the V5-E persistent memory store.
- C139/C140 collision-free vocabulary-basis encoding is diagnostic, not a scalable production tokenizer proposal.
- Gate C/D and C97-C140 evidence remains scoped unless explicitly measured otherwise.
