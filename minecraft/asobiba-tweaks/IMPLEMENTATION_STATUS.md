# AsobibaTweaks implementation status

Target: Minecraft 1.21.1 / NeoForge 21.1.219 / Java 21

This file maps the accepted implementation backlog in `../MOD_IDEAS.md` to its current MVP implementation.

Detailed village-system gap analysis and migration order: [`VILLAGE_IMPLEMENTATION_AUDIT.md`](VILLAGE_IMPLEMENTATION_AUDIT.md).

| Accepted feature | Main implementation | Status |
|---|---|---|
| Growing Items / mining-tier mutation | `GrowingItemsEvents`, `GrowingItemData` | Implemented |
| Daily Favor | `DailyFavorEvents` | Implemented |
| Universal Bond | `UniversalBondEvents`, `UniversalBondData` | Implemented |
| World Folklore / local memory / rituals | `FolkloreAndMoonEvents`, `FolkloreSavedData` | Implemented |
| Lunar Offering | `FolkloreAndMoonEvents` | Implemented |
| Wall Kick / Sliding / Ledge Climb | `MovementTweaksEvents` | Implemented |
| Field Repair | `InteractionTweaksEvents` | Implemented |
| Weapon / Torch Throwing | `InteractionTweaksEvents` | Implemented |
| Carry Small Mobs | `InteractionTweaksEvents` | Implemented |
| Expanded Fishing Rod | `InteractionTweaksEvents` | Implemented |
| Extinguish Primed Creepers | `InteractionTweaksEvents` | Implemented |
| Temporary Ender Pearl Return Point | `InteractionTweaksEvents` | Implemented |
| Firework Propulsion | `InteractionTweaksEvents` | Implemented |
| Dispenser-fired Ender Pearls | `InteractionTweaksEvents` | Implemented |
| Expanded Riding | `InteractionTweaksEvents` | Implemented |
| Mob-on-Mob Riding | `WorldOddityEvents` | Implemented |
| Linked Double Doors | `InteractionTweaksEvents` | Implemented |
| Armor Stand Loadout Swap | `InteractionTweaksEvents` | Implemented |
| Enderman Micro-Building | `WorldOddityEvents` | Implemented |
| Parrot Perches | `WorldOddityEvents` | Implemented |
| Mob Gatherings | `WorldOddityEvents` | Implemented |
| Rare Armor Stand Pose Drift | `WorldOddityEvents` | Implemented |
| Elytra Armor Stand Display | `ArmorStandElytraMixin` | Implemented; visual playtest required |
| Auto-connected Map Walls | `OceanAndDisplayEvents` | Implemented |
| High-Speed Minecarts | `AbstractMinecartMixin` | Implemented |
| Minecart Collision Damage | `PhysicsTransportEvents` | Implemented |
| Minecart Momentum Dismount | `TransportTweaksEvents` | Implemented |
| Coupled Minecarts | `PhysicsTransportEvents` | Implemented |
| Blast / Slipstream Wind Pressure | `PhysicsTransportEvents` | Implemented |
| Wind Pressure Resistance | datapack enchantment + `PhysicsTransportEvents` | Implemented |
| Growing Enchantments | `EnchantmentTweaksEvents`, `EnchantmentMasteryData` | Implemented |
| Enchantment Branches | `EnchantmentTweaksEvents` | **V16+V17 expanded**: explicit branch-selection state plus concrete Efficiency / Feather Falling / Fortune / Respiration branch effects; Mending is excluded from branch selection as designed. Remaining accepted branch families are still pending |
| Curse Growth | `EnchantmentTweaksEvents` | Implemented |
| Fortune / Silk Touch Switching | `EnchantmentTweaksEvents` | Implemented |
| Mastery Inheritance | `EnchantmentTweaksEvents` | Implemented |
| Uncapped Anvil XP Cost | `AnvilMenuMixin` | Implemented |
| Direct Enchanting-Table Reroll | `EnchantmentMenuExtensionsMixin`, `EnchantingScreenEvents` | Implemented; XP cost |
| Enchantment-Pool Bookshelves | Arcane Bookshelf + `EnchantmentMenuExtensionsMixin` | Implemented |
| Extended Enchanting Targets | `ExtendedEnchantableItemMixin`, `EnchantmentExtensionMixin`, `EnchantedWorkBlockSavedData` | Implemented; effects intentionally deferred |
| Raised Enchantment Level Caps | `EnchantmentExtensionMixin` | Implemented; configurable cap |
| Atlas / Map Binder | `AtlasItem`, `AtlasItemInHandRendererMixin` | Implemented |
| Potion Mixing | `AlchemyExplosivesCraftingEvents` | Implemented |
| TNT Design | `AlchemyExplosivesCraftingEvents`, `TntDesignSavedData`, `PrimedTntMixin` | Implemented |
| Fletching Table Expansion | `AlchemyExplosivesCraftingEvents` | Implemented |
| Giant Crops | `GiantOrganismEvents` | Implemented |
| Giant Mobs | `GiantOrganismEvents`, `GiantCreeperMixin` | Implemented |
| Continental Oceans / Islands / Archipelagos | `ContinentalWorldgenEvents` | Implemented; default OFF |
| Continental River Networks | `ContinentalRiverGenerator`, `ContinentalWorldgenEvents` | **V8 implemented initial network generator**: deterministic macro drainage cells, downhill neighbor routing, tributary widening, major rivers, meanders, sink lakes, delta widening and rapid/waterfall shaping; configurable and only active inside optional continental worldgen; CI build + dedicated-server smoke PASS, visual/new-world tuning still required |
| Large Boats / Cargo Rafts | `OceanAndDisplayEvents`, `BoatMixin` | Implemented |
| Ocean Drift Debris | `OceanAndDisplayEvents` | Implemented |
| Nether / Lava Fishing | `NetherFishingEvents` | Implemented |
| Nether Fish | `NetherFishEntity`, `NetherFishingEvents`, renderer/registry | Implemented |
| Mob-Used Buildings | `MobBuildingUseEvents`, `VillageBuildingService` | **V8 integrated**: mobs/villagers prefer indexed validated BuildingRecords for shelter before bounded local fallback scans; gathering/campfire fallback remains lightweight |
| Villager Welfare / Confinement | `VillagerWelfareService`, `VillagerWelfareMixin`, `VillagerSimData` | **V4 implemented**: Active-time weighted Welfare 0-100, refusal <20 / recovery >=40, restock blocking, trade price modifiers and feature toggle; CI build + dedicated-server smoke PASS |
| Village Status / Public Needs UI | `VillageStatusEvents`, `VillageStatusNetworking`, `VillageStatusPayload`, `VillageStatusScreen`, `VillagePublicWorksService` | **V7+V9 implemented**: Sneak+right-click recognized Bell opens read-only Overview / Needs / Projects UI from a server-authoritative compact snapshot; Needs now reads persistent real-deficit PublicRequestRecords, refresh is limited to ~40 ticks while open; CI build + dedicated-server smoke PASS |
| Village persistent state / indexes / simulation budgets | `VillageSavedData`, `VillagerSimData`, `VillageIdentityBootstrap`, `VillageSimulationScheduler`, `VillageDirtyEvents`, `VillageStorageService` | **V1-V5 foundation implemented**: versioned persistent records/IDs, chunk index, bounded scheduler/configurable budgets, loaded-chunk guards, dirty invalidation, recognized StorageRecords/ledger/reservations, persistent cargo, shared ProjectRecords and lazy BuildingRecord revalidation; CI build + dedicated-server smoke PASS |
| Regional Trade Value | `VillageEconomyService`, `VillagerWelfareMixin`, `VillageSimulationEvents` | **V6 implemented core**: real-ledger daily scarcity bands, bounded 0.8x-1.8x regional/economic pricing, Welfare composition, sold goods entering recognized storage, synthetic bonus-Emerald path removed; UI reasons are exposed through Village Status Needs |
| Fire Village Emergency | `VillageFireEmergencyService`, `VillagerSimData`, `VillageStatusNetworking` | **V8+ implemented core**: village-level sustained-fire detection, bounded emergency scans, temporary responder/evacuation Duties, real nearby-water or Water Bucket handling, suspended unloaded-chunk state, post-fire building invalidation and Bell emergency visibility; CI build + dedicated-server smoke PASS |
| Autonomous Village Growth | `VillageSimulationEvents`, `VillageSavedData`, `VillageStorageService` | **V5+V15 implemented core**: shared persistent ProjectRecord construction with real Carpenter cargo, concurrency caps and legacy migration plus a skill-gated housing family from basic one-story -> Trained gabled -> Skilled two-story -> Master three-story. Higher templates validate their full vertical build volume and contribute real matching bed capacity |
| Carpenter Profession | `AsobibaRegistries`, `VillageSimulationEvents`, `VillageDutyScheduler` | **V4/V5+V11 implemented**: formal Carpenter profession, persistent Duty integration, 8-slot work cargo, shared ProjectRecord execution, 0-100 skill migration/progression, skill-gated two-story template, accepted trade ladder and Building-Culture-aware wood-family trade palette |
| Village Logistics Roles | `VillageDutyScheduler`, `VillageSimulationEvents`, `VillagerSimData`, `VillageStorageService`, `VillageOutpostLifecycleService` | **V4+V10 implemented core**: demand-driven persistent Duties, profession affinities, Nitwit exclusion, physical worker cargo plus Outpost-specific worker assignment and physical Porter supply/export runs; water-logistics specialization remains later work |
| Outposts / Satellite Sites | `VillageSimulationEvents`, `VillageOutpostLifecycleService`, `VillageSavedData.WorkSiteRecord`, `VillagerSimData` | **V10 implemented core**: Outposts require real wood/stone demand plus validated remote resources, remain parent-linked, gain persistent purpose/state, use 1-2 physical remote workers, local buffering and Porter supply/export runs, reactivate from inactive state, become inactive after sustained loss of demand/route/resources and abandoned after longer failure; founding preparation now requires operational 7-day Outpost history and final 6-bed / local-storage / 48-food / active-route validation before daughter Village ID creation. Initial autonomous work purposes are Forestry/Quarry/Fishing/Farm |
| Roads / Bridges / River Use | `VillageSimulationEvents`, `VillageSavedData.RouteRecord/ProjectRecord`, `VillageRoadPlanner`, `VillageRiverService` | **V5+V8+V12+V13 implemented core**: persistent road/bridge projects, compact persistent route waypoints/indexing, bounded loaded-terrain cost routing, real bridge materials, River Corridor recognition, traffic-driven 1-3 block widening and Dirt -> Gravel -> Stone/Cobblestone upgrades with real Carpenter cargo. Visual terrain/bridge tuning remains playtest work |
| Building Recognition / Occupancy | `VillageSavedData.BuildingRecord`, `VillageBuildingService`, `VillageBuildingAdoptionService`, `VillageDirtyEvents`, `MobBuildingUseEvents` | **V5+ implemented**: persistent village-built recognition plus conservative player-built adoption, semantic residential/storage/workshop/mixed-use classification, edit-driven reclassification, adopted storage integration and adopted-building culture influence; CI build + dedicated-server smoke PASS |
| Building Culture | `VillageSavedData.VillageRecord`, `VillageSimulationEvents` | **V5+V14 implemented**: completed construction records weighted village and nearest-district plank/form history; local dominant culture receives ~80% preference, village-wide dominant culture remains the fallback, one-time storage dumps do not redefine culture, and merged former villages retain independent district weights while influencing the shared culture gradually |
| Imperfect Construction | `VillageSimulationEvents` ProjectRecord template generation | **V5 initial plan-time model implemented**: deterministic project variant seed with skill-band cosmetic substitution chances; structural/project validation remains authoritative |
| Carpenter Progression | `VillagerSimData`, `VillageSimulationEvents` | **V5+V15 implemented**: persistent 0-100 skill, Novice/Trained/Skilled/Master template gates, complexity-weighted completion growth, harmless skill-scaled imperfections and Master work-speed bump. Basic survival housing remains available without skill gating |
| Adaptive Plans / Public Works | `VillagePublicWorksService`, `VillageSavedData.PublicRequestRecord`, `VillageSimulationEvents`, `VillageStatusNetworking` | **V9 implemented core**: persistent deduplicated request records derived from real stock deficits, fire state and remaining ProjectRecord material requirements; automatic resolution, immediate refresh after trade/fire/project shortages, priority recomputation and Bell Needs integration; CI build + dedicated-server smoke PASS |
| Refugees / Migration / Village Fission | `VillagePopulationMigrationService`, `VillageSavedData.MigrationRecord`, `VillageSimulationEvents`, `VillageOutpostLifecycleService` | **V6+V10 implemented core**: Viability-driven planned/refugee waves, persistent MigrationRecords, physical loaded-route travel, real travel/founding supplies, Displaced return/permanence, relocation/abandonment hysteresis, sustained-integration merge redirects, and delayed daughter-Village creation only after mature Outpost infrastructure validation; CI build + dedicated-server smoke PASS |
| Villager Breeding Overhaul | `VillagePopulationMigrationService`, `VillageEconomyService` | **V6 implemented**: sustainable-population / Viability / housing / Welfare / food gates, village-wide birth cooldown and recovery-only Recovery Growth path |
| Forest Regeneration | `ForestRegenerationEvents`, `VillageBuildingService` | **V8 integrated**: bounded natural regeneration plus suppression near indexed buildings, active work sites and recognized road corridors; broader player-land-use heuristics remain playtest/tuning work |
| Play Time Limit | `PlayTimeLimitEvents` | Implemented; default OFF |

