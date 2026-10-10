package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.entity.PathfinderMob;
import net.minecraft.world.entity.animal.Animal;
import net.minecraft.world.entity.animal.IronGolem;
import net.minecraft.world.entity.npc.Villager;
import net.neoforged.bus.api.SubscribeEvent;
import net.neoforged.neoforge.event.tick.EntityTickEvent;

public final class MobBuildingUseEvents {
    @SubscribeEvent
    public void onMobTick(EntityTickEvent.Post event) {
        if (!AsobibaTweaksConfig.VILLAGE_SIMULATION_ENABLED.getAsBoolean()
                || !AsobibaTweaksConfig.MOB_USED_BUILDINGS_ENABLED.getAsBoolean()
                || !(event.getEntity() instanceof PathfinderMob mob)
                || mob.level().isClientSide()
                || mob.tickCount % 160 != Math.floorMod(mob.getId(), 160)
                || (!(mob instanceof Animal) && !(mob instanceof Villager) && !(mob instanceof IronGolem))) {
            return;
        }

        ServerLevel level = (ServerLevel)mob.level();
        VillageSimulationScheduler.enqueueValidation(
                level,
                "mob_building:" + mob.getUUID(),
                () -> {
                    if (!AsobibaTweaksConfig.VILLAGE_SIMULATION_ENABLED.getAsBoolean()
                            || !AsobibaTweaksConfig.MOB_USED_BUILDINGS_ENABLED.getAsBoolean()
                            || !mob.isAlive() || mob.isRemoved() || mob.level() != level) return;
                    tickBuildingUse(mob, level);
                }
        );
    }

    private static void tickBuildingUse(PathfinderMob mob, ServerLevel level) {
        if (!MobBuildingUseService.isAvailable(mob, level)) return;
        boolean shelter = level.isRainingAt(mob.blockPosition());
        long dayTime = Math.floorMod(level.getDayTime(), 24000L);
        if (shelter || mob.getRandom().nextDouble() < 0.10D)
            MobBuildingUseService.tryVisit(mob, level, shelter, dayTime > 12500L && dayTime < 22000L);
    }
}
