package io.github.akakishi04.asobibatweaks.feature;

import java.util.Set;
import net.minecraft.core.Holder;
import net.minecraft.core.component.DataComponents;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.tags.EnchantmentTags;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.component.CustomData;
import net.minecraft.world.item.enchantment.Enchantment;
import net.minecraft.world.item.enchantment.EnchantmentHelper;
import net.minecraft.world.item.enchantment.ItemEnchantments;

public final class EnchantmentMasteryData {
    private static final String MASTERY = "asobibatweaks_enchantment_mastery";
    private static final String BRANCHES = "asobibatweaks_enchantment_branches";
    private static final String STORED_EXCLUSIVE = "asobibatweaks_stored_exclusive";
    private static final String STORED_EXCLUSIVE_LEVEL = "asobibatweaks_stored_exclusive_level";

    private EnchantmentMasteryData() {}

    public static ItemEnchantments enchantments(ItemStack stack) {
        return EnchantmentHelper.getEnchantmentsForCrafting(stack);
    }

    public static String id(Holder<Enchantment> enchantment) {
        return enchantment.unwrapKey()
                .map(key -> key.location().toString())
                .orElse("unregistered");
    }

    public static int getMastery(ItemStack stack, Holder<Enchantment> enchantment) {
        if (isIndependent(enchantment)) return 0;
        CompoundTag root = custom(stack);
        return root.getCompound(MASTERY).getInt(id(enchantment));
    }

    public static void addMastery(ItemStack stack, Holder<Enchantment> enchantment, int amount) {
        if (isIndependent(enchantment)) return;
        CompoundTag root = custom(stack);
        CompoundTag values = root.getCompound(MASTERY);
        String key = id(enchantment);
        values.putInt(key, Math.max(0, values.getInt(key) + amount));
        root.put(MASTERY, values);
        setCustom(stack, root);
    }

    public static int getBranch(ItemStack stack, Holder<Enchantment> enchantment) {
        if (isIndependent(enchantment)) return -1;
        CompoundTag branches = custom(stack).getCompound(BRANCHES);
        String key = id(enchantment);
        return branches.contains(key) ? branches.getInt(key) : -1;
    }

    public static boolean hasBranch(ItemStack stack, Holder<Enchantment> enchantment) {
        if (isIndependent(enchantment)) return false;
        return custom(stack).getCompound(BRANCHES).contains(id(enchantment));
    }

    public static int cycleBranch(ItemStack stack, Holder<Enchantment> enchantment) {
        if (isIndependent(enchantment)) return -1;
        CompoundTag root = custom(stack);
        CompoundTag branches = root.getCompound(BRANCHES);
        String key = id(enchantment);
        int current = branches.contains(key) ? branches.getInt(key) : -1;
        int branchCount = "minecraft:flame".equals(key) ? 2 : 3;
        int next = (current + 1) % branchCount;
        branches.putInt(key, next);
        root.put(BRANCHES, branches);
        setCustom(stack, root);
        return next;
    }

    public static void mergeInherited(ItemStack output, ItemStack left, ItemStack right) {
        CompoundTag outRoot = custom(output);
        CompoundTag outMastery = outRoot.getCompound(MASTERY);
        CompoundTag leftMastery = custom(left).getCompound(MASTERY);
        CompoundTag rightMastery = custom(right).getCompound(MASTERY);

        Set<String> keys = new java.util.HashSet<>(leftMastery.getAllKeys());
        keys.addAll(rightMastery.getAllKeys());
        for (String key : keys) {
            int inherited = Math.max(leftMastery.getInt(key), rightMastery.getInt(key) / 2);
            if (inherited > 0) outMastery.putInt(key, inherited);
        }
        outRoot.put(MASTERY, outMastery);
        setCustom(output, outRoot);
    }

    public static void storeExclusive(ItemStack stack, String enchantmentId, int level) {
        CompoundTag root = custom(stack);
        root.putString(STORED_EXCLUSIVE, enchantmentId);
        root.putInt(STORED_EXCLUSIVE_LEVEL, Math.max(1, level));
        setCustom(stack, root);
    }

    public static String storedExclusive(ItemStack stack) {
        return custom(stack).getString(STORED_EXCLUSIVE);
    }

    public static int storedExclusiveLevel(ItemStack stack) {
        return custom(stack).getInt(STORED_EXCLUSIVE_LEVEL);
    }

    public static void clearStoredExclusive(ItemStack stack) {
        CompoundTag root = custom(stack);
        root.remove(STORED_EXCLUSIVE);
        root.remove(STORED_EXCLUSIVE_LEVEL);
        setCustom(stack, root);
    }

    private static boolean isIndependent(Holder<Enchantment> enchantment) {
        return enchantment.unwrapKey().map(NewEnchantments::isIndependent).orElse(false);
    }

    public static boolean isCurse(Holder<Enchantment> enchantment) {
        return enchantment.is(EnchantmentTags.CURSE);
    }

    private static CompoundTag custom(ItemStack stack) {
        return stack.getOrDefault(DataComponents.CUSTOM_DATA, CustomData.EMPTY).copyTag();
    }

    private static void setCustom(ItemStack stack, CompoundTag tag) {
        stack.set(DataComponents.CUSTOM_DATA, CustomData.of(tag));
    }
}
