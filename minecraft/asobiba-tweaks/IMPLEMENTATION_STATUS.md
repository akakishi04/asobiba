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
| Enchantment Branches | `EnchantmentTweaksEvents` | MVP framework implemented; concrete branch effects partial (currently Efficiency / Feather Falling), remaining accepted branch behaviors pending |
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
| Autonomous Village Growth | `VillageSimulationEvents`, `VillageSavedData`, `VillageStorageService` | **V5 project architecture implemented**: new construction is shared persistent ProjectRecord work with phase/cursor persistence, real Carpenter cargo, project concurrency caps, legacy BUILD_* migration and initial two-story house template. Dynamic-boundary/adaptive template expansion still has further tuning work |
| Carpenter Profession | `AsobibaRegistries`, `VillageSimulationEvents`, `VillageDutyScheduler` | **V4/V5 core implemented**: formal Carpenter profession, persistent Duty integration, 8-slot work cargo, shared ProjectRecord execution, 0-100 skill migration/progression and skill-gated two-story template; final trade palette polish remains |
| Village Logistics Roles | `VillageDutyScheduler`, `VillageSimulationEvents`, `VillagerSimData`, `VillageStorageService` | **V4 implemented**: demand-driven persistent Duties, profession affinities, Nitwit exclusion, hold time/staffing caps plus V3 physical cargo paths; additional Outpost/water-logistics specialization remains later work |
| Outposts / Satellite Sites | `VillageSimulationEvents` | MVP implemented; accepted parent-linked lifecycle, lodging/logistics and shutdown behavior pending |
| Roads / Bridges / River Use | `VillageSimulationEvents`, `VillageSavedData.RouteRecord/ProjectRecord`, `VillageRiverService` | **V5+V8 implemented core**: persistent road/bridge projects, real bridge materials, route indexing across traversed chunks and low-frequency physical River Corridor recognition. Full terrain cost-map and road width/upgrade families remain later tuning/features |
| Building Recognition / Occupancy | `VillageSavedData.BuildingRecord`, `VillageBuildingService`, `VillageDirtyEvents`, `MobBuildingUseEvents` | **V5 persistent village-built recognition implemented**: bounds/classification/capacity records plus dirty chunk lazy revalidation from physical beds/storage/interior. Broader player-built semantic adoption remains pending |
| Building Culture | `VillageSavedData.VillageRecord`, `VillageSimulationEvents` | **V5 persistent culture implemented**: completed construction records weighted plank/form history; dominant culture receives ~75% preference and one-time storage dumps no longer instantly redefine culture. District-level culture remains pending |
| Imperfect Construction | `VillageSimulationEvents` ProjectRecord template generation | **V5 initial plan-time model implemented**: deterministic project variant seed with skill-band cosmetic substitution chances; structural/project validation remains authoritative |
| Carpenter Progression | `VillagerSimData`, `VillageSimulationEvents` | **V5 initial 0-100 progression implemented**: legacy XP migration, persistent skill, completion growth, Skilled two-story gating and Master work-speed bump; broader template complexity ladder remains extensible |
| Adaptive Plans / Public Works | `VillagePublicWorksService`, `VillageSavedData.PublicRequestRecord`, `VillageSimulationEvents`, `VillageStatusNetworking` | **V9 implemented core**: persistent deduplicated request records derived from real stock deficits, fire state and remaining ProjectRecord material requirements; automatic resolution, immediate refresh after trade/fire/project shortages, priority recomputation and Bell Needs integration; CI build + dedicated-server smoke PASS |
| Refugees / Migration / Village Fission | `VillagePopulationMigrationService`, `VillageSavedData.MigrationRecord`, `VillageSimulationEvents` | **V6 implemented core**: Viability-driven planned/refugee waves, persistent MigrationRecords, physical loaded-route travel, real travel/founding supplies, Displaced return/permanence, relocation/abandonment hysteresis, mature-Outpost fission and sustained-integration merge redirects; CI build + dedicated-server smoke PASS |
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

Forester, Quarry Worker, Porter, Farmer export and ordinary Carpenter block placement now use persistent physical work cargo rather than harvest/build-time direct item teleport. Current legacy road/bridge placement still consumes materials through its MVP path and is scheduled for replacement by the accepted V5 RouteRecord/public-works construction system.


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
