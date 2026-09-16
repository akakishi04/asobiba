# C171 preregistration — Bounded derived-result contract

Registered 2026-09-17 JST after C170 acceptance/handoff commit
`77bebd715ae18215546c7d4e1cf5414d04f663a6`.
Read `structured-derived-result-v0.1.md`,`structured-task-interface-v0.1.md`,and
`gate-e-evaluation-contract-v0.1.md`. Past conditions and verdicts remain unchanged.

## Formal state / one question

**C171 ACTIVE / NOT YET JUDGED.**
Experiment `C171-v5e-bounded-derived-result-contract`.
Stage `V5-E-BOUNDED-DERIVED-RESULT-CONTRACT`;branch `feat/sft-target-loss`.
Use the final registration commit as ExpectedHead. C172 is not registered.
C170 remains ACCEPTED PASS;C160/C168/C169 remain ACCEPTED VALID NEGATIVE.
**Gate E NOT PASSED.** Production runtime is not wired to the new module.

Question: can a separate bounded proof/result boundary validate proposed Boolean
conclusions against current usable support without promoting an unobserved fact to
an observation,repairing a bad candidate,or weakening the C159 observed-value guard?
This is implementation/reference validation,not an unseen learned-model experiment.

Changed variable: add opt-in `fold_lm.v05.structured_derived_result` and its new proof/result
schema. Hold C170 input,all historical core/Controller/retrieval/emitter code,weights,
previous experiments and Gate E evaluation scope fixed. No old-index action remapping,
learner,training,new seed,new checkpoint,acquisition,full live cycle,evidence write,
source authentication or production rollout. Scripted proof fixtures are explicitly
hand-written test producers,not trained reasoning or a solver supplied to a model.

## Exact finite batch:600 verifier calls

| Group | Calls | Registered check |
|---|---:|---|
| reference |504|C170's10 development structures x their252 UNOBSERVED/0/1 assignments x two proposed conclusions. Check accept/reject against independent exhaustive completion truth.|
| malformed |48|24 fixed corruptions x observed controlling bit0/1. Every candidate must be rejected without value/support/proof leakage.|
| unusable |14|7 non-OBSERVED statuses x two proposed bits;fake observed-leaf support must be rejected.|
| rebound |16|8 changes to actual current task/evidence x bit0/1;old candidate must reject.|
| resources |8|4 runtime-resource snapshots x bit0/1;same static proof remains valid without granting acquisition permission.|
| capacity |8|max_steps0/1/2/7 x two two-step proofs;only2/7 accept;0/1 reject before rule evaluation.|
| rule_scope |2|A OR NOT A and A AND NOT A with A unknown;local proof set lacks case split,so empty proof is rejected despite a logically determined result.|

All groups run as one batch after one focused regression. Capture full current views,
original candidates,results,expected outcomes,completion sets and per-case checks.
600 is total verifier calls,not600 independent questions or model decisions.
The252 reference views are reused development structures,not a new heldout split.

The benchmark's proof builder uses only visible TaskView facts and local rules. The
checker does not import it. For the reference group,claim0 and claim1 are both proposed;
evaluator enumerates all assignments of unknown variables after candidate construction.
No actual hidden world value is supplied. Expected labels are scoring-only.

Corruptions fixed before execution:schema,request,scope,expression/evidence digests,
time/revision,flipped/Boolean/float conclusion,empty/list/oversize/reversed proof,
invalid node,Boolean step value,unknown rule,self premise,other child,changed leaf value,
missing/wrong/duplicate/list support. No representative replacement after failure.
Rebound views change request,scope,time,revision,operator,fact ID,support ID,or observed value.
Unusable statuses remain UNOBSERVED,STALE,CONFLICT,INVALID,SOURCE_UNBOUND,
SNAPSHOT_MISMATCH,REFERENCE_MISMATCH;all valuesNone.

