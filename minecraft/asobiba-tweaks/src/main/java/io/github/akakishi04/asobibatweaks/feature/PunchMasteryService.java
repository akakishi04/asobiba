package io.github.akakishi04.asobibatweaks.feature;

import net.minecraft.world.effect.MobEffectInstance;
import net.minecraft.world.effect.MobEffects;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.projectile.AbstractArrow;
import net.minecraft.world.item.ArrowItem;
import net.minecraft.world.phys.Vec3;

/** Transform the real Punch impulse, separately from generic hurt knockback. */
public final class PunchMasteryService {
    private PunchMasteryService() {}
    public static Vec3 impulse(AbstractArrow arrow, LivingEntity target, Vec3 original) {
        if (!(arrow.getPickupItemStackOrigin().getItem() instanceof ArrowItem)) return original;
        var weapon = arrow.getWeaponItem();
        if (weapon == null) return original;
        var branch = LauncherReloadMasteryEvents.branch(weapon, "minecraft:punch");
        if (branch == null) return original;
        double progress = branch.progress();
        if (branch.choice() == 0) return original.multiply(1.15D + 0.25D * progress, 1, 1.15D + 0.25D * progress);
        if (branch.choice() == 1) {
            double conversion = 0.30D + 0.30D * progress;
            return new Vec3(original.x * (1 - conversion),
                    original.y + original.horizontalDistance() * conversion, original.z * (1 - conversion));
        }
        target.addEffect(new MobEffectInstance(MobEffects.MOVEMENT_SLOWDOWN,
                (int)Math.round(20 + 30 * progress), progress >= 0.75D ? 2 : 1));
        return original.scale(0.25D);
    }
}
