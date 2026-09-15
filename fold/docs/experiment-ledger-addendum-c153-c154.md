# FOLD experiment ledger addendum — C153 to C154

## C153 — ACCEPTED PASS (validated evidence admission, sequential diagnostic scope)

Experiment `C153-v5e-validated-evidence-admission`; execution commit `dc5f5d8bf72bc04692411c05213c824eb8c8c918`.
Evidence: user's full terminal log `貼り付けられたテキスト（1 点）(20260915-173848).txt`, SHA256 `6fb537ce4283a798fac33ec083db643f7527c0737dce774f944293b26d900eb8`. Reviewed 2026-09-16 JST. Reviewer read the supplied terminal log and repository implementation; the formal integration was not rerun by the reviewer.

Full report: `runs/c153-v5e-evidence-admission-6a96d53560a0454082d0ae22c143fdf0/summary.json`.
**C153 report SHA256:** `cddf360fc2211302d1dab0abd8d96038bb3d39ab273f9dea336da348d70d3a78`.
Source C152 report SHA256: `d70b57b6d7c0aa8876c0647ab1d858ec2808fd3478cf12c02b3d83be8cf2d844`.
Source C151 report SHA256: `d2b48acb36d28f0422d09067cc23af882c812d020a00ccfc8c6e8286fd896afa`.

Focused regression **346/346**. Source selection traces from all 24 C152 heads and both persisted layouts were reused. Model loading, new scoring, fresh seeds and training were all zero. The run performed **82,944 actual retrievals** and **580,608 delivery submissions** using the registered seven-step protocol. All input/protected hashes, tracked-tree checks and execution-HEAD postchecks passed; `run_execution_valid=True`.

Registered aggregate outcome:

```text
5 controlled rejection types/request x 82944 requests = 414720 rejections
1 valid admission/request                     = 82944 COMMITTED
1 repeated valid delivery/request             = 82944 DUPLICATE
```

For every arm/layout group, all 20,736 cases passed the admission protocol. Status counts were exactly 20,736 each for `MISSING`, `WRONG_KEY`, `WRONG_SOURCE`, `WRONG_SCOPE`, `STALE_REQUEST`, `COMMITTED`, and `DUPLICATE`. Every valid request produced exactly one immutable diagnostic inbox entry; each invalid delivery and duplicate preserved the prior state object. Exact scan accounting remained 64 vectors/request.

Semantic correctness was preserved rather than repaired:

| Arm / layout | committed entries | semantic correct |
|---|---:|---:|
| WITHIN_FACTOR / CANONICAL | 20,736 | 20,727 |
| WITHIN_FACTOR / PERMUTED | 20,736 | 20,727 |
| GLOBAL_CONCEPT / CANONICAL | 20,736 | 20,736 |
| GLOBAL_CONCEPT / PERMUTED | 20,736 | 20,736 |

Thus the authentic nine source-selection mistakes in the control arm remain semantic errors in each layout even though their selected evidence has valid provenance. Admission does not use answer truth to repair model decisions.

**Supported claim:** within this trusted sequential diagnostic setup, validated retrieval results can be admitted exactly once per logical request while five registered malformed/stale deliveries and a successful repeat leave state unchanged. Actual payload, selected record identity, snapshot provenance and request context are preserved in the admitted entry.

**Non-claims:** this is not a durable or production state commit, concurrent atomicity test, crash-restart test, cryptographic source authentication, semantic verification, learned missing-target detection, controller integration, re-observation, ANSWER, independent natural-language generalization or Gate E completion. `MISSING` is injected after a real retrieval, and source-name/hash checks do not prove arbitrary third-party content truth.

Gate E remains **NOT PASSED**. All previous scoped verdicts remain unchanged.

## Review decision

Do not repeat C153 fault injection or reopen synthetic ranker tuning. The next boundary should separate **logical request admission** from **authoritative evidence identity state**. C153 deduplicates per logical request and therefore legitimately admits many requests that point to the same persisted record. The existing V5 `EvidenceState`, however, requires unique `EvidenceRef.evidence_id` values and records observation provenance rather than request receipts.

Before durable commit or re-observation, test this representation crossing directly using the existing `fold_lm.v05.state.EvidenceState` contract. Do not simultaneously add payload dereferencing, SQLite durability, concurrency, crash injection, controller routing or ANSWER.

## C154 — ACTIVE, awaiting user CPU execution

Experiment `C154-v5e-evidence-state-projection`; stage `V5-E-EVIDENCE-STATE-PROJECTION`.

