package io.github.akakishi04.asobibatweaks.mixin;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import io.github.akakishi04.asobibatweaks.feature.ExtendedEnchantingTargets;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.enchantment.Enchantment;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

@Mixin(Enchantment.class)
public abstract class EnchantmentExtensionMixin {
    @Inject(method = "getMaxLevel", at = @At("RETURN"), cancellable = true)
    private void asobibatweaks$raiseMaxLevel(CallbackInfoReturnable<Integer> cir) {
        if (AsobibaTweaksConfig.RAISED_ENCHANTMENT_CAPS_ENABLED.getAsBoolean()) {
            cir.setReturnValue(Math.max(cir.getReturnValue(), AsobibaTweaksConfig.ENCHANTMENT_LEVEL_CAP.getAsInt()));
        }
    }

    @Inject(method = "isSupportedItem", at = @At("HEAD"), cancellable = true)
    private void asobibatweaks$supportExtendedItems(ItemStack stack, CallbackInfoReturnable<Boolean> cir) {
        if (AsobibaTweaksConfig.EXTENDED_ENCHANTING_TARGETS_ENABLED.getAsBoolean()
                && ExtendedEnchantingTargets.isExtendedTarget(stack)) {
            cir.setReturnValue(true);
        }
    }

    @Inject(method = "isPrimaryItem", at = @At("HEAD"), cancellable = true)
    private void asobibatweaks$primaryExtendedItems(ItemStack stack, CallbackInfoReturnable<Boolean> cir) {
        if (AsobibaTweaksConfig.EXTENDED_ENCHANTING_TARGETS_ENABLED.getAsBoolean()
                && ExtendedEnchantingTargets.isExtendedTarget(stack)) {
            cir.setReturnValue(true);
        }
    }

    @Inject(method = "canEnchant", at = @At("HEAD"), cancellable = true)
    private void asobibatweaks$canEnchantExtendedItems(ItemStack stack, CallbackInfoReturnable<Boolean> cir) {
        if (AsobibaTweaksConfig.EXTENDED_ENCHANTING_TARGETS_ENABLED.getAsBoolean()
                && ExtendedEnchantingTargets.isExtendedTarget(stack)) {
            cir.setReturnValue(true);
        }
    }
}
