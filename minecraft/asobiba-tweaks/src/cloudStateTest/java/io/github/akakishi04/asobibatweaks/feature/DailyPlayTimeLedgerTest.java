package io.github.akakishi04.asobibatweaks.feature;

import java.time.Instant;
import java.util.UUID;

/** Deterministic clock tests: no Minecraft bootstrap, waiting, wall-clock edits or client needed. */
public final class DailyPlayTimeLedgerTest {
    private static final UUID A = new UUID(0, 1);
    private static final UUID B = new UUID(0, 2);
    private static final long DAY = DailyPlayTimeLedger.DAY_MILLIS;
    private static final long START = Instant.parse("2026-10-10T03:00:00Z").toEpochMilli();
    private static final DailyPlayTimeLedger.Settings ON = new DailyPlayTimeLedger.Settings(true, 120 * 60_000L, 540);
    private static final DailyPlayTimeLedger.Settings OFF = new DailyPlayTimeLedger.Settings(false, ON.limitMillis(), 540);
    private static int assertions;

    public static void main(String[] args) {
        cumulativeRelogRestartAndOfflineDays();
        midnightSplitsOnlyActualPlay();
        pauseAndDisableExcludeElapsed();
        monotonicLagAndClockChanges();
        settingsChangesPreserveBudgetAndDays();
        identityAndWorldIsolation();
        boundedHistoryAndSnapshotIsolation();
        inspectionBeforeSettlement();
        duplicateJoinAndClockBounds();
        pathologicalLongIntervalIsBounded();
        System.out.println("DailyPlayTimeLedgerTest passed: " + assertions + " assertions");
    }

    private static void cumulativeRelogRestartAndOfflineDays() {
        var ledger = new DailyPlayTimeLedger();
        check(ledger.join(A, START, 0, ON, false).playedDays() == 0, "mere login is not play");
        var played = ledger.sample(A, START + 60_000, 60_000, ON, false);
        check(played.playedDays() == 1 && played.remainingMillis() == ON.limitMillis() - 60_000, "one played day");
        ledger.leave(A, START + 60_000, 60_000, ON, false);
        ledger.join(A, START + 600_000, 900_000, ON, false);
        var relog = ledger.sample(A, START + 630_000, 930_000, ON, false);
        check(relog.playedDays() == 1 && relog.remainingMillis() == ON.limitMillis() - 90_000, "same-date relog cumulative, offline excluded");
        ledger = DailyPlayTimeLedger.restore(ledger.saveState());
        check(ledger.onlinePlayers().isEmpty(), "restart has no online session");
        var restarted = ledger.join(A, START + 700_000, 1, ON, false);
        check(restarted.remainingMillis() == relog.remainingMillis(), "normal saved restart retains usage");
        ledger.leave(A, START + 700_000, 1, ON, false);
        var future = ledger.join(A, START + 5 * DAY, 4, ON, false);
        check(future.playedDays() == 1 && future.remainingMillis() == ON.limitMillis(), "skipped days not played");
        check(ledger.sample(A, START + 5 * DAY + 1, 5, ON, false).playedDays() == 2, "only actual next played date increments");
    }

    private static void midnightSplitsOnlyActualPlay() {
        long before = Instant.parse("2026-10-10T14:59:58Z").toEpochMilli();
        var ledger = new DailyPlayTimeLedger();
        var start = ledger.join(A, before, 0, ON, false);
        check(start.resetAtEpochMillis() == before + 2000, "default reset is Japanese midnight");
        var across = ledger.sample(A, before + 4000, 4000, ON, false);
        check(across.playedDays() == 2 && across.remainingMillis() == ON.limitMillis() - 2000, "active crossing splits midnight exactly");
        var dates = ledger.saveState().accounts().get(A).playedDates();
        check(dates.values().stream().mapToLong(Long::longValue).sum() == 4000, "split preserves elapsed total");
        ledger = new DailyPlayTimeLedger();
        ledger.join(A, before, 0, ON, false);
        var exact = ledger.sample(A, before + 2000, 2000, ON, false);
        check(exact.playedDays() == 1 && exact.remainingMillis() == ON.limitMillis(), "exact boundary does not invent next-day play");
        check(ledger.sample(A, before + 2001, 2001, ON, false).playedDays() == 2, "positive post-midnight play increments");
    }

