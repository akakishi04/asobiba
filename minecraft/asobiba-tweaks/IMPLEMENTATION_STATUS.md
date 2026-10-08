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
| Enchantment Branches | `EnchantmentTweaksEvents`, `ChannelingMasteryEvents`, `InfinityMasteryEvents`, `PowerMasteryEvents` | **V16-V54 expanded**: explicit mastery branch selection and concrete effects for Efficiency / Feather Falling / Fortune / Respiration / Protection / Projectile Protection / Sharpness / Smite / Bane / Fire Protection / Blast Protection / Fire Aspect / Thorns / Breach / Knockback / Punch / Impaling / Flame / Depth Strider / Aqua Affinity / Looting / Soul Speed / Swift Sneak / Riptide / Channeling / Unbreaking / Infinity / Quick Charge. Mending intentionally has no selectable branch. Other accepted enchantment families and enchanted-ammo integration remain pending |
| Curse Growth | `EnchantmentTweaksEvents` | Implemented |
| Fortune / Silk Touch Switching | `EnchantmentTweaksEvents` | Implemented |
| Mastery Inheritance | `EnchantmentTweaksEvents` | Implemented |
| Uncapped Anvil XP Cost | `AnvilMenuMixin` | Implemented |
| Direct Enchanting-Table Reroll | `EnchantmentMenuExtensionsMixin`, `EnchantingScreenEvents` | Implemented; XP cost |
| Enchantment-Pool Bookshelves | Arcane Bookshelf + `EnchantmentMenuExtensionsMixin` | Implemented |
| Extended Enchanting Targets | `ExtendedEnchantableItemMixin`, `ArrowEnchantmentEligibilityMixin`, `ArrowTableCompatibilityMixin`, `ArrowAnvilCompatibilityMixin`, `EnchantmentExtensionMixin`, `EnchantedWorkBlockSavedData` | **V52-V53**: only the 13 accepted vanilla effects are eligible on arrows through NeoForge item primary/supported hooks; extended block enchanting unchanged; runtime tests pending |
| Arrow-side Looting | `ArrowLootingSupport`, vanilla Looting count/chance mixins | **V51 added**: real loot-table count/rare-roll Looting checks use max(launcher/equipped, arrow), never additive or post-death item duplication; gameplay verification pending |
| Raised Enchantment Level Caps | `EnchantmentExtensionMixin` | Implemented; configurable cap; explicit higher-level Mending enabled in V40 |
| High-level Mending and Over-Repair | `MendingExtendedEvents`, `ExperienceOrbMendingMixin` | **V41 implemented initial transaction**: IV-IX equipped distribution, X inventory routing, per-level efficiency loss, 5%-20% mastery durability reserve and UI tooltip; in-game tests required |
| Frost Walker runtime toggle | `FrostWalkerToggle`, `FrostWalkerLocationMixin`, client gesture + network payload | **V39 implemented**: sneak+jump toggles the boots' stored ON/OFF state; disabled mode suppresses new ice creation, preserving enchantment and damage protection |
| Shared Bow / Crossbow Enchantment Pool | additive `minecraft:enchantable/bow` and `minecraft:enchantable/crossbow` tags, `LauncherEnchantmentCompatibilityMixin` | **V37-V38 implemented core**: shared launcher eligibility and Infinity + Mending compatibility, plus Bow Quick Charge's diminishing draw-time reduction up to X. Other cross-launcher projectile effects still require in-game validation |
| Atlas / Map Binder | `AtlasItem`, `AtlasItemInHandRendererMixin` | Implemented |
| Potion Mixing | `AlchemyExplosivesCraftingEvents` | Implemented |
| TNT Design | `AlchemyExplosivesCraftingEvents`, `TntDesignSavedData`, `PrimedTntMixin` | Implemented |
| Fletching Table Expansion | `AlchemyExplosivesCraftingEvents`, `EnchantedArrowCopyService` | **V42 added**: enchanted-arrow source-template copying with precise enchantment anvil-weighted XP points, quantity selected by offhand stack size, preserved source and compatible same-type material |
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