Maximum proof7 AST-bound steps. Only declared local AND/OR/observed-leaf rules are used.
Scope controls explicitly exclude a complete Boolean-solver claim;their rejection is not
counted as a claim that the task is unanswerable. Genuine reference false rejection or
acceptance is a failure. The limited verifier is not final Gate E completeness.

Label-free manifest SHA256:
`af6df4dff24b42b95bfb081485127604a5ce8c6c15753522838fe3abe6799285`.
The manifest fixes rules,templates,control names and all counts;source pins are added to
the saved plan. No deciding run or post-result fixture tuning before this registration.

## Formal decision rules

**PASS:** exactly the declared600 checks in all7 groups,zero failed checks,zero false
accepts/rejects in the declared reference family;all result bindings/statuses/typed values/
serialization intact;verified proofs/supports copied without alteration;rejected output
valueNone/supports/proof empty;view and candidate unchanged;checked_steps within capacity;
all source/input/output/tree/HEAD protections pass. This is a scoped proof-interface PASS.
It does not close action-dispatch or learned-necessity gaps or pass Gate E.

**ACCEPTED VALID NEGATIVE / FAIL:** finite guard,derivation,binding,cost-accounting,
mutation or expected-outcome error under valid setup. Save all remaining independent
cases. No case removal,proof repair,rule addition,checkpoint selection or threshold change
inside C171. A complete finite negative exits0 for result collection.

**INVALID / RETRY C171:** source/parent/hash/manifest drift,malformed fixture construction,
unexpected exception,incomplete coverage or outer artifact/tree/HEAD failure. Preserve
invalid report when output directory exists;restore validity and retry identical C171.
Wrong candidate types/values listed as adversarial inputs are finite rejection tests,
not global invalidity. Wrong trusted configuration is invalid setup.

## Parent / source / output identity

C170 `runs/c170-v5e-structured-task-input-e999793ff0314b959994ea3ed308aa5e/summary.json`.
SHA256 `a1858cd65a56b5cad09b1e339500f7f8a9011c4f1de721300c3a77ee11f1183e`.
Execution `da09a86e25f12927a9206217b7933609c2fe1b8c`.
Use this full hash-pinned parent for lineage;C171 does not consume its separate532-packet
artifact or earlier48 traces. Preserve all of them;do not claim recursive replay.
Pin parent's18 historical source entries plus C170's6 own source/doc files to its
execution HEAD. New module/benchmark/test/runner/design/preregistration bytes are checked
against current registration HEAD;LF/CRLF-equivalent checkouts are accepted.
C37 and composition fixture remain outer protected files,not model inputs.

Fresh UUID directory:derived-result-plan.json before measurement,proof-results.json with
all600 rows,and full summary.json. Record hashes,sizes,counts,source/commit,timing and
limitations. Python and PowerShell check inputs/code/tree/HEAD;runner verifies new output
hashes and sizes. File-integrity checks are not independent semantic replay.

## Reviewer verification / command / stop

New module,benchmark and test Python files compiled. **36/36 new tests passed** using
actual new modules and an exact byte-for-byte copy of C170 structured_task_input whose
Git blob matches `b874b6abf17fb938a5cc873ff2090c6493f00010`. No dependency substitutes.
Development unit fixtures test rules,malformed proposals,binding changes,immutability,
capacity and known local-rule incompleteness;they are not the deciding C171 artifact run.
Full repository **845 tests=809+36**,Windows PowerShell and the artifact-backed600-case
CLI/source-guard execution have not been run by the reviewer. No learned/GPU run is needed.

Runner `.venv-py31315/Scripts/python.exe`;`tools/run_c171.ps1 -C170Summary ... -ExpectedHead ...`.
55 focused test modules,regression once;then `[C171] plan fixed`,
`[C171] checked=600/600 failed=... verified=... rejected=...`,RESULT and POSTCHECK.
Return full log including valid FAIL. C170 stays accepted and need not be rerun.
**Judge C171 -> ledger/handoff -> next design;no C172 or action/learning run before judgment.**
