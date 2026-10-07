package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.entity.PathfinderMob;
import net.minecraft.world.entity.animal.Animal;
import net.minecraft.world.entity.animal.IronGolem;
import net.minecraft.world.entity.npc.Villager;
import net.minecraft.world.level.block.Blocks;
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
                    if (!mob.isAlive() || mob.isRemoved() || mob.level() != level) return;
                    tickBuildingUse(mob, level);
                }
        );
    }

    private static void tickBuildingUse(PathfinderMob mob, ServerLevel level) {
        if (level.isRainingAt(mob.blockPosition()) && !mob.getNavigation().isInProgress()) {
            BlockPos shelter = findShelter(level, mob.blockPosition(), 9, mob);
            if (shelter != null) {
                mob.getNavigation().moveTo(shelter.getX() + 0.5D, shelter.getY(), shelter.getZ() + 0.5D, 0.75D);
                return;
            }
        }

        long dayTime = Math.floorMod(level.getDayTime(), 24000L);
        if (dayTime > 12500L && dayTime < 22000L && !mob.getNavigation().isInProgress()
                && mob.getRandom().nextDouble() < 0.10D) {
            BlockPos campfire = findCampfire(level, mob.blockPosition(), 12, mob);
            if (campfire != null) {
                BlockPos target = campfire.offset(
                        mob.getRandom().nextInt(5) - 2,
                        0,
                        mob.getRandom().nextInt(5) - 2
                );
                if (VillageSimulationScheduler.isChunkLoaded(level, target)
                        && level.getBlockState(target).isAir()
                        && level.getBlockState(target.below()).isFaceSturdy(level, target.below(), Direction.UP)) {
                    mob.getNavigation().moveTo(target.getX() + 0.5D, target.getY(), target.getZ() + 0.5D, 0.6D);
                }
            }
        }
    }

    private static BlockPos findShelter(ServerLevel level, BlockPos center, int radius, PathfinderMob mob) {
        BlockPos min = center.offset(-radius, -2, -radius);
        BlockPos max = center.offset(radius, 3, radius);
        if (!VillageSimulationScheduler.isAreaLoaded(level, min, max)) return null;

        BlockPos best = null;
        int bestScore = Integer.MIN_VALUE;
        for (int attempt = 0; attempt < 64; attempt++) {
            if (!VillageSimulationScheduler.tryConsumeBlockProbe(level)) break;
            BlockPos pos = center.offset(
                    mob.getRandom().nextInt(radius * 2 + 1) - radius,
                    mob.getRandom().nextInt(6) - 2,
                    mob.getRandom().nextInt(radius * 2 + 1) - radius
            );
            if (!level.getBlockState(pos).isAir()
                    || !level.getBlockState(pos.above()).isAir()
                    || !level.getBlockState(pos.below()).isFaceSturdy(level, pos.below(), Direction.UP)
                    || level.canSeeSky(pos)) {
                continue;
            }

            int walls = 0;
            for (Direction dir : Direction.Plane.HORIZONTAL) {
                if (!level.getBlockState(pos.relative(dir)).isAir()) walls++;
            }
            int score = walls * 4 - (int)center.distManhattan(pos);
            if (level.getBlockState(pos.above(2)).isFaceSturdy(level, pos.above(2), Direction.DOWN)) score += 6;
            if (score > bestScore) {
                bestScore = score;
                best = pos.immutable();
            }
        }
        return best;
    }

    private static BlockPos findCampfire(ServerLevel level, BlockPos center, int radius, PathfinderMob mob) {
        BlockPos min = center.offset(-radius, -3, -radius);
        BlockPos max = center.offset(radius, 3, radius);
        if (!VillageSimulationScheduler.isAreaLoaded(level, min, max)) return null;

        for (int attempt = 0; attempt < 64; attempt++) {
            if (!VillageSimulationScheduler.tryConsumeBlockProbe(level)) return null;
            BlockPos pos = center.offset(
                    mob.getRandom().nextInt(radius * 2 + 1) - radius,
                    mob.getRandom().nextInt(7) - 3,
                    mob.getRandom().nextInt(radius * 2 + 1) - radius
            );
            if (level.getBlockState(pos).is(Blocks.CAMPFIRE) || level.getBlockState(pos).is(Blocks.SOUL_CAMPFIRE)) {
                return pos.immutable();
            }
        }
        return null;
    }
}
