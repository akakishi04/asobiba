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
`docs/evidence-recovery-mode-v0.1.md` remains a separate design, not implemented by this admission diagnostic.

## Accepted through C152

- C137 PASS, lexical addressing/growth. C138-C140 VALID NEGATIVE on composition/seed sensitivity; the C138/C139 comparison also changed dimensions, parameter shapes and seeds, so collision causality is not isolated.
- C141 PASS, oracle substitution only; C142 PASS, supervised color alignment on the original small task. C143 VALID NEGATIVE on expanded ranking; C144 PASS, descriptive mismatch accounting.
- C145 VALID NEGATIVE, material supervision (1464->346 errors). C146 VALID NEGATIVE, all-factor reference (476->11); named-loss ladder closed.
- C147 VALID NEGATIVE, frozen composition (11->4, 3 new errors). C148 VALID NEGATIVE, train consistency (11->12, no rescue); no demonstrated remedy.
- C149 PASS, arithmetic accounting only; same-factor and normalization helped observed errors while cross-factor terms reversed their signs under that decomposition. Not unique causality or authorization to remove terms.
- C150 PASS, original synthetic split: WITHIN_FACTOR 20735/20736; GLOBAL_CONCEPT 20736/20736; 1 rescue/0 regressions, worst margins -0.0000681 versus +0.1425753. Ranking-only.
- C151 PASS, fixed-recipe same-task cross-split replication: 298/298 regression; four replacement splits / three paired fresh initializations each. WITHIN_FACTOR 20727/20736, GLOBAL_CONCEPT 20736/20736; original12 strict passes 12/12 both. Nine control errors concentrate in S2/20261726, COLOR only; all three other splits have no accuracy contrast. Min margin -0.0321333110 versus +0.1315777004. Not independent language/task generalization.
- **C152 ACCEPTED PASS**, selected-identity-to-persisted-evidence bridge, from full user terminal log at `7bd822c5b4086db7a09e83523fdfa75ac0bdfd0e`; 322/322 regression; 24 frozen heads; full/source-original replay and all reported protection/weight/order/tree/HEAD checks pass. No new learning or production mutation.

```text
C152 real adapter calls: 82944; exact scans: 64/call -> 5308416 vectors
CANONICAL and PERMUTED, 20736 cases per arm/layout:
  selected identity / provenance / payload / cost correctness = all cases
  WITHIN_FACTOR semantic correctness = 20727 each
  GLOBAL_CONCEPT semantic correctness = 20736 each
Source nine semantic mistakes persist per layout; no oracle repair.
Controller=False / evidence_commit=False / ANSWER=False
```

C152 supports the bridge within two trusted synthetic snapshots, not broad intelligence, absent-target detection, arbitrary provenance security, bounded sublinear retrieval or Gate E completion. All older verdicts remain valid within their own scope. Do not invent unprinted per-query errors.

**C152 report:** `runs/c152-v5e-persisted-bridge-c14bc4bd93e64087991290cb92e2b42a/summary.json`.
SHA256 `d70b57b6d7c0aa8876c0647ab1d858ec2808fd3478cf12c02b3d83be8cf2d844`.
**C151 report:** `runs/c151-v5e-cross-split-e9d383a3c4c64f9faca48eb81313d441/summary.json`.
SHA256 `d2b48acb36d28f0422d09067cc23af882c812d020a00ccfc8c6e8286fd896afa`.
Manifest SHA256 `5a19de10d8152ac262846682a79a13bb942eeacd7dca979afb09b70170ebdd65`.
Split plan SHA256 `db65d4754e465c55bfc19438f9d50324bb49e928911a53643deddc531625f4c0`.
Detailed C152 judgment / next preregistration: **`docs/experiment-ledger-addendum-c152-c153.md`**. Earlier details remain in `experiment-ledger-addendum-c150-c151.md` and `experiment-ledger-addendum-c151-c152.md`.

## Review decision

Synthetic ranker optimization and replacement-split tuning remain closed. Keep both checkpoint families; GLOBAL_CONCEPT is task-scoped, not a deployed fix. No loss/width/coefficient/step sweep or favorable-model selection. Independent language/task-family evaluation remains unresolved and is not replaced by engineering integration.

## Active C153 — Validated evidence admission

`C153-v5e-validated-evidence-admission`, stage `V5-E-VALIDATED-EVIDENCE-ADMISSION`; ACTIVE, awaiting user CPU integration, no formal result claimed.

Question: can recorded C152 selections drive real retrieval and sequential state admission while bad deliveries and successful repeats leave state unchanged?

- Reuse all C152 selected-handle traces (24 source heads x both layouts); no model loading, new scoring, fresh seeds or training. This is a downstream trace-driven integration, not a full neural pipeline rerun.
- Require exact C152/C151 report hashes, manifest and original persisted snapshots; reaggregate the full C152 trace and preserve semantic error identities. Checkpoints untouched.
- Same adapter and exact64 retrieval: 82944 actual calls. Per call, submit five controlled faults (MISSING, WRONG_KEY with unchanged bit, WRONG_SOURCE, WRONG_SCOPE, STALE_REQUEST), then original good evidence, then duplicate: 580608 submissions.
- New **diagnostic immutable in-process inbox**, using existing commit-context and pure receipt-claim helpers. Accepted state stores actual value, selected identity, provenance and request context; it is not a synthetic commit counter. Invalid paths must not consume claims. Store 48 actual inbox snapshots and hashes.
- Deduplicate per logical request, not record key. Ground-truth values/semantic labels are consulted only after admission. Authentic wrong control evidence is admitted under its selected identity, not reclassified as semantic truth.

PASS: all 414720 fault rejections preserve state; 82944 good deliveries each add one entry/claim; 82944 duplicates preserve state; actual stored payloads and costs agree; semantics remain GLOBAL 20736 and WITHIN 20727 per layout. FAIL: valid setup but admission/bridge requirements fail. INVALID: prerequisite/reaggregation/identity/hash/execution inconsistency; fix same C153.

**Not production session/memory integration.** No controller, ANSWER, concurrent/crash durability, learned abstention, missing-target inference, cryptographic payload integrity or Gate E promotion. State-file export is not a tested restore protocol. No C154 registered; review after judgment.

Implementation: `gate_e_c153_evidence_admission.py`, `gate_e_c153_cli.py`, `tests_lm/test_v05_c153_evidence_admission.py`, `tools/run_c153.ps1`.
Reviewer: **24/24 new CPU tests** with real adapter/index, immutable admission, retry and duplicate checks; Python compilation passed. Expected focused suite **346 tests**. Full suite, actual full C152 artifacts/trace integration and PowerShell were not reviewer-executed. Reference dependency copies matched repository Git blobs and are not changes to production files.

## Non-claims

Shared-Basis partition and KV/context work are separate. `fold/fold_memory.py` is a QuadraticMemory reference, not the V5-E store. Oracle replacement, explicit supervision, manual composition and automatically discovered factors differ. Ranking, persisted retrieval, diagnostic state admission and production commit/answer integration are separate claims.