## Validation gates

- **Compile/build:** GitHub Actions `Minecraft Mods CI`
- **Runtime initialization:** dedicated-server smoke start in the same workflow
- **Gameplay/balance:** still requires in-game playtesting; CI cannot validate feel, tuning or long-duration simulation stability

The implementation label means the accepted behavior has a working MVP code path. It does not mean final art, balance, performance tuning or long-duration world testing is complete.

For enchantment mastery branches specifically, "MVP framework implemented" means mastery storage, branch selection/cycling and some representative effects exist. It does **not** mean every accepted or pending vanilla-enchantment branch in `MOD_IDEAS.md` has a concrete runtime effect yet.


## Village-simulation status note

The village rows above distinguish working implementation from the deeper accepted design in `../MOD_IDEAS.md`. V1-V8 have now replaced the original per-villager/scan-heavy foundation with persistent Village IDs/records, recognized real storage, bounded scheduling, persistent Duties, Welfare, shared ProjectRecords, demographic/migration state, read-only Bell status UI, indexed building use and River Corridor recognition.

Remaining village work is no longer missing foundation architecture. Resource-aware fire response and persistent public-works/adaptive-priority records are now implemented. Remaining work is concentrated in deeper behavior fidelity and content breadth: broader player-built semantic building adoption, Outpost lifecycle polish, richer road cost/upgrade families, additional complex building templates and long-duration balance/playtesting.


