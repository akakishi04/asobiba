# FOLD experiment ledger addendum — C138 to C139

## C138 — ACCEPTED VALID NEGATIVE

`C138-v5e-compositional-alias-generalization` completed as a formally valid scientific `FAIL` on fresh seeds `20261581..83`.

Focused regression was 90/90. The eight training-combination controls remained perfect on every seed, while the four held-out recombinations reached only `0.25` unseen-combination accuracy and `0.25` unseen retrieval-key accuracy on every seed. Overall scenario/retrieval/evidence accuracy was `0.75`. Control Lane `RETRIEVE`, provenance validation, exactly-one evidence commit, post-commit `ANSWER`, zero paired lexical overlap, unseen-alias training coverage, dynamic candidate growth, accepted C137 prerequisite, and protected-artifact/postcheck conditions all remained valid. The raw hashed-feature unseen baseline was `0.0`.

Therefore C138 is closed as a negative result: the current C137 path, as actually encoded and trained in C138, does not reliably recombine learned alias correspondences into held-out three-attribute combinations.

A post-result audit found a material causal confound in the C138 text front end. `hashed_text_features(feature_dim=128)` maps each token to a single signed hash bucket, and the C138 training vocabulary contains real collisions. In particular `amber` and canonical `red` map to the same bucket; other collisions also exist. The persistent C138 error `amber boxy timber -> red square wood` is consistent with this collision. This does not invalidate the C138 negative result for the current system, but it prevents attributing the failure solely to `SharedRetrievalContentHead` compositionality.

## C139 — ACTIVE

Experiment: `C139-v5e-hash-collision-composition-diagnostic`.

Question: does the C138 held-out-combination failure persist when feature-hash collisions are removed while keeping the same pooled bag-of-token representation, the same `SharedRetrievalContentHead`, the same train/evaluation combinations, and the same learning objective?

C139 is a diagnostic and changes no production runtime code.

The diagnostic vocabulary is built only from C138 training-combination descriptors and training queries. Every validation and evaluation-descriptor token must already be covered by that training vocabulary. Each token receives its own diagnostic basis dimension, eliminating token collisions without adding validation labels or held-out-combination supervision.

Fresh seeds: `20261591,20261592,20261593`.

Per seed:

```text
8 TRAIN_COMBINATION controls
4 UNSEEN_COMBINATION recombinations
12 live retrieval candidates
same pooled SharedRetrievalContentHead
collision-free training-vocabulary bag features
```

Required at `1.0`: known and unseen combination accuracy, unseen/overall retrieval-key accuracy, provenance validation, exactly-one evidence commit, post-commit `ANSWER`, final evidence accuracy, zero-OOV collision-free feature control, reproduced-C138-collision control, raw collision-free baseline nontriviality, candidate growth, and accepted valid-negative C138 prerequisite.

Interpretation boundary:

- C139 PASS: C138's 128-dimensional single-bucket hash collisions were a material confound; the pooled head can solve this controlled recombination task once token identity is preserved.
- C139 FAIL: the controlled compositional failure persists even after removing hash collisions, strengthening the case that pooled representation/head structure is insufficient.

C139 is not a scalable tokenizer proposal and does not establish open-domain semantic composition. Gate E remains NOT PASSED.
