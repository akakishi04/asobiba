package io.github.akakishi04.asobibatweaks.mixin;

import com.llamalad7.mixinextras.injector.ModifyExpressionValue;
import io.github.akakishi04.asobibatweaks.feature.ArrowLootingSupport;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.level.storage.loot.LootContext;
import net.minecraft.world.level.storage.loot.functions.EnchantedCountIncreaseFunction;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;

@Mixin(EnchantedCountIncreaseFunction.class)
public abstract class EnchantedCountIncreaseArrowLootingMixin {
    @ModifyExpressionValue(
            method = "run",
            at = @At(value = "INVOKE",
                    target = "Lnet/minecraft/world/item/enchantment/EnchantmentHelper;getEnchantmentLevel(Lnet/minecraft/core/Holder;Lnet/minecraft/world/entity/LivingEntity;)I")
    )
    private int asobibatweaks$useArrowLootingForCount(
            int vanilla, ItemStack stack, LootContext context) {
        return ArrowLootingSupport.effectiveLevel(
                vanilla,
                ((LootingCountEnchantmentAccessor)(Object)this).asobibatweaks$getEnchantment(),
                context
        );
    }
}
