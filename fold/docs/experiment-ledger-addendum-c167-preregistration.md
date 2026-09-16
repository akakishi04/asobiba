# C167 preregistration — Live query warm reference

Registered 2026-09-16 JST after C166 acceptance and authoritative handoff update.
C166 verdict: `experiment-ledger-addendum-c166-c167.md` at `a651c3765618d0c52927e1c7dcdcdc29b96a8b3c`.
Acceptance-only handoff: `da060aa975642a9907891b6d7bfdde61383b868d`.
Historical C160-C166 results, implementations and preregistrations are not revised.

## Formal state / stage

**C167 — ACTIVE / NOT YET JUDGED**.
Experiment `C167-v5e-live-query-warm-reference`.
Stage `V5-E-LIVE-QUERY-WARM-REFERENCE`; branch `feat/sft-target-loss`.
Use the final registration commit containing module/tests/runner/this document/handoff as ExpectedHead.
Diagnostic only; production runtime unchanged; **Gate E NOT PASSED**. No C168 is registered.

## One scientific question

With permission and acquisition budget available, does an initially present, exact provenance-bound reference let the frozen raw-query path answer after one paid dereference and one Controller decision, without redundant acquisition, while the matched cold control retains its accepted recovery behavior?

C163-C166 start their query-originating cycles with the selected reference removed. They test normal recovery and three distinct unavailable-acquisition outcomes, but not the case where recovery is already unnecessary. C158 measured WARM_PRESENT only after record preselection. This experiment connects that condition to live raw-query ranking and typed output.

```text
raw query -> fresh frozen selection (one shared ranking prefix)
    |-- selected reference absent, other63 present
    |     -> reobserve unbound -> RETRIEVE -> fetch/admit/restore
    |     -> paid readback -> ANSWER -> typed observed bit
    `-- selected reference already present, all64 present
          -> paid dereference -> ANSWER -> typed observed bit
          -> no acquisition, no admission/publication, budget retained
