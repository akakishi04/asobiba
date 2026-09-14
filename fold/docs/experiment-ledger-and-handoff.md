# FOLD Experiment Ledger and Handoff

> Current authoritative handoff. Detailed history is retained in Gate decisions and experiment-ledger addenda.

## Environment / protocol

- Repo: `akakishi04/asobiba`
- Branch: `feat/sft-target-loss`
- Local: `M:\asobiba\fold`
- Python 3.13.15 / PyTorch 2.10.0+cu130 / CUDA 13.0 / RTX 4070 Ti SUPER
- Protected C37 SHA256: `FD4A8DA897BDAEA9D103A252E30212C7FF842D23300D7C837333E146DEE51931`
- Protected fixture SHA256: `A52F8209703149407580F7E2965B61B78653030EE992AF6D759865736741CA9E`
- One scientific question per C number. Invalid execution retries keep the same C number.

## Gate status

- Gate A: PASSED
- Gate B: PASSED
- Gate C: PASSED, scoped
- Gate D: PASSED, scoped
- Gate E: NOT PASSED; active

Gate C lead: `W_module = W_base + A_module @ B_shared`.
Gate D lead: `fold_lm.v05.controller.ControlLaneActionRouter`.
Primary product priority: operational VRAM headroom, then peak/resident VRAM, latency/throughput, artifact size.

## V5-E runtime chain

```text
model/router proposal
-> authoritative availability / permission
-> outcome validation
-> receipt binding / authority / scope
-> commit-context revalidation
-> replay suppression / atomic claim
-> pending/completed recovery state
-> post-transition reconciliation
-> concurrent recovery ownership
-> lease takeover + fencing token
-> completion
```

## Accepted through C129

C97-C107 established the synthetic information-sufficiency and routing baseline. C108 was a valid negative on arbitrary signed boolean amplitudes; C109-C111 localized and repaired it with schema-aware canonicalization. C112-C118 hardened natural sampling, eligibility refresh, preflight, failure fallback and UNKNOWN_EFFECT containment. C119-C123 established reconciliation, receipt binding/authority/scope and commit-context revalidation. C124-C129 progressively established sequential replay suppression, concurrent atomic receipt claim, restart recovery, post-transition crash recovery, concurrent recovery ownership and lease-expiry fencing.

C129 valid retry: fresh seeds `20261491..93`; 1,442 scenarios per seed across 2/4/8 workers; all deciding rates `1.0`; focused regression 60/60; C37 and fixture preserved; tracked tree clean. The first C129 execution was invalid before benchmark execution because the CLI searched the wrong C128 result prefix. The retry kept the same scientific settings.

## Active experiment — C130

Experiment: `C130-v5e-lease-renewal-boundary-falsification`.

Question: can the current recovery owner renew an active lease before expiry without changing its fencing token, while preserving an unambiguous expiry boundary and safe takeover after the renewed lease expires?

Production extension: `fold_lm.v05.recovery_fencing.RecoveryFencingRegistry.renew`.

Semantics:

```text
active                    -> now < expires_at
expired                   -> now == expires_at
valid renewal             -> current owner + current token + pre-expiry
renewal token             -> unchanged
renewed expiry            -> max(current expiry, now + lease_ticks)
renewal at exact expiry   -> rejected
takeover at exact expiry  -> allowed with a higher token
```

Fresh seeds: `20261501,20261502,20261503`.
Renewal ticks: `1,3,4`.
Coverage: 1,440 renewal-boundary cases + 2 confirmed-none controls = 1,442 scenarios per seed.

Required rates at `1.0`: C129 control preservation, wrong-owner renewal rejection, valid renewal, token preservation, expiry extension/no shortening, old-expiry takeover block, exact-expiry renewal rejection, exact-expiry takeover acceptance, higher takeover token, stale-token rejection, new-token acceptance, APPLIED / NOT_APPLIED / STILL_UNKNOWN recovery controls, timing-specific boundary rates and hidden trace invariance.

Scope: deterministic logical time only. Real-clock skew, scheduler pauses and storage-enforced renewal remain outside C130. Gate E remains NOT PASSED.

## Non-claims

- Shared-Basis auto-partition remains separate.
- Context/KV replacement remains separate.
- Gate C/D and C97-C130 evidence remains synthetic/scoped unless explicitly measured otherwise.
