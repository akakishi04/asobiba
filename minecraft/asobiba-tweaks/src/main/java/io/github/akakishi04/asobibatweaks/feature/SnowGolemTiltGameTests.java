package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaks;
import java.util.HashSet;
import java.util.Set;
import java.util.UUID;
import java.util.function.BooleanSupplier;
import java.util.function.DoubleSupplier;
import net.minecraft.core.BlockPos;
import net.minecraft.gametest.framework.GameTest;
import net.minecraft.gametest.framework.GameTestHelper;
import net.neoforged.neoforge.gametest.GameTestHolder;
import net.neoforged.neoforge.gametest.PrefixGameTestTemplate;

/** Dedicated-server-safe tests for the pure observer state; no renderer/client is loaded. */
@GameTestHolder(AsobibaTweaks.MOD_ID)
@PrefixGameTestTemplate(false)
public final class SnowGolemTiltGameTests {
    private static final BlockPos MARK = new BlockPos(1, 1, 1);
    private static final UUID FIRST = new UUID(0L, 1L);
    private static final UUID SECOND = new UUID(0L, 2L);

    private SnowGolemTiltGameTests() {}

    @GameTest(template = "empty3x3x3", batch = "independent_enchantments")
    public static void unseenTiltRevealsThenReturnsNeutralAfterLookingAway(GameTestHelper helper) {
        var state = armed(FIRST, true);
        state.observe(FIRST, true, false);
        state.observe(FIRST, true, true);
        if (state.tiltDegrees(FIRST) != 6.0F) {
            helper.fail("An unseen prepared tilt must appear on the first actual gaze", MARK);
            return;
        }
        state.observe(FIRST, true, false);
        state.observe(FIRST, true, true);
        var random = new CountingRandom(0.0D, false);
        update(state, FIRST, 200, false, random);
        if (state.tiltDegrees(FIRST) != 0.0F || random.rolls != 0 || random.signs != 0) {
            helper.fail("Looking away and back, even within one tick, must stay neutral", MARK);
            return;
        }
        helper.succeed();
    }

    @GameTest(template = "empty3x3x3", batch = "independent_enchantments")
    public static void continuousGazeNeverStartsTiltOrSamplesChance(GameTestHelper helper) {
        var state = new SnowGolemTiltState();
        var random = new CountingRandom(0.0D, false);
        for (int tick = 0; tick <= 2000; tick++) {
            update(state, FIRST, tick, true, random);
        }
        state.observe(SECOND, true, true);
        if (random.rolls != 0 || random.signs != 0 || state.tiltDegrees(FIRST) != 0.0F || state.size() != 1) {
            helper.fail("Staring or observing an untracked ID must not generate a visible tilt", MARK);
            return;
        }
        update(state, FIRST, 2001, false, random);
        state.observe(FIRST, true, true);
        if (state.tiltDegrees(FIRST) != -6.0F || random.rolls != 1 || random.signs != 1) {
            helper.fail("A due off-gaze roll must prepare one fixed negative tilt", MARK);
            return;
        }
        for (int tick = 2002; tick < 2100; tick++) {
            update(state, FIRST, tick, true, random);
        }
        if (state.tiltDegrees(FIRST) != -6.0F || random.signs != 1) {
            helper.fail("A revealed tilt must not reroll its direction while being watched", MARK);
            return;
        }
        helper.succeed();
    }

    @GameTest(template = "empty3x3x3", batch = "independent_enchantments")
    public static void initialWarmupAndFailedRollIntervalsAreAtLeast200Ticks(GameTestHelper helper) {
        var state = new SnowGolemTiltState();
        var random = new CountingRandom(0.5D, true);
        update(state, FIRST, 0, false, random);
        update(state, FIRST, 199, false, random);
        if (random.rolls != 0) {
            helper.fail("Initial observation must wait the complete 200-tick warmup", MARK);
            return;
        }
        update(state, FIRST, 200, false, random);
        update(state, FIRST, 200, false, random);
        update(state, FIRST, 399, false, random);
        if (random.rolls != 1 || random.signs != 0) {
            helper.fail("Duplicate observations or the following 199 ticks must not retry a failed chance", MARK);
            return;
        }
        update(state, FIRST, 400, false, random);
        if (random.rolls != 2 || random.signs != 0 || state.tiltDegrees(FIRST) != 0.0F) {
            helper.fail("The next failed chance must be sampled once at the 200-tick boundary", MARK);
            return;
        }
        helper.succeed();
    }

