# FOLD experiment ledger addendum — C129 to C130

## C129 — ACCEPTED PASS

`C129-v5e-recovery-fencing-falsification` passed on the valid retry with fresh seeds `20261491..93`.

The first C129 execution was invalid before the benchmark began because the CLI searched for the wrong C128 output-directory prefix. The retry kept the same C number, seeds, worker counts, thresholds and scientific conditions. The corrected CLI selected the accepted C128 summary by experiment id, PASS status and gate flag.

Per valid-retry seed: 1,442 scenarios, including 1,440 lease-expiry takeover/fencing cases across 2/4/8 workers. All deciding rates were `1.0`: C128 control preservation, exactly-one takeover winner, strictly higher fencing token, new-owner acceptance, stale-owner write/release rejection, loser zero-action, APPLIED / NOT_APPLIED / STILL_UNKNOWN recovery controls, worker-specific takeover rates and hidden trace invariance. Focused regression was 60/60. Protected C37 and fixture were preserved and the tracked tree remained clean.

## C130 — ACTIVE

Experiment: `C130-v5e-lease-renewal-boundary-falsification`.

Question: can an active recovery owner renew a lease before expiry without changing its fencing token, while keeping exact expiry semantics unambiguous and preserving safe takeover/fencing after the renewed lease expires?

Production extension: `fold_lm.v05.recovery_fencing.RecoveryFencingRegistry.renew`.

Lease interval is half-open: `now < expires_at` is active; `now == expires_at` is expired. Renewal is permitted only for the exact current owner/token before expiry. Renewal never shortens a lease: new expiry is `max(current.expires_at, now + lease_ticks)`.

Fresh seeds: `20261501,20261502,20261503`. Renewal ticks: `1,3,4`. Expected coverage: 1,442 scenarios per seed, including 1,440 renewal-boundary cases.

Required semantics include valid pre-expiry renewal, wrong-owner renewal rejection, token preservation across renewal, expiry extension without shortening, takeover rejection at the old expiry after renewal, renewal rejection at the exact renewed expiry, takeover acceptance at that same boundary, higher takeover token, stale-token rejection, new-token acceptance, C129 control preservation, and the registered APPLIED / NOT_APPLIED / STILL_UNKNOWN recovery outcomes. All deciding rates are fixed at `1.0`.

C130 uses deterministic logical time. It does not establish real-clock skew tolerance, scheduler-pause behavior, or database-enforced lease renewal. Gate E remains NOT PASSED.
