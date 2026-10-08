package io.github.akakishi04.asobibatweaks.feature;

import net.minecraft.server.level.ServerPlayer;
import net.neoforged.neoforge.network.event.RegisterPayloadHandlersEvent;

public final class FrostWalkerToggleNetworking {
    private FrostWalkerToggleNetworking() {}

    public static void registerPayloads(RegisterPayloadHandlersEvent event) {
        event.registrar("1").playToServer(
                FrostWalkerTogglePayload.TYPE,
                FrostWalkerTogglePayload.STREAM_CODEC,
                (payload, context) -> context.enqueueWork(() -> {
                    if (context.player() instanceof ServerPlayer player
                            && payload.request() == 1) {
                        FrostWalkerToggle.toggle(player);
                    }
                })
        );
    }
}
