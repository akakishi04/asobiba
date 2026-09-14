# FOLD experiment ledger addendum — C137 to C138

## C137 — ACCEPTED PASS

`C137-v5e-content-addressed-corpus-growth` passed on fresh seeds `20261571..73`.

Focused regression was 87/87. Training used eight candidate records; evaluation expanded the live candidate set to twelve records by adding four entities with zero query-head training examples. Per seed, all twelve validation cases passed. All deciding rates were `1.0`: Control Lane `RETRIEVE`, known-entity address selection, unseen-entity address selection, unseen and overall retrieved-key accuracy, provenance validation, exactly-one evidence commit, post-commit `ANSWER`, final evidence accuracy, dynamic candidate-set growth, and accepted C136 prerequisite. Protected C37 and fixture were preserved and the tracked tree remained clean.

C137 established dynamic content-addressed candidate selection rather than a fixed output-class address head. Scope remains limited: each unseen query and its candidate descriptor shared the same unseen entity token, so C137 did not establish semantic alias generalization.

## C138 — ACTIVE

Experiment: `C138-v5e-compositional-alias-generalization`.

Question: can the accepted C137 shared content head generalize learned query/descriptor attribute correspondences to held-out combinations when the paired validation query and record descriptor share zero lexical tokens?

C138 reuses the C137 production `SharedRetrievalContentHead` and persisted 12-record corpus unchanged. It adds no production runtime code.

Fresh seeds: `20261581,20261582,20261583`.

Training uses eight known three-attribute combinations. Query-side alias vocabulary and descriptor-side canonical vocabulary are disjoint for every validation pair. Four evaluation records are held-out recombinations of attribute values seen during training. Every alias token used by an unseen-combination query appears somewhere in training, so the held-out factor is the combination rather than vocabulary.

Per seed:

```text
8 TRAIN_COMBINATION controls
4 UNSEEN_COMBINATION recombinations
12 live retrieval candidates
```

Required at `1.0`: known-combination selection, unseen-combination selection, unseen and overall retrieval-key accuracy, provenance, exactly-one commit, post-commit `ANSWER`, final evidence accuracy, zero paired lexical overlap, unseen-alias training coverage, raw-baseline-not-perfect control, candidate growth, and accepted C137 prerequisite.

The raw hashed-feature negative control must not solve all unseen combinations. A scientifically valid C138 failure is accepted as a negative result if execution, protected artifacts, prerequisite identity, and postchecks are valid; it would indicate that C137's shared content head does not compositionally recombine learned alias correspondences under this controlled OOD split.

Progress output reports router training, content-head training, all twelve evaluation cases, and remaining work. Gate E remains NOT PASSED.
