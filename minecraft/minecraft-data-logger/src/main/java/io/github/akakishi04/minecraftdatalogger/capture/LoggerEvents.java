package io.github.akakishi04.minecraftdatalogger.capture;

import com.google.gson.JsonObject;
import io.github.akakishi04.minecraftdatalogger.LoggerConfig;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.server.level.ServerPlayer;
import net.neoforged.bus.api.SubscribeEvent;
import net.neoforged.neoforge.event.entity.living.LivingDeathEvent;
import net.neoforged.neoforge.event.entity.player.PlayerEvent;
import net.neoforged.neoforge.event.level.BlockDropsEvent;
import net.neoforged.neoforge.event.server.ServerStoppingEvent;
import net.neoforged.neoforge.event.tick.PlayerTickEvent;

public final class LoggerEvents {
    private final LoggerManager manager = new LoggerManager();

    @SubscribeEvent
    public void onLogin(PlayerEvent.PlayerLoggedInEvent event) {
        if (!LoggerConfig.ENABLED.getAsBoolean()) {
            return;
        }
        if (!(event.getEntity() instanceof ServerPlayer player)) {
            return;
        }

        PlayerLogSession session = manager.open(player);
        if (session != null) {
            JsonObject record = ObservationBuilder.base(session, player, "event");
            record.addProperty("event", "login");
            session.event(record);
        }
    }

    @SubscribeEvent
    public void onLogout(PlayerEvent.PlayerLoggedOutEvent event) {
        if (!(event.getEntity() instanceof ServerPlayer player)) {
            return;
        }

        PlayerLogSession session = manager.get(player);
        if (session != null) {
            JsonObject record = ObservationBuilder.base(session, player, "event");
            record.addProperty("event", "logout");
            session.event(record);
        }
        manager.close(player.getUUID());
    }

    @SubscribeEvent
    public void onPlayerTick(PlayerTickEvent.Post event) {
        if (!LoggerConfig.ENABLED.getAsBoolean()) {
            return;
        }
        if (!(event.getEntity() instanceof ServerPlayer player)) {
            return;
        }

        PlayerLogSession session = manager.get(player);
        if (session == null) {
            return;
        }

        int interval = LoggerConfig.OBSERVATION_INTERVAL_TICKS.getAsInt();
        if (player.level().getGameTime() % interval == 0L) {
            session.observation(ObservationBuilder.build(session, player));
        }
    }

    @SubscribeEvent
    public void onBlockDrops(BlockDropsEvent event) {
        if (!LoggerConfig.ENABLED.getAsBoolean() || !LoggerConfig.CAPTURE_EVENTS.getAsBoolean()) {
            return;
        }
        if (!(event.getBreaker() instanceof ServerPlayer player)) {
            return;
        }

        PlayerLogSession session = manager.get(player);
        if (session == null) {
            return;
        }

        JsonObject record = ObservationBuilder.base(session, player, "event");
        record.addProperty("event", "block_break");
        record.addProperty("block", BuiltInRegistries.BLOCK.getKey(event.getState().getBlock()).toString());
        record.addProperty("x", event.getPos().getX());
        record.addProperty("y", event.getPos().getY());
        record.addProperty("z", event.getPos().getZ());
        session.event(record);
    }

    @SubscribeEvent
    public void onDeath(LivingDeathEvent event) {
        if (!LoggerConfig.ENABLED.getAsBoolean() || !LoggerConfig.CAPTURE_EVENTS.getAsBoolean()) {
            return;
        }
        if (!(event.getSource().getEntity() instanceof ServerPlayer player)) {
            return;
        }

        PlayerLogSession session = manager.get(player);
        if (session == null) {
            return;
        }

        JsonObject record = ObservationBuilder.base(session, player, "event");
        record.addProperty("event", "entity_killed");
        record.addProperty("entity_type", BuiltInRegistries.ENTITY_TYPE.getKey(event.getEntity().getType()).toString());
        session.event(record);
    }

    @SubscribeEvent
    public void onServerStopping(ServerStoppingEvent event) {
        manager.closeAll();
    }
}
