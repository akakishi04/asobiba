# FOLD Experiment Ledger and Handoff

> Current authoritative handoff. Detailed history is retained in Gate decisions and experiment-ledger addenda.

## Environment / protocol

- Repo: `akakishi04/asobiba`; branch `feat/sft-target-loss`; local `M:\asobiba\fold`.
- Python 3.13.15 / PyTorch 2.10.0+cu130 / CUDA 13.0 / RTX 4070 Ti SUPER. User execution uses `.venv-py31315\Scripts\python.exe`.
- Protected C37: `runs/chatgpt-last-result.json`; SHA256 `FD4A8DA897BDAEA9D103A252E30212C7FF842D23300D7C837333E146DEE51931`.
- Protected fixture: `runs/fixtures/v05-c-composition-20260921.pt`; SHA256 `A52F8209703149407580F7E2965B61B78653030EE992AF6D759865736741CA9E`.
- One scientific question per C number. Invalid executions retry the same C number. Valid negatives close their C number and may advance after interpretation.
- Long benchmarks expose seed/phase/case progress and remaining work.
- Conversation, execution-command, formal-verdict, and cross-chat handoff responses follow `docs/experiment-conversation-handoff-protocol.md`. Read `AGENTS.md`, that protocol, and this handoff before continuing the active C number.

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

C133-C135 moved RETRIEVE onto a real persisted corpus and StructuralIndex, established safe zero-hit semantics, and added explicitly measured exact recovery after bounded-LSH false negatives. C136 learned fixed-address query formation. C137 replaced fixed output classes with shared content addressing and dynamic candidate-set growth.

Production content head: `fold_lm.v05.retrieval_content.SharedRetrievalContentHead`.
Production retrieval adapter: `fold_lm.v05.retrieval_adapter.PersistedStructuralRetrievalAdapter`.

## Accepted through C141

C137: ACCEPTED PASS within lexical content-addressing/corpus-growth scope; 87/87 regression, 3 fresh seeds, 8-to-12 candidate growth, all deciding rates 1.0. See `experiment-ledger-addendum-c137-c138.md`.

C138: ACCEPTED VALID NEGATIVE; 90/90 regression, known accuracy 1.0, unseen 0.25 on every seed. Real signed-hash collisions exist. See `experiment-ledger-addendum-c138-c139.md`.

C139: ACCEPTED VALID NEGATIVE; 93/93 regression; 49-dimensional collision-free features, zero OOV; unseen `1.0, 0.5, 1.0`. A solution is possible on this finite fixture, but the all-seed gate failed. C138/C139 differ in input dimension, parameter shapes/counts, encoding and seeds, so their comparison does not isolate a collision-removal causal effect. See `experiment-ledger-addendum-c139-c140.md` and subsequent audits.

C140: ACCEPTED VALID NEGATIVE based on the user's log at `f036550182c99a06865d788dacf055e3dea5820d`; 96/96 regression; fresh seeds `20261601..20261612`; known 96/96, unseen 44/48, overall 140/144; completely correct seeds 8/12. Errors: `20261602: q10->q2`, `20261604: q11->q1`, `20261606: q11->q1`, `20261612: q10->q2`. Worst margin `-0.0787280798`. This replicates seed-associated sensitivity, not its unique mechanism. See `experiment-ledger-addendum-c140-c141.md`.

C141: **ACCEPTED PASS, oracle color-localization scope only**, based on the user's complete terminal log at `b913e56950e7c0454ca63ec58f1f05f7439e7205`; focused regression 108/108; same twelve C140 seeds, fresh count zero. Baseline replay matches, all four failures rescued, all 140 successes preserved, zero new errors, treatment 144/144 and all margins positive. Frozen weights, input/protected hashes, tracked tree and execution HEAD are preserved. No production change. This is sufficiency of an evaluation-only oracle substitution, not learned original-query improvement or a new robustness proof. C139/C140 negatives remain in force.

