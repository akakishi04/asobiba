package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import java.util.Comparator;
import java.util.List;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Holder;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.LightningBolt;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.projectile.ThrownTrident;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.enchantment.Enchantment;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.EntityHitResult;
import net.minecraft.world.phys.HitResult;
import net.minecraft.world.phys.Vec3;
import net.neoforged.bus.api.SubscribeEvent;
import net.neoforged.neoforge.event.entity.ProjectileImpactEvent;

/**
 * Channeling mastery effects for thrown tridents.
 *
 * <p>Normal vanilla thunderstorm lightning is not replaced. Extra strikes are bounded,
 * non-recursive and never load a chunk. A future enchanted-ammo pass can reuse the
 * branch semantics without assuming that a bow's weapon stack is its arrow stack.</p>
 */
public final class ChannelingMasteryEvents {
    private static final String CHANNELING = "minecraft:channeling";
    private static final String IMPACT_HANDLED = "asobibatweaks_channeling_mastery_impact";
    private static final float PRIMARY_LIGHTNING_DAMAGE = 5.0F;

    @SubscribeEvent
    public void onProjectileImpact(ProjectileImpactEvent event) {
        if (event.isCanceled()
                || !AsobibaTweaksConfig.GROWING_ENCHANTMENTS_ENABLED.getAsBoolean()
                || !AsobibaTweaksConfig.ENCHANTMENT_BRANCHES_ENABLED.getAsBoolean()
                || !(event.getProjectile() instanceof ThrownTrident trident)
                || !(trident.level() instanceof ServerLevel level)
                || !(trident.getOwner() instanceof ServerPlayer player)) {
            return;
        }

        if (trident.getPersistentData().getBoolean(IMPACT_HANDLED)) return;

        Branch selected = selectedBranch(trident.getWeaponItem());
        if (selected == null) return;

        HitResult hit = event.getRayTraceResult();
        if (hit.getType() == HitResult.Type.MISS) return;
        Vec3 at = hit.getLocation();
        BlockPos position = BlockPos.containing(at);

        // Keep the same open-sky prerequisite as ordinary Channeling.
        if (!level.canSeeSky(position.above())) return;

        boolean thunder = level.isThundering();
        boolean ordinaryRain = !thunder && level.isRainingAt(position.above());
        if (!thunder && !ordinaryRain) return;

        trident.getPersistentData().putBoolean(IMPACT_HANDLED, true);
        double mastery = Math.max(0.0D, Math.min(1.0D, (selected.mastery - 50) / 50.0D));

        if (selected.branch == 0 && thunder) {
            chainLightning(level, player, hit, at, mastery);
        } else if (selected.branch == 1 && ordinaryRain) {
            double chance = 0.15D + 0.35D * mastery;
            if (level.random.nextDouble() < chance) {
                spawnCosmeticLightning(level, player, at);
                if (hit instanceof EntityHitResult entityHit && entityHit.getEntity() instanceof LivingEntity target) {
                    if (target.isAlive() && target != player) {
                        target.hurt(level.damageSources().lightningBolt(), PRIMARY_LIGHTNING_DAMAGE * 0.5F);
                    }
                }
            }
        } else if (selected.branch == 2 && thunder) {
            conductorStrike(level, player, hit, position, mastery);
        }
    }

    private static Branch selectedBranch(ItemStack weapon) {
        if (weapon.isEmpty()) return null;
        for (Holder<Enchantment> enchantment : EnchantmentMasteryData.enchantments(weapon).keySet()) {
            if (!CHANNELING.equals(EnchantmentMasteryData.id(enchantment))) continue;
            int mastery = EnchantmentMasteryData.getMastery(weapon, enchantment);
            int choice = EnchantmentMasteryData.getBranch(weapon, enchantment);
            return mastery >= 50 && choice >= 0 && choice <= 2 ? new Branch(mastery, choice) : null;
        }
        return null;
    }

