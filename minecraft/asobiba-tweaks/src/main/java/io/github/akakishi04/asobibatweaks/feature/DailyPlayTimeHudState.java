package io.github.akakishi04.asobibatweaks.feature;

import java.util.Locale;

/** Pure presentation state. Never grants time, advances calendar dates, or changes server data. */
public final class DailyPlayTimeHudState {
    public static final long MAX_INTERPOLATION_NANOS = 3_000_000_000L;
    public static final long MAX_LIMIT_MILLIS = 86_400_000L;
    private Object connection;
    private Object world;
    private boolean enabled;
    private boolean serverPaused;
    private boolean localPaused;
    private long playedDays;
    private long remainingMillis;
    private long limitMillis;
    private long resetAtEpochMillis;
    private long receivedNanos;
    private long lastNanos;
    private long elapsedNanos;
    private long ageNanos;

    /** Identity comparisons deliberately distinguish reconnects to the same named server/world. */
    public void context(Object currentConnection, Object currentWorld) {
        if (currentConnection == null || currentWorld == null
                || connection != currentConnection || world != currentWorld) {
            clear();
            connection = currentConnection;
            world = currentWorld;
        }
    }

    public void clear() {
        connection = null;
        world = null;
        enabled = false;
        serverPaused = false;
        localPaused = false;
        playedDays = remainingMillis = limitMillis = resetAtEpochMillis = 0;
        receivedNanos = lastNanos = elapsedNanos = ageNanos = 0;
    }

    public boolean accept(Object sourceConnection, boolean active, long days, long remaining,
            long limit, long resetAt, boolean paused, long nowNanos) {
        if (connection == null || world == null || sourceConnection != connection) return false;
        // Invalid snapshots fail closed cosmetically; they cannot affect enforcement.
        enabled = active && days >= 0 && limit > 0 && limit <= MAX_LIMIT_MILLIS
                && remaining >= 0 && remaining <= limit && resetAt > 0;
        if (!enabled) {
            playedDays = remainingMillis = limitMillis = resetAtEpochMillis = 0;
            serverPaused = false;
            return true;
        }
        playedDays = days;
        remainingMillis = remaining;
        limitMillis = limit;
        resetAtEpochMillis = resetAt;
        serverPaused = paused;
        receivedNanos = lastNanos = nowNanos;
        elapsedNanos = ageNanos = 0;
        return true;
    }

    /** Uses monotonic elapsed time only, capped to recent server updates. */
    public void advance(long nowNanos, boolean integratedGamePaused) {
        if (!enabled) {
            localPaused = integratedGamePaused;
            return;
        }
        long nextAge = nowNanos - receivedNanos;
        long step = nowNanos - lastNanos;
        if (nextAge < 0 || step < 0) {
            // Clock anomalies never add allowance or resume a stale countdown.
            ageNanos = MAX_INTERPOLATION_NANOS;
            localPaused = integratedGamePaused;
            return;
        }
        long boundedAge = Math.min(MAX_INTERPOLATION_NANOS, nextAge);
        if (!localPaused && !serverPaused && !integratedGamePaused) {
            elapsedNanos += Math.max(0, boundedAge - Math.min(MAX_INTERPOLATION_NANOS, ageNanos));
        }
        ageNanos = Math.max(ageNanos, nextAge);
        lastNanos = nowNanos;
        localPaused = integratedGamePaused;
    }

    public boolean visible() { return enabled && connection != null && world != null; }
    public boolean paused() { return serverPaused || localPaused; }
    public boolean stale() { return ageNanos >= MAX_INTERPOLATION_NANOS; }
    public long playedDays() { return playedDays; }
    public long limitMillis() { return limitMillis; }
    public long resetAtEpochMillis() { return resetAtEpochMillis; }
    public long remainingMillis() { return Math.max(0, remainingMillis - elapsedNanos / 1_000_000L); }

    /** Ceil to seconds so 1 ms remaining is not rendered as already exhausted. */
    public static String formatCountdown(long millis) {
        long safeMillis = Math.max(0, Math.min(MAX_LIMIT_MILLIS, millis));
        long seconds = safeMillis / 1000 + (safeMillis % 1000 == 0 ? 0 : 1);
        return String.format(Locale.ROOT, "%02d:%02d:%02d", seconds / 3600,
                (seconds / 60) % 60, seconds % 60);
    }
}