    private static void pauseAndDisableExcludeElapsed() {
        long before = Instant.parse("2026-10-10T14:59:58Z").toEpochMilli();
        var ledger = new DailyPlayTimeLedger();
        ledger.join(A, before, 0, ON, false);
        ledger.sample(A, before + 1000, 1000, ON, true);
        var paused = ledger.sample(A, before + 2 * DAY, 2 * DAY, ON, true);
        check(paused.playedDays() == 1 && paused.remainingMillis() == ON.limitMillis(), "pause crossing days never charges or counts");
        ledger.sample(A, before + 2 * DAY + 1, 2 * DAY + 1, ON, false);
        var resumed = ledger.sample(A, before + 2 * DAY + 1001, 2 * DAY + 1001, ON, false);
        check(resumed.playedDays() == 2 && resumed.remainingMillis() == ON.limitMillis() - 1000, "resume excludes paused duration");
        ledger = new DailyPlayTimeLedger();
        ledger.join(A, START, 0, OFF, false);
        check(ledger.sample(A, START + 50_000, 50_000, OFF, false).playedDays() == 0, "disabled starts no history");
        ledger.sample(A, START + 60_000, 60_000, ON, false);
        ledger.sample(A, START + 65_000, 65_000, OFF, false);
        var disabled = ledger.sample(A, START + 500_000, 500_000, OFF, false);
        check(!disabled.enabled() && disabled.remainingMillis() == ON.limitMillis() - 5000, "disable retains used budget without new charge");
        ledger.sample(A, START + 600_000, 600_000, ON, false);
        check(ledger.sample(A, START + 601_000, 601_000, ON, false).remainingMillis() == ON.limitMillis() - 6000, "reenable never refunds same date");
    }

    private static void monotonicLagAndClockChanges() {
        var ledger = new DailyPlayTimeLedger();
        ledger.join(A, START, 0, ON, false);
        var lag = ledger.sample(A, START + 200_000, 200_000, ON, false);
        check(lag.remainingMillis() == ON.limitMillis() - 200_000, "lag counts real elapsed, not callback count");
        var rollback = ledger.sample(A, START - DAY, 201_000, ON, false);
        check(rollback.playedDays() == 1 && rollback.remainingMillis() == ON.limitMillis() - 201_000, "wall rollback neither resets nor erases elapsed");
        ledger = DailyPlayTimeLedger.restore(ledger.saveState());
        check(ledger.join(A, START - DAY, 0, ON, false).remainingMillis() == rollback.remainingMillis(), "rollback high-water survives restart");
        var leap = ledger.sample(A, START + 30_000 * DAY, 1000, ON, false);
        check(leap.playedDays() == 2 && leap.remainingMillis() == ON.limitMillis() - 1000, "forward jump does not fabricate thirty thousand played days");
        var tiny = new DailyPlayTimeLedger.Settings(true, 10, 540);
        ledger = new DailyPlayTimeLedger();
        ledger.join(A, START, 0, tiny, false);
        check(!ledger.sample(A, START + 9, 9, tiny, false).exhausted(), "before exact cap allowed");
        check(ledger.sample(A, START + 10, 10, tiny, false).exhausted(), "exact cap exhausted");
        ledger.leave(A, START + 10, 10, tiny, false);
        check(ledger.inspect(A, START + 1000, tiny, false).exhausted(), "same date relog blocked");
        check(!ledger.inspect(A, START + DAY, tiny, false).exhausted(), "real next date restores allowance");
    }

    private static void settingsChangesPreserveBudgetAndDays() {
        long wall = Instant.parse("2026-10-10T15:00:00Z").toEpochMilli();
        var east = new DailyPlayTimeLedger.Settings(true, 100_000, 840);
        var west = new DailyPlayTimeLedger.Settings(true, 100_000, -840);
        var ledger = new DailyPlayTimeLedger();
        ledger.join(A, wall, 0, east, false);
        ledger.sample(A, wall + 1000, 1000, east, false);
        var edit = ledger.sample(A, wall + 1000, 1000, west, false);
        check(edit.playedDays() == 1 && edit.remainingMillis() == 99_000, "offset edit alone does not reset or count");
        check(ledger.sample(A, wall + 2000, 2000, west, false).playedDays() == 2, "positive play on different offset date counts once");
        var back = ledger.sample(A, wall + 2000, 2000, east, false);
        check(back.remainingMillis() == 98_000 && back.playedDays() == 2, "offset toggle carries usage without duplicate day");
        check(ledger.sample(A, wall + 3000, 3000, east, false).playedDays() == 2, "revisited counted day no duplicate");
        var reduced = new DailyPlayTimeLedger.Settings(true, 2000, 840);
        check(ledger.sample(A, wall + 3000, 3000, reduced, false).exhausted(), "reducing limit takes effect without reset");
        var increased = new DailyPlayTimeLedger.Settings(true, 4000, 840);
        check(ledger.sample(A, wall + 3000, 3000, increased, false).remainingMillis() == 1000, "increasing allowance preserves use");
    }

