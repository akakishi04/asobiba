package io.github.akakishi04.asobibatweaks.feature;

import java.util.ArrayList;
import java.util.List;
import java.util.Objects;
import java.util.function.BooleanSupplier;
import java.util.function.DoubleSupplier;

/** Pure observer-local cloud animation; no world, entities, packets, persistence or gameplay RNG. */
public final class CloudLineState {
    public static final int CLOUD_COUNT = 5;
    public static final int CHANCE_INTERVAL_TICKS = 1200;
    public static final int SUCCESS_COOLDOWN_TICKS = 12000;
    public static final int FADE_IN_TICKS = 100;
    public static final int ALIGNED_TICKS = 1200;
    public static final int DISPERSAL_TICKS = 600;
    public static final int LIFETIME_TICKS = ALIGNED_TICKS + DISPERSAL_TICKS;
    public static final double DEFAULT_CHANCE = 0.02D;
    public static final double DRIFT_PER_TICK = -0.03D;
    public static final double SPACING = 48.0D;
    public static final double SPAWN_DISTANCE = 96.0D;
    private static final double[] SIZES = {18.0D, 30.0D, 12.0D, 36.0D, 24.0D};
    private static final double[] SCATTER = {-24.0D, 16.0D, -8.0D, -18.0D, 26.0D};

    private boolean initialized;
    private long tick;
    private long lastAttempt;
    private boolean coolingDown;
    private long lastSuccess;
    private Formation formation;

    /** Only due, eligible attempts consume observer-owned random values. */
    public void update(long observationTick, boolean eligible, double cameraX, double cameraZ,
            double forwardX, double forwardZ, double chance, DoubleSupplier roll, BooleanSupplier reverse) {
        advance(observationTick);
        double forwardLength = Math.hypot(forwardX, forwardZ);
        if (!eligible || !Double.isFinite(cameraX) || !Double.isFinite(cameraZ)
                || !Double.isFinite(forwardLength) || forwardLength < 0.001D) {
            resetObservation();
            return;
        }
        if (formation != null || !elapsed(tick, lastAttempt, CHANCE_INTERVAL_TICKS)
                || coolingDown && !elapsed(tick, lastSuccess, SUCCESS_COOLDOWN_TICKS)) {
            return;
        }
        lastAttempt = tick;
        double boundedChance = Double.isFinite(chance) ? Math.clamp(chance, 0.0D, 1.0D) : 0.0D;
        if (boundedChance == 0.0D) return;
        double sample = Objects.requireNonNull(roll, "roll").getAsDouble();
        if (!Double.isFinite(sample) || sample < 0.0D || sample >= 1.0D || sample >= boundedChance) return;
        boolean reversed = Objects.requireNonNull(reverse, "reverse").getAsBoolean();
        double forwardUnitX = forwardX / forwardLength;
        double forwardUnitZ = forwardZ / forwardLength;
        formation = new Formation(tick, cameraX + forwardUnitX * SPAWN_DISTANCE,
                cameraZ + forwardUnitZ * SPAWN_DISTANCE, -forwardUnitZ, forwardUnitX, reversed);
        coolingDown = true;
        lastSuccess = tick;
    }

    /** Updates expiry even if the caller is not attempting another formation. */
    public void advance(long observationTick) {
        if (initialized && observationTick < tick) clear();
        tick = observationTick;
        if (!initialized) {
            initialized = true;
            lastAttempt = tick;
        }
        if (formation != null && elapsed(tick, formation.started, LIFETIME_TICKS)) formation = null;
    }

    /** Five world-anchored squares, never camera-following. Alpha and motion are frame-interpolated. */
    public List<Cloud> snapshot(float partialTick) {
        if (formation == null) return List.of();
        double partial = Float.isFinite(partialTick) ? Math.clamp((double) partialTick, 0.0D, 1.0D) : 0.0D;
        double age = Math.max(0.0D, (double) (tick - formation.started)) + partial;
        if (age >= LIFETIME_TICKS) return List.of();
        double dispersal = smooth((age - ALIGNED_TICKS) / DISPERSAL_TICKS);
        float alpha = (float) (0.8D * smooth(age / FADE_IN_TICKS) * (1.0D - dispersal));
        List<Cloud> clouds = new ArrayList<>(CLOUD_COUNT);
        for (int slot = 0; slot < CLOUD_COUNT; slot++) {
            int variant = formation.reversed ? CLOUD_COUNT - slot - 1 : slot;
            double along = (slot - (CLOUD_COUNT - 1) / 2.0D) * SPACING;
            double spread = SCATTER[variant] * dispersal;
            // Extra separation is small, slow and only begins after the regular line has lingered.
            double x = formation.x + formation.axisX * along + DRIFT_PER_TICK * age
                    - formation.axisZ * spread;
            double z = formation.z + formation.axisZ * along + formation.axisX * spread;
            clouds.add(new Cloud(x, z, SIZES[variant], alpha));
        }
        return List.copyOf(clouds);
    }

    /** Pause/settings/camera changes cancel immediately but preserve the success cooldown. */
    public void resetObservation() {
        formation = null;
        lastAttempt = tick;
    }

    /** Leaving the world clears all observer state. */
    public void clear() {
        initialized = false;
        tick = 0L;
        lastAttempt = 0L;
        coolingDown = false;
        lastSuccess = 0L;
        formation = null;
    }

    public boolean active() {
        return formation != null;
    }

    private static boolean elapsed(long now, long since, int duration) {
        long difference = now - since;
        return now >= since && (difference < 0L || difference >= duration);
    }

    private static double smooth(double value) {
        double bounded = Math.clamp(value, 0.0D, 1.0D);
        return bounded * bounded * (3.0D - 2.0D * bounded);
    }

    public record Cloud(double x, double z, double size, float alpha) {}

    private record Formation(long started, double x, double z, double axisX, double axisZ, boolean reversed) {}
}
