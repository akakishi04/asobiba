# FOLD experiment addendum — C109 to C110

## C109 — accepted diagnostic localization

Experiment: `C109-v5e-reencoding-failure-localization`

C109 replayed C108 without changing training, thresholds, architecture, codebooks, or seeds.

Accepted execution facts:

- branch / commit valid;
- focused controller regression passed;
- C37 and runtime fixture preserved;
- tracked tree clean;
- `status=PASS`;
- C108 negative reproduced.

Localization:

```text
failing conditions = 1
seed                = 20261311
codebook            = ood_b
false / true        = -0.1 / +4.0
accuracy            = 0.953125
error count         = 6
```

Per-class recall in the failing condition:

```text
ANSWER           = 0.9583333333333334
READ_MEMORY      = 1.0
RETRIEVE         = 1.0
OBSERVE          = 1.0
ASK_USER         = 1.0
STOP_UNRESOLVED  = 0.0
```

All other seed/codebook pairs were perfect.

Interpretation: C108 is not a broad policy collapse. The failure is localized to an asymmetric signed encoding and to boundary actions (`ANSWER` / `STOP_UNRESOLVED`), while all four acquisition-mechanism classes remain intact.

Do not claim LayerNorm is the confirmed cause yet. C109 localizes but does not repair or causally identify the representation failure.

## C110 — prospective signed-control canonicalization diagnostic

Experiment: `C110-v5e-signed-control-canonicalization-diagnostic`

Question:

> If schema-known signed boolean Control-Lane values are canonicalized to `-1/+1` before the production router, does the registered C108 failure disappear while the raw path still reproduces the negative result?

C110 is paired and diagnostic only.

Unchanged:

```text
router architecture
training steps
optimizer
training codebooks
OOD codebooks
replay seeds = 20261311,20261312,20261313
```

Only diagnostic adapter:

```text
schema-known boolean signed value
-> sign(value)
-> {-1,+1}
```

Base remains untouched.

Prospective gate:

```text
raw C108 negative reproduced                  = true
canonical anchor action accuracy min          = 1.0
canonical anchor minimum class recall min     = 1.0
canonical OOD action accuracy min             = 1.0
canonical OOD minimum class recall min        = 1.0
canonical OOD minimum-burden rate min         = 1.0
canonical OOD ineligible mechanism count sum  = 0
canonical OOD action flip count sum           = 0
canonical all validation passed               = true
```

If C110 passes, the supported conclusion is narrow: explicit boolean canonicalization is sufficient to remove the registered C108 amplitude sensitivity under the sign contract. It does not mean the raw router is encoding-invariant, and it does not yet justify production integration.

If C110 fails, continue diagnosis rather than loosening thresholds.
