# C154 verdict and PC-ALM hypothesis review

Reviewed: 2026-09-16 JST.
Status: documentation-only review. No C155 or PA experiment is preregistered or implemented by this document.

## 1. Review sources and authority

C154 execution source: the user's complete terminal log `貼り付けられたテキスト（1 点）(20260915-210554).txt`.
Uploaded log SHA256, independently computed by reviewer: `541b2bd4e2fffed2aea5860992a77e838e45a1fe9bb05f222024e69e91697e32`.
Execution commit: `8768303869d6ee24d72cc98a9690219a4205a495`, branch `feat/sft-target-loss`.
Implementation and preregistration: `gate_e_c154_evidence_state_projection.py`, `docs/experiment-ledger-addendum-c153-c154.md`, existing `fold_lm/v05/state.py` and handoff at that commit.

C154 full local report: `runs/c154-v5e-evidence-state-projection-ddacda18a60e4b7b91c370155ae5551c/summary.json`.
Report SHA256 printed by the user's runner: `4814c9489b76bfb124e7134336611a3f513eb922083b0eca251be533820c4284`.
Consumed C153 SHA256: `cddf360fc2211302d1dab0abd8d96038bb3d39ab273f9dea336da348d70d3a78`.
The reviewer parsed the uploaded result and checked aggregate arithmetic, but did not receive the full local report/state files and did not independently rerun the integration or 363-test suite. Do not describe the emitted report SHA as independently recomputed from full report bytes.

New research source, read in full: `fold/docs/pcalm-layer-local-credit-hypothesis-report.md` on `main`, commit `903e31f1e509c92877206741672918e7bacc701b`, blob `62f61588de77d9c277f4dcac2170ba29db0a1a03`. Title: **PC-ALM x FOLD — Layer-Local Credit Assignment Integration Hypothesis Report**; source document date 2026-09-16. This is distinct from the previously reviewed Multi-Axis report at `53bca2b32c299836dae2ec9a8ae937439edbd3c0`.

External primary-source checks, read 2026-09-16:

- Seely and Gould, *Augmented Lagrangian Predictive Coding*, arXiv `2605.31022v1`, HTML text, especially Algorithm 1 and Sections 3–4: `https://arxiv.org/html/2605.31022v1`.
- Sakana AI research article: `https://pub.sakana.ai/pc-alm/`.
- Official reference README: `https://github.com/SakanaAI/pc-alm`.
- Official `pcalm/inference.py`, inspected blob `cdc32302a2404a02099ae2eb13413c48db113788`: `https://github.com/SakanaAI/pc-alm/blob/main/pcalm/inference.py`.

The following explicitly separates reported results, source-proposed hypotheses, and reviewer deductions/recommendations.

## 2. C154 — ACCEPTED PASS, representation-boundary scope

The supplied log meets the registered success conditions:

| Item | Observed result |
|---|---:|
| Focused regression | 363/363 |
| Source streams | 48 |
| Accepted request entries consumed | 82,944 |
| ADDED references | 3,072 |
| ALREADY_PRESENT transitions | 79,872 |
| PROVENANCE_CONFLICT rejections | 3,072 |
| Final observations, summed over states | 3,072 |
| Final observations per state | 64 |

Arithmetic: `48 * 1728 = 82944`, `48 * 64 = 3072`, `82944 - 3072 = 79872`. Every reported stream has 64 added references, 1,664 idempotent repeats and 64 conflicting-provenance controls. Duplicate/conflict paths preserve the state object under the registered implementation checks.

Input/C153 state-file hashes are included in the report; the implementation verifies them before use and again at completion. C37, fixture, C153 summary, tracked tree and execution HEAD postchecks pass; `run_execution_valid=True`. No new model load, training, scoring, retrieval or production code mutation.

**Supported claim:** C153 request-level accepted entries can be mapped into instances of the existing V5 `EvidenceState`/`EvidenceRef` contract, collapsing repeated record identities within each separate stream and rejecting same-ID conflicting provenance without state replacement.

**Non-claims:** 3,072 is the sum of 64 references across 48 separate states, not 3,072 distinct corpus records. The cardinality reduction is not a measured storage/VRAM compression ratio. Payload values are not stored in these EvidenceStates. No new semantic retrieval evaluation, payload dereference, re-observation, Controller, ANSWER, durable commit, concurrent publication, restore or crash recovery was tested. Gate E remains NOT PASSED.

The source semantic counts remain WITHIN_FACTOR 20,727/20,736 and GLOBAL_CONCEPT 20,736/20,736 in each layout. These are reaggregated source outcomes, not new post-projection answer accuracy. Projection must not erase the original request trace or infer that a state containing all 64 records corrected the earlier nine wrong selections.

