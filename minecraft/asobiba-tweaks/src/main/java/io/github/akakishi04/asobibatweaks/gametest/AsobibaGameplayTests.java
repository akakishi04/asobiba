package io.github.akakishi04.asobibatweaks.gametest;

import io.github.akakishi04.asobibatweaks.AsobibaTweaks;
import io.github.akakishi04.asobibatweaks.feature.EnchantedWorkBlockSavedData;
import io.github.akakishi04.asobibatweaks.feature.EnchantmentMasteryData;
import io.github.akakishi04.asobibatweaks.feature.ExtendedEnchantingTargets;
import io.github.akakishi04.asobibatweaks.feature.FrostWalkerToggle;
import net.minecraft.core.BlockPos;
import net.minecraft.core.component.DataComponents;
import net.minecraft.core.registries.Registries;
import net.minecraft.gametest.framework.GameTest;
import net.minecraft.gametest.framework.GameTestHelper;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.item.component.CustomData;
import net.minecraft.world.item.enchantment.EnchantmentHelper;
import net.minecraft.world.item.enchantment.Enchantments;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.entity.AbstractFurnaceBlockEntity;
import net.neoforged.neoforge.gametest.GameTestHolder;
import net.neoforged.neoforge.gametest.PrefixGameTestTemplate;

/**
 * Executed by the REAL NeoForge GameTestServer, not by Gradle compilation.
 * All tests use a reviewed empty 3x3x3 structure and required=true (default).
 *
 * This initial suite covers identity, persistence, world placement and an
 * actual ticking block entity. Player-driven combat and inventory mutation
 * still require subsequent scenario-specific GameTests.
 */
@GameTestHolder(AsobibaTweaks.MOD_ID)
@PrefixGameTestTemplate(false)
public final class AsobibaGameplayTests {
    private static final BlockPos CENTER = new BlockPos(1, 1, 1);

    private AsobibaGameplayTests() {}

    @GameTest(template = "empty3x3x3", batch = "general_gameplay")
    public static void arrowEnchantmentEligibility(GameTestHelper helper) {
        var enchantments = helper.getLevel().registryAccess()
                .lookupOrThrow(Registries.ENCHANTMENT);
        var sharpness = enchantments.getOrThrow(Enchantments.SHARPNESS);
        var smite = enchantments.getOrThrow(Enchantments.SMITE);
        var looting = enchantments.getOrThrow(Enchantments.LOOTING);
        var fortune = enchantments.getOrThrow(Enchantments.FORTUNE);

        if (!ExtendedEnchantingTargets.isExtendedArrowTarget(new ItemStack(Items.ARROW))
                || !ExtendedEnchantingTargets.isExtendedArrowTarget(new ItemStack(Items.SPECTRAL_ARROW))
                || !ExtendedEnchantingTargets.isExtendedArrowTarget(new ItemStack(Items.TIPPED_ARROW))) {
            helper.fail("All 3 vanilla Arrow types must be valid extended targets", CENTER);
        }
        ItemStack arrow = new ItemStack(Items.ARROW);
        if (!arrow.isEnchantable()
                || !ExtendedEnchantingTargets.allowsArrowEnchantment(sharpness)
                || !ExtendedEnchantingTargets.allowsArrowEnchantment(smite)
                || !ExtendedEnchantingTargets.allowsArrowEnchantment(looting)
                || ExtendedEnchantingTargets.allowsArrowEnchantment(fortune)
                || !ExtendedEnchantingTargets.allowsArrowPair(arrow, sharpness, smite)) {
            helper.fail("Arrow whitelist/coexistence diverges from the 13 accepted effects", CENTER);
        }
        helper.succeed();
    }

    @GameTest(template = "empty3x3x3", batch = "general_gameplay")
    public static void masteryBranchPersistsOnStack(GameTestHelper helper) {
        var registry = helper.getLevel().registryAccess()
                .lookupOrThrow(Registries.ENCHANTMENT);
        var quickCharge = registry.getOrThrow(Enchantments.QUICK_CHARGE);
        ItemStack crossbow = new ItemStack(Items.CROSSBOW);
        crossbow.enchant(quickCharge, 1);

        EnchantmentMasteryData.addMastery(crossbow, quickCharge, 50);
        if (EnchantmentMasteryData.getMastery(crossbow, quickCharge) != 50
                || EnchantmentMasteryData.getBranch(crossbow, quickCharge) != -1) {
            helper.fail("Mastery 50 must be unlocked but initially unselected", CENTER);
        }

        if (EnchantmentMasteryData.cycleBranch(crossbow, quickCharge) != 0
                || EnchantmentMasteryData.cycleBranch(crossbow, quickCharge) != 1) {
            helper.fail("Mastery branch selection must cycle 0 then 1", CENTER);
        }
        ItemStack clone = crossbow.copy();
        if (EnchantmentMasteryData.getMastery(clone, quickCharge) != 50
                || EnchantmentMasteryData.getBranch(clone, quickCharge) != 1) {
            helper.fail("Mastery/branch must persist through normal ItemStack copy", CENTER);
        }
        helper.succeed();
    }

