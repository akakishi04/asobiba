# FOLD experiment ledger addendum — C125 to C126

## C125 — ACCEPTED PASS

`C125-v5e-atomic-receipt-claim-falsification` passed on fresh seeds `20261451..53`.

Per seed: 1,442 scenarios, including 1,440 concurrent duplicate-claim cases across worker counts 2, 4, and 8. The atomic registry produced exactly one winner in every case; post-race duplicate claims were rejected; the registry contained exactly one receipt id. The deliberately non-atomic negative control produced multiple winners and was detected. C124 controls and downstream APPLIED / NOT_APPLIED / STILL_UNKNOWN totals remained exact. C37 and fixture were preserved and the tracked tree was clean.

Scope: in-process Python-thread atomicity only. Cross-process/distributed atomicity and crash durability are not established.

## C126 — ACTIVE

Experiment: `C126-v5e-restart-recovery-falsification`.

Question: after a receipt claim has been persisted but before downstream transition begins, can restart reconstruction preserve a distinct pending state, suppress fresh duplicate claims, resume exactly once, and persist completion?

Production state: `fold_lm.v05.receipt_recovery.ReceiptRecoverySnapshot` and `ReceiptRecoveryRegistry`.

Fresh seeds: `20261461,20261462,20261463`. Restart counts: 1, 2, 3.

Per seed coverage: 1,440 restart-recovery cases plus 2 confirmed-none controls, for 1,442 scenarios total. Snapshot state crosses a JSON-serializable payload boundary on every simulated restart.

All deciding rates are fixed at 1.0, including C125 control preservation, pending-state survival, duplicate-claim rejection during restart, exactly-one resume, completion persistence, post-completion duplicate rejection, downstream outcome totals, confirmed-none STOP, and hidden trace invariance.

C126 does not prove filesystem fsync durability and does not cover a crash after downstream transition has begun or concurrent recovery ownership after restart. Gate E remains NOT PASSED.
