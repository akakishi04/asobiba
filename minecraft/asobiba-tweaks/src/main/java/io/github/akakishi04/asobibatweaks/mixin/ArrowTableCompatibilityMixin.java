package io.github.akakishi04.asobibatweaks.mixin;

import com.llamalad7.mixinextras.injector.wrapoperation.Operation;
import com.llamalad7.mixinextras.injector.wrapoperation.WrapOperation;
import com.llamalad7.mixinextras.sugar.Local;
import io.github.akakishi04.asobibatweaks.feature.ExtendedEnchantingTargets;
import java.util.List;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.enchantment.Enchantment;
import net.minecraft.world.item.enchantment.EnchantmentHelper;
import net.minecraft.world.item.enchantment.EnchantmentInstance;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;

/**
 * The table's random multi-enchant selection knows the actual target stack.
 * Override only the remove-conflicts step, and only for approved arrow pairs.
 */
@Mixin(EnchantmentHelper.class)
public abstract class ArrowTableCompatibilityMixin {
    @WrapOperation(
            method = "selectEnchantment",
            at = @At(value = "INVOKE", target =
                    "Lnet/minecraft/world/item/enchantment/EnchantmentHelper;filterCompatibleEnchantments(Ljava/util/List;Lnet/minecraft/world/item/enchantment/EnchantmentInstance;)V")
    )
    private static void asobibatweaks$keepCompatibleArrowCandidates(
            List<EnchantmentInstance> candidates,
            EnchantmentInstance selected,
            Operation<Void> original,
            @Local(argsOnly = true) ItemStack targetStack) {
        if (!ExtendedEnchantingTargets.isExtendedArrowTarget(targetStack)) {
            original.call(candidates, selected);
            return;
        }

        candidates.removeIf(next ->
                !ExtendedEnchantingTargets.allowsArrowPair(
                        targetStack, selected.enchantment, next.enchantment)
                        && !Enchantment.areCompatible(
                                selected.enchantment, next.enchantment)
        );
    }
}
