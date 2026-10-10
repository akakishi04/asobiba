package io.github.akakishi04.asobibatweaks.feature;

import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.entity.npc.Villager;
import net.neoforged.bus.api.SubscribeEvent;
import net.neoforged.neoforge.event.entity.EntityLeaveLevelEvent;
import net.neoforged.neoforge.event.level.LevelEvent;
import net.neoforged.neoforge.event.server.ServerStoppedEvent;
import net.neoforged.neoforge.event.tick.EntityTickEvent;
import net.neoforged.neoforge.event.tick.LevelTickEvent;

/** Server-only, transient scenes; priority and route safety checked before and after native AI. */
public final class VillagerArmorStandImitationEvents {
    @SubscribeEvent public void onLevelTick(LevelTickEvent.Post event) {
        if (event.getLevel() instanceof ServerLevel level) VillagerArmorStandImitationService.tick(level);
    }
    @SubscribeEvent public void onEntityPre(EntityTickEvent.Pre event) {
        if (event.getEntity() instanceof Villager villager) VillagerArmorStandImitationService.onEntityTick(villager, false);
    }
    @SubscribeEvent public void onEntityPost(EntityTickEvent.Post event) {
        if (event.getEntity() instanceof Villager villager) VillagerArmorStandImitationService.onEntityTick(villager, true);
    }
    @SubscribeEvent public void onLeave(EntityLeaveLevelEvent event) {
        if (event.getLevel() instanceof ServerLevel level) VillagerArmorStandImitationService.onLeave(event.getEntity(), level);
    }
    @SubscribeEvent public void onUnload(LevelEvent.Unload event) {
        if (event.getLevel() instanceof ServerLevel level) VillagerArmorStandImitationService.stop(level);
    }
    @SubscribeEvent public void onStop(ServerStoppedEvent event) { VillagerArmorStandImitationService.reset(); }
}
