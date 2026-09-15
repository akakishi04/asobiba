# FOLD experiment ledger addendum — C152 to C153

## C152 — ACCEPTED PASS (selected identity to persisted evidence only)

Experiment `C152-v5e-frozen-persisted-retrieval-bridge`; execution commit `7bd822c5b4086db7a09e83523fdfa75ac0bdfd0e`.
Evidence: user's terminal log `貼り付けられたテキスト（1 点）(20260915-170536).txt`, SHA256 `5c3f1ffbc25d3ba4919f9e65ab8ab5a63ba88eb00d90b40f81c14d12c681e7ad`. Reviewed 2026-09-16 JST. The reviewer parsed the log, not the full local records, and did not rerun the formal integration.
Full report: `runs/c152-v5e-persisted-bridge-c14bc4bd93e64087991290cb92e2b42a/summary.json`.
**Report SHA256:** `d70b57b6d7c0aa8876c0647ab1d858ec2808fd3478cf12c02b3d83be8cf2d844`.
Source C151 report SHA256: `d2b48acb36d28f0422d09067cc23af882c812d020a00ccfc8c6e8286fd896afa`.

Focused regression **322/322**. All 24 source heads replayed: 41,472 full rankings and 288 original12 controls. Fresh seeds/training = zero. Full replay, reordered selection identity, frozen weights and all reported input/C37/fixture/source/tree/HEAD guards passed. `run_execution_valid=True`.

| Arm / layout | Calls | Selected identity / provenance / payload / scan accounting | Semantically correct evidence |
|---|---:|---:|---:|
| WITHIN_FACTOR / CANONICAL | 20,736 | 20,736 in each metric | 20,727 |
| WITHIN_FACTOR / PERMUTED | 20,736 | 20,736 in each metric | 20,727 |
| GLOBAL_CONCEPT / CANONICAL | 20,736 | 20,736 in each metric | 20,736 |
| GLOBAL_CONCEPT / PERMUTED | 20,736 | 20,736 in each metric | 20,736 |

Total **82,944 actual adapter calls**, explicitly scanning 64 records/call: **5,308,416 vector comparisons**. Each layout's source hash/index fingerprint is independently valid; reordering does not require equal byte hashes. The source control's nine semantic errors persist in each layout; authentic provenance did not conceal them. These are repeated queries/models/layouts, not 82,944 independent tasks or new learning.

Reported setup time 0.4243875 s, benchmark wall time 18.5115101 s; CUDA allocated peak 11,631,104 bytes and reserved peak 25,165,824 bytes. These are this small diagnostic's measurements, not production latency, total process memory or full FOLD cost claims. The recurring C145 helper scalar-conversion warning did not fail regression.

**Supported:** within two registered trusted snapshots, selected catalog identities correctly connect to real persisted evidence despite catalog/storage reordering. **Not supported:** controller routing, evidence commit, duplicate/crash durability, ANSWER, absent-target detection, untrusted-source authenticity, arbitrary payload tampering detection or independent natural-language generalization. Gate E remains **NOT PASSED**. Earlier scoped verdicts remain unchanged.

## Review decision

Do not reopen synthetic-ranker optimization. Next isolate the **evidence admission boundary**: accept validated data into an explicit diagnostic state, reject bad deliveries without consuming a request, and suppress a repeated successful delivery. This is not authorization to claim a deployed FOLD session/memory integration. Keep controller, answering, concurrent/crash recovery, learned abstention and stale-snapshot refresh out of this experiment. Independent task-family/language evaluation remains open.

## C153 — ACTIVE, awaiting user CPU integration

Experiment `C153-v5e-validated-evidence-admission`; stage `V5-E-VALIDATED-EVIDENCE-ADMISSION`.
**Question:** can the C152 selection traces drive actual retrieval and a sequential validated state transition that rejects five controlled bad deliveries, admits the good evidence once, and leaves state unchanged on duplicate delivery?

```text
Pinned C152 selection trace (both arms/all heads/layouts)
-> same real adapter fetch (no labels/expected value argument)
-> request/scope/context/key/provenance/payload-type/cost validation
-> immutable diagnostic inbox entry + request claim
-> duplicate delivery: no second entry
```

### Changed and fixed

The added component is a **new diagnostic immutable in-process inbox**, not a production memory store. It uses existing `commit_context_matches` and pure `claim_receipt_once`; the claim and actual payload/provenance entry are returned in one new state value. The caller adopts that state only after validation. Rejected paths return the exact original state object. This demonstrates sequential all-or-nothing reference transitions, **not** concurrency, process-crash atomicity or durable exactly-once effects.