### C154 reuse cautions (reviewer observations)

- The source_id is a digest of source path, source SHA and index fingerprint. It binds an identity but is not itself a reverse lookup table or cryptographic proof that arbitrary payloads are true. A resolver still needs trusted snapshot metadata.
- Mapping request epoch 1 to evidence time 1, and provider generation 1 to revision 1, is explicitly experiment-local. Multiple sources, changing snapshots and session time require a separate clock/identity contract; do not generalize this mapping silently.
- Record keys are deduplicated inside isolated stream states. Multi-source namespaces and replacements/retractions are not validated here.
- **Verdict plumbing limitation:** `_stream_projection` raises `ValueError` for several behavioral failures that the preregistration calls valid negatives; `run` catches all exceptions as INVALID. The successful run still meets PASS, so this does not change its verdict. Before reusing the runner as a fault/negative experiment template, separate source/execution invalidity from measured projection failures. Do not relabel a valid bad behavioral result as an invalid run to retry away.

Candidate next boundary, not preregistered: reference plus trusted snapshot registry -> exact payload dereference -> preserved source binding, including missing binding/wrong snapshot/value-zero controls. Do not add learned routing, new training and durable commit at the same time merely because C154 passed.

## 3. New report: what it proposes

The source names **FOLD Hybrid Local Credit (FHLC)**. It proposes keeping ordinary autograd inside differentiable modules while replacing long depth-spanning credit propagation with lifted boundary activations and local primal-dual dynamics. Shared parameters still require group reduction. This is not a gradient-free method and not a proposal to turn inference-time evidence into trainable beliefs.

The source's independent proposed sequence is:

`PA-0 reference reproduction -> PA-1 FOLD-shaped depth credit -> PA-2 next-token CE -> PA-3 Shared Basis credit reconstruction -> PA-4 Auto-Partition shadow decisions -> PA-5 FOLD-R hybrid -> PA-6 temporal research`.

The report does not authorize immediate replacement of FOLD BP, a 1000-layer FOLD, temporal credit replacement, automatic splits from dual norms, or simultaneous Multi-Axis integration. These boundaries are appropriate and should be retained.

Three research questions remain different:

| Track | Question |
|---|---|
| C152–C154 | Does selected/validated evidence cross the runtime/state boundary correctly? |
| Multi-Axis / proposed MA track | Can condition-specific weight updates be factorized/composed economically? |
| PC-ALM / proposed PA track | Can module-local dynamics produce useful learning gradients? |

C154 is not experimental evidence for either architecture hypothesis. The repeated constraint-checking in C154 is not PC-ALM training.

## 4. External claims checked separately

The primary materials support the report's conservative distinction between linear-network equilibrium results and finite-budget nonlinear experiments. The 1000-layer result is presented by the official September article as MNIST residual-MLP training, not an LLM/FOLD-R result. The arXiv v1 abstract describes nonlinear experiments through depth 128; do not assign every later article result to that version without a specific reference.

The official JAX reference's `supervised_loss` and `bp_loss` are squared-error objectives. Its README provides the cited Fashion-MNIST width-32/depth-32 seed-0 values: BP 78.66%, PC 68.13%, PC-ALM 77.75%; cosine 1.000/0.604/0.909, with a `2L` budget. These are external reference values, not FOLD results or independently reproduced reviewer results.

Official discussion identifies temporal tasks and self-supervised losses as future directions. This supports requiring a separate CE/temporal validation rather than assuming applicability to language-model training. Neither primary-source inspection nor this review demonstrates a speed or memory improvement on the user's hardware.

## 5. Implementation blockers / reviewer recommendations

### R1. Fix the finite-iteration algorithm, not only the energy formula

The report's equations are useful at hypothesis level but not yet a reproducible training specification. Pin rho, alpha, eta_h, T, inner_steps, activity update ordering, loss reduction, precision, initialization, and output boundary semantics before PA-0. Pin the official source version.

Official Algorithm 1 performs T-1 primal/dual pairs followed by a final primal step. The reference supports `pre_dual_energy` and `post_dual_energy`; default scheduling uses pre-dual energy. A naive T repetitions of both updates can select a different final credit. The reference places constraints on hidden edges, not a hard constraint forcing the label residual to zero.

With the report convention `r_m = h_m - f_m`, holding lifted h and lambda fixed, a hidden module's parameter derivative contains

`-(d f_m / d theta_m)^T (lambda_m + rho r_m)`.

This is a reviewer derivation from the report's energy, not a new experimental finding. Output-head direct-loss terms must be specified separately. Do not use lambda alone at finite residual, or silently reverse the residual sign.

