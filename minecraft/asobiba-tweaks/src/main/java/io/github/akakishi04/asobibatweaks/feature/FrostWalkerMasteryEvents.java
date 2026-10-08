package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import java.util.HashSet;
import java.util.Set;
import net.minecraft.core.BlockPos;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.effect.MobEffectInstance;
import net.minecraft.world.effect.MobEffects;
import net.minecraft.world.entity.EquipmentSlot;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.tags.FluidTags;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;
import net.neoforged.bus.api.SubscribeEvent;
import net.neoforged.neoforge.event.tick.PlayerTickEvent;

/**
 * Frost Walker mastery tracks only freshly created Frosted Ice per invocation,
 * not every existing ice block from other players. Terrain reads and
 * transformations never force-load chunks.
 */
public final class FrostWalkerMasteryEvents {
    private static final ThreadLocal<Snapshot> PENDING = new ThreadLocal<>();

    public static LauncherReloadMasteryEvents.Branch branch(ServerPlayer player) {
        if (!AsobibaTweaksConfig.ENCHANTMENT_BRANCHES_ENABLED.getAsBoolean()) return null;
        ItemStack boots = player.getItemBySlot(EquipmentSlot.FEET);
        if (!FrostWalkerToggle.enabled(boots)) return null;
        return LauncherReloadMasteryEvents.branch(boots, "minecraft:frost_walker");
    }

    public static void before(ServerLevel level, ServerPlayer player, int enchantmentLevel) {
        PENDING.remove();
        var branch = branch(player);
        if (branch == null || !player.onGround()) return;
        BlockPos center = player.blockPosition().below();
        int radius = Math.min(16, Math.max(3, 3 + enchantmentLevel));
        Set<Long> existing = new HashSet<>();
        for (int dx = -radius; dx <= radius; dx++) {
            for (int dz = -radius; dz <= radius; dz++) {
                BlockPos pos = center.offset(dx, 0, dz);
                if (level.hasChunkAt(pos) && level.getBlockState(pos).is(Blocks.FROSTED_ICE)) {
                    existing.add(pos.asLong());
                }
            }
        }
        PENDING.set(new Snapshot(center, radius, existing, branch));
    }

    public static void after(ServerLevel level, ServerPlayer player) {
        Snapshot snapshot = PENDING.get();
        PENDING.remove();
        if (snapshot == null) return;

        var branch = snapshot.branch();
        int r = snapshot.radius();
        double t = branch.progress();
        Vec3 input = player.getDeltaMovement().multiply(1.0D, 0.0D, 1.0D);
        if (input.horizontalDistanceSqr() < 0.0004D) {
            input = player.getLookAngle().multiply(1.0D, 0.0D, 1.0D);
        }
        Vec3 forward = input.horizontalDistanceSqr() <= 0.00001D
                ? new Vec3(0.0D, 0.0D, 1.0D) : input.normalize();

        long now = level.getGameTime();
        int changed = 0;
        for (int dx = -r; dx <= r && changed < 768; dx++) {
            for (int dz = -r; dz <= r && changed < 768; dz++) {
                BlockPos pos = snapshot.center().offset(dx, 0, dz);
                if (!level.hasChunkAt(pos) || snapshot.before().contains(pos.asLong())
                        || !level.getBlockState(pos).is(Blocks.FROSTED_ICE)) continue;
                changed++;

                if (branch.choice() == 0) {
                    double longitudinal = dx * forward.x + dz * forward.z;
                    double lateral = Math.abs(dx * -forward.z + dz * forward.x);
                    double maxLateral = r * (0.65D - 0.25D * t);
                    if (lateral > maxLateral || longitudinal < -r * 0.25D) {
                        // Only revert blocks formed during this exact enchant
                        // invocation; do not thaw pre-existing player ice.
                        level.setBlockAndUpdate(pos, Blocks.WATER.defaultBlockState());
                    }
                } else if (branch.choice() == 1) {
                    // FrostedIce normally lasts ~3-5 minutes with age ticks.
                    // Guarantee a longer life: +50%-200% relative to 200 ticks.
                    long guarantee = now + (long)Math.round(200.0D * (1.5D + 1.5D * t));
                    MasteryFrostIceData.get(level).track(level, pos, guarantee, 0L);
                } else if (branch.choice() == 2) {
                    MasteryFrostIceData.get(level).track(level, pos, 0L,
                            now + 60L);
                }
            }
        }

        // Narrow Path extends the accepted directional reach only through
        // currently loaded valid source water under air, never through
        // solid blocks, ice from another player, or unloaded terrain.
        if (branch.choice() == 0 && changed > 0) {
            int reach = Math.min(24, (int)Math.ceil(r * (1.25D + 0.50D * t)));
            int lane = Math.max(1, (int)Math.floor(r * (0.65D - 0.25D * t)));
            int extended = 0;
            for (int step = r; step <= reach && extended < 64; step++) {
                for (int lateral = -lane; lateral <= lane && extended < 64; lateral++) {
                    Vec3 point = new Vec3(snapshot.center().getX(), 0.0D,
                            snapshot.center().getZ())
                            .add(forward.scale(step))
                            .add(-forward.z * lateral, 0.0D, forward.x * lateral);
                    BlockPos pos = new BlockPos((int)Math.round(point.x),
                            snapshot.center().getY(), (int)Math.round(point.z));
                    if (!level.hasChunkAt(pos)
                            || !level.getFluidState(pos).is(FluidTags.WATER)
                            || !level.getBlockState(pos.above()).isAir()) continue;
                    level.setBlockAndUpdate(pos, Blocks.FROSTED_ICE.defaultBlockState());
                    extended++;
                }
            }
        }
    }

    @SubscribeEvent
    public void onFrostAura(PlayerTickEvent.Post event) {
        if (!(event.getEntity() instanceof ServerPlayer player)
                || player.tickCount % 10 != 0
                || !(player.level() instanceof ServerLevel level)) return;
        var branch = branch(player);
        if (branch == null || branch.choice() != 2) return;

        double t = branch.progress();
        double radius = 4.0D + 2.0D * t;
        MasteryFrostIceData data = MasteryFrostIceData.get(level);
        for (LivingEntity target : level.getEntitiesOfClass(LivingEntity.class,
                player.getBoundingBox().inflate(radius, 1.5D, radius),
                candidate -> candidate != player && candidate.isAlive()
                        && candidate.isInWaterOrRain())) {
            BlockPos footing = target.blockPosition().below();
            if (!level.hasChunkAt(footing)
                    || !level.getBlockState(footing).is(Blocks.FROSTED_ICE)
                    || !data.recentlyCreated(level, footing)) continue;
            int amplifier = t >= 0.75D ? 1 : 0;
            int duration = (int)Math.round(30.0D + 30.0D * t);
            target.addEffect(new MobEffectInstance(
                    MobEffects.MOVEMENT_SLOWDOWN, duration, amplifier));
        }
        if (player.tickCount % 200 == 0) data.prune(level.getGameTime());
    }

    private record Snapshot(BlockPos center, int radius,
                            Set<Long> before, LauncherReloadMasteryEvents.Branch branch) {}
}
