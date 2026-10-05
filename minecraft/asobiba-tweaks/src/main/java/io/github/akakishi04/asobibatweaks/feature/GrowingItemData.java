package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import net.minecraft.core.component.DataComponents;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.tags.ItemTags;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.item.component.CustomData;

public final class GrowingItemData {
    private static final String XP_KEY = "asobibatweaks_growth_xp";
    private static final String MINING_TIER_BONUS_KEY = "asobibatweaks_mining_tier_bonus";

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

    public static int getMiningTierBonus(ItemStack stack) {
        return stack.getOrDefault(DataComponents.CUSTOM_DATA, CustomData.EMPTY)
                .copyTag()
                .getInt(MINING_TIER_BONUS_KEY);
    }

    public static void setMiningTierBonus(ItemStack stack, int bonus) {
        int max = AsobibaTweaksConfig.GROWING_ITEMS_MAX_MINING_TIER_BONUS.getAsInt();
        CompoundTag tag = stack.getOrDefault(DataComponents.CUSTOM_DATA, CustomData.EMPTY).copyTag();
        tag.putInt(MINING_TIER_BONUS_KEY, Math.max(0, Math.min(max, bonus)));
        stack.set(DataComponents.CUSTOM_DATA, CustomData.of(tag));
    }

    public static boolean isPickaxe(ItemStack stack) {
        return stack.is(ItemTags.PICKAXES);
    }

    public static int baseMiningTier(ItemStack stack) {
        if (stack.is(Items.NETHERITE_PICKAXE)) return 4;
        if (stack.is(Items.DIAMOND_PICKAXE)) return 3;
        if (stack.is(Items.IRON_PICKAXE)) return 2;
        if (stack.is(Items.STONE_PICKAXE)) return 1;
        if (stack.is(Items.WOODEN_PICKAXE) || stack.is(Items.GOLDEN_PICKAXE)) return 0;
        return 0;
    }

    public static int effectiveMiningTier(ItemStack stack) {
        return baseMiningTier(stack) + getMiningTierBonus(stack);
    }

    public static String miningTierName(int tier) {
        return switch (tier) {
            case 0 -> "Wood";
            case 1 -> "Stone";
            case 2 -> "Iron";
            case 3 -> "Diamond";
            default -> "Netherite+";
        };
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
