package io.github.akakishi04.asobibatweaks.mixin;

import net.minecraft.core.Holder;
import net.minecraft.world.item.enchantment.Enchantment;
import net.minecraft.world.level.storage.loot.functions.EnchantedCountIncreaseFunction;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.gen.Accessor;

/** Read the function's configured enchantment, not every enchantment. */
@Mixin(EnchantedCountIncreaseFunction.class)
public interface LootingCountEnchantmentAccessor {
    @Accessor("enchantment")
    Holder<Enchantment> asobibatweaks$getEnchantment();
}