    private static void identityAndWorldIsolation() {
        var world = new DailyPlayTimeLedger();
        world.join(A, START, 0, ON, false);
        world.sample(A, START + 5000, 5000, ON, false);
        check(world.join(B, START + 5000, 5000, ON, false).remainingMillis() == ON.limitMillis(), "UUIDs have independent budgets");
        check(new DailyPlayTimeLedger().join(A, START + 5000, 5000, ON, false).playedDays() == 0, "same UUID in another world independent");
        // No dimension, gameTime, dayTime, sleep, death, weather, tick-rate or client value enters this model.
        check(world.inspect(A, START + 5000, ON, false).remainingMillis() == ON.limitMillis() - 5000, "inspection does not depend on Minecraft day");
    }

    private static void boundedHistoryAndSnapshotIsolation() {
        var ledger = new DailyPlayTimeLedger();
        for (int day = 0; day < 100; day++) {
            ledger.join(A, START + day * DAY, 0, ON, false);
            ledger.leave(A, START + day * DAY + 1, 1, ON, false);
        }
        var state = ledger.saveState();
        check(state.accounts().get(A).playedDates().size() == DailyPlayTimeLedger.RETAINED_DATES, "history bounded per player");
        check(state.accounts().get(A).playedDays() == 100, "durable total exceeds retained history");
        var restored = DailyPlayTimeLedger.restore(state);
        check(restored.inspect(A, START + 99 * DAY + 2, ON, false).playedDays() == 100, "count survives pruned-history restart");
        try { state.accounts().clear(); throw new AssertionError("mutable saved accounts"); }
        catch (UnsupportedOperationException expected) { assertions++; }
        try { state.accounts().get(A).playedDates().clear(); throw new AssertionError("mutable date history"); }
        catch (UnsupportedOperationException expected) { assertions++; }
    }

    private static void inspectionBeforeSettlement() {
        long before = Instant.parse("2026-10-10T14:59:58Z").toEpochMilli();
        var ledger = new DailyPlayTimeLedger();
        ledger.join(A, before, 0, ON, false);
        ledger.inspect(A, before + 4000, ON, false);
        var settled = ledger.sample(A, before + 4000, 4000, ON, false);
        check(settled.playedDays() == 2 && settled.remainingMillis() == ON.limitMillis() - 2000, "inspection cannot misassign old-day interval to new date");
    }

    private static void duplicateJoinAndClockBounds() {
        var ledger = new DailyPlayTimeLedger();
        ledger.join(A, START, 100, ON, false);
        check(ledger.join(A, START + 1000, 1100, ON, false).remainingMillis() == ON.limitMillis() - 1000, "duplicate join settles existing elapsed");
        ledger.sample(A, START + 1001, 1099, ON, false);
        check(ledger.sample(A, START + 1002, 1101, ON, false).remainingMillis() == ON.limitMillis() - 1001, "backward monotonic test reading does not double charge");
        check(DailyPlayTimeLedger.dayAt(-1, 0) == -1, "pre-epoch dates use floor division");
        check(DailyPlayTimeLedger.dayAt(0, -840) == -1, "western offset supported");
        for (int bad : new int[] {-841, 841}) {
            try { new DailyPlayTimeLedger.Settings(true, 1, bad); throw new AssertionError("bad offset accepted"); }
            catch (IllegalArgumentException expected) { assertions++; }
        }
    }

    private static void pathologicalLongIntervalIsBounded() {
        var ledger = new DailyPlayTimeLedger();
        ledger.join(A, START, 0, ON, false);
        var after = ledger.sample(A, START + 100_000 * DAY, 100_000 * DAY, ON, false);
        check(after.playedDays() == 100_001, "long genuinely active interval counts distinct days arithmetically");
        check(ledger.saveState().accounts().get(A).playedDates().size() == 32, "long interval retains only bounded buckets");
        check(after.remainingMillis() == 0, "long interval retains current-day elapsed despite bounded history");
        ledger = new DailyPlayTimeLedger();
        ledger.join(A, Long.MIN_VALUE, 0, ON, false);
        var extreme = ledger.sample(A, Long.MAX_VALUE, Long.MAX_VALUE, ON, false);
        check(extreme.resetAtEpochMillis() > 0 && extreme.playedDays() > 0, "malformed extreme clocks remain bounded without arithmetic overflow");
        var row = new DailyPlayTimeLedger.AccountState(DailyPlayTimeLedger.dayAt(START, 540), 1, 540, 1,
                Long.MIN_VALUE, java.util.Map.of(1L, -5L));
        var restored = DailyPlayTimeLedger.restore(new DailyPlayTimeLedger.SavedState(START, java.util.Map.of(A, row)));
        check(restored.saveState().accounts().get(A).playedDates().isEmpty(), "negative historical usage is rejected");
        try { new DailyPlayTimeLedger.Settings(true, DAY + 1, 540); throw new AssertionError("oversized limit accepted"); }
        catch (IllegalArgumentException expected) { assertions++; }
    }

    private static void check(boolean ok, String message) {
        assertions++;
        if (!ok) throw new AssertionError(message);
    }
}
