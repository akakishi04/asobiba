package io.github.akakishi04.asobibatweaks.feature;

import java.util.HashSet;
import java.util.function.BooleanSupplier;
import java.util.function.DoubleSupplier;

/** Standalone pure-Java regression runner; no Minecraft bootstrap or graphics context needed. */
public final class CloudLineStateTest {
    private static int assertions;

    public static void main(String[] args) {
        warmupAndRandomBudget();
        chanceAndInputBounds();
        arrangementAndInterpolation();
        dispersalAndExpiry();
        cancellationAndCooldown();
        contextAndClockBoundaries();
        snapshotIsolationAndBoundedLifetime();
        System.out.println("CloudLineStateTest passed: " + assertions + " assertions");
    }

    private static void warmupAndRandomBudget() {
        var state = new CloudLineState();
        var random = new CountingRandom(0.8D, false);
        update(state, 0, true, 0.02D, random);
        update(state, 1199, true, 0.02D, random);
        check(random.rolls == 0 && !state.active(), "initial warmup");
        update(state, 1200, true, 0.02D, random);
        update(state, 1200, true, 0.02D, random);
        update(state, 2399, true, 0.02D, random);
        check(random.rolls == 1 && random.shapes == 0, "failed interval and duplicate call");
        update(state, 2400, true, 0.02D, random);
        check(random.rolls == 2 && !state.active(), "next exact interval");
        update(state, 3000, false, 1.0D, random);
        update(state, 4199, true, 1.0D, random);
        check(random.rolls == 2, "ineligible time restarts warmup");
        update(state, 4200, true, 1.0D, random);
        check(state.active() && random.rolls == 3 && random.shapes == 1, "one successful shape");
        for (int tick = 4201; tick < 6000; tick++) update(state, tick, true, 1.0D, random);
        check(random.rolls == 3 && random.shapes == 1, "active row never rerolls");
    }

    private static void chanceAndInputBounds() {
        for (double chance : new double[] {0.0D, -1.0D, Double.NaN, Double.POSITIVE_INFINITY}) {
            var state = new CloudLineState();
            var random = new CountingRandom(0.0D, true);
            update(state, 0, true, chance, random);
            update(state, 1200, true, chance, random);
            check(!state.active() && random.rolls == 0, "invalid chance consumes no random");
        }
        for (double sample : new double[] {-1.0D, Double.NaN, Double.POSITIVE_INFINITY, 1.0D, 0.02D}) {
            var state = new CloudLineState();
            var random = new CountingRandom(sample, true);
            update(state, 0, true, 0.02D, random);
            update(state, 1200, true, 0.02D, random);
            check(!state.active() && random.rolls == 1 && random.shapes == 0, "invalid/failing random");
        }
        var state = new CloudLineState();
        var random = new CountingRandom(0.9D, false);
        update(state, 0, true, 20.0D, random);
        update(state, 1200, true, 20.0D, random);
        check(state.active(), "chance clamped above one");
        for (double bad : new double[] {Double.NaN, Double.POSITIVE_INFINITY}) {
            state.update(1300, true, bad, 0.0D, 0.0D, 1.0D, 1.0D, random, random);
            check(!state.active(), "invalid camera cancels");
            state.update(2500, true, 0.0D, 0.0D, bad, 1.0D, 1.0D, random, random);
            check(!state.active(), "invalid heading cancels");
        }
        state.update(5000, true, 0, 0, 0, 0, 1, random, random);
        check(!state.active(), "zero heading cancels");
    }

    private static void arrangementAndInterpolation() {
        var state = armed(false);
        var initial = state.snapshot(0.0F);
        check(initial.size() == 5 && initial.get(0).alpha() == 0.0F, "bounded fade-in");
        var sizes = new HashSet<Double>();
        for (int i = 0; i < initial.size(); i++) {
            sizes.add(initial.get(i).size());
            check(initial.get(i).z() == 96.0D, "regular straight row");
            if (i != 0) close(initial.get(i - 1).x() - initial.get(i).x(), 48.0D, "regular spacing");
        }
        check(sizes.size() == 5, "five different sizes");
        state.advance(1300);
        var full = state.snapshot(0.0F);
        check(full.get(0).alpha() == 0.8F, "vanilla-like full opacity");
        close(full.get(0).x() - initial.get(0).x(), -3.0D, "normal cloud speed and direction");
        close(state.snapshot(0.5F).get(0).x() - full.get(0).x(), -0.015D, "partial tick smooth drift");
        close(state.snapshot(Float.NaN).get(0).x(), full.get(0).x(), "NaN partial tick fails closed");
        close(state.snapshot(-100.0F).get(0).x(), full.get(0).x(), "negative partial clamp");
        close(state.snapshot(999.0F).get(0).x() - full.get(0).x(), -0.03D, "large partial clamp");
        var reversed = armed(true).snapshot(0);
        for (int i = 0; i < 5; i++) close(initial.get(i).size(), reversed.get(4 - i).size(), "stable shape reversal");
        var random = new CountingRandom(0.0D, false);
        state.update(1301, true, 10000, -10000, 1, 0, 1, random, random);
        close(state.snapshot(0).get(0).x() - full.get(0).x(), -0.03D, "active row does not follow camera");
        close(state.snapshot(0).get(0).z(), full.get(0).z(), "active row does not rotate with camera");
        check(random.rolls == 0, "camera motion cannot reroll active row");
    }

