package io.github.akakishi04.asobibatweaks.feature;

import net.minecraft.world.item.ItemStack;

/** Effective Mending level and direct durability-per-XP curve. */
public final class MendingLevelHelper {
    private MendingLevelHelper() {}

    public static int level(ItemStack stack) {
        if (stack.isEmpty()) return 0;
        for (var entry : EnchantmentMasteryData.enchantments(stack).entrySet()) {
            if ("minecraft:mending".equals(EnchantmentMasteryData.id(entry.getKey()))) {
                return Math.max(0, entry.getIntValue());
            }
        }
        return 0;
    }

    public static int durabilityPerXp(int level) {
        if (level <= 0) return 0;
        return Math.min(4, level + 1);
    }
}
