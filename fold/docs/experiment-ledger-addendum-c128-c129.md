# FOLD experiment ledger addendum — C128 to C129

## C128 — ACCEPTED PASS

`C128-v5e-concurrent-recovery-ownership-falsification` passed on fresh seeds `20261481..83`.

Per seed: 1,442 scenarios, including 1,440 concurrent recovery cases across 2/4/8 workers. All deciding rates were `1.0`: naive ownership race detection, single owner, exact owner identity, loser zero-action, exact owner release, APPLIED / NOT_APPLIED / STILL_UNKNOWN recovery controls, worker-specific single-owner rates, hidden trace invariance, and C127 control preservation. Protected C37 and fixture were preserved and the tracked tree remained clean.

## C129 — ACTIVE

Experiment: `C129-v5e-recovery-fencing-falsification`.

Question: after a recovery owner lease expires, can concurrent takeover issue a strictly higher fencing token and prevent the stale owner from driving any recovery write or release after a new owner has taken over?

Production primitive: `fold_lm.v05.recovery_fencing.RecoveryFencingRegistry`.

Fresh seeds: `20261491,20261492,20261493`. Worker counts: `2,4,8`. Expected coverage: 1,442 scenarios per seed, including 1,440 takeover/fencing cases.

Required semantics include exactly one takeover winner, monotonically higher fencing token, new-owner write acceptance, stale-owner write and release rejection, loser zero-action, exact owner release, C128 control preservation, and the registered APPLIED / NOT_APPLIED / STILL_UNKNOWN recovery outcomes. A dedicated regression also proves that an old token is rejected even when the worker id itself is reused by a newer incarnation.

C129 uses deterministic logical-time leases in one Python process. It does not establish distributed consensus, database-enforced fencing, lease renewal, or clock-skew semantics. Gate E remains NOT PASSED.
