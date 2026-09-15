# FOLD experiment ledger addendum — C151 to C152

## C151 — ACCEPTED PASS (same-task cross-split replication)

Experiment `C151-v5e-cross-split-replication`, stage V5-E. Execution commit `1e8c4bfa18f3c28a654e6530ac56909a484411fb`.
Evidence: user's full terminal log `貼り付けられたテキスト（1 点）(20260915-163454).txt`, SHA256 `ebe0a662af0c7765aa573fe9125169d3b08ccf88bb8f96c88dc137206ee54dc9`. Reviewed 2026-09-16 JST. The reviewer parsed the supplied log, not the user's full local records or checkpoints, and did not rerun the CUDA experiment.
Full local report: `runs/c151-v5e-cross-split-e9d383a3c4c64f9faca48eb81313d441/summary.json`.
**C151 full-report SHA256:** `d2b48acb36d28f0422d09067cc23af882c812d020a00ccfc8c6e8286fd896afa`.
Split-plan SHA256: `db65d4754e465c55bfc19438f9d50324bb49e928911a53643deddc531625f4c0`.
Evaluation-manifest SHA256: `5a19de10d8152ac262846682a79a13bb942eeacd7dca979afb09b70170ebdd65`.

Focused regression **298/298**. Four registered replacement splits, three fresh paired initializations per split, 24 heads; seeds `20261721..20261732`. All declared paired-initialization, evaluator-reference, immutable-weight, source/protected-file, tracked-tree and execution-HEAD controls passed. `run_execution_valid=True`. The C145 helper's scalar-conversion warning is not a test failure or C151 performance result.

| Measurement | WITHIN_FACTOR | GLOBAL_CONCEPT |
|---|---:|---:|
| Correct full rankings | 20,727 / 20,736 | 20,736 / 20,736 |
| Errors | 9 | 0 |
| Exhaustive positive-margin model passes | 11/12 | 12/12 |
| Original12 strict model passes | 12/12 | 12/12 |
| Minimum full-catalog margin | -0.0321333110 | +0.1315777004 |
| Current-train correct, aggregated across splits | 2,592 / 2,592 | 2,592 / 2,592 |
| Held-out correct, aggregated across splits | 18,135 / 18,144 | 18,144 / 18,144 |

| Split (3 models each) | WITHIN errors | GLOBAL errors | WITHIN min margin | GLOBAL min margin |
|---|---:|---:|---:|---:|
| S1 | 0 | 0 | +0.0066914856 | +0.1651229858 |
| S2 | 9 | 0 | -0.0321333110 | +0.1315777004 |
| S3 | 0 | 0 | +0.0166789293 | +0.1486018300 |
| S4 | 0 | 0 | +0.0175899267 | +0.1398902535 |

Paired result: **9 rescues, 0 new errors, 20,727 both correct, 0 both wrong**. All nine errors belong to the WITHIN_FACTOR model for **S2 / seed 20261726**, are held-out under that split and have COLOR-only mismatch. The exact queries/selected descriptors are not printed; do not invent them or treat nine errors as nine independent seed replications. Three splits have no accuracy contrast because both arms are perfect.

**Claim:** the fixed GLOBAL_CONCEPT recipe meets its registered strict ranking gate on all four replacement training splits and all twelve initializations within the same closed synthetic vocabulary/task. Its success is not confined to the original eight main-training combinations. **Non-claims:** general superiority at statistical significance, unseen-token semantics, independent task-family generalization, automatic factor discovery, calibrated confidence, orthogonality, scalable retrieval, actual evidence acquisition, commit, ANSWER or Gate E completion. Auxiliary positive correspondences still cover all 36 aliases. All older scoped verdicts remain unchanged.

## Review decision

Close further tuning of this synthetic composition task and its replacement splits. Retain both recipes/checkpoint families, with GLOBAL_CONCEPT a task-scoped research candidate. Do not add new losses, coefficients, training steps, wider heads or new split searches to chase a larger headline metric.

The next question crosses a **runtime component boundary**, not another accuracy intervention. Connect the frozen candidate selector to the existing persisted retrieval adapter and validate returned identity/provenance. Do not simultaneously add a router, learned abstention, commit protocol or language-generation head. Independent task-family/language evaluation remains a separate unresolved requirement; this integration is not a substitute for it.

## C152 — ACTIVE, awaiting user integration execution

Experiment `C152-v5e-frozen-persisted-retrieval-bridge`, stage `V5-E-FROZEN-PERSISTED-RETRIEVAL-BRIDGE`.
**Question:** can the unchanged frozen C151 selector retrieve and validate the evidence belonging to its selected candidate through the real persisted adapter, without confusing candidate positions with record identities when catalog and storage order change?

```text
C151: raw query -> frozen composed encoder -> selected candidate index -> ranking score
C152: raw query -> SAME encoder -> selected catalog handle
      -> existing PersistedStructuralRetrievalAdapter / StructuralIndex
      -> actual persisted RetrievalEvidence -> identity/provenance validation
```

### Frozen inputs and corpus construction