## V3 storage / cargo note

V3 replaces the old permanent radius-based arbitrary-container path with recognized `StorageRecord` access. Villages that predate the record system may perform one conservative one-time legacy bootstrap of loaded Chest/Trapped Chest/Barrel blocks inside vanilla-recognized village space; after that, storage access uses persistent recognized positions only.

Loaded recognized containers are authoritative. Each StorageRecord caches its last validated item totals so unloaded storage is remembered rather than treated as empty. Village ledger totals are rebuilt from those cached per-storage values. Manual player edits are caught by periodic low-priority reconciliation of recognized storage only.

Forester, Quarry Worker, Porter, Farmer export and ordinary Carpenter block placement now use persistent physical work cargo rather than harvest/build-time direct item teleport. V5 replaced the legacy immediate road path with RouteRecord/ProjectRecord construction, and V10 additionally prevents loaded-but-distant StorageRecords from being used as remote item teleport sources.


## V4-V5 village note

V4 replaces the provisional UUID-hash / profession-hardwired logistics routing with persistent village Duties and implements the accepted Welfare refusal/price-feedback loop. V5 moves newly planned construction off per-Carpenter BUILD_* ownership into shared persistent ProjectRecords; legacy in-progress BUILD_* state is migrated when encountered. Building projects now survive Carpenter replacement/reload through shared site/template/variant/phase/cursor state, and qualifying Skilled Carpenters can initiate the first two-story template.

