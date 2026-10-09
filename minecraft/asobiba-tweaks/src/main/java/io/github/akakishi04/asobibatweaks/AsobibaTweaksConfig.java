package io.github.akakishi04.asobibatweaks;

import net.neoforged.neoforge.common.ModConfigSpec;

public final class AsobibaTweaksConfig {
    private static final ModConfigSpec.Builder BUILDER = new ModConfigSpec.Builder();

    public static final ModConfigSpec.BooleanValue GROWING_ITEMS_ENABLED = bool("growingItems.enabled", true, "Enable per-item growth XP and levels for damageable items.");
    public static final ModConfigSpec.IntValue GROWING_ITEMS_MAX_LEVEL = BUILDER.defineInRange("growingItems.maxLevel", 10, 1, 100);
    public static final ModConfigSpec.IntValue GROWING_ITEMS_BASE_XP = BUILDER.defineInRange("growingItems.baseXp", 20, 1, 100000);
    public static final ModConfigSpec.DoubleValue GROWING_ITEMS_REPAIR_CHANCE_PER_LEVEL = BUILDER.defineInRange("growingItems.repairChancePerLevel", 0.02D, 0.0D, 1.0D);
    public static final ModConfigSpec.DoubleValue GROWING_ITEMS_MINING_TIER_UPGRADE_CHANCE = BUILDER.defineInRange("growingItems.miningTierUpgradeChance", 0.12D, 0.0D, 1.0D);
    public static final ModConfigSpec.IntValue GROWING_ITEMS_MAX_MINING_TIER_BONUS = BUILDER.defineInRange("growingItems.maxMiningTierBonus", 2, 0, 4);

    public static final ModConfigSpec.BooleanValue DAILY_FAVOR_ENABLED = bool("dailyFavor.enabled", true, "Enable one small deterministic activity bonus per Minecraft day.");
    public static final ModConfigSpec.DoubleValue DAILY_FAVOR_REWARD_CHANCE = BUILDER.defineInRange("dailyFavor.rewardChance", 0.25D, 0.0D, 1.0D);
    public static final ModConfigSpec.IntValue DAILY_FAVOR_XP = BUILDER.defineInRange("dailyFavor.rewardXp", 1, 0, 100);

    public static final ModConfigSpec.BooleanValue UNIVERSAL_BOND_ENABLED = bool("universalBond.enabled", true, "Allow any Mob to build bond with a player.");
    public static final ModConfigSpec.IntValue UNIVERSAL_BOND_PER_GIFT = BUILDER.defineInRange("universalBond.bondPerGift", 25, 1, 100);
    public static final ModConfigSpec.BooleanValue UNIVERSAL_BOND_FOLLOW = bool("universalBond.followOwner", true, "Allow bonded pathfinding mobs in Follow mode to navigate toward their owner.");
    public static final ModConfigSpec.BooleanValue UNIVERSAL_BOND_FRIENDLY_FIRE = bool("universalBond.friendlyFire", false, "Allow owner and bonded mob to damage each other.");
    public static final ModConfigSpec.BooleanValue UNIVERSAL_BOND_ALLOW_BOSSES = bool("universalBond.allowBosses", false, "Allow Ender Dragon and Wither to participate in Universal Bond.");

    public static final ModConfigSpec.BooleanValue PLAY_TIME_LIMIT_ENABLED = bool("playTimeLimit.enabled", false, "Enable a per-login-session play time limit.");
    public static final ModConfigSpec.IntValue PLAY_TIME_LIMIT_MINUTES = BUILDER.defineInRange("playTimeLimit.limitMinutes", 120, 1, 10080);
    public static final ModConfigSpec.IntValue PLAY_TIME_WARNING_MINUTES = BUILDER.defineInRange("playTimeLimit.warningMinutes", 10, 0, 1440);
    public static final ModConfigSpec.ConfigValue<String> PLAY_TIME_LIMIT_MODE = BUILDER.define("playTimeLimit.mode", "WARN_ONLY", value ->
            value instanceof String s && (s.equalsIgnoreCase("WARN_ONLY") || s.equalsIgnoreCase("DISCONNECT")));

