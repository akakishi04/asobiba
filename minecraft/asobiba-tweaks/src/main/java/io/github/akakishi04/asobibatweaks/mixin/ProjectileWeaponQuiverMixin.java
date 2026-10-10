package io.github.akakishi04.asobibatweaks.mixin;

import com.llamalad7.mixinextras.injector.ModifyExpressionValue;
import io.github.akakishi04.asobibatweaks.feature.QuiverAmmoEvents;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.ProjectileWeaponItem;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

@Mixin(ProjectileWeaponItem.class)
public abstract class ProjectileWeaponQuiverMixin {
    @ModifyExpressionValue(
            method = "useAmmo",
            at = @At(value = "INVOKE",
                    target = "Lnet/minecraft/world/item/enchantment/EnchantmentHelper;processAmmoUse(Lnet/minecraft/server/level/ServerLevel;Lnet/minecraft/world/item/ItemStack;Lnet/minecraft/world/item/ItemStack;I)I")
    )
    private static int asobibatweaks$specialAmmoNotFree(
            int vanilla, ItemStack weapon, ItemStack ammo, LivingEntity shooter,
            boolean secondary) {
        return QuiverAmmoEvents.forceConsumableSpecialArrow(
                vanilla, weapon, ammo, secondary, shooter.hasInfiniteMaterials());
    }

    @Inject(method = "useAmmo", at = @At("RETURN"))
    private static void asobibatweaks$commitQuiverConsumption(
            ItemStack weapon, ItemStack ammo, LivingEntity shooter,
            boolean secondary, CallbackInfoReturnable<ItemStack> cir) {
        if (shooter.level() instanceof ServerLevel) QuiverAmmoEvents.commitAmmoUse(ammo, cir.getReturnValue());
    }
}
