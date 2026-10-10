package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.mixin.GameRulesIntegerValueAccessor;
import net.minecraft.server.MinecraftServer;
import net.minecraft.world.level.GameRules;

/** Per-world settings, persisted by vanilla in level.dat and shown in world creation. */
public final class PlayTimeRules {
    public static final int DEFAULT_LIMIT_MINUTES = 120;
    public static final int MIN_LIMIT_MINUTES = 1;
    public static final int MAX_LIMIT_MINUTES = 1440;
    public static final int DEFAULT_RESET_UTC_OFFSET_MINUTES = 540;
    public static final int MIN_RESET_UTC_OFFSET_MINUTES = -840;
    public static final int MAX_RESET_UTC_OFFSET_MINUTES = 840;

    public static final GameRules.Key<GameRules.BooleanValue> ENABLED = GameRules.register(
            "asobibaDailyPlayTimeEnabled", GameRules.Category.PLAYER,
            GameRules.BooleanValue.create(false));
    public static final GameRules.Key<GameRules.IntegerValue> LIMIT_MINUTES = GameRules.register(
            "asobibaDailyPlayTimeLimitMinutes", GameRules.Category.PLAYER,
            GameRulesIntegerValueAccessor.asobiba$createBounded(DEFAULT_LIMIT_MINUTES,
                    MIN_LIMIT_MINUTES, MAX_LIMIT_MINUTES, (server, value) -> {}));
    public static final GameRules.Key<GameRules.IntegerValue> RESET_UTC_OFFSET_MINUTES = GameRules.register(
            "asobibaDailyPlayTimeResetUtcOffsetMinutes", GameRules.Category.PLAYER,
            GameRulesIntegerValueAccessor.asobiba$createBounded(DEFAULT_RESET_UTC_OFFSET_MINUTES,
                    MIN_RESET_UTC_OFFSET_MINUTES, MAX_RESET_UTC_OFFSET_MINUTES, (server, value) -> {}));

    private PlayTimeRules() {}

    /** Call during common mod construction, before any GameRules instance is constructed. */
    public static void register() {
        // Loading this class registers the native rules exactly once.
    }

    public static boolean enabled(MinecraftServer server) {
        return enabled(server.getGameRules());
    }

    public static boolean enabled(GameRules rules) {
        return rules.getBoolean(ENABLED);
    }

    public static int limitMinutes(MinecraftServer server) {
        return limitMinutes(server.getGameRules());
    }

    public static int limitMinutes(GameRules rules) {
        // Vanilla NBT deserialization does not apply command argument bounds. A malformed or
        // externally edited level.dat must not introduce a negative or overflowing allowance.
        int value = rules.getInt(LIMIT_MINUTES);
        return value >= MIN_LIMIT_MINUTES && value <= MAX_LIMIT_MINUTES ? value : DEFAULT_LIMIT_MINUTES;
    }

    public static long limitMillis(MinecraftServer server) {
        return limitMinutes(server) * 60_000L;
    }

    public static int offsetMinutes(MinecraftServer server) {
        return offsetMinutes(server.getGameRules());
    }

    public static int offsetMinutes(GameRules rules) {
        int value = rules.getInt(RESET_UTC_OFFSET_MINUTES);
        return value >= MIN_RESET_UTC_OFFSET_MINUTES && value <= MAX_RESET_UTC_OFFSET_MINUTES
                ? value : DEFAULT_RESET_UTC_OFFSET_MINUTES;
    }
}
