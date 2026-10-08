package io.github.akakishi04.asobibatweaks.mixin;

import com.llamalad7.mixinextras.injector.wrapoperation.Operation;
import com.llamalad7.mixinextras.injector.wrapoperation.WrapOperation;
import io.github.akakishi04.asobibatweaks.feature.VolleyMasteryEvents;
import java.util.List;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.projectile.Projectile;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.ProjectileWeaponItem;
import org.jetbrains.annotations.Nullable;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;

/**
 * Weapon's original projectile loop still controls projectile count, ammo,
 * primary/secondary pickup flags, and durability.
 */
@Mixin(ProjectileWeaponItem.class)
public abstract class ProjectileVolleyMasteryMixin {
    @WrapOperation(method = "shoot",
            at = @At(value = "INVOKE", target =
                    "Lnet/minecraft/world/item/ProjectileWeaponItem;shootProjectile(Lnet/minecraft/world/entity/LivingEntity;Lnet/minecraft/world/entity/projectile/Projectile;IFFFLnet/minecraft/world/entity/LivingEntity;)V"))
    private void asobibatweaks$shapeVolley(
            ProjectileWeaponItem weaponItem, LivingEntity shooter, Projectile projectile,
            int index, float velocity, float inaccuracy, float angle,
            @Nullable LivingEntity target, Operation<Void> original,
            ServerLevel level, LivingEntity originalShooter, InteractionHand hand,
            ItemStack weapon, List<ItemStack> projectiles, float originalVelocity,
            float originalInaccuracy, boolean critical,
            @Nullable LivingEntity originalTarget) {
        float modifiedAngle = VolleyMasteryEvents.spreadAngle(
                weapon, index, projectiles.size(), angle);
        original.call(weaponItem, shooter, projectile, index,
                velocity, inaccuracy, modifiedAngle, target);
        VolleyMasteryEvents.applyVerticalVolley(
                weapon, index, projectiles.size(), angle, projectile);
    }
}
