# FOLD Experiment Ledger and Handoff

> Current authoritative handoff for FOLD. Read this first in a new session. Update after every accepted Cxx result, retry decision, or Gate decision change.

## 1. Environment / repository

- Repository: `akakishi04/asobiba`
- FOLD path: `fold/`
- Branch: `feat/sft-target-loss`
- Local repo: `M:\asobiba\fold`
- Python: `M:\asobiba\fold\.venv-py31315\Scripts\python.exe`
- Python 3.13.15
- PyTorch `2.10.0+cu130`
- CUDA 13.0
- GPU: RTX 4070 Ti SUPER
- VS2022 Developer PowerShell 17.14.27

## 2. Protected artifacts

- C37 result: `M:\asobiba\fold\runs\chatgpt-last-result.json`
- SHA256: `FD4A8DA897BDAEA9D103A252E30212C7FF842D23300D7C837333E146DEE51931`
- runtime fixture: `M:\asobiba\fold\runs\fixtures\v05-c-composition-20260921.pt`
- SHA256: `A52F8209703149407580F7E2965B61B78653030EE992AF6D759865736741CA9E`

Diagnostics must preserve both.

## 3. Experiment protocol

1. One experiment / verification question per C number.
2. Full output overwrites `M:\asobiba\fold\runs\chatgpt-last.log`.
3. User pastes the complete log back into ChatGPT.
4. ChatGPT judges the result.
5. Increment only after a valid successful run.
6. Failed / invalid retries keep the same C number.
7. `status=PASS` means the experiment executed correctly, not automatically that a stage gate passed.
8. Invalid import/parser/hash/experiment-ID runs are not evidence.
9. Prefer tracked benchmark files and short tracked runners over large pasted scripts.
10. If a scientific acceptance margin is needed, define it before collecting deciding data.

PC clipboard:

```powershell
$log = "M:\asobiba\fold\runs\chatgpt-last.log"
Get-Content -LiteralPath $log -Raw -Encoding UTF8 -ErrorAction Stop | Set-Clipboard
```

Smartphone / Termius OSC52:

```powershell
$log = "M:\asobiba\fold\runs\chatgpt-last.log"
$text = Get-Content -LiteralPath $log -Raw -Encoding UTF8 -ErrorAction Stop
$b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($text))
[Console]::Write("$([char]27)]52;c;$b64$([char]7)")
```

## 4. Gate status

### Gate A

Passed previously: reference math/accounting/causality established.

### Gate B

Passed previously: uncompressed shared-core + fixed/teacher-routed modules learn the registered tiny tasks reproducibly.

### Gate C

**PASSED on 2026-09-14, scoped to the registered V5 synthetic task/runtime regime.**

Formal decision:

`fold/docs/gate-c-decision-2026-09-14.md`

This is not a claim that FOLD broadly outperforms Transformer LLMs.

Current lead routed-weight family:

```text
W_module = W_base + A_module @ B_shared
```

Selected tiny-task capacities:

```text
Condition   rank3
Composition rank2
Language    rank4
```

Accepted production execution policy:

```text
training  -> materialized arithmetic
inference -> GEMM-native arithmetic
```

The same persistent Shared-Basis parameter layout/checkpoint is used in both modes.

## 5. Model-lightness priority

Primary product objective:

> Minimize operational VRAM occupied by FOLD so other applications retain usable GPU-memory headroom.

Priority order:

1. incremental operational device VRAM consumed / remaining headroom;
2. peak allocated and peak reserved VRAM;
3. resident model VRAM;
4. latency / throughput practicality;
5. serialized artifact size as supporting deployment/storage evidence.

Do not use parameter count alone as the authoritative model-weight metric.

## 6. Gate C accepted evidence summary

### C41-C57 — codebook path rejected as lead runtime

Direct fine-grained codebook execution reduced storage but decode/gather overhead scaled badly. C57 width1024 compact/dense latency reached `12.88719x`. Codebook remains a storage/reference baseline, not the lead execution family.

### C58-C67 — Shared Basis established

Lead family:

```text
W_module = W_base + A_module @ B_shared
```

Task-aware/native factorized training recovered the registered task quality. Aligned training rule:

```text
factor_lr = common_lr
```

Composition rank2 and Language rank4 became stable selected points; Condition was refined further in C74-C76.

### C68-C69 — Condition rank4 robustness

12 exhaustive seeds showed no systematic rank4 deficit against Dense:

- rank4 wins 6 / Dense wins 6;
- sign-test p = 1.0;
- mean exact delta `-0.00025117894`.

### C73 — rank/runtime scaling

At width5120:

| fraction | full-core persistent ratio | batch1 latency | batch8 latency |
|---|---:|---:|---:|
| 1/16 | ~0.7136 | 1.05725x | 1.06427x |
| 1/8 | ~0.7605 | 1.07800x | 1.11564x |
| 1/4 | ~0.8542 | 1.23527x | 1.21851x |

Rank is therefore an operational capacity cost, not a free quality knob.

### C74-C76 — Condition rank3 selection

C74 identified rank3 as plausible but did not justify adoption retrospectively.

C75 showed rank3-vs-rank4 operational benefit: about 5.5% lower full-core persistent bytes and roughly 3-5.5% lower endpoint latency tax at large width.

