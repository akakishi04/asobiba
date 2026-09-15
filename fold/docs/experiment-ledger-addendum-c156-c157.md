# C156 verdict -> C157 learned Controller readback bridge

Reviewed/preregistered 2026-09-16 JST. V5-E integration; no production mutation.

## C156 — ACCEPTED PASS

Execution commit: `fe2b277341b62abf04bb51d284ce7fd288f15581`.
Evidence: user's complete terminal log `貼り付けられたテキスト（1 点）(20260915-220558).txt`.
Reviewer-computed uploaded-log SHA256: `98a9db2eeecbd8eebfc3befbd33c443d979734f55e78fd62b8d718e4060b5986`.
Full local report: `runs/c156-v5e-request-reobservation-0d0d4cb6c1704c4987ebf8651fc683e0/summary.json`.
Report SHA256 printed by the runner: `b2c43401a6731400de8e18697f82f5e220aeb3f2368737d9dee5847f7ca1f84f`.
The reviewer parsed the console JSON and checked the aggregate arithmetic. The full local report and per-stream JSONL files were not supplied; no independent formal rerun is claimed. The uploaded-log hash is not the report hash.

| Registered measurement | Observed |
|---|---:|
| Focused regression | 412/412 |
| Source streams / requests | 48 / 82,944 |
| Reobservation views | 331,776 |
| RESOLVED | 82,944 |
| REFERENCE_UNBOUND / SOURCE_UNBOUND / SNAPSHOT_MISMATCH | 82,944 each |
| Resolved zero / one | 34,992 / 47,952 |
| Behavioral errors / control tensor failures | 0 / 0 |
| EvidenceState / old WorkingState mutations | 0 / 0 |
| Actual exact64 reads / vectors scored | 82,944 / 5,308,416 |
| Internal-step debits / acquisition debits | 331,776 / 0 |

All 48 streams completed; prior reports and state/resolution/snapshot files passed the implementation's hash checks, and C37/fixture/outer inputs/tree/HEAD passed the reported postchecks. `run_execution_valid=True`. The old C145 helper's scalar-conversion warning is not a failing test or a C156 error.

Supported: each pinned request's selected reference was read into actual WorkingState and existing signed working channels; valid zero stays present; the three unresolved conditions remove old presence/payload instead of using another reference. Exactly one internal step is debited per independent scenario branch, without advancing evidence time/revision or acquiring/committing a new observation.

Not supported: a learned Controller consuming those inputs, answer generation, runtime permission enforcement, a live acquisition loop, semantic relevance recognition, changing/concurrent snapshots, durable publication or recovery. Source semantic counts remain bookkeeping: WITHIN_FACTOR 20,727/layout, GLOBAL_CONCEPT 20,736/layout. Authentic irrelevant evidence is not repaired. The 331,776 views are repeated controlled states over 64 records, not independent reasoning problems. Reported wall time 26.3767912 seconds is a diagnostic total, not production latency. Gate E remains NOT PASSED.

## C157 — ACTIVE, awaiting user CPU execution

Experiment: `C157-v5e-learned-controller-readback-bridge`.
Stage: `V5-E-LEARNED-CONTROLLER-READBACK-BRIDGE`.

**Question:** do the recorded C156 working inputs, combined with explicit current acquisition availability, make the existing learned Control Lane select the appropriate next action, including ANSWER for a resolved zero and no ANSWER for an unresolved read?

The one new boundary is accepted recorded working input -> learned action decision. This is not another ranker experiment or a full live replay of acquisition, admission and reobservation.

```text
hash-pinned C156 per-request raw/signed working inputs
    -> existing canonicalize_boolean_channels (reconstructed and checked)
    + explicit eligibility context and operation ID 0
    -> actual ControlLaneActionRouter forward
    -> raw action logits / argmax
    -> post-forward action/margin evaluation
```

No rule replaces a wrong model output. No action mask, forced ANSWER, expected action, semantic label, source record key or source arm enters the network. Expected actions are used only after logits have been obtained. The full eight working channels are preserved; the production router reads only its four-channel control lane.

### Controller preparation: training is explicit, not zero

C151-C156 provide ranking checkpoints and then recorded readbacks; this protocol does **not** claim to load an old accepted Controller checkpoint. Prepare three new reference routers using the existing, unchanged `gate_e_c113_stale_eligibility_preflight._train_router` function. Fresh router seeds: **20261741, 20261742, 20261743**. These differ from the twelve source artifact seeds 20261721..20261732. No registered C157 seed is used in reviewer helper tests.

Fixed C113 configuration: width 8, control width 4, hidden width 8, operation vocabulary 1, six actions; AdamW lr 0.01, weight decay 0; 900 optimizer steps; existing C112 natural-frequency sampling and C111 canonical input conversion; original logical training bases 0/1/2. CPU float32, highest matmul precision, two CPU threads. Source inputs use base channel 1.0, corresponding to the older held-out base 3 convention. The logical presence/availability policy is not novel training content.

