package io.github.akakishi04.asobibatweaks.feature;

import java.util.Locale;

/** Standalone, deterministic HUD lifecycle tests: no Minecraft bootstrap or graphics required. */
public final class DailyPlayTimeHudStateTest {
    private static final long SECOND = 1_000_000_000L;
    private static int assertions;

    public static void main(String[] args) {
        formatting();
        recentSnapshotInterpolation();
        staleSnapshotsNeverInventTime();
        integratedPauseAndServerPause();
        connectionWorldAndPacketIdentity();
        authoritativeResetAndSettingsChanges();
        malformedPayloadsAndClockBoundaries();
        System.out.println("DailyPlayTimeHudStateTest passed: " + assertions + " assertions");
    }

    private static void formatting() {
        eq("00:00:00", DailyPlayTimeHudState.formatCountdown(0), "zero");
        eq("00:00:01", DailyPlayTimeHudState.formatCountdown(1), "positive fraction ceilings");
        eq("00:00:01", DailyPlayTimeHudState.formatCountdown(999), "sub-second ceiling");
        eq("00:00:01", DailyPlayTimeHudState.formatCountdown(1000), "exact second");
        eq("00:01:00", DailyPlayTimeHudState.formatCountdown(59_001), "minute ceiling");
        eq("01:00:00", DailyPlayTimeHudState.formatCountdown(3_600_000), "hour rollover");
        eq("02:00:00", DailyPlayTimeHudState.formatCountdown(7_200_000), "default allowance");
        eq("24:00:00", DailyPlayTimeHudState.formatCountdown(86_400_000), "largest daily cap");
        eq("00:00:00", DailyPlayTimeHudState.formatCountdown(Long.MIN_VALUE), "negative guard");
        eq("24:00:00", DailyPlayTimeHudState.formatCountdown(Long.MAX_VALUE), "overflow guard");
        Locale before = Locale.getDefault();
        try {
            Locale.setDefault(Locale.forLanguageTag("ar"));
            eq("01:02:03", DailyPlayTimeHudState.formatCountdown(3_723_000), "stable ASCII digits");
        } finally {
            Locale.setDefault(before);
        }
    }

    private static void recentSnapshotInterpolation() {
        var state = active(120_000, false, 0);
        check(state.visible() && state.playedDays() == 7 && !state.paused(), "enabled snapshot");
        state.advance(SECOND, false);
        check(state.remainingMillis() == 119_000, "one real second, independent of tick count");
        state.advance(SECOND, false);
        check(state.remainingMillis() == 119_000, "duplicate renders do not consume twice");
        state.advance(SECOND + 500_000_000L, false);
        check(state.remainingMillis() == 118_500, "smooth subsecond interpolation");
        check(state.limitMillis() == 120_000 && state.resetAtEpochMillis() == 100_000, "server metadata kept intact");
        check(!state.stale(), "recent snapshot");
    }

    private static void staleSnapshotsNeverInventTime() {
        var state = active(120_000, false, 0);
        state.advance(3 * SECOND, false);
        check(state.remainingMillis() == 117_000 && state.stale(), "interpolation ends at three seconds");
        state.advance(3600 * SECOND, false);
        check(state.remainingMillis() == 117_000 && state.stale(), "packet gap freezes estimate");
        check(state.playedDays() == 7 && state.resetAtEpochMillis() == 100_000, "client cannot create a next date");
        var exhausted = active(1500, false, 0);
        exhausted.advance(2 * SECOND, false);
        check(exhausted.remainingMillis() == 0 && exhausted.visible(), "zero remains visible until server handles expiry");
        exhausted.advance(3600 * SECOND, false);
        check(exhausted.remainingMillis() == 0 && exhausted.playedDays() == 7, "no automatic fresh budget after zero");
    }

    private static void integratedPauseAndServerPause() {
        var state = active(120_000, false, 0);
        state.advance(SECOND, false);
        state.advance(SECOND, true);
        state.advance(2 * SECOND, true);
        check(state.remainingMillis() == 119_000 && state.paused(), "local pause excludes paused interval");
        state.advance(2 * SECOND, false);
        state.advance(3 * SECOND, false);
        check(state.remainingMillis() == 118_000 && !state.paused(), "local resume does not charge pause");
        var serverPaused = active(120_000, true, 0);
        serverPaused.advance(2 * SECOND, false);
        check(serverPaused.remainingMillis() == 120_000 && serverPaused.paused(), "server pause authoritative despite local unpause");
        serverPaused.advance(500 * SECOND, false);
        check(serverPaused.remainingMillis() == 120_000, "long server pause never drains estimate");
        var c = new Object();
        var w = new Object();
        state.context(c, w);
        state.accept(c, true, 8, 90_000, 120_000, 200_000, true, 10 * SECOND);
        state.advance(11 * SECOND, false);
        check(state.remainingMillis() == 90_000, "paused fresh snapshot freezes at server amount");
        state.accept(c, true, 8, 89_000, 120_000, 200_000, false, 11 * SECOND);
        state.advance(12 * SECOND, false);
        check(state.remainingMillis() == 88_000 && !state.paused(), "authoritative unpause resumes");
    }