No model is loaded or reranked. Reuse the **recorded selections from all 24 C152 source heads**, both arms and both layouts. Thus model-loading, new scoring, fresh-seed and training counts are all zero. This is a trace-driven downstream integration, not a rerun of the full neural pipeline. Require the exact full C152 report hash and reaggregate all 82,944 source cases against the original catalog, payloads and C151 manifest; verify ordering and preserve source semantic errors. C151 report and manifest have pinned hashes. Checkpoints are neither read nor modified.

Reload the original C152 persisted snapshots. Every selected handle makes one new real exact adapter call over 64 records. The validator sees the selected request identity and trusted snapshot provenance, not the semantic answer key or expected payload. Grading consults ground truth only after admission. A control model's authentic but irrelevant record is admitted under its own identity and remains a semantic error; admission does not repair ranking.

### Seven submissions per request

For each actual retrieval, submit the following to the same current inbox, in this fixed order:

1. `MISSING`: replace delivered evidence with None. This is injected missing delivery, not learned missing-target detection.
2. `WRONG_KEY`: alter the returned key while keeping the same bit payload. Must not accept by payload equality alone.
3. `WRONG_SOURCE`: alter the returned source SHA256.
4. `WRONG_SCOPE`: alter the delivery's scope identity.
5. `STALE_REQUEST`: delivery epoch 0 against current request epoch 1.
6. Original good delivery: write its actual bit payload, selected key/domain/schema/operations, source path/hash, index fingerprint, request/scope/epoch/generation into a real state entry and claim the logical request.
7. Repeat that good delivery: report `DUPLICATE`; no state change.

The five fault envelopes are controlled copies of one actual provider result; do not count them as additional retrieval calls. Guards for provider generation, other metadata, scan costs, malformed payloads and wrong request identity are also covered by helper tests, not additional formal scenario families. This is a trusted in-process transport reference: source-name checks alone do not authenticate an arbitrary substituted payload bit.

### Size, outputs and limits

48 state streams (24 source-head traces x 2 layouts), each with 1,728 distinct logical requests. Same record may legitimately appear in multiple requests; deduplication is per logical request, not per record key.

```text
82,944 actual retrievals / expected new state entries
414,720 expected fault rejections (5/request)
82,944 expected duplicate rejections (1/request)
580,608 total delivery submissions (7/request)
5,308,416 declared adapter vector comparisons
```

Save all transition outcomes plus **48 actual state snapshots**, containing entries and processed request identities, with file hashes. These serialized inspection artifacts do not imply a tested restart/restore protocol. Immutable tuple/frozenset growth and full scans are unoptimized diagnostic costs; no production efficiency claim.

**PASS:** every prescribed rejection preserves state and leaves the request available; every good delivery produces exactly one complete entry and one claim; every duplicate preserves state; every stored payload matches the selected persisted record; exact scan costs match. Semantic correctness must remain GLOBAL_CONCEPT 20,736 and WITHIN_FACTOR 20,727 in each layout. All source/hash/immutability controls remain valid.

**VALID NEGATIVE / FAIL:** valid source/setup, but actual retrieval/admission/protocol outcomes violate those requirements. Do not label lost legitimate evidence, duplicate writes or accepting corrupted metadata as a successful test merely because a final counter looks correct.

**INVALID:** source hash/reaggregation/catalog/manifest/input identity or execution failure. Repair same C153 without changing cases or thresholds.

Controller=False; ANSWER=False; production state commit=False; crash recovery=False. No C154 registered. Review next integration scope after judgment, not further ranker tuning.

### Reviewer validation

**24/24 new CPU tests passed**, including actual `PersistedStructuralRetrievalAdapter`/`StructuralIndex` over 64 records in two storage orders, all seven submissions, zero-valued evidence, same-bit wrong-key rejection, stale epoch/generation, source/metadata/cost validation, reject-then-valid retry, exact duplicate-state identity, multiple requests for the same record, immutable entries and serialization.

Test dependencies exactly match repository Git blobs: commit-context `04f967a98f6486db36412e2ff3833f9d5b109751`, receipt-replay `f1890a8fec0a6f820a1b85fe20cf14551fdb0fb8`, adapter `5324f7c8d52190e82a5db7cd3cb5503afb6c5831`, index `e213a96ee100449117cb8998f8ecba8b38b66e04`. These local reference copies are not repository changes. Python compilation passed.

Full **346-test** regression (322+24), successful full C152 trace reaggregation, actual user's artifacts and PowerShell were **not reviewer-executed**. No CUDA is required for C153 itself. CLI exits zero for valid PASS/FAIL; exceptions are nonzero and leave an invalid marker. Output is a unique directory; sources/protected C37 are never overwritten.