## V30 impaling-branch note

Impaling now implements all three accepted specializations for both direct and weapon-attributed projectile hits. Wet Hunt grants wet non-Impaling-sensitive targets 50%-100% of the weapon's ordinary 2.5-damage-per-level Impaling bonus while leaving dry non-aquatic targets unchanged. Harpoon writes a two-tick target marker and reverses only the next actual knockback vector into a 0.15-0.45 pull toward the source path. Deep Hunter adds 10%-30% of the ordinary Impaling bonus when the attacker is fully underwater at least eight water blocks below the local surface and the target is normally Impaling-sensitive. The depth check is a bounded same-column 32-block scan.


## V31 flame-branch note

Flame now implements both accepted specialization branches; the intentionally-open third slot is not exposed by branch cycling. Long Burn extends the projectile's ordinary fire window by 25%-75% without shortening a stronger pre-existing burn. Stacked Ignition requires the target to already be burning, adds roughly 1.0-2.5 seconds per qualifying Flame hit, and caps the branch-added window at roughly 3-8 seconds beyond the normal five-second Flame reference. The branch acts only on projectile hits whose DamageSource carries the enchanted launcher ItemStack.


## V32 depth-strider note

Depth Strider now implements all three accepted movement branches with bounded post-tick velocity adjustments. Current Rider reads the real local FluidState flow vector and increases only the portion of horizontal motion already aligned with that current by 10%-30%, with a 0.40 horizontal-speed safety cap. Seabed Runner applies a 10%-25% grounded-underwater horizontal boost capped at 0.35. Diver increases existing vertical underwater movement authority by 10%-35% while clamping vertical speed to +/-0.35; it does not create vertical motion from rest. These caps prevent multiplicative per-tick runaway while preserving the intended specialization.


## V33 channeling-branch note

`ChannelingMasteryEvents` implements the three accepted Channeling mastery specializations for **player-thrown Tridents**, while preserving vanilla Channeling's one-level maximum and full thunderstorm strike. It does not infer arrow-ammo enchantments from a Bow/Crossbow weapon stack; enchanted-arrow Channeling belongs to the later arrow-projectile integration.

- **Chain Lightning** (branch 0): normal qualifying thunderstorm/open-sky trident impact adds 1/2/3 non-recursive secondary target strikes at mastery 50/75/100 within a 4->6 block range. Each secondary hit uses 35%->50% of the standard 5-damage lightning reference, with cosmetic bolt visuals and separate bounded damage.
- **Rain Channeling** (branch 1): in ordinary rain (not a thunderstorm), with open sky, one impact has a mastery-scaled 15%->50% chance to make a cosmetic lightning strike plus 50% of reference lightning damage on an entity hit; other weather conditions retain vanilla behavior.
- **Conductor** (branch 2): normal thunderstorm impacts search a bounded 4->8-block area and prefer valid open-sky Lightning Rod blocks ahead of supported Copper block families. A selected rod receives a separate zero-damage physical bolt for redstone interaction; selected Copper receives only a cosmetic secondary arc. This initial supplemental-conductor path does **not** suppress or relocate vanilla's ordinary impact strike, and therefore is not yet a true single-strike redirect.
- Once a thrown Trident processes a qualifying mastery impact, it records a projectile-local deduplication marker. Channeling's extra bolts do not recursively activate this handler. Candidate checks require already-loaded chunks.
- **Validation:** GitHub Actions Minecraft Mods CI run `37732270864`: Gradle Build PASS, Dedicated Server smoke PASS for code commit `92a6b412994c102da46895c1fbc70fedd23f8b81`. In-game verification remains needed for thunderstorm/open-sky block hits, secondary-hit damage, ordinary-rain probability, redstone/lightning-rod behavior, cancellation/inter-mod event ordering, and client rendering/audio.


## V34 Unbreaking mastery-branch note

