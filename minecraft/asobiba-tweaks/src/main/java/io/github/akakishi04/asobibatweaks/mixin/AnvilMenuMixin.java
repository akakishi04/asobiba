package io.github.akakishi04.asobibatweaks.mixin;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import io.github.akakishi04.asobibatweaks.feature.ExtendedEnchantingTargets;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.inventory.DataSlot;
import org.spongepowered.asm.mixin.Shadow;
import org.spongepowered.asm.mixin.Final;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;
import net.minecraft.world.inventory.AnvilMenu;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.Constant;
import org.spongepowered.asm.mixin.injection.ModifyConstant;

@Mixin(AnvilMenu.class)
public abstract class AnvilMenuMixin {
    @Shadow @Final private DataSlot cost;

    /**
     * AnvilMenu operates on the whole input ItemStack, not just one
     * projectile. Never allow applying a paid enchantment to a stack
     * of 2-64 arrows for the price of one enchantment.
     */
    @Inject(method = "createResult", at = @At("HEAD"), cancellable = true)
    private void asobibatweaks$singleArrowEnchantmentUnit(CallbackInfo ci) {
        AnvilMenu menu = (AnvilMenu)(Object)this;
        ItemStack input = menu.getSlot(AnvilMenu.INPUT_SLOT).getItem();
        if (!AsobibaTweaksConfig.EXTENDED_ENCHANTING_TARGETS_ENABLED.getAsBoolean()
                || !ExtendedEnchantingTargets.isExtendedArrowTarget(input)
                || input.getCount() <= 1) return;

        this.cost.set(0);
        menu.getSlot(AnvilMenu.RESULT_SLOT).set(ItemStack.EMPTY);
        menu.broadcastChanges();
        ci.cancel();
    }


    @ModifyConstant(method = "createResult", constant = @Constant(intValue = 40))
    private int asobibatweaks$removeTooExpensiveLimit(int original) {
        return AsobibaTweaksConfig.UNCAPPED_ANVIL_ENABLED.getAsBoolean() ? Integer.MAX_VALUE : original;
    }
}
