# FOLD experiment ledger addendum — C120 to C121

## C120 — ACCEPTED PASS

`C120-v5e-receipt-binding-falsification` completed validly on seeds `20261401..03`.

Coverage per seed:
- 81 mask pairs
- 1,922 scenarios
- 480 exact-binding controls
- 1,440 invalid-binding cases

All deciding rates were `1.0`: valid binding acceptance, invalid binding rejection/containment, zero commit/retry/fallback on invalid binding, confirmed-none STOP, and hidden trace invariance. Protected artifacts remained unchanged and the tracked tree was clean.

Production primitive `receipt_matches_request` is accepted for the registered synthetic request-key / mechanism / epoch binding contract.

Gate E remains NOT PASSED.

## C121 — ACTIVE

Question: after exact request binding, may reconciliation proceed only when the receipt also comes from the expected provider and an external verifier has marked it valid?

Production primitive: `receipt_is_authoritative`.

Fresh seeds: `20261411, 20261412, 20261413`.

Per seed coverage:
- 480 trusted receipt cases
- 960 untrusted receipt cases
- 2 confirmed-none controls
- 1,442 scenarios total

Prospective gate: all deciding rates exactly `1.0`, including trusted acceptance, wrong-provider rejection, failed-verification rejection, untrusted containment with zero commit/retry/fallback, confirmed-none STOP, C120 control preservation, and hidden trace invariance.

C121 consumes an external verification verdict; it does not validate the verifier implementation or cryptography itself.