Unbreaking's three accepted durability specializations are implemented with a
post-vanilla ItemStack durability hook. The hook receives the result of ordinary
Unbreaking processing and only subtracts additional durability loss; it never
refunds damage after an item has already broken or creates a new item.

- **Rested Reserve** (branch 0) stores 1-3 charges on the exact ItemStack.
  Consecutive idle intervals of 20s at mastery 50 down to 10s at mastery 100
  recharge that reserve. Each charge saves one actual post-vanilla durability
  point. First use starts the idle clock, without an instant free reserve.
- **Continuous Operation** (branch 1) builds over ten qualifying uses, giving
  an additional 5%-15% durability-loss negation at full streak. A 3s inactivity
  gap resets the streak. Main-hand and offhand swaps also reset it on the
  server, preventing indefinite streak preservation when the item is put away.
- **Protective Mode** (branch 2) activates under 15%-25% remaining durability,
  then negates an additional 30%-60% of post-vanilla loss. The trade-off is
  roughly 10% reduced mining speed and attack/projectile damage for active
  held items, or 10% increased post-mitigation damage taken when any actively
  protective armor piece is worn. The armor penalty applies at most once.
- Branch runtime information persists on the ItemStack alongside mastery
  data. Vanilla armor/item durability resolution is preserved, and all
  three branches require an explicit enchanting-table choice at mastery 50.
- Gameplay tests still needed: combat, armor damage, unusual durability costs,
  swap/reset, item break at one remaining durability, save/reload and inter-mod
  durability hook ordering.


## V35 Infinity mastery-branch note

Infinity now supports the accepted three explicit level-50 mastery choices.
Pure Infinity provides a normal, unenchanted, non-recoverable seed Arrow only
when no projectile source exists. Vanilla ammo-use and creative/intangible
rules still determine whether that ordinary arrow is consumed.

Rapid Infinity tracks actual shot groups (not Multishot projectile instances)
on the server. A streak of three ordinary-arrow shots within four seconds
gives a mastery-scaled 10%-35% chance to avoid that group's durability cost.
Other ammunition does not increase this streak.

Precision Infinity applies a mastery-scaled 15%-50% durability-avoidance
chance to a fully drawn Bow shot (velocity >= 2.85) or an ordinary fully
charged Crossbow shot. The same per-group roll applies to the durability
points spent in that group. Ordinary low-charge bow shots receive no bonus.

The durability effect composes after vanilla Unbreaking and the V34 mastery
hook. Runtime streak/shot markers are weak, server-only references rather
than new permanent NBT, so cooldowns reset naturally on world reload.

Remaining: actual Quiver ammo selection/consumption integration, common
launcher enchantment acquisition/compatibility, enchanted arrow effects,
in-game shot pickup/Multishot/creative verification.


## V36 Quiver physical ammunition integration

Selected Quiver ammunition now takes priority at Bow/Crossbow ammo resolution;
an incompatible or empty selected slot falls back to vanilla offhand/inventory.
The projectile receives a transient copy of the exact ammunition, tracked on
the server by an identity-based pending source reference. At completion of
vanilla ProjectileWeaponItem.useAmmo, only the actual consumed count is
committed to the original Quiver slot, and only if that slot still holds the
same ItemStack components. Multishot secondary projectile copies have no
Quiver source token; Crossbows commit consumption when charged, not again
on firing. Unspent ordinary Infinity ammunition is retained.

Vanilla Infinity's Items.ARROW predicate includes custom enchanted ordinary
Arrow stacks. The ammo-use result is now forced back to one consumed item
for enchanted/customized Arrow ammo (excluding creative/Multishot secondary).
Only the untouched ordinary Arrow remains free under base Infinity.

New server-to-client snapshot payload syncs Quiver contents/selection after
all server changes and during login/respawn/dimension transitions. The HUD
can now display server-authoritative ammunition while the inventory is closed.

In-game item-conservation, reload, Multishot, server/client and inter-mod
compatibility playtests remain required.


