package io.github.akakishi04.asobibatweaks.feature;

import java.util.HashMap;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

/**
 * Pure real-time accounting. One instance belongs to one world save, never to a dimension.
 * Wall time selects calendar dates; a monotonic clock alone measures active online duration.
 * Sessions are deliberately absent from persisted state: offline time is never charged.
 */
public final class DailyPlayTimeLedger {
    public static final long DAY_MILLIS = 86_400_000L;
    public static final int RETAINED_DATES = 32;
    private static final long UNSET = Long.MIN_VALUE;
    // More than sufficient for real host dates; bound arithmetic even for malformed saved values.
    private static final long MIN_WALL = -62_135_596_800_000L; // 0001-01-01
    private static final long MAX_WALL = 253_402_300_799_999L; // 9999-12-31
    private final Map<UUID, Account> accounts = new HashMap<>();
    private final Map<UUID, Session> sessions = new HashMap<>();
    private long wallHighWater = UNSET;
    private long revision;

    public record Settings(boolean enabled, long limitMillis, int offsetMinutes) {
        public Settings {
            if (limitMillis < 1 || limitMillis > DAY_MILLIS || offsetMinutes < -840 || offsetMinutes > 840) {
                throw new IllegalArgumentException("Invalid daily play-time settings");
            }
        }
    }

    public record Snapshot(boolean enabled, long playedDays, long remainingMillis,
                           long limitMillis, long resetAtEpochMillis, boolean paused) {
        public boolean exhausted() { return enabled && remainingMillis == 0; }
    }

    public record AccountState(long day, long usedMillis, int offsetMinutes, long playedDays,
                               long prunedDateFence, Map<Long, Long> playedDates) {
        public AccountState { playedDates = Map.copyOf(playedDates); }
    }

    public record SavedState(long wallHighWater, Map<UUID, AccountState> accounts) {
        public SavedState { accounts = Map.copyOf(accounts); }
    }

    public Snapshot join(UUID player, long wallMillis, long monotonicMillis, Settings settings, boolean paused) {
        // A repeated login callback must not erase time accrued by an existing live session.
        if (sessions.containsKey(player)) return sample(player, wallMillis, monotonicMillis, settings, paused);
        long now = observeWall(wallMillis);
        Account account = account(player, now, settings.offsetMinutes());
        sessions.put(player, new Session(now, monotonicMillis, settings.enabled() && !paused,
                settings.offsetMinutes()));
        return snapshot(account, now, settings, paused);
    }

    public Snapshot sample(UUID player, long wallMillis, long monotonicMillis, Settings settings, boolean paused) {
        Session session = sessions.get(player);
        if (session == null) return join(player, wallMillis, monotonicMillis, settings, paused);
        long now = observeWall(wallMillis);
        Account account = accounts.get(player);
        long elapsed = monotonicMillis < session.monotonicMillis ? 0L : monotonicMillis - session.monotonicMillis;
        if (elapsed < 0) elapsed = Long.MAX_VALUE; // Subtraction overflow from a malformed test/clock reading.
        if (session.active && elapsed > 0) {
            charge(account, session.wallMillis, now, elapsed, session.offsetMinutes);
        }
        rebase(account, now, settings.offsetMinutes());
        session.wallMillis = now;
        session.monotonicMillis = Math.max(session.monotonicMillis, monotonicMillis);
        session.active = settings.enabled() && !paused;
        session.offsetMinutes = settings.offsetMinutes();
        return snapshot(account, now, settings, paused);
    }

    public Snapshot leave(UUID player, long wallMillis, long monotonicMillis, Settings settings, boolean paused) {
        Snapshot result = sessions.containsKey(player)
                ? sample(player, wallMillis, monotonicMillis, settings, paused)
                : inspect(player, wallMillis, settings, paused);
        sessions.remove(player);
        return result;
    }