Road creation from completed buildings is now represented as persistent RouteRecord + road ProjectRecord work and advances one loaded step at a time rather than mutating an entire route in one completion callback. Building Culture is learned from completed projects and BuildingRecords are lazily revalidated after indexed world edits. The remaining V5 depth items are primarily richer semantic/player-built building adoption, route cost-map/bridge families/width upgrades, and a wider complex-template catalog rather than missing persistence foundations.


## V6-V7 village note

V6 replaces the old per-villager distress migration heuristic with persistent VillageRecord demographic pressure, Settlement Viability and MigrationRecords. Planned migration, emergency refugees, return/permanence, durable abandonment, mature-Outpost daughter settlement founding and conservative multi-day merge evidence now operate on shared settlement state. Regional trade pricing is driven from the real recognized-storage ledger and composes with Welfare pricing rather than spawning synthetic bonus currency.

V7 adds the accepted read-only Bell interface. Sneak+right-click on a recognized Bell requests a compact server-authoritative snapshot and opens Overview / Needs / Projects. While the screen is open it refreshes at most once every 40 ticks; closing it ends refresh traffic. It exposes planner/resource state without worker assignment, price controls or construction-management buttons.


## V8 village/world note

V8 reuses the persistent Building/Route/WorkSite indexes at runtime instead of adding new broad scans. Mob/villager shelter selection now prefers validated BuildingRecords, forest regeneration avoids maintained village space, and route records are indexed across every traversed chunk so road-adjacent ecology checks work away from endpoints.

