# FOLD Experiment Ledger and Handoff

> Current authoritative state; detailed history remains in chained experiment-ledger addenda.

## Environment / protocol

- Repository `akakishi04/asobiba`, branch `feat/sft-target-loss`; local `M:\asobiba\fold`.
- Python 3.13.15 / PyTorch 2.10.0+cu130 / CUDA 13.0 / RTX 4070 Ti SUPER; `.venv-py31315\Scripts\python.exe`.
- Protected C37 `runs/chatgpt-last-result.json`: SHA256 `FD4A8DA897BDAEA9D103A252E30212C7FF842D23300D7C837333E146DEE51931`.
- Protected fixture `runs/fixtures/v05-c-composition-20260921.pt`: SHA256 `A52F8209703149407580F7E2965B61B78653030EE992AF6D759865736741CA9E`.
- Read AGENTS.md, docs/experiment-conversation-handoff-protocol.md and this handoff. One question per C number; invalid runs retry the same number; all accepted negatives remain recorded.

## Gate status and boundaries

Gate A/B PASSED; Gate C/D PASSED within measured scope; **Gate E NOT PASSED**, active.
Priority: operational VRAM headroom, peak/resident VRAM, latency/throughput, artifact size.

```text
learned Control Lane -> authoritative availability/permission -> learned acquisition request
-> real acquisition -> provenance/outcome validation -> evidence commit -> reobserve
-> answer / further acquisition / unresolved
```

C132 and earlier: binding/scope/authority, replay, atomic claim, recovery/fencing. C133-C135: persisted corpus/StructuralIndex. C136: fixed-address query formation. C137: shared content addressing/dynamic candidates.
Production head `fold_lm.v05.retrieval_content.SharedRetrievalContentHead`; adapter `fold_lm.v05.retrieval_adapter.PersistedStructuralRetrievalAdapter`.
`docs/evidence-recovery-mode-v0.1.md` remains a separate design; it is not silently implemented by the current diagnostic.

## Accepted through C151

- C137 PASS, lexical addressing/growth; C138-C140 VALID NEGATIVE, composition/seed sensitivity. C138/C139 do not isolate hash-collision causality because dimensions, parameter shapes and seeds also differ.
- C141 PASS, oracle color substitution only. C142 PASS, train-only color supervision on original 12-candidate task. C143 VALID NEGATIVE on expanded rankings; C144 PASS, descriptive mismatch accounting.
- C145 VALID NEGATIVE, material supervision (1464->346 errors); C146 VALID NEGATIVE, all-factor reference (476->11). Named-attribute-loss ladder closed. See the corresponding addenda.
- C147 VALID NEGATIVE, frozen composition (11->4 with 3 new errors). C148 VALID NEGATIVE, train consistency (11->12, no rescue, 1 regression). See `experiment-ledger-addendum-c147-c148.md` and `experiment-ledger-addendum-c148-c149.md`.
- C149 PASS, arithmetic accounting only; cross-factor terms reverse the sign in observed errors under the specified decomposition. Normalization helps those comparisons. Not unique causal attribution or permission to delete cross terms. See `experiment-ledger-addendum-c149-c150.md`.
- C150 PASS, original synthetic split: WITHIN_FACTOR 20735/20736 versus GLOBAL_CONCEPT 20736/20736, 1 rescue/0 regressions, min margins -0.0000681 versus +0.1425753. No runtime path. See `experiment-ledger-addendum-c150-c151.md`.
- **C151 ACCEPTED PASS**, same-task cross-split replication, based on full user log at `1e8c4bfa18f3c28a654e6530ac56909a484411fb`: focused regression 298/298; all declared protection/replay-reference/weight/tree/HEAD controls valid. Four preregistered replacement splits, three fresh paired seeds each; no recipe change or production mutation.

```text
C151: seeds 20261721..20261732 / 4 splits / 24 heads
WITHIN_FACTOR: 20727/20736, 9 errors; 11/12 exhaustive-perfect heads
GLOBAL_CONCEPT: 20736/20736, 0 errors; 12/12 exhaustive-perfect heads
Original12 strict passes: 12/12 in BOTH arms
Paired: 9 rescues / 0 regressions / 20727 both correct / 0 both wrong
All errors: control S2, seed 20261726, COLOR only, held-out under current split
Minimum margin: -0.0321333110 -> +0.1315777004
S1 GLOBAL min +0.1651229858; S2 +0.1315777004; S3 +0.1486018300; S4 +0.1398902535
```

Exact error texts are not printed; do not invent them. Nine errors cluster in one model, not nine independent replications. Three splits provide no accuracy contrast. Margins are not calibrated confidence. New splits do not constitute an independent task family: all aliases and explicit auxiliary correspondences remain known. C151 confirms scoped recipe sufficiency beyond the original eight combinations, not open-domain understanding, automatic factor discovery or runtime correctness.

