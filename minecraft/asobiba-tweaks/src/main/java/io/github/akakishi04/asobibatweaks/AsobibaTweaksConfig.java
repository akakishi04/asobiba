package io.github.akakishi04.asobibatweaks;

import net.neoforged.neoforge.common.ModConfigSpec;

public final class AsobibaTweaksConfig {
    private static final ModConfigSpec.Builder BUILDER = new ModConfigSpec.Builder();

    public static final ModConfigSpec.BooleanValue GROWING_ITEMS_ENABLED = BUILDER
            .comment("Enable per-item growth XP and levels for damageable items.")
            .define("growingItems.enabled", true);

    public static final ModConfigSpec.IntValue GROWING_ITEMS_MAX_LEVEL = BUILDER
            .comment("Maximum growth level.")
            .defineInRange("growingItems.maxLevel", 10, 1, 100);

    public static final ModConfigSpec.IntValue GROWING_ITEMS_BASE_XP = BUILDER
            .comment("XP scale. The next level threshold is baseXp * currentLevel^2.")
            .defineInRange("growingItems.baseXp", 20, 1, 100000);

    public static final ModConfigSpec.DoubleValue GROWING_ITEMS_REPAIR_CHANCE_PER_LEVEL = BUILDER
            .comment("Chance per level to repair one durability point whenever growth XP is earned.")
            .defineInRange("growingItems.repairChancePerLevel", 0.02D, 0.0D, 1.0D);

    public static final ModConfigSpec.DoubleValue GROWING_ITEMS_MINING_TIER_UPGRADE_CHANCE = BUILDER
            .comment("Chance when a pickaxe levels up to gain +1 effective mining tier.")
            .defineInRange("growingItems.miningTierUpgradeChance", 0.12D, 0.0D, 1.0D);

    public static final ModConfigSpec.IntValue GROWING_ITEMS_MAX_MINING_TIER_BONUS = BUILDER
            .comment("Maximum bonus mining tiers an individual pickaxe can gain.")
            .defineInRange("growingItems.maxMiningTierBonus", 2, 0, 4);

    public static final ModConfigSpec.BooleanValue DAILY_FAVOR_ENABLED = BUILDER
            .comment("Enable one small deterministic activity bonus per Minecraft day.")
            .define("dailyFavor.enabled", true);

    public static final ModConfigSpec.DoubleValue DAILY_FAVOR_REWARD_CHANCE = BUILDER
            .comment("Chance for a matching action to grant the daily favor reward.")
            .defineInRange("dailyFavor.rewardChance", 0.25D, 0.0D, 1.0D);

    public static final ModConfigSpec.IntValue DAILY_FAVOR_XP = BUILDER
            .comment("Experience points granted when the daily favor reward triggers.")
            .defineInRange("dailyFavor.rewardXp", 1, 0, 100);

    public static final ModConfigSpec.BooleanValue UNIVERSAL_BOND_ENABLED = BUILDER
            .comment("Allow any Mob to build bond with a player using sneak-interact gifts.")
            .define("universalBond.enabled", true);

    public static final ModConfigSpec.IntValue UNIVERSAL_BOND_PER_GIFT = BUILDER
            .comment("Bond gained for each accepted gift. 100 bond completes bonding.")
            .defineInRange("universalBond.bondPerGift", 25, 1, 100);

    public static final ModConfigSpec.BooleanValue UNIVERSAL_BOND_FOLLOW = BUILDER
            .comment("Allow bonded pathfinding mobs in Follow mode to navigate toward their owner.")
            .define("universalBond.followOwner", true);

    public static final ModConfigSpec.BooleanValue UNIVERSAL_BOND_FRIENDLY_FIRE = BUILDER
            .comment("Allow owner and bonded mob to damage each other.")
            .define("universalBond.friendlyFire", false);

    public static final ModConfigSpec.BooleanValue UNIVERSAL_BOND_ALLOW_BOSSES = BUILDER
            .comment("Allow Ender Dragon and Wither to participate in Universal Bond. Experimental.")
            .define("universalBond.allowBosses", false);

    public static final ModConfigSpec.BooleanValue PLAY_TIME_LIMIT_ENABLED = BUILDER
            .comment("Enable a per-login-session play time limit.")
            .define("playTimeLimit.enabled", false);

    public static final ModConfigSpec.IntValue PLAY_TIME_LIMIT_MINUTES = BUILDER
            .comment("Session time limit in minutes.")
            .defineInRange("playTimeLimit.limitMinutes", 120, 1, 10080);

    public static final ModConfigSpec.IntValue PLAY_TIME_WARNING_MINUTES = BUILDER
            .comment("Show a warning this many minutes before the limit.")
            .defineInRange("playTimeLimit.warningMinutes", 10, 0, 1440);

    public static final ModConfigSpec.ConfigValue<String> PLAY_TIME_LIMIT_MODE = BUILDER
            .comment("WARN_ONLY or DISCONNECT.")
            .define("playTimeLimit.mode", "WARN_ONLY", value ->
                    value instanceof String s && (s.equalsIgnoreCase("WARN_ONLY") || s.equalsIgnoreCase("DISCONNECT")));

    public static final ModConfigSpec SPEC = BUILDER.build();

    private AsobibaTweaksConfig() {
    }
}