**Scientific question:** can all accepted C153 request-level entries be projected into actual V5 `EvidenceState` record-identity references so repeated requests collapse idempotently, while the same evidence identity with conflicting provenance is rejected without state change?

```text
C153 diagnostic inbox
  1728 request entries / stream
        |
        v
record identity + snapshot provenance
        |
        v
actual fold_lm.v05.state.EvidenceState
  one EvidenceRef per persisted record identity
```

### Changed variable / held constants

Changed variable: representation boundary only — request-scoped admitted `Entry` -> record-scoped `EvidenceRef` in actual V5 `EvidenceState`.

Held constant:

- exact accepted C153 report and all 48 state files;
- no model load, encoder, ranking, retrieval, new scoring, fresh seed or training;
- no answer truth is used to decide projection;
- C153 query-level semantic outcomes are only reaggregated after source validation and must remain unchanged;
- production modules are not modified; benchmark glue invokes the existing `EvidenceState`, `EvidenceRef`, `Provenance` and `ProvenanceKind` classes;
- each C153 arm/layout stream remains a separate EvidenceState because CANONICAL and PERMUTED snapshots have different provenance identities.

### Projection contract

For each C153 entry:

1. `EvidenceRef.evidence_id` is the selected persisted **record key**, never the logical request id.
2. `Provenance.kind = OBSERVED`.
3. `Provenance.source_id` is a deterministic digest binding the C153 `source_sha256`, `index_fingerprint`, and `source_path`.
4. In this diagnostic mapping, `request_epoch=1` maps to `evidence_time=1` and `provider_generation=1` maps to `revision=1`. This is an experiment-local compatibility mapping, not a final production clock contract.
5. First occurrence of a record key -> `ADDED` and a new EvidenceState value.
6. Exact repeated reference -> `ALREADY_PRESENT` and the exact same EvidenceState object.
7. Same evidence id with changed provenance -> `PROVENANCE_CONFLICT` and the exact same EvidenceState object.

The source task covers all 64 persisted identities per stream. Therefore the registered aggregate is:

```text
48 source streams x 1728 C153 entries = 82944 source entries
48 x 64 first record identities          = 3072 ADDED
82944 - 3072                             = 79872 ALREADY_PRESENT
one injected provenance conflict/new id  = 3072 PROVENANCE_CONFLICT rejections
48 final EvidenceStates x 64 refs         = 3072 final observations
```

`EvidenceState` intentionally stores the identity/provenance reference, **not the Boolean evidence payload**. Payload dereference/re-observation is deliberately left for a later experiment.

### PASS / FAIL / INVALID

**PASS:** exact C153 summary/state hashes validate; all 82,944 genuine source entries project with exactly the registered `ADDED`/`ALREADY_PRESENT` counts; every one of 3,072 same-id conflicting-provenance controls is rejected with state object identity preserved; all 48 final actual EvidenceStates contain exactly 64 unique OBSERVED references; source semantic totals remain WITHIN_FACTOR 20,727/20,736 and GLOBAL_CONCEPT 20,736/20,736 in each layout.

**VALID NEGATIVE / FAIL:** source execution is valid but projection loses or duplicates record identities, treats request ids as evidence ids, accepts conflicting provenance, mutates state on conflict/exact duplicate, or produces an invalid EvidenceState.

**INVALID:** C153 report/hash/state-file coverage, source request binding, protected artifacts, tracked tree, or execution controls are inconsistent. Repair and retry C154 without changing the registered counts or mapping.

A PASS establishes this representation crossing only. It does not establish payload availability from EvidenceState, re-observation, durable storage, restart recovery, concurrent exactly-once behavior, controller/answer integration, or Gate E completion.

### Reviewer preparation

New implementation:

- `fold_lm/v05_benchmarks/gate_e_c154_evidence_state_projection.py`
- `fold_lm/v05_benchmarks/gate_e_c154_cli.py`
- `tests_lm/test_v05_c154_evidence_state_projection.py`
- `tools/run_c154.ps1`

The new unit file contains 12 focused tests covering deterministic snapshot-source binding, record-key identity, OBSERVED provenance, payload rejection, new/duplicate/conflict state transitions, distinct identities, actual EvidenceState future-provenance guard, registered aggregate gate, strict C153 header, complete provenance binding and evidence-clock preservation. Existing `tests_lm.test_v05_state` adds 5 baseline state-contract tests. Expected focused suite: **363 tests** (346 prior + 5 state + 12 new).

Repository-side formal C154 execution, the user's real C153 state files and the 363-test PowerShell suite are not reviewer-executed at preregistration time. No CUDA is required by C154 itself. No C155 is registered; review the next boundary only after C154 judgment.
