# C165 verdict and handoff boundary

Recorded 2026-09-16 JST from the user-uploaded complete console log.
Preregistration: `experiment-ledger-addendum-c165-preregistration.md`.
Previous accepted verdict: `experiment-ledger-addendum-c164-c165.md`.
This acceptance is recorded before any C166 registration. C160 remains ACCEPTED VALID NEGATIVE.

## 1. Formal verdict

**C165 — ACCEPTED PASS**.
Experiment `C165-v5e-live-query-permission-denied`.
Stage `V5-E-LIVE-QUERY-PERMISSION-DENIED`.
Execution branch `feat/sft-target-loss`; execution HEAD `4dfc1634ea4a18f70390807011a83f60654e1b00`.
Diagnostic only; production runtime was not modified. **Gate E NOT PASSED**.

The registered permission-only comparison completed its full coverage with valid setup/postchecks and no finite behavioral failures. No threshold, checkpoint, case, layout, scope or seed was changed to obtain this verdict.

## 2. Evidence identity and execution validity

- Uploaded log: `貼り付けられたテキスト（1 点）(20260916-045917).txt`.
- SHA256 of the actual uploaded bytes: `01a3c05d7c08b59be6682ff2593fe524522cfc50c892f1efc90309bbcf9fcc1b`.
- C165 report: `runs/c165-v5e-live-permission-denied-e8e5f5d4b9504812bfeeecba65db79d7/summary.json`.
- Report SHA256 reported by the runner: `7cdfbf97fec85bb28e3fbc3fe4cbb470ec4497c31dbec33879d7b442097724c6`.
- Permission plan SHA256: `5d84b8a80dad07487c936393625f72267a0ffb8266e29ee69b2edba6eda3ebea`.
- Guard controls SHA256: `8c6ada9f2e8f694736e4ca381509d487d566883cd1097514b6973998a08a3f3b`.
- Accepted C164 parent SHA256: `42df47fe4c03d24df064ff47eecf5b3c84b8df2f36d6a47b7f861ac14778fed2`.

Focused regression **665/665 PASS**, 8.338 seconds. All 384 progress entries report failed=0; final branch episode count is 165,888. C151 ranker replay is 41,472 cases plus 288 original12 cases. C159 recorded-emission replay is 6,528 calls. These are prerequisites, not new live episodes.

Frozen models: 24 rankers on CUDA float32/highest, three Controllers on CPU, two threads. Training steps=0 and fresh seeds=0 in the benchmark. Environment reports torch 2.10.0+cu130 / CUDA 13.0 / NVIDIA GeForce RTX 4070 Ti SUPER. Runner uses `.venv-py31315/Scripts/python.exe`.

All 596 consumed inputs were rehashed and preserved. C37, the protected fixture, C164 parent, historical source blobs, tracked tree and execution HEAD were preserved. Weight mutations=0, output mutations=0, serialization failures=0. `diagnostic_execution_valid=true` and `run_execution_valid=True`.

The C145 tensor-to-scalar warning occurs inside a passing historical regression and is not C165 execution invalidity.

Reviewer parsed the uploaded JSON and independently checked 106 aggregate/identity/progress/postcheck consistency assertions against the preregistration and inspected source. This is **not** a new formal test count or a raw-trace replay. Console `records` is omitted; the full report SHA256 is retained as runner-reported, not independently reconstructed. The reviewer did not read the user's 48 new trace files or rerun the learned-model experiment. Distinguish log validation, source inspection and user-side artifact checks.

## 3. Deciding metrics

| Metric | Allowed | Permission denied | Total |
|---|---:|---:|---:|
| Branch episodes | 82,944 | 82,944 | 165,888 |
| Failed episodes | 0 | 0 | 0 |
| Controller decisions | 165,888 | 165,888 | 331,776 |
| Executed acquisitions | 82,944 | 0 | 82,944 |
| Publications/restorations | 82,944 | 0 | 82,944 |
| Exact64 adapter calls | 165,888 | 0 | 165,888 |
| Vectors scanned | 10,616,832 | 0 | 10,616,832 |
| Typed ANSWERED | 82,944 | 0 | 82,944 |
| Typed UNRESOLVED | 0 | 82,944 | 82,944 |
| Terminal correct | 82,944 | 82,944 | 165,888 |