    @GameTest(template = "empty3x3x3", batch = "independent_enchantments")
    public static void unseenAndSeenTiltsExpireAtTheirExactBounds(GameTestHelper helper) {
        var unseen = armed(FIRST, true);
        unseen.tick(799);
        if (unseen.tiltDegrees(FIRST) != 6.0F) {
            helper.fail("An unseen tilt expired before its 600-tick limit", MARK);
            return;
        }
        unseen.tick(800);
        var seen = armed(FIRST, false);
        seen.tick(799);
        seen.observe(FIRST, true, true);
        seen.tick(1998);
        if (unseen.tiltDegrees(FIRST) != 0.0F || seen.tiltDegrees(FIRST) != -6.0F) {
            helper.fail("Unseen expiry or the independent 1200-tick revealed lifetime is wrong", MARK);
            return;
        }
        seen.tick(1999);
        seen.observe(FIRST, true, true);
        if (seen.tiltDegrees(FIRST) != 0.0F) {
            helper.fail("A continuously watched tilt must still expire after its bounded hold", MARK);
            return;
        }
        helper.succeed();
    }

    @GameTest(template = "empty3x3x3", batch = "independent_enchantments")
    public static void successCooldownsSurviveCancellationAndSeparateGolems(GameTestHelper helper) {
        var own = armed(FIRST, true);
        own.cancel(FIRST);
        var ownRandom = new CountingRandom(0.0D, false);
        update(own, FIRST, 12199, false, ownRandom);
        if (ownRandom.rolls != 0 || own.tiltDegrees(FIRST) != 0.0F) {
            helper.fail("A canceled success must retain the golem's full 12000-tick cooldown", MARK);
            return;
        }
        update(own, FIRST, 12200, false, ownRandom);
        var observer = armed(FIRST, true);
        observer.retain(Set.of());
        var observerRandom = new CountingRandom(0.0D, true);
        update(observer, SECOND, 200, false, observerRandom);
        update(observer, SECOND, 6199, false, observerRandom);
        if (own.tiltDegrees(FIRST) != -6.0F || ownRandom.rolls != 1 || observerRandom.rolls != 0) {
            helper.fail("Per-golem cooldown expiry or observer cooldown after removal is wrong", MARK);
            return;
        }
        update(observer, SECOND, 6200, false, observerRandom);
        if (observer.tiltDegrees(SECOND) != 6.0F || observerRandom.rolls != 1) {
            helper.fail("A different golem may arm only after the observer's full 6000-tick cooldown", MARK);
            return;
        }
        helper.succeed();
    }

    @GameTest(template = "empty3x3x3", batch = "independent_enchantments")
    public static void uuidStateIsIsolatedAndAtMostOneGolemCanBeArmed(GameTestHelper helper) {
        var state = new SnowGolemTiltState();
        var random = new CountingRandom(0.0D, true);
        update(state, FIRST, 0, false, random);
        update(state, SECOND, 0, false, random);
        update(state, new UUID(0L, 1L), 200, false, random);
        update(state, SECOND, 200, false, random);
        state.observe(SECOND, false, false);
        state.cancel(new UUID(0L, 99L));
        if (state.size() != 2 || state.tiltDegrees(FIRST) != 6.0F
                || state.tiltDegrees(SECOND) != 0.0F || random.rolls != 1) {
            helper.fail("UUID value identity, single-active limit, or unrelated cancellation is wrong", MARK);
            return;
        }
        state.observe(new UUID(0L, 1L), false, true);
        if (state.tiltDegrees(FIRST) != 0.0F || state.size() != 2) {
            helper.fail("An ineligible equivalent UUID must cancel only its own angle", MARK);
            return;
        }
        helper.succeed();
    }

