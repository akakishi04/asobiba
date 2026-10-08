package io.github.akakishi04.asobibatweaks.mixin;

import com.llamalad7.mixinextras.injector.wrapoperation.Operation;
import com.llamalad7.mixinextras.injector.wrapoperation.WrapOperation;
import io.github.akakishi04.asobibatweaks.feature.ExtendedEnchantingTargets;
import net.minecraft.core.Holder;
import net.minecraft.world.inventory.AnvilMenu;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.enchantment.Enchantment;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;

/**
 * Permit normally exclusive damage/enchantment combinations only when the
 * first anvil input is a supported arrow. Weapons and armor retain vanilla
 * compatibility restrictions.
 */
@Mixin(AnvilMenu.class)
public abstract class ArrowAnvilCompatibilityMixin {
    @WrapOperation(
            method = "createResult",
            at = @At(value = "INVOKE", target =
                    "Lnet/minecraft/world/item/enchantment/Enchantment;areCompatible(Lnet/minecraft/core/Holder;Lnet/minecraft/core/Holder;)Z")
    )
    private boolean asobibatweaks$acceptArrowEnchantPair(
            Holder<Enchantment> first,
            Holder<Enchantment> second,
            Operation<Boolean> original) {
        ItemStack target = ((AnvilMenu)(Object)this).getSlot(0).getItem();
        if (ExtendedEnchantingTargets.allowsArrowPair(target, first, second)) {
            return true;
        }
        return original.call(first, second);
    }
}