The optional continental world-generation mode now has deterministic seed/world-coordinate river networks. Macro drainage cells choose lower-potential neighbors, direct tributary inflow widens downstream channels, low basins can form lakes, lowland outlets can widen into deltas, and high-relief sections can form rapids/waterfall steps. No runtime water-current physics is simulated. VillageRiverService only caches low-frequency recognition of long physical water corridors for settlement planning; the water blocks remain authoritative.


## V9 public-works note

V9 replaces transient nearby-player material-request chat with persistent `PublicRequestRecord` state. Daily planning derives shortage records from the recognized physical storage ledger and active ProjectRecord material requirements; fire emergencies can create immediate support needs. Requests are deduplicated by underlying need, update their real remaining amount, and resolve automatically when inventory/project state recovers.

Building ProjectRecords now retain a remaining material summary that is initialized from deterministic template plans, decremented as blocks are physically placed, and lazily reconstructed for projects that predate V9. Bell Needs reads these persistent records directly. Trade deliveries, active fire changes and blocked construction can enqueue immediate refreshes rather than waiting for the next daily pass.


## V10 Outpost lifecycle note

V10 makes Outposts demand-driven remote work infrastructure rather than randomly placed miniature villages. Initial autonomous Outposts are limited to Forestry and Quarry because those purposes already have real physical worker execution. Candidate sites require the corresponding village shortage and actual nearby renewable wood or shallow stone resources; unloaded terrain is never force-loaded to find a site.

An Outpost persists its purpose, lifecycle state, idle history and founding-preparation state. Once its road is active, matching Forester/Quarry workers physically travel along loaded terrain to the site. Local output is buffered in recognized Outpost storage. Porters use a persistent haul phase to move food from parent storage to the Outpost and logs/stone back to parent storage with real ItemStacks; distant loaded containers can no longer be accessed remotely by ordinary village work.

If demand disappears, the route fails or the resource becomes physically depleted, the Outpost moves through active -> inactive -> abandoned over multiple daily evaluations. Assigned workers physically return toward the parent settlement; buildings are not deleted.

Normal fission now separates preparation from settlement identity. A mature operational Outpost can trigger extra lodging construction, but no daughter Village ID is created until the site validates at least 6 housing capacity, recognized local storage, 48 units of local food reserve, an active route and an operational work site. Founding groups and supplies then move through the existing physical MigrationRecord flow.


## V11 fishing-outpost note

Fishing Outposts now use the existing persistent Outpost lifecycle instead of remaining a design-only purpose. Scarce fish stock can select a water-backed remote site; a loaded Fisherman assigned to that active Outpost physically travels there, performs bounded common-fish catches from nearby real water, carries COD/SALMON in persistent worker cargo, deposits into recognized local Outpost storage, and the existing Porter haul phase exports surplus back to parent storage. Resource checks remain loaded-chunk-only and no treasure/rare fishing loot is synthesized.

Farm Outpost execution is implemented in the following V11 note using real irrigation, planting stock and physical cargo.


## V11 farm-outpost note

Farm Outposts now use the same persistent lifecycle and physical-logistics rules as the other remote work sites. Food scarcity can select a remote site only when loaded terrain contains enough usable soil plus real nearby irrigation water. The Outpost work boundary expands around the lodging, but Farmers only modify natural dirt/grass/farmland inside that recognized site.

Planting does not synthesize seeds or water. Porters physically haul Wheat/Beetroot Seeds from recognized parent storage into local Outpost storage; the assigned Farmer physically retrieves a small seed cargo, walks to irrigatable soil, tills it, plants it, and later harvests mature Wheat/Carrots/Potatoes/Beetroot while resetting the same crop. Harvest becomes persistent worker cargo, local storage stock, and then ordinary Porter export. Food-producing Outposts retain their local food reserve before exporting surplus.


## V11 carpenter-trade note

