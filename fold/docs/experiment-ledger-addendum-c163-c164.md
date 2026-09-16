# C163 verdict and next-experiment boundary

Reviewed 2026-09-16 JST. V5-E diagnostic integration only.

## C163 — ACCEPTED PASS

Experiment `C163-v5e-live-evidence-container-bridge`.
Stage `V5-E-LIVE-EVIDENCE-CONTAINER-BRIDGE`.
Execution branch `feat/sft-target-loss`; HEAD `d3cecf1c1221d2119a2e6ab172c69770bde46788`.
Preregistration: `experiment-ledger-addendum-c162-c163.md` at that execution commit, unchanged.

Evidence: uploaded console log `貼り付けられたテキスト（1 点）(20260916-033445).txt`, 256561 bytes.
Reviewer-computed uploaded-log SHA256: `7dc7cb7d151fd82f3cbd094ca4e3e4c5eeedade25e2a1b857da78ac8d560c15c`.
Local report: `runs/c163-v5e-live-container-bridge-113788996bc74a1886db817fd95dceae/summary.json`.
Runner-printed report SHA256: `7afc8838d152e791ed33f87e7a9d64d5e4802f9c57ef49b911ca47c4691efd60`.
Plan SHA256: `884e5f63ef4a462bc228fde19a24be5d96e843bcd4ab692ae2cfad693969ffa9`.
Guard artifact SHA256: `d165b06f2ba1bec5205e336c697b2a5bc5dc2d69e1602d786c416dea03ae9e3d`.

The reviewer parsed the uploaded log and compared its reported aggregates, identity and postchecks with the pinned source and preregistration. The console substitutes a string for `records`; the complete report hash cannot be reconstructed from this extract. The reviewer did not independently load the user's full local report, 48 live trace files or checkpoints. The log hash and runner-printed report hash identify different artifacts. Formal acceptance follows the existing console-plus-source protocol, not a claim of independent full replay.

### Execution validity

- Focused regression **614/614 PASS**, 12.902 seconds. The older C145 scalar-conversion warning is in a passing regression; it is not C163 invalidity.
- Exact registered execution HEAD, 24 frozen rankers on CUDA float32/highest, three frozen Controllers on CPU, two threads.
- Training steps and fresh seeds zero. Full C151 replay 41472 plus 288 original12 cases; old C159 emission replay 6528. These are separate from new live measurements.
- Full 48 streams x 1728 queries = 82944 new live cycles completed.
- `diagnostic_execution_valid=true`, `run_execution_valid=True`, `production_runtime_modified=false`, `gate_e_candidate=false`.
- C162/C160/C37/fixture preserved; all **494** consumed input identities preserved at outer postcheck. Historical source blobs, tracked tree and execution HEAD preserved.
- Weight mutations, output mutations and serialization failures all zero.

### Registered metrics / observed result

| Metric | Registered | Observed |
|---|---:|---:|
| Live episodes | 82944 | 82944 |
| Candidate scores | 5308416 | 5308416 |
| Controller decisions | 165888 | 165888 |
| Authorized acquisitions | 82944 | 82944 |
| Published/restored references | 82944 | 82944 |
| Exact64 adapter calls | 165888 | 165888 |
| Vectors scanned, including readback | 10616832 | 10616832 |
| Episodes per assigned Controller | 27648 | 27648 each |
| Candidate ANSWERED / OBSERVED_VALUE | 82944 | 82944 |
| Failed live episodes | 0 | 0 |
| Native emitter controls | 82944 | 82944 MALFORMED_EVIDENCE |
| Adapted emitter calls | 82944 | 82944 |
| Native tuple / adapted list checks | 82944 each | 82944 each |
| Content / input preservation checks | 82944 each | 82944 each |
| Guard calls / passed / failed | 768 / 768 / 0 | 768 / 768 / 0 |
| Guard source-record bindings | 128 | 128 |
| Minimum Controller margin | finite, >0 | 6.142457485198975 |
| Observed zero / one | 34992 / 47952 | 34992 / 47952 |

In each layout, all 20736 outputs per arm are bound to the selected record. Semantic correctness is **WITHIN_FACTOR 20727/20736** and **GLOBAL_CONCEPT 20736/20736**. The known nine control errors repeated in two layouts remain 18 instances, not 18 new failure types. Operational integrity being perfect does not mean all semantic targets are correct.

### Scientific interpretation

The registered same-process path now succeeds in C163:

```text
raw query -> frozen C151 selection -> C157 Controller
-> authorized C153 acquisition/admission -> C154 reference restoration
-> C155/C156 readback/reobservation -> Controller ANSWER
-> observations-only terminal adapter -> unchanged C159 typed observed-bit output
```

Native and adapted emissions use the same freshly produced cycle. All native controls still reject; all adapted outputs are correctly bound. Together with C161 localization and C162 offline differential, this supports the container-representation explanation on this controlled live path, not merely on reconstructed traces.

**C160 remains ACCEPTED VALID NEGATIVE with zero ANSWERED.** C161/C162 remain accepted within their own scopes. A separate C163 PASS does not rewrite the old result. The adapter is diagnostic-only; the historical C160 path itself was not patched.

No learned answer generator, open-ended natural-language understanding, absent-target detector, relevance-based abstention, dynamic evidence epoch, initially empty world, durable publication, production rollout or Gate E completion was tested. There are 1728 reused synthetic queries, not 82944 independent new tasks; each query is assigned one Controller, not all three. The other 63 references remain in each cold fixture.

### Confound audit

No change to training, seeds, checkpoints, query coverage, known semantic errors, source values, provenance, clocks or historical emitter guards is needed to explain the paired result. Native controls rule out merely attributing a between-run change to the adapter. Content/type and mutation checks support an observations-container-only intervention. Six copied-fault classes remain effective in the registered 768 probes; this is not universal adversarial or cryptographic assurance.

The main remaining integration constraint is **successful authorized delivery only**. C163's copied-fault emitter probes are not fresh failed-acquisition cycles. C158 tested unsuccessful outcomes from a preselected record; their presence there does not establish query-originating typed UNRESOLVED on the new adapter path.

Resource fields are diagnostic measurements only: PyTorch peak allocated 11956224 bytes, peak reserved 25165824 bytes, total diagnostic wall-clock 578.8213642000046 seconds. The memory values are allocator peaks over this small-model measurement interval, not complete process/device resident VRAM or target-model footprint. Wall-clock includes source validation, replay, controls, serialization and I/O, not production per-query latency. No speedup claim is made.

## Next-experiment state

C163 is formally judged and this verdict is recorded before any next experiment registration. **C164 is not yet registered in this commit.** Gate E remains NOT PASSED. Multi-Axis and PC-ALM/FHLC remain separate tracks.
