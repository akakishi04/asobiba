# C162 verdict -> C163 live evidence-container bridge

Reviewed/preregistered 2026-09-16 JST. V5-E diagnostic integration only.

## C162 — ACCEPTED PASS

Experiment `C162-v5e-evidence-container-differential`.
Stage `V5-E-EVIDENCE-CONTAINER-DIFFERENTIAL`.
Execution branch `feat/sft-target-loss`; commit `32c6ceb4dd3748ea0d89a065f8ecd004cc20f117`.
The preregistration in `experiment-ledger-addendum-c161-c162.md` remains unchanged.

Evidence: uploaded console log `貼り付けられたテキスト（1 点）(20260916-014755).txt`, 136580 bytes.
Reviewer-computed uploaded-log SHA256:
`e055d84e43267a526f3db6de8982b4b4375e69e70b561f4e0d9671630c3a265d`.
Local report: `runs/c162-v5e-evidence-container-a9f04a81882346c99d11c1cafa6f771c/summary.json`.
Runner-printed report SHA256:
`0da31284af3a58ba052ba9629e321520f7f2dbb9352a32c52c3892adff65cdac`.
Container plan SHA256: `3c3c9049dd7ebd24c9c0a101d1dbe395f41721fc6440bac9f8786a6cdbc03f43`.
Guard controls SHA256: `9270ebf5c21d2c9ee2e62d8e6fbaac93fcddf1bafe66a644dbe2d52e25b98373`.

The reviewer parsed the uploaded console JSON and independently checked the registered aggregate gate and postchecks against inspected source. The console omits `records`; it cannot reconstruct or independently verify the complete local report hash. The 48 differential output files and guard artifact were not uploaded/replayed by the reviewer. The log hash is NOT the report hash.

### Execution validity

588/588 regression PASS (14.237 seconds). All 48 source-state files and 48 source traces were consumed. Both accepted C160/C161 report identities match. Native-state reconstruction digest/count matched 82944/82944. Historical core/C158/C159/C160 Git blobs match their preregistered identities. End-of-run source checks and independent PowerShell checks report all 104 consumed inputs preserved, C37/fixture and C160/C161 reports preserved, tracked tree clean, execution HEAD preserved, and `run_execution_valid=True`.

Benchmark training/fresh seeds/model/retrieval/live-cycle execution are zero; emitter execution is true. Production runtime modified and Gate E candidate are false. Regression execution is separate from the benchmark's no-model claim. The C145 tensor-to-scalar warning remains in a passing older regression test.

### Metrics

| Measurement | Registered | Observed |
|---|---:|---:|
| Differential pairs | 82944 | 82944 |
| Pair PASS / FAIL | 82944 / 0 | 82944 / 0 |
| Reconstructed-state matches | 82944 | 82944 |
| Pair emitter calls | 165888 | 165888 |
| Native output reproduced / MALFORMED_EVIDENCE | 82944 each | 82944 each |
| List-form bound / source-payload correct | 82944 each | 82944 each |
| Content unchanged / input preserved / JSON-stable | 82944 each | 82944 each |
| Guard calls / passed / failed | 768 / 768 / 0 | 768 / 768 / 0 |
| Guard snapshot/record bindings | 128 | 128 |
| Router-associated source rows | 27648 each | 27648 each |
| Returned observed zero / one | Both represented | 34992 / 47952 |

False pair checks: none. Per layout, WITHIN_FACTOR list_bound=20736 and semantic_correct=20727; GLOBAL_CONCEPT list_bound=semantic_correct=20736. The nine WITHIN_FACTOR errors per layout remain the same frozen ranker boundary; two layouts repeat those errors, not 18 novel failure types.

### Scientific interpretation

Under source-driven reconstruction of the C160 records, changing only `final_evidence.observations` tuple -> list is sufficient to turn every saved native rejection into a bound observed-bit output through the unchanged C159 emitter. Equal canonical JSON content, exact reconstruction digests, correct selected-record payloads, preserved source identity and all six tested guards support this specific container-representation explanation. No later guard blocked any of the 82944 list-form base outputs.

