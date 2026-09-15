# C155 verdict -> C156 request-bound reobservation

Reviewed/preregistered 2026-09-16 JST. V5-E integration. No production code change.

## C155 — ACCEPTED PASS

Execution commit: `ab8e29bc1d7fa3a9fa4cb786874aef4f5b881fe4`.
Evidence: user's complete terminal log `貼り付けられたテキスト（1 点）(20260915-214100).txt`.
Reviewer-computed uploaded-log SHA256: `4bda88bb68b903b6ded14626eba5e4c39be0cf54be57e5ed684817981901314f`.
Full local report: `runs/c155-v5e-payload-dereference-2e18c0303d69421e8f1d21f9d0a3e2a1/summary.json`.
Report SHA256 printed by runner: `1ac82ec4c4e60e6c7586058d497096d602a861e191909ca2adfd685f1f2fb4aa`.
The reviewer parsed the console JSON and checked arithmetic; full local reports/resolution files were not supplied and formal integration was not independently rerun. Do not confuse the uploaded-log hash with the report hash.

| Registered measurement | Observed |
|---|---:|
| Focused regression | 388/388 |
| Source states / references | 48 / 3072 |
| Resolver calls | 12288 |
| RESOLVED | 3072 |
| SOURCE_UNBOUND | 3072 |
| SNAPSHOT_MISMATCH | 3072 |
| RECORD_UNBOUND | 3072 |
| Failed cases / state mutations | 0 / 0 |
| Real adapter calls / scored vectors | 3072 / 196608 |
| Resolved zero / one | 1296 / 1776 |

All 48 streams completed. C154/C153 inputs, original snapshot files, C37, fixture, tracked tree and execution HEAD passed the reported checks. No model loading, neural scoring, fresh seed, training, Controller, ANSWER or new observation commit. The existing C145 helper emits a scalar-conversion warning but passes; that warning is not a C155 execution failure.

Claim: in the fixed trusted-snapshot setup, actual V5 EvidenceState references recover their corresponding persisted bit values, including zero; the three registered unbound/mismatched conditions expose no value and make no payload read. This is a read-only representation/resolution boundary, not learned relevance, query-answer accuracy, concurrent freshness, cryptographic source authentication, durable state publication or Gate E completion.

Source semantic bookkeeping remains WITHIN_FACTOR 20727/20736 and GLOBAL_CONCEPT 20736/20736 in each layout. These counts are not new post-readback task scores. All 64 records eventually occurring in each state cannot repair the original nine wrong query selections. The 3072 references repeat the same 64 records in 48 separate states, not independent facts/tasks. Reported wall time 2.0278062 seconds is this diagnostic run, not a production inference benchmark.

## Next boundary and rationale

C155 enumerates record references, not the current query's request. A consumer must not read an arbitrary available record merely because EvidenceState is nonempty, and must not retain a previous query's payload after a failed dereference. C156 therefore restores the original **request -> selected record reference** binding and refreshes the actual working-state evidence channels. It does not reopen synthetic ranker tuning or introduce a new router training exercise.

## C156 — ACTIVE, awaiting user CPU execution

Experiment `C156-v5e-request-bound-reobservation`; stage `V5-E-REQUEST-BOUND-REOBSERVATION`.

**Question:** can a C153 request's selected reference be dereferenced into the existing WorkingState/control-input schema, preserving request identity and evidence clocks while clearing stale payload/presence on unresolved reads?

```text
pinned original C153 request -> selected key + source/provenance
    -> exact matching ref in actual C154 EvidenceState
    -> unchanged C155 resolver + real persisted adapter
    -> actual WorkingState / advance_internal / BudgetState
    -> existing canonicalize_boolean_channels, working tensor only
```

No learned Controller forward pass or ANSWER is included. Context eligibility and operation-ID inputs are not newly constructed or validated here. This tests the working-input side of reobservation, not the whole controller pipeline.

### Changed and held constant

One new boundary: per-request resolved/unresolved readback -> refreshed working state and its signed control channels.

Held: accepted C155/C154/C153 reports and per-stream files; existing resolver/adapter/state/canonicalizer implementations; original snapshot paths/hashes; original selected record identities; no new language query, selection, training, fresh seed, source-semantic repair, durable commit or observation acquisition. Both source arms, layouts, and all twelve old artifact seed labels are retained.

A request's binding is diagnostic metadata derived from the pinned C153 trace, not a learned query resolver. Expected values enter only the evaluator after working inputs have been built. Reobservation has no expected-value or semantic-label parameter. Even an authentic but irrelevant selected record remains the source-selected record.

