# Village Simulation Implementation Audit

Audit branch: `feat/minecraft-mods-bootstrap`  
Audit baseline: `1645911ebc08d4d54b6646a174ada8ce93c81b6f`

Scope: compare the current runtime MVP against the accepted village/world-simulation design in `../MOD_IDEAS.md`, with emphasis on the newly finalized Duty model, Village Status UI, persistence/indexing, partial-chunk behavior, real logistics, Welfare, migration lifecycle and performance budgets.

## Executive result

The existing village implementation is a useful feature-demonstration MVP, but it is **not structurally equivalent to the accepted final architecture**.

The main issue is not that a few constants are missing. Most village behavior currently lives in one event class and is driven by repeated local world scans plus per-villager persistent tags. The accepted design instead requires stable village/project/building/site records, indexed/event-driven invalidation, real carried cargo, bounded scheduling and conservative behavior across unloaded chunks.

Recommendation: **do not keep adding final-spec behavior directly into the current `VillageSimulationEvents` shape.** Preserve the working mechanics as references, but introduce the persistent/scheduled village core first and migrate behaviors onto it in controlled passes.

## Current implementation shape

Primary files:
- `VillageSimulationEvents.java` — ~974 lines; construction, roads, logistics, trade bonus, breeding, fire, migration, shelter and resource gathering are concentrated here
- `AsobibaRegistries.java` — Carpenter profession / POI / workbench
- `ForestRegenerationEvents.java` — player-centered probabilistic sapling regeneration
- `MobBuildingUseEvents.java` — repeated local shelter/campfire scans
- `ContinentalWorldgenEvents.java` — existing continent/ocean post-generation shaping
- `AsobibaTweaksConfig.java` — feature toggles

Persistent village-wide SavedData / VillageRecord / BuildingRecord / ProjectRecord / RouteRecord / WorkSiteRecord / MigrationRecord were not found. Bell status-screen/networking implementation was not found.

## P0 — architecture / correctness blockers

### 1. No stable village-level persistence model

Current construction/migration state is stored primarily on individual villagers through keys such as:
- `BUILD_X/Y/Z`
- `BUILD_STEP`
- `BUILD_ACTIVE`
- `BUILDER_XP`
- `DISTRESS`
- `SETTLE_X/Y/Z`
- `SETTLE_UNTIL`

Consequences:
- a project is effectively owned by one Carpenter rather than by a persistent village ProjectRecord
- lead-Carpenter replacement cannot safely resume an existing shared project
- there is no stable Village ID, district identity, building/site/route identity or schema version
- no robust Cached/Unknown model exists for partially unloaded villages
- merge/fission/abandonment cannot be represented faithfully

Required foundation:
- versioned per-`ServerLevel` VillageSavedData
- stable Village IDs
- Building/Storage/WorkSite/Route/Project/Migration records
- per-villager simulation data for Duty, Welfare, Carpenter Skill and Displaced state
- chunk-to-record index

### 2. Accepted Active/Cached/Unknown chunk model is not implemented

The current MVP operates directly from loaded villager events and local world queries. There is no persistent cached infrastructure model.

High-risk calls include build-site / road queries such as remote `getHeight(...)` and block-state access around candidate sites. These accesses must be guarded so the village simulation never requests distant chunks solely to evaluate or complete work.

Required:
- explicit loaded-chunk checks before physical queries/mutations
- pause project work when the next work unit is unavailable
- chunk-load revalidation through the chunk index
- no interpretation of unloaded housing/storage as zero

### 3. Resource movement is not physical logistics yet

Examples in the current MVP:
- Quarry Worker generates a Cobblestone ItemStack directly into nearby storage before removing stone
- Forester generates the log directly into nearby storage before removing the log block
- Porter picks up a ground ItemEntity and inserts it directly into storage
- Carpenter consumes each block directly from nearby storage during placement

This bypasses the accepted work-cargo / transfer model.

Required:
- persistent worker cargo: ordinary material workers 8 stacks, Porter 16 stacks, Carpenter 8 stacks
- gather -> worker cargo -> physical travel -> storage
- storage -> Carpenter cargo -> site -> placement
- Cargo Raft / pack-animal cargo remains real inventory
- ledger counts cargo separately until delivery

