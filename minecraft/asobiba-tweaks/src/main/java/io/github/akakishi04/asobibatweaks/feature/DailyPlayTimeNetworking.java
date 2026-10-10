package io.github.akakishi04.asobibatweaks.feature;

import java.util.function.BiConsumer;
import net.minecraft.network.Connection;
import net.minecraft.server.level.ServerPlayer;
import net.neoforged.neoforge.network.PacketDistributor;
import net.neoforged.neoforge.network.event.RegisterPayloadHandlersEvent;
import net.neoforged.neoforge.network.registration.NetworkRegistry;

public final class DailyPlayTimeNetworking {
    private static volatile BiConsumer<DailyPlayTimePayload, Connection> clientHandler = (payload, connection) -> {};

    private DailyPlayTimeNetworking() {}

    public static void registerPayloads(RegisterPayloadHandlersEvent event) {
        // HUD support is optional. A missing/modified client cannot bypass server accounting.
        event.registrar("1").optional().playToClient(DailyPlayTimePayload.TYPE,
                DailyPlayTimePayload.STREAM_CODEC, (payload, context) -> {
                    Connection source = context.connection();
                    context.enqueueWork(() -> clientHandler.accept(payload, source));
                });
    }

    public static void installClientHandler(BiConsumer<DailyPlayTimePayload, Connection> handler) {
        clientHandler = handler == null ? (payload, connection) -> {} : handler;
    }

    public static void send(ServerPlayer player, boolean enabled, long playedDays, long remainingMillis,
            long limitMillis, long resetAtEpochMillis, boolean paused) {
        if (player.connection == null
                || !NetworkRegistry.hasChannel(player.connection, DailyPlayTimePayload.TYPE.id())) return;
        PacketDistributor.sendToPlayer(player, new DailyPlayTimePayload(enabled, playedDays,
                remainingMillis, limitMillis, resetAtEpochMillis, paused));
    }
}
