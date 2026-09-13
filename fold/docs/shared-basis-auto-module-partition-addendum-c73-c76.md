# Shared Basis Auto-Partition Addendum — C73 to C76

Date: 2026-09-14

This addendum records accepted consequences from C73-C76 without replacing the
larger `shared-basis-auto-module-partition-report.md` living hypothesis document.

## Accepted evidence

### C73 — rank fraction is a runtime variable

At width5120, the full-core Shared/Dense runtime/storage frontier depended
strongly on rank fraction:

| profile | rank fraction | full-core persistent ratio | batch1 latency | batch8 latency |
|---|---:|---:|---:|---:|
| lean | 1/16 | ~0.7136 | 1.05725 | 1.06427 |
| medium | 1/8 | ~0.7605 | 1.07800 | 1.11564 |
| high | 1/4 | ~0.8542 | 1.23527 | 1.21851 |

Therefore rank/capacity is not free after quality is satisfied. Runtime cost must
be part of the capacity decision.

### C74 — retrospective rank3 signal

Condition rank3 reduced routed-weight ratio from 0.78125 (rank4) to 0.7109375,
but retrospective 12-seed exhaustive evidence was mildly worse versus Dense and
had no predeclared equivalence margin. Rank3 was kept as a candidate rather than
adopted.

### C75 — rank3 operational benefit

At the width5120 scaling bridge, rank3-equivalent 3/16 capacity used about 94.51%
of rank4-equivalent 1/4 full-core persistent bytes and reduced the endpoint
Shared/Dense latency tax by roughly 3-5.5% in the tested batches.

### C76 — prospective rank3 non-inferiority

A prospective independent 24-seed test fixed the decision rule before observing
new outcomes:

- primary delta: rank3 - rank4 exhaustive trajectory-exact accuracy;
- margin: -0.002 absolute accuracy;
- inference unit: model/data seed;
- deterministic paired bootstrap: 100,000 resamples;
- one-sided 95% lower bound.

Accepted result:

- mean delta: -0.00007946044;
- median: -0.00019994378;
- bootstrap lower 95%: -0.00051262739;
- required lower bound: > -0.002;
- non-inferiority gate: PASS;
- seed wins: rank3 10 / rank4 13 / tie 1;
- sign-test p: 0.67763948;
- pooled net rank3 correct advantage: -62 across 780,288 exhaustive held-out trajectories.

Condition rank3 is therefore the selected capacity point for subsequent
integration work, limited to the current synthetic-domain evidence.

## Auto-Partition rule update

The decision cascade remains quality-first, but rank selection now has an
explicit Pareto objective.

For a module/group whose current rank passes the functional gate:

1. do not increase rank from noisy single-seed or mixed-direction evidence;
2. when considering rank reduction, measure the operational benefit first;
3. if the benefit is material, define a prospective quality tolerance before
   collecting the deciding data;
4. adopt the lower rank only if that prospective quality gate passes;
5. after a selected-rank change, refresh execution/recurrence equivalence before
   production structural mutation;
6. among capacities that pass the same quality contract, prefer the lower-rank
   Pareto point unless another measured constraint dominates.

This strengthens the earlier principle:

```text
KEEP
 -> CO-ADAPTATION CHECK
 -> GROW_RANK only for persistent directional deficit
 -> SHADOW/SPLIT only after capacity/optimizer explanations are exhausted
```

with a complementary downward-capacity path:

```text
CURRENT RANK
 -> operational benefit estimate
 -> prospective quality margin
 -> independent quality gate
 -> LOWER RANK if gate passes
```

## Current selected ranks

For the present Gate-C task family:

- Condition: rank3
- Composition: rank2
- Language: rank4

These are task-specific selected points, not a universal width-to-rank law.
