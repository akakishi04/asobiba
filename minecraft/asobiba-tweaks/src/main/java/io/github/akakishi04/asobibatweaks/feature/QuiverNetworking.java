package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import net.minecraft.server.level.ServerPlayer;
import net.neoforged.neoforge.network.event.RegisterPayloadHandlersEvent;
import net.neoforged.neoforge.network.PacketDistributor;
import net.neoforged.neoforge.network.registration.NetworkRegistry;
import java.util.function.Consumer;

public final class QuiverNetworking {
    private static volatile Consumer<QuiverSyncPayload> CLIENT_HANDLER = payload -> {};

    private QuiverNetworking() {
    }

    public static void registerPayloads(RegisterPayloadHandlersEvent event) {
        var registrar = event.registrar("1");
        registrar.playToClient(
                QuiverSyncPayload.TYPE,
                QuiverSyncPayload.STREAM_CODEC,
                (payload, context) -> context.enqueueWork(() -> CLIENT_HANDLER.accept(payload))
        );
        registrar.playToServer(
                QuiverSelectPayload.TYPE,
                QuiverSelectPayload.STREAM_CODEC,
                (payload, context) -> context.enqueueWork(() -> {
                    if (!(context.player() instanceof ServerPlayer player)
                            || !AsobibaTweaksConfig.QUIVER_ENABLED.getAsBoolean()) {
                        return;
                    }

                    int slot = payload.slot();
                    if (slot < 0 || slot >= QuiverData.AMMO_SLOTS
                            || !QuiverData.hasEquipped(player)
                            || QuiverData.ammo(player, slot).isEmpty()) {
                        return;
                    }
                    QuiverData.setSelectedSlot(player, slot);
                })
        );
    }

    public static void installClientHandler(Consumer<QuiverSyncPayload> handler) {
        CLIENT_HANDLER = handler == null ? payload -> {} : handler;
    }

    public static void sendSnapshot(ServerPlayer player) {
        // The GameTest mock player (and any connection that has not negotiated
        // our optional payload) cannot receive a quiver snapshot. Query the
        // actual listener's negotiated channels rather than assuming every
        // ServerPlayer connection supports the client payload.
        if (player.connection == null
                || !NetworkRegistry.hasChannel(player.connection, QuiverSyncPayload.TYPE.id())) {
            return;
        }
        PacketDistributor.sendToPlayer(player, new QuiverSyncPayload(QuiverData.snapshot(player)));
    }
}