**Source for next run:** `runs/c151-v5e-cross-split-e9d383a3c4c64f9faca48eb81313d441/summary.json`.
C151 full-report SHA256: `d2b48acb36d28f0422d09067cc23af882c812d020a00ccfc8c6e8286fd896afa`.
Split-plan SHA256: `db65d4754e465c55bfc19438f9d50324bb49e928911a53643deddc531625f4c0`.
Manifest SHA256: `5a19de10d8152ac262846682a79a13bb942eeacd7dca979afb09b70170ebdd65`.
Full judgment and next specification: **`docs/experiment-ledger-addendum-c151-c152.md`**.

## Review decision

Stop optimizing this synthetic composition task and its replacement splits. Keep GLOBAL_CONCEPT as a task-scoped research candidate and retain the control. No new losses, coefficient/width/step sweeps or favorable-seed selection. Cross the selected-candidate -> actual-evidence boundary next, without simultaneously implementing a router, learned abstention, commits or answering. Independent language/task evaluation remains open and separate.

## Active C152 — Frozen persisted retrieval bridge

`C152-v5e-frozen-persisted-retrieval-bridge`, stage `V5-E-FROZEN-PERSISTED-RETRIEVAL-BRIDGE`; ACTIVE, awaiting user execution. No result claimed.

**Question:** does the frozen C151 selector retrieve the evidence for its selected record, preserving identity/provenance across separately reordered catalog and storage layouts?

- Use all 24 saved C151 models, both arms and all splits. Fresh seeds=0; training=0. No checkpoint continuation or model selection.
- Reaggregate full C151 source outcomes/metrics; verify source/manifest/plan hashes and model byte/tensor/vocabulary/config/scope metadata. Replay all 41472 full plus 288 old-12 rankings at absolute score tolerance 1e-5.
- Generate and reload 64-record snapshots from existing descriptors only. Catalog entries expose descriptor/key/request signature, not answer payload. One-hot signatures are manual adapter metadata, not a learned fixed classifier or scalable index proposal.
- CANONICAL catalog and independently key-sorted storage; PERMUTED catalog cyclic shift and reversed physical storage. Same descriptors/keys/signatures/Boolean payloads. Each snapshot has its own bound hashes/fingerprint.
- Same composed encoder; selection returns a catalog handle. Never interpret candidate position as a record address. Labels/expected values are consulted only after actual retrieval for scoring.
- **82944 actual adapter calls** (24 heads x 2 snapshots x 1728 queries), explicit exact 64-record scan each. No hidden fallback/cache substitute; 5308416 adapter vector comparisons are expected, plus encoder/ranking work.
- Validate selected identity, source hash/path, index fingerprint, schema/domain/operations and actual returned value. Key equality is mandatory even when two Boolean values match. Keep authentic-but-semantically-wrong control evidence visible.

**PASS:** all calls preserve selected record identity/provenance/value and declared costs; GLOBAL_CONCEPT evidence is semantically correct for every query in both orderings. WITHIN_FACTOR retains the source nine semantic errors per ordering. **FAIL:** valid setup/replay but integration misses/rejects/misbinds/returns wrong values. **INVALID:** source/model/replay/order-identity/numeric/immutability or execution problem; resolve and retry C152.

Actual existing adapter retrieval and provenance validation are exercised, but **controller=False / evidence_commit=False / ANSWER=False**. No synthetic commit counter. No production source changes. Catalog includes every target: no learned missing-answer detection, ambiguity, stale refresh, safe-answering or generalization claim. Exact full scan is a reference, not bounded-sublinear production retrieval. Gate E remains NOT PASSED. No C153 registered.

Implementation: `gate_e_c152_persisted_bridge.py`, `gate_e_c152_cli.py`, `tests_lm/test_v05_c152_persisted_bridge.py`, `tools/run_c152.ps1`.
Reviewer: **24/24 CPU helper tests passed** and Python compilation. Real adapter/index over generated 64-record snapshots was tested. Source dependencies matched their Git blobs. Full **322-test** suite, actual C151 full-record/checkpoint integration, formal CUDA run and PowerShell remain unexecuted by reviewer. Source checkpoints remain untouched; reports publish to unique run directories, with invalid markers on execution failure.

## Non-claims

Shared-Basis partition and KV/context work are separate. `fold/fold_memory.py` is a QuadraticMemory reference, not the V5-E store. Oracle replacement, explicit supervision, manual composition and discovered factors differ. Ranking PASS cannot establish acquisition/commit/ANSWER; a partial retrieval bridge cannot establish the rest of that pipeline either.