    private static void chainLightning(ServerLevel level, ServerPlayer player, HitResult hit, Vec3 origin, double mastery) {
        int maxTargets = 1 + (mastery >= 0.5D ? 1 : 0) + (mastery >= 1.0D ? 1 : 0);
        double radius = 4.0D + 2.0D * mastery;
        float damage = (float)(PRIMARY_LIGHTNING_DAMAGE * (0.35D + 0.15D * mastery));

        Entity original = hit instanceof EntityHitResult entityHit ? entityHit.getEntity() : null;
        List<LivingEntity> targets = level.getEntitiesOfClass(
                LivingEntity.class,
                new AABB(origin, origin).inflate(radius),
                entity -> entity.isAlive()
                        && entity != player && entity != original
                        && entity.distanceToSqr(origin) <= radius * radius
                        && level.canSeeSky(entity.blockPosition().above())
        );
        targets.sort(Comparator
                .comparingDouble((LivingEntity entity) -> entity.distanceToSqr(origin))
                .thenComparing(entity -> entity.getUUID().toString()));

        int struck = 0;
        for (LivingEntity target : targets) {
            if (struck >= maxTargets) break;
            spawnCosmeticLightning(level, player, target.position());
            target.hurt(level.damageSources().lightningBolt(), damage);
            struck++;
        }
    }

    private static void conductorStrike(ServerLevel level, ServerPlayer player, HitResult hit,
                                        BlockPos origin, double mastery) {
        int radius = (int)Math.round(4.0D + 4.0D * mastery);
        BlockPos min = origin.offset(-radius, -2, -radius);
        BlockPos max = origin.offset(radius, 2, radius);
        if (!VillageSimulationScheduler.isAreaLoaded(level, min, max)) return;

        BlockPos best = null;
        int bestRank = Integer.MAX_VALUE;
        double bestDistance = Double.POSITIVE_INFINITY;

        // Only executed for a player-owned, mastery-enabled trident impact in a thunderstorm.
        // At level 100 this scans at most 17x17x5 blocks once per thrown trident.
        for (int dx = -radius; dx <= radius; dx++) {
            for (int dz = -radius; dz <= radius; dz++) {
                if (dx * dx + dz * dz > radius * radius) continue;
                for (int dy = -2; dy <= 2; dy++) {
                    BlockPos candidate = origin.offset(dx, dy, dz);
                    Block block = level.getBlockState(candidate).getBlock();
                    int rank = block == Blocks.LIGHTNING_ROD ? 0 : isCopperConductor(block) ? 1 : -1;
                    if (rank < 0 || !level.canSeeSky(candidate.above())) continue;

                    double dist = candidate.distSqr(origin);
                    if (rank < bestRank || (rank == bestRank && dist < bestDistance)) {
                        bestRank = rank;
                        bestDistance = dist;
                        best = candidate.immutable();
                    }
                }
            }
        }

        if (best == null || best.equals(origin)) return;

        if (bestRank == 0) {
            // A real, zero-damage strike can activate a lightning rod without adding a
            // second combat-damage pulse to the ordinary vanilla Channeling impact.
            LightningBolt bolt = new LightningBolt(EntityType.LIGHTNING_BOLT, level);
            bolt.moveTo(Vec3.atBottomCenterOf(best.above()));
            bolt.setDamage(0.0F);
            bolt.setCause(player);
            level.addFreshEntity(bolt);
        } else {
            // Copper makes an audible/visible secondary path; avoid producing free fire,
            // item drops or an extra full lightning-damage event.
            spawnCosmeticLightning(level, player, Vec3.atCenterOf(best));
        }
    }

    private static boolean isCopperConductor(Block block) {
        return block == Blocks.COPPER_BLOCK
                || block == Blocks.EXPOSED_COPPER
                || block == Blocks.WEATHERED_COPPER
                || block == Blocks.OXIDIZED_COPPER
                || block == Blocks.WAXED_COPPER_BLOCK
                || block == Blocks.WAXED_EXPOSED_COPPER
                || block == Blocks.WAXED_WEATHERED_COPPER
                || block == Blocks.WAXED_OXIDIZED_COPPER;
    }

    private static void spawnCosmeticLightning(ServerLevel level, ServerPlayer cause, Vec3 at) {
        LightningBolt bolt = new LightningBolt(EntityType.LIGHTNING_BOLT, level);
        bolt.moveTo(at.x, at.y, at.z);
        bolt.setVisualOnly(true);
        bolt.setCause(cause);
        level.addFreshEntity(bolt);
    }

    private record Branch(int mastery, int branch) {
    }
}
