package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaks;
import java.util.HashSet;
import java.util.function.BooleanSupplier;
import java.util.function.DoubleSupplier;
import net.minecraft.core.BlockPos;
import net.minecraft.gametest.framework.GameTest;
import net.minecraft.gametest.framework.GameTestHelper;
import net.neoforged.neoforge.gametest.GameTestHolder;
import net.neoforged.neoforge.gametest.PrefixGameTestTemplate;

/** Dedicated-server-safe animation contract tests; actual graphics require client playtesting. */
@GameTestHolder(AsobibaTweaks.MOD_ID)
@PrefixGameTestTemplate(false)
public final class CloudLineGameTests {
    private static final BlockPos MARK = new BlockPos(1, 1, 1);

    private CloudLineGameTests() {}

    @GameTest(template = "empty3x3x3", batch = "independent_enchantments")
    public static void rareCloudAttemptsRequireWarmupAndRespectIntervals(GameTestHelper helper) {
        var state = new CloudLineState();
        var random = new CountingRandom(0.5D, false);
        update(state, 0, true, 0.02D, random);
        update(state, 1199, true, 0.02D, random);
        if (random.rolls != 0) { helper.fail("Cloud attempts must wait a full eligible minute", MARK); return; }
        update(state, 1200, true, 0.02D, random);
        update(state, 1200, true, 0.02D, random);
        update(state, 2399, true, 0.02D, random);
        if (random.rolls != 1 || random.shapes != 0 || state.active()) {
            helper.fail("A failed roll must not repeat early or allocate a formation", MARK); return;
        }
        update(state, 2400, true, 0.02D, random);
        if (random.rolls != 2) { helper.fail("Next attempt is due at the exact interval", MARK); return; }
        helper.succeed();
    }

    @GameTest(template = "empty3x3x3", batch = "independent_enchantments")
    public static void lineHasFiveDistinctSquareSizesAndRegularSpacing(GameTestHelper helper) {
        var state = armed(false);
        state.advance(1300);
        var clouds = state.snapshot(0);
        var sizes = new HashSet<Double>();
        if (clouds.size() != 5) { helper.fail("Exactly five clouds form one bounded line", MARK); return; }
        for (int slot = 0; slot < clouds.size(); slot++) {
            var cloud = clouds.get(slot);
            sizes.add(cloud.size());
            if (cloud.z() != 96.0D || cloud.alpha() != 0.8F || cloud.size() < 12 || cloud.size() > 36
                    || slot > 0 && Math.abs(clouds.get(slot - 1).x() - cloud.x() - 48) > 1.0E-8) {
                helper.fail("Clouds must remain equally spaced, square and naturally translucent", MARK); return;
            }
        }
        if (sizes.size() != 5) { helper.fail("The line needs differently sized squares", MARK); return; }
        helper.succeed();
    }

    @GameTest(template = "empty3x3x3", batch = "independent_enchantments")
    public static void cloudDriftMatchesVanillaAndInterpolatesSmoothly(GameTestHelper helper) {
        var state = armed(false);
        double x = state.snapshot(0).get(0).x();
        state.advance(1300);
        double moved = state.snapshot(0).get(0).x();
        double interpolated = state.snapshot(0.5F).get(0).x();
        if (Math.abs(moved - x + 3) > 1.0E-8 || Math.abs(interpolated - moved + 0.015D) > 1.0E-8) {
            helper.fail("Clouds must drift west at vanilla's 0.03 blocks per tick, including partial ticks", MARK); return;
        }
        helper.succeed();
    }

    @GameTest(template = "empty3x3x3", batch = "independent_enchantments")
    public static void cloudLineDispersesAndExpiresWithoutLingeringState(GameTestHelper helper) {
        var state = armed(false);
        if (state.snapshot(0).get(0).alpha() != 0.0F) { helper.fail("A line must fade in", MARK); return; }
        state.advance(2400);
        for (var cloud : state.snapshot(0)) {
            if (cloud.z() != 96.0D) { helper.fail("The line dispersed before its aligned phase ended", MARK); return; }
        }
        state.advance(2700);
        var dispersed = state.snapshot(0);
        if (dispersed.get(0).z() == dispersed.get(1).z()
                || dispersed.get(0).alpha() <= 0 || dispersed.get(0).alpha() >= 0.8F) {
            helper.fail("Dispersal must separate the clouds and reduce opacity", MARK); return;
        }
        state.advance(2999);
        if (!state.active() || !state.snapshot(1).isEmpty()) {
            helper.fail("Partial ticks must finish the fade at its exact boundary", MARK); return;
        }
        state.advance(3000);
        if (state.active() || !state.snapshot(0).isEmpty()) { helper.fail("Expired clouds must leave no geometry", MARK); return; }
        helper.succeed();
    }

    @GameTest(template = "empty3x3x3", batch = "independent_enchantments")
    public static void pauseCameraAndToggleResetPreservesLongCooldown(GameTestHelper helper) {
        var state = armed(false);
        state.advance(1300);
        state.resetObservation();
        var random = new CountingRandom(0.0D, true);
        update(state, 2500, true, 1.0D, random);
        update(state, 13199, true, 1.0D, random);
        if (state.active() || random.rolls != 0) {
            helper.fail("Pause, camera and settings resets must cancel without farming another roll", MARK); return;
        }
        update(state, 13200, true, 1.0D, random);
        if (!state.active() || random.rolls != 1 || random.shapes != 1) {
            helper.fail("A fresh line may begin only at the success cooldown boundary", MARK); return;
        }
        helper.succeed();
    }

