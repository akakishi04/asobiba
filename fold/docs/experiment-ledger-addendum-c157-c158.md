# C157 verdict -> C158 bounded Controller-driven reference recovery

Reviewed/preregistered 2026-09-16 JST. V5-E integration; no production change.

## C157 — ACCEPTED PASS

Execution commit: `40f63b46c67d5c71a8e8bc75ac6ba07ddd3ef05a`.
Evidence: user's complete terminal log `貼り付けられたテキスト（1 点）(20260915-222700).txt`.
Reviewer-computed uploaded-log SHA256: `87e8ae858e3a88decdf42374a13fca5719a60a2aa98051023247a56430ab70d6`.
Full local report: `runs/c157-v5e-controller-bridge-e68cc92a350145b983d123acad386982/summary.json`.
Runner-printed report SHA256: `b521eafc61fedaf3b9d2f78fb9c591de654b95cfa6689938c8c042fbc200b934`.
The reviewer parsed the uploaded console JSON and checked counts and the registered gate. Full local report/checkpoints/NPZ arrays were not uploaded; the formal run was not independently repeated. The log hash is not the report hash.

| Measurement | Observed |
|---|---:|
| Focused regression | 440/440 |
| Newly trained reference routers | 3 |
| Router seeds / optimizer updates | 20261741..20261743 / 900 each |
| Recorded views / distinct full inputs | 331,776 / 6 working-context patterns |
| Learned decisions / evaluation batches | 1,990,656 / 576 |
| Wrong actions / nonpositive margins | 0 / 0 |
| Minimum expected-action logit margin | 5.344475269317627 |
| Completely successful routers | 3/3 |
| ANSWER / RETRIEVE / STOP_UNRESOLVED | 497,664 / 746,496 / 746,496 |
| Correct ANSWER with value zero / one | 209,952 / 287,712 |
| Input / weight mutation | 0 / 0 |

All recorded inputs, protected artifacts, tracked tree and execution HEAD passed the reported checks; `run_execution_valid=True`. The existing C145 scalar-conversion warning occurred in a passing test, not in the Controller result. Final training losses printed to eight decimals were 0.00021728, 0.00009998 and 0.00020829.

Claim: the three fixed-recipe reference routers consumed the accepted recorded working inputs plus two explicit availability contexts and selected the registered action, including ANSWER for a present zero and no ANSWER when unresolved. Raw model outputs were not replaced by a rule. The logit margin is not a probability or calibration result.

Non-claims: six repeated patterns are not nearly two million independent reasoning tasks. No live retrieval/reobservation, external action execution, answer text/value generation, learned semantic relevance, durable commit or recovery was measured. The old source semantics remain bookkeeping (WITHIN_FACTOR 20,727/layout; GLOBAL_CONCEPT 20,736/layout). An authentic irrelevant record still counts as present to this Controller. Reported 25.6644146 seconds includes validation/training/evaluation/storage and is not production inference latency. Gate E remains NOT PASSED.

## C158 — ACTIVE, awaiting user CPU execution

Experiment: `C158-v5e-bounded-controller-reference-recovery`.
Stage: `V5-E-BOUNDED-CONTROLLER-REFERENCE-RECOVERY`.

**Question:** can the frozen C157 Controller's actual action drive one authorized retrieval, validated in-process admission and reference restoration, followed by live reobservation and a terminal action, while denied or missing deliveries lead to bounded unresolved termination without stale payload use?

One new integration boundary: **act on the learned proposal and feed the resulting live state back**, rather than replaying independent recorded views. Existing C153 admission, C154 projection, C155 resolver, C156 working-state reobservation and production Controller/state primitives are reused, not redesigned.

```text
selected request/ref, current state and explicit availability
-> live C156 reobservation -> frozen learned Controller
-> if raw action is RETRIEVE, authoritative permission/budget check
-> real persisted adapter -> actual C153 admission -> C154 reference projection
-> live C156 reobservation -> same frozen Controller -> ANSWER action or STOP
```

