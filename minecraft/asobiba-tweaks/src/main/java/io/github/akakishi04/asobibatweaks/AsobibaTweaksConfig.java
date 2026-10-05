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
