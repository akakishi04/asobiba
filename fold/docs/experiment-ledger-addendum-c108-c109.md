# FOLD Experiment Ledger Addendum — C108 to C109

## C108 — accepted valid negative: feature re-encoding falsification

Experiment: `C108-v5e-feature-reencoding-falsification`

Execution was valid:

- branch / commit correct;
- focused controller regression passed 6/6;
- protected C37 and runtime fixture preserved;
- tracked repository clean;
- benchmark `status=PASS`;
- production runtime unchanged.

Scientific gate result: **FAIL (valid negative)**.

Prospective thresholds were not relaxed.

Training codebooks:

```text
train_a: false=-0.5, true=+0.75
train_b: false=-2.0, true=+1.25
```

Held-out OOD codebooks:

```text
ood_a: false=-3.5, true=+0.20
ood_b: false=-0.10, true=+4.0
ood_c: false=-7.0, true=+9.0
```

All OOD scalar values were absent from training and all codebooks preserved the registered sign contract `false < 0 < true`.

Accepted result:

- anchor action accuracy min `1.0`;
- anchor minimum class recall min `1.0`;
- OOD action accuracy min `0.953125`;
- OOD minimum class recall min `0.0`;
- OOD minimum-burden rate min `1.0`;
- OOD ineligible mechanism count sum `2`;
- OOD action flip count sum `6`;
- OOD hidden-counterfactual action invariance min `1.0`;
- only seed `20261311` failed the predeclared gate; seeds `20261312` and `20261313` passed.

Interpretation:

1. The learned mechanism policy remains correct on the registered anchor representation.
2. The Control Lane is not fully invariant to arbitrary signed boolean amplitude changes even when sign semantics are preserved.
3. The failure is representation robustness, not evidence of hidden/target leakage: hidden-counterfactual invariance remained `1.0`.
4. Because ineligible mechanism predictions occurred, this is operationally relevant; it is not merely a harmless confidence/margin change.
5. Do not treat `false < 0 < true` alone as a sufficient production input contract for the current router.

C108 does **not** invalidate C103-C107. It narrows the supported representation scope.

## C109 — active diagnostic: failure localization

Experiment: `C109-v5e-reencoding-failure-localization`

Question:

> Which held-out codebook and action class caused the accepted C108 failure, and does the known failing seed reproduce deterministically without any training or threshold changes?

C109 changes no architecture, training hyperparameters, codebooks, seeds, labels, or acceptance thresholds. It replays C108 seeds:

```text
20261311
20261312
20261313
```

For each OOD codebook it records:

- action accuracy;
- per-class recall;
- full 6x6 confusion matrix;
- logical rows that flipped;
- working/control lane values for each error;
- post-LayerNorm feature values for each error.

C109 is diagnostic only. It does not repair C108 and has no Gate-E passage claim.

No canonicalization or preprocessing fix is registered until C109 identifies the failure pattern.
