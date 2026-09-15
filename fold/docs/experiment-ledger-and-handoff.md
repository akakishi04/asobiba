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
`docs/evidence-recovery-mode-v0.1.md` remains a separate design, not implemented by the projection diagnostic.

## Accepted through C154

- C137 PASS, lexical addressing/growth. C138-C140 VALID NEGATIVE on composition/seed sensitivity; C138/C139 also changed dimensions, shapes and seeds, so collision causality is not isolated.
- C141 PASS, oracle substitution only; C142 PASS, supervised color alignment on the original small task. C143 VALID NEGATIVE on expanded ranking; C144 PASS, descriptive mismatch accounting.
- C145 VALID NEGATIVE, material supervision (1464->346 errors). C146 VALID NEGATIVE, all-factor reference (476->11); named-loss ladder closed.
- C147 VALID NEGATIVE, frozen composition (11->4, 3 new errors). C148 VALID NEGATIVE, train consistency (11->12, no rescue); no demonstrated remedy.
- C149 PASS, arithmetic accounting only; same-factor and normalization helped observed errors while cross-factor terms reversed their signs under that decomposition. Not unique causality or authorization to remove terms.
- C150 PASS, original synthetic split: WITHIN_FACTOR 20735/20736; GLOBAL_CONCEPT 20736/20736; 1 rescue/0 regressions, worst margins -0.0000681 versus +0.1425753. Ranking-only.
- C151 PASS, fixed-recipe same-task cross-split replication: 298/298 regression; four replacement splits / three paired fresh initializations each. WITHIN_FACTOR 20727/20736, GLOBAL_CONCEPT 20736/20736; original12 strict passes 12/12 both. Nine control errors concentrate in S2/20261726, COLOR only; three splits have no accuracy contrast. Min margin -0.0321333110 versus +0.1315777004. Not independent language/task generalization.
- C152 PASS, selected-identity-to-persisted-evidence bridge: 322/322 regression; 24 frozen heads; full/source-original replay and all reported protection/weight/order/tree/HEAD checks pass. 82,944 actual adapter calls, 64 exact vectors/call. Identity/provenance/payload/cost correct in every case. WITHIN_FACTOR semantic correctness 20,727/layout; GLOBAL_CONCEPT 20,736/layout. No new learning or production mutation.
- C153 PASS, validated evidence admission, execution commit `dc5f5d8bf72bc04692411c05213c824eb8c8c918`; 346/346 regression; 82,944 actual retrievals; 580,608 submissions: 414,720 registered fault rejections, 82,944 valid request admissions and 82,944 duplicate rejections. Fault/duplicate paths preserve the immutable diagnostic state. Authentic wrong control evidence is not oracle-repaired. No production/durable commit, Controller or ANSWER.
- **C154 ACCEPTED PASS**, EvidenceState projection, execution commit `8768303869d6ee24d72cc98a9690219a4205a495`; 363/363 regression. Exact accepted C153 state artifacts: 48 streams, 82,944 entries, 3,072 ADDED, 79,872 ALREADY_PRESENT, 3,072 injected PROVENANCE_CONFLICT rejections. Each actual V5 EvidenceState ends with 64 unique OBSERVED refs. All reported source/protected hashes, tracked-tree and HEAD postchecks pass; `run_execution_valid=True`.

C154 maps request-level admissions to record-key references. The 3,072 observations are 64 refs in each of 48 isolated states, not 3,072 distinct corpus records or a measured memory-compression gain. Payloads are not stored in EvidenceState; no new retrieval/scoring/training or payload re-observation was performed. The source semantic counts are only reaggregated: WITHIN_FACTOR 20,727/20,736 and GLOBAL_CONCEPT 20,736/20,736 per layout. Do not infer corrected query decisions from final record-set coverage.

## Accepted artifact chain

