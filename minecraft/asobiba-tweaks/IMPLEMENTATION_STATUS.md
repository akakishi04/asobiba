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
| Enchantment Branches | `EnchantmentTweaksEvents` | **V16+V17 expanded**: explicit branch-selection state plus concrete Efficiency / Feather Falling / Fortune / Respiration / Protection / Projectile Protection / Sharpness / Smite / Bane of Arthropods / Fire Protection / Blast Protection / Fire Aspect / Thorns / Breach / Knockback / Punch branch effects; Mending is excluded from branch selection as designed. Remaining accepted branch families are still pending |
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


## V18 protection-branch note

Protection now implements all three accepted specialization branches at the final post-vanilla damage stage. General Defense removes an additional mastery-scaled 3%-8% of remaining protectable damage. First-Hit Defense arms after about 8 seconds without qualifying damage and removes 10%-25% of the next hit before restarting its timer. Crisis Defense activates below 40% health and ramps toward a mastery-scaled 5%-20% reduction near 10% health. Damage types tagged to bypass enchantments are explicitly excluded so the branch does not protect against domains vanilla enchantment mitigation intentionally bypasses.


## V19 projectile-protection note

Projectile Protection now implements all three accepted branches on post-vanilla projectile damage. Frontal Guard checks the incoming source direction against the player's view and applies its extra reduction only inside the forward ~120-degree arc. Sniper Resistance uses attacker-to-player range as the bounded runtime proxy for projectile travel distance, beginning at 16 blocks and reaching full branch strength at 48+. Barrage Resistance tracks recent qualifying projectile hits in player-persistent state, adds mastery-scaled mitigation for up to three prior hits inside the 3-second chain window, and resets after the accepted quiet period. Damage types that bypass enchantments remain excluded.


## V20 sharpness-branch note

Sharpness now implements all three accepted melee specializations before armor mitigation. Duel tracks only the attacker's current target, last direct-melee hit time and a five-stack bounded streak; consecutive hits within about 3 seconds gain +1%-3% damage per prior stack. Heavy Strike applies +5%-15% only to roughly 95%+ charged direct melee hits. Execute applies +5%-20% only while the struck target is already below 25% maximum health. Projectile/indirect player damage does not trigger these branches.


## V21 smite-branch note

Smite now implements all three accepted undead-only branches using the vanilla SENSITIVE_TO_SMITE entity-type tag. Exorcism converts 15%-35% of the weapon's vanilla Smite bonus into a bounded nearby-undead-only echo on a direct melee kill; a recursion guard prevents the echo from re-triggering weapon branch damage. Holy Strike marks an undead target for roughly 2-4 seconds so its outgoing damage is reduced by 5%-15%, refreshing rather than stacking. Gravebreaker adds 10%-30% of the vanilla Smite bonus again only against substantially armored undead (initial threshold: 10 armor), leaving unarmored targets unchanged.


## V22 bane-branch note

Bane of Arthropods now implements all three accepted branches using the vanilla SENSITIVE_TO_BANE_OF_ARTHROPODS tag. Binding Venom extends the expected Slowness-IV window by a mastery-scaled 25%-100% without creating a stronger amplifier. Swarm Extermination counts at most three additional nearby arthropods and adds 5%-12% of the weapon's ordinary Bane bonus per nearby target. Antivenom grants a short combat grace window after striking an arthropod and reduces only NeoForge-tagged poison damage by 15%-50%; unrelated magic damage is not captured by the branch.


## V23 fire-protection note

Fire Protection now implements all three accepted branches. Rapid Extinguishing detects a new/refreshed ignition and shortens that remaining burn window once by 20%-50%, avoiding exponential per-tick shortening. Heat Adaptation tracks continuous fire/lava exposure, begins after about 2 seconds, reaches its full 5%-15% additional post-vanilla fire-damage reduction after about 6 seconds total exposure, and resets after roughly 3 safe seconds. Lava Adaptation restores 20%-60% of vanilla lava's horizontal movement impairment by converting the normal ~0.5 horizontal drag into an effective ~0.6-0.8 drag; it does not reduce fire damage or grant lava immunity.


## V24 blast-protection note

Blast Protection now implements all three accepted branches. Blast Anchor marks only a qualifying explosion hit and applies one bounded 20%-55% velocity reduction on the next player tick, then clears the marker so ordinary movement is unaffected. Epicenter Resistance adds 5%-20% post-vanilla damage reduction inside roughly 3 blocks and fades linearly to zero at 6 blocks. Chain-Blast Resistance tracks up to three recent qualifying explosions, adds 5%-12% remaining-damage reduction per prior blast within about 4 seconds, and resets after roughly 5 seconds without another explosion.


## V25 fire-aspect note

Fire Aspect now implements all three accepted branches for direct melee hits. Long Burn extends the normal 4-seconds-per-level burn window by 25%-75%. Flash Burn shortens that window to roughly 60% but marks only the resulting on-fire damage window for a 1.2x-1.6x burn-damage multiplier; lava/direct-fire damage is not multiplied. Cauterize marks the target for the expected burn window and reduces healing by 10%-30% only while the target is still burning. Smite Exorcism echo damage is explicitly excluded from re-triggering these weapon branches.


## V26 thorns-branch note

Thorns now implements all three accepted specializations around actual vanilla Thorns events. Retaliatory Spikes multiplies only reflected Thorns damage by 1.15x-1.40x. Entangling Thorns reduces reflected damage to 70% but applies a bounded 1.0-2.5 second slowdown plus a small outward control impulse to the entity that actually received the retaliation. Stored Retaliation accumulates 15%-35% of the wearer's post-mitigation incoming damage, caps at 3-8 damage by mastery, and releases once as Thorns-typed auxiliary damage on the wearer's next successful direct melee hit. Auxiliary retaliation is guarded from recursively triggering weapon mastery branches.


## V27 breach-branch note

Breach now implements all three accepted branches. Heavy Armor Crusher applies a mastery-scaled +5%-15% adjustment to post-vanilla remaining damage only against targets with substantial armor (initial threshold: 10 armor), approximating additional removal of the armor effectiveness left after ordinary Breach. Shield Breaker listens only to successful ShieldBlockEvent instances caused by a direct player hit, stops the active guard and adds a 0.5-1.5 second item cooldown to the shield that actually blocked. Fracture stores an attacker-specific 2-4 second mark on the target; subsequent direct Breach hits by that same attacker gain +5%-15% remaining damage and refresh the mark rather than stacking multiple marks.


## V28 knockback-branch note

Knockback now implements all three accepted direct-melee branches without altering unrelated knockback sources. A qualifying hit writes a two-tick marker to that specific target and the next actual LivingKnockBackEvent consumes it. Launch converts 30%-60% of the normal horizontal knockback strength into an upward impulse instead of adding free total horizontal force. Blowback multiplies normal knockback strength by 1.15x-1.40x. Recoil Step leaves the target's ordinary knockback intact and pushes the attacking player away by 10%-30% of that event's strength. Explosion, mob and environmental knockback never receive these weapon markers.


## V29 punch-branch note

Punch now implements all three accepted projectile-control branches using the weapon ItemStack carried by the projectile DamageSource. A qualifying projectile hit writes a two-tick target marker that is consumed only by the next actual LivingKnockBackEvent. Blowback increases horizontal knockback strength by 15%-40%. Launch converts 30%-60% of that event's horizontal strength into vertical impulse. Pinning Shot cuts ordinary displacement to 25% and replaces it with a bounded 1.0-2.5 second Slowness control effect whose amplifier rises with mastery. Melee Knockback and projectile Punch use separate markers and cannot cross-trigger.
