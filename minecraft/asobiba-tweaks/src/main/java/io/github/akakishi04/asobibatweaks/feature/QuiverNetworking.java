package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import net.minecraft.server.level.ServerPlayer;
import net.neoforged.neoforge.network.event.RegisterPayloadHandlersEvent;

public final class QuiverNetworking {
    private QuiverNetworking() {
    }

    public static void registerPayloads(RegisterPayloadHandlersEvent event) {
        event.registrar("1").playToServer(
                QuiverSelectPayload.TYPE,
                QuiverSelectPayload.STREAM_CODEC,
                (payload, context) -> {
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
                }
        );
    }
}
