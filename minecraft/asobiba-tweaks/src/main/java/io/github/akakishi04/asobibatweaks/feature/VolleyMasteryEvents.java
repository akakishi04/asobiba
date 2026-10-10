package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.world.damagesource.DamageSource;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.projectile.AbstractArrow;
import net.minecraft.world.entity.projectile.Projectile;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.phys.Vec3;
import net.neoforged.bus.api.SubscribeEvent;
import net.neoforged.neoforge.event.entity.living.LivingDamageEvent;
import net.neoforged.neoforge.event.entity.living.LivingIncomingDamageEvent;

/**
 * Multishot uses the same physical projectile group and ammo handling as
 * vanilla. Only shot spread/shape changes; no extra projectiles or items.
 *
 * Piercing observes successful arrow hits and operates on per-projectile
 * persistent counters. Each hit remains a distinct damage transaction.
 */
public final class VolleyMasteryEvents {
    private static final String HITS = "asobibatweaks_piercing_mastery_hits";
    private static final String PRE_HIT_SPEED = "asobibatweaks_piercing_speed_before_hit";
    private static final String MOMENTUM_DUE = "asobibatweaks_piercing_momentum_due";

    public static LauncherReloadMasteryEvents.Branch multishot(ItemStack weapon) {
        return LauncherReloadMasteryEvents.branch(weapon, "minecraft:multishot");
    }

    public static float spreadAngle(ItemStack weapon, int index, int projectileCount,
                                    float vanillaAngle) {
        if (index == 0 || projectileCount < 3) return vanillaAngle;
        var branch = multishot(weapon);
        if (branch == null) return vanillaAngle;
        double x = branch.progress();
        return switch (branch.choice()) {
            case 0 -> (float)(vanillaAngle * (0.75D - 0.35D * x));
            case 1 -> (float)(vanillaAngle * (1.25D + 0.55D * x));
            case 2 -> 0.0F;  // Vertical Volley applies pitch below.
            default -> vanillaAngle;
        };
    }

    public static void applyVerticalVolley(ItemStack weapon, int index, int projectileCount,
                                           float vanillaAngle, Projectile projectile) {
        var branch = multishot(weapon);
        if (branch == null || branch.choice() != 2
                || index == 0 || projectileCount < 3) return;

        Vec3 velocity = projectile.getDeltaMovement();
        double speed = velocity.length();
        if (speed <= 0.001D) return;

        double pitchDegrees = Math.abs(vanillaAngle) * (1.0D + 0.40D * branch.progress());
        int sign = (index & 1) == 1 ? 1 : -1;
        // Rotate the final normalized flight direction upward/downward.
        double radians = Math.toRadians(Math.min(45.0D, pitchDegrees)) * sign;
        Vec3 direction = velocity.scale(1.0D / speed);
        double horizontal = Math.sqrt(direction.x * direction.x + direction.z * direction.z);
        double beforePitch = Math.atan2(direction.y, horizontal);
        double nextPitch = Math.max(-Math.PI / 2, Math.min(Math.PI / 2, beforePitch + radians));
        double newHorizontal = Math.cos(nextPitch);
        Vec3 moved = horizontal < 0.0001D
                ? new Vec3(0.0D, Math.sin(nextPitch), 0.0D)
                : new Vec3(direction.x / horizontal * newHorizontal,
                        Math.sin(nextPitch), direction.z / horizontal * newHorizontal);
        projectile.setDeltaMovement(moved.scale(speed));
        projectile.hurtMarked = true;
    }

    private static LauncherReloadMasteryEvents.Branch piercing(AbstractArrow arrow) {
        ItemStack launcher = arrow.getWeaponItem();
        return launcher == null ? null
                : LauncherReloadMasteryEvents.branch(launcher, "minecraft:piercing");
    }

    @SubscribeEvent
    public void onPiercingDamage(LivingIncomingDamageEvent event) {
        if (!AsobibaTweaksConfig.ENCHANTMENT_BRANCHES_ENABLED.getAsBoolean()
                || event.getAmount() <= 0.0F
                || !(event.getSource().getDirectEntity() instanceof AbstractArrow arrow)
                || arrow.level().isClientSide()
                || arrow.getPierceLevel() <= 0) return;
        var branch = piercing(arrow);
        if (branch == null) return;

        CompoundTag marker = arrow.getPersistentData();
        int priorHits = Math.min(3, marker.getInt(HITS));
        if (branch.choice() == 0) {
            marker.putDouble(PRE_HIT_SPEED, arrow.getDeltaMovement().length());
            marker.putBoolean(MOMENTUM_DUE, true);
        } else if (branch.choice() == 2 && priorHits > 0) {
            double perHit = 0.03D + 0.05D * branch.progress();
            event.setAmount((float)Math.min(Float.MAX_VALUE,
                    event.getAmount() * (1.0D + perHit * priorHits)));
        }
    }

    @SubscribeEvent
    public void onPiercingAfterDamage(LivingDamageEvent.Post event) {
        if (!AsobibaTweaksConfig.ENCHANTMENT_BRANCHES_ENABLED.getAsBoolean()
                || event.getNewDamage() <= 0.0F
                || !(event.getSource().getDirectEntity() instanceof AbstractArrow arrow)
                || arrow.level().isClientSide() || arrow.getPierceLevel() <= 0) return;

        var branch = piercing(arrow);
        if (branch == null) return;
        CompoundTag marker = arrow.getPersistentData();
        int hits = Math.min(127, marker.getInt(HITS) + 1);
        marker.putInt(HITS, hits);

        if (branch.choice() == 0 && marker.getBoolean(MOMENTUM_DUE)) {
            marker.remove(MOMENTUM_DUE);
            double previous = marker.getDouble(PRE_HIT_SPEED);
            double current = arrow.getDeltaMovement().length();
            double retained = 0.90D + 0.10D * branch.progress();
            double targetSpeed = Math.max(current, previous * retained);
            if (current > 0.001D && targetSpeed > current + 0.001D) {
                arrow.setDeltaMovement(arrow.getDeltaMovement().scale(targetSpeed / current));
                arrow.hurtMarked = true;
            }
        } else if (branch.choice() == 1 && hits >= arrow.getPierceLevel() + 1) {
            Vec3 horizontal = arrow.getDeltaMovement().multiply(1.0D, 0.0D, 1.0D);
            if (horizontal.lengthSqr() > 0.0001D) {
                Vec3 force = horizontal.normalize().scale(0.15D + 0.25D * branch.progress());
                event.getEntity().push(force.x, 0.10D, force.z);
                event.getEntity().hurtMarked = true;
            }
        }
    }
}
