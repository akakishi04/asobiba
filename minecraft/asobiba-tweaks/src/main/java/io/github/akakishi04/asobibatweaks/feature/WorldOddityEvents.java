package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import java.util.Comparator;
import java.util.List;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Rotations;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.entity.Mob;
import net.minecraft.world.entity.PathfinderMob;
import net.minecraft.world.entity.animal.Animal;
import net.minecraft.world.entity.animal.Parrot;
import net.minecraft.world.entity.decoration.ArmorStand;
import net.minecraft.world.entity.monster.EnderMan;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.BlockState;
import net.neoforged.bus.api.SubscribeEvent;
import net.neoforged.neoforge.event.tick.EntityTickEvent;

public final class WorldOddityEvents {
    @SubscribeEvent
    public void onEntityTick(EntityTickEvent.Post event) {
        if (event.getEntity().level().isClientSide()) return;
        if (event.getEntity() instanceof EnderMan enderman) tickEnderman(enderman);
        if (event.getEntity() instanceof Parrot parrot) tickParrot(parrot);
        if (event.getEntity() instanceof Animal animal) tickGathering(animal);
        if (event.getEntity() instanceof ArmorStand stand) tickArmorStand(stand);
        if (AsobibaTweaksConfig.MOB_ON_MOB_RIDING_ENABLED.getAsBoolean() && event.getEntity() instanceof Mob mob) {
            tryMobRide(mob);
        }
    }

    private static void tickEnderman(EnderMan enderman) {
        if (!AsobibaTweaksConfig.ENDERMAN_MICRO_BUILD_ENABLED.getAsBoolean()
                || enderman.getCarriedBlock() == null
                || enderman.tickCount % 400 != Math.floorMod(enderman.getId(), 400)
                || enderman.getRandom().nextInt(160) != 0) return;

        ServerLevel level = (ServerLevel)enderman.level();
        BlockState carried = enderman.getCarriedBlock();
        var data = enderman.getPersistentData();

        if (!data.getBoolean("asobibatweaks_micro_active")) {
            BlockPos origin = enderman.blockPosition().offset(
                    enderman.getRandom().nextInt(7) - 3,
                    0,
                    enderman.getRandom().nextInt(7) - 3
            );
            origin = new BlockPos(
                    origin.getX(),
                    level.getHeight(net.minecraft.world.level.levelgen.Heightmap.Types.MOTION_BLOCKING_NO_LEAVES,
                            origin.getX(), origin.getZ()),
                    origin.getZ()
            );
            data.putBoolean("asobibatweaks_micro_active", true);
            data.putInt("asobibatweaks_micro_x", origin.getX());
            data.putInt("asobibatweaks_micro_y", origin.getY());
            data.putInt("asobibatweaks_micro_z", origin.getZ());
            data.putInt("asobibatweaks_micro_step", 0);
            data.putInt("asobibatweaks_micro_length", 2 + enderman.getRandom().nextInt(4));
            data.putInt("asobibatweaks_micro_pattern", enderman.getRandom().nextInt(4));
        }

        BlockPos origin = new BlockPos(
                data.getInt("asobibatweaks_micro_x"),
                data.getInt("asobibatweaks_micro_y"),
                data.getInt("asobibatweaks_micro_z")
        );
        int step = data.getInt("asobibatweaks_micro_step");
        int length = data.getInt("asobibatweaks_micro_length");
        int pattern = data.getInt("asobibatweaks_micro_pattern");
        BlockPos target = microBuildTarget(origin, step, pattern);

        boolean placed = level.getBlockState(target).canBeReplaced()
                && level.getBlockState(target.below()).isFaceSturdy(
                        level, target.below(), net.minecraft.core.Direction.UP);

        if (placed) {
            level.setBlockAndUpdate(target, carried);
            enderman.setCarriedBlock(null);
            step++;
            data.putInt("asobibatweaks_micro_step", step);
        } else {
            data.remove("asobibatweaks_micro_active");
            return;
        }

        if (step >= length) {
            data.remove("asobibatweaks_micro_active");
            data.remove("asobibatweaks_micro_step");
            data.remove("asobibatweaks_micro_length");
            data.remove("asobibatweaks_micro_pattern");
        }
    }

    private static BlockPos microBuildTarget(BlockPos origin, int step, int pattern) {
        return switch (pattern) {
            case 0 -> origin.above(step); // tiny pillar
            case 1 -> origin.offset(step, step % 2, 0); // crude stair
            case 2 -> switch (step) { // tiny L / corner
                case 0 -> origin;
                case 1 -> origin.east();
                case 2 -> origin.east().south();
                case 3 -> origin.east().south().above();
                default -> origin.east().south().above(step - 2);
            };
            default -> switch (step) { // little arch-like shape
                case 0 -> origin;
                case 1 -> origin.east(2);
                case 2 -> origin.above();
                case 3 -> origin.east(2).above();
                default -> origin.east().above(2);
            };
        };
    }

    private static void tickParrot(Parrot parrot) {
        if (!AsobibaTweaksConfig.PARROT_PERCHES_ENABLED.getAsBoolean() || parrot.isPassenger()) return;

        BlockState below = parrot.level().getBlockState(parrot.blockPosition().below());
        boolean perch = below.is(Blocks.CHAIN)
                || below.is(Blocks.END_ROD)
                || below.is(net.minecraft.tags.BlockTags.FENCES)
                || below.is(net.minecraft.tags.BlockTags.WALLS);

        boolean auto = parrot.getPersistentData().getBoolean("asobibatweaks_auto_perched");
        if (perch && parrot.onGround() && parrot.getTarget() == null && !parrot.isOrderedToSit()) {
            parrot.setOrderedToSit(true);
            parrot.getPersistentData().putBoolean("asobibatweaks_auto_perched", true);
        } else if (auto && !perch) {
            parrot.setOrderedToSit(false);
            parrot.getPersistentData().remove("asobibatweaks_auto_perched");
        }
    }

