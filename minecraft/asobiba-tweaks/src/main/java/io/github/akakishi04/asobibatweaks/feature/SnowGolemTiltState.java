package io.github.akakishi04.asobibatweaks.feature;

import java.util.HashMap;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.UUID;
import java.util.function.BooleanSupplier;
import java.util.function.DoubleSupplier;

/**
 * Observer-local cosmetic state, deliberately independent of client and world classes.
 * A tilt is prepared out of sight, revealed unchanged, and forgotten on looking away.
 * Callers own eligibility and gaze checks and reset observation on camera/pause changes.
 * All calls belong to the observer's game thread.
 */
public final class SnowGolemTiltState {
    public static final int MAX_TRACKED_GOLEMS = 32;
    public static final int CHANCE_INTERVAL_TICKS = 200;
    public static final int UNSEEN_LIFETIME_TICKS = 600;
    public static final int SEEN_LIFETIME_TICKS = 1200;
    public static final int GOLEM_COOLDOWN_TICKS = 12000;
    public static final int OBSERVER_COOLDOWN_TICKS = 6000;
    public static final double DEFAULT_CHANCE = 0.01D;
    public static final float TILT_DEGREES = 6.0F;

    private final Map<UUID, Entry> entries = new HashMap<>();
    private UUID activeId;
    private boolean clockInitialized;
    private long currentTick;
    private boolean observerCoolingDown;
    private long observerLastSuccess;

    /** Advances the local game clock, expiring old tilts even when no golems are updated. */
    public void tick(long observationTick) {
        if (clockInitialized && observationTick < currentTick) {
            clear();
        }
        clockInitialized = true;
        currentTick = observationTick;
        if (activeId == null) {
            return;
        }
        Entry active = entries.get(activeId);
        if (active == null) {
            activeId = null;
        } else if (active.seen
                ? elapsed(currentTick, active.seenAt, SEEN_LIFETIME_TICKS)
                : elapsed(currentTick, active.armedAt, UNSEEN_LIFETIME_TICKS)) {
            cancel(activeId);
        }
    }

    /**
     * Observes one loaded golem on a game tick. Randomness is requested only for a due,
     * eligible, off-gaze attempt; the sign is sampled only on success. Duplicate calls
     * cannot repeat a roll in the same interval. New IDs fail closed at the cache limit.
     */
    public void update(UUID id, long observationTick, boolean eligible, boolean looking,
            double chance, DoubleSupplier roll, BooleanSupplier positiveSign) {
        Objects.requireNonNull(id, "id");
        tick(observationTick);
        Entry entry = entries.get(id);
        if (entry == null) {
            if (!eligible || entries.size() >= MAX_TRACKED_GOLEMS) {
                return;
            }
            entry = new Entry(currentTick);
            entries.put(id, entry);
        }
        observe(id, eligible, looking);
        if (!eligible || looking || activeId != null
                || (entry.coolingDown && !elapsed(currentTick, entry.lastSuccess, GOLEM_COOLDOWN_TICKS))
                || (observerCoolingDown && !elapsed(currentTick, observerLastSuccess, OBSERVER_COOLDOWN_TICKS))
                || !elapsed(currentTick, entry.lastAttempt, CHANCE_INTERVAL_TICKS)) {
            return;
        }

        // Creation sets lastAttempt to the observation tick, providing the initial warmup.
        // Even a disabled/invalid chance consumes this interval rather than spinning rolls.
        entry.lastAttempt = currentTick;
        double boundedChance = Double.isFinite(chance) ? Math.max(0.0D, Math.min(1.0D, chance)) : 0.0D;
        if (boundedChance == 0.0D) {
            return;
        }
        double sampled = Objects.requireNonNull(roll, "roll").getAsDouble();
        if (!Double.isFinite(sampled) || sampled < 0.0D || sampled >= 1.0D || sampled >= boundedChance) {
            return;
        }

        entry.angle = Objects.requireNonNull(positiveSign, "positiveSign").getAsBoolean()
                ? TILT_DEGREES : -TILT_DEGREES;
        entry.armedAt = currentTick;
        entry.seen = false;
        entry.coolingDown = true;
        entry.lastSuccess = currentTick;
        activeId = id;
        observerCoolingDown = true;
        observerLastSuccess = currentTick;
    }

    /**
     * Applies actual frame visibility to an existing armed tilt without creating entries,
     * advancing time, or sampling randomness. Same-tick gaze changes are intentional.
     */
    public void observe(UUID id, boolean eligible, boolean looking) {
        Entry entry = entries.get(id);
        if (entry == null || entry.angle == 0.0F) {
            return;
        }
        if (!eligible || (entry.seen && !looking)) {
            cancel(id);
        } else if (looking && !entry.seen) {
            entry.seen = true;
            entry.seenAt = currentTick;
        }
    }

    /** Returns a prepared angle; the caller must separately gate rendering on eligibility. */
    public float tiltDegrees(UUID id) {
        Entry entry = entries.get(id);
        return entry == null ? 0.0F : entry.angle;
    }

    /** Immediately restores neutral without shortening either success cooldown. */
    public void cancel(UUID id) {
        Entry entry = entries.get(id);
        if (entry != null) {
            entry.angle = 0.0F;
            entry.seen = false;
        }
        if (Objects.equals(activeId, id)) {
            activeId = null;
        }
    }

    /** Drops unloaded/removed IDs without retaining the caller's set or any world object. */
    public void retain(Set<UUID> aliveLoaded) {
        Objects.requireNonNull(aliveLoaded, "aliveLoaded");
        entries.keySet().removeIf(id -> !aliveLoaded.contains(id));
        if (activeId != null && !entries.containsKey(activeId)) {
            activeId = null;
        }
    }

    /**
     * Restarts observation after a pause/menu/camera change in the same world. Successful
     * rolls keep both cooldowns, so toggling the view cannot farm another prepared tilt.
     */
    public void resetObservation() {
        for (Entry entry : entries.values()) {
            entry.angle = 0.0F;
            entry.seen = false;
            entry.lastAttempt = currentTick;
        }
        activeId = null;
    }

    /** Fully resets observation, angles, and cooldowns after leaving/changing the world. */
    public void clear() {
        entries.clear();
        activeId = null;
        clockInitialized = false;
        currentTick = 0L;
        observerCoolingDown = false;
        observerLastSuccess = 0L;
    }

    public int size() {
        return entries.size();
    }

    private static boolean elapsed(long now, long since, int duration) {
        // A nonnegative clock difference can overflow only after an enormous forward jump.
        long difference = now - since;
        return now >= since && (difference < 0L || difference >= duration);
    }

    private static final class Entry {
        private long lastAttempt;
        private float angle;
        private long armedAt;
        private boolean seen;
        private long seenAt;
        private boolean coolingDown;
        private long lastSuccess;

        private Entry(long firstObservedTick) {
            lastAttempt = firstObservedTick;
        }
    }
}
