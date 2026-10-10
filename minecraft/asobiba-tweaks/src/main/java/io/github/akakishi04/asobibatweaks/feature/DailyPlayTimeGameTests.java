package io.github.akakishi04.asobibatweaks.feature;

import com.mojang.authlib.GameProfile;
import io.github.akakishi04.asobibatweaks.AsobibaTweaks;
import io.netty.channel.embedded.EmbeddedChannel;
import java.net.InetSocketAddress;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.UUID;
import net.minecraft.gametest.framework.GameTest;
import net.minecraft.gametest.framework.GameTestHelper;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.network.Connection;
import net.minecraft.network.protocol.PacketFlow;
import net.minecraft.network.protocol.common.ClientboundDisconnectPacket;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.server.network.CommonListenerCookie;
import net.minecraft.server.network.ServerGamePacketListenerImpl;
import net.minecraft.world.level.saveddata.SavedData;
import net.minecraft.world.level.storage.DimensionDataStorage;
import net.neoforged.neoforge.common.IOUtilities;
import net.neoforged.neoforge.gametest.GameTestHolder;
import net.neoforged.neoforge.gametest.PrefixGameTestTemplate;

/** NBT, real disk reload, actual login hook and native connection-close integration coverage. */
@GameTestHolder(AsobibaTweaks.MOD_ID)
@PrefixGameTestTemplate(false)
public final class DailyPlayTimeGameTests {
    private static final DailyPlayTimeLedger.Settings ON = new DailyPlayTimeLedger.Settings(true, 60_000, 540);
    private DailyPlayTimeGameTests() {}

    @GameTest(template = "empty3x3x3", batch = "daily_play_time_data")
    public static void nbtRoundTripKeepsUuidBudgetsDaysAndRollbackFence(GameTestHelper h) {
        var data = new DailyPlayTimeSavedData();
        UUID first = UUID.randomUUID(), second = UUID.randomUUID();
        long now = System.currentTimeMillis();
        data.ledger().join(first, now, 0, ON, false);
        data.ledger().leave(first, now, 60_000, ON, false);
        data.ledger().join(second, now, 0, ON, false);
        data.ledger().leave(second, now, 5000, ON, false);
        CompoundTag tag = data.save(new CompoundTag(), h.getLevel().registryAccess());
        var loaded = DailyPlayTimeSavedData.load(tag.copy(), h.getLevel().registryAccess());
        var blocked = loaded.ledger().inspect(first, now - DailyPlayTimeLedger.DAY_MILLIS, ON, false);
        h.assertTrue(blocked.exhausted() && blocked.playedDays() == 1,
                "NBT reload must keep exhausted UUID and conservative real-date fence");
        var independent = loaded.ledger().inspect(second, now, ON, false);
        h.assertTrue(independent.remainingMillis() == 55_000 && independent.playedDays() == 1,
                "NBT reload keeps each UUID independent");
        h.assertTrue(loaded.ledger().onlinePlayers().isEmpty(), "Saved data must never restore an online session");
        h.succeed();
    }

    @GameTest(template = "empty3x3x3", batch = "daily_play_time_data")
    public static void nativeSavedDataDiskReloadKeepsSameDateRejection(GameTestHelper h) throws Exception {
        var server = h.getLevel().getServer();
        var data = new DailyPlayTimeSavedData();
        UUID id = UUID.randomUUID();
        long now = System.currentTimeMillis();
        data.ledger().join(id, now, 0, ON, false);
        data.ledger().leave(id, now, 60_000, ON, false);
        Path directory = Files.createTempDirectory("asobiba-daily-play-time-");
        Path file = directory.resolve(DailyPlayTimeSavedData.NAME + ".dat");
        try {
            data.setDirty();
            data.save(file.toFile(), server.registryAccess());
            IOUtilities.waitUntilIOWorkerComplete();
            h.assertTrue(Files.isRegularFile(file) && Files.size(file) > 0, "Native SavedData must write actual disk bytes");
            var freshStorage = new DimensionDataStorage(directory.toFile(), server.getFixerUpper(), server.registryAccess());
            var factory = new SavedData.Factory<>(DailyPlayTimeSavedData::new, DailyPlayTimeSavedData::load);
            var reloaded = freshStorage.get(factory, DailyPlayTimeSavedData.NAME);
            h.assertTrue(reloaded != null && reloaded != data, "Fresh storage must deserialize, not reuse cached ledger");
            var joined = reloaded.ledger().join(id, now, 0, ON, false);
            h.assertTrue(joined.exhausted() && joined.playedDays() == 1,
                    "A same-date join after disk reload keeps exhausted allowance and one played day");
            var nextDay = reloaded.ledger().inspect(id, now + DailyPlayTimeLedger.DAY_MILLIS, ON, false);
            h.assertTrue(!nextDay.exhausted() && nextDay.playedDays() == 1,
                    "Next real date restores allowance without fabricating played history");
        } finally {
            IOUtilities.waitUntilIOWorkerComplete();
            // Test-created scratch only; never touch a user's actual world ledger.
            try (var files = Files.list(directory)) {
                for (Path path : files.toList()) Files.deleteIfExists(path);
            }
            Files.deleteIfExists(directory);
        }
        h.succeed();
    }