This is offline causal evidence for this boundary, not a new live query-to-result execution or a production fix. It does not show language generation, relevance recognition, task generalization, efficient retrieval or Gate E completion. Reported 102.7806473 seconds is whole offline diagnostic time, not model latency.

C160 stays **ACCEPTED VALID NEGATIVE**, with its original zero ANSWERED outputs. C161 stays **ACCEPTED PASS**. Nothing is relabeled INVALID or retroactively repaired.

### Confound audit

Changing checkpoints, training, dropping cases, changing thresholds, correcting targets, accepting incidental same-bit wrong-record matches, changing evidence order/content, or weakening the historical emitter cannot explain the measured differential: those are held fixed or explicitly checked. Both payload values, all arms/layouts and all assigned routers are represented. The six registered guard classes remain effective in the tested probes; this is not proof against every possible malformed input or cryptographic authentication.

The remaining limitation is offline reconstruction rather than a fresh native result produced in a live cycle. C163 removes exactly that limitation. Source-level scope: authoritative EvidenceState remains tuple-backed; normalization belongs at a diagnostic output boundary, not in the authoritative state or by silently relaxing C159's historical guard.

## C163 — ACTIVE / NOT YET JUDGED

Experiment `C163-v5e-live-evidence-container-bridge`.
Stage `V5-E-LIVE-EVIDENCE-CONTAINER-BRIDGE`.

### One scientific question

Does an explicit observations-only tuple -> list adapter at the live terminal handoff make the frozen C160 query-originating composition produce bound typed observed-bit results, while the unadapted emitter still reproduces the original rejection on the same freshly produced cycles?

```text
raw query -> frozen C151 selection -> unchanged C158 live recovery
-> fresh native terminal result
   A: native result -> unchanged C159 emitter (diagnostic negative control)
   B: observations-only list copy -> same C159 emitter (candidate output)
-> post-emission cycle/output/semantic assessment
```

Changed variable: representation adaptation at the live terminal handoff ONLY.
Held constant: all 24 C151 rankers, three C157 Controllers, checkpoints, CUDA float32/highest ranker arithmetic, CPU Controller/two threads, query text/manifest/49-feature vocabulary, two original C152 layouts, source-state iteration, selected-reference removal/restoration, permission=true, budget(3 internal,1 acquisition), clocks/revision=1, COLD_RECOVER and expected RETRIEVE -> ANSWER.

No training, fresh seeds, checkpoint selection, new query split, learned answer head or production-runtime edit. The original C158/C159/C160/core and C161/C162 files are unchanged and Git-blob checked. C163 is a separately named diagnostic using existing C160 helper functions and the same run orchestration, NOT an overwrite/retry of C160. New request IDs use the `C163` namespace; this identity renaming is declared and does not encode targets.

### Adapter and controls

The adapter shallow-copies the terminal dictionary and its `final_evidence` dictionary only when observations is exactly tuple, then creates a list retaining all elements and ordering. It does not sort, deduplicate, reconstruct sources, cast payloads, revise clocks, supply missing evidence or use expected labels. Non-tuple/malformed inputs are delegated unchanged to the existing emitter; they are not repaired. Authoritative EvidenceState remains unchanged.

Every new cycle is executed once, and its fresh result is passed to the native control and the adapted candidate. Native control results never replace the candidate output or feed the Controller. Record both outputs and per-pair native type/content/mutation checks. Control overhead is separately counted, not presented as production latency.

Six copied-fault guard probes are executed through the new native-input adapter on the first encountered result for every snapshot/source-record identity (128 identities; independent of correctness/value). Wrong request, wrong provenance, wrong payload, ungrounded ANSWER, wrong clock and duplicate reference must retain the six existing C162 reason contracts and expose no usable payload. If a finite failed live terminal cannot support these probes, save unsuccessful probe records, count actual calls separately and return scientific FAIL; never select a replacement case.

### Prerequisites and provenance

Pin C162 summary hash above and accepted C160 negative hash `1c99ab5395e67c859a7730e1a9111d4595e2668b85cb56d0a31dfff79aea4bbd`. Check C162 full profile, all 48 pair files' hashes/sizes, its control/plan files and all consumed input hashes. This verifies the accepted diagnostic's artifact identity, not a new replay of all C162 emissions. Locate C151 and C159 reports only via pinned C160 ancestor hashes.

