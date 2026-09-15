# FOLD Experiment Ledger and Handoff

> Current authoritative handoff. Detailed history remains in chained experiment-ledger addenda and Gate decisions.

## Environment / protocol

- Repo `akakishi04/asobiba`; branch `feat/sft-target-loss`; local `M:\asobiba\fold`.
- Python 3.13.15 / PyTorch 2.10.0+cu130 / CUDA 13.0 / RTX 4070 Ti SUPER; user runs `.venv-py31315\Scripts\python.exe`.
- Protected C37 `runs/chatgpt-last-result.json`, SHA256 `FD4A8DA897BDAEA9D103A252E30212C7FF842D23300D7C837333E146DEE51931`.
- Protected fixture `runs/fixtures/v05-c-composition-20260921.pt`, SHA256 `A52F8209703149407580F7E2965B61B78653030EE992AF6D759865736741CA9E`.
- One scientific question per C number. Invalid executions retry same number; accepted negatives remain recorded.
- Read `AGENTS.md`, `docs/experiment-conversation-handoff-protocol.md`, and this handoff; preserve claim/non-claim, guards, progress and log collection.

## Gate status and architecture

Gate A/B PASSED; Gate C/D PASSED within measured scope; **Gate E NOT PASSED**, active.
Priority: operational VRAM headroom, peak/resident VRAM, latency/throughput, artifact size.

```text
learned Control Lane -> authoritative availability/permission
-> learned acquisition request -> real acquisition -> provenance/outcome validation
-> evidence commit -> reobserve -> answer / further acquisition / unresolved
```

Hardening through C132: binding/scope/authority, commit-context, replay suppression, atomic claim, recovery, ownership/fencing. C133-C135: persisted corpus/StructuralIndex. C136: fixed-address query formation. C137: shared content addressing/dynamic candidates.
Production head `fold_lm.v05.retrieval_content.SharedRetrievalContentHead`; adapter `fold_lm.v05.retrieval_adapter.PersistedStructuralRetrievalAdapter`.
`docs/evidence-recovery-mode-v0.1.md` is separate design, not implemented by these ranking diagnostics.

## Accepted chain through C149

- C137 PASS, lexical addressing/corpus growth; C138-C140 VALID NEGATIVE, composition and seed sensitivity. Collision-only causality was not isolated because dimensions, parameter shapes and seeds also differed.
- C141 PASS, oracle color substitution only; C142 PASS, training-only color alignment on original 12-candidate task.
- C143 VALID NEGATIVE, expanded frozen ranking; C144 PASS, descriptive factor-mismatch accounting.
- C145 VALID NEGATIVE, material supervision, errors 1464->346; C146 VALID NEGATIVE, all-factor reference, errors 476->11. Named attribute-loss ladder closed. See `docs/experiment-ledger-addendum-c145-c146.md` and `docs/experiment-ledger-addendum-c146-c147.md`.
- C147 VALID NEGATIVE, frozen composition change, errors 11->4 with 3 new errors; no unique cause from mixing order alone. See `docs/experiment-ledger-addendum-c147-c148.md`.
- C148 VALID NEGATIVE, same composed evaluator but different main training computation; errors 11->12, no rescues, 1 regression. Ten of twelve models perfect in both arms. No demonstrated improvement from train consistency. See `docs/experiment-ledger-addendum-c148-c149.md`.
- **C149 ACCEPTED PASS — numerical accounting only**, user log at `f02b3612183753973c1282924216f9703b49dbbe`. Focused regression 255/255; all 24 heads, 41,472 full and 288 old-12 replays; reconstruction/immutability/hash/HEAD/tree checks passed. No model improvement or runtime path.

```text
C149 error means (same / cross / candidate_norm):
POOLED_TRAIN:   +0.3146923217 / -0.4162158787 / +0.0892313441 (11 errors)
COMPOSED_TRAIN: +0.3190750911 / -0.4284724834 / +0.0878052995 (12 errors)
All 23 errors: same > 0, cross < 0, normalization > 0
Maximum reconstruction error: 2.3360549542e-7 (< 1e-5)
12 distinct failing texts; only seeds 20261683 and 20261692
Confusions: red hexagonal stone -> yellow hexagonal stone;
            blue hexagonal metal -> blue round metal
Source pairing unchanged: 0 rescues, 1 new error, 20724 both correct, 11 both wrong
```

These are convention-dependent arithmetic contributions, not unique training causality. Normalization helps the observed errors; no justification for deleting it. Error-conditioned summaries do not establish the distribution in successful cases. Exact C148 singleton-fit values are not printed in the C149 console; full records retain them. Source errors are unchanged; C148 stays negative.

