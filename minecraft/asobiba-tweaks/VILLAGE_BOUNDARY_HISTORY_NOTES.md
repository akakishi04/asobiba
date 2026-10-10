# Village activity boundary and history maintenance

## Implemented behavior

- `VillageActivityBoundary` provides one horizontal spatial reference: a 48-block initial core, a bounded union of recognized anchor neighborhoods, and a 128-block cap from the effective center. The center follows the median concentration of recognized local anchors in steps of at most four blocks, with horizontal recentering limited to 16 blocks from the original seed.
- Growth admits at most eight new anchors per refresh from the preceding envelope, with 16-block neighborhoods and at most 128 persisted anchors. A connected chain cannot be absorbed in one refresh. Dense anchors within six blocks are deduplicated.
- Candidate sources are existing village Building/Storage/WorkSite/Route records and HOME/JOB_SITE/MEETING_POINT memories of loaded assigned residents. Index searches and candidate/node counts are bounded; no chunk loading or block adoption occurs during boundary refresh.
- Remote outposts, satellite-linked resource sites, and both `dock` and `river_dock` work-site labels cannot seed ordinary core expansion. Surveyed road waypoints can support gradual connected growth; an imagined straight route cannot.
- Definitely invalid indexed storage/building anchors are retired. Disconnected cached islands are removed. Unloaded or unknown resident anchors remain last-known information rather than being treated as destroyed.
- Ordinary new construction checks every horizontal footprint column, including non-convex gaps, with a maximum checked footprint of 32 by 32. Explicit outpost/colony planning keeps its separate spatial rules.
- Resource gathering uses the shared API through the designated-resource-site implementation. Housing/workshop demand, village welfare/safety aggregation, bootstrap membership, semantic adoption eligibility, and ordinary material-storage targeting also use the shared envelope.
- Freight's indexed storage facade, physical local container access, explicit satellite-worker access, emergency recovery, and already-paid cargo recovery remain available independently of ordinary core targeting. The boundary does not change carrier searches or freight recovery radii.

## Persistence and maintenance

- Village schema 12 adds the original boundary seed, bounded anchor positions, observed active ticks, and boundary/history/traffic scheduling metadata. Earlier saves default to the existing village center and an empty anchor list.
- Observation is driven by currently loaded resident ticks. The observation timestamp is runtime-only; loading a save cannot add the elapsed offline interval. A gap between observations contributes at most 40 ticks.
- Maintenance runs through the existing reconciliation scheduler every 1,200 observed active ticks. It keeps at most 64 eligible terminal ephemeral project results and 64 closed public requests/empty terminal migration records per village.
- Completed original construction, expansion, reuse, and circulation blueprints are preserved for physical repair ancestry. Only known completed building-repair/fixture jobs are eligible as ephemeral building work; active projects are never eligible.
- Reverse project-reference counts and village-local request/migration indexes are maintained on mutation and rebuilt once on load. Maintenance does not sweep the world's project/site history to discover references.
- Active project references, active request links, dock-purpose links, unresolved construction-aid ownership, known cargo/carrier ownership, and terminal jobs whose assigned worker is unloaded or still carrying cargo prevent deletion.
- Cancellation/completion clears project material bills immediately. Terminal records loaded from earlier saves also drop inert bills. Terminal setters cannot re-add a reservation until the project is returned to an active phase.
- Deleted ephemeral projects are removed from both their village and chunk indexes. No physical building/storage/work-site/route record, resident identity, migration with members, carrier identity, or cargo receipt is removed.
- Traffic is saturated at 10,000 and decays by one eighth (at least one) per observed active day. Cargo receipts are accounting for real physical transfers and are deliberately not treated as disposable rolling statistics.

## Conservative limits still in force

- A legacy per-village project, request, or migration catalog larger than 2,048 records fails closed for that category. Other bounded categories can still compact. A project with more than 256 parameter/reservation entries is retained. An oversized legacy catalog requires separately designed migration/manual review; this change does not claim to automatically compact arbitrary legacy histories.
- Route decay skips a village with more than 512 routes. Route writes/load still enforce the traffic saturation bound.
- Referenced records and durable physical blueprints are exempt from the 64-result ephemeral limit. Safety and repair ancestry take precedence over a blanket record-count target.
- Previously recognized POIs whose destruction has not been positively established retain conservative cached anchors. Boundary membership alone never establishes ownership of player property.
- This change does not erase abandoned settlements or introduce optional seven-/thirty-active-day physical-record compaction. Existing outpost lifecycle behavior remains in charge of those records.

## Regression coverage and verification

`VillageActivityBoundaryGameTests` covers initial size, one-hop connected asymmetric growth, maximum core extent, anchor-derived center, isolated structures, no property adoption, reload/active-clock behavior, negative terrain altitude, non-convex footprint gaps, and retiring proven-invalid anchors without deleting physical records.

`VillageHistoryMaintenanceGameTests` covers bounded terminal history, structural blueprint preservation, immediate reservation release, active references, unloaded owners, migration members, construction-aid ownership, closed versus active requests, traffic saturation/active-time decay/cargo receipts, rebuilt and released reverse references, and oversized legacy fail-closed behavior.

The central round-6 snapshot ran 223 tests; all ten boundary/history tests included in that snapshot passed. The subsequently added invalid-anchor-retirement regression and final terminal-reservation load/setter tightening need inclusion in the next central verification run. No independent Gradle run or push was performed for this workstream.