    public static final ModConfigSpec.BooleanValue WORLD_FOLKLORE_ENABLED = bool("worldFolklore.enabled", true, "Enable seed-specific hidden folklore rules and tiny ritual responses.");
    public static final ModConfigSpec.BooleanValue LUNAR_OFFERING_ENABLED = bool("worldFolklore.lunarOffering", true, "Enable full-moon item offerings and delayed returns.");

    public static final ModConfigSpec.BooleanValue WALL_KICK_ENABLED = bool("movement.wallKick", true, "Enable lightweight wall kicks.");
    public static final ModConfigSpec.BooleanValue SLIDING_ENABLED = bool("movement.sliding", true, "Enable sprint-crouch sliding.");
    public static final ModConfigSpec.BooleanValue LEDGE_CLIMB_ENABLED = bool("movement.ledgeClimb", true, "Enable short automatic ledge climbs.");
    public static final ModConfigSpec.BooleanValue FIELD_REPAIR_ENABLED = bool("interaction.fieldRepair", true, "Enable inefficient field repairs with matching material.");
    public static final ModConfigSpec.BooleanValue WEAPON_THROWING_ENABLED = bool("interaction.weaponThrowing", true, "Enable throwing swords and axes.");
    public static final ModConfigSpec.BooleanValue TORCH_THROWING_ENABLED = bool("interaction.torchThrowing", true, "Enable throwing torches to place them.");
    public static final ModConfigSpec.BooleanValue CARRY_SMALL_MOBS_ENABLED = bool("interaction.carrySmallMobs", true, "Enable carrying small mobs.");
    public static final ModConfigSpec.BooleanValue EXPANDED_FISHING_ROD_ENABLED = bool("interaction.expandedFishingRod", true, "Allow fishing rods to pull nearby dropped items.");
    public static final ModConfigSpec.BooleanValue EXTINGUISH_CREEPERS_ENABLED = bool("interaction.extinguishCreepers", true, "Allow water bottles to interrupt primed creepers.");
    public static final ModConfigSpec.BooleanValue ENDER_PEARL_ANCHOR_ENABLED = bool("interaction.enderPearlAnchor", true, "Enable temporary ender-pearl return points.");
    public static final ModConfigSpec.IntValue ENDER_PEARL_ANCHOR_MINUTES = BUILDER.defineInRange("interaction.enderPearlAnchorMinutes", 10, 1, 120);
    public static final ModConfigSpec.BooleanValue FIREWORK_PROPULSION_ENABLED = bool("interaction.fireworkPropulsion", true, "Allow fireworks to propel selected entities.");

    public static final ModConfigSpec.BooleanValue ARMOR_STAND_SWAP_ENABLED = bool("vanilla.armorStandLoadoutSwap", true, "Enable whole-armor loadout swapping with armor stands.");
    public static final ModConfigSpec.BooleanValue LINKED_DOUBLE_DOORS_ENABLED = bool("vanilla.linkedDoubleDoors", true, "Open matching adjacent double doors together.");
    public static final ModConfigSpec.BooleanValue ENDERMAN_MICRO_BUILD_ENABLED = bool("oddities.endermanMicroBuilding", true, "Allow extremely rare tiny Enderman block arrangements.");
    public static final ModConfigSpec.BooleanValue PARROT_PERCHES_ENABLED = bool("vanilla.parrotPerches", true, "Allow parrots to perch on narrow vanilla blocks.");
    public static final ModConfigSpec.BooleanValue MOB_GATHERINGS_ENABLED = bool("oddities.mobGatherings", true, "Enable rare unexplained same-species mob gatherings.");
    public static final ModConfigSpec.DoubleValue MOB_GATHERING_CHANCE = BUILDER.defineInRange("oddities.mobGatheringChancePerCheck", 0.002D, 0.0D, 1.0D);
    public static final ModConfigSpec.BooleanValue ARMOR_STAND_POSE_DRIFT_ENABLED = bool("oddities.armorStandPoseDrift", true, "Allow very rare subtle armor-stand pose changes.");
    public static final ModConfigSpec.DoubleValue ARMOR_STAND_POSE_DRIFT_CHANCE = BUILDER.defineInRange("oddities.armorStandPoseDriftChancePerCheck", 0.0005D, 0.0D, 1.0D);

