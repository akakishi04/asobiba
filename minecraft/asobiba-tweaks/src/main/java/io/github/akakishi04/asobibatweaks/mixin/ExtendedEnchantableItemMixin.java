package io.github.akakishi04.asobibatweaks.mixin;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import io.github.akakishi04.asobibatweaks.feature.ExtendedEnchantingTargets;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.ItemStack;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

@Mixin(Item.class)
public abstract class ExtendedEnchantableItemMixin {
    @Inject(method = "isEnchantable", at = @At("HEAD"), cancellable = true)
    private void asobibatweaks$allowExtendedEnchanting(ItemStack stack, CallbackInfoReturnable<Boolean> cir) {
        if (AsobibaTweaksConfig.EXTENDED_ENCHANTING_TARGETS_ENABLED.getAsBoolean()
                && ExtendedEnchantingTargets.isExtendedTarget(stack)) {
            cir.setReturnValue(true);
        }
    }

    @Inject(method = "getEnchantmentValue", at = @At("HEAD"), cancellable = true)
    private void asobibatweaks$extendedEnchantability(CallbackInfoReturnable<Integer> cir) {
        Item self = (Item)(Object)this;
        ItemStack probe = new ItemStack(self);
        if (AsobibaTweaksConfig.EXTENDED_ENCHANTING_TARGETS_ENABLED.getAsBoolean()
                && ExtendedEnchantingTargets.isExtendedTarget(probe)) {
            cir.setReturnValue(10);
        }
    }
}
