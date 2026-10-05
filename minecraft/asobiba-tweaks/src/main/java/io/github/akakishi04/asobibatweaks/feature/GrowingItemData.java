package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import net.minecraft.core.component.DataComponents;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.component.CustomData;

public final class GrowingItemData {
    private static final String XP_KEY = "asobibatweaks_growth_xp";

    private GrowingItemData() {
    }

    public static boolean isEligible(ItemStack stack) {
        return !stack.isEmpty() && stack.isDamageableItem();
    }

    public static int getXp(ItemStack stack) {
        return stack.getOrDefault(DataComponents.CUSTOM_DATA, CustomData.EMPTY)
                .copyTag()
                .getInt(XP_KEY);
    }

    public static void setXp(ItemStack stack, int xp) {
        CompoundTag tag = stack.getOrDefault(DataComponents.CUSTOM_DATA, CustomData.EMPTY).copyTag();
        tag.putInt(XP_KEY, Math.max(0, xp));
        stack.set(DataComponents.CUSTOM_DATA, CustomData.of(tag));
    }

    public static int getLevel(ItemStack stack) {
        return levelForXp(getXp(stack));
    }

    public static int levelForXp(int xp) {
        int baseXp = AsobibaTweaksConfig.GROWING_ITEMS_BASE_XP.getAsInt();
        int maxLevel = AsobibaTweaksConfig.GROWING_ITEMS_MAX_LEVEL.getAsInt();
        int level = 1 + (int) Math.floor(Math.sqrt(Math.max(0, xp) / (double) baseXp));
        return Math.min(maxLevel, Math.max(1, level));
    }

    public static int nextLevelThreshold(int level) {
        int baseXp = AsobibaTweaksConfig.GROWING_ITEMS_BASE_XP.getAsInt();
        return Math.multiplyExact(baseXp, Math.multiplyExact(level, level));
    }
}