Reuse unchanged C160 prerequisite loading: C159's 6528 recorded emissions replayed; accepted source-state maps/catalogs reloaded; all ranker/Controller weights verified; all 41472 C151 rankings plus 288 original12 rankings replayed before the corresponding live per-layout selection. C157's earlier 1990656-row action replay is not repeated. Missing/changed artifacts are never regenerated or rebound.

Save the fixed plan, source identities, checkpoint hashes, router schedule and counts before live measurement. Rehash all consumed inputs and historical source blobs at the end; PowerShell independently repeats these postchecks. No prediction/payload cache substitutes for live selection or either real adapter read.

### Registered measurement

- 24 frozen rankers x 2 layouts x 1728 queries = **82944 NEW LIVE episodes** on the same previously inspected synthetic task.
- **5308416** live ranker candidate scores.
- **165888** Controller decisions; **82944** authorized acquisitions and **82944** reference restorations.
- **165888** exact64 adapter calls; **10616832** vectors scanned, including readback.
- Modulo-three router assignment unchanged: **27648** episodes per Controller, not a three-router Cartesian product.
- **82944** native control emitter calls + **82944** candidate emitter calls + **768** guard calls = **166656** new emitter calls. Old **6528** C159 replay calls remain separate.
- Candidate **82944 ANSWERED** results; observed zero/one **34992/47952** under the frozen selection/source boundary.
- Every arm/layout: **20736** bound outputs; semantic_correct **20727 WITHIN_FACTOR / 20736 GLOBAL_CONCEPT**. Preserve the known nine errors/layout, including wrong-record same-bit cases.

Save all per-query actions/logits, native output, adapted output, type/content/mutation checks, compact cycle state digest/count, original cycle assessment and post-emission output/semantic assessment in 48 new gzip JSONL files. Save all 768 guard cases separately. Do not edit old artifacts.

### PASS / VALID NEGATIVE / INVALID

**PASS:** all original C160 cycle/output/count/semantic gates pass without changing them, all 82944 native controls reject MALFORMED_EVIDENCE, all normalized content/type/preservation checks pass, all 768 guards pass, exact bit/router coverage and source protections pass. Supports the adapted live same-process composition on the fixed controlled task only. Gate E remains NOT PASSED.

**VALID NEGATIVE / FAIL:** valid setup/replays but finite wrong actions, bound output defects, native-control discrepancies, content/model mutation, missing restoration, wrong costs, guard defects or changed terminal semantic counts. Save all outcomes, return CLI zero for scientific FAIL. Do not change models, thresholds or case coverage to obtain PASS.

**INVALID:** wrong/missing source hash/schema/checkpoint, historical code drift, source replay mismatch, nonfinite arithmetic, unexpected execution exception or outer postcheck/HEAD failure. Restore validity and retry C163 with the same scientific conditions. Do not regenerate C160/C162 artifacts or relabel C160.

### Implementation/reviewer scope

Files: `fold_lm/v05_benchmarks/gate_e_c163_live_container_bridge.py`, `tests_lm/test_v05_c163_live_container_bridge.py`, `tools/run_c163.ps1`.
Focused regression **614 expected = 588 previous + 26 new**. Runner uses `.venv-py31315\Scripts\python.exe`, an explicit ExpectedHead and fresh output directory, never overwrites source runs.

Reviewer compiled both new Python files and passed **26/26 helper tests** under Python 3.13.5. Local dependency modules were excerpts reconstructed from the inspected C160/core/C159/C162 definitions, not a full repository checkout; no byte-identical complete dependency import is claimed. Tests include tuple/list and malformed-input boundaries, real-contract-shaped state -> C160 execute-selected callback -> unchanged emitter, six guard classes, strict bit/provenance checks, mutation detection and unreduced gates. The cycle callback in the wiring test is controlled, NOT a real artifact-backed acquisition or trained Controller. No formal 614-test run, real CUDA/CPU 82944-episode run or PowerShell execution was reviewer-executed. Formal C163 has no result yet.

Stop after C163 execution for formal judgment and ledger update. **No C164 registered.** Multi-Axis and PC-ALM/FHLC remain separate research tracks.
