# C160 verdict -> C161 failure-boundary localization

Reviewed/preregistered 2026-09-16 JST. V5-E diagnostic integration only.

## C160 — ACCEPTED VALID NEGATIVE

Experiment: `C160-v5e-live-query-to-terminal-result`.
Stage: `V5-E-LIVE-QUERY-TO-TERMINAL-RESULT`.
Execution commit: `d2c1468a19e9a13a8fa47fafe3aad5fa01597aec`.
Evidence: user's complete console log `貼り付けられたテキスト（1 点）(20260916-004831).txt`.
Reviewer-computed uploaded-log SHA256: `98eafa0e628e1d214ba3f9c63cf1eee22c7bd3708092932be51026f2c1d3fc43`.
Local report: `runs/c160-v5e-live-query-result-80754c5ca25f4970aa1ceeb5d3a8b04b/summary.json`.
Runner-printed report SHA256: `1c99ab5395e67c859a7730e1a9111d4595e2668b85cb56d0a31dfff79aea4bbd`.
Query-cycle plan SHA256: `656b53b55db3ed756a6421f767527857f8d71886c8e976735f3734d7160beb13`.

The uploaded console log is sufficient to establish the registered aggregate result and postchecks. The 48 gzip per-query traces and local summary bytes were not uploaded for independent reviewer replay; C161 is explicitly designed to analyze those preserved local traces without rerunning the live experiment.

### Execution validity

C160 is a valid execution, not an INVALID retry case.

- Branch `feat/sft-target-loss`; execution HEAD exactly `d2c1468a19e9a13a8fa47fafe3aad5fa01597aec`.
- Focused regression **546/546 PASS**.
- C159 summary, C151 summary, C37 result, fixture and the full chained source/checkpoint/catalog/state hashes were accepted by the C160 prerequisite logic.
- C151 replay coverage: **41,472** ranker cases plus **288** original12 replay cases.
- C159 deterministic emission replay: **6,528** calls.
- All **24 rankers** and **3 frozen Controllers** loaded; fresh seeds **0**, training steps **0**.
- Full registered live coverage completed: **82,944** episodes.
- `diagnostic_execution_valid=true`; `run_execution_valid=True`.
- Protected C159/C151/C37/fixture artifacts preserved; tracked tree clean; execution HEAD preserved.
- Production runtime modified: **false**. Gate E candidate: **false**.
- No weight mutation, output mutation or JSON serialization failure was reported.

The C145 tensor-to-scalar warning remains a warning in an older passing regression test and is not a C160 execution invalidity.

### Registered metrics versus observed

| Measurement | Registered | Observed |
|---|---:|---:|
| Focused regression | 546 | 546 PASS |
| Live query episodes | 82,944 | 82,944 |
| Candidate scores | 5,308,416 | 5,308,416 |
| Controller decisions | 165,888 | 165,888 |
| Authorized acquisitions | 82,944 | 82,944 |
| Publications/restorations | 82,944 | 82,944 |
| Adapter calls | 165,888 | 165,888 |
| Vectors scanned | 10,616,832 | 10,616,832 |
| Router episodes / Controller | 27,648 | 27,648 each |
| Typed ANSWERED outputs | 82,944 | **0** |
| Failed episodes | 0 | **82,944** |
| Minimum Controller margin | >0 | **6.142457485198975** |
| Weight mutations | 0 | 0 |
| Output mutations | 0 | 0 |
| Serialization failures | 0 | 0 |

Every arm/layout contained 20,736 cases but reported `binding_correct=0` and `semantic_correct=0`. Therefore the preregistered semantic boundary of 20,727/20,736 WITHIN_FACTOR and 20,736/20,736 GLOBAL_CONCEPT per layout was not reached at the terminal-result level. The known 9 WITHIN_FACTOR ranker errors per layout are not reclassified as 82,944 semantic ranking failures; the universal composition failure masks the intended downstream semantic accounting.

