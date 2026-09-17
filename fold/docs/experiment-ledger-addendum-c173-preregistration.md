# C173 preregistration — Bounded acquisition lifecycle

Registered 2026-09-17 JST after C172 acceptance/handoff commit
`544f6adceae37481cb414f0db8abce9929ec31da`.
Read `structured-acquisition-lifecycle-v0.1.md`, the C170/C171/C172 contracts and
`gate-e-evaluation-contract-v0.1.md`. Historical results and thresholds stay fixed.

## Formal state / question

**C173 ACTIVE / NOT YET JUDGED.**
`C173-v5e-bounded-acquisition-lifecycle`; `V5-E-BOUNDED-ACQUISITION-LIFECYCLE`.
Branch `feat/sft-target-loss`; use the final registration commit as ExpectedHead.
C172/C171/C170 remain ACCEPTED PASS; C160/C168/C169 remain ACCEPTED VALID NEGATIVE.
**Gate E NOT PASSED. C174 NOT REGISTERED.**

Can the reserved-intent lifecycle reauthorize a bounded actual local file read, validate
its response, publish only the selected observed fact, and resume the unchanged derived-
answer path without duplicate spend, stale proof reuse or fabricated evidence?
Implementation/reference integration question, not an unseen learned-model comparison.

Changed: add opt-in structured_acquisition_lifecycle. Hold C170 input, C171 proof rules,
C172 named actions/reservation costs and all earlier core/Controller/retrieval/emitter,
checkpoints, verdicts and Gate E scope unchanged. No neural policy, training, new seed,
C151 ranking, old large-query replay, network or external-account communication.
The provider is a new tiny exact file reference, not the historical vector adapter.
OBSERVE and ASK_USER are explicitly local-file simulations, not sensors/human interaction.

## Fixed finite batch:122 scenarios in8 groups

| Group | Scenarios | Fixed checks |
|---|---:|---|
| success |12|3 tools x AND/OR x acquired bit0/1. Known A is neutral; B is genuinely unobserved in TaskView until file admission. Reserve, dispatch, repeated dispatch, supplied three-step proof staging and verified answer.|
| delivery_faults |60|3 tools x20 fixed mutations/failures AFTER actual file read. Reject bad envelope, forged bit or false miss; then STOP.|
| pre_dispatch |27|3 tools x9 preconditions: revoked permission/availability, stale expression/fact, internal0/1, wrong intent, no pending, stopped. Provider calls0.|
| source_guards |8|One RETRIEVE each for hash mismatch, duplicate fact, Boolean bit, float bit, wrong epoch, malformed JSON, oversize and missing record.|
| staged |6|3 tools x controlling A0/1. Stage an old valid supplied proof, acquire B, require staging cleared, reject unprepared ANSWER, then restage old proof and require EVIDENCE_MISMATCH.|
| reentrant |3|One per tool; callback attempts nested dispatch. Nested call denied, outer call reads once and publishes once.|
| retry_budget |3|One per tool; missing delivery after real read, fresh retry denied for exhausted acquisition budget, old dispatch not repeated.|
| replay_delivery |3|One per tool; acquire B, then request C using second budget unit. Callback returns the OLD B delivery without a new file read. Reject it; C remains unobserved.|

20 delivery faults, fixed by name in manifest: missing, schema, intent, request, scope,
action, fact, provider, source, time, revision, reference, boolean, float, range,
payload_none, status, exception, value_flip, false_missing. Missing returns None; exception
raises declared ProviderFailure after the actual read. Both fail closed without fact update.
Valid bit substitution is checked against the hash-pinned witness, not a ground-truth label.

Each fresh owner has internal12/acquisition1, except replay_delivery acquisition2; time/
revision1, default max_dispatches4. Two valid source files contain B0/C1 and B1/C0. Eight
fixed fault-source files are written once before probes; all ten raw hashes/sizes and
expected binding hashes are in the label-free manifest. Deliberately wrong binding hashes
are distinct from actual-file protection hashes. No source is edited mid-run to rescue it.
Source max4096 bytes,4 records; oversized guard reads at most4097. No fallback provider.
Source request contains no expression, necessity label or evaluator target answer.

Scripted successful proof producer uses only actual admitted TaskView facts. It is hand-
written, not a learner; the fixed bit used for scoring is not supplied to that producer.
No heldout quality, hallucination reduction, autonomous acquisition or real ASK_USER claim.
Only selected fact publication in TaskView is counted; production EvidenceState writes0.

## Counts / deciding conditions

