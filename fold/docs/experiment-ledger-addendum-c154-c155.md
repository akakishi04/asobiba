# C154 -> C155: provenance-bound payload dereference

Preregistered 2026-09-16 JST. V5-E integration; no model training or production mutation.

## Accepted starting point

C154 is **ACCEPTED PASS** within request-to-record-reference projection scope: 363/363 focused tests; 48 states; 82,944 source request entries; 3,072 ADDED, 79,872 ALREADY_PRESENT, 3,072 provenance-conflict rejections; 64 unique OBSERVED references in each state. Source/protected hashes, tracked tree and execution HEAD passed according to the supplied full terminal log. Detailed review and the separate PC-ALM review remain in `experiment-ledger-addendum-c154-pcalm-review.md`.

C154 execution commit: `8768303869d6ee24d72cc98a9690219a4205a495`.
C154 report: `runs/c154-v5e-evidence-state-projection-ddacda18a60e4b7b91c370155ae5551c/summary.json`.
SHA256 printed in the accepted user log: `4814c9489b76bfb124e7134336611a3f513eb922083b0eca251be533820c4284`.
C153 report: `runs/c153-v5e-evidence-admission-6a96d53560a0454082d0ae22c143fdf0/summary.json`.
SHA256: `cddf360fc2211302d1dab0abd8d96038bb3d39ab273f9dea336da348d70d3a78`.

The full local C154/C153 report and state files were not supplied to the reviewing agent. Their hashes will be verified locally during C155; the reviewer does not claim an independent formal rerun. No C154 verdict is changed.

## C155 — ACTIVE, awaiting user CPU execution

Experiment: `C155-v5e-provenance-bound-payload-dereference`.
Stage: `V5-E-PROVENANCE-BOUND-PAYLOAD-DEREFERENCE`.

**Question:** can actual C154 EvidenceState references recover their stored Boolean payload through a trusted, provenance-bound snapshot registry, while an unbound source, wrong snapshot and unbound record expose no value?

The one new boundary is `EvidenceRef -> trusted snapshot/record handle -> real persisted payload read`. No encoder, controller, evidence publication or learning change is included.

```text
C154 EvidenceState (identity + provenance only)
    -> ref.provenance.source_id
    -> registry: source SHA + index fingerprint + canonical path + diagnostic clock
    -> selected record key -> handle without payload
    -> existing PersistedStructuralRetrievalAdapter, explicit exact64
    -> checked identity/provenance + stored value, including zero
```

The registry is **not learned**. It is reconstructed from the exact hash-pinned C153 accepted request metadata. C153 entry values are used only by the post-read evaluator, not by the resolver or its handles. Record signatures/scope come from the original persisted snapshot after checking its hash and adapter fingerprint. The C154 three-field source digest is reproduced exactly; no silent source-ID/clock redesign is introduced.

## Source validation and fixed conditions

Require both exact report hashes, the full 48 streams and every named C153/C154 state file with its declared hash. File names cannot escape the input run directories. Compare every decoded C154 reference and order against the unique record references implied by the accepted C153 entries, including scope/request claims and diagnostic clock mapping. Preserve the full request trace; do not infer corrected query outcomes from set coverage.

All 48 states and 64 refs/state are included, regardless of source arm or seed. These are **3,072 reference observations over the same 64 corpus records**, not 3,072 independent facts or new tasks. The 12 old seed labels only identify artifacts; fresh seed count is zero. C153 semantics are reaggregated as source bookkeeping (WITHIN_FACTOR 20,727/layout, GLOBAL_CONCEPT 20,736/layout), not reevaluated as new query/answer accuracy.

Load the two original C152 persisted snapshots at the absolute paths recorded in the accepted C153 entries. Require the original path, file SHA, index fingerprint, source clock and record count. If files have moved or are absent, stop with INVALID; do not search for another file or rewrite provenance to make the run pass. Adapter contents are loaded once and remain fixed; no claim about concurrent file changes or remote freshness is made. Source files, both sets of state files and reports are hashed again at completion.

## Registered conditions per reference

| Scenario | Intervention | Expected result | Actual adapter reads |
|---|---|---|---:|
| MATCHED | Correct reference and trusted registry | RESOLVED, exact key/provenance/value | 1 |
| MISSING_SOURCE | Registry has no binding | SOURCE_UNBOUND, no evidence/value | 0 |
| WRONG_SNAPSHOT | Reference source ID points to the other valid snapshot binding | SNAPSHOT_MISMATCH before payload read | 0 |
| MISSING_RECORD | Same source, synthetic nonregistered record key | RECORD_UNBOUND, no evidence/value | 0 |