    public static final ModConfigSpec.BooleanValue DISPENSER_ENDER_PEARLS_ENABLED = bool("redstone.dispenserEnderPearls", true, "Allow dispensers to fire real Ender Pearls.");
    public static final ModConfigSpec.BooleanValue HIGH_SPEED_MINECARTS_ENABLED = bool("transport.highSpeedMinecarts", true, "Enable high-speed minecart behavior.");
    public static final ModConfigSpec.BooleanValue MINECART_COLLISION_ENABLED = bool("transport.minecartCollisionDamage", true, "Scale minecart collision damage with speed.");
    public static final ModConfigSpec.BooleanValue MINECART_DISMOUNT_ENABLED = bool("transport.minecartMomentumDismount", true, "Preserve minecart momentum when jumping out.");
    public static final ModConfigSpec.BooleanValue MINECART_COUPLING_ENABLED = bool("transport.minecartCoupling", true, "Allow minecarts to be linked with chains.");
    public static final ModConfigSpec.BooleanValue WIND_PRESSURE_ENABLED = bool("physics.windPressure", true, "Enable blast/slipstream wind pressure.");
    public static final ModConfigSpec.BooleanValue WIND_PRESSURE_RESISTANCE_ENABLED = bool("physics.windPressureResistance", true, "Enable wind-pressure resistance from marked armor.");

    public static final ModConfigSpec.BooleanValue GROWING_ENCHANTMENTS_ENABLED = bool("enchantments.growingEnchantments", true, "Enable per-enchantment mastery.");
    public static final ModConfigSpec.BooleanValue ENCHANTMENT_BRANCHES_ENABLED = bool("enchantments.growthBranches", true, "Enable side-grade mastery branches.");
    public static final ModConfigSpec.BooleanValue CURSE_GROWTH_ENABLED = bool("enchantments.curseGrowth", true, "Allow curses to gain mastery and compensating quirks.");
    public static final ModConfigSpec.BooleanValue ENCHANTMENT_SWITCHING_ENABLED = bool("enchantments.exclusiveSwitching", true, "Allow selected exclusive enchantments to coexist with one active mode.");
    public static final ModConfigSpec.BooleanValue ENCHANTMENT_INHERITANCE_ENABLED = bool("enchantments.masteryInheritance", true, "Allow partial enchantment mastery inheritance.");
    public static final ModConfigSpec.BooleanValue UNCAPPED_ANVIL_ENABLED = bool("enchantments.uncappedAnvil", true, "Remove the survival Too Expensive rejection while preserving cost.");
    public static final ModConfigSpec.BooleanValue RAISED_ENCHANTMENT_CAPS_ENABLED = bool("enchantments.raisedLevelCaps", true, "Allow enchantments above their vanilla maximum level.");
    public static final ModConfigSpec.IntValue ENCHANTMENT_LEVEL_CAP = BUILDER.defineInRange("enchantments.levelCap", 10, 1, 255);
    public static final ModConfigSpec.BooleanValue EXTENDED_ENCHANTING_TARGETS_ENABLED = bool("enchantments.extendedTargets", true, "Allow selected work blocks and arrows to receive normal enchantments.");
    public static final ModConfigSpec.BooleanValue ENCHANTMENT_POOL_BOOKSHELF_ENABLED = bool("enchantments.arcaneBookshelfPool", true, "Allow Arcane Bookshelves to expand enchanting-table candidate pools.");
    public static final ModConfigSpec.BooleanValue ENCHANTMENT_REROLL_ENABLED = bool("enchantments.directReroll", true, "Enable direct enchanting-table offer rerolls.");
    public static final ModConfigSpec.IntValue ENCHANTMENT_REROLL_LEVEL_COST = BUILDER.defineInRange("enchantments.rerollLevelCost", 1, 1, 30);