C141 full local report: `runs/c141-v5e-color-alias-localization-718ccf78048943dd92820ea86cfa11b0/summary.json`.
C141 consumed C140 SHA256: `a0b23c3a24d6674efd3f9c229d994543af4b1918318e4caa1e9c4c5e6e8d8ca8` (not the C141 report's own hash).

Training audit: all 8 training records have distinct shape/material pairs, permitting selection without color. All C140 wrong selections retain shape/material and change color. C141's rescue localizes an effective intervention but does not prove color was wholly unlearned or distinguish residual lexical overlap from contextual alignment. Provenance authenticates a source, not relevance; commit-once here is a harness indicator, not a new durability proof.

Detailed C141 verdict and C142 preregistration: **`experiment-ledger-addendum-c141-c142.md`**.

## Active experiment — C142

Experiment: `C142-v5e-training-only-color-alignment`.
Stage: `V5-E-TRAINING-ONLY-COLOR-ALIGNMENT`.
Status: ACTIVE, awaiting user CUDA execution; no result claimed.

Question: does a training-only color-alias alignment auxiliary objective make the unchanged shared head solve the original held-out alias queries across fresh paired seeds, without inference-time oracle substitution?

```text
12 fresh seeds 20261621..20261632
same initial head copied into BASELINE and COLOR_AUX per seed
BASELINE loss = original retrieval cross entropy
COLOR_AUX loss = original retrieval cross entropy + 1.0 * color-alignment cross entropy
same 600 optimizer steps / lr 0.002 / logit scale 12.0
same head: feature_dim=49 / hidden_dim=64 / residual_scale=1.0
same 24 full queries / 8 full training candidates / 12 evaluation candidates
extra training-only supervision: 12 distinct aliases versus 4 canonical colors
no validation/held-out fields used to derive training pairs
original raw query text in BOTH evaluation arms; zero paired lexical overlap
144 baseline + 144 COLOR_AUX cases = 288 decisions; 24 trained heads
```

This introduces explicit color-first training supervision and extra computation, not additional model parameters or inference processing. Same optimizer steps does not mean equal training FLOPs. No auxiliary coefficient search, model-size change, extra epochs or validation-based selection.

- PASS: every COLOR_AUX case is correct through retrieval/evidence/ANSWER with a strictly positive finite expected-class margin; all controls valid.
- If baseline has errors, report paired rescue and new errors. If both arms are perfect, treatment sufficiency passed but improvement over baseline is unproven; do not substitute seeds.
- FAIL: valid execution but any treatment error/nonpositive margin remains. Partial improvement is not relabeled PASS.
- INVALID: prerequisite/input/protection, OOV/overlap, paired initialization, evaluation mutation, numeric, authority or execution failure; resolve and retry C142.

The unchanged fixture has already informed intervention design; this is targeted development-set research. Fresh seeds are not fresh tasks. PASS does not demonstrate automatically discovered semantic factors, open-domain reasoning, scalable text encoding or production readiness. Gate E remains NOT PASSED. Do not begin C143 before C142 is judged.

Implementation: `fold_lm/v05_benchmarks/gate_e_c142_color_alignment.py`, `gate_e_c142_cli.py`, `tests_lm/test_v05_c142_color_alignment.py`.
Reviewer validation: **22/22 new CPU tests**, including synthetic adapter evaluation and checkpoint reconstruction; Python compilation passed. Expected full focused suite: **130 tests**. Full focused suite and formal CUDA benchmark are not reviewer-executed. No registered fresh-seed benchmark result was inspected.

C142 validates the full C141 report and saves both arms' cases, margins, losses, initial/final fingerprints, model-only checkpoints, input/prerequisite hashes, commit and environment under a unique run directory. Do not overwrite protected C37. Scientific FAIL has exit code 0; execution exceptions return nonzero.

## Non-claims

- Shared-Basis auto-partition and context/KV replacement remain separate.
- `fold/fold_memory.py` is a QuadraticMemory numerical reference kernel, not the V5-E persistent memory store.
- C139-C142 vocabulary-basis features are diagnostics, not scalable production tokenizer proposals.
- C141 oracle substitution is not a deployed fix; C142 structured auxiliary supervision is not unsupervised semantic discovery.
- Gate C/D and C97-C142 evidence remains scoped unless explicitly measured otherwise.
