package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaks;
import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.Registries;
import net.minecraft.gametest.framework.GameTest;
import net.minecraft.gametest.framework.GameTestHelper;
import net.minecraft.tags.EnchantmentTags;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.item.enchantment.Enchantments;
import net.neoforged.neoforge.gametest.GameTestHolder;
import net.neoforged.neoforge.gametest.PrefixGameTestTemplate;

/** Exercises real datapack holders, acquisition tags, and independent mastery isolation. */
@GameTestHolder(AsobibaTweaks.MOD_ID)
@PrefixGameTestTemplate(false)
public final class IndependentEnchantmentGameTests {
    private IndependentEnchantmentGameTests() {}

    @GameTest(template = "empty3x3x3", batch = "independent_enchantments")
    public static void registeredSingleLevelEnchantmentsHaveNormalAcquisition(GameTestHelper helper) {
        var registry = helper.getLevel().registryAccess().lookupOrThrow(Registries.ENCHANTMENT);
        for (var key : java.util.List.of(NewEnchantments.ROOTED, NewEnchantments.OMINOUS,
                NewEnchantments.AFTERIMAGE, NewEnchantments.NOD)) {
            var holder = registry.getOrThrow(key);
            if (holder.value().getMaxLevel() != 1 || !holder.is(EnchantmentTags.IN_ENCHANTING_TABLE)
                    || !holder.is(EnchantmentTags.TRADEABLE) || !holder.is(EnchantmentTags.ON_RANDOM_LOOT)
                    || holder.is(EnchantmentTags.CURSE)) {
                helper.fail("Independent enchant must be single-level, ordinarily obtainable and not a curse: " + key,
                        BlockPos.ZERO);
                return;
            }
        }
        helper.succeed();
    }

    @GameTest(template = "empty3x3x3", batch = "independent_enchantments")
    public static void independentEnchantmentsDoNotInventMasteryBranches(GameTestHelper helper) {
        var registry = helper.getLevel().registryAccess().lookupOrThrow(Registries.ENCHANTMENT);
        for (var key : java.util.List.of(NewEnchantments.ROOTED, NewEnchantments.OMINOUS,
                NewEnchantments.AFTERIMAGE, NewEnchantments.NOD)) {
            var holder = registry.getOrThrow(key);
            ItemStack stack = new ItemStack(Items.DIAMOND_HOE);
            stack.enchant(holder, 1);
            EnchantmentMasteryData.addMastery(stack, holder, 100);
            if (EnchantmentMasteryData.getMastery(stack, holder) != 0
                    || EnchantmentMasteryData.cycleBranch(stack, holder) != -1
                    || EnchantmentMasteryData.hasBranch(stack, holder)) {
                helper.fail("Independent enchant gained an undefined mastery branch", BlockPos.ZERO);
                return;
            }
        }
        var vanilla = registry.getOrThrow(Enchantments.EFFICIENCY);
        var tool = new ItemStack(Items.DIAMOND_HOE);
        tool.enchant(vanilla, 1);
        EnchantmentMasteryData.addMastery(tool, vanilla, 100);
        if (EnchantmentMasteryData.getMastery(tool, vanilla) != 100
                || EnchantmentMasteryData.cycleBranch(tool, vanilla) != 0) {
            helper.fail("Independent isolation changed an existing vanilla mastery", BlockPos.ZERO);
            return;
        }
        helper.succeed();
    }

    @GameTest(template = "empty3x3x3", batch = "independent_enchantments")
    public static void independentSupportedEquipmentDomainsStaySeparate(GameTestHelper helper) {
        var registry = helper.getLevel().registryAccess().lookupOrThrow(Registries.ENCHANTMENT);
        var rooted = registry.getOrThrow(NewEnchantments.ROOTED).value();
        var ominous = registry.getOrThrow(NewEnchantments.OMINOUS).value();
        var afterimage = registry.getOrThrow(NewEnchantments.AFTERIMAGE).value();
        var nod = registry.getOrThrow(NewEnchantments.NOD).value();
        if (!rooted.isSupportedItem(new ItemStack(Items.DIAMOND_HOE))
                || rooted.isSupportedItem(new ItemStack(Items.DIAMOND_PICKAXE))
                || !ominous.isSupportedItem(new ItemStack(Items.DIAMOND_BOOTS))
                || ominous.isSupportedItem(new ItemStack(Items.DIAMOND_SWORD))
                || !afterimage.isSupportedItem(new ItemStack(Items.DIAMOND_CHESTPLATE))
                || afterimage.isSupportedItem(new ItemStack(Items.DIAMOND_HELMET))
                || !nod.isSupportedItem(new ItemStack(Items.DIAMOND_HELMET))
                || nod.isSupportedItem(new ItemStack(Items.DIAMOND_CHESTPLATE))) {
            helper.fail("Independent enchant equipment domain is wrong", BlockPos.ZERO);
            return;
        }
        helper.succeed();
    }
}