    /** Checking admission or a paused day rollover does not create a played day. */
    public Snapshot inspect(UUID player, long wallMillis, Settings settings, boolean paused) {
        long now = observeWall(wallMillis);
        Account account = account(player, now, settings.offsetMinutes());
        return snapshot(account, now, settings, paused);
    }

    public Set<UUID> onlinePlayers() { return Set.copyOf(sessions.keySet()); }
    public long revision() { return revision; }

    public SavedState saveState() {
        Map<UUID, AccountState> result = new HashMap<>();
        accounts.forEach((id, account) -> result.put(id, new AccountState(account.day,
                account.usedMillis, account.offsetMinutes, account.playedDays, account.prunedDateFence, account.playedDates)));
        return new SavedState(wallHighWater, result);
    }

    public static DailyPlayTimeLedger restore(SavedState state) {
        DailyPlayTimeLedger ledger = new DailyPlayTimeLedger();
        ledger.wallHighWater = state.wallHighWater() == UNSET ? UNSET : boundedWall(state.wallHighWater());
        state.accounts().forEach((id, row) -> {
            if (row.usedMillis() < 0 || row.offsetMinutes() < -840 || row.offsetMinutes() > 840) return;
            Account account = new Account(boundedDay(row.day()), row.offsetMinutes());
            account.usedMillis = row.usedMillis();
            row.playedDates().forEach((day, used) -> { if (used > 0 && day == boundedDay(day)) account.playedDates.put(day, used); });
            account.playedDays = Math.max(row.playedDays(), account.playedDates.size());
            account.prunedDateFence = row.prunedDateFence() == UNSET ? UNSET : boundedDay(row.prunedDateFence());
            prune(account);
            ledger.accounts.put(id, account);
        });
        return ledger;
    }

    public static long dayAt(long wallMillis, int offsetMinutes) {
        return Math.floorDiv(boundedWall(wallMillis) + offsetMinutes * 60_000L, DAY_MILLIS);
    }

    private static long boundedWall(long wall) { return Math.max(MIN_WALL, Math.min(MAX_WALL, wall)); }
    private static long boundedDay(long day) {
        return Math.max(Math.floorDiv(MIN_WALL, DAY_MILLIS) - 1,
                Math.min(Math.floorDiv(MAX_WALL, DAY_MILLIS) + 1, day));
    }

    private long observeWall(long now) {
        now = boundedWall(now);
        // Persist this high-water mark to prevent a clock rollback/restart from refunding a day.
        if (now > wallHighWater) { wallHighWater = now; revision++; }
        return wallHighWater;
    }

    private Account account(UUID player, long now, int offset) {
        Account account = accounts.get(player);
        if (account == null) {
            account = new Account(dayAt(now, offset), offset);
            accounts.put(player, account);
            revision++;
        } else rebase(account, now, offset);
        return account;
    }

    private void rebase(Account account, long now, int offset) {
        long today = dayAt(now, offset);
        if (account.offsetMinutes != offset) {
            // A settings edit is not a fresh allowance. Carry usage to the newly selected day;
            // the next genuine midnight at that fixed offset starts the next allowance.
            account.day = today;
            account.usedMillis = Math.max(account.usedMillis, account.usageOn(today));
            account.offsetMinutes = offset;
            revision++;
        } else rollTo(account, today);
    }

    private void rollTo(Account account, long day) {
        if (day > account.day) {
            account.day = day;
            account.usedMillis = account.usageOn(day);
            revision++;
        }
    }

    private void add(Account account, long day, long elapsed) {
        if (elapsed <= 0) return;
        rollTo(account, day);
        long previous = day == account.day ? account.usedMillis : account.usageOn(day);
        long used = saturatedAdd(previous, elapsed);
        if (!account.playedDates.containsKey(day) && day > account.prunedDateFence) {
            account.playedDays = saturatedAdd(account.playedDays, 1);
        }
        account.playedDates.put(day, used);
        if (day == account.day) account.usedMillis = used;
        prune(account);
        revision++;
    }