### 4. Storage discovery / accounting is scan-based and over-broad

`containers(...)` scans every BlockPos in a large cuboid and treats every found Container as eligible village storage.

Problems:
- repeated expensive scans
- arbitrary player containers may become village storage without intentional integration
- no categories, reservations, dirty-index reconciliation or storage identity
- no distinction between recognized village storage and unrelated containers

Required:
- StorageRecord registry
- explicit recognized-container membership
- event-driven dirty updates
- Resource Ledger cache
- material reservations
- periodic reconciliation safety audit only

### 5. No global simulation budget

Current work is mostly triggered from per-entity tick events. Several routines perform broad scans independently.

Notable scan sizes:
- `containers(radius=18)`: up to roughly 37×7×37 = 9,583 BlockPos checks per call
- breeding `countBlocks(radius=24)`: up to roughly 49×11×49 = 26,411 block checks
- Quarry Worker local search: roughly 17×7×17 = 2,023 positions
- Forester local search: roughly 21×8×21 = 3,528 positions
- rain shelter search in `MobBuildingUseEvents`: roughly 19×6×19 = 2,166 positions per qualifying mob
- campfire search can scan roughly 25×7×25 = 4,375 positions
- Forest regeneration can perform many repeated ~15×11×15 neighborhood scans during one attempt cycle

This conflicts with the accepted per-level queued budgets.

Required:
- central VillageSimulationScheduler
- bounded queues for planning, validation, container reconciliation and route/site searches
- stagger by Village ID / entity
- indexed lookup instead of repeated cuboid scans

## P1 — major accepted-feature gaps

### 6. Duty model conflicts with accepted design

Current routing:
- Mason -> Quarry Worker
- Fletcher -> Forester
- NONE or NITWIT -> Quartermaster/Porter, selected by UUID hash
- Shepherd -> shepherd work
- Farmer -> food export

Accepted design:
- Carpenter is the custom formal profession
- Quartermaster / Forester / Quarry Worker / Porter / Fire Responder are Duties
- Nitwits are excluded from routine labor
- Duty selection is demand-driven, persistent and reassessed at bounded cadence
- profession affinities are preferences, not hard mappings

Required:
- Duty enum/data
- staffing calculation per village
- assignment/reassignment timestamps
- staffing caps
- critical-profession preservation
- remove UUID-hash role selection

### 7. Carpenter implementation is still fixed-template MVP

Current:
- simple 5×5 hut/storage plans
- project state on Carpenter
- block list rebuilt from hardcoded methods
- no explicit phase record
- no final building/function validation
- no multi-story templates
- no semantic anchors
- no team/lead project ownership

Carpenter Skill currently increments as a small integer and can drive up to three placement actions per tick-cycle, which does not match the accepted 0–100 scale / ~1.35x max work-speed model.

Required:
- template/variant registry
- ProjectRecord with deterministic template+transform+variant seed
- phase/work cursor
- Lead Carpenter
- multi-worker claims
- final BuildingRecord validation
- 0–100 Carpenter Skill and accepted complexity bands

### 8. Some current construction creates blocks from incomplete material costs

Examples:
- Barrel / Composter / Carpenter Workbench placements in hardcoded plans can cost only a single plank Item in the current BuildStep model
- bridge logic may consume “any plank” and then place the biome-selected plank type

This violates the accepted real-resource/no-hidden-conversion rule.

Required:
- explicit material bills per template phase
- exact/compatible ingredient consumption
- approved substitutions through Building Culture, not item transmutation

### 9. Welfare / Confinement is absent

No implementation was found for:
- Welfare 0–100
- weighted life-history signals
- trade modifiers
- Refusal below 20
- recovery threshold 40
- Active-time-only observation
- anti-trading-hall behavior

`DISTRESS` is not a substitute for Welfare.

Required as an early migration pass because Arcane Folio pricing and breeding/migration depend on it.

### 10. Fire emergency behavior is much simpler than accepted

Current:
- every adult villager checks for any nearby fire
- one nearby fire is enough
- if water exists nearby, the villager can directly remove the fire block when close
- no sustained 3–4 fire threshold
- no water/container resource consumption
- no role-specific responder assignment
- baby villagers are excluded from the main villager tick path, so the accepted vulnerable-population evacuation behavior is absent

