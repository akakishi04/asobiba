# FOLD experiment ledger addendum — C122 to C123

## C122 — ACCEPTED PASS

Fresh seeds `20261421..23`; 1,922 scenarios per seed.

Accepted result:

- 480 valid-scope cases;
- 1,440 invalid-scope cases;
- valid scope acceptance `1.0`;
- invalid scope rejection `1.0`;
- invalid scope commit / retry / fallback all zero;
- C121 control preserved;
- hidden trace invariance `1.0`;
- protected C37 and fixture preserved;
- tracked tree clean.

Interpretation: a verification verdict may be consumed only when its receipt id, source id, and scope epoch match the current receipt scope.

Gate E remains NOT PASSED.

## C123 — ACTIVE

Experiment: `C123-v5e-commit-context-falsification`.

Question: after receipt binding, authority, and verdict scope all pass, can runtime reject a result whose authoritative request epoch or provider generation changes before the state transition is committed?

Fresh seeds: `20261431,20261432,20261433`.

Coverage per seed:

- 480 unchanged-context controls;
- 1,440 changed-context cases;
- 2 confirmed-none controls;
- 1,922 scenarios total.

Every deciding rate is fixed at `1.0`. A changed context must produce zero commit, zero retry, and zero fallback. C122 remains a required control gate.

C123 remains synthetic and does not establish Gate E passage.
