package io.github.akakishi04.asobibatweaks.feature;

import java.time.Instant;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.util.HashMap;
import java.util.IdentityHashMap;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.TimeUnit;
import net.minecraft.network.chat.Component;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerPlayer;

/** Server-thread-only lifecycle, authoritative enforcement, and bounded durable checkpoints. */
public final class DailyPlayTimeService {
    public static final long CHECKPOINT_MILLIS = 30_000;
    private static final long SNAPSHOT_MILLIS = 1_000;
    private static final Map<MinecraftServer, DailyPlayTimeService> SERVICES = new IdentityHashMap<>();
    private static final DateTimeFormatter RESET_FORMAT = DateTimeFormatter.ofPattern("uuuu-MM-dd HH:mm 'UTC'xxx");
    private final MinecraftServer server;
    private final DailyPlayTimeSavedData data;
    private final DailyPlayTimeLedger ledger;
    private final Map<UUID, ServerPlayer> players = new HashMap<>();
    private final Map<UUID, DailyPlayTimeLedger.Snapshot> sent = new HashMap<>();
    private long lastCheckpoint;
    private long lastSnapshot;
    private boolean suspended;

    private DailyPlayTimeService(MinecraftServer server) {
        this.server = server;
        this.data = DailyPlayTimeSavedData.get(server);
        this.ledger = data.ledger();
        this.lastCheckpoint = monotonicMillis();
        this.lastSnapshot = lastCheckpoint;
    }

    private static DailyPlayTimeService get(MinecraftServer server) {
        return SERVICES.computeIfAbsent(server, DailyPlayTimeService::new);
    }

    private static DailyPlayTimeLedger.Settings settings(MinecraftServer server) {
        return new DailyPlayTimeLedger.Settings(PlayTimeRules.enabled(server),
                PlayTimeRules.limitMillis(server), PlayTimeRules.offsetMinutes(server));
    }

    private static long monotonicMillis() { return TimeUnit.NANOSECONDS.toMillis(System.nanoTime()); }

    /** Called after the virtual tickServer invocation, including genuinely paused integrated loops. */
    public static void onServerLoop(MinecraftServer server) {
        if (server.overworld() == null) return;
        DailyPlayTimeService service = SERVICES.get(server);
        if (service == null) {
            if (!PlayTimeRules.enabled(server) || server.getPlayerList().getPlayers().isEmpty()) return;
            service = get(server);
        }
        if (service.suspended && !PlayTimeRules.enabled(server)) return;
        service.tick(System.currentTimeMillis(), monotonicMillis());
    }

    private void tick(long wall, long monotonic) {
        var settings = settings(server);
        boolean paused = server.isPaused();
        boolean broadcast = monotonic - lastSnapshot >= SNAPSHOT_MILLIS;
        // Copy because disconnect may synchronously trigger PlayerLoggedOutEvent/remove.
        for (ServerPlayer player : java.util.List.copyOf(server.getPlayerList().getPlayers())) {
            UUID id = player.getUUID();
            long before = ledger.revision();
            if (players.get(id) != player) {
                // Settle the former entity before replacing an anchor with the same UUID.
                if (players.containsKey(id)) ledger.leave(id, wall, monotonic, settings, paused);
                players.put(id, player);
                ledger.join(id, wall, monotonic, settings, paused);
            }
            var snapshot = ledger.sample(id, wall, monotonic, settings, paused);
            dirtyIfChanged(before);
            publish(player, snapshot, broadcast);
            if (snapshot.exhausted()) {
                data.checkpoint(server);
                disconnectIfExhausted(player, snapshot, settings.offsetMinutes());
            }
        }
        suspended = !settings.enabled();
        if (suspended) {
            long before = ledger.revision();
            for (UUID id : ledger.onlinePlayers()) ledger.leave(id, wall, monotonic, settings, paused);
            dirtyIfChanged(before);
            players.clear();
            sent.clear();
            data.checkpoint(server);
        }
        if (broadcast) lastSnapshot = monotonic;
        if (monotonic - lastCheckpoint >= CHECKPOINT_MILLIS) {
            data.checkpoint(server);
            lastCheckpoint = monotonic;
        }
    }