    @GameTest(template = "empty3x3x3", batch = "independent_enchantments")
    public static void chanceAndInjectedRandomValuesFailClosedOutsideValidBounds(GameTestHelper helper) {
        for (double chance : new double[] {0.0D, -1.0D, Double.NaN, Double.POSITIVE_INFINITY, Double.NEGATIVE_INFINITY}) {
            var state = new SnowGolemTiltState();
            var random = new CountingRandom(0.0D, true);
            state.update(FIRST, 0, true, false, chance, random, random);
            state.update(FIRST, 200, true, false, chance, random, random);
            if (state.tiltDegrees(FIRST) != 0.0F || random.rolls != 0 || random.signs != 0) {
                helper.fail("Disabled, negative, or non-finite chance must fail closed", MARK);
                return;
            }
        }
        for (double roll : new double[] {-0.1D, 1.0D, Double.NaN, Double.POSITIVE_INFINITY, Double.NEGATIVE_INFINITY}) {
            var state = new SnowGolemTiltState();
            var random = new CountingRandom(roll, true);
            state.update(FIRST, 0, true, false, 1.0D, random, random);
            state.update(FIRST, 200, true, false, 1.0D, random, random);
            if (state.tiltDegrees(FIRST) != 0.0F || random.rolls != 1 || random.signs != 0) {
                helper.fail("Invalid random samples must consume the attempt without arming a tilt", MARK);
                return;
            }
        }
        var saturated = new SnowGolemTiltState();
        var certain = new CountingRandom(0.99999D, false);
        saturated.update(FIRST, 0, true, false, 2.0D, certain, certain);
        saturated.update(FIRST, 200, true, false, 2.0D, certain, certain);
        var edge = new SnowGolemTiltState();
        var exact = new CountingRandom(SnowGolemTiltState.DEFAULT_CHANCE, true);
        update(edge, FIRST, 0, false, exact);
        update(edge, FIRST, 200, false, exact);
        if (saturated.tiltDegrees(FIRST) != -6.0F || edge.tiltDegrees(FIRST) != 0.0F) {
            helper.fail("Finite chance must cap at one and an exact threshold sample must fail", MARK);
            return;
        }
        helper.succeed();
    }

    @GameTest(template = "empty3x3x3", batch = "independent_enchantments")
    public static void cacheOverflowFailsClosedAndRetainingLoadedIdsPrunes(GameTestHelper helper) {
        var state = new SnowGolemTiltState();
        var random = new CountingRandom(0.0D, true);
        Set<UUID> loaded = new HashSet<>();
        for (int i = 0; i < SnowGolemTiltState.MAX_TRACKED_GOLEMS; i++) {
            UUID id = new UUID(1L, i);
            loaded.add(id);
            update(state, id, 0, false, random);
        }
        UUID overflow = new UUID(2L, 0L);
        update(state, overflow, 0, false, random);
        update(state, overflow, 200, false, random);
        if (state.size() != 32 || state.tiltDegrees(overflow) != 0.0F || random.rolls != 0) {
            helper.fail("The 33rd observed UUID must not displace state or consume randomness", MARK);
            return;
        }
        loaded.remove(new UUID(1L, 0L));
        state.retain(loaded);
        update(state, overflow, 200, false, random);
        update(state, overflow, 399, false, random);
        if (state.size() != 32 || random.rolls != 0) {
            helper.fail("A newly admitted UUID must receive its own complete warmup", MARK);
            return;
        }
        update(state, overflow, 400, false, random);
        state.retain(loaded);
        loaded.clear();
        if (state.size() != 31 || state.tiltDegrees(overflow) != 0.0F || random.rolls != 1) {
            helper.fail("Pruning must discard active removed IDs and must not retain the supplied set", MARK);
            return;
        }
        helper.succeed();
    }

    @GameTest(template = "empty3x3x3", batch = "independent_enchantments")
    public static void observationResetRestartsWarmupWithoutBypassingSuccessCooldowns(GameTestHelper helper) {
        var own = armed(FIRST, true);
        own.observe(FIRST, true, true);
        own.resetObservation();
        own.observe(FIRST, true, true);
        var ownRandom = new CountingRandom(0.0D, false);
        update(own, FIRST, 400, false, ownRandom);
        update(own, FIRST, 12199, false, ownRandom);
        if (own.size() != 1 || own.tiltDegrees(FIRST) != 0.0F || ownRandom.rolls != 0) {
            helper.fail("A same-world observation reset must clear the angle but retain the golem cooldown", MARK);
            return;
        }
        update(own, FIRST, 12200, false, ownRandom);

        var observer = armed(FIRST, true);
        observer.resetObservation();
        var observerRandom = new CountingRandom(0.0D, true);
        update(observer, SECOND, 400, false, observerRandom);
        update(observer, SECOND, 6199, false, observerRandom);
        if (ownRandom.rolls != 1 || own.tiltDegrees(FIRST) != -6.0F || observerRandom.rolls != 0) {
            helper.fail("Observation reset must preserve the full observer cooldown for other golems", MARK);
            return;
        }
        update(observer, SECOND, 6200, false, observerRandom);

        var warmup = new SnowGolemTiltState();
        var warmupRandom = new CountingRandom(0.5D, true);
        update(warmup, FIRST, 0, false, warmupRandom);
        warmup.tick(100);
        warmup.resetObservation();
        update(warmup, FIRST, 299, false, warmupRandom);
        if (observerRandom.rolls != 1 || observer.tiltDegrees(SECOND) != 6.0F || warmupRandom.rolls != 0) {
            helper.fail("A soft reset must also restart the observation warmup for unsuccessful golems", MARK);
            return;
        }
        update(warmup, FIRST, 300, false, warmupRandom);
        if (warmupRandom.rolls != 1) {
            helper.fail("The reset observation warmup must finish exactly 200 ticks later", MARK);
            return;
        }
        helper.succeed();
    }