Shared prefix: 82,944 newly executed rankings / 5,308,416 candidate scores. Each prefix has two fresh independent cold continuations; these are not 165,888 independent raw queries.

Each Controller has 27,648 episodes per condition / 55,296 total. Raw actions: RETRIEVE(2)=165,888; ANSWER(0)=82,944; STOP(5)=82,944. Minimum expected-action margin: allowed `6.142457485198975`; denied `5.3444743156433105`.

Denied-specific counts are all 82,944: first authority PERMISSION_DENIED, acquisition budget preserved, no unpermitted fetch, and payload-free unresolved output. Acquisition allowance stays 1; internal steps are still consumed by reobservation/decisions. UNRESOLVED reason is PERMISSION_DENIED, not MISSING_DELIVERY or BUDGET_EXHAUSTED.

Normal output values: zero=34,992 / one=47,952. Every arm/layout has 20,736 bound outputs; semantic_correct remains WITHIN_FACTOR=20,727 and GLOBAL_CONCEPT=20,736. Known nine WITHIN_FACTOR failures repeated across two layouts remain 18 instances, not 18 novel error types. Denied semantic_correct is null/not applicable.

Emitter accounting: 165,888 native tuple controls and 165,888 adapted candidates; every native control rejects MALFORMED_EVIDENCE; all content/type/input checks pass. Adapted reasons: OBSERVED_VALUE=82,944 / PERMISSION_DENIED=82,944. Guard probes=768, passed=768, failed=0 over 128 source/record identities. New emitter calls total 332,544; old C159 replay calls remain separate.

## 4. Scientific interpretation

```text
raw query -> frozen live ranker selection (shared prefix)
  -> identical learned RETRIEVE proposal
       |-- Permission(True) -> fetch -> admit/project -> readback -> ANSWERED(bit)
       `-- Permission(False) -> no fetch/debit/publication -> reobserve -> STOP
                                                    -> UNRESOLVED/PERMISSION_DENIED
```

C165 supports separation of learned acquisition proposals from authoritative runtime permission on the fixed synthetic query-to-terminal composition. The permission flag is enforced after the raw proposal; it does not train or override the model's action. Runtime then exposes unavailability and the frozen Controller stops. The typed emitter copies the runtime reason and returns no answer payload.

This is not evidence that the model understands arbitrary policies, learns a general refusal concept, or reasons about whether permission is justified. It is also not target absence, retrieval miss, transport loss or semantic relevance abstention.

## 5. Confound audit / remaining limits

Only Permission.allowed differs between continuations. Ranking, selected identity, models, delivery, budgets, clocks, other 63 references and emitter stay fixed. Separate state/working/inbox/budget per continuation prevents using the allowed branch's restored reference in the denied branch. Expected semantic keys/values and condition names are confined to post-execution scoring or request identity, not learned inputs.

**Zero denied adapter calls is not zero total search/computation or zero file access.** The shared catalog ranking still occurs, and prerequisite loaders/fixture validation read source artifacts. The experiment tests dispatch of runtime evidence acquisition in this harness, not OS permissions, encrypted storage, confidential catalog access or a complete access-control system. There is no claim that the denied process could not access already-loaded fixture data.

Normal-first order is fixed, not counterbalanced. Repeated fixed synthetic episodes are coverage, not independent task/language generalization. No natural-language answer generation, initial empty world, new external epoch, budget-exhausted raw-query path, warm query-originating read path, durable publication or production rollout is established here.

Diagnostic wall-clock=855.9414085000026 seconds; PyTorch peak allocated=11,956,224 bytes and reserved=25,165,824 bytes. These include or reflect validation/replay/controls/serialization and small diagnostic models, not production query latency, full process VRAM or final FOLD capacity.

## 6. Handoff / next-C boundary

Accepted through C165. C160's valid negative and C161-C164 accepted passes remain unchanged. Gate E remains NOT PASSED. Historical core/C158-C165 experiment code, checkpoints, runs and preregistration thresholds remain immutable in this acceptance.

At acceptance, **no C166 is registered**. Update authoritative handoff first; any next-C design/preregistration must be a later change with one explicit scientific question. Multi-Axis and PC-ALM/FHLC remain separate research tracks.