### Scenarios per original request

| Condition | Modification | Expected status | Adapter reads |
|---|---|---|---:|
| MATCHED | Exact bound reference/source | RESOLVED | 1 |
| MISSING_REFERENCE | Remove only that ref in an isolated diagnostic state branch | REFERENCE_UNBOUND | 0 |
| MISSING_SOURCE | Empty registry | SOURCE_UNBOUND | 0 |
| WRONG_SNAPSHOT | Bind the source ID to the other original snapshot | SNAPSHOT_MISMATCH | 0 |

The absent-reference condition must not synthesize a new ref from a catalog handle or read one of the other 63 observations. Input state files are never changed. Same-key/wrong-provenance, wrong readback key/scope/source and inconsistent payload responses are additionally checked by helper tests.

For each branch start with the same deliberately stale WorkingState (`evidence_present=1`, old bit alternates by case ordinal), internal step 7, internal budget 3 and acquisition budget 2. These values are fixed fixture choices, not inferred production settings. Replace only channels 2 and 3; preserve base/dependency and channels 4..7. `advance_internal` performs k=7->8 and internal budget 3->2. EvidenceState identity/time/revision and acquisition budget stay unchanged. Four branches are alternatives from the same initial state, not a sequential four-step loop.

Raw control channels follow C108/C113: base, dependency, evidence_present, observed bit. The existing canonicalizer maps channels 1/2/3 from 0/1 to -1/+1 for the router working tensor `[batch,1,8]`:

- valid bit 0: presence/value = `(+1,-1)`, explicit `Observation.value=0`;
- valid bit 1: `(+1,+1)`;
- unresolved: `(-1,-1)`, explicit `Observation.value=None`, no accepted EvidenceRef.

The -1 placeholder is not an asserted false fact: its presence channel is false. No readback advances evidence time or claims that rereading acquired a new observation. Exact-read costs remain separately visible; unchanged acquisition budget does not mean reads are free.

### Size and input validation

48 streams x 1728 original requests = **82944 requests**.
4 conditions/request = **331776 reobservations**.
Matched = **82944 actual exact64 reads**, **5308416 scored vectors**.
Other conditions = **248832 unresolved views without a read**.
Fresh seeds/training steps/model loads = **0**.

Validate all three pinned reports, reaggregate all C155 resolution files, and reuse C155's C154/C153 state-lineage validation. Retain original request identifiers and traces. Check all source files again at completion. Do not recreate missing artifacts, relocate snapshots, or rewrite hashes. C155 statuses/counts are prerequisites, not a newly measured result.

Save all request/scenario readbacks and raw/signed control channels to per-stream JSONL with hashes and serialized byte counts. This costs additional diagnostic storage and is not a production session serializer. Console output is per stream, not per 331776 view.

### PASS / FAIL / INVALID

PASS: every registered view has the expected status, request/reference identity, correct value or None, exact raw/signed input channels, unchanged evidence state/clock and old working object, exactly one internal-step debit, zero acquisition debit and the registered read/scan counts. Zero and one must both be covered. No semantic correction claim is made.

VALID NEGATIVE / FAIL: valid sources but measured wrong request binding, stale-payload leakage, wrong control channels, changed state, incorrect clocks/budget or read accounting. Retain per-case failures and emit a valid FAIL summary; no threshold or fixture adjustment under the same number.

INVALID: source/hash/file/lineage failure, invalid input schema, unhandled execution/numerical exception or outer branch/protection failure. Retain invalid output where available and retry C156 only after fixing execution validity. Unit tests explicitly check that a measured wrong payload makes the evaluator false, rather than being relabeled invalid.

Gate E remains NOT PASSED. No C157 registered. PC-ALM/FHLC and Multi-Axis remain independent; neither starts here.

### Reviewer verification

New files: benchmark, CLI, 24-test helper file and PowerShell runner, plus this addendum and handoff update. Reviewer **24/24 CPU helper tests passed** and Python compilation passed. Exact local production dependency copies were verified by Git blob SHA: state `aa3f4938f6b5d403d8ee05c4220f686695cef3f0`, controller `e726bdb05cb0b99b409448f8f56832078658dd04`. They are test preparation only and are not committed changes.

The helpers use controlled resolver responses to isolate the new bridge; they do not independently rerun C155's real adapter integration. Formal run uses the unchanged C155 resolver with the actual adapter. Full **412-test suite (388+24)**, user's real artifact chain, full C156 integration and PowerShell execution were not reviewer-executed. No formal C156 result claimed.
