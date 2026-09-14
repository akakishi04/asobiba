# FOLD experiment ledger addendum — C126 to C127

## C126 — ACCEPTED PASS

`C126-v5e-restart-recovery-falsification` passed on fresh seeds `20261461..63`.

Per seed: 1,442 scenarios, including 1,440 restart-recovery cases across 1/2/3 restarts. All deciding rates were `1.0`: pending snapshot survival, duplicate rejection after restart, exactly-one resume, completion persistence, post-completion duplicate rejection, downstream outcome controls, hidden trace invariance, and C125 control preservation. Snapshot state also crossed a JSON-serializable payload roundtrip. Protected C37 and fixture were preserved and the tracked tree remained clean.

## C127 — ACTIVE

Experiment: `C127-v5e-post-transition-crash-falsification`.

Crash point: receipt claim remains persisted as `pending`; downstream transition has been invoked; process crashes before local completion state is persisted.

Recovery is driven by an authoritative transition-status reconciliation:

```text
APPLIED       -> no replay; mark completed
NOT_APPLIED   -> replay once with the same transition key; then mark completed
STILL_UNKNOWN -> no replay; do not complete; keep pending
```

Fresh seeds: `20261471,20261472,20261473`. Restart counts: `1,2,3`. Expected coverage: 1,442 scenarios per seed, including 1,440 post-transition crash cases. C126 remains a required control gate. All deciding rates are fixed at `1.0`.

C127 assumes an authoritative source can classify the downstream transition outcome. It does not establish filesystem transaction durability or distributed recovery ownership. Gate E remains NOT PASSED.
