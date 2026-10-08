package io.github.akakishi04.asobibatweaks.mixin;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import io.github.akakishi04.asobibatweaks.feature.ExtendedEnchantingTargets;
import java.util.Optional;
import net.minecraft.core.Holder;
import net.minecraft.core.HolderSet;
import net.minecraft.world.item.ArrowItem;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.item.enchantment.Enchantment;
import net.neoforged.neoforge.common.extensions.IItemExtension;
import org.spongepowered.asm.mixin.Mixin;

/**
 * NeoForge delegates itemstack enchantment eligibility to Item's extension
 * methods. All three vanilla arrow items inherit ArrowItem's overrides.
 */
@Mixin(ArrowItem.class)
public abstract class ArrowEnchantmentEligibilityMixin implements IItemExtension {
    @Override
    public boolean isPrimaryItemFor(ItemStack stack, Holder<Enchantment> enchantment) {
        if (AsobibaTweaksConfig.EXTENDED_ENCHANTING_TARGETS_ENABLED.getAsBoolean()
                && ExtendedEnchantingTargets.isExtendedArrowTarget(stack)) {
            return ExtendedEnchantingTargets.allowsArrowEnchantment(enchantment);
        }
        Optional<HolderSet<Item>> primary = enchantment.value().definition().primaryItems();
        return supportsEnchantment(stack, enchantment)
                && (primary.isEmpty() || stack.is(primary.get()));
    }

    @Override
    public boolean supportsEnchantment(ItemStack stack, Holder<Enchantment> enchantment) {
        if (AsobibaTweaksConfig.EXTENDED_ENCHANTING_TARGETS_ENABLED.getAsBoolean()
                && ExtendedEnchantingTargets.isExtendedArrowTarget(stack)) {
            return ExtendedEnchantingTargets.allowsArrowEnchantment(enchantment);
        }
        return stack.is(Items.ENCHANTED_BOOK) || enchantment.value().isSupportedItem(stack);
    }
}
