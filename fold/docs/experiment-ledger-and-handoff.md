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

Production head: `fold_lm.v05.retrieval_content.SharedRetrievalContentHead`.
Production adapter: `fold_lm.v05.retrieval_adapter.PersistedStructuralRetrievalAdapter`.

## Accepted through C142

C137: ACCEPTED PASS within lexical content-addressing/corpus-growth scope; 87/87 regression, 8-to-12 candidate growth, all deciding rates 1.0. See `experiment-ledger-addendum-c137-c138.md`.

C138: ACCEPTED VALID NEGATIVE; 90/90 regression; known 1.0, unseen 0.25 on every seed; real hash collisions. See `experiment-ledger-addendum-c138-c139.md`.

C139: ACCEPTED VALID NEGATIVE; 93/93 regression; 49-dimensional collision-free features; unseen `1.0, 0.5, 1.0`. C138/C139 also differ in input dimension, parameter shapes/counts, encoding and seed sets: their comparison does not isolate the causal effect of collision removal. See `experiment-ledger-addendum-c139-c140.md` and subsequent audits.

C140: ACCEPTED VALID NEGATIVE; 96/96 regression; known 96/96, unseen 44/48, overall 140/144; 8/12 completely correct seeds. Fixed-configuration seed sensitivity reproduced, mechanism not isolated. See `experiment-ledger-addendum-c140-c141.md`.

C141: ACCEPTED PASS, oracle localization only; 108/108 regression; the same C140 models reconstructed, four errors rescued and 140 successes preserved by evaluation-only canonical color substitution. No fresh seeds or learned original-query improvement. See `experiment-ledger-addendum-c141-c142.md`.

C142: **ACCEPTED PASS, training-only supervised alignment on the registered fixture**, based on the uploaded user log at `680ad7b4063e284504a36e0ded1c05a781d467a3`. Focused regression 130/130. Twelve fresh paired seeds `20261621..20261632`. BASELINE: known 96/96, unseen 39/48, overall 135/144, 5/12 full model passes. COLOR_AUX: known 96/96, unseen 48/48, overall 144/144, 12/12 full model passes. All nine baseline errors rescued; all 135 successes preserved; no new errors. Worst treatment unseen margin `+0.0474634767` versus baseline `-0.0809568167`. All reported input/protection/paired-init/no-inference-oracle/frozen-evaluation/tracked-tree/HEAD checks passed. No production runtime change.

C142 adds a fixed-weight color-alignment auxiliary loss using the same head. It supplies structured training labels and extra training computation, not extra inference parameters or an evaluation-time dictionary. Same optimizer-step count does not mean equal compute. Only four distinct held-out combinations were used; fresh seeds are not fresh tasks. The `q9->q2` baseline error preserves color and changes other attributes, so the improvement is not proof of a uniquely isolated color-only mechanism. C139/C140 negatives remain valid under their own conditions.

C142 full local result and 24 model checkpoints:
`runs/c142-v5e-training-only-color-alignment-90ebc41c7ada4d679d20b7c902cd3d29/`.
The C142 report consumed C141 SHA `1a3ded18c9066cfbfc7ab4a60839058ced82120abc3036258dad9170fc7deadc`; its own report hash must be computed locally, not copied from that field.

Detailed verdict and C143 preregistration: **`experiment-ledger-addendum-c142-c143.md`**.

## Active experiment — C143

Experiment: `C143-v5e-frozen-factorial-ranking-audit`.
Stage: `V5-E-FROZEN-FACTORIAL-RANKING-AUDIT`.
Status: ACTIVE, awaiting user evaluation; no C143 model result claimed.

Question: do the stored C142 heads generalize beyond the four studied combinations to the exhaustive in-vocabulary factor/alias product?

```text
Load all 24 saved C142 heads; no retraining or model selection
Original 12-query / 12-candidate ranking reconstruction against the C142 report
4 colors x 4 shapes x 4 materials = 64 descriptor candidates
8 training + 4 prior held-out + 52 newly evaluated combinations
3 aliases per factor -> 27 raw query variants per combination
1,728 queries/model x 24 models = 41,472 ranking decisions
plus 288 original-12 reconstruction controls
fresh_seed_count = 0; additional_training_steps = 0
```

Test generation uses training-only factor/alias tables; raw query and descriptor features alone enter the scorer. Use the unchanged C139 feature implementation and same stored head weights. Zero target-paired lexical overlap and zero OOV are required. Enumerate and write the manifest before any model scoring. No inference-time alias replacement or auxiliary loss at evaluation.

**Ranking only:** no expanded persisted-corpus retrieval, provenance validation, commit or ANSWER is executed in C143. `runtime_path_exercised=False`. The generated 64-descriptor catalog is not a production corpus update. Do not report its ranking accuracy as end-to-end success.

- PASS: all 20,736 COLOR_AUX rankings are correct with strictly positive finite expected-class margins, with all controls valid.
- FAIL: valid reconstruction but any treatment ranking error/nonpositive margin in the expanded suite. Retain the scoped C142 PASS; examine new-combination and original-query-in-64 groups separately.
- INVALID: prerequisite/checkpoint/hash/config/vocabulary/reconstruction/OOV/numeric/immutability/execution failure. Retry C143 after resolution; no retraining fallback.

Per-model groups: training combinations 216 strings (including 24 training strings), previously held-out combinations 108, new combinations 1,404. The exact 12 original validation strings in 64 candidates are an overlapping diagnostic group. Catalog expansion and query coverage expand together, so this is not an isolated one-factor causal comparison. The 52 new combinations are related synthetic tasks, not a separately sourced sealed dataset.

Implementation: `gate_e_c143_frozen_factorial_audit.py`, `gate_e_c143_cli.py`, `tests_lm/test_v05_c143_frozen_factorial_audit.py`, `tools/run_c143.ps1`. Reviewer: 22/22 new CPU tests and Python compilation passed using synthetic weights. Full focused suite expected **152**; full suite and actual CUDA checkpoint evaluation not reviewer-executed. PowerShell reviewed, not executed by reviewer.

Save the evaluation manifest, complete rankings, reconstruction evidence and input/checkpoint hashes under a new run directory. Read C142 reports/checkpoints and protected C37/fixture without modification. Scientific FAIL returns exit code zero; execution errors return nonzero. Gate E remains NOT PASSED. No C144 before C143 judgment.

## Non-claims

- Shared-Basis auto-partition and context/KV replacement remain separate.
- `fold/fold_memory.py` is a QuadraticMemory numerical reference kernel, not the V5-E persistent memory store.
- C139-C143 vocabulary-basis features are diagnostics, not scalable production tokenizer proposals.
- Oracle substitution, explicit training supervision, and automatically discovered semantic factors are different claims.
- C143 is a frozen selector audit, not a new full-runtime gate.
- Gate C/D and C97-C143 evidence remains scoped unless explicitly measured otherwise.
