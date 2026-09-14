# Experiment Ledger Addendum — C114 to C115

## C114 — ACCEPTED performance characterization

Experiment: `C114-v5e-production-control-hot-path-profile`

Execution was valid: focused regression passed, protected artifacts were preserved, tracked tree was clean, and all functional-equivalence checks passed.

Batch=1 / slots=1 medians:

| width | path | wall us/decision | device us/decision |
| ---: | --- | ---: | ---: |
| 8 | router_only | 595.909100 | 595.873779 |
| 8 | adapter_only | 906.926850 | 906.882568 |
| 8 | production | 1604.818550 | 1604.684448 |
| 5120 | router_only | 529.513100 | 529.186279 |
| 5120 | adapter_only | 862.851700 | 862.811646 |
| 5120 | production | 1625.510850 | 1624.994873 |

Derived observations:

- router parameter count remained 186 at width 8 and 5120;
- production width5120/width8 wall ratio = `1.0128938564`;
- production width5120/width8 device ratio = `1.0126569587`;
- adapter width5120/width8 ratios were about `0.9514`, consistent with no meaningful full-width growth in this batch-1 profile;
- width5120 production/router-only ratio was about `3.07x`;
- extra warmup operational VRAM at width5120 versus router-only was `0 bytes` at measurement resolution;
- no post-hoc performance threshold was applied.

Interpretation: the production adapter is not showing width-proportional latency or operational-VRAM growth at width 5120 in the registered batch-1 resident-CUDA profile. Its absolute overhead is material relative to the tiny router itself (~1.63 ms production versus ~0.53 ms router-only), but remains small for event-level V5-E acquisition decisions. This does not justify per-token or per-layer use without separate profiling.

Gate E remains NOT PASSED.

## C115 — ACTIVE stale-low terminal refresh falsification

Experiment: `C115-v5e-stale-low-terminal-refresh`

Question:

> If model-visible eligibility is stale-low and the router proposes `STOP_UNRESOLVED` while critical evidence is still missing, can runtime perform one authoritative availability refresh, recover newly available mechanisms, and only accept terminal STOP when authoritative availability is truly empty?

Fresh seeds:

```text
20261351
20261352
20261353
```

Registered scope:

- model-visible mask may be a subset of the authoritative actual mask;
- refresh occurs only before terminal `STOP_UNRESOLVED` while evidence remains missing;
- a newly discovered mechanism must be reobserved and selected according to the registered burden order;
- confirmed-empty authoritative state may accept `STOP_UNRESOLVED`;
- if a visible mechanism is already executable, C115 does not refresh merely to discover a lower-burden hidden mechanism. That is a separate experiment.

Prospective gate for every fresh seed:

```text
required scenario pass rate                  = 1.0
false-negative recovery rate                 = 1.0
false-negative exactly-one refresh rate      = 1.0
confirmed-unavailable STOP rate              = 1.0
confirmed-unavailable zero-execution rate    = 1.0
visible-available zero-refresh rate          = 1.0
hidden action-trace invariance               = 1.0
priority violation count                     = 0
premature STOP accept count                  = 0
```

A valid negative result completes C115 without relaxing thresholds.