Use **all 24 C151 checkpoints**, both WITHIN_FACTOR/GLOBAL_CONCEPT arms and all four splits. Fresh seeds and training steps are **zero**. No retraining or favorable-model selection. Require exact C151 report, plan and manifest hashes; reaggregate all source full/original12 outcomes and split/paired metrics. Checkpoint filenames are derived from registered split/seed/arm, not trusted as arbitrary paths. Load with `weights_only=True`; validate byte hashes, vocabulary, configuration, scope/composition metadata and tensor fingerprints.

First replay every one of the **41,472 original full rankings plus 288 original12 controls** with discrete outcomes equal and score/margin differences at most `1e-5`. Source WITHIN_FACTOR errors must remain errors, not disappear by consulting expected labels.

Generate 64 persisted records from the existing candidate **descriptors only**, before model execution. A companion catalog exposes descriptor, stable key and request signature, but not evidence values. Stable keys are full SHA256-derived identities; 64-dimensional one-hot signatures are explicit deterministic adapter plumbing. They are not learned fixed output classes or a proposed scalable indexing representation. The adapter's existing schema only supports Boolean-like integer payloads; generate 0/1 values from a fixed key hash. Key equality is mandatory: matching a single bit cannot establish retrieval correctness.

Persist and reload two equivalent snapshots:

- CANONICAL: original descriptor catalog order; physical corpus ordered independently by key.
- PERMUTED: cyclically shift every catalog position by one and reverse physical corpus order. Keep keys, descriptors, signatures and payload values unchanged.

Each snapshot has its own content SHA256, catalog-to-corpus hash binding and index fingerprint. Do not require fingerprints to be equal across reordered files. A selected catalog entry supplies the request structure. Never turn the displayed row index directly into a one-hot address. Candidate expected labels and values are consulted only after real retrieval, for scoring.

### Execution and costs

Per head and snapshot: 1,728 real adapter calls, each using declared **exact=True**, k=1 via the adapter and a structure threshold of 0.999999. All 64 records are explicitly scored per call. There is no hidden approximate-search fallback or evidence cache standing in for calls.

```text
24 frozen heads x 2 snapshots x 1,728 queries = 82,944 real retrieval calls
64 records scored/call = 5,308,416 adapter vector comparisons
In addition: source ranking replay, live catalog ranking and original12 replay controls
```

Report corpus/catalog bytes, index fingerprints, total setup/evaluation wall time, CUDA allocated/reserved peaks, per-snapshot calls/scan counts, selected/returned keys, actual payload, provenance acceptance and semantic correctness. This is an explicit full-scan integration reference, not a bounded-sublinear or production latency benchmark. Python/object/RAM overhead is not comprehensively profiled; do not claim total memory efficiency from the recorded bytes.

**Actual existing retrieval and provenance validation are exercised. Controller, evidence commit, exactly-once durability and ANSWER are NOT exercised.** No fake commit counter is introduced. Production code is unmodified; new glue stays in the diagnostic benchmark.

### Gate, validity and interpretation

**PASS:** source replay and catalog-order selection identity agree; all 82,944 calls bind the returned key/domain/schema/operations/source path/source hash/index fingerprint to the selected handle and have declared scan accounting; every payload matches that selected stored record. GLOBAL_CONCEPT additionally has all 20,736 semantically correct evidence results in **each** snapshot. WITHIN_FACTOR should retain its source nine semantic errors per snapshot; authentic wrong-record evidence must not be relabeled correct.

**VALID NEGATIVE / FAIL:** with input/replay/model controls valid, the actual bridge misses, rejects, misbinds or returns wrong payloads, or GLOBAL_CONCEPT evidence correctness falls short. This is an integration failure, not evidence that the learned ranker changed. Report binding correctness and semantic correctness separately.

**INVALID:** prerequisite/hash/source-reaggregation/checkpoint/replay/order-selection/numeric/immutability/execution discrepancy. Repair and retry C152 with the same conditions. Declared source-model errors are not invalid.

A PASS establishes this **selected-identity-to-persisted-evidence bridge only**. The catalog contains every requested target. No conclusion about missing-target detection, ambiguous queries, stale snapshot refresh, malformed natural language, rejection calibration or safe final answering follows. Provenance authenticates an internal trusted snapshot, not arbitrary third-party testimony or signatures. Unit-level negative controls test missing requested addresses and wrong provenance, but are not a learned open-set experiment. Gate E remains NOT PASSED. No C153 registered; review the next acquisition boundary after judgment, not more tuning of the synthetic ranker.

### Reviewer verification

**24/24 new CPU tests passed**, including the actual adapter/StructuralIndex reading 64 persisted records in both orderings, wrong-key same-payload rejection, provenance failures, zero-valued evidence, missing requested record, naive row-index negative control, immutable generation, replay checks and safely reconstructed toy checkpoints. Exact local test dependencies match Git blobs: head `afcf55267cd1fa6341b1fa058a0da4fb439f7ad6`, adapter `5324f7c8d52190e82a5db7cd3cb5503afb6c5831`, index `e213a96ee100449117cb8998f8ecba8b38b66e04`. These reference copies are test-environment inputs, **not changed repository files**.

Python compilation passed. Full **322-test** suite (298+24), actual full C151 source reaggregation/checkpoints, CUDA replay/integration and PowerShell are **not reviewer-executed**. No registered model was trained by the reviewer. Valid scientific FAIL returns exit code zero; execution exceptions return nonzero and preserve an invalid marker in the unique run directory. Source files and checkpoints are never overwritten.