-122 complete scenario records; group counts exactly as above.
-236 C172 action calls and143 owner dispatch calls, including3 nested denied calls.
-122 acquisition reservations;417 internal units charged across logged action/dispatch calls.
-98 provider callback invocations;95 actual file-read attempts. The3 second replay callbacks
  reuse an old response and perform no new file read. These are NOT98 new observations.
-24 admitted facts/receipts;12 proof-verified task answers.
-18 C171 verifier calls and36 evaluated proof steps. Six old-proof rejections evaluate0 rules.
-Failure is counted per scenario as failed_checks; keep each underlying named Boolean check.
-Source bytes/read counters and successfully validated source-record count are reported,
  but do not call them all parse operations or a model-performance benchmark.
-0 learned forwards,0 training/fresh seeds,0 network calls,0 core EvidenceState/durable writes.

Source data witnesses stay runtime-private. Public admitted receipts strip the raw document;
only the chosen fact's value/reference enters C170's72-feature/binding packet. Unchosen source
records are not copied into known facts. Fixed snapshot epoch does not imply a dynamic-world
freshness/conflict-resolution algorithm. Trusted refresh controls are explicitly supplied
pre-dispatch invalidations; they are not policy actions or internally charged computation.

Label-free manifest SHA256:
`4d80ee765b8c277228b1fd73e187a086d2922e3a4d3d3900863691a53bac862f`.
Exact fixture shapes, fault names and accounting are fixed before the deciding run.

**PASS:** all122 scenarios and exact accounting;every named scenario check true;matching
admission only, no failed evidence leakage or unintended fact changes;old proofs/replies and
reentrant dispatch handled as registered;source/input/output/tree/HEAD protection preserved.
A scoped lifecycle PASS is not learned control, full transport security or full Gate E.

**ACCEPTED VALID NEGATIVE / FAIL:** finite wrong transition, output, source acceptance,
publication, replay or budget behavior under valid setup. Collect remaining independent
scenarios and preserve counterexamples. No case removal, callback substitution, cost-policy
change, schema repair or threshold movement during C173. Complete finite negatives exit0.

**INVALID / RETRY C173:** malformed trusted setup, source/parent/hash/manifest drift,
unexpected exception, incomplete coverage or outer protection failure. Save completed
scenario records in invalid.json once the run directory exists;restore execution validity
and retry unchanged C173. Declared malformed responses/sources are finite rejection tests,
not reasons to silently skip cases. No automatic continuation to C174.

## Source / output identity and reviewer verification

Parent C172 `runs/c172-v5e-action-runtime-dd06f1dd06d84fe8a0e215c04c76fac4/summary.json`.
SHA256 `b1698509fa5ab384b86731662092568e9348fe907ab9f4707ed0ea802709e943`.
Execution HEAD `e38ca796acd51dc54d6041ae69988f57592573e4`.
Pin its30 historical source entries plus C172's6 own source/doc files at that HEAD.
New module/benchmark/test/runner/design/preregistration checked against registration HEAD;
exact bytes or LF/CRLF-equivalent checkout only. No old197-row/600-row/large-query replay.
C37 and composition fixture stay protected outer artifacts, not loaded model inputs.

Fresh UUID directory:acquisition-plan.json before measurement,ten sources under sources/,
acquisition-results.json with all122 scenario transitions/receipts/checks,and full summary.
Record all hashes,sizes,count,source/commit,time and non-claims. Python and PowerShell
recheck source/input/tree/HEAD;runner rehashes new source/output artifacts and checks rows.
Hash/size checking is file integrity,not independent scientific replay.

Reviewer compiled three new Python files and passed **36/36 new tests** with actual new
modules and exact Git-blob-identical C170/C171/C172 dependencies (b874b6ab...,56709025...,
672a79ea...). No dependency substitutes. Four embedded runner Python commands parsed.
Those development unit examples are not a formal source/artifact-backed deciding run.
The full921 regression,actual Windows PowerShell,source guards and complete122-scenario
formal CLI were NOT run in the reviewer environment before registration.

Focused regression **921 expected=885+36**,57 modules,once before the batch. CPU test.
Runner `.venv-py31315/Scripts/python.exe`;`tools/run_c173.ps1 -C172Summary ... -ExpectedHead ...`.
Progress `[C173] plan fixed`,1/8 through8/8,`checked=122/122`,RESULT,POSTCHECK,
`run_execution_valid=True`. Keep valid FAIL. **Judge C173 -> ledger/handoff -> next design.**