C76 then used 24 fresh seeds and a prospectively fixed non-inferiority margin `-0.002`:

- mean rank3-rank4 exact delta `-0.0000794604421`;
- one-sided 95% bootstrap lower bound `-0.000512627388`;
- non-inferiority gate PASS.

Decision: Condition rank3 selected.

### C77 — final selected-rank recurrence equivalence

Condition3 / Composition2 / Language4, 3 fresh seeds each:

- all validation scores equal;
- all validation semantics equal;
- all validation tensors allclose;
- recurrence depths 1/2/4/8/16/32/64 allclose;
- max recurrence abs gap `9.72747802734375e-05`;
- max recurrence relative-L2 gap `2.7345954560493825e-06`.

### C78-C80 — production training/inference policy

C78 valid negative result: direct GEMM-native arithmetic during optimization accumulated small long-training tensor drift despite nearly identical initial gradients and unchanged scores/semantics.

C79 localized the drift to arithmetic order: production parameter layout + materialized arithmetic matched the accepted materialized reference with output and parameter gap exactly `0.0`.

C80 accepted the explicit policy on fresh Language seeds:

```text
training  -> materialized
inference -> gemm_native
```

- production training parameters exact vs accepted reference;
- materialized outputs exact;
- native inference scores/semantics equal;
- native validation max abs gap `1.9073486328125e-06`;
- V5 regression suite passed.

### C81 — production large-shape runtime / resident memory

Actual production `SharedBasisFixedRoutingCore`, width5120:

| profile | persistent ratio | batch1 latency | batch8 latency |
|---|---:|---:|---:|
| 1/16 | 0.713616 | 1.05653x | 1.06662x |
| 1/8 | 0.760479 | 1.06485x | 1.10225x |
| 3/16 | 0.807342 | 1.11150x | 1.14160x |

All outputs allclose. Predeclared production practicality ceilings passed.

### C82 — production serialized artifact

Width3072 state_dict ratios:

- 1/16: `0.713668`;
- 1/8: `0.760522`;
- 3/16: `0.807377`.

All round-trips exact; no materialized effective-weight bank serialized.

### C83 — authoritative operational VRAM/headroom gate

Fresh-process width5120 measurements, 3 repeats/point, CUDA context initialized before baseline.

| profile | batch | Dense ready | Shared ready | headroom gain |
|---|---:|---:|---:|---:|
| 1/16 | 1 | 1.2422 GiB | 0.9141 GiB | 0.3281 GiB |
| 1/8 | 1 | 1.2422 GiB | 0.9668 GiB | 0.2754 GiB |
| 3/16 | 1 | 1.2422 GiB | 1.0215 GiB | 0.2207 GiB |
| 1/16 | 8 | 1.2617 GiB | 0.9512 GiB | 0.3105 GiB |
| 1/8 | 8 | 1.2617 GiB | 1.0039 GiB | 0.2578 GiB |
| 3/16 | 8 | 1.2617 GiB | 1.0586 GiB | 0.2031 GiB |

All points exceeded the prospectively declared `0.15 GiB` minimum headroom gain. Peak allocated and peak reserved VRAM were lower than Dense for every comparison.

Approximate inference-ready VRAM reduction is about 16% to 26% across the tested profiles/batches.

## 7. Production state after Gate C

`fold_lm.v05.modules.SharedBasisFixedRoutingCore` is the accepted V5-C candidate implementation.

Properties:

- existing Dense `HighPrecisionFixedRoutingCore` remains available;
- Shared Basis remains explicit/opt-in at this stage;
- execution mode is explicit and does not silently follow `train()` / `eval()`;
- train with `materialized` arithmetic;
- deploy/infer with `gemm_native` arithmetic;
- state_dict stores only canonical Shared-Basis parameters, not effective routed-weight copies.

## 8. Current stage — V5-D

V5-C is closed. Proceed to **V5-D — adaptive computation and routing**.

Roadmap action space begins with:

```text
ANSWER
COMPUTE(module, steps)
```

Initial V5-D principles:

1. establish fixed-step/fixed-route baselines before training a router;
2. on tiny tasks, enumerate candidate routes/step counts to create oracle/near-oracle routing targets;
3. begin with supervised routing;
4. compare dynamic computation against fixed maximum-step baselines;
5. quality must not be traded away merely to stop earlier;
6. harder cases should use more computation than easier cases if adaptive compute is meaningful.

Gate D eventually requires:

- additional steps used meaningfully on difficult cases;
- lower average compute on easy cases than fixed maximum-step execution;
- no quality collapse from premature stopping;
- routing-head compression must not cause unacceptable action flips.

## 9. Immediate next work

First V5-D experiment should register the routing/action semantics and establish an oracle/fixed-step baseline before adding a learned controller. Do not combine controller learning, information acquisition, memory, or Vision into the first V5-D experiment.

## 10. Scope / non-claims

Gate C PASS is limited to the registered V5 synthetic tasks, current selected ranks/fractions, float32 execution, the current Windows/CUDA/PyTorch environment, and tested two-module routed-core shapes.

Do not claim broad language quality or general superiority over Transformers/LLMs from these diagnostics.