C149 report: `runs/c149-v5e-margin-accounting-44e251b5b99849c099196b996b617d94/summary.json`, SHA256 **`d2fdfab39fdc09f250ed5c9cdbdae159b148c3d06bd023288961993913a54250`**.
C148 report: `runs/c148-v5e-train-consistent-composition-fe85fcf3544e4965ace63f90cca84223/summary.json`, SHA256 **`4a2b32d45eff90295505440c6258808319f20e2751ba798f7779763c4fe6d30e`**.
Manifest: `5a19de10d8152ac262846682a79a13bb942eeacd7dca979afb09b70170ebdd65`.
Detailed verdict, review and next registration: **`docs/experiment-ledger-addendum-c149-c150.md`**.

## Active experiment — C150

`C150-v5e-global-auxiliary-negatives`, stage `V5-E-GLOBAL-AUXILIARY-NEGATIVES`.
Status **ACTIVE, awaiting user CUDA execution**. No performance result claimed.

Question: is widening auxiliary competing candidates from within-factor four words to all twelve existing canonical concepts sufficient for exhaustive positive-margin ranking, with main training and inference fixed?

```text
12 fresh paired seeds 20261701..20261712; 24 new heads; no checkpoint continuation
WITHIN_FACTOR:   36 existing positive aliases; each chooses among own factor's 4 words
GLOBAL_CONCEPT:  SAME positives; each chooses among all 12 existing canonical words
Both: pooled main training, encode-then-pool evaluation
main CE + color CE + material CE + shape CE; each coefficient 1.0
Sum of three per-factor means (not a single mean dividing auxiliary weight by 3)
Same feature49/hidden64/residual1, AdamW .002, weight_decay0, 600 updates, scale12
Same main24 queries/8 candidates; full64 candidates/1728 queries
20736 full + 144 original12 rankings per arm (41760 total decisions)
```

The new variable is auxiliary negative-candidate construction, not a new attribute loss or inference scorer. Positive labels are unchanged, but each alias receives eight extra exclusion comparisons; supervision/compute are not unchanged. Candidate words and mappings come only from existing TRAIN extraction. No held-out fields, extra combination examples, factor-aware inference masks, dictionary replacement or removed cross terms.

The control retains C148's POOLED_TRAIN reference; COMPOSED_TRAIN was not proven superior. Both arms evaluate the exact existing composed scorer and validate reference agreement. Same initial weights and independent optimizers; no selection/tuning by validation. Store both local-four and global-twelve training-fit diagnostics and per-arm costs (not unbiased production performance).

- PASS: GLOBAL_CONCEPT is exhaustive-correct with strictly positive finite margins on all 12 models, including original12 controls; all guards valid. Report paired rescues/new errors. A perfect control means no demonstrated superiority.
- FAIL: valid execution with any treatment residual/nonpositive margin/old12 failure; record partial gains without moving the gate.
- INVALID: prerequisite/hash/reaggregation/manifest/config/OOV/init/numeric/reference/immutability/execution problem; repair and rerun C150.

Both full C149/C148 reports are required with exact hashes. Revalidate source rankings and audit accounting. No old checkpoint is loaded; source files remain unchanged. Save both arms' checkpoints, original/full rankings, margins, fits, alignment specs, hashes, environment and cost accounting.

All evaluations are ranking-only. No retrieval/provenance/commit/ANSWER or Gate E promotion. Named-attribute additions and train-composition sweeps stay closed. This one scoped negative-pool experiment is not authorization for further coefficient/width/steps sweeps. After judgment, review independent-task evaluation or acquisition/runtime boundaries rather than automatically optimizing this same fixture further. No C151 registered.

Implementation: `gate_e_c150_global_negatives.py`, `gate_e_c150_cli.py`, `tests_lm/test_v05_c150_global_negatives.py`, `tools/run_c150.ps1`.
Reviewer: **20/20 CPU helper tests**, toy inputs/synthetic full-size audit; control arithmetic and positive/candidate identity, loss weighting, checkpoint metadata checked. Production-head bytes matched Git blob `afcf55267cd1fa6341b1fa058a0da4fb439f7ad6`; Python compilation passed. Full **275-test** suite, actual C149/C148 integration, CUDA and PowerShell not reviewer-executed. No registered fresh-seed performance inspected.

## Non-claims

Shared-Basis partition and KV/context-memory work remain separate. `fold/fold_memory.py` is a QuadraticMemory reference, not the V5-E persistent store. Repeatedly inspected synthetic tasks are not independent open-domain benchmarks. Oracle replacement, supervised alignment, manual composition and discovered factors differ. Ranking-only success cannot establish full runtime or general FOLD intelligence.