    @GameTest(template = "empty3x3x3", batch = "independent_enchantments")
    public static void clearRemovesAnglesEntriesAndOldContextCooldowns(GameTestHelper helper) {
        var state = armed(FIRST, true);
        state.observe(FIRST, true, true);
        state.clear();
        state.observe(FIRST, true, true);
        if (state.size() != 0 || state.tiltDegrees(FIRST) != 0.0F) {
            helper.fail("A context reset must leave no angle or tracked UUID", MARK);
            return;
        }
        var random = new CountingRandom(0.0D, false);
        update(state, FIRST, 200, false, random);
        update(state, FIRST, 399, false, random);
        if (random.rolls != 0) {
            helper.fail("Returning after clear must start a fresh warmup", MARK);
            return;
        }
        update(state, FIRST, 400, false, random);
        if (state.tiltDegrees(FIRST) != -6.0F || random.rolls != 1) {
            helper.fail("The old context's success cooldown must not survive clear", MARK);
            return;
        }
        helper.succeed();
    }

    @GameTest(template = "empty3x3x3", batch = "independent_enchantments")
    public static void clockRollbackClearsStateAndRestartsObservationWarmup(GameTestHelper helper) {
        var state = new SnowGolemTiltState();
        var random = new CountingRandom(0.0D, true);
        update(state, FIRST, 1000, false, random);
        update(state, FIRST, 1200, false, random);
        state.tick(1199);
        if (state.size() != 0 || state.tiltDegrees(FIRST) != 0.0F) {
            helper.fail("Clock rollback must discard active angles and old timestamps", MARK);
            return;
        }
        update(state, FIRST, 1199, false, random);
        update(state, FIRST, 1398, false, random);
        if (random.rolls != 1) {
            helper.fail("Rollback must not allow an immediate retrigger", MARK);
            return;
        }
        update(state, FIRST, 1399, false, random);
        state.tick(Long.MAX_VALUE);
        if (random.rolls != 2 || state.tiltDegrees(FIRST) != 0.0F) {
            helper.fail("Rollback recovery or expiry after a large forward jump is wrong", MARK);
            return;
        }
        state.tick(Long.MIN_VALUE);
        update(state, FIRST, Long.MIN_VALUE, false, random);
        update(state, FIRST, Long.MIN_VALUE + 200L, false, random);
        state.tick(Long.MAX_VALUE);
        if (random.rolls != 3 || state.tiltDegrees(FIRST) != 0.0F) {
            helper.fail("Clock wrap and elapsed arithmetic must fail closed rather than retain old tilts", MARK);
            return;
        }
        helper.succeed();
    }

    private static SnowGolemTiltState armed(UUID id, boolean positive) {
        var state = new SnowGolemTiltState();
        var random = new CountingRandom(0.0D, positive);
        update(state, id, 0, false, random);
        update(state, id, 200, false, random);
        return state;
    }

    private static void update(SnowGolemTiltState state, UUID id, long tick, boolean looking,
            CountingRandom random) {
        state.update(id, tick, true, looking, SnowGolemTiltState.DEFAULT_CHANCE, random, random);
    }

    private static final class CountingRandom implements DoubleSupplier, BooleanSupplier {
        private final double roll;
        private final boolean positive;
        private int rolls;
        private int signs;

        private CountingRandom(double roll, boolean positive) {
            this.roll = roll;
            this.positive = positive;
        }

        @Override
        public double getAsDouble() {
            rolls++;
            return roll;
        }

        @Override
        public boolean getAsBoolean() {
            signs++;
            return positive;
        }
    }
}