    @GameTest(template = "empty3x3x3", batch = "general_gameplay")
    public static void workBlockSavedDataRoundTrip(GameTestHelper helper) {
        var level = helper.getLevel();
        var efficiency = level.registryAccess().lookupOrThrow(Registries.ENCHANTMENT)
                .getOrThrow(Enchantments.EFFICIENCY);
        BlockPos absolute = helper.absolutePos(CENTER);
        ItemStack furnace = new ItemStack(Items.FURNACE);
        furnace.enchant(efficiency, 5);
        EnchantedWorkBlockSavedData storage = EnchantedWorkBlockSavedData.get(level);

        try {
            storage.put(absolute.asLong(), furnace);
            CompoundTag encoded = storage.save(new CompoundTag(), level.registryAccess());
            var restored = EnchantedWorkBlockSavedData.load(encoded, level.registryAccess());
            ItemStack restoredStack = restored.peek(absolute.asLong());

            if (!restoredStack.is(Items.FURNACE) || restoredStack.getCount() != 1
                    || EnchantmentHelper.getItemEnchantmentLevel(efficiency, restoredStack) != 5) {
                helper.fail("SavedData lost a placed work-block enchantment", CENTER);
            }
        } finally {
            storage.remove(absolute.asLong());
        }
        helper.succeed();
    }

    @GameTest(template = "empty3x3x3", batch = "general_gameplay")
    public static void frostWalkerToggleIsItemLocal(GameTestHelper helper) {
        ItemStack boots = new ItemStack(Items.IRON_BOOTS);
        if (!FrostWalkerToggle.enabled(boots)) {
            helper.fail("Unmarked boots must default to Frost Walker enabled", CENTER);
        }
        CustomData.update(DataComponents.CUSTOM_DATA, boots,
                tag -> tag.putBoolean("asobibatweaks_frost_walker_enabled", false));
        if (FrostWalkerToggle.enabled(boots)
                || FrostWalkerToggle.enabled(boots.copy())
                || !FrostWalkerToggle.enabled(new ItemStack(Items.IRON_BOOTS))) {
            helper.fail("Frost Walker ON/OFF must be stack-local and copy-safe", CENTER);
        }
        helper.succeed();
    }

    // This real 125-tick block-entity smelting test must not share a
    // concurrently reset default-batch fixture with unrelated construction
    // tests. Batching changes no enchantment logic or required assertion.
    @GameTest(template = "empty3x3x3", timeoutTicks = 165,
            batch = "furnace_real_smelting")
    public static void furnaceEfficiencyAffectsRealSmelting(GameTestHelper helper) {
        // On a GameTestServer without a nearby human, an otherwise perfectly
        // initialized furnace can stop receiving normal block-entity ticks.
        // Keep a genuine mock ServerPlayer standing on its physically stable
        // test block, as in the real loaded survival-world experience.
        helper.setBlock(CENTER.below(), Blocks.STONE);
        helper.setBlock(CENTER, Blocks.FURNACE);
        BlockPos absolute = helper.absolutePos(CENTER);
        ServerPlayer observer = helper.makeMockServerPlayerInLevel();
        observer.setPos(absolute.getX() + 0.5D,
                absolute.getY() + 1.0D, absolute.getZ() + 0.5D);
        var entity = helper.getLevel().getBlockEntity(absolute);
        if (!(entity instanceof AbstractFurnaceBlockEntity furnace)) {
            helper.fail("GameTest furnace block entity was not created", CENTER);
            return;
        }

        var efficiency = helper.getLevel().registryAccess()
                .lookupOrThrow(Registries.ENCHANTMENT)
                .getOrThrow(Enchantments.EFFICIENCY);
        ItemStack enchantedFurnace = new ItemStack(Items.FURNACE);
        enchantedFurnace.enchant(efficiency, 10);
        var persisted = EnchantedWorkBlockSavedData.get(helper.getLevel());
        persisted.put(absolute.asLong(), enchantedFurnace);

        furnace.setItem(0, new ItemStack(Items.IRON_ORE, 1));
        furnace.setItem(1, new ItemStack(Items.COAL, 1));
        furnace.setChanged();

        // Vanilla iron smelting takes 200 active ticks. Efficiency X aims
        // at twice that throughput, so one ingot must exist by tick 125.
        helper.runAtTickTime(125, () -> {
            try {
                if (!helper.getLevel().getBlockState(absolute).is(Blocks.FURNACE)
                        || helper.getLevel().getBlockEntity(absolute) != furnace) {
                    helper.fail("The physical furnace fixture was replaced before live smelting finished", CENTER);
                    return;
                }
                if (!furnace.getItem(2).is(Items.IRON_INGOT)
                        || !furnace.getItem(0).isEmpty()) {
                    helper.fail("Efficiency X did not finish a real recipe within 125 ticks"
                            + " with loaded observer at " + observer.blockPosition()
                            + "; actual input=" + furnace.getItem(0)
                            + ", output=" + furnace.getItem(2), CENTER);
                }
            } finally {
                persisted.remove(absolute.asLong());
            }
            helper.succeed();
        });
    }
}
