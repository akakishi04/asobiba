# FOLD experiment ledger addendum — C139 to C140

## C139 — ACCEPTED VALID NEGATIVE

`C139-v5e-hash-collision-composition-diagnostic` completed as a formally valid scientific `FAIL` on fresh seeds `20261591..93`.

Focused regression was 93/93. The collision-free diagnostic vocabulary had 49 dimensions, zero evaluation OOV tokens, and reproduced six collision buckets from the old C138 128-dimensional hashed front end including the `amber` / canonical `red` collision. Protected C37 and fixture hashes were preserved, the tracked tree remained clean, the accepted valid-negative C138 prerequisite was used, and no production runtime code was modified.

Known training combinations remained `1.0` accurate on every seed. Held-out recombination accuracy changed materially from C138's `0.25` on every seed to C139 values `1.0, 0.5, 1.0` (mean `0.833333`, median `1.0`). Seeds `20261591` and `20261593` solved all four held-out recombinations; seed `20261592` missed `q10` and `q11`, selecting known-combination addresses `q2` and `q1`. Overall retrieval/evidence accuracy was `0.944444` mean. Router RETRIEVE, provenance validation, exactly-one evidence commit, post-commit ANSWER, collision-free/OOV controls, dynamic candidate growth and prerequisite checks remained valid.

C139 therefore remains a negative result under its preregistered all-seed `1.0` criterion: collision removal was not sufficient to make the controlled compositional behavior robust. However, the two perfect seeds establish that the unchanged pooled representation plus `SharedRetrievalContentHead` is not strictly incapable of representing a solution to this finite controlled task. The large improvement relative to C138 is consistent with hash collisions having been a material confound/contributor, but because the fresh seed sets differ and C139 did not fully pass, C139 does not establish collisions as the sole cause.

The remaining question is now seed robustness / training-solution stability under the unchanged collision-free configuration. Changing hidden width, objective, pooling or production encoding before measuring that would confound capacity/architecture changes with initialization sensitivity.

## C140 — ACTIVE

Experiment: `C140-v5e-collision-free-multiseed-robustness`.

Question: is the unchanged collision-free C139 solution robust across a broader set of fresh initialization seeds?

C140 changes no production runtime code and makes no architecture or training-hyperparameter intervention. It repeats the exact C139 collision-free training/evaluation configuration on twelve fresh seeds `20261601..20261612`.

Held constant:

```text
same 49-d collision-free training-vocabulary bag representation
same pooled SharedRetrievalContentHead
same hidden width / residual scale
same train steps / learning rate / objective
same 8 TRAIN_COMBINATION controls
same 4 UNSEEN_COMBINATION recombinations
same 12 live retrieval candidates
same persisted C137 corpus
same exact retrieval / provenance / commit / ANSWER path
```

C140 additionally records the expected-class score margin against the best competing candidate for every case. This is observational instrumentation only and does not affect selection or training.

Required for PASS:

- all 12 fresh seeds pass all 12 cases;
- known and unseen combination accuracy are `1.0` on every seed;
- unseen/overall retrieval-key accuracy, provenance, exactly-one commit, post-commit ANSWER and final evidence accuracy are `1.0` on every seed;
- collision-free/OOV controls, raw-baseline control, dynamic candidate growth and accepted C139 prerequisite are valid;
- every held-out recombination has strictly positive expected-class margin on every seed.

Interpretation boundary:

- C140 PASS: the exact C139 collision-free configuration is robust across this 12-seed replication. C139 seed `20261592` becomes an observed but not reproduced instability; the next step should test scalability/generalization rather than redesign the head solely from that one failure.
- C140 FAIL: initialization/training sensitivity is reproduced under the unchanged configuration. Because C139 already demonstrated that successful parameterizations exist, the next diagnostic should localize why training converges to factor-aligned versus shortcut/non-compositional solutions before changing production architecture.

C140 is a controlled robustness experiment only. It does not establish open-domain compositional semantics or a scalable tokenizer/front-end design. Gate E remains NOT PASSED.
