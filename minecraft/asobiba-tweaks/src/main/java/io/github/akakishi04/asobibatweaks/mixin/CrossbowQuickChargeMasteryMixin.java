package io.github.akakishi04.asobibatweaks.mixin;

import com.llamalad7.mixinextras.injector.ModifyReturnValue;
import io.github.akakishi04.asobibatweaks.feature.LauncherReloadMasteryEvents;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.item.CrossbowItem;
import net.minecraft.world.item.ItemStack;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;

@Mixin(CrossbowItem.class)
public abstract class CrossbowQuickChargeMasteryMixin {
    @ModifyReturnValue(method = "getChargeDuration", at = @At("RETURN"))
    private static int asobibatweaks$masteryChargeDuration(
            int vanillaTicks, ItemStack stack, LivingEntity shooter) {
        return LauncherReloadMasteryEvents.chargeDuration(stack, shooter, vanillaTicks);
    }
}