The official inner solver multiplies eta_h by batch size when differentiating a batch-mean energy to recover the per-example activity step. For language CE, batch/token/padding reductions need an explicit comparable scaling contract. A transplanted numerical step size alone is not sufficient.

### R2. Separate exact chain-rule algebra from approximate BP credit

For `DeltaW_m = A_m B_g`, the identities `dL_local/dA_m = G_m B_g^T` and `dL_local/dB_g = A_m^T G_m` are chain-rule identities for the supplied effective derivative G_m. They do not prove G_m equals the global BP derivative. Finite-T local gradients should be named as such rather than represented as exact BP gradients.

Compare local and BP gradients at the **same weights, batch and state**, before comparing separate training trajectories. Group reduction should occur after all occurrence contributions for that update are formed using the same B_g, not after sequential in-place optimizer updates to shared B_g. Module contributions mean contributions of each use of a shared parameter to a common objective, not automatically independent task losses.

Check individual and reduced gradient norm error as well as cosine. Near-canceling module contributions can make a small absolute local error large relative to the group gradient. Near-zero gradients need a declared cosine/sign policy. A reduction equality test and a local-versus-BP fidelity test are separate tests.

Dense G_m is convenient notation; materializing a full d_out-by-d_in gradient merely to construct a low-rank contribution could erase memory advantages. A module-local vector-Jacobian product can compute factor contributions without requiring that dense representation; measure actual allocations.

### R3. Explicitly constrain training-state mutation

The source appropriately keeps FOLD-R semantics and temporal credit separate. Add an operational rule: within the T-step solver, the weight snapshot and external authoritative EvidenceState/snapshot stay fixed. Any differentiable memory/Writer transition is functional on a training-local copy, not a repeated production write. Local h/r/lambda are numerical training states, not newly observed facts.

Define whether module-internal temporal recurrence is differentiated across the whole training block, a fixed window, or a detached state. Do not change that policy at the same time as depth-local credit. Treat hard retrieval, discrete routing, permissions and capability status branches as explicit boundaries, not silently differentiable operators.

The original report references v0.3/research-plan/local-training. An executable FOLD plan also needs the current v0.5 architecture/theory/roadmap, `state.py`, AGENTS boundaries and accepted runtime contracts. The older references are context, not authority to overwrite those boundaries.

### R4. Count local iterations and state, not just removed backward edges

The report already warns about cost; turn that warning into a preregistered accounting model. If every iteration touches L similarly sized modules, work is proportional to L*T module work. With T=2L this is quadratic in depth under that simplified fixed-width accounting, even when layers can run in parallel. This is a reviewer operation-count deduction, not a GPU wall-clock prediction.

Lifted activations, equally shaped duals, local residuals, buffers, module-autograd workspaces, group reductions and optimizer state remain memory costs. Do not build a differentiated graph through all T solver iterations when claiming local gradient generation; local derivative calculation and differentiation through the solver history are different algorithms/costs.

Report fixed-update, fixed-training-data and fixed-wall-clock comparisons separately. Compare against a credible BP implementation and separate compile/warm-up from steady execution. Locality alone is not a demonstrated benefit on a single RTX 4070 Ti SUPER.

### R5. Make proposed PA gates decidable before running them

PA-0's phrases 'clearly closer to BP', PA-1's 'low alignment', and PA-2's 'continuously breaks down' are not numerical acceptance criteria. Preserve them as proposal-level intentions, then preregister exact seed sets, configurations, stopping budgets, quality margins, norm/cosine policies, divergence handling and allowed tuning budgets before running a formal PA experiment.

First verify algebra/signs on a tiny fixed linear example, then the official residual-MLP reproduction, then FOLD-shaped modules. Do not jump straight into a broad grid or import a new JAX environment into the protected FOLD Python environment as a side effect of this review. PA-2 CE remains a dependency before PA-3 despite the report ranking PA-3 as higher research interest.

For Auto-Partition, preserve shadow-only authority and validate functional split outcomes, not just correlation with a gradient matrix. A large dual norm does not identify a capacity shortage or authorize a split.

## 6. Review decision and next authority

**Retain PC-ALM/FHLC as an independent research candidate, with implementation-specification supplements required. Do not adopt it as standard FOLD training or claim it improves current model intelligence, training speed, memory or V5-E completion.**

The most direct FOLD-specific hypothesis is preservation of per-module Shared Basis credit/conflict structure, not the generic chain-rule formula itself. Whether this offers a benefit over BP is unmeasured.

This review records C154 as ACCEPTED PASS, keeps Gate E NOT PASSED and leaves C155 and PA-0 unregistered/unimplemented. It does not merge main, modify the original hypothesis, alter production state code, fix prior benchmark code or issue a new execution command. Full reproduction of the external reference and new FOLD benchmarks were not performed.