The Carpenter trade ladder now matches the accepted baseline without hard-coding Oak for every wood-family offer. Log purchase, Door sale and Fence sale resolve a stable wood family from the same Building Culture / stocked-material / biome fallback used by village construction; Scaffolding, Cobblestone, Bricks and Lantern offers keep their accepted fixed quantities and prices. The Carpenter Workbench recipe also accepts the normal `minecraft:logs` tag instead of Oak logs only.


## V12 road-maturation note

RouteRecord now persists road quality and width alongside traffic demand. Sustained active Outpost logistics raises the route's bounded traffic score; inactive use decays it. Traffic can schedule low-priority Carpenter public works that widen a route from one to two and eventually three blocks, and mature the surface from Dirt Path to Gravel and then Stone/Cobblestone paving. Every Gravel/Stone/bridge lane block is withdrawn as a real Carpenter cargo item before placement. Existing higher-quality paving and unrelated player/structure blocks are preserved rather than bulldozed.

This pass deliberately keeps the existing endpoint interpolation for route geometry. The remaining road-specific architecture gap is the accepted terrain cost-map / detour planner; it is isolated for the next pass rather than mixing path-search risk into the material/traffic migration.


## V13 terrain-route note

New road geometry is planned through the scheduler's dedicated low-frequency route-search queue. The planner uses a bounded coarse cost map over already-loaded chunks only: existing road surfaces are cheapest, ordinary flat ground is preferred next, gentle/moderate elevation changes cost progressively more, vegetation/awkward terrain costs more again, and water carries a strong crossing penalty. This makes routes bend around expensive terrain when the detour is cheaper while still allowing short crossings when they beat a large detour.

RouteRecord persists only compact direction-change waypoints rather than every physical road block, and the chunk index follows those segments. Carpenter construction and later Gravel/Stone/width upgrades reconstruct the centerline deterministically from the same waypoints. If the full bounded search corridor is not loaded, planning conservatively falls back to the two endpoints; it never requests/generates chunks solely to inspect terrain.


## V14 district-culture note

Building Culture now has a persistent spatial layer keyed to the nearest recognized district center. Completed buildings teach both the village-wide culture and their local district. New construction—and the Carpenter's culture-aware wood-family offers because they use the same selector—prefers the nearest district's dominant plank family about 80% of the time before falling back to the broader village culture, real stock and biome.

When villages merge, a legacy village-wide culture is first seeded into that settlement's original district and existing district weights are transferred without averaging them away. The surviving VillageRecord still blends the old village-wide cultures more slowly, so former settlements can remain visibly different districts while later construction gradually changes both local and shared history.


## V15 template-ladder note

Carpenter template complexity now has a concrete initial ladder rather than one simple hut plus a single Skilled exception. Novices can always build the basic one-story house; Trained Carpenters can choose a higher gabled two-bed house; Skilled Carpenters can lead a four-bed two-story house; Masters in sufficiently populated settlements can lead a six-bed three-story house. The multi-story plans keep explicit stair openings between floors and validate the full intended vertical volume before the project is created.

Construction remains block-by-block with real Carpenter cargo and deterministic plans. Successful completion now awards more Carpentry Skill for more complex template families (while still being bounded), and the resulting gabled/multi-story form is recorded into both village-wide and district Building Culture.


## V16 enchantment-branch note

Branch state now distinguishes **unselected** from explicit branch 0. Mastery 50 therefore unlocks specialization without silently granting the first branch, and the first enchanting-table selection correctly chooses branch 0 before cycling onward. The selection UI currently exposes only branch families with concrete runtime behavior; Mending remains branchless by design.

Fortune now implements Ore Specialist, Harvest Specialist and High Variance as bounded post-vanilla drop adjustments. Ore/Harvest branches use conservative reviewed target families and add at most one extra eligible drop on a mastery-scaled chance. High Variance applies an expected-neutral +/-1 swing only when a qualifying drop stack has at least two items, avoiding negative/zero drops while increasing variance. Existing Efficiency and Feather Falling effects now also require an explicit branch selection.


## V17 respiration-branch note

Respiration now has all three accepted mastery branches. Deep Breath probabilistically preserves air only when vanilla underwater breathing actually consumes air; Quiet Breath applies the stronger preservation only while nearly stationary underwater; Rapid Ventilation observes vanilla breathable-air recovery and adds a mastery-scaled extra refill without exceeding the normal maximum air supply. The implementation stores only the previous air value on the player and performs no broad scans or off-thread work.