    private static void dispersalAndExpiry() {
        var state = armed(false);
        state.advance(2400);
        var aligned = state.snapshot(0);
        for (var cloud : aligned) close(cloud.z(), 96.0D, "alignment until dispersal boundary");
        state.advance(2700);
        var dispersed = state.snapshot(0);
        check(dispersed.get(0).z() != dispersed.get(1).z(), "clouds separate independently");
        check(dispersed.get(0).alpha() > 0 && dispersed.get(0).alpha() < aligned.get(0).alpha(), "gentle dispersal fade");
        state.advance(2999);
        check(state.active() && !state.snapshot(0).isEmpty(), "present through final whole tick");
        check(state.snapshot(1).isEmpty(), "interpolated exact expiry");
        state.advance(3000);
        check(!state.active() && state.snapshot(0).isEmpty(), "exact hard expiry");
    }

    private static void cancellationAndCooldown() {
        var state = armed(false);
        state.advance(1300);
        state.resetObservation();
        check(!state.active() && state.snapshot(0).isEmpty(), "pause/settings/camera cancellation");
        var random = new CountingRandom(0.0D, true);
        update(state, 2500, true, 1, random);
        update(state, 13199, true, 1, random);
        check(!state.active() && random.rolls == 0, "cancellation preserves success cooldown");
        update(state, 13200, true, 1, random);
        check(state.active() && random.rolls == 1 && random.shapes == 1, "cooldown exact boundary");
        update(state, 13300, false, 1, random);
        check(!state.active(), "eligibility loss cancels active cloud");
    }

    private static void contextAndClockBoundaries() {
        var state = armed(false);
        state.clear();
        var random = new CountingRandom(0, false);
        update(state, 5, true, 1, random);
        update(state, 1204, true, 1, random);
        check(!state.active() && random.rolls == 0, "world reset requires fresh warmup");
        update(state, 1205, true, 1, random);
        check(state.active(), "new world has no inherited cooldown");
        state.advance(1204);
        check(!state.active(), "clock rollback clears");
        update(state, 2403, true, 1, random);
        check(random.rolls == 1, "rollback warmup");
        update(state, 2404, true, 1, random);
        check(state.active() && random.rolls == 2, "rollback recovery");
        state.advance(Long.MAX_VALUE);
        check(!state.active(), "forward jump expires");
        update(state, Long.MIN_VALUE, true, 1, random);
        update(state, Long.MIN_VALUE + 1200, true, 1, random);
        check(state.active(), "clock wrap recovery");
        state.advance(Long.MAX_VALUE);
        check(!state.active(), "overflow-safe elapsed expiry");
    }

    private static void snapshotIsolationAndBoundedLifetime() {
        var state = armed(false);
        var before = state.snapshot(0);
        try {
            before.clear();
            throw new AssertionError("snapshot must be immutable");
        } catch (UnsupportedOperationException expected) {
            assertions++;
        }
        state.advance(1300);
        check(before.get(0).alpha() == 0.0F && state.snapshot(0).get(0).alpha() == 0.8F, "snapshot independent");
        for (int tick = 1300; tick <= 3000; tick++) {
            state.advance(tick);
            var snapshot = state.snapshot(0.5F);
            check(snapshot.size() <= 5, "memory/geometry bound");
            for (var cloud : snapshot) {
                check(Double.isFinite(cloud.x()) && Double.isFinite(cloud.z()) && cloud.alpha() >= 0
                        && cloud.alpha() <= 0.8F && cloud.size() >= 12 && cloud.size() <= 36,
                        "finite bounded geometry");
            }
        }
        check(!state.active(), "long run fully drained");
    }

    private static CloudLineState armed(boolean reverse) {
        var state = new CloudLineState();
        var random = new CountingRandom(0, reverse);
        update(state, 0, true, 1, random);
        update(state, 1200, true, 1, random);
        check(state.active(), "fixture armed");
        return state;
    }

    private static void update(CloudLineState state, long tick, boolean eligible, double chance, CountingRandom random) {
        state.update(tick, eligible, 0, 0, 0, 1, chance, random, random);
    }

    private static void close(double actual, double expected, String name) {
        check(Math.abs(actual - expected) < 1.0E-8, name + ": " + actual + " versus " + expected);
    }

    private static void check(boolean condition, String name) {
        assertions++;
        if (!condition) throw new AssertionError(name);
    }

    private static final class CountingRandom implements DoubleSupplier, BooleanSupplier {
        private final double roll;
        private final boolean reverse;
        private int rolls;
        private int shapes;
        private CountingRandom(double roll, boolean reverse) { this.roll = roll; this.reverse = reverse; }
        @Override public double getAsDouble() { rolls++; return roll; }
        @Override public boolean getAsBoolean() { shapes++; return reverse; }
    }
}
