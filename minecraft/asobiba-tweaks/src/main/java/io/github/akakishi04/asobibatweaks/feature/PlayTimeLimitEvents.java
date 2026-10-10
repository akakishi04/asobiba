package io.github.akakishi04.asobibatweaks.feature;

import net.minecraft.server.level.ServerPlayer;
import net.neoforged.bus.api.SubscribeEvent;
import net.neoforged.neoforge.event.entity.player.PlayerEvent;
import net.neoforged.neoforge.event.server.ServerStoppedEvent;
import net.neoforged.neoforge.event.server.ServerStoppingEvent;

/** Lifecycle only: elapsed time is sampled by the common server-loop hook, never by tick counts. */
public final class PlayTimeLimitEvents {
    @SubscribeEvent
    public void onLogin(PlayerEvent.PlayerLoggedInEvent event) {
        if (event.getEntity() instanceof ServerPlayer player) DailyPlayTimeService.onLogin(player);
    }

    @SubscribeEvent
    public void onLogout(PlayerEvent.PlayerLoggedOutEvent event) {
        if (event.getEntity() instanceof ServerPlayer player) DailyPlayTimeService.onLogout(player);
    }

    @SubscribeEvent
    public void onStopping(ServerStoppingEvent event) { DailyPlayTimeService.onStopping(event.getServer()); }

    @SubscribeEvent
    public void onStopped(ServerStoppedEvent event) { DailyPlayTimeService.onStopped(event.getServer()); }
}
