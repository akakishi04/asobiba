# FOLD Experiment Ledger and Handoff

> Current authoritative handoff. Detailed history remains in Gate decisions and `experiment-ledger-addendum-*` files.

## Environment / protocol

- Repo: `akakishi04/asobiba`, branch `feat/sft-target-loss`, local `M:\asobiba\fold`.
- Python: `.venv-py31315\Scripts\python.exe`; Python 3.13.15; PyTorch 2.10.0+cu130; CUDA 13.0; RTX 4070 Ti SUPER.
- Protected C37 SHA256: `FD4A8DA897BDAEA9D103A252E30212C7FF842D23300D7C837333E146DEE51931`.
- Protected fixture SHA256: `A52F8209703149407580F7E2965B61B78653030EE992AF6D759865736741CA9E`.
- One scientific question per C number. Full output overwrites `runs/chatgpt-last.log`. Judge execution validity separately from scientific result. Invalid retries keep the same C number. Valid negatives may complete it.

## Gate status

- Gate A: PASSED.
- Gate B: PASSED.
- Gate C: PASSED, scoped.
- Gate D: PASSED, scoped.
- Gate E: NOT PASSED; active stage.

Gate C lead: `W_module = W_base + A_module @ B_shared`, materialized training / GEMM-native inference.

Gate D lead: `fold_lm.v05.controller.ControlLaneActionRouter`. Main working-state width and routing-control width are independent capacity axes.

Primary product priority: operational VRAM headroom, then peak/resident VRAM, then latency/throughput, then artifact size.

## V5-E current production contract

Action family:

```text
ANSWER / READ_MEMORY / RETRIEVE / OBSERVE / ASK_USER / STOP_UNRESOLVED
```

Authority:

```text
model/router -> proposes action
runtime      -> owns availability, permission, acquisition outcome, validation,
                eligibility mutation, and authoritative evidence mutation
```

Representation:

```text
raw runtime encoding
-> schema-aware Control Representation Adapter
-> canonical boolean Control Lane
-> ControlLaneActionRouter
```

Production adapter: `fold_lm.v05.controller.canonicalize_boolean_channels`.

## Accepted V5-E evidence

- C97-C99: information sufficiency and successful acquire/reobserve/answer loop.
- C100-C102: learned SUCCESS / UNAVAILABLE / DENIED / INVALID handling with no guessed answers, repeat acquisition, or budget violations.
- C103-C105: six-action mechanism selection and runtime-owned fallback; minimum-burden semantics passed.
- C106: unseen eligibility-mask composition PASS; finite 16-mask memorization weakened.
- C107: independent evaluator PASS; shared train/eval generator bug weakened.
- C108: VALID NEGATIVE; raw signed-boolean amplitude changes caused a representation failure.
- C109: localized failure to seed `20261311`, `ood_b (-0.1,+4.0)`, boundary actions ANSWER/STOP.
- C110: diagnostic `-1/+1` canonicalization removed the C108 failure.
- C111: production adapter integration PASS; known regression and fresh seeds recovered.
- C112: natural class-frequency PASS; class-balanced sampling is not required in registered synthetic scope.
- C113: stale-high eligibility PASS; runtime preflight rejects stale proposals before execution and falls back safely.

## C114 — performance characterization: ACCEPTED

Batch=1, slots=1, fresh CUDA process per condition.

Median hot-path results:

```text
width 8:    router ~0.596 ms, adapter ~0.907 ms, production ~1.605 ms
width 5120: router ~0.530 ms, adapter ~0.863 ms, production ~1.626 ms
```

Production width5120/width8 latency ratio ~`1.013`; width5120 production/router-only ~`3.07`; extra warmup operational VRAM at width5120 `0 bytes`; router parameter count remained `186` at both widths.

Interpretation: production adapter cost is material relative to the tiny router but does not show meaningful width scaling or extra operational VRAM in the registered batch=1/slots=1 profile.

## C115 — stale-low terminal refresh: ACCEPTED PASS

Fresh seeds `20261351..53`; 81 mask pairs / 162 required cases / 30 false-negative cases.

STOP_UNRESOLVED with missing evidence triggers one authoritative availability refresh. Newly available mechanisms recover to ANSWER; confirmed-unavailable cases stop with zero execution. Required pass/recovery/STOP rates were `1.0`, with zero priority violations or premature STOP accepts.

## C116 — authoritative priority refresh: ACCEPTED PASS

Fresh seeds `20261361..63`; 81 mask pairs / 162 required cases; 50 priority-upgrade and 30 terminal-recovery cases.

Before external execution or terminal STOP, runtime refreshes authoritative availability. If a lower-burden mechanism has become available, the current proposal is suppressed, state is replaced by the authoritative mask, and the router reobserves before execution.

All registered rates were `1.0`; priority violations and premature STOP accepts were `0`; hidden action-trace invariance `1.0`.

## C117 — post-preflight clean-failure fallback: ACCEPTED PASS

The first C117 attempt was invalid because its helper referenced a nonexistent internal target helper. The retry preserved the experiment number, seeds, thresholds, and scientific question, corrected target construction through the existing direct-answer semantics, and added an import-preflight smoke check.

Valid retry on fresh seeds `20261371..73` evaluated 81 mask pairs and 594 trajectories per seed. Accepted metrics:

```text
trajectory pass rate            = 1.0
preflight correct rate          = 1.0
failure fallback recovery rate  = 1.0
hidden action-trace invariance  = 1.0
ineligible mechanism count      = 0
repeat failed mechanism count   = 0
budget violation count          = 0
```

Interpretation: under the registered synthetic contract, authoritative preflight composes with post-preflight clean failure handling. Failed mechanisms commit no evidence, are removed from eligibility, and fallback continues in minimum-burden order until success or STOP_UNRESOLVED.

## Active experiment — C118

Experiment: `C118-v5e-unknown-effect-containment`.

Question: if a mechanism passes authoritative preflight and executes, but runtime cannot determine whether a potentially non-idempotent external effect occurred, can runtime contain the ambiguity without false evidence commit, duplicate execution, or automatic fallback?

Registered UNKNOWN_EFFECT policy:

```text
exactly one external execution has occurred
-> evidence commit = 0
-> retry same mechanism = 0
-> automatic fallback execution = 0
-> terminal runtime state = UNRESOLVED_UNKNOWN_EFFECT
```

SUCCESS remains a control path and must commit exactly once and reobserve to ANSWER.

Prospective conditions:

```text
fresh seeds       = 20261381,20261382,20261383
validation base   = 3
mask pairs        = all 81 visible<=authoritative pairs
hidden            = 0,1
non-empty actual  -> SUCCESS and UNKNOWN_EFFECT controls
empty actual      -> confirmed unavailable STOP control
```

Every fresh seed must satisfy all registered success and containment rates at `1.0`, including exactly-one execution, zero commit/retry/fallback after UNKNOWN_EFFECT, confirmed-none STOP, and hidden action-trace invariance.

C118 remains synthetic and deliberately conservative. Reconciliation and idempotency-key recovery are separate future questions. Gate E remains NOT PASSED.

## Separate tracks / non-claims

- Shared-Basis auto-partition remains separate.
- Context/KV-replacement remains separate.
- Gate C/D and C97-C118 evidence is synthetic/scoped unless explicitly measured otherwise.
- Do not claim broad language quality, general epistemic self-knowledge, real-world tool selection, or general superiority over Transformer/LLM systems.
