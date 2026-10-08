package io.github.akakishi04.asobibatweaks.feature;

import java.util.Set;
import net.minecraft.core.Holder;
import net.minecraft.network.chat.contents.TranslatableContents;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.enchantment.Enchantment;
import net.minecraft.world.item.Items;

public final class ExtendedEnchantingTargets {
    private static final Set<String> WORK_BLOCK_EFFECTS =
            Set.of("efficiency", "fortune");

    private static final Set<String> ARROW_EFFECTS = Set.of(
            "power", "punch", "flame", "piercing", "sharpness",
            "smite", "bane_of_arthropods", "impaling", "looting",
            "breach", "wind_burst", "channeling", "loyalty");

    private ExtendedEnchantingTargets() {}

    public static boolean allowsWorkBlockEnchantment(Holder<Enchantment> enchantment) {
        return enchantment.unwrapKey().map(key ->
                "minecraft".equals(key.location().getNamespace())
                        && WORK_BLOCK_EFFECTS.contains(key.location().getPath())).orElse(false);
    }

    public static boolean allowsWorkBlockEnchantment(Enchantment enchantment) {
        if (!(enchantment.description().getContents()
                instanceof TranslatableContents translated)) return false;
        String name = translated.getKey();
        return name.equals("enchantment.minecraft.efficiency")
                || name.equals("enchantment.minecraft.fortune");
    }

    public static boolean allowsArrowEnchantment(Holder<Enchantment> enchantment) {
        return enchantment.unwrapKey().map(key ->
                "minecraft".equals(key.location().getNamespace())
                        && ARROW_EFFECTS.contains(key.location().getPath())
        ).orElse(false);
    }

    /**
     * Only arrows may combine normally conflicting members of the accepted
     * projectile-effect set. Other item types continue using vanilla rules.
     */
    public static boolean allowsArrowPair(
            ItemStack stack, Holder<Enchantment> first, Holder<Enchantment> second) {
        return io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig
                        .EXTENDED_ENCHANTING_TARGETS_ENABLED.getAsBoolean()
                && isExtendedArrowTarget(stack)
                && !first.equals(second)
                && allowsArrowEnchantment(first)
                && allowsArrowEnchantment(second);
    }

    public static boolean allowsArrowEnchantment(Enchantment enchantment) {
        if (!(enchantment.description().getContents()
                instanceof TranslatableContents translated)) return false;
        String prefix = "enchantment.minecraft.";
        String name = translated.getKey();
        return name.startsWith(prefix)
                && ARROW_EFFECTS.contains(name.substring(prefix.length()));
    }


    public static boolean isExtendedTarget(ItemStack stack) {
        return isExtendedBlockTarget(stack) || isExtendedArrowTarget(stack);
    }

    public static boolean isExtendedBlockTarget(ItemStack stack) {
        return stack.is(Items.FURNACE)
                || stack.is(Items.BLAST_FURNACE)
                || stack.is(Items.SMOKER)
                || stack.is(Items.ENCHANTING_TABLE);
    }

    public static boolean isExtendedArrowTarget(ItemStack stack) {
        return stack.is(Items.ARROW)
                || stack.is(Items.SPECTRAL_ARROW)
                || stack.is(Items.TIPPED_ARROW);
    }
}