    private static void tickGathering(Animal animal) {
        if (!AsobibaTweaksConfig.MOB_GATHERINGS_ENABLED.getAsBoolean() || animal.isBaby()) return;

        long now = animal.level().getGameTime();
        long until = animal.getPersistentData().getLong("asobibatweaks_gather_until");
        if (until > now && animal instanceof PathfinderMob pathfinder) {
            double cx = animal.getPersistentData().getDouble("asobibatweaks_gather_x");
            double cy = animal.getPersistentData().getDouble("asobibatweaks_gather_y");
            double cz = animal.getPersistentData().getDouble("asobibatweaks_gather_z");
            if (animal.level().getNearestPlayer(animal, 5.0D) != null) {
                animal.getPersistentData().remove("asobibatweaks_gather_until");
                pathfinder.getNavigation().stop();
                return;
            }
            pathfinder.getLookControl().setLookAt(cx, cy, cz);
            return;
        }

        if (animal.tickCount % 1200 != Math.floorMod(animal.getId(), 1200)
                || animal.getRandom().nextDouble() >= AsobibaTweaksConfig.MOB_GATHERING_CHANCE.getAsDouble()) return;

        List<Animal> same = animal.level().getEntitiesOfClass(
                Animal.class,
                animal.getBoundingBox().inflate(10.0D),
                other -> other.getType() == animal.getType() && other.isAlive() && !other.isBaby() && !other.isPassenger()
        );
        if (same.size() < 4) return;

        same = same.stream()
                .sorted(Comparator.comparingDouble(animal::distanceToSqr))
                .limit(7)
                .toList();

        double cx = same.stream().mapToDouble(Mob::getX).average().orElse(animal.getX());
        double cy = same.stream().mapToDouble(Mob::getY).average().orElse(animal.getY());
        double cz = same.stream().mapToDouble(Mob::getZ).average().orElse(animal.getZ());

        for (int i = 0; i < same.size(); i++) {
            Animal member = same.get(i);
            if (!(member instanceof PathfinderMob pathfinder)) continue;
            double angle = Math.PI * 2.0D * i / same.size();
            double tx = cx + Math.cos(angle) * 2.2D;
            double tz = cz + Math.sin(angle) * 2.2D;
            pathfinder.getNavigation().moveTo(tx, cy, tz, 0.9D);
            member.getPersistentData().putLong("asobibatweaks_gather_until", now + 400L);
            member.getPersistentData().putDouble("asobibatweaks_gather_x", cx);
            member.getPersistentData().putDouble("asobibatweaks_gather_y", cy);
            member.getPersistentData().putDouble("asobibatweaks_gather_z", cz);
        }
    }

    private static void tickArmorStand(ArmorStand stand) {
        if (!AsobibaTweaksConfig.ARMOR_STAND_POSE_DRIFT_ENABLED.getAsBoolean()
                || stand.tickCount % 2400 != Math.floorMod(stand.getId(), 2400)
                || stand.level().getNearestPlayer(stand, 12.0D) != null
                || stand.getRandom().nextDouble() >= AsobibaTweaksConfig.ARMOR_STAND_POSE_DRIFT_CHANCE.getAsDouble()) return;

        switch (stand.getRandom().nextInt(4)) {
            case 0 -> stand.setHeadPose(new Rotations(
                    stand.getRandom().nextFloat() * 10.0F - 5.0F,
                    stand.getRandom().nextFloat() * 18.0F - 9.0F,
                    stand.getRandom().nextFloat() * 8.0F - 4.0F));
            case 1 -> {
                stand.setShowArms(true);
                stand.setLeftArmPose(new Rotations(
                        stand.getRandom().nextFloat() * 16.0F - 8.0F,
                        0.0F,
                        stand.getRandom().nextFloat() * 12.0F - 6.0F));
            }
            case 2 -> {
                stand.setShowArms(true);
                stand.setRightArmPose(new Rotations(
                        stand.getRandom().nextFloat() * 16.0F - 8.0F,
                        0.0F,
                        stand.getRandom().nextFloat() * 12.0F - 6.0F));
            }
            default -> stand.setBodyPose(new Rotations(
                    stand.getRandom().nextFloat() * 8.0F - 4.0F,
                    stand.getRandom().nextFloat() * 8.0F - 4.0F,
                    stand.getRandom().nextFloat() * 6.0F - 3.0F));
        }
    }

    private static void tryMobRide(Mob mob) {
        if (mob.isPassenger()
                || mob.isVehicle()
                || mob.getBbWidth() > 0.75F
                || mob.getBbHeight() > 1.15F
                || mob.tickCount % 2400 != Math.floorMod(mob.getId(), 2400)
                || mob.getRandom().nextInt(240) != 0) return;

        List<Mob> hosts = mob.level().getEntitiesOfClass(
                Mob.class,
                mob.getBoundingBox().inflate(3.0D),
                other -> other != mob
                        && !other.isPassenger()
                        && !other.isVehicle()
                        && other.getBbWidth() > mob.getBbWidth() * 1.4F
                        && other.getBbHeight() > mob.getBbHeight() * 1.2F
        );
        if (!hosts.isEmpty()) mob.startRiding(hosts.get(mob.getRandom().nextInt(hosts.size())), true);
    }
}