    public static final ModConfigSpec.BooleanValue POTION_MIXING_ENABLED = bool("alchemy.potionMixing", true, "Allow weaker multi-effect potion mixtures.");
    public static final ModConfigSpec.BooleanValue TNT_DESIGN_ENABLED = bool("explosives.tntDesign", true, "Enable configurable TNT behavior.");
    public static final ModConfigSpec.BooleanValue FLETCHING_TABLE_ENABLED = bool("crafting.fletchingTableExpansion", true, "Give the vanilla Fletching Table survival uses.");
    public static final ModConfigSpec.BooleanValue QUIVER_ENABLED = bool("combat.quiver", true, "Enable the dedicated Quiver equipment/ammunition slots.");

    public static final ModConfigSpec.BooleanValue GIANT_CROPS_ENABLED = bool("organisms.giantCrops", true, "Enable very rare giant crop outcomes.");
    public static final ModConfigSpec.DoubleValue GIANT_CROP_CHANCE = BUILDER.defineInRange("organisms.giantCropChance", 0.002D, 0.0D, 1.0D);
    public static final ModConfigSpec.BooleanValue GIANT_MOBS_ENABLED = bool("organisms.giantMobs", true, "Enable rare oversized mob variants.");
    public static final ModConfigSpec.DoubleValue GIANT_MOB_CHANCE = BUILDER.defineInRange("organisms.giantMobChance", 0.0005D, 0.0D, 1.0D);
    public static final ModConfigSpec.DoubleValue GIANT_MOB_BIRTH_CHANCE = BUILDER.defineInRange("organisms.giantMobBirthChance", 0.0D, 0.0D, 1.0D);

    public static final ModConfigSpec.BooleanValue EXPANDED_RIDING_ENABLED = bool("riding.expandedRiding", true, "Allow saddles on more suitable mobs.");
    public static final ModConfigSpec.BooleanValue MOB_ON_MOB_RIDING_ENABLED = bool("riding.mobOnMobRiding", true, "Allow rare small-mob-on-large-mob riding.");
    public static final ModConfigSpec.BooleanValue NETHER_FISHING_ENABLED = bool("nether.lavaFishing", true, "Enable heat-treated fishing rods and lava fishing.");
    public static final ModConfigSpec.BooleanValue NETHER_FISH_ENABLED = bool("nether.netherFish", true, "Enable natural lava-dwelling Nether fish.");

    public static final ModConfigSpec.BooleanValue VILLAGE_SIMULATION_ENABLED = bool("village.simulation", true, "Master switch for lightweight village simulation features.");
    public static final ModConfigSpec.BooleanValue VILLAGE_CARPENTER_ENABLED = bool("village.carpenter", true, "Enable carpenter trades and construction behavior.");
    public static final ModConfigSpec.BooleanValue VILLAGE_AUTONOMOUS_GROWTH_ENABLED = bool("village.autonomousGrowth", true, "Allow villages to spend real stored resources on new buildings.");
    public static final ModConfigSpec.BooleanValue VILLAGE_LOGISTICS_ENABLED = bool("village.logistics", true, "Enable quartermaster, porter, forester, quarry and food logistics behaviors.");
    public static final ModConfigSpec.BooleanValue VILLAGE_FIRE_EMERGENCY_ENABLED = bool("village.fireEmergency", true, "Enable village fire alarms, evacuation and simple firefighting.");
    public static final ModConfigSpec.BooleanValue VILLAGE_WELFARE_ENABLED = bool("village.welfareAndConfinement", true, "Enable persistent villager welfare, confinement penalties and refusal behavior.");
    public static final ModConfigSpec.BooleanValue VILLAGE_OUTPOSTS_ENABLED = bool("village.outposts", true, "Allow mature villages to build occasional satellite outposts.");
    public static final ModConfigSpec.BooleanValue VILLAGE_FISSION_ENABLED = bool("village.fission", true, "Allow mature villages to found rare small daughter settlements.");
    public static final ModConfigSpec.BooleanValue VILLAGE_ROADS_ENABLED = bool("village.roadsAndBridges", true, "Allow village construction to add paths and small bridges.");
    public static final ModConfigSpec.BooleanValue VILLAGE_RIVER_DOCKS_ENABLED = bool("village.riverDocks", true, "Allow Carpenters to build small material-backed docks on surveyed navigable rivers; never automatically move items by water.");
    public static final ModConfigSpec.BooleanValue VILLAGE_RIVER_CARGO_ENABLED = bool("village.experimentalRiverCargo", true, "EXPERIMENTAL (default ON): allow one persistent physical chest boat per validated river route to shuttle eligible real items between recognized dock Barrels; disable if issues occur in multiplayer worlds.");
    public static final ModConfigSpec.BooleanValue VILLAGE_REFUGEES_ENABLED = bool("village.refugeesAndMigration", true, "Allow distressed villagers to migrate and new outposts to receive settlers.");
    public static final ModConfigSpec.BooleanValue VILLAGE_BREEDING_ENABLED = bool("village.breedingOverhaul", true, "Use settlement food, beds and population pressure for villager reproduction.");
    public static final ModConfigSpec.BooleanValue VILLAGE_BUILDING_CULTURE_ENABLED = bool("village.buildingCulture", true, "Let local/supplied materials influence new village architecture.");
    public static final ModConfigSpec.BooleanValue VILLAGE_IMPERFECT_CONSTRUCTION_ENABLED = bool("village.imperfectConstruction", true, "Allow inexperienced carpenters to make harmless cosmetic substitutions.");
    public static final ModConfigSpec.BooleanValue VILLAGE_PUBLIC_WORKS_ENABLED = bool("village.publicWorksRequests", true, "Surface real village shortages to nearby players.");
    public static final ModConfigSpec.BooleanValue MOB_USED_BUILDINGS_ENABLED = bool("village.mobUsedBuildings", true, "Allow villagers and passive mobs to seek plausible shelter and gathering spaces.");
    public static final ModConfigSpec.BooleanValue REGIONAL_TRADE_VALUE_ENABLED = bool("village.regionalTradeValue", true, "Enable simple distance/region trade-value bonuses.");