## V37 shared Bow/Crossbow enchantment-pool note

The vanilla minecraft:enchantable/bow item tag now additionally contains
Crossbows, and minecraft:enchantable/crossbow additionally contains Bows.
These are additive entries (replace: false), retaining vanilla members and
third-party contributions. They make the accepted launcher candidate pool
available through standard enchanting/book/anvil acquisition without
copying all the enchantment definitions.

A narrowly scoped Enchantment.areCompatible mixin permits Infinity + Mending,
in both pair orders, while preserving every other vanilla compatibility
decision (notably Multishot vs Piercing). This compatibility function is
item-agnostic upstream, so it is necessarily a rule on the enchantment pair;
the normal supported-item tags still determine legal targets.

V37 specifically addresses eligibility and compatibility, not every
launcher-specific behavior. Bow Quick Charge reduction still needs a Bow
draw-duration implementation. Crossbow Power/Punch/Flame and Bow Multishot/
Piercing need in-game confirmation that their projectile effects are applied
as intended. Bow and Crossbow firework handling remains launcher-specific.


## V38 Bow Quick Charge draw-speed note

Quick Charge on an enchanted Bow now modifies the vanilla power-for-time
calculation when releasing a shot, rather than changing base arrow damage.
Levels I-V reduce the virtual full-draw time by 8% each, VI-X by 4% each.
The draw-speed reduction is capped at 60% (full power after 40% of the
ordinary 20-tick draw at Quick Charge X).

The effect is applied on both logical sides by the same BowItem mixin.
A normal or unenchanted Bow retains vanilla power/charge timing, and
Crossbow timing stays on its separate vanilla Quick Charge path.
The native arrow-loose hook retains its ability to deny an attack.

Gameplay follow-up: confirm client hand/draw animation agrees with
actual charge/crit timing; integrate the faster charge into its display
if needed. Verify full-power thresholds and other mods' ArrowLoose hooks.


## V39 Frost Walker persistent runtime toggle

Holding sneak and pressing jump sends a one-shot client-to-server toggle
request. The server checks for Frost Walker on the equipped boots, updates
those boots' CUSTOM_DATA and displays an ON/OFF action-bar message. Held
jump does not retrigger; closing an inventory with jump held does not
produce a new rising edge.

The world-side Enchantment.applyLocationBasedEffects hook suppresses the
Frost Walker location-change pass only when the boots' item-local state
is OFF. It does not remove/rewrite the enchantment or suppress unrelated
enchantment effects such as Frost Walker's magma damage protection.
Absence of the tag on legacy boots means ON.

The state follows the boots across normal equip/unequip, save/reload, and
ItemStack transfer. Frozen ice placed before turning OFF melts normally.
Dedicated-server startup and real multiplayer client input need testing.


## V40 Mending II-X level-cap and direct repair note

Mending is now the explicitly approved exception to the single-level cap.
Mending's canonical translatable-description key is checked to avoid
extending unrelated one-level enchantments; the configured general raised
enchantment cap controls its maximum acquisition level.

Normal Mending I remains vanilla 2 durability per XP. Mending II adds one
more point per XP; III through X add two more, with a fixed 4 durability
per XP ceiling. The repair-rate hook composes after the base enchantment
calculation rather than replacing all other repair sources.

Important remaining Mending work: Mending IV-IX active-equipped linked
XP distribution; Mending X full-inventory linked targets; 40%-80%
transfer-efficiency/recipient-multiplier curves; mastery 50-100
over-repair buffer and its priority-before-durability behavior.


## V41 Mending linked XP routing and over-repair

An equipped/held Mending IV-X item acts as the router. The highest-level router wins, with durability wear breaking level ties. IV-IX only route to equipment and hands. X additionally routes to Mending items inside the player inventory. Carrying an X item without equipping it never activates routing.

Recipients need Mending themselves. Damaged items are prioritized over buffer filling, then by damaged percentage and Mending level. Cross-item XP reaches recipients at 40%-80% source efficiency times the accepted 50%-100% recipient-level multiplier, while the router's own repair is direct. Fractional durability credits are kept in the recipient ItemStack.

