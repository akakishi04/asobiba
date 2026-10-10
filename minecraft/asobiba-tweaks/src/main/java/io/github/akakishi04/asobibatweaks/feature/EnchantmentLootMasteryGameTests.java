package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaks;
import java.util.Optional;
import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.Registries;
import net.minecraft.gametest.framework.GameTest;
import net.minecraft.gametest.framework.GameTestHelper;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.item.enchantment.Enchantments;
import net.minecraft.world.item.enchantment.LevelBasedValue;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.storage.loot.LootContext;
import net.minecraft.world.level.storage.loot.LootParams;
import net.minecraft.world.level.storage.loot.functions.ApplyBonusCount;
import net.minecraft.world.level.storage.loot.functions.EnchantedCountIncreaseFunction;
import net.minecraft.world.level.storage.loot.parameters.LootContextParams;
import net.minecraft.world.level.storage.loot.parameters.LootContextParamSets;
import net.minecraft.world.level.storage.loot.predicates.LootItemRandomChanceWithEnchantedBonusCondition;
import net.minecraft.world.level.storage.loot.providers.number.ConstantValue;
import net.minecraft.world.phys.Vec3;
import net.neoforged.neoforge.gametest.GameTestHolder;
import net.neoforged.neoforge.gametest.PrefixGameTestTemplate;

/** Executes vanilla loot functions/conditions with deterministic real contexts. */
@GameTestHolder(AsobibaTweaks.MOD_ID)
@PrefixGameTestTemplate(false)
public final class EnchantmentLootMasteryGameTests {
    private static final BlockPos MARK = new BlockPos(1, 1, 1);
    private EnchantmentLootMasteryGameTests() {}

    @GameTest(template = "empty3x3x3", batch = "enchantment_loot")
    public static void bigGameChangesRealRareRollAndOnlyActualCommonBonus(GameTestHelper helper) {
        var player = helper.makeMockServerPlayerInLevel();
        var looting = helper.getLevel().registryAccess().lookupOrThrow(Registries.ENCHANTMENT)
                .getOrThrow(Enchantments.LOOTING);
        ItemStack weapon = new ItemStack(Items.DIAMOND_SWORD);
        weapon.enchant(looting, 1);
        player.setItemInHand(InteractionHand.MAIN_HAND, weapon);
        var condition = new LootItemRandomChanceWithEnchantedBonusCondition(
                0.6F, LevelBasedValue.constant(0.6F), looting);
        // Java/vanilla seed42 begins with float0.7275: ordinary60% fails,
        // completed Big Game's relative30% increase (78%) succeeds.
        if (condition.test(entityContext(helper, player, 42))) {
            helper.fail("Seeded ordinary rare-drop control unexpectedly succeeded", MARK);
            return;
        }
        EnchantmentMasteryData.addMastery(weapon, looting, 100);
        for (int i = 0; i < 3; i++) EnchantmentMasteryData.cycleBranch(weapon, looting);
        if (!condition.test(entityContext(helper, player, 42))) {
            helper.fail("Big Game did not improve the actual vanilla rare roll", MARK);
            return;
        }
        var increase = EnchantedCountIncreaseFunction.lootingMultiplier(
                helper.getLevel().registryAccess(), ConstantValue.exactly(4)).build();
        ItemStack result = increase.apply(new ItemStack(Items.ROTTEN_FLESH, 5), entityContext(helper, player, 42));
        if (result.getCount() != 8 || weapon.getCount() != 1) {
            helper.fail("Big Game must keep5 ordinary items and75% of the real4-item Looting bonus", MARK);
            return;
        }
        helper.succeed();
    }