This is both a correctness gap and a performance hotspot.

### 11. Regional economy is not the accepted inventory-backed economy

Current `onRegionalTrade`:
- detects a few biome/item combinations
- randomly grants an extra Emerald to the player

This does not implement:
- inventory-backed scarcity/surplus
- 0.8x–1.8x bounded value bands
- actual goods entering village storage
- reserve-aware selling
- Welfare price composition
- player-visible reason strings

It also creates a bonus Emerald outside the accepted “same real economy” model.

### 12. Breeding model is still bed/food local heuristic

Current breeding gate uses nearby villager count, beds and food count.

Missing:
- village-wide sustainable population
- average Welfare
- infrastructure/logistics constraint
- 3-day food-reserve estimate
- <90% sustainable-pop eligibility
- settlement-wide birth cooldown
- Recovery Growth as a proper village state

Current `DISTRESS` / `RECOVERY_UNTIL` storage is per-villager, so shortage state can be inconsistent between prospective parents and the villager that detected the shortage.

### 13. Outpost / fission / migration lifecycle is only representative MVP

Current:
- outpost/colony selection depends on population + Carpenter XP modulo conditions
- settlers are selected from nearby loaded villagers
- target counts are 2/3
- no real founding supplies
- no Village ID creation
- refugee destination is effectively a nearby loaded villager with a bed
- no Viability
- no destination-capacity scoring
- no Displaced state
- no return/permanent-settlement lifecycle
- no Village Relocation
- no Village Merge / districts

Required after VillageRecord, Duty, storage and Welfare foundations exist.

### 14. Roads / bridges are immediate construction, not demand-driven projects

Current `buildRoadAndBridge`:
- runs after building completion
- interpolates a direct route
- immediately mutates path/bridge blocks in one call
- has no traffic demand
- no Road/RouteRecord
- no staged Carpenter public-works project
- no detour-vs-bridge cost model
- no width/upgrade lifecycle

Move road/bridge creation onto RouteRecord + Public Works projects.

### 15. Building Recognition / Occupancy is not yet the accepted persistent classifier

Current building-use logic is mainly local shelter/campfire heuristics plus vanilla POI assumptions.

Missing:
- BuildingRecord
- functional classifications
- semantic anchors
- validated capacity
- player-built structure adoption rules
- local dirty revalidation
- multi-story usable-floor records

### 16. Building Culture is inventory-biased rather than history-based

Current `chooseBuildingPlanks` selects the most abundant nearby plank type once it exceeds a small threshold, otherwise biome wood.

This means a one-time storage dump can immediately change architecture.

Accepted model requires:
- persistent weighted culture
- completed-building history
- structural/foundation/roof/trim preferences
- district culture
- slow drift
- parent-culture inheritance for founded settlements

### 17. Public Works is transient chat, not a persistent real-need view

Current `requestMaterials` sends a text message to a nearby player with a cooldown.

Missing:
- persistent request record
- real required/remaining quantities
- merged duplicate requests
- urgency
- destination/project context
- automatic closure
- Bell Status Needs/Projects UI

### 18. Village Status UI / networking is absent

No Bell status interaction, status screen, DTO/network payload or refresh protocol was found.

Required UI:
- Sneak+right-click Bell
- Overview / Needs / Projects
- read-only
- server-authoritative compact snapshots
- <=40-tick refresh while open only

## P2 — secondary systems / integration gaps

### 19. Forest regeneration needs integration with recognized land use

Current regeneration:
- player-centered random attempts
- biome + nearby log/leaves heuristic
- directly places sapling

Missing:
- explicit suppression near roads/buildings/farms/quarries/maintained player space
- recognized forest-edge / Forestry Site integration
- long-term managed/abandoned site behavior

### 20. Mob-used buildings should consume BuildingRecord indexes

Current mob shelter/campfire behavior repeatedly scans local blocks per mob.

Once BuildingRecord / public-space indexes exist, mobs should query indexed shelter/gathering candidates rather than perform large independent cuboid scans.

### 21. Continental River Networks are entirely pending

Current `ContinentalWorldgenEvents` implements continent/ocean shaping only.