From mastery 50, Mending over-repair increases 5%-20% of normal durability. The buffer persists in CUSTOM_DATA and is consumed first during the normal hurtAndBreak durability path, after base Unbreaking and mastery rolls. XP not used on any eligible damage or buffer is returned to the player through the normal experience-orb flow.

Gameplay validation remains for mixed levels, transfer math, inventory X, orb sizes, durability loss, save/reload, and interactions with other mods.


## V42 enchanted-arrow copying at the Fletching Table

Holding an enchanted Arrow, Spectral Arrow or Tipped Arrow in the main hand
and ordinary same-kind arrow materials in the offhand activates copying
when right-clicking a Fletching Table. The offhand stack count (1-64) is
the chosen batch size; split the offhand stack in the inventory to set
an exact quantity. Tipped Arrows must carry identical potion contents.

Per-arrow XP = sum of each enchantment level times that enchantment's
runtime anvil cost. Total XP = per-arrow XP times batch size, without
bulk discounts or surcharges. Player experience is checked as actual
spendable XP points, not the misleading lifetime totalExperience counter.
The material stack and XP are debited before emitting copied ItemStacks.
The original enchanted source is unchanged and can be reused. Output
inherits the exact source ItemStack components and is split according to
the resulting stack's maximum size. Full inventory drops overflow locally.

This reuses the existing Fletching Table interaction path, without
opening an extra GUI or changing the vanilla block entity structure.
Remaining UX work: dedicated batch-quantity picker/preview GUI and
live XP preview. In-game tests still needed for creative, custom
potion arrows, overlapping inventories, XP event handlers and full
inventory overflow.


## V43 enchanted projectile combat core

Normal, Spectral and Tipped Arrow projectiles now inspect the exact ammo ItemStack already retained by vanilla AbstractArrow. Supported initial arrow-side combat effects are Sharpness damage, Smite vs undead, Bane of Arthropods vs tagged arthropods plus vanilla-style slow, Impaling vs vanilla-sensitive aquatic targets, Flame ignition and Piercing hit count. All target-condition bonuses are evaluated per successful projectile hit, including later Piercing hits, without adding launcher-side levels to ammo-side levels. The added Piercing level is max(launcher, ammo), not their sum. No secondary ammo ItemStacks are generated by this handler.

Still pending: arrow Power drag preservation; Punch and Breach; Wind Burst and Channeling impact effects; arrow-side Looting and Loyalty; embedded recoverable arrow return; full in-game compatibility tests.


## V44 arrow flight Power and impact environment effects

Power on ammunition now compensates normal air-flight velocity decay by 8% per level (up to 80% at X); water/lava drag is unchanged and gravity is preserved separately. The projectile never gains net air acceleration from this correction. Wind Burst impacts generate a bounded radial impulse for loaded nearby entities and items with radius 2.5..4.75 blocks and strength 1.0..1.9 across levels I-X. Arrow Channeling triggers an ordinary physical lightning strike for open-sky impacts during thunderstorms, including valid block hits. These effects are resolved for each Piercing impact without an artificial per-projectile trigger cap.

Remaining arrow systems: Punch, Breach, Looting and Loyalty; arrow recovery/embedded-arrow death drops; exact inter-mod/creature interaction tests.


## V45 ammo Punch and Breach damage reduction

Ammo-side Breach is now installed as an ARMOR reduction modifier during LivingIncomingDamageEvent. The target's real armor mitigation is scaled by max(0,1-0.15*level), capped at 100% at VII. If the launcher also has Breach, the callback uses the ratio between the stronger ammo-side fraction and the launcher-side fraction, preventing same-effect multiplication or level addition.

Ammo-side Punch is applied only after a positive, successful LivingDamageEvent.Post. The arrow's real horizontal flight direction and target knockback resistance determine an additional impulse only when arrow-side Punch exceeds launcher Punch. Its level shape is I=1, II=2, III=2.5, V=3.5, X=6. Vanilla launchers continue their own knockback resolution without replacing it.

