package io.github.akakishi04.asobibatweaks.feature;

import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.entity.monster.EnderMan;
import net.neoforged.bus.api.SubscribeEvent;
import net.neoforged.neoforge.event.level.LevelEvent;
import net.neoforged.neoforge.event.server.ServerStoppedEvent;
import net.neoforged.neoforge.event.tick.EntityTickEvent;
import net.neoforged.neoforge.event.tick.LevelTickEvent;

/** Loaded-world, server-authoritative scheduling; never creates or teleports participants. */
public final class EndermanVoidGatheringEvents {
    @SubscribeEvent
    public void onLevelTick(LevelTickEvent.Post event) {
        if (event.getLevel() instanceof ServerLevel level) EndermanVoidGatheringService.tick(level);
    }

    @SubscribeEvent
    public void onEntityTick(EntityTickEvent.Post event) {
        if (event.getEntity() instanceof EnderMan enderman && !enderman.level().isClientSide()) {
            EndermanVoidGatheringService.onEntityTick(enderman);
        }
    }

    @SubscribeEvent
    public void onUnload(LevelEvent.Unload event) {
        if (event.getLevel() instanceof ServerLevel level) EndermanVoidGatheringService.stop(level);
    }

    @SubscribeEvent
    public void onServerStopped(ServerStoppedEvent event) {
        EndermanVoidGatheringService.reset();
    }
}