### Scientific interpretation

C160 answers its registered question negatively within the measured scope.

The same-process composition did execute raw-query ranking, Controller decisions, authorized acquisition, publication, exact64 readback accounting and structured terminal emission calls across the complete registered coverage. However, **not one episode produced a bound typed ANSWERED result**. Consequently C158's previously accepted selected-record live recovery and C159's previously accepted recorded-trace emitter contract cannot yet be claimed to compose end-to-end under the C160 query-originating path.

This result does **not** invalidate C151-C159 within their accepted scopes. In particular:

- C151 ranking replay remained accepted before the live measurement.
- C157 Controllers retained positive margins and exact registered episode allocation.
- Acquisition/publication/read costs exactly matched registration.
- C159's old recorded outputs replayed successfully before the new measurement.

The new evidence is specifically an interaction/composition failure exposed when those accepted components are wired together in C160.

No claim is made that the ranker degraded, that the Controller chose the wrong action in every episode, or that the evidence payload became semantically wrong. The console aggregate does not expose the per-row `cycle_assessment` false-check counts or terminal rejection reason, so the exact common rejection boundary is not yet established.

### Confound audit

The following explanations are already strongly disfavored by the registered aggregate evidence:

- **Training/checkpoint selection drift:** no training or fresh seeds; all frozen source checkpoints were pinned/replayed.
- **Coverage shrinkage:** all 82,944 episodes ran.
- **Router imbalance:** exactly 27,648 episodes per frozen Controller.
- **Controller indecision/tie:** minimum registered-action margin remained +6.142457485198975.
- **Missing acquisition dispatch:** 82,944 acquisitions occurred.
- **Missing publication:** 82,944 publications occurred.
- **Hidden retrieval-cost bypass:** 165,888 exact64 calls / 10,616,832 vectors were metered.
- **Weight/output mutation or serialization failure:** all zero.
- **Single ranker/layout/Controller-specific pathology:** progress shows the failed count increasing one-for-one through all heads, arms and both layouts.
- **Protected artifact/HEAD drift:** postchecks passed.

The strongest remaining confound is therefore a **shared composition boundary after or during C158 cycle assessment and before a C159-bound ANSWERED result**. The console alone cannot distinguish whether all `cycle_assessment.passed` values were false, whether they all passed and the C159 guard rejected one shared invariant, or whether multiple guard reasons coexist. The preserved C160 traces contain exactly those fields and are the correct next evidence source.

C160 is therefore retained permanently as **ACCEPTED VALID NEGATIVE**. Do not retrain, change thresholds, choose different checkpoints, drop cases, repair the 18 known semantic controls, or rerun C160 merely to obtain PASS.

Gate E remains **NOT PASSED**.

## C161 — ACTIVE / NOT YET JUDGED

Experiment: `C161-v5e-c160-failure-boundary-localization`.
Stage: `V5-E-C160-FAILURE-BOUNDARY-LOCALIZATION`.

### Scientific question

**Is the universal C160 failure entirely a single post-cycle terminal rejection after an otherwise accepted C158 cycle assessment?**

This removes one major confound only: whether the 82,944 universal failures belong to the live recovery cycle itself or to the terminal-result boundary immediately after that cycle.

```text
C160 preserved row
  -> stored cycle_assessment.passed / checks / margins
  -> stored terminal output.status / output.reason
  -> stored output_assessment.bound / serialization_ok
  -> classify failure boundary

NO model forward
NO retrieval
NO acquisition/publication
NO live-cycle rerun
NO emitter repair
```

### Variables

Scientific question: one common post-cycle terminal rejection versus cycle/multiple-boundary failure.

Changed variable: **none in the measured runtime**. C161 changes only the diagnostic observation: it reads the already frozen C160 traces and aggregates fields that C160 did not expose in its console summary.

Held constant:

- exact accepted C160 summary SHA256 `1c99ab5395e67c859a7730e1a9111d4595e2668b85cb56d0a31dfff79aea4bbd`;
- the 48 trace filenames, hashes and byte sizes registered inside that summary;
- all 82,944 C160 rows;
- all ranker/Controller choices, selected keys, margins, cycle results and terminal outputs exactly as saved;
- no threshold, checkpoint, case, layout, router assignment, source state or semantic label change.

Training split: none.
Evaluation split: preserved C160 rows only.
Fresh seeds: **0**.
Training steps: **0**.
Production code change: **none**; new code is diagnostic-only.
Model execution: **0**.
Retrieval execution: **0**.
Live-cycle execution: **0**.
Gate E candidate: **false**.

### Required coverage and outputs

C161 must hash-check and parse all **48 gzip JSONL traces x 1,728 rows = 82,944 episodes**.

For every row it verifies at least:

- unique case identity within stream;
- registered query-index-modulo-3 Controller schedule;
- Boolean `cycle_assessment.passed`;
- complete Boolean cycle-check map;
- finite stored margins;
- terminal `output.status` and `output.reason`;
- Boolean `output_assessment.bound`, semantic flag and serialization flag;
- the preserved C160 row remains `passed=false`.

It aggregates:

- cycle passed / failed counts;
- every false C158 cycle-check name and count;
- terminal status and reason counts;
- output bound / unbound and serialization counts;
- four boundary classes;
- boundary counts per arm/layout;
- router coverage;
- one compact representative example per boundary/reason class.

No C160 row is modified or rewritten.

### PASS / VALID NEGATIVE / INVALID

**PASS:** all 82,944 preserved rows are valid and **all** satisfy the registered single-boundary hypothesis:

- `cycle_assessment.passed == true` for 82,944/82,944;
- no false cycle checks;
- terminal status is `REJECTED` for 82,944/82,944;
- exactly one terminal `output.reason` exists across all 82,944 rows;
- `output_assessment.bound == false` for all rows;
- output serialization remains valid for all rows;
- every row classifies as `POST_CYCLE_TERMINAL_REJECTION`.

A C161 PASS identifies the common rejection boundary/reason only. It does **not** repair C160 or pass Gate E.

**ACCEPTED VALID NEGATIVE / FAIL:** source traces are valid and complete, but one or more C158 cycle assessments fail, multiple terminal reasons/boundaries exist, or any row falls outside the single post-cycle rejection pattern. Preserve the exact aggregate/result and design the next experiment from that observed branch. Do not alter C160.

**INVALID:** wrong C160 summary hash/profile, missing/changed trace bytes, malformed JSON/schema, incomplete 48x1,728 coverage, router schedule drift, unsafe path or outer execution/postcheck failure. Restore validity and retry C161 under the same number; never regenerate C160 traces to fit the hypothesis.

### Files / execution contract

- `fold_lm/v05_benchmarks/gate_e_c161_failure_localization.py`
- `tests_lm/test_v05_c161_failure_localization.py`
- `tools/run_c161.ps1`

The runner requires the accepted C160 summary path plus an explicit expected branch HEAD. It reruns the prior focused regression plus **12 C161 helper tests**, for **558 expected tests** total, then performs only the preserved-trace diagnostic.

The new helper tests were authored and syntax-checked during registration; the formal 558-test user run and real 48-trace C161 diagnostic have **not yet been executed**. No C161 result is claimed.

## Interpretation boundary after C161

Do not preregister a repair experiment until C161 is judged.

- If C161 PASS localizes one post-cycle reason, the next experiment may isolate that exact invariant with the smallest possible unchanged-artifact reproduction.
- If C161 is a valid negative, the next experiment must follow the measured cycle-check/reason partition rather than assuming a terminal-only defect.
- If C161 is invalid, restore the preserved C160 trace source and retry C161; do not rerun C160.

Gate E remains NOT PASSED. Multi-Axis and PC-ALM/FHLC remain separate research tracks.
