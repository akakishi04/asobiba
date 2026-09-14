# FOLD Experiment Ledger and Handoff

> Current authoritative handoff. Detailed history remains in Gate decisions and `experiment-ledger-addendum-*` files.

## 1. Environment / protected artifacts

- Repository: `akakishi04/asobiba`
- Branch: `feat/sft-target-loss`
- Local repo: `M:\asobiba\fold`
- Python: `M:\asobiba\fold\.venv-py31315\Scripts\python.exe`
- Python 3.13.15 / PyTorch 2.10.0+cu130 / CUDA 13.0
- GPU: RTX 4070 Ti SUPER

Protected:

- `runs/chatgpt-last-result.json`
- SHA256 `FD4A8DA897BDAEA9D103A252E30212C7FF842D23300D7C837333E146DEE51931`
- `runs/fixtures/v05-c-composition-20260921.pt`
- SHA256 `A52F8209703149407580F7E2965B61B78653030EE992AF6D759865736741CA9E`

## 2. Experiment protocol

1. One scientific question per C number.
2. Full output overwrites `runs/chatgpt-last.log`.
3. User pastes the complete log.
4. Judge execution validity separately from scientific/performance interpretation.
5. Invalid retries keep the same C number.
6. Valid negative results may complete the C number.
7. Predeclare deciding thresholds before deciding data; characterization-only experiments must not invent post-hoc thresholds.
8. Preserve protected artifacts and require tracked tree clean.

## 3. Gate status

- Gate A: PASSED.
- Gate B: PASSED.
- Gate C: PASSED, scoped.
- Gate D: PASSED, scoped.
- Gate E: NOT PASSED. Active stage.

Gate C lead:

```text
W_module = W_base + A_module @ B_shared
training  -> materialized
inference -> gemm_native
```

Gate D lead: `fold_lm.v05.controller.ControlLaneActionRouter`.

Supported principle: main working-state width and routing-control width are independent capacity axes.

Primary product objective: operational VRAM headroom, then peak/resident VRAM, then latency/throughput, then artifact size.

## 4. V5-E current contract

Action family:

```text
ANSWER
READ_MEMORY
RETRIEVE
OBSERVE
ASK_USER
STOP_UNRESOLVED
```

Authority:

```text
model/router -> proposes action
runtime      -> owns availability, permission, acquisition outcome, validation, eligibility mutation, and authoritative evidence mutation
```

Production representation boundary:

```text
raw runtime encoding
-> schema-aware Control Representation Adapter
-> canonical boolean Control Lane
-> ControlLaneActionRouter
```

Production primitive: `fold_lm.v05.controller.canonicalize_boolean_channels`.

## 5. Accepted V5-E capability evidence — C97 to C105

C97-C99 established information sufficiency and the successful acquisition/reobserve/answer loop.

C100-C102 established learned handling of `SUCCESS / UNAVAILABLE / DENIED / INVALID` with no guessed answers, repeat acquisition, or budget violations.

C103-C105 expanded to the six-action mechanism policy and passed learned minimum-burden selection plus runtime-owned failure fallback.

## 6. Falsification / representation evidence — C106 to C112

- C106 unseen eligibility-mask composition: PASS. Finite 16-mask memorization weakened as an explanation.
- C107 independent evaluator: PASS. Shared train/eval generator bug weakened as an explanation.
- C108 signed feature re-encoding: VALID NEGATIVE. Raw Control Lane was not invariant to arbitrary signed boolean amplitudes.
- C109 localized the only failing condition to seed `20261311`, `ood_b (-0.1,+4.0)`, concentrated in `ANSWER` and `STOP_UNRESOLVED`.
- C110 diagnostic canonicalization: PASS. Mapping schema-known boolean inputs to `-1/+1` removed the registered failure.
- C111 production adapter integration: PASS. Known regression recovered and fresh seeds `20261321..23` all passed.
- C112 natural class-frequency falsification: PASS. Removing class-balanced training still yielded perfect six-class recall under the registered synthetic distribution, including rare `ASK_USER` and `STOP_UNRESOLVED` classes at `1.5625%` each.

## 7. C113 — stale eligibility runtime preflight: ACCEPTED PASS

Experiment: `C113-v5e-stale-eligibility-preflight`.

Fresh seeds `20261341..43`; unseen base=3; natural row sampling; production canonicalizer.

Exhaustive stale-high test:

```text
model-visible mask may contain false-positive eligibility
actual authoritative mask is a subset
router proposes
-> runtime preflight
-> stale proposal: external execution 0, commit 0, clear visible bit, reobserve
-> next minimum-burden action
```

Accepted across all seeds:

- 81 mask pairs / 162 required cases / 80 stale cases;
- answerable ANSWER `1.0`;
- required scenario pass `1.0`;
- stale-prefix exact `1.0`;
- actual-available ANSWER `1.0`;
- actual-available exactly-one execution `1.0`;
- no-actual STOP `1.0`;
- no-actual zero-execution `1.0`;
- hidden action-trace invariance `1.0`;
- priority violations `0`;
- stale external executions `0`;
- repeat stale rejects `0`.

Interpretation: stale-high model-visible eligibility can be contained safely by authoritative runtime preflight in the registered synthetic scope. Stale false-negative availability and real tool execution remain untested.

## 8. Active experiment — C114 production control hot-path performance

Experiment: `C114-v5e-production-control-hot-path-profile`.

Question:

> What latency and operational-VRAM cost does the production Control Representation Adapter add to the batch-1 Control Lane hot path, and does that cost grow with full core width despite the fixed-width router?

Profiles:

```text
router_only
adapter_only
production = adapter + router
```

Widths: `8` and `5120`.

Fixed measurement contract:

```text
batch=1
slots=1
control_width=4
hidden_width=8
action_count=6
warmup=200
iterations/sample=2000
samples=5
fresh CUDA process per (path,width)
```

Measure synchronized wall time, CUDA-event device time, warmup/post-profile free-VRAM consumption, single-decision peak allocated/reserved deltas, router parameter count, and production-vs-precanonicalized functional equivalence.

Derived comparisons include width5120/width8 scaling for adapter and production, width5120 production/router-only latency ratios, and extra operational VRAM at width5120.

C114 is characterization-only: no post-hoc performance threshold. Performance decisions are made after the registered measurements are observed.

## 9. Separate tracks / non-claims

- Shared-Basis auto-partition remains separate.
- Context/KV-replacement remains separate.
- Gate C/D and C97-C114 evidence is synthetic/scoped unless explicitly measured otherwise.
- Do not claim broad language quality, general epistemic self-knowledge, real-world tool selection, or general superiority over Transformer/LLM systems.