There is no expected action, query target or expected payload argument to the cycle. Scenario names enter only fixture setup and post-execution assessment. Wrong finite actions remain in the trace and fail the experiment, not an override to the desired branch. Only RETRIEVE invokes acquisition. Unexpected actions do not trigger another tool. ANSWER remains a terminal action plus recorded readback metadata, not language generation or a learned Boolean answer head.

### Fixed models and exhaustive record-level coverage

Use **all three C157 checkpoints**, seeds 20261741, 20261742 and 20261743, frozen and safely reconstructed with `weights_only=True`. Fresh seeds/training steps = 0. No source ranker is loaded or trained.

Before new measurement, replay all **1,990,656 original C157 decisions** against the original C156 inputs and saved C157 NPZ arrays: exact actions/labels, logits and margins within absolute tolerance 1e-5, no relative tolerance, and unchanged weights/inputs. Validate the full pinned C157/C156 reports and every referenced input hash. C154/C153 state lineage is reaggregated by the existing C155 loader. Missing/relocated/modified artifacts are INVALID; do not recreate them or silently rebind a snapshot.

The new unit of coverage is a **snapshot/record binding**, not every past query. Reaggregate all 48 C154/C153 streams, then select one representative request for each of the 64 keys in each of the two original layouts. Representatives are selected deterministically by stored request identity (lexicographically smallest of the per-stream first representatives), never by correctness, payload or model scores. The representative's source state has all 64 refs. All repeated identities/values must agree.

Save all 128 bindings, request metadata, five scenarios and three router identities to `episode-plan.json` before replay/new decisions. Values are retained only in the evaluator's separate source-value table. No new natural-language query or relevance comparison is made. The original nine wrong query selections are neither repaired nor counted as newly solved. Six Controller input patterns still suffice for this fixture; the novelty is the sequential live integration, not a new learned policy.

### Five independent episodes per binding/router

| Scenario | Starting selected reference | Authority / acquisition budget | Expected raw action sequence | Actual exact64 reads |
|---|---|---|---|---:|
| WARM_PRESENT | Present | allowed / 1 | ANSWER | 1 readback |
| COLD_RECOVER | Only selected ref removed | allowed / 1 | RETRIEVE -> ANSWER | 1 acquisition + 1 readback |
| COLD_MISSING_DELIVERY | Only selected ref removed | allowed / 1 | RETRIEVE -> STOP_UNRESOLVED | 1 acquisition; response deliberately withheld |
| COLD_PERMISSION_DENIED | Only selected ref removed | denied / 1 | RETRIEVE -> STOP_UNRESOLVED | 0 |
| COLD_BUDGET_EXHAUSTED | Only selected ref removed | allowed / 0 | RETRIEVE -> STOP_UNRESOLVED | 0 |

`COLD` means the selected reference is missing from an isolated diagnostic branch of the state; the other 63 refs remain. It does not mean no prior world evidence or a new world snapshot. The original state files are untouched. Working state starts at internal step 7 with stale presence=1 and alternating old bit; non-evidence channels match C156/C157. Each live reobservation consumes one internal step via actual `advance_internal`; initial internal budget is 3. Acquisition budget is debited exactly once **after authorization**, including a dispatched acquisition whose delivery is subsequently withheld. Denied attempts incur no acquisition debit and make no adapter call.

Initial model-visible RETRIEVE availability is true in all five cases. It is intentionally stale-high for permission/budget denial. Runtime revalidation, not the model, prevents unauthorized execution. After the first proposal the current attempt is marked spent and visible eligibility becomes false, regardless of its outcome. The hard cap is three learned decisions and **at most one authorized acquisition attempt**. A broken Controller repeatedly proposing RETRIEVE cannot cause unbounded execution: later proposals receive ATTEMPT_LIMIT and the cap is a recorded behavioral FAIL, not a successful model STOP.

