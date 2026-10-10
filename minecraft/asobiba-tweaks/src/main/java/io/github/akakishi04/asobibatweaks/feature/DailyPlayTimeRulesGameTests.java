package io.github.akakishi04.asobibatweaks.feature;

import com.mojang.brigadier.StringReader;
import com.mojang.brigadier.exceptions.CommandSyntaxException;
import com.mojang.serialization.Dynamic;
import io.github.akakishi04.asobibatweaks.AsobibaTweaks;
import io.netty.buffer.Unpooled;
import net.minecraft.gametest.framework.GameTest;
import net.minecraft.gametest.framework.GameTestHelper;
import net.minecraft.nbt.NbtOps;
import net.minecraft.world.level.GameRules;
import net.neoforged.neoforge.gametest.GameTestHolder;
import net.neoforged.neoforge.gametest.PrefixGameTestTemplate;

/** Native world-creation/command parser and level.dat persistence contracts. */
@GameTestHolder(AsobibaTweaks.MOD_ID)
@PrefixGameTestTemplate(false)
public final class DailyPlayTimeRulesGameTests {
    private DailyPlayTimeRulesGameTests() {}

    @GameTest(template = "empty3x3x3", batch = "daily_play_time")
    public static void newWorldOptsOutWithJapanMidnightDefault(GameTestHelper helper) {
        GameRules rules = new GameRules();
        helper.assertTrue(!PlayTimeRules.enabled(rules), "Every new world must explicitly opt in");
        helper.assertTrue(PlayTimeRules.limitMinutes(rules) == 120, "Default cap is two hours");
        helper.assertTrue(PlayTimeRules.offsetMinutes(rules) == 540, "Default reset offset is fixed Japan UTC+09:00");
        helper.succeed();
    }

    @GameTest(template = "empty3x3x3", batch = "daily_play_time")
    public static void nativeRulesPersistAndWorldCopiesAreIndependent(GameTestHelper helper) {
        GameRules first = new GameRules();
        first.getRule(PlayTimeRules.ENABLED).set(true, null);
        first.getRule(PlayTimeRules.LIMIT_MINUTES).set(45, null);
        first.getRule(PlayTimeRules.RESET_UTC_OFFSET_MINUTES).set(-480, null);
        GameRules reloaded = new GameRules(new Dynamic<>(NbtOps.INSTANCE, first.createTag()));
        helper.assertTrue(PlayTimeRules.enabled(reloaded) && PlayTimeRules.limitMinutes(reloaded) == 45
                && PlayTimeRules.offsetMinutes(reloaded) == -480, "All three settings survive native NBT round-trip");
        GameRules other = new GameRules();
        helper.assertTrue(!PlayTimeRules.enabled(other) && PlayTimeRules.limitMinutes(other) == 120,
                "A different world cannot inherit opt-in or modified budget");
        GameRules copy = reloaded.copy();
        copy.getRule(PlayTimeRules.ENABLED).set(false, null);
        copy.getRule(PlayTimeRules.LIMIT_MINUTES).set(30, null);
        helper.assertTrue(PlayTimeRules.enabled(reloaded) && PlayTimeRules.limitMinutes(reloaded) == 45,
                "Cancelled/changed creation-screen copies cannot mutate the original world settings");
        helper.succeed();
    }

    @GameTest(template = "empty3x3x3", batch = "daily_play_time")
    public static void creationScreenRejectsInvalidDailyLimits(GameTestHelper helper) {
        var value = new GameRules().getRule(PlayTimeRules.LIMIT_MINUTES);
        for (String valid : new String[] {"1", "120", "1440"}) {
            helper.assertTrue(value.tryDeserialize(valid), "Native creation UI must accept bounded limit " + valid);
        }
        for (String invalid : new String[] {"0", "-1", "1441", "10080", "2147483648", "", "abc", "12.5", "30junk"}) {
            helper.assertTrue(!value.tryDeserialize(invalid), "Native creation UI must reject invalid limit " + invalid);
        }
        helper.succeed();
    }

    @GameTest(template = "empty3x3x3", batch = "daily_play_time")
    public static void creationScreenAndCopyRejectInvalidUtcOffsets(GameTestHelper helper) {
        GameRules rules = new GameRules();
        for (GameRules candidate : new GameRules[] {rules, rules.copy()}) {
            var value = candidate.getRule(PlayTimeRules.RESET_UTC_OFFSET_MINUTES);
            for (String valid : new String[] {"-840", "0", "540", "840"}) {
                helper.assertTrue(value.tryDeserialize(valid), "Native UI must accept fixed offset " + valid);
            }
            for (String invalid : new String[] {"-841", "841", "2147483648", "NaN", "540m"}) {
                helper.assertTrue(!value.tryDeserialize(invalid), "Native UI copy must retain offset bounds " + invalid);
            }
        }
        helper.succeed();
    }