```

## Changed / held-constant variables

Changed scientific variable: **initial selected-reference membership in EvidenceState**.

C160's historical helper still constructs its original cold state. A local explicit cycle wrapper verifies that state equals the full source fixture with only the selected reference removed. Cold passes that state unchanged; warm passes a fresh immutable copy of the pinned full fixture. Every other actual C158 cycle argument is forwarded unchanged, including permission, budget, working state, requests, registry, transport and operations. No global monkeypatch or model action override is used.

The warm state is not constructed from the preceding cold branch's final state. Immutable reference tuples may share source objects; no mutable working state/inbox/budget or recovered result is reused. The wrapper records the actual effective initial state's digest, count and selected membership before invoking the cycle. These are trace metadata, not Controller features.

Held constant: all24 C151 rankers (12 seeds20261721..20261732 x two arms), three C157 Controllers20261741..20261743, all checkpoints,1,728 queries,64 descriptors,C151 vocabulary/manifest/splits,two C152 layouts,CUDA float32/highest rankers,CPU Controllers/two threads,query-index-modulo-three router assignment,stale working bit=query_index%2,internal step7,external clocks/revision1,initial BudgetState(3,1),Permission(True),identity delivery,unchanged C158 cycle,C163 observations-only terminal normalization and C159 emitter. The other63 reference identities remain fixed.

Training split: none. Evaluation split: unchanged C151 manifest. Training steps0; fresh seeds0. Source-condition labels occur in request namespace `C167|seed|arm|layout|condition` for disjoint identity only, not learned features. Evaluator targets/expected payloads never enter ranking, Controller, acquisition or emitter.

## Coverage / accounting

**82,944 fresh live ranking prefixes** =24 heads x2 layouts x1,728 queries. Each feeds two fresh independent continuations in fixed order: COLD_RECOVER then WARM_PRESENT. This is165,888 branch episodes, not165,888 independent questions, and not a Cartesian product with all three Controllers.

| Metric | Cold | Warm | Total |
|---|---:|---:|---:|
| Episodes |82944|82944|165888|
| Controller decisions/internal debits |165888|82944|248832|
| Executed acquisitions |82944|0|82944|
| Publications/restorations |82944|0|82944|
| Exact64 adapter reads |165888|82944|248832|
| Vectors scanned |10616832|5308416|15925248|
| Typed ANSWERED |82944|82944|165888|
| Typed UNRESOLVED |0|0|0|
| Episodes per Controller |27648|27648|55296|

Shared candidate scores5,308,416. Prerequisite C151 replay41,472 plus original12 replay288; historical C159 emitter replay6,528, all separate from new measurement. No new large C157 replay or training.

Raw actions: RETRIEVE(2)=82,944; ANSWER(0)=165,888; no STOP. Cold actions[2,0]; warm actions[0]. Cold final budget(1 internal,0 acquisition), internal step9. Warm final budget(2 internal,1 acquisition), internal step8.

**Warm is not free**: it still performs one actual exact64 payload dereference, scans64 vectors and consumes one internal step. It avoids the additional acquisition and recovery round, not all file access or candidate ranking. It is not an answer-cache, warm language-session/prefix-reuse or production-performance experiment.

## Exact behavioral / semantic boundary

Each cold branch must retain the complete unchanged C160 successful-path gate. Both branches must emit the selected record's actual bit with exact request/scope/key/source/time/revision binding and stable serialization. Their observed output fields must match in82,944 pairs, with disjoint request/scope identities.

Every warm episode must have zero acquisition, admission, inbox entry, publication and authority invocation; all step fetched fieldsNone; exactly one ANSWER decision; initial and final evidence identical including tuple order/digest; acquisition allowance1->1; one internal step paid. Initial effective state metadata must agree with the registered full fixture. Initial budgets must remain(3,1) for both.

Both branches separately preserve20,736 bound outputs per arm/layout; WITHIN_FACTOR semantic_correct20,727 and GLOBAL_CONCEPT20,736 per layout. Do not repair the nine known control errors. With two layouts AND two answered conditions there are **36 repeated error instances =9 x2 x2**, not36 independent error types. Each condition retains zero34,992/one47,952; total zero69,984/one95,904. Matching a bit from the wrong record remains a semantic error.

## Emitter controls / protected source

Use unchanged C163 AuditedEmitter:165,888 native tuple controls plus165,888 adapted candidate emissions. Native controls all retain MALFORMED_EVIDENCE. Adapted results all require ANSWERED/OBSERVED_VALUE. First encountered cold source-record identities generate128 x6 copied-fault guards=768; no representative replacement after failure. New emitter calls332,544, separate from old C1596,528.

All historical core/C158-C166 blobs remain fixed, including C166 `8954953256124e90c93945b521dc2f801f425e4b`. EvidenceState remains tuple-backed; no production code, historical evaluator, emitter, Controller, checkpoint, threshold or source artifact is changed.

## Prerequisites / output artifacts

Pin accepted C166 report:
`runs/c166-v5e-live-budget-exhausted-94d4977de28e464aa298c02f1f63bf06/summary.json`.
SHA256 `77596c3765a83ea4ccf68a289059cb26f603b2a4fe28b3392f0fe24cec9861a2`.
Execution identity `dc1f315cac66d1963f8e0d08bb897457affbe94a`.

Validate its full identity/profile,48 trace hashes/sizes/3456-row declarations,plan/controls and all consumed inputs. Follow pinned C165/C164/C163 ancestors through unchanged loaders. Revalidate C151 ranking and C159 recorded emissions as above. Parent traces are hash-checked, not claimed as newly executed. Missing prerequisites are not regenerated.

Write `reference-presence-plan.json` before new measurement. Save48 gzip traces x3456 rows including actual initial state digest/count/membership,initial budget,all model actions/logits,authority/admission/projection/fetched trace,compact final state digest/count,cycle/output/presence assessments,both emitter outcomes and passed bit. Save768 guards separately. Use a fresh UUID directory; never overwrite past results.

Python and PowerShell recheck input/code/tree/HEAD protections. Runner additionally checks declared new trace/plan/control output hashes and sizes after the run. This is file-integrity validation, not independent semantic replay.

## Formal decision rule

**PASS:** complete counts and matched outputs; unchanged cold success gate; every warm episode answers the selected bit with one paid read/one decision and zero redundant acquisition/admission/publication; exact initial/final state and budget audits; positive finite action margins; fixed semantic/error/value boundaries; independent adapter meters; all native controls,768 guards,mutability/serialization and input/output/code/tree/HEAD protections pass.

PASS supports avoiding redundant acquisition on this fixed already-bound-reference task. It does not by itself pass Gate E or establish reduced human questioning on natural-language tasks.

**ACCEPTED VALID NEGATIVE / FAIL:** valid setup but finite wrong action/output, warm redundant acquisition or extra decision, missing paid dereference, wrong budget/state/binding, pair mismatch, cold regression, altered known semantic boundary, guard defects or measured mutation. Save all outcomes; CLI exits0 so the report can be collected. No tuning checkpoints/thresholds/cases for PASS.

**INVALID / RETRY C167:** source/hash/schema/checkpoint/code drift, invalid base input, prerequisite replay failure, nonfinite arithmetic, unexpected exception, incomplete run or outer artifact/tree/HEAD failure. Restore validity and retry the same C unchanged. No automatic C168 execution.

## Reviewer / implementation scope

Files: `fold_lm/v05_benchmarks/gate_e_c167_live_warm_reference.py`, `tests_lm/test_v05_c167_live_warm_reference.py`, `tools/run_c167.ps1`.
Focused regression **725 expected =695 existing +30 new helper tests**.

Reviewer compiled both Python files and passed **22 dependency-light tests** using their AST plus inspected old-gate/output excerpts and dataclass test doubles. Eight actual C158-cycle/C163-emitter integration methods were not executed in that harness. No complete repository import/regression725,real artifact-backed CUDA/CPU run or Windows PowerShell execution is claimed. These checks are not the C167 scientific result. Uploaded code/test/runner Git blobs match the reviewed local bytes.

Runner `.venv-py31315/Scripts/python.exe`; arguments `-C166Summary`, `-ExpectedHead`.
Progress includes `[C167] lineage/replay verified; initial-reference-only plan fixed; training=0`,head/arm/layout/query/episode/failed/remaining fields,`=== C167 RESULT ===`,`=== C167 POSTCHECK ===`,`run_execution_valid=True`.

**Stop for C167 judgment and ledger/handoff update before C168.** C160 remains ACCEPTED VALID NEGATIVE; C166 remains ACCEPTED PASS; Gate E NOT PASSED. Multi-Axis and PC-ALM/FHLC remain independent tracks.