In the missing-delivery branch a real lookup happens first; its key/value are checked by the post-execution evaluator. Only then does the transport fixture withhold `evidence`. Actual C153 admission must return MISSING and publish nothing. This is not an absent-corpus test, arbitrary network recovery or proof that the information does not exist. After the next reobservation no payload may leak from the fetched-but-not-admitted response or prior working state.

Successful C153 admission creates an immutable inbox candidate, and the admitted entry is converted to an actual EvidenceRef by C154. Adopt inbox and projected EvidenceState together only after identity/projection checks succeed. Projection failure must not leave a partially adopted inbox. This is sequential in-process publication, **not durable atomicity**; older crash/concurrency claims are not re-tested.

All sources and restored refs remain at their already pinned evidence time/revision 1. Reading/restoring a reference within the same known snapshot does not assert that a new external observation epoch occurred. An actual clock-advancing acquisition from a changing world is outside this experiment.

### Registered size / costs

```text
2 snapshots x 64 keys x 3 frozen routers x 5 scenarios = 1,920 live episodes
384 episodes/scenario; 640 episodes/router
Expected live learned decisions / internal-step debits = 3,456
Expected authorized acquisitions = 768
Expected new in-process reference publications = 384
Expected exact adapter calls = 1,536; vectors scored = 98,304
Terminal ANSWER action = 768; terminal STOP_UNRESOLVED = 1,152
Resolved terminal zero = 324; one = 444
```

Readback costs are counted in addition to acquisition costs: a successful cold recovery reads the actual adapter twice. A metered wrapper counts underlying calls independently of episode status. No silent exact fallback or result cache; exact64 is the declared diagnostic reference path, not efficient production retrieval. Replay decisions/costs and new live-cycle counts are distinguished. Save all episode states, logits/actions, admission/projection outcomes, raw fetched metadata, readback values, budgets, correctness checks and margins as per-router JSONL, with hashes and serialized byte counts. This is diagnostic storage, not a production save/session format.

### PASS / FAIL / INVALID

**PASS:** all 1,920 episodes have registered action sequences and positive finite expected-action margins, correct request/reference identity and source value or None, admission/projection outcomes, bounded authority behavior, unchanged source state/old working objects, fixed evidence clocks and exact internal/acquisition budgets/read costs. Every router and both bit values are required; all aggregate counts above must hold.

**VALID NEGATIVE / FAIL:** valid sources/setup but wrong finite actions, nonpositive margins, missing-delivery acceptance, unpermitted dispatch, stale-value leakage, wrong publication/value/reference/clock/budget/cost, or measured weight/input mutation. Keep traces and use status FAIL with a zero CLI exit code; do not tune, replace checkpoints, or rerun away a learned failure.

**INVALID:** wrong prerequisite/hash/schema/lineage, replay mismatch, incompatible checkpoint, missing snapshot, nonfinite output, unexpected exception or outer guard failure. Preserve invalid output and retry C158 after fixing validity. This does not undo C157 PASS. A replay mismatch before new episodes is a setup failure, distinct from a wrong new episode action.

Gate E stays NOT PASSED. This is no live query selection, generated answer, dynamic-world update, general recovery planner, production deployment, persistence restore or concurrency benchmark. C159 is not registered. PC-ALM/FHLC and Multi-Axis remain independent.

## Reviewer verification

New benchmark, CLI, helper tests, PowerShell runner, this addendum and handoff update. Reviewer **35/35 new CPU helper tests passed**, Python compilation passed. Local state/controller dependency copies matched repository blobs `aa3f4938f6b5d403d8ee05c4220f686695cef3f0` and `e726bdb05cb0b99b409448f8f56832078658dd04` exactly and are not part of the commit.

Helpers use controlled acquisition/admission/readback callbacks and explicit rule-based test routers to isolate orchestration; one test calls the actual production Controller and checkpoint tests reconstruct it. These test doubles are not formal learned results or independent verification of the full C153-C156 integration. No C157 saved model was available to the reviewer. Full **475-test suite = 440 + 35**, actual artifact-chain replay, formal live cycle and PowerShell execution were **not reviewer-executed**. No C158 result claimed.
