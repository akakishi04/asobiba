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
| Continental River Networks | planned continental worldgen drainage/river layer | **Planned; accepted spec, not yet implemented** |
| Large Boats / Cargo Rafts | `OceanAndDisplayEvents`, `BoatMixin` | Implemented |
| Ocean Drift Debris | `OceanAndDisplayEvents` | Implemented |
| Nether / Lava Fishing | `NetherFishingEvents` | Implemented |
| Nether Fish | `NetherFishEntity`, `NetherFishingEvents`, renderer/registry | Implemented |
| Mob-Used Buildings | `MobBuildingUseEvents`, village shelter logic | Implemented |
| Villager Welfare / Confinement | planned village-state / villager persistent data | **Planned; accepted spec, not yet implemented** |
| Village Status / Public Needs UI | planned Bell interaction + server status DTO/screen | **Planned; accepted spec, not yet implemented** |
| Village persistent state / indexes / simulation budgets | `VillageSavedData`, `VillagerSimData` | **V1 foundation implemented**: versioned SavedData, stable record APIs, derived chunk index and namespaced per-villager state compile/smoke PASS; spatial Village-ID bootstrap/reconciliation and V2 scheduler/budgets still pending |
| Regional Trade Value | `VillageSimulationEvents` | MVP implemented; accepted inventory-backed scarcity, Welfare and UI integration pending |
| Fire Village Emergency | `VillageSimulationEvents` | MVP implemented; accepted resource-aware multi-role emergency flow pending |
| Autonomous Village Growth | `VillageSimulationEvents` | MVP implemented; accepted dynamic-boundary, real-storage and phased-project architecture pending |
| Carpenter Profession | `AsobibaRegistries`, `VillageSimulationEvents` | Core implemented; accepted final work-cargo, trade/palette and profession-duty integration pending |
| Village Logistics Roles | `VillageSimulationEvents` | MVP implemented; accepted Duty scheduler, staffing rules and persistent cargo pending |
| Outposts / Satellite Sites | `VillageSimulationEvents` | MVP implemented; accepted parent-linked lifecycle, lodging/logistics and shutdown behavior pending |
| Roads / Bridges / River Use | `VillageSimulationEvents` | MVP implemented; accepted demand-driven roads/bridges and River Corridor integration pending |
| Building Recognition / Occupancy | vanilla POI + `MobBuildingUseEvents` heuristics | MVP implemented; accepted persistent functional records/revalidation pending |
| Building Culture | `VillageSimulationEvents` material palette selection | MVP implemented; accepted weighted persistent/district culture pending |
| Imperfect Construction | `VillageSimulationEvents` | MVP implemented; accepted plan-time safe cosmetic-variant model pending |
| Carpenter Progression | `VillageSimulationEvents` | MVP implemented; accepted 0-100 skill, lead-builder and complexity gates pending |
| Adaptive Plans / Public Works | `VillageSimulationEvents` | MVP implemented; accepted priority queue, real request lifecycle and status-UI integration pending |
| Refugees / Migration / Village Fission | `VillageSimulationEvents` | MVP implemented; accepted Viability, refugee return, relocation and merge lifecycle pending |
| Villager Breeding Overhaul | `VillageSimulationEvents` | MVP implemented; accepted sustainable-population model and Recovery Growth pending |
| Forest Regeneration | `ForestRegenerationEvents` | Implemented |
| Play Time Limit | `PlayTimeLimitEvents` | Implemented; default OFF |

## Validation gates

- **Compile/build:** GitHub Actions `Minecraft Mods CI`
- **Runtime initialization:** dedicated-server smoke start in the same workflow
- **Gameplay/balance:** still requires in-game playtesting; CI cannot validate feel, tuning or long-duration simulation stability

The implementation label means the accepted behavior has a working MVP code path. It does not mean final art, balance, performance tuning or long-duration world testing is complete.

For enchantment mastery branches specifically, "MVP framework implemented" means mastery storage, branch selection/cycling and some representative effects exist. It does **not** mean every accepted or pending vanilla-enchantment branch in `MOD_IDEAS.md` has a concrete runtime effect yet.


## Village-simulation status note

The village rows above distinguish the existing runtime MVP from the much more detailed accepted design in `../MOD_IDEAS.md`. In particular, the current `VillageSimulationEvents` implementation still contains provisional profession-based role routing (for example Mason/Fletcher/unemployed/Nitwit branches) and does **not** yet represent the accepted final Duty scheduler. Nitwits are excluded from routine labor in the accepted design.

The accepted final village architecture now also includes persistent Village IDs/records, Active/Cached/Unknown chunk handling, real-container-backed ledgers/reservations, bounded project scheduling, Bell-based read-only status UI, Welfare/Confinement, migration/relocation lifecycle, and event-driven indexed validation. These are implementation backlog items until their concrete code paths and validation gates exist.
