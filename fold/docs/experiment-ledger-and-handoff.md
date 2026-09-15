# FOLD Experiment Ledger and Handoff

> Current authoritative state; detailed history remains in chained experiment-ledger addenda.

## Environment / protocol

- Repository `akakishi04/asobiba`, branch `feat/sft-target-loss`; local `M:\asobiba\fold`.
- Python 3.13.15 / PyTorch 2.10.0+cu130 / CUDA 13.0 / RTX 4070 Ti SUPER; `.venv-py31315\Scripts\python.exe`.
- Protected C37 `runs/chatgpt-last-result.json`: SHA256 `FD4A8DA897BDAEA9D103A252E30212C7FF842D23300D7C837333E146DEE51931`.
- Protected fixture `runs/fixtures/v05-c-composition-20260921.pt`: SHA256 `A52F8209703149407580F7E2965B61B78653030EE992AF6D759865736741CA9E`.
- Read AGENTS.md, docs/experiment-conversation-handoff-protocol.md and this handoff. One question per C number; invalid runs retry that number; accepted negatives remain recorded.

## Gate status / boundaries

Gate A/B PASSED; Gate C/D PASSED within measured scope; **Gate E NOT PASSED**, active.
Priority: operational VRAM headroom, peak/resident VRAM, latency/throughput, artifact size.

```text
learned Control Lane -> authoritative availability/permission -> learned acquisition request
-> real acquisition -> provenance/outcome validation -> evidence commit -> reobserve
-> answer / further acquisition / unresolved
```

C132 and earlier cover binding/scope/authority, replay, atomic claim and recovery/fencing. C133-C135 introduce persisted retrieval; C136 fixed-address query formation; C137 shared content addressing/dynamic candidates.
Production head: `fold_lm.v05.retrieval_content.SharedRetrievalContentHead`; adapter: `fold_lm.v05.retrieval_adapter.PersistedStructuralRetrievalAdapter`.
`docs/evidence-recovery-mode-v0.1.md` remains a separate design, not implemented by the current projection diagnostic.

## Accepted through C153

- C137 PASS, lexical addressing/growth. C138-C140 VALID NEGATIVE on composition/seed sensitivity; C138/C139 also changed dimensions, shapes and seeds, so collision causality is not isolated.
- C141 PASS, oracle substitution only; C142 PASS, supervised color alignment on the original small task. C143 VALID NEGATIVE on expanded ranking; C144 PASS, descriptive mismatch accounting.
- C145 VALID NEGATIVE, material supervision (1464->346 errors). C146 VALID NEGATIVE, all-factor reference (476->11); named-loss ladder closed.
- C147 VALID NEGATIVE, frozen composition (11->4, 3 new errors). C148 VALID NEGATIVE, train consistency (11->12, no rescue); no demonstrated remedy.
- C149 PASS, arithmetic accounting only; same-factor and normalization helped observed errors while cross-factor terms reversed their signs under that decomposition. Not unique causality or authorization to remove terms.
- C150 PASS, original synthetic split: WITHIN_FACTOR 20735/20736; GLOBAL_CONCEPT 20736/20736; 1 rescue/0 regressions, worst margins -0.0000681 versus +0.1425753. Ranking-only.
- C151 PASS, fixed-recipe same-task cross-split replication: 298/298 regression; four replacement splits / three paired fresh initializations each. WITHIN_FACTOR 20727/20736, GLOBAL_CONCEPT 20736/20736; original12 strict passes 12/12 both. Nine control errors concentrate in S2/20261726, COLOR only; three splits have no accuracy contrast. Min margin -0.0321333110 versus +0.1315777004. Not independent language/task generalization.
- C152 PASS, selected-identity-to-persisted-evidence bridge: 322/322 regression; 24 frozen heads; full/source-original replay and all reported protection/weight/order/tree/HEAD checks pass. 82,944 actual adapter calls, 64 exact vectors/call. Identity/provenance/payload/cost correct in every case. WITHIN_FACTOR semantic correctness 20,727/layout; GLOBAL_CONCEPT 20,736/layout. No new learning or production mutation.
- **C153 ACCEPTED PASS**, validated evidence admission, execution commit `dc5f5d8bf72bc04692411c05213c824eb8c8c918`; 346/346 regression; 82,944 actual retrievals; 580,608 delivery submissions. No model loading/scoring/training.

```text
C153 per request:
  MISSING       -> rejected, state unchanged
  WRONG_KEY     -> rejected, state unchanged
  WRONG_SOURCE  -> rejected, state unchanged
  WRONG_SCOPE   -> rejected, state unchanged
  STALE_REQUEST -> rejected, state unchanged
  valid delivery-> COMMITTED exactly once
  repeat valid  -> DUPLICATE, state unchanged

Totals:
  414720 registered fault rejections
   82944 valid admissions
   82944 duplicate rejections
```