Both effects are reevaluated for each successfully pierced target; in-game comparison with enhanced launchers remains necessary.


## V46 embedded-arrow death recovery

Non-piercing, normally pickup-allowed Arrow/Spectral Arrow/Tipped Arrow
projectiles are recorded only after a positive successful living-target
damage event. Each arrow can be recorded at most once and each victim
holds a bounded maximum of 48 physical embedded-arrow records. The exact
source ItemStack, including enchantments and potion components, persists
on the victim through save/reload and drops when that target dies.

Secondary Multishot projectiles and Infinity/creative nonrecoverable
projectiles are excluded through vanilla pickup authorization. Piercing
arrows are excluded while continuing in flight, preventing multi-target
duplication. V48 Loyalty projectiles are explicitly excluded from victim death-drop storage to prevent double recovery.

Drop records are removed once after emitting the actual ItemEntity
instances, preventing repeated death-drop callback duplication. Manual
game tests should cover non-lethal hit then death, lethal hit, unloaded
targets, modded pickups and multiple simultaneous arrows.


## V47 Power mastery branches

Power now exposes three explicit level-50 mastery specializations. Sniping uses the projectile's recorded launch origin and gives a distance-scaled +5%-20% damage bonus ramping across 16..48 blocks. Heavy Draw provides +5%-15% damage on genuine full-charge Bow shots or fully loaded Crossbow shots. Quick Shot offsets 15%-45% of a Bow's partial-draw damage penalty without allowing tap-fire to equal a full-charge arrow. Each arrow records its launch velocity exactly once on EntityJoinLevelEvent. Damage is evaluated per target, so piercing targets get appropriate effects individually. Launcher Power mastery is distinct from arrow-side Power drag preservation.

Gameplay tests still required for custom-arrow launch velocity and client/other-mod event composition.


## V48 enchanted-arrow Loyalty return (initial integration)

Arrow-side Loyalty on a normally recoverable primary projectile now returns one exact arrow ItemStack toward the original player. For a non-piercing, successful living hit, vanilla removes the projectile, so a single non-colliding return projectile replaces it after damage. For Piercing arrows, ordinary multi-hit flight continues until the projectile embeds or genuinely becomes stationary. Any Loyalty arrow is excluded from V46 embedded death-drop recovery.

After normal flight termination, return delay is max(1,11-level) ticks and homing movement scales 1.0x at I to 2.35x at X. Return storage prioritizes an original Quiver slot when confirmed, then another compatible Quiver slot, normal inventory and an item drop at the player if full. The confirmed source-slot token persists with a fired Bow/Crossbow arrow (including charged Crossbows), and is stripped from the ItemStack when delivered. Returning clones are never pickable and are delivered only once. Owner logout, dimension separation, or unloaded path chunks suspend homing without force-loading any world chunks.

Remaining edge tests: Piercing projectiles removed by exhausted penetration count without block impact; long-distance suspended return on unloaded chunks; full-inventory and crossbow reload transactions; projectile event ordering with other mods.


## V49 Loyalty mastery return specializations

Returned Loyalty ammunition now receives one item-local mastery point per completed return, permitting specialization at mastery 50. Explicit enchanting-table branch selection enables: Fast Return (+15%-50% homing speed), Safe Return (25%-75% stronger steering and a loaded-only 4..12 block terrain-detour probe), and Pursuing Return (when the owner moves away, +20%-60% steering acceleration and capped +10%-30% return speed). Normal returns now use bounded momentum correction, making these sidegrades distinct from a purely instantaneous direction change. Already-loaded collision-shape checks are bounded by a maximum of 12 sample blocks, with at most two local offset probes; no force-loads or chunk tickets are issued. Absence of a selected branch retains ordinary Loyalty behavior.

Real-world multiplayer and large-distance return testing remains required, especially where a chunk on the return path is unloaded.