**C154 report:** `runs/c154-v5e-evidence-state-projection-ddacda18a60e4b7b91c370155ae5551c/summary.json`.
SHA256 printed in the user's log: `4814c9489b76bfb124e7134336611a3f513eb922083b0eca251be533820c4284`.
**C153 report:** `runs/c153-v5e-evidence-admission-6a96d53560a0454082d0ae22c143fdf0/summary.json`.
SHA256 `cddf360fc2211302d1dab0abd8d96038bb3d39ab273f9dea336da348d70d3a78`.
**C152 report:** `runs/c152-v5e-persisted-bridge-c14bc4bd93e64087991290cb92e2b42a/summary.json`.
SHA256 `d70b57b6d7c0aa8876c0647ab1d858ec2808fd3478cf12c02b3d83be8cf2d844`.
**C151 report:** `runs/c151-v5e-cross-split-e9d383a3c4c64f9faca48eb81313d441/summary.json`.
SHA256 `d2b48acb36d28f0422d09067cc23af882c812d020a00ccfc8c6e8286fd896afa`.
Manifest SHA256 `5a19de10d8152ac262846682a79a13bb942eeacd7dca979afb09b70170ebdd65`.
Split plan SHA256 `db65d4754e465c55bfc19438f9d50324bb49e928911a53643deddc531625f4c0`.

Detailed current verdict and concurrent report review: **`docs/experiment-ledger-addendum-c154-pcalm-review.md`**. C154 preregistration remains unchanged in `docs/experiment-ledger-addendum-c153-c154.md`; older details remain in the previous chained addenda.

Review evidence is the user's terminal log and source inspection, not an independent rerun of full local artifacts. The reviewer parsed the C154 console JSON and checked aggregate arithmetic; no new benchmark/regression suite was run for this documentation-only update.

## Review decision / next experiment boundary

Synthetic ranker tuning remains closed. C154 closes the registered request-to-reference projection, not payload availability or durable production session integration. **No C155 is currently preregistered or implemented.** The next candidate boundary is provenance-bound payload dereference/re-observation using trusted snapshot metadata; this is a planning direction, not an active experiment or execution instruction.

Before reusing the C154 runner template, distinguish source/execution INVALID from valid negative projection behavior: several registered FAIL conditions currently raise exceptions caught as INVALID. This does not change the observed C154 PASS, but the classification must not be used to retry away a genuine negative. Existing experiment code is unchanged by this review.

The epoch/generation -> evidence-time/revision mapping is diagnostic-only. Cross-source namespaces, changing snapshots, replacement/retraction, concurrency, persistent publication, Controller and ANSWER require their own explicit contracts. Do not silently erase request-level audit history after record-reference deduplication.

## Independent research reports

**Multi-Axis Shared Basis:** separate architecture hypothesis, previously reviewed. MA-1 is not proved by C150-C154 and is not folded into V5-E integration.

**PC-ALM / FOLD Hybrid Local Credit (FHLC):** new report `fold/docs/pcalm-layer-local-credit-hypothesis-report.md` on main at `903e31f1e509c92877206741672918e7bacc701b`, blob `62f61588de77d9c277f4dcac2170ba29db0a1a03`. Original report is not copied/merged/rewritten by this update. Review is recorded in `experiment-ledger-addendum-c154-pcalm-review.md`.

Decision: retain an independent research candidate; not standard FOLD training or an executable preregistration. Proposed PA-0..PA-6 belong to a separate track. Before execution: fix finite-iteration timing, output/hidden boundary and reduction scales; separate exact chain-rule factorization from approximate global credit; compare gradients at the same weights/state; keep authoritative evidence immutable during local dynamics; account for all primal/dual/graph/reduction costs; quantify gates and tuning budgets. CE validation cannot be skipped before Shared Basis adoption. PA-0 has not been implemented, run or formally preregistered in this review.

## Non-claims

Gate E is still NOT PASSED. Shared-Basis partition, Multi-Axis, PC-ALM credit, KV/context work, ranking, persisted retrieval, request-level admission, EvidenceState projection, durable storage, re-observation and ANSWER are separate claims. `fold/fold_memory.py` is a QuadraticMemory reference, not the V5-E store. Oracle replacement, explicit supervision, manual composition and automatically discovered factors differ.