    private static void connectionWorldAndPacketIdentity() {
        var state = new DailyPlayTimeHudState();
        var c1 = new Object();
        var c2 = new Object();
        var w1 = new Object();
        var w2 = new Object();
        check(!state.accept(c1, true, 1, 100, 1000, 10_000, false, 0), "packet before live world rejected");
        state.context(c1, w1);
        check(state.accept(c1, true, 1, 100, 1000, 10_000, false, 0), "matching connection accepted");
        state.context(c1, w1);
        check(state.visible(), "same context retains snapshot");
        state.context(c1, w2);
        check(!state.visible() && state.playedDays() == 0, "dimension/world switch clears before next server snapshot");
        state.accept(c1, true, 2, 90, 1000, 10_000, false, 0);
        check(state.visible() && state.playedDays() == 2, "fresh dimension snapshot");
        state.context(c2, w2);
        check(!state.visible(), "different connection clears even if world name could match");
        check(!state.accept(c1, true, 99, 900, 1000, 10_000, false, 0), "late old-connection packet rejected");
        check(!state.visible(), "late packet cannot resurrect old HUD");
        state.accept(c2, true, 3, 80, 1000, 10_000, false, 0);
        state.context(null, null);
        check(!state.visible() && state.remainingMillis() == 0, "logout clears all display data");
        state.context(c2, w2);
        check(!state.visible(), "relogin awaits fresh authority");
        state.clear();
        check(!state.accept(c2, true, 1, 100, 1000, 10_000, false, 0), "explicit logout blocks queued packet");
    }

    private static void authoritativeResetAndSettingsChanges() {
        var state = new DailyPlayTimeHudState();
        var c = new Object();
        state.context(c, new Object());
        state.accept(c, true, 12, 1000, 120_000, 100_000, false, 0);
        state.advance(2 * SECOND, false);
        check(state.remainingMillis() == 0, "old date depleted");
        state.accept(c, true, 13, 120_000, 120_000, 86_500_000, false, 2 * SECOND);
        check(state.remainingMillis() == 120_000 && state.playedDays() == 13, "server-only calendar rollover replaces snapshot");
        check(!state.stale(), "new reset snapshot clears stale status");
        state.accept(c, true, 13, 60_000, 60_000, 86_500_000, false, 2 * SECOND);
        check(state.limitMillis() == 60_000 && state.remainingMillis() == 60_000, "changed setting replaces allowance");
        state.accept(c, false, 13, 60_000, 60_000, 86_500_000, false, 2 * SECOND);
        check(!state.visible() && state.playedDays() == 0, "disabled rule hides immediately");
        state.accept(c, true, 13, 59_000, 60_000, 86_500_000, false, 3 * SECOND);
        check(state.visible() && state.remainingMillis() == 59_000, "re-enable uses server's preserved allowance");
    }

    private static void malformedPayloadsAndClockBoundaries() {
        var state = new DailyPlayTimeHudState();
        var c = new Object();
        state.context(c, new Object());
        long[][] invalid = {
                {-1, 1000, 1000, 1}, {1, -1, 1000, 1}, {1, 1001, 1000, 1},
                {1, 0, 0, 1}, {1, 1, -1, 1}, {1, 1, Long.MAX_VALUE, 1},
                {1, 1, 1000, 0}, {1, 1, 1000, -1}};
        for (long[] s : invalid) {
            state.accept(c, true, s[0], s[1], s[2], s[3], false, 0);
            check(!state.visible(), "malformed snapshot hidden");
        }
        state.accept(c, true, Long.MAX_VALUE, 86_400_000, 86_400_000, Long.MAX_VALUE, false, 0);
        check(state.visible() && state.playedDays() == Long.MAX_VALUE, "large day count remains a long");
        state.advance(-SECOND, false);
        check(state.stale() && state.remainingMillis() == 86_400_000, "regressed monotonic clock cannot add budget");
        state.advance(SECOND, false);
        check(state.remainingMillis() == 86_400_000, "clock anomaly waits for a new snapshot");
        long start = Long.MAX_VALUE - SECOND / 2;
        state.accept(c, true, 1, 60_000, 60_000, 100_000, false, start);
        state.advance(start + SECOND, false);
        check(state.remainingMillis() == 59_000, "normal nanoTime signed wrap uses elapsed subtraction");
        state.accept(c, true, 1, 60_000, 60_000, 100_000, false, 0);
        state.advance(Long.MAX_VALUE, false);
        check(state.remainingMillis() == 57_000 && state.stale(), "enormous packet gap stays bounded");
    }

    private static DailyPlayTimeHudState active(long remaining, boolean paused, long now) {
        var state = new DailyPlayTimeHudState();
        var c = new Object();
        state.context(c, new Object());
        state.accept(c, true, 7, remaining, 120_000, 100_000, paused, now);
        return state;
    }

    private static void check(boolean condition, String message) {
        assertions++;
        if (!condition) throw new AssertionError(message);
    }

    private static void eq(String expected, String actual, String message) {
        check(expected.equals(actual), message + ": expected " + expected + ", got " + actual);
    }
}
