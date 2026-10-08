package io.github.akakishi04.asobibatweaks.mixin;

import com.llamalad7.mixinextras.injector.ModifyExpressionValue;
import io.github.akakishi04.asobibatweaks.feature.ArrowLootingSupport;
import net.minecraft.world.level.storage.loot.LootContext;
import net.minecraft.world.level.storage.loot.predicates.LootItemRandomChanceWithEnchantedBonusCondition;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;

@Mixin(LootItemRandomChanceWithEnchantedBonusCondition.class)
public abstract class RandomChanceArrowLootingMixin {
    @ModifyExpressionValue(
            method = "test(Lnet/minecraft/world/level/storage/loot/LootContext;)Z",
            at = @At(value = "INVOKE",
                    target = "Lnet/minecraft/world/item/enchantment/EnchantmentHelper;getEnchantmentLevel(Lnet/minecraft/core/Holder;Lnet/minecraft/world/entity/LivingEntity;)I")
    )
    private int asobibatweaks$useArrowLootingForRareDrop(
            int vanilla, LootContext context) {
        LootItemRandomChanceWithEnchantedBonusCondition condition =
                (LootItemRandomChanceWithEnchantedBonusCondition)(Object)this;
        return ArrowLootingSupport.effectiveLevel(
                vanilla, condition.enchantment(), context
        );
    }
}