    @GameTest(template = "empty3x3x3", batch = "daily_play_time")
    public static void gameruleCommandUsesSameBoundsAndDiscoverableTypes(GameTestHelper helper) {
        int[] found = {0};
        GameRules.visitGameRuleTypes(new GameRules.GameRuleTypeVisitor() {
            @Override
            public void visitBoolean(GameRules.Key<GameRules.BooleanValue> key, GameRules.Type<GameRules.BooleanValue> type) {
                if (key.equals(PlayTimeRules.ENABLED)) found[0]++;
            }

            @Override
            public void visitInteger(GameRules.Key<GameRules.IntegerValue> key, GameRules.Type<GameRules.IntegerValue> type) {
                if (key.equals(PlayTimeRules.LIMIT_MINUTES)) {
                    found[0]++;
                    assertCommand(helper, type, "1", true);
                    assertCommand(helper, type, "1440", true);
                    assertCommand(helper, type, "0", false);
                    assertCommand(helper, type, "1441", false);
                } else if (key.equals(PlayTimeRules.RESET_UTC_OFFSET_MINUTES)) {
                    found[0]++;
                    assertCommand(helper, type, "-840", true);
                    assertCommand(helper, type, "840", true);
                    assertCommand(helper, type, "-841", false);
                    assertCommand(helper, type, "841", false);
                }
            }
        });
        helper.assertTrue(found[0] == 3, "All three native types must be visible to world creation and /gamerule");
        helper.succeed();
    }

    @GameTest(template = "empty3x3x3", batch = "daily_play_time")
    public static void malformedNativeNbtCannotProduceInvalidEffectiveAllowance(GameTestHelper helper) {
        var tag = new GameRules().createTag();
        for (String invalid : new String[] {"-1", "0", "1441", "2147483647", "2147483648", "garbage"}) {
            tag.putString(PlayTimeRules.LIMIT_MINUTES.getId(), invalid);
            GameRules reloaded = new GameRules(new Dynamic<>(NbtOps.INSTANCE, tag));
            helper.assertTrue(PlayTimeRules.limitMinutes(reloaded) == 120, "Unsafe saved cap must use safe default: " + invalid);
        }
        for (String invalid : new String[] {"-841", "841", "2147483647", "-2147483648"}) {
            tag.putString(PlayTimeRules.RESET_UTC_OFFSET_MINUTES.getId(), invalid);
            GameRules reloaded = new GameRules(new Dynamic<>(NbtOps.INSTANCE, tag));
            helper.assertTrue(PlayTimeRules.offsetMinutes(reloaded) == 540, "Unsafe saved offset must use Japan default: " + invalid);
        }
        helper.succeed();
    }

    @GameTest(template = "empty3x3x3", batch = "daily_play_time")
    public static void displayPayloadRoundTripsLongCountsAndFixedWireSize(GameTestHelper helper) {
        var original = new DailyPlayTimePayload(true, 3_000_000_000L, 7_123_456, 7_200_000, 1_800_000_000_000L, true);
        var buffer = Unpooled.buffer();
        try {
            DailyPlayTimePayload.STREAM_CODEC.encode(buffer, original);
            helper.assertTrue(buffer.readableBytes() == 34, "Snapshot must remain a small fixed-size payload");
            var decoded = DailyPlayTimePayload.STREAM_CODEC.decode(buffer);
            helper.assertTrue(decoded.equals(original) && buffer.readableBytes() == 0,
                    "All authority fields, including long day count and pause, round-trip exactly");
        } finally {
            buffer.release();
        }
        helper.succeed();
    }

    private static void assertCommand(GameTestHelper helper, GameRules.Type<GameRules.IntegerValue> type,
            String text, boolean expectedValid) {
        boolean valid;
        try {
            var reader = new StringReader(text);
            type.createArgument("value").getType().parse(reader);
            valid = !reader.canRead();
        } catch (CommandSyntaxException expected) {
            valid = false;
        }
        helper.assertTrue(valid == expectedValid, "Command parser must enforce native rule bounds for " + text);
    }
}