    @GameTest(template = "empty3x3x3", batch = "enchantment_loot")
    public static void fortuneVarianceUsesEntireRealBonusAndPreservesCropBaseline(GameTestHelper helper) {
        var fortune = helper.getLevel().registryAccess().lookupOrThrow(Registries.ENCHANTMENT)
                .getOrThrow(Enchantments.FORTUNE);
        ItemStack tool = new ItemStack(Items.DIAMOND_PICKAXE);
        tool.enchant(fortune, 3);
        EnchantmentMasteryData.addMastery(tool, fortune, 100);
        for (int i = 0; i < 3; i++) EnchantmentMasteryData.cycleBranch(tool, fortune);
        var crop = ApplyBonusCount.addBonusBinomialDistributionCount(fortune, 1.0F, 3).build();
        boolean lower = false;
        boolean upper = false;
        for (long seed = 1; seed <= 128; seed++) {
            ItemStack result = crop.apply(new ItemStack(Items.WHEAT_SEEDS, 1),
                    blockContext(helper, tool, seed, Blocks.WHEAT.defaultBlockState()));
            // Input1 + three non-Fortune trials =4 unavoidable base items.
            // Three real Fortune trials add3: ordinary7, volatile4 or10.
            int count = result.getCount();
            if (count != 4 && count != 7 && count != 10) {
                helper.fail("Fortune variance touched crop baseline or only changed an arbitrary single item: " + count, MARK);
                return;
            }
            lower |= count == 4;
            upper |= count == 10;
        }
        if (!lower || !upper) {
            helper.fail("Actual crop loot function never produced both accepted volatile outcomes", MARK);
            return;
        }
        helper.succeed();
    }

    @GameTest(template = "empty3x3x3", batch = "enchantment_loot")
    public static void oreSpecialistNeverBonusesRawBlocksOrNoFortuneRoll(GameTestHelper helper) {
        var fortune = helper.getLevel().registryAccess().lookupOrThrow(Registries.ENCHANTMENT)
                .getOrThrow(Enchantments.FORTUNE);
        ItemStack tool = new ItemStack(Items.DIAMOND_PICKAXE);
        tool.enchant(fortune, 3);
        EnchantmentMasteryData.addMastery(tool, fortune, 100);
        EnchantmentMasteryData.cycleBranch(tool, fortune);
        var zeroBonus = ApplyBonusCount.addUniformBonusCount(fortune, 0).build();
        for (long seed = 1; seed <= 128; seed++) {
            ItemStack result = zeroBonus.apply(new ItemStack(Items.RAW_IRON, 1),
                    blockContext(helper, tool, seed, Blocks.IRON_ORE.defaultBlockState()));
            if (result.getCount() != 1) {
                helper.fail("A Fortune roll with no actual bonus created free Ore Specialist stock", MARK);
                return;
            }
            var rawContext = blockContext(helper, tool, seed, Blocks.RAW_IRON_BLOCK.defaultBlockState());
            if (FortuneMasteryService.adjust(1, 3, rawContext) != 3) {
                helper.fail("Raw storage blocks must not qualify as Fortune ores", MARK);
                return;
            }
        }
        helper.succeed();
    }

    private static LootContext entityContext(GameTestHelper helper, ServerPlayer player, long seed) {
        var params = new LootParams.Builder(helper.getLevel())
                .withParameter(LootContextParams.THIS_ENTITY, player)
                .withParameter(LootContextParams.ORIGIN, player.position())
                .withParameter(LootContextParams.DAMAGE_SOURCE, player.damageSources().playerAttack(player))
                .withParameter(LootContextParams.ATTACKING_ENTITY, player)
                .withParameter(LootContextParams.DIRECT_ATTACKING_ENTITY, player)
                .create(LootContextParamSets.ENTITY);
        return new LootContext.Builder(params).withOptionalRandomSeed(seed).create(Optional.empty());
    }

    private static LootContext blockContext(GameTestHelper helper, ItemStack tool, long seed,
            net.minecraft.world.level.block.state.BlockState state) {
        var params = new LootParams.Builder(helper.getLevel())
                .withParameter(LootContextParams.ORIGIN, Vec3.ZERO)
                .withParameter(LootContextParams.BLOCK_STATE, state)
                .withParameter(LootContextParams.TOOL, tool)
                .create(LootContextParamSets.BLOCK);
        return new LootContext.Builder(params).withOptionalRandomSeed(seed).create(Optional.empty());
    }
}