Every arm/layout group passed all 20,736 protocol cases. Source semantics remain WITHIN_FACTOR 20,727/20,736 and GLOBAL_CONCEPT 20,736/20,736 in both layouts; admission does not oracle-repair authentic but irrelevant control evidence. All input/protected hashes, tracked-tree and HEAD postchecks passed; `run_execution_valid=True`.

**C153 report:** `runs/c153-v5e-evidence-admission-6a96d53560a0454082d0ae22c143fdf0/summary.json`.
SHA256 `cddf360fc2211302d1dab0abd8d96038bb3d39ab273f9dea336da348d70d3a78`.
**C152 report:** `runs/c152-v5e-persisted-bridge-c14bc4bd93e64087991290cb92e2b42a/summary.json`.
SHA256 `d70b57b6d7c0aa8876c0647ab1d858ec2808fd3478cf12c02b3d83be8cf2d844`.
**C151 report:** `runs/c151-v5e-cross-split-e9d383a3c4c64f9faca48eb81313d441/summary.json`.
SHA256 `d2b48acb36d28f0422d09067cc23af882c812d020a00ccfc8c6e8286fd896afa`.
Manifest SHA256 `5a19de10d8152ac262846682a79a13bb942eeacd7dca979afb09b70170ebdd65`.
Split plan SHA256 `db65d4754e465c55bfc19438f9d50324bb49e928911a53643deddc531625f4c0`.
Detailed C153 judgment / next preregistration: **`docs/experiment-ledger-addendum-c153-c154.md`**. Earlier details remain in `experiment-ledger-addendum-c151-c152.md` and `experiment-ledger-addendum-c152-c153.md`.

## Review decision

Synthetic ranker optimization remains closed. Keep both checkpoint families; GLOBAL_CONCEPT remains task-scoped. C153 closes the sequential request-admission diagnostic within its registered scope, but it is not a durable/production state commit.

The next boundary is the representation crossing from **logical request admissions** to the existing V5 **record-identity EvidenceState**. Do not simultaneously add payload dereference/re-observation, SQLite durability, concurrency/crash injection, controller routing, ANSWER, new learning, or source-semantic repair.

The Multi-Axis Shared Basis hypothesis is a separate architecture research track. Its MA-1 experiment must not be inferred from C150-C153 results and is not folded into the active V5-E integration number.

## Active C154 — EvidenceState projection

`C154-v5e-evidence-state-projection`, stage `V5-E-EVIDENCE-STATE-PROJECTION`; ACTIVE, awaiting user CPU execution.

Question: can the exact accepted C153 request-level entries be projected into actual `fold_lm.v05.state.EvidenceState` record-identity references, so repeated requests collapse idempotently while same-ID conflicting provenance is rejected without changing state?

- Exact C153 report hash and all 48 state-file hashes required.
- No model load, retrieval, scoring, fresh seed or training. Source query semantics are only reaggregated after input validation.
- `EvidenceRef.evidence_id` = persisted record key, never request id.
- `Provenance.kind=OBSERVED`; source_id binds source SHA256 + index fingerprint + source path.
- Experiment-local mapping only: request_epoch 1 -> evidence_time 1; provider_generation 1 -> revision 1.
- Each arm/layout remains a separate EvidenceState because snapshot provenance differs.
- Genuine source entry transitions across 48 streams: 3,072 `ADDED`, 79,872 `ALREADY_PRESENT`.
- One injected conflicting-provenance case per newly added record identity: 3,072 `PROVENANCE_CONFLICT`, exact state object preserved.
- Final state cardinality: 48 x 64 = 3,072 unique OBSERVED refs.
- Existing `EvidenceState` is actually instantiated; production modules are not modified. Payload values are not stored in EvidenceState, and re-observation is not tested.

PASS: all registered counts/identity/provenance invariants hold and source semantic totals remain unchanged. FAIL: valid source but projection loses/duplicates identities, accepts conflict, or mutates state on duplicate/conflict. INVALID: source/hash/request/protected/execution discrepancy; retry same C154.

Implementation: `gate_e_c154_evidence_state_projection.py`, `gate_e_c154_cli.py`, `tests_lm/test_v05_c154_evidence_state_projection.py`, `tools/run_c154.ps1`.
Expected focused suite **363 tests** = 346 prior + 5 baseline state tests + 12 new projection tests. C154 itself is CPU-only. No C155 registered; judge C154 before selecting the next boundary.

## Non-claims

Gate E is still NOT PASSED. Shared-Basis partition, Multi-Axis, KV/context work, ranking, persisted retrieval, request-level admission, EvidenceState projection, durable storage, re-observation and ANSWER are separate claims. `fold/fold_memory.py` is a QuadraticMemory reference, not the V5-E store. Oracle replacement, explicit supervision, manual composition and automatically discovered factors differ.
