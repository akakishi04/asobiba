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

## Accepted through C140

C137 is ACCEPTED PASS within lexical content-addressing/corpus-growth scope: 87/87 regression, 3 fresh seeds, 8-to-12 candidate growth, all deciding rates 1.0. See `experiment-ledger-addendum-c137-c138.md`.

C138 is ACCEPTED VALID NEGATIVE: 90/90 regression, known accuracy 1.0, unseen accuracy 0.25 on every seed. Real collisions exist in the 128-dimensional signed-hash front end. See `experiment-ledger-addendum-c138-c139.md`.

C139 is ACCEPTED VALID NEGATIVE: 93/93 regression; 49-dimensional collision-free training-vocabulary features, zero OOV; unseen accuracy `1.0, 0.5, 1.0`. Two complete successes show a solution is possible on this finite fixture, but the all-seed criterion failed. Comparing C138 and C139 does not isolate collision removal: input dimension, parameter shapes/counts, encoding and seed sets also differ. See `experiment-ledger-addendum-c139-c140.md` and the C140 audit addendum.

C140 is ACCEPTED VALID NEGATIVE based on the user's terminal log at commit `f036550182c99a06865d788dacf055e3dea5820d`: focused regression 96/96; fresh seeds `20261601..20261612`; known 96/96, unseen 44/48, overall scenario/key/evidence 140/144; completely correct seeds 8/12. All reported control/provenance/commit-indicator/ANSWER/prerequisite/protected-artifact/tracked-tree checks passed. No production change.

Errors: `20261602: q10->q2`, `20261604: q11->q1`, `20261606: q11->q1`, `20261612: q10->q2`. Worst margin `-0.0787280798`. C140 reproduces seed-associated sensitivity under the fixed C139 configuration. It neither identifies the optimization mechanism nor proves inability to represent a solution. The unseen evaluations repeat four distinct queries, not 48 independent tasks.

Training-only fixture audit: all 8 training records have distinct shape/material pairs, so record identity can be distinguished without color. All C140 errors preserve shape/material and select the wrong color. This permits a shortcut explanation but does not prove the learned heads used that shortcut. Provenance authenticates the source, not query relevance; the C140 commit metric is a harness indicator, not a new durability proof.

Detailed verdict, error margins, evidence provenance and C141 preregistration: **`experiment-ledger-addendum-c140-c141.md`**.

## Active experiment — C141

Experiment: `C141-v5e-color-alias-localization`.
Stage: `V5-E-COLOR-ALIAS-LOCALIZATION`.
Status: ACTIVE, awaiting user CUDA execution; no result claimed.

Question: on replayed C140 heads with frozen parameters, does evaluation-only replacement of the query's color alias by its canonical color rescue all four C140 failures without introducing new errors?

```text
same C140 seeds 20261601..20261612 (REPLAY, not fresh)
same C139 training function / data / objective / schedule / head
same 49-dimensional collision-free vocabulary basis
same 12 descriptors / persisted records / retrieval and evidence harness
12 original queries + 12 color-only substitutions per seed
144 baseline + 144 intervention = 288 decisions
```

The positional alias map is derived only from TRAIN_COMBINATION rows. This is an **oracle diagnostic** using fixture structure, not a learned production canonicalizer. Canonical color intentionally creates lexical overlap. Do not describe a positive result as learned semantic generalization.

C140 saved no head checkpoints. C141 retrains with the exact same function/seeds, verifies the original discrete outcomes and score margins against the full local C140 `summary.json` (absolute tolerance `1e-5`), then compares both arms with identical parameters. Replay mismatch is INVALID. Model/input/prerequisite fingerprints must be preserved.

- PASS: rescue all 4 errors, preserve all 140 successes, and achieve positive expected-class margins for all treatment cases with all execution controls valid. This supports only the diagnostic substitution's sufficiency.
- FAIL: valid replay but incomplete rescue, new errors or nonpositive treatment margins. Report partial rescue and new errors separately; no unique causal claim follows automatically.
- INVALID: prerequisite, replay, OOV, numeric, authority, artifact or execution failure; resolve and retry C141.

Implementation: `fold_lm/v05_benchmarks/gate_e_c141_color_alias_localization.py`, `gate_e_c141_cli.py` and `tests_lm/test_v05_c141_color_alias_localization.py`. New helper tests: 12/12 passed on reviewer CPU. Expected full focused suite: 108 tests; full suite and CUDA benchmark not yet run by reviewer.

No production runtime change. Gate E remains NOT PASSED. Do not begin C142 before C141 is judged.

## Non-claims

- Shared-Basis auto-partition and context/KV replacement remain separate.
- `fold/fold_memory.py` is a QuadraticMemory numerical reference kernel, not the V5-E persistent memory store.
- C139-C141 vocabulary-basis features are diagnostics, not scalable production tokenizer proposals.
- C141 oracle color substitution is not a deployed fix or fresh-seed robustness evidence.
- Gate C/D and C97-C141 evidence remains scoped unless explicitly measured otherwise.