    private void charge(Account account, long previousWall, long now, long elapsed, int offset) {
        long wallElapsed = Math.max(0L, now - previousWall);
        long mapped = Math.min(elapsed, wallElapsed);
        // If wall time stalls or rolls back, continue charging the existing calendar day using
        // the monotonic clock, without synthesizing a future midnight or granting a reset.
        add(account, dayAt(previousWall, offset), elapsed - mapped);
        // A forward wall-clock jump is not proof of play on intervening dates. Only map the
        // actual monotonic interval ending at 'now', rather than filling the wall-time gap.
        long cursor = now - mapped;
        if (mapped > 0) {
            long firstDay = dayAt(cursor, offset);
            long lastDay = dayAt(now - 1, offset);
            if (lastDay - firstDay >= RETAINED_DATES) {
                // A multi-month stall must not cause unbounded work. Count old contiguous played
                // dates arithmetically, retain only the latest 32 budgets, then split those below.
                long lastPruned = lastDay - RETAINED_DATES;
                long firstUncounted = Math.max(firstDay, account.prunedDateFence + 1);
                long newDates = Math.max(0, lastPruned - firstUncounted + 1);
                for (long date : account.playedDates.keySet()) {
                    if (date >= firstUncounted && date <= lastPruned) newDates--;
                }
                account.playedDays = saturatedAdd(account.playedDays, newDates);
                account.prunedDateFence = Math.max(account.prunedDateFence, lastPruned);
                account.playedDates.keySet().removeIf(date -> date <= lastPruned);
                cursor = (lastPruned + 1) * DAY_MILLIS - offset * 60_000L;
                revision++;
            }
        }
        while (cursor < now) {
            long day = dayAt(cursor, offset);
            long boundary = (day + 1) * DAY_MILLIS - offset * 60_000L;
            long end = Math.min(now, boundary);
            add(account, day, end - cursor);
            cursor = end;
        }
    }

    private Snapshot snapshot(Account account, long now, Settings settings, boolean paused) {
        long reset = (Math.max(account.day, dayAt(now, settings.offsetMinutes())) + 1) * DAY_MILLIS
                - settings.offsetMinutes() * 60_000L;
        return new Snapshot(settings.enabled(), account.playedDays,
                Math.max(0L, settings.limitMillis() - Math.min(settings.limitMillis(), account.usedMillis)),
                settings.limitMillis(), reset, paused);
    }

    private static void prune(Account account) {
        while (account.playedDates.size() > RETAINED_DATES) {
            long oldest = account.playedDates.keySet().stream().mapToLong(Long::longValue).min().orElseThrow();
            account.prunedDateFence = Math.max(account.prunedDateFence, oldest);
            account.playedDates.remove(oldest);
        }
    }

    private static long saturatedAdd(long a, long b) { return a > Long.MAX_VALUE - b ? Long.MAX_VALUE : a + b; }

    private static final class Account {
        private long day;
        private long usedMillis;
        private int offsetMinutes;
        private long playedDays;
        private long prunedDateFence = UNSET;
        private final Map<Long, Long> playedDates = new HashMap<>();
        private long usageOn(long date) {
            return playedDates.getOrDefault(date, date <= prunedDateFence ? Long.MAX_VALUE : 0L);
        }
        private Account(long day, int offsetMinutes) { this.day = day; this.offsetMinutes = offsetMinutes; }
    }

    private static final class Session {
        private long wallMillis;
        private long monotonicMillis;
        private boolean active;
        private int offsetMinutes;
        private Session(long wallMillis, long monotonicMillis, boolean active, int offsetMinutes) {
            this.wallMillis = wallMillis;
            this.monotonicMillis = monotonicMillis;
            this.active = active;
            this.offsetMinutes = offsetMinutes;
        }
    }
}
