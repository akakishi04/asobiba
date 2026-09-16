# C164 verdict / C165 handoff

Recorded 2026-09-16 JST after formal review of the complete C164 user execution log.

## C164 — ACCEPTED PASS

Experiment `C164-v5e-live-query-missing-delivery`.
Stage `V5-E-LIVE-QUERY-MISSING-DELIVERY`.
Execution branch `feat/sft-target-loss` at commit `c3ee72d7ad7b7112fb45c6601899b69a96cf4969`.

Uploaded execution-log SHA256: `8b1a735e212cb10f2c72bcc3e58a69045f0cdba6a3c1badccc7730aca536b54c`.
Accepted summary: `runs/c164-v5e-live-missing-delivery-47e1d170b3114b8d94e6c1d221ebf464/summary.json`.
Summary SHA256: `42df47fe4c03d24df064ff47eecf5b3c84b8df2f36d6a47b7f861ac14778fed2`.
Plan SHA256: `09c1cedcf371e320cae3cb1451319ff837a9abe33d1fb78ee7b3acaa74a8f04e`.
Controls SHA256: `800c27c47f2fad4db97188a96e95f894de22f0e7dcc9de40650fe88841c66bb9`.

### Execution validity

- focused regression **638/638 PASS**;
- parent C163 summary hash matches the preregistered `7afc8838d152e791ed33f87e7a9d64d5e4802f9c57ef49b911ca47c4691efd60`;
- 24 frozen C151 rankers and three frozen C157 Controllers used; training steps 0, fresh seeds 0;
- 41,472 C151 ranking replays plus 288 original12 replays and 6,528 old C159 emissions reproduced as registered prerequisites;
- all 545 consumed inputs preserved; historical source Git blobs preserved; tracked tree clean; execution HEAD preserved;
- weight mutations, output mutations and serialization failures are all zero;
- `diagnostic_execution_valid=true`, `production_runtime_modified=false`, `gate_e_candidate=false`, outer `run_execution_valid=True`.

The existing C145 tensor-to-scalar warning occurs inside a passing regression test and is not C164 invalidity.

### Registered measurement reproduced

One fresh live ranking prefix is shared only between two fresh independent cold continuations. The result therefore represents **82,944 fresh ranking prefixes / 165,888 branch episodes**, not 165,888 independent queries.

| Metric | Observed |
|---|---:|
| live ranking prefixes | 82,944 |
| candidate scores | 5,308,416 |
| branch episodes | 165,888 |
| failed episodes | 0 |
| Controller decisions | 331,776 |
| acquisitions | 165,888 |
| publications/restorations | 82,944 |
| exact64 adapter calls | 248,832 |
| vectors scanned | 15,925,248 |
| typed ANSWERED | 82,944 |
| typed UNRESOLVED | 82,944 |
| emitter native controls | 165,888 |
| emitter adapted outputs | 165,888 |
| guard calls | 768 |

Router coverage is exactly 55,296 branch episodes per Controller, 27,648 per Controller per condition. Raw learned actions are RETRIEVE=165,888, ANSWER=82,944, STOP=82,944. No action was replaced by evaluator truth.

#### Normal-delivery branch

All 82,944 episodes pass the existing successful live-cycle/output contract: 165,888 Controller decisions, 82,944 acquisitions, 82,944 publications, 165,888 reads / 10,616,832 vectors, 82,944 ANSWERED and zero UNRESOLVED. Minimum expected-action margin is `6.142457485198975`. Observed values remain zero/one = 34,992/47,952.

Every arm/layout has 20,736 bound outputs. Semantic correctness remains exactly the frozen boundary: WITHIN_FACTOR 20,727/20,736 per layout and GLOBAL_CONCEPT 20,736/20,736 per layout. The same known nine WITHIN_FACTOR errors repeated over two layouts remain 18 measured occurrences and are not repaired.

#### Missing-delivery branch

All 82,944 episodes pass the existing C158 missing-delivery cycle contract and typed-output contract: 165,888 Controller decisions, 82,944 real acquisitions, **zero publications**, only 82,944 reads / 5,308,416 vectors, zero ANSWERED and 82,944 `UNRESOLVED / MISSING_DELIVERY`. Minimum expected-action margin is `5.3444743156433105`.

Each missing-delivery output retains request/scope identity but has `value`, `record_key`, `source_id`, `evidence_time` and `revision` unset. All 82,944 are counted `unresolved_without_payload`. Semantic correctness is intentionally null/not-applicable, not zero accuracy or a new semantic success. The pre-delivery debug trace contains the actual fetched bit but that bit never becomes an authorized returned answer.

#### Emitter controls

All 165,888 unadapted tuple-backed controls still reject `MALFORMED_EVIDENCE`. The adapted outputs split exactly into 82,944 `ANSWERED / OBSERVED_VALUE` and 82,944 `UNRESOLVED / MISSING_DELIVERY`. All 768 copied-fault guards pass over 128 source/record identities. Content/input preservation checks all pass.

### Scientific interpretation

C164 supports the following narrow claim on the fixed synthetic task:

```text
raw query -> fresh frozen selection -> learned RETRIEVE proposal
-> real exact acquisition
   normal delivery -> admission/projection/readback -> ANSWERED observed bit
   evidence removed after fetch -> no admission/publication/readback -> learned STOP -> payload-free UNRESOLVED
```

Thus the query-originating composition does not reuse the stale working bit or the debug-visible fetched payload when evidence is lost after the actual fetch. It distinguishes a real zero-valued observation from no delivered evidence, and the Controller's second decision changes from ANSWER to STOP after reobservation without a restored reference.

This does **not** establish absent-target detection, exact-search miss handling at query level, semantic relevance abstention, permission denial, budget exhaustion, changing evidence epochs, initially empty worlds, durable publication, learned/generated language answers, task/language generalization, or production rollout/performance. C164 intentionally preserves the 63 other references in the source state and uses the same synthetic closed-set manifest.

C160 remains **ACCEPTED VALID NEGATIVE** and is never retroactively rewritten. C163 remains **ACCEPTED PASS**. C164 is a new accepted integration result, not a retry of either experiment.

### Confound audit

The measured contrast changes only delivery of the fetched evidence object after a real fetch. Permission and acquisition budget stay authorized, ranker predictions/checkpoints are fixed, both continuations receive fresh independent cold state/working/budget, the normal branch cannot seed the missing branch, and the condition label is evaluator/request identity only rather than a Controller input. The missing branch still pays the real acquisition search cost but performs no payload readback. Source/code/input protections and independent adapter meters agree with the registered accounting.

The result therefore should not be interpreted as proof that the model knows the target is absent or irrelevant; it demonstrates correct bounded behavior under a specific post-fetch transport failure.

## Gate state after C164

Gate A/B PASSED. Gate C/D PASSED within measured scope. **Gate E remains NOT PASSED** because the broader V5-E gate also requires controlled behavior for runtime authority/budget boundaries, unnecessary acquisition/question controls, coverage-vs-unresolved collapse, and quality improvement/generalization claims beyond this fixed observed-bit diagnostic.

## Next experiment state

C164 is judged and recorded. **No C165 is registered by this verdict document.** The next experiment must remove one remaining integration constraint without changing the accepted C160-C164 historical results or merging the independent Multi-Axis / PC-ALM(FHLC) research tracks.