    public static void onLogin(ServerPlayer player) {
        MinecraftServer server = player.server;
        if (!PlayTimeRules.enabled(server)) return;
        DailyPlayTimeService service = get(server);
        var settings = settings(server);
        long before = service.ledger.revision();
        long wall = System.currentTimeMillis();
        long mono = monotonicMillis();
        ServerPlayer old = service.players.put(player.getUUID(), player);
        if (old != null && old != player) service.ledger.leave(player.getUUID(), wall, mono, settings, server.isPaused());
        var snapshot = service.ledger.join(player.getUUID(), wall, mono, settings, server.isPaused());
        service.dirtyIfChanged(before);
        service.publish(player, snapshot, true);
        if (snapshot.exhausted()) {
            service.data.checkpoint(server);
            disconnectIfExhausted(player, snapshot, settings.offsetMinutes());
        }
    }

    public static void onLogout(ServerPlayer player) {
        DailyPlayTimeService service = SERVICES.get(player.server);
        // An old duplicate connection must never remove a replacement player's live session.
        if (service == null || service.players.get(player.getUUID()) != player) return;
        long before = service.ledger.revision();
        service.ledger.leave(player.getUUID(), System.currentTimeMillis(), monotonicMillis(),
                settings(player.server), player.server.isPaused());
        service.players.remove(player.getUUID());
        service.sent.remove(player.getUUID());
        service.dirtyIfChanged(before);
        service.data.checkpoint(player.server);
    }

    /** Checked before world join, and again by vanilla after configuration completes. */
    public static Component loginRejection(MinecraftServer server, UUID id) {
        if (server.overworld() == null || !PlayTimeRules.enabled(server)) return null;
        DailyPlayTimeService service = get(server);
        var settings = settings(server);
        long before = service.ledger.revision();
        boolean online = service.ledger.onlinePlayers().contains(id);
        var snapshot = online
                ? service.ledger.sample(id, System.currentTimeMillis(), monotonicMillis(), settings, server.isPaused())
                : service.ledger.inspect(id, System.currentTimeMillis(), settings, server.isPaused());
        service.dirtyIfChanged(before);
        if (!snapshot.exhausted()) return null;
        // Offline usage already came from a durable logout/cap checkpoint or disk load.
        // A rejected attempt adds no play and must not force another disk flush on every retry.
        // A duplicate login can settle new online usage, so that path still checkpoints now.
        if (online) service.data.checkpoint(server);
        return limitMessage(snapshot, settings.offsetMinutes());
    }

    public static void onStopping(MinecraftServer server) {
        DailyPlayTimeService service = SERVICES.get(server);
        if (service == null) return;
        long wall = System.currentTimeMillis();
        long monotonic = monotonicMillis();
        long before = service.ledger.revision();
        var settings = settings(server);
        for (UUID id : service.ledger.onlinePlayers()) {
            service.ledger.leave(id, wall, monotonic, settings, server.isPaused());
        }
        service.dirtyIfChanged(before);
        service.data.checkpoint(server);
        service.players.clear();
        service.sent.clear();
    }

    public static void onStopped(MinecraftServer server) { SERVICES.remove(server); }

    private void dirtyIfChanged(long before) { if (before != ledger.revision()) data.setDirty(); }

    private void publish(ServerPlayer player, DailyPlayTimeLedger.Snapshot snapshot, boolean periodic) {
        var previous = sent.get(player.getUUID());
        boolean changed = previous == null || previous.enabled() != snapshot.enabled()
                || previous.paused() != snapshot.paused() || previous.playedDays() != snapshot.playedDays()
                || previous.limitMillis() != snapshot.limitMillis()
                || previous.resetAtEpochMillis() != snapshot.resetAtEpochMillis()
                || previous.exhausted() != snapshot.exhausted();
        if (!periodic && !changed) return;
        DailyPlayTimeNetworking.send(player, snapshot.enabled(), snapshot.playedDays(),
                snapshot.remainingMillis(), snapshot.limitMillis(), snapshot.resetAtEpochMillis(), snapshot.paused());
        sent.put(player.getUUID(), snapshot);
    }

    static boolean disconnectIfExhausted(ServerPlayer player, DailyPlayTimeLedger.Snapshot snapshot, int offset) {
        if (!snapshot.exhausted()) return false;
        player.connection.disconnect(limitMessage(snapshot, offset));
        return true;
    }

    private static Component limitMessage(DailyPlayTimeLedger.Snapshot snapshot, int offset) {
        String reset = RESET_FORMAT.format(Instant.ofEpochMilli(snapshot.resetAtEpochMillis())
                .atOffset(ZoneOffset.ofTotalSeconds(offset * 60)));
        return Component.translatable("asobibatweaks.play_time.limit_reached", reset);
    }
}