Missing:
- drainage basins
- tributary/main-river topology
- lakes/outlets
- river terrain shaping
- river width/depth hierarchy
- delta/waterfall/rapid options
- village/structure river-placement bias
- River Corridor metadata integration

### 22. Tests / validation are insufficient for the accepted architecture

No focused village GameTests/unit tests were found in the repository tree.

Required minimum test families:
- SavedData round-trip / schema migration
- stable Village/Building/Project IDs
- reservation and ledger reconciliation
- no-duplication worker cargo transfer
- chunk unload/reload project pause/resume
- no force-load guard tests where feasible
- Welfare progression / Refusal hysteresis
- Duty assignment / Nitwit exclusion
- construction project resume after Lead loss
- migration group persistence and destination capacity
- public-request lifecycle
- deterministic template/variant reconstruction
- budget/scheduler starvation tests
- long-duration dedicated-server soak test

## What is already worth preserving

The audit does **not** recommend discarding everything.

Useful existing pieces:
- Carpenter custom profession / POI / workbench registration
- current Carpenter trade ladder as baseline content
- basic construction block placement mechanics
- biome-aware plank fallback
- fire/pathing prototypes
- basic farmer export/shepherd interaction prototypes
- simple forest regeneration behavior as a prototype
- existing feature toggles
- existing dedicated-server CI smoke gate

These should be migrated behind the new architecture rather than expanded in-place.

## Recommended implementation order

### Pass V0 — Freeze old MVP expansion
- no new village features added directly to `VillageSimulationEvents`
- preserve behavior while foundation is introduced

### Pass V1 — Persistent core
- VillageSavedData + schema version
- VillageRecord / BuildingRecord / StorageRecord / WorkSiteRecord / ProjectRecord
- stable IDs
- chunk index
- per-villager VillagerSimData
- basic reconciliation

**Gate:** save/reload preserves IDs and records; unloaded chunks are not treated as missing.

### Pass V2 — Scheduler / budgets / chunk safety
- central per-level work queues
- accepted planning/reconcile/validation budgets
- loaded-chunk guards
- event-driven dirty records
- remove repeated broad scans from hot per-villager paths

**Gate:** no village-owned chunk tickets; profiler/diagnostic counters demonstrate bounded per-tick work.

### Pass V3 — Recognized storage, ledger, reservations and physical cargo
- StorageRecord
- Resource Ledger
- project reservations
- worker cargo
- Porter transfer jobs
- Carpenter cargo
- remove direct harvest-to-storage teleport

**Gate:** item conservation tests pass across gather -> transport -> build.

### Pass V4 — Duty scheduler + Welfare
- accepted Duty model
- Nitwit exclusion
- staffing caps/affinities
- Welfare 0–100
- Refusal/hysteresis
- Welfare trade modifier

**Gate:** one-cell permanent trading hall reliably reaches refusal; normal compact house does not.

### Pass V5 — Projects / buildings / culture / roads
- modular templates + semantic anchors
- project phases
- Lead Carpenter + team claims
- multi-story templates
- BuildingRecord classifier
- persistent Building Culture
- demand-driven RouteRecord / roads / bridges

**Gate:** project can pause/unload/reload/change lead and still finish without duplication or corruption.

### Pass V6 — Economy / population / migration lifecycle
- inventory-backed scarcity
- sustainable population
- Recovery Growth
- Settlement Viability
- migration/refugee/return/relocation
- fission/merge/districts

**Gate:** multi-day simulation preserves people/items and never teleports resources.

### Pass V7 — Village Status UI
- Bell interaction
- server DTO
- Overview / Needs / Projects
- regional-trade reason display

**Gate:** read-only UI shows the same authoritative request/project state used by the simulation.

### Pass V8 — forest/building-use integration + river worldgen
- indexed mob shelter/gathering
- recognized-land-use forest regeneration
- Continental River Networks
- River Corridor integration

**Gate:** long-duration new-world playtest + worldgen compatibility testing.

## Recommended immediate next step

Begin **V1 only**. Do not implement Welfare, roads, migration UI or river worldgen before the persistent village core exists. Nearly every accepted feature depends on stable shared records, and implementing them first against the old per-villager/tag architecture would create avoidable rework.