Wrong-snapshot injection changes only a diagnostic registry mapping, never source files or EvidenceState. The missing-record reference is a separate immutable control, not added to source state. This is not absence detection in natural language: an unbound reference does not prove that a real-world fact does not exist.

Both stored values 0 and 1 must occur in matched reads. Successful zero returns `RESOLVED` with `value=0` and an evidence object. All unsuccessful resolutions return `value=None` and `evidence=None`; no zero/default, alternate-source search or exact-recovery fallback is allowed.

The exact64 adapter is an intentionally measured reference path, not an O(1), bounded-latency or production-scaling claim. Signature lookup uses pinned handle metadata; the returned payload must come from a real adapter call, not the old inbox value or an answer-key table.

```text
48 states x 64 refs = 3072 references
4 conditions/ref = 12288 resolver calls
MATCHED = 3072 real exact reads x 64 scored records = 196608 vectors
three unresolved controls = 9216 guarded resolutions with no payload read
```

Additional unit tests exercise actual exact-search miss, wrong returned key with the same bit, bad payload type/value, scope/provenance/cost errors, source tampering and duplicate read immutability. These are helper tests, not extra scenarios counted in the formal integration.

## PASS / valid FAIL / INVALID

**PASS:** all 12,288 expected statuses and invariants hold; 3,072 matched values and complete returned source identities agree; both bit values are covered; 9,216 controls expose no evidence/value and make no adapter call; 196,608 vectors are scored; all source states, clocks and files remain unchanged.

**VALID NEGATIVE / FAIL:** source setup is valid but a measured resolver result is incorrect (wrong/missing matched payload, wrong source exposed, zero/miss confusion, cost mismatch, state mutation, or guard bypass). Retain its per-reference outcome and write a valid `summary.json` with status FAIL. Do not raise a setup exception merely to retry the failed behavior away.

**INVALID:** wrong/missing prerequisite, input hash, state coverage, source binding/clock, missing original source files, decoding failure, unhandled execution exception, or failed outer protection checks. Keep `invalid.json` where the output directory has been established; fix and retry C155 without changing the registered experiment.

This explicitly avoids the C154 template's behavioral-FAIL-to-INVALID ambiguity without modifying any old C154 code or verdict. PASS and valid FAIL both have CLI exit code 0; unexpected exceptions are nonzero. The PowerShell runner independently checks commit, status/flag consistency and postchecks.

## Interpretation boundaries

PASS means existing observed references can be dereferenced in the declared trusted synthetic snapshot setup. Reading existing evidence is **not new observation acquisition**: evidence_time/revision do not advance, no new observation is committed, and no downstream Controller consumes it. No concurrent/durable state publication, restore/crash safety, learned retrieval/abstention, cryptographic security of arbitrary data, or ANSWER is tested. Exported diagnostic JSON is not a production Save/Load design. Gate E remains **NOT PASSED**.

PC-ALM/FHLC and Multi-Axis/MA-1 remain independent research candidates. No PA experiment or MA-1 starts as part of C155. C156 is not registered; judge C155 before selecting another boundary.

## Files and reviewer validation

- `fold_lm/v05_benchmarks/gate_e_c155_payload_dereference.py`
- `fold_lm/v05_benchmarks/gate_e_c155_cli.py`
- `tests_lm/test_v05_c155_payload_dereference.py`
- `tools/run_c155.ps1`

Reviewer ran **25/25 new CPU tests** successfully and compiled the new Python files. Used exact local copies of the existing production dependencies, verified by Git blob SHA: state `aa3f4938f6b5d403d8ee05c4220f686695cef3f0`; retrieval adapter `5324f7c8d52190e82a5db7cd3cb5503afb6c5831`; StructuralIndex `e213a96ee100449117cb8998f8ecba8b38b66e04`. Those copies are test preparation only and are not published changes.

A separate synthetic plumbing smoke exercised the full 48-stream/3,072-reference loop with fabricated source artifacts and the real adapter. It produced PASS; a deliberately wrong returned value produced a valid FAIL (48 affected cases), not INVALID; a corrupted source state produced INVALID. This verifies plumbing and classification, **not the user's artifact chain or a formal C155 outcome**.

Expected focused suite is **388 tests = 363 prior + 25 new**. Full focused suite, actual user's C154/C153 artifacts and PowerShell execution were not run by the reviewer. No formal result claimed.
