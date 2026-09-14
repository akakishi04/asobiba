# FOLD experiment ledger addendum — C136 to C137

## C136 — ACCEPTED PASS

`C136-v5e-learned-retrieval-query-formation` passed on fresh seeds `20261561..63`.

Focused regression was 84/84. Per seed, eight held-out paraphrases were evaluated after training on three paraphrases per address. All deciding rates were `1.0`: learned Control Lane `RETRIEVE`, held-out query-address accuracy, persisted retrieval-key accuracy, provenance validation, exactly-one evidence commit, post-commit `ANSWER`, final evidence accuracy, full-corpus exact scoring, and accepted C135 prerequisite. Protected C37 and fixture were preserved and the tracked tree remained clean.

C136 established:

```text
held-out query text
-> learned fixed-size RetrievalAddressHead
-> predicted address 0..7
-> real persisted retrieval
-> validated evidence
-> reobserve
-> ANSWER
```

C136 remained limited because the head had eight fixed output classes and each validation paraphrase retained the address-specific codeword observed in training. It did not establish corpus-growth or unseen-entity generalization.

## C137 — ACTIVE

Experiment: `C137-v5e-content-addressed-corpus-growth`.

Question: can a shared content-addressed retrieval head trained with eight known entities continue to choose correct retrieval candidates after the catalog grows to twelve records, including four entity labels never seen in query-head training, without changing the head output dimensionality or retraining it after corpus growth?

Production component: `fold_lm.v05.retrieval_content.SharedRetrievalContentHead`.

The head encodes query text features and record-descriptor features with the same residual encoder, then scores the current candidate set by dot product. It therefore has no fixed address-class output layer.

Training catalog: 8 entities (`q0..q7`) with three query paraphrases each. Evaluation catalog: 12 entities (`q0..q11`). The four added entities (`q8..q11`: topaz, cedar, violet, bronze) have zero training paraphrases. Evaluation uses one validation query for every catalog record.

Fresh seeds: `20261571,20261572,20261573`.

Required rates at `1.0`: Control Lane `RETRIEVE`, known-entity address accuracy, unseen-entity address accuracy, unseen-entity retrieval-key accuracy, overall retrieval-key accuracy, provenance validation, exactly-one evidence commit, post-commit `ANSWER`, final evidence accuracy, dynamic candidate-growth contract, and accepted C136 prerequisite.

The expected address is used only for evaluation. The actual retrieval structure is generated from the candidate index selected by the content head over the 12-record evaluation catalog.

Progress reports router train start/done, content-head train start/done, the catalog-growth boundary, every one of 12 evaluation cases and remaining work.

Scope: unseen entity labels are recoverable because query and record descriptor share the same lexical entity token. C137 does not establish unseen semantic aliases, open-domain retrieval, or natural-language semantic embedding quality. Exact evidence retrieval remains the post-selection validation path. Gate E remains NOT PASSED.
