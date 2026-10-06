package io.github.akakishi04.asobibatweaks.feature;

import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;

public final class ExtendedEnchantingTargets {
    private ExtendedEnchantingTargets() {}

    public static boolean isExtendedTarget(ItemStack stack) {
        return stack.is(Items.CRAFTING_TABLE)
                || stack.is(Items.FURNACE)
                || stack.is(Items.BLAST_FURNACE)
                || stack.is(Items.SMOKER)
                || stack.is(Items.ENCHANTING_TABLE)
                || stack.is(Items.ARROW)
                || stack.is(Items.SPECTRAL_ARROW)
                || stack.is(Items.TIPPED_ARROW);
    }
}
