package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.entity.vehicle.AbstractMinecart;
import net.minecraft.world.phys.Vec3;
import net.neoforged.bus.api.SubscribeEvent;
import net.neoforged.neoforge.event.entity.player.PlayerEvent;
import net.neoforged.neoforge.event.tick.PlayerTickEvent;

public final class TransportTweaksEvents {
    private final Map<UUID, Vec3> lastCartVelocity = new HashMap<>();
    private final Map<UUID, Boolean> wasInCart = new HashMap<>();

    @SubscribeEvent
    public void onPlayerTick(PlayerTickEvent.Post event) {
        if (!(event.getEntity() instanceof ServerPlayer player)
                || !AsobibaTweaksConfig.MINECART_DISMOUNT_ENABLED.getAsBoolean()) return;

        UUID id = player.getUUID();
        if (player.getVehicle() instanceof AbstractMinecart cart) {
            lastCartVelocity.put(id, cart.getDeltaMovement());
            wasInCart.put(id, true);
            return;
        }

        if (Boolean.TRUE.equals(wasInCart.remove(id))) {
            Vec3 inherited = lastCartVelocity.remove(id);
            if (inherited != null && inherited.horizontalDistanceSqr() > 0.01D) {
                Vec3 current = player.getDeltaMovement();
                player.setDeltaMovement(current.x + inherited.x, Math.max(current.y, inherited.y + 0.08D), current.z + inherited.z);
                player.hurtMarked = true;
            }
        }
    }

    @SubscribeEvent
    public void onLogout(PlayerEvent.PlayerLoggedOutEvent event) {
        UUID id = event.getEntity().getUUID();
        lastCartVelocity.remove(id);
        wasInCart.remove(id);
    }
}