    @GameTest(template = "empty3x3x3", batch = "daily_play_time_server")
    public static void actualPlayerListHookRejectsExhaustedUuidBeforeJoin(GameTestHelper h) {
        var server = h.getLevel().getServer();
        var rules = server.getGameRules();
        boolean oldEnabled = rules.getBoolean(PlayTimeRules.ENABLED);
        int oldLimit = rules.getInt(PlayTimeRules.LIMIT_MINUTES);
        int oldOffset = rules.getInt(PlayTimeRules.RESET_UTC_OFFSET_MINUTES);
        // GameTestServer's shared list has capacity 1, and unrelated test mock players can
        // occupy it. Exercise the same transformed vanilla method with an isolated empty list;
        // no ban, whitelist, capacity or timer rejection is weakened or overridden.
        var admission = new net.minecraft.server.players.PlayerList(server, server.registries(), null, 20) {};
        var profile = new GameProfile(UUID.randomUUID(), "daily-cap-probe");
        var address = new InetSocketAddress("127.0.0.1", 25565);
        try {
            rules.getRule(PlayTimeRules.ENABLED).set(false, server);
            rules.getRule(PlayTimeRules.LIMIT_MINUTES).set(1, server);
            rules.getRule(PlayTimeRules.RESET_UTC_OFFSET_MINUTES).set(540, server);
            var baseline = admission.canPlayerLogin(address, profile);
            h.assertTrue(baseline == null,
                    "Fresh isolated probe must be admissible; vanilla reason=" + baseline);
            var data = DailyPlayTimeSavedData.get(server);
            long now = System.currentTimeMillis();
            data.ledger().join(profile.getId(), now, 0, ON, false);
            data.ledger().leave(profile.getId(), now, 60_000, ON, false);
            data.setDirty();
            rules.getRule(PlayTimeRules.ENABLED).set(true, server);
            var rejection = admission.canPlayerLogin(address, profile);
            h.assertTrue(rejection != null && rejection.getContents() instanceof net.minecraft.network.chat.contents.TranslatableContents translated
                            && translated.getKey().equals("asobibatweaks.play_time.limit_reached"),
                    "Actual transformed PlayerList.canPlayerLogin must reject exhausted UUID before placement");
            h.assertTrue(data.isDirty(), "Offline rejected retries must not force synchronous disk flushes");
            h.assertTrue(server.getPlayerList().getPlayer(profile.getId()) == null,
                    "Rejected login must not insert a player into the world");
            var other = new GameProfile(UUID.randomUUID(), "daily-other");
            h.assertTrue(admission.canPlayerLogin(address, other) == null,
                    "Another UUID retains its allowance");
            rules.getRule(PlayTimeRules.ENABLED).set(false, server);
            h.assertTrue(admission.canPlayerLogin(address, profile) == null,
                    "Disabled rule bypasses enforcement without clearing durable usage");
            rules.getRule(PlayTimeRules.ENABLED).set(true, server);
            h.assertTrue(admission.canPlayerLogin(address, profile) != null,
                    "Same-date reenable does not refund used time");
            long mono = java.util.concurrent.TimeUnit.NANOSECONDS.toMillis(System.nanoTime());
            data.ledger().join(profile.getId(), System.currentTimeMillis(), mono, ON, false);
            try {
                data.setDirty();
                h.assertTrue(admission.canPlayerLogin(address, profile) != null && !data.isDirty(),
                        "An online duplicate admission must settle and checkpoint newly accrued capped usage");
            } finally {
                data.ledger().leave(profile.getId(), System.currentTimeMillis(),
                        java.util.concurrent.TimeUnit.NANOSECONDS.toMillis(System.nanoTime()), ON, false);
                data.setDirty();
            }
        } finally {
            rules.getRule(PlayTimeRules.ENABLED).set(oldEnabled, server);
            rules.getRule(PlayTimeRules.LIMIT_MINUTES).set(oldLimit, server);
            rules.getRule(PlayTimeRules.RESET_UTC_OFFSET_MINUTES).set(oldOffset, server);
        }
        h.succeed();
    }

    @GameTest(template = "empty3x3x3", batch = "daily_play_time_connection")
    public static void exhaustedSnapshotUsesNativeDisconnectWithoutStoppingServer(GameTestHelper h) {
        var server = h.getLevel().getServer();
        var cookie = CommonListenerCookie.createInitial(new GameProfile(UUID.randomUUID(), "daily-disconnect"), false);
        var player = new ServerPlayer(server, h.getLevel(), cookie.gameProfile(), cookie.clientInformation());
        var connection = new Connection(PacketFlow.SERVERBOUND);
        var otherConnection = new Connection(PacketFlow.SERVERBOUND);
        var channel = new EmbeddedChannel(connection);
        var otherChannel = new EmbeddedChannel(otherConnection);
        try {
            new ServerGamePacketListenerImpl(server, connection, player, cookie);
            long reset = System.currentTimeMillis() + DailyPlayTimeLedger.DAY_MILLIS;
            var disabled = new DailyPlayTimeLedger.Snapshot(false, 1, 0, 60_000, reset, false);
            h.assertTrue(!DailyPlayTimeService.disconnectIfExhausted(player, disabled, 540) && connection.isConnected(),
                    "Disabled state may never disconnect, even with stored exhausted budget");
            var exhausted = new DailyPlayTimeLedger.Snapshot(true, 1, 0, 60_000, reset, false);
            h.assertTrue(DailyPlayTimeService.disconnectIfExhausted(player, exhausted, 540), "Exact cap invokes native disconnect");
            channel.runPendingTasks();
            h.assertTrue(!connection.isConnected(), "Native disconnect must actually close the player's channel");
            Object packet = channel.readOutbound();
            h.assertTrue(packet instanceof ClientboundDisconnectPacket, "Client receives vanilla world-disconnect packet");
            h.assertTrue(otherConnection.isConnected() && server.isRunning(),
                    "Another player channel and the Minecraft server remain running");
        } finally {
            channel.finishAndReleaseAll();
            otherChannel.finishAndReleaseAll();
            player.getTextFilter().leave();
        }
        h.succeed();
    }
}
