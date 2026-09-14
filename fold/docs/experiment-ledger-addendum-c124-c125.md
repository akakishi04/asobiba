# C124-C125 experiment addendum

## C124 — ACCEPTED PASS

Fresh seeds `20261441..43`; 1,442 scenarios per seed. Sequential duplicate delivery was suppressed exactly once. All deciding rates were `1.0`; C37 and fixture were preserved; tracked tree was clean.

## C125 — ACTIVE

Experiment: `C125-v5e-atomic-receipt-claim-falsification`.

Fresh seeds `20261451..53`; worker counts `2,4,8`; 1,442 scenarios per seed. The gate requires the naive non-atomic negative control to expose a race while the production atomic registry yields exactly one winner, rejects post-race duplicates, retains one receipt id, preserves C124 controls, and keeps downstream APPLIED / NOT_APPLIED / STILL_UNKNOWN totals exact.

Scope: in-process Python threads only. Distributed atomicity and crash durability are not claimed.