    // Bounded V2 scheduler defaults. These caps limit work already requested by loaded gameplay;
    // they never authorize chunk loading or offline simulation.
    public static final ModConfigSpec.IntValue VILLAGE_MAX_EMERGENCY_JOBS_PER_TICK =
            BUILDER.defineInRange("village.scheduler.emergencyJobsPerTick", 4, 1, 64);
    public static final ModConfigSpec.IntValue VILLAGE_MAX_WORKER_JOBS_PER_TICK =
            BUILDER.defineInRange("village.scheduler.workerJobsPerTick", 8, 1, 128);
    public static final ModConfigSpec.IntValue VILLAGE_MAX_PLANNING_JOBS_PER_TICK =
            BUILDER.defineInRange("village.scheduler.planningJobsPerTick", 2, 1, 32);
    public static final ModConfigSpec.IntValue VILLAGE_MAX_RECONCILE_JOBS_PER_TICK =
            BUILDER.defineInRange("village.scheduler.reconcileJobsPerTick", 4, 1, 64);
    public static final ModConfigSpec.IntValue VILLAGE_MAX_VALIDATION_JOBS_PER_TICK =
            BUILDER.defineInRange("village.scheduler.validationJobsPerTick", 2, 1, 32);
    public static final ModConfigSpec.IntValue VILLAGE_ROUTE_SEARCH_INTERVAL_TICKS =
            BUILDER.defineInRange("village.scheduler.routeSearchIntervalTicks", 10, 1, 200);
    public static final ModConfigSpec.IntValue VILLAGE_BACKGROUND_PROBES_PER_TICK =
            BUILDER.defineInRange("village.scheduler.backgroundProbesPerTick", 256, 16, 16384);
    public static final ModConfigSpec.IntValue VILLAGE_WORKER_PROBES_PER_TICK =
            BUILDER.defineInRange("village.scheduler.workerProbesPerTick", 2048, 64, 65536);
    public static final ModConfigSpec.IntValue VILLAGE_EMERGENCY_PROBES_PER_TICK =
            BUILDER.defineInRange("village.scheduler.emergencyProbesPerTick", 4096, 128, 131072);

    public static final ModConfigSpec.BooleanValue FOREST_REGENERATION_ENABLED = bool("world.forestRegeneration", true, "Enable very slow natural forest-edge regeneration.");

