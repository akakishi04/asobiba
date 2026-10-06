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
        if (level.isRainingAt(mob.blockPosition()) && !mob.getNavigation().isInProgress()) {
            BlockPos shelter = findShelter(level, mob.blockPosition(), 9);
            if (shelter != null) {
                mob.getNavigation().moveTo(shelter.getX() + 0.5D, shelter.getY(), shelter.getZ() + 0.5D, 0.75D);
                return;
            }
        }

        long dayTime = Math.floorMod(level.getDayTime(), 24000L);
        if (dayTime > 12500L && dayTime < 22000L && !mob.getNavigation().isInProgress()
                && mob.getRandom().nextDouble() < 0.10D) {
            BlockPos campfire = findCampfire(level, mob.blockPosition(), 12);
            if (campfire != null) {
                BlockPos target = campfire.offset(
                        mob.getRandom().nextInt(5) - 2,
                        0,
                        mob.getRandom().nextInt(5) - 2
                );
                if (level.getBlockState(target).isAir()
                        && level.getBlockState(target.below()).isFaceSturdy(level, target.below(), Direction.UP)) {
                    mob.getNavigation().moveTo(target.getX() + 0.5D, target.getY(), target.getZ() + 0.5D, 0.6D);
                }
            }
        }
    }

    private static BlockPos findShelter(ServerLevel level, BlockPos center, int radius) {
        BlockPos best = null;
        int bestScore = Integer.MIN_VALUE;
        for (BlockPos pos : BlockPos.betweenClosed(center.offset(-radius, -2, -radius), center.offset(radius, 3, radius))) {
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

    private static BlockPos findCampfire(ServerLevel level, BlockPos center, int radius) {
        for (BlockPos pos : BlockPos.betweenClosed(center.offset(-radius, -3, -radius), center.offset(radius, 3, radius))) {
            if (level.getBlockState(pos).is(Blocks.CAMPFIRE) || level.getBlockState(pos).is(Blocks.SOUL_CAMPFIRE)) {
                return pos.immutable();
            }
        }
        return null;
    }
}