    @GameTest(template = "empty3x3x3", batch = "independent_enchantments")
    public static void lossOfEligibilityCancelsAndRestartsWarmup(GameTestHelper helper) {
        var state = new CloudLineState();
        var random = new CountingRandom(0.0D, false);
        update(state, 0, true, 1, random);
        update(state, 1199, false, 1, random);
        update(state, 1200, true, 1, random);
        update(state, 2398, true, 1, random);
        if (random.rolls != 0) { helper.fail("Time without valid cloud rendering must not count toward a new attempt", MARK); return; }
        update(state, 2399, true, 1, random);
        update(state, 2400, false, 1, random);
        if (state.active() || random.rolls != 1) { helper.fail("Ineligible contexts must cancel immediately", MARK); return; }
        helper.succeed();
    }

    @GameTest(template = "empty3x3x3", batch = "independent_enchantments")
    public static void invalidChanceAndRollsNeverAllocateClouds(GameTestHelper helper) {
        for (double chance : new double[] {0, -1, Double.NaN, Double.POSITIVE_INFINITY}) {
            var state = new CloudLineState();
            var random = new CountingRandom(0, false);
            update(state, 0, true, chance, random);
            update(state, 1200, true, chance, random);
            if (state.active() || random.rolls != 0) { helper.fail("Invalid or disabled chance must not consume RNG", MARK); return; }
        }
        for (double roll : new double[] {-1, 1, Double.NaN, Double.POSITIVE_INFINITY, 0.02D}) {
            var state = new CloudLineState();
            var random = new CountingRandom(roll, false);
            update(state, 0, true, 0.02D, random);
            update(state, 1200, true, 0.02D, random);
            if (state.active() || random.rolls != 1 || random.shapes != 0) {
                helper.fail("Invalid or failing roll must not choose shapes or create clouds", MARK); return;
            }
        }
        helper.succeed();
    }

    @GameTest(template = "empty3x3x3", batch = "independent_enchantments")
    public static void worldUnloadAndClockRollbackDiscardCloudState(GameTestHelper helper) {
        var state = armed(false);
        state.clear();
        var random = new CountingRandom(0, true);
        update(state, 5, true, 1, random);
        update(state, 1204, true, 1, random);
        if (state.active()) { helper.fail("A new world requires a fresh warmup", MARK); return; }
        update(state, 1205, true, 1, random);
        if (!state.active()) { helper.fail("Old-world cooldown must not cross world unload", MARK); return; }
        state.advance(1204);
        if (state.active()) { helper.fail("A reversed clock must clear all active geometry", MARK); return; }
        update(state, 2404, true, 1, random);
        state.advance(Long.MAX_VALUE);
        if (state.active()) { helper.fail("A large forward jump must expire the line", MARK); return; }
        update(state, Long.MIN_VALUE, true, 1, random);
        update(state, Long.MIN_VALUE + 1200, true, 1, random);
        state.advance(Long.MAX_VALUE);
        if (state.active()) { helper.fail("Elapsed arithmetic must also survive overflow", MARK); return; }
        helper.succeed();
    }

    @GameTest(template = "empty3x3x3", batch = "independent_enchantments")
    public static void activeCloudsStayWorldAnchoredInsteadOfFollowingCamera(GameTestHelper helper) {
        var state = armed(false);
        state.advance(1300);
        var before = state.snapshot(0);
        var random = new CountingRandom(0, true);
        state.update(1301, true, 10000, -10000, 1, 0, 1, random, random);
        var after = state.snapshot(0);
        if (Math.abs(after.get(0).x() - before.get(0).x() + 0.03D) > 1.0E-8
                || after.get(0).z() != before.get(0).z() || random.rolls != 0) {
            helper.fail("Turning or moving the camera cannot drag, rotate or reroll an active cloud line", MARK); return;
        }
        helper.succeed();
    }

    @GameTest(template = "empty3x3x3", batch = "independent_enchantments")
    public static void snapshotsAreFiniteImmutableAndBoundedForEntireAnimation(GameTestHelper helper) {
        var state = armed(false);
        var snapshot = state.snapshot(0);
        try {
            snapshot.clear();
            helper.fail("Render snapshots must not expose mutable state", MARK); return;
        } catch (UnsupportedOperationException expected) {
            // Expected: callers cannot retain and mutate the animation's state.
        }
        for (int tick = 1200; tick <= 3000; tick++) {
            state.advance(tick);
            var clouds = state.snapshot(0.5F);
            if (clouds.size() > 5) { helper.fail("At most five cloud geometries may exist", MARK); return; }
            for (var cloud : clouds) {
                if (!Double.isFinite(cloud.x()) || !Double.isFinite(cloud.z())
                        || cloud.alpha() < 0 || cloud.alpha() > 0.8F) {
                    helper.fail("Geometry and opacity must stay finite and bounded", MARK); return;
                }
            }
        }
        if (state.active() || snapshot.get(0).alpha() != 0) {
            helper.fail("Old snapshots must remain independent while live state expires", MARK); return;
        }
        helper.succeed();
    }

    private static CloudLineState armed(boolean reversed) {
        var state = new CloudLineState();
        var random = new CountingRandom(0, reversed);
        update(state, 0, true, 1, random);
        update(state, 1200, true, 1, random);
        return state;
    }

    private static void update(CloudLineState state, long tick, boolean eligible, double chance, CountingRandom random) {
        state.update(tick, eligible, 0, 0, 0, 1, chance, random, random);
    }

    private static final class CountingRandom implements DoubleSupplier, BooleanSupplier {
        private final double roll;
        private final boolean reversed;
        private int rolls;
        private int shapes;
        private CountingRandom(double roll, boolean reversed) { this.roll = roll; this.reversed = reversed; }
        @Override public double getAsDouble() { rolls++; return roll; }
        @Override public boolean getAsBoolean() { shapes++; return reversed; }
    }
}