    public static final ModConfigSpec.BooleanValue CONTINENTAL_WORLDGEN_ENABLED = bool("worldgen.continentalOceans", false, "Enable optional continent/ocean-biased world generation hooks for new worlds.");
    public static final ModConfigSpec.IntValue CONTINENT_SCALE = BUILDER.defineInRange("worldgen.continentScale", 1536, 384, 8192);
    public static final ModConfigSpec.IntValue ISLAND_SCALE = BUILDER.defineInRange("worldgen.islandScale", 288, 96, 2048);
    public static final ModConfigSpec.DoubleValue OCEAN_BIAS = BUILDER.defineInRange("worldgen.oceanBias", 0.04D, -0.45D, 0.45D);
    public static final ModConfigSpec.DoubleValue LANDMASS_SEPARATION_BIAS = BUILDER.defineInRange("worldgen.landmassSeparationBias", 0.08D, 0.0D, 0.35D);
    public static final ModConfigSpec.DoubleValue ISLAND_THRESHOLD = BUILDER.defineInRange("worldgen.islandThreshold", 0.68D, 0.40D, 0.95D);
    public static final ModConfigSpec.DoubleValue ISLAND_FREQUENCY = BUILDER.defineInRange("worldgen.islandFrequency", 0.32D, 0.0D, 1.0D);
    public static final ModConfigSpec.DoubleValue ARCHIPELAGO_FREQUENCY = BUILDER.defineInRange("worldgen.archipelagoFrequency", 0.12D, 0.0D, 1.0D);

    public static final ModConfigSpec.BooleanValue CONTINENTAL_RIVERS_ENABLED =
            bool("worldgen.continentalRivers", true, "Generate deterministic connected river networks inside continental world generation.");
    public static final ModConfigSpec.DoubleValue RIVER_DENSITY =
            BUILDER.defineInRange("worldgen.rivers.density", 1.0D, 0.25D, 2.0D);
    public static final ModConfigSpec.DoubleValue MAJOR_RIVER_FREQUENCY =
            BUILDER.defineInRange("worldgen.rivers.majorFrequency", 0.18D, 0.0D, 1.0D);
    public static final ModConfigSpec.DoubleValue RIVER_WIDTH_SCALE =
            BUILDER.defineInRange("worldgen.rivers.widthScale", 1.0D, 0.5D, 2.5D);
    public static final ModConfigSpec.DoubleValue RIVER_MEANDER_STRENGTH =
            BUILDER.defineInRange("worldgen.rivers.meanderStrength", 0.65D, 0.0D, 1.5D);
    public static final ModConfigSpec.DoubleValue RIVER_LAKE_FREQUENCY =
            BUILDER.defineInRange("worldgen.rivers.lakeFrequency", 0.12D, 0.0D, 1.0D);
    public static final ModConfigSpec.DoubleValue RIVER_WATERFALL_FREQUENCY =
            BUILDER.defineInRange("worldgen.rivers.waterfallFrequency", 0.15D, 0.0D, 1.0D);
    public static final ModConfigSpec.DoubleValue RIVER_DELTA_FREQUENCY =
            BUILDER.defineInRange("worldgen.rivers.deltaFrequency", 0.18D, 0.0D, 1.0D);

    public static final ModConfigSpec.BooleanValue LARGE_BOATS_ENABLED = bool("ocean.largeBoats", true, "Enable large cargo-boat behavior.");
    public static final ModConfigSpec.BooleanValue OCEAN_DEBRIS_ENABLED = bool("ocean.driftDebris", true, "Enable sparse ocean drift debris.");

    public static final ModConfigSpec.BooleanValue MAP_WALLS_ENABLED = bool("display.autoConnectedMapWalls", true, "Improve adjacency behavior for map walls.");
    public static final ModConfigSpec.BooleanValue ATLAS_ENABLED = bool("display.locationAwareAtlas", true, "Enable the portable multi-map atlas and automatic current-location page selection.");
    public static final ModConfigSpec.BooleanValue ELYTRA_DISPLAY_ENABLED = bool("display.elytraArmorStandDisplay", true, "Enable opened-Elytra presentation on armor stands.");

    public static final ModConfigSpec SPEC = BUILDER.build();

    private static ModConfigSpec.BooleanValue bool(String key, boolean value, String comment) {
        return BUILDER.comment(comment).define(key, value);
    }

    private AsobibaTweaksConfig() {
    }
}