Train all three routers before reading their bridge predictions, retain the final scheduled checkpoint, then freeze each for all evaluations. No checkpoint selection, new losses, seed substitution, retry-until-success, or width/step tuning. Save tensor/basic-metadata checkpoints, reload with `weights_only=True`, and compare exact weight fingerprints. A finite but poorly trained router remains an evaluated router and may produce a valid FAIL; it is not discarded as invalid.

### Availability conditions

Use both conditions for every recorded view; do not choose a mask based on whether the read succeeded.

| Context | Raw eligibility bits | If value is 0 or 1 | If value is None |
|---|---|---|---|
| RETRIEVE_AVAILABLE | (0,1,0,0) | ANSWER action 0 | RETRIEVE action 2 |
| NO_ACQUISITION | (0,0,0,0) | ANSWER action 0 | STOP_UNRESOLVED action 5 |

Context bits are canonicalized to -1/+1; other context channels are zero and operation IDs are int64 zero. These are **hand-specified availability fixtures**, not learned availability, external permission enforcement, recovery planning, or a claim that RETRIEVE will repair every unresolved cause. No selected acquisition action is executed. STOP is a proposed action here, not a tested multi-step termination property.

ANSWER action 0 means the Controller selects its answer branch under the existing logical policy. **No answer text or value is generated.** In particular, a present but irrelevant source record can still induce ANSWER. The source's nine semantic mistakes per layout are not inferable from this presence bit; no relevance correction is claimed.

### Source validation and size

Require the exact C156 report hash, full 48 stream records, and all declared JSONL hashes/byte sizes. Revalidate request IDs/scopes, observed provenance, scenario ordering, statuses, resolved integer bits versus None, raw/signed channels, internal clock/budget and recorded read costs. Reaggregate the status/value counts before training. Also hash every input artifact listed by the accepted C156 report, including the prior reports/state files and original snapshots. Missing files are INVALID; no silent reconstruction or relocation.

```text
82,944 source requests x 4 readback conditions = 331,776 recorded views
2 availability contexts x 3 new reference routers
= 1,990,656 learned decisions

Per router: 663,552 decisions
Expected per-router counts: ANSWER 165,888; RETRIEVE 248,832; STOP_UNRESOLVED 248,832
All routers: ANSWER 497,664; RETRIEVE 746,496; STOP_UNRESOLVED 746,496
ANSWER with value zero: 209,952; with value one: 287,712
```

**Only three distinct full working vectors and six distinct working/context/operation combinations occur.** The large count checks every original request row and the artifact interface; it is not millions of independent reasoning tasks or broad uncertainty generalization. There is no unique-vector caching: every row is forwarded in batches. With the fixed chunk of 4096 and 6912 views/stream, evaluation uses 576 batched forward invocations. Training forwards are separate.

No source ranker is loaded or retrained. No retrieval, actual WorkingState advancement, new observation, durable commit, Controller-driven action execution or answer generation is performed during C157. Input creation was C156's measurement; this experiment consumes its recorded artifacts.

Save actual logits, actions, expected actions and margins in per-router/per-stream compressed NPZ arrays. Axes are the two availability modes in fixed order, then original request order with the four C156 outcomes in fixed order. The summary binds each array to the source trace filename/hash and router checkpoint. Serialized bytes are recorded. This is diagnostic storage, not a production persistence or model-compression design.

### PASS / FAIL / INVALID

**PASS:** all three frozen routers choose every registered expected action with a strictly positive finite expected-action logit margin; both resolved bits are handled correctly; all decision counts and exact input/weight preservation checks hold. No probability calibration claim follows from a logit margin.

**VALID NEGATIVE / FAIL:** the source/setup is valid but any finite wrong action, nonpositive margin or measured input/weight mutation remains. Keep all model and case outputs. Do not replace action labels, filter seeds or retry away a learned failure.

**INVALID:** missing or altered source/artifact/recipe, malformed source schema, nonfinite training/output, unexpected execution exception or outer guard failure. Preserve invalid output and retry C157 after fixing execution validity. This does not change C156's accepted scope.

Gate E remains NOT PASSED. C158 is not registered; judge C157 first. PC-ALM/FHLC and Multi-Axis remain separate research tracks.

## Reviewer verification / files

New benchmark, CLI, 28-test helper file and PowerShell runner, plus this addendum and authoritative handoff. Reviewer **28/28 new CPU tests passed** and Python compilation passed. Exact local production `controller.py` was verified against Git blob `e726bdb05cb0b99b409448f8f56832078658dd04`; it is test preparation only, not a published modification.

Helpers cover full-shaped fabricated source decoding, scope/hash/clock/value safeguards, context construction, the actual production router's batched forward, wrong-output retention, strict margins and safe checkpoint reconstruction. Controller preparation is exercised with a controlled test trainer, not a formal C113 learning run. No fresh registered router was trained/evaluated by the reviewer. Full **440-test suite = 412 + 28**, user's actual artifact chain, formal Controller training/evaluation and PowerShell execution have **not** been reviewer-executed.
