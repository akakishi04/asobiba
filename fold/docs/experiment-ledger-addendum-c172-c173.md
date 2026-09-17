# C172 verdict and next boundary

Recorded 2026-09-17 JST from the user-uploaded C172 execution log.
Preregistration: `experiment-ledger-addendum-c172-preregistration.md`.
Acceptance precedes any C173 implementation or registration.

## 1. Formal verdict

**C172 — ACCEPTED PASS.**
`C172-v5e-typed-action-runtime-boundary`; `V5-E-TYPED-ACTION-RUNTIME-BOUNDARY`.
Execution branch `feat/sft-target-loss`, HEAD `e38ca796acd51dc54d6041ae69988f57592573e4`.
C170/C171 and earlier scoped accepted results remain unchanged.
C160/C168/C169 retain ACCEPTED VALID NEGATIVE. **Gate E NOT PASSED.**
C173 is not registered at this acceptance boundary.

## 2. Execution validity and artifact identity

Uploaded log `貼り付けられたテキスト（1 点）(20260917-003840).txt`, 167362 bytes.
Independently computed uploaded-byte SHA256:
`5d391b4c08a40e41be0cdfd2d1a5cf47953decb11dea95afcbbcd650c8eaa708`.
Report `runs/c172-v5e-action-runtime-dd06f1dd06d84fe8a0e215c04c76fac4/summary.json`.
SHA256 `b1698509fa5ab384b86731662092568e9348fe907ab9f4707ed0ea802709e943`.
Reviewer parsed the complete console summary and reproduced that hash using sorted,
indented UTF-8 JSON, LF and a final newline. This is not a user-machine rerun.
Plan SHA256 `31a56cfab6aef948085d503d6bbbe80092bc7cbfd0b3704d11460add8c32c10c`.
Detailed `action-results.json`: 197 rows, 971804 bytes, SHA256
`b9e08da4b713e4bf6859e4a3ce6f84f16a92341b06347e79e5d26ec4b5500fb7`.
Parent C171 SHA256 `4509a1e9fa5bf2072af18ac633fd2ee95ba2da35af4ab0dc3bc661437fc9853c`.

885/885 focused regression PASS in 6.496 seconds; 885 test-method lines counted
independently. Source precheck PASS. All eight registered groups complete.
38 declared input paths (including plan), 30 historical source pins, protected C37 and
composition fixture, output files, tracked tree and execution HEAD preserved per runner.
`diagnostic_execution_valid=true`, `run_execution_valid=True`.
`production_runtime_modified=false`, `gate_e_candidate=false`.
Existing C145 tensor-to-scalar warning belongs to a passing historical regression.
It is not C172 invalidity.

## 3. Metrics

| Metric | Observed |
|---|---:|
| Calls / failed checks |197 / 0|
| Acquisition reservations |27|
| Internal units charged |147|
| C171 verifier calls |46|
| Proof-rule evaluations |28|
| Actual provider calls / acquisitions / evidence writes |0 / 0 / 0|
| Learned forwards / training / fresh seeds |0 / 0 / 0|

Groups: external_grid48, local10, malformed24, stale12, pending15,
proof_rejection24, proof_budget40, fact_status24. Total197.
Status counts: PENDING27, STAGED14, VERIFIED_DERIVED10, UNRESOLVED5,
DENIED62, REJECTED79. These match preregistered accounting exactly.
The accepted fraction is not learned accuracy. Calls include dependent program steps.
Wall clock 1.8482976999948733 seconds is contract-benchmark time, not model latency.

## 4. Scientific interpretation

trusted current runtime + named proposal -> binding/permission/budget checks
-> unverified staging -> paid C171 proof check -> derived result / rejection;
or -> one reserved pending external intent; STOP -> unresolved closure.

Within the finite registered suite, stage/verify/close, stale or malformed proposal
rejection, pending duplicate suppression and resource accounting satisfy the contract.
No acquisition intent is promoted to an observed fact. A staged proof is not solved or
repaired by COMPUTE. Existing observation and proof components remain distinct.

## 5. Confound audit and limits

Scripted proposals and trusted fixture states, not learned policy performance.
No provider transport or reply admission ran. PENDING27 means reservations27, not fetches27.
Reservation duplicate suppression assumes a single trusted owner adopts returned states;
the digest is not a signature, OS access boundary, concurrent CAS or crash-safe receipt.
Internal units exclude Python validation/hash overhead and future neural compute.
The known limited proof-rule scope is unchanged. Runtime rejection is not semantic
abstention and the supplied correct proofs do not establish a learned reasoner.

The full summary was independently hash-reconstructed and checked against source,
preregistration, counts, status accounting, execution identity and postchecks.
The separate 197-row detail file was not uploaded: its hash/size and runner verification
are recorded, but no independent per-transition replay or 885-test rerun is claimed.

## 6. Ledger and next design

Keep C172 code, preregistration, report, plan and action-results unchanged. No rerun is
required merely for this acceptance or later new files. Update handoff before C173.
The next major missing connection is the reserved-intent-to-delivery lifecycle:
reauthorize actual dispatch, validate a matching response, publish only usable observed
payload with provenance, clear pending work, and let the unchanged task/proof path use
that admitted fact. Batch lifecycle controls rather than rediscover known source gaps.
No actual external account messaging, Vision or learned policy is authorized by this
paragraph. Exact next scope, fixtures, costs and decision rules require preregistration.