## V50 Piercing exhaustion and Loyalty terminal recovery

The arrow now persists a bounded count of successful living-target Piercing damage events. Reaching the entity penetration budget does not itself begin Loyalty homing. On the next entity collision, where vanilla would otherwise discard the exhausted Piercing projectile without another valid hit, the pre-impact handler cancels only that terminal collision and transitions the SAME projectile into a non-pickup Loyalty return. This avoids creating a second item or returning prematurely. Collision handling runs at high event priority so invalid extra hits do not trigger impact-only enchant effects.

Remaining corner case: armor stands and nonliving entities can consume vanilla piercing-hit slots without producing LivingDamageEvent.Post; exact nonliving hit accounting needs an additional authoritative pierce-set hook before it can be considered fully covered. Target-block terminal flight and multi-hit living targets are handled by the current paths.


## V51 real loot-table Arrow Looting

Two precise loot-table interceptors augment the attacker-equipment Looting level when the death DamageSource's direct entity is an AbstractArrow and the attacking entity is that physical arrow's owner. Both the enchanted count-increase function and the random-chance-with-enchanted-bonus condition use the higher of the vanilla equipped/launcher level and the source ammo level. Non-Looting enchantments in those same generic loot functions are unchanged. The vanilla roll, cap, rarity, loot conditions and mob drop table remain authoritative. The subsystem creates zero independent drop Items, so it cannot accidentally double-roll drops after a death event. Disabling extended enchanting targets restores vanilla behavior.

Remaining: in-game loot-table execution tests (including Bow/Crossbow, large Looting levels, spectral/tipped ammo, mob equipment drops and modded loot tables). No runtime claim is made until real shots are tested.


## V52 exact Arrow-enchantment candidate pool

Normal/Spectral/Tipped Arrow enchanting now accepts only the 13 specific vanilla effects in MOD_IDEAS.md. NeoForge's ArrowItem primary/supported methods are overridden to allow those candidates through both the Enchanting Table and the Anvil, rather than relying solely on the deprecated Enchantment.isPrimaryItem hook. The older direct Enchantment compatibility checks enforce the same 13-name whitelist, not a blanket yes on every arrow. Extended work-block enchantments are unchanged. Disabling EXTENDED_ENCHANTING_TARGETS restores the vanilla supported-item rules. Arrow-local mutual-exclusion overrides are still a separate implementation and do not become global rules for swords or launchers.


## V53 arrow-local mutually compatible enchantments

The two stack-aware vanilla acquisition paths now allow any two DIFFERENT approved arrow enchantments to coexist on one Arrow/Spectral Arrow/Tipped Arrow item. During EnchantmentHelper.selectEnchantment, only conflicting candidate filtering is bypassed for supported pairs on an arrow; normal weighted selection and chance remain untouched. When an AnvilMenu combines an arrow and an enchanted book, only the compatibility check is bypassed for approved arrow pairs; the required XP and material handling remain vanilla plus the existing anvil cost extension. Non-arrow items retain all normal enchantment exclusivity. Identical enchantment candidates are not duplicated within the same table roll.

Remaining gameplay tests: high-count co-enchantment rolls, recipe/anvil level persistence, projectile behavior with combined enchantments, and interactions with third-party enchantment-mod compatibility rules.


## V54 Quick Charge mastery specializations

Crossbow Quick Charge now offers First Load, Reload Rhythm, and Mobile Reload at mastery 50. First Load shortens a reload by 10%-30% when no shot has been fired for at least 60 ticks. Reload Rhythm tracks up to three releases within successive 60-tick windows and shaves 5%-10% charge duration per stack, capped at 15%-30%; inactivity resets the streak. Mobile Reload partially compensates movement slowdown while charging, with bounded server-authoritative horizontal motion adjustments only while grounded and below sprint velocity. Shot timestamps and streak are stored on the weapon stack; all duration modifications apply after vanilla Quick Charge level scaling and do not affect ammo consumption.
