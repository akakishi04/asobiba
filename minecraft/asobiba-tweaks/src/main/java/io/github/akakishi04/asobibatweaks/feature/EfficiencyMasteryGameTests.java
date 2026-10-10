package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaks;
import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.Registries;
import net.minecraft.gametest.framework.GameTest;
import net.minecraft.gametest.framework.GameTestHelper;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.item.enchantment.Enchantments;
import net.minecraft.world.level.block.Blocks;
import net.neoforged.neoforge.gametest.GameTestHolder;
import net.neoforged.neoforge.gametest.PrefixGameTestTemplate;

@GameTestHolder(AsobibaTweaks.MOD_ID)
@PrefixGameTestTemplate(false)
public final class EfficiencyMasteryGameTests {
    private static final BlockPos MARK = new BlockPos(1, 1, 1);
    private EfficiencyMasteryGameTests() {}

    @GameTest(template = "empty3x3x3", batch = "efficiency_mastery")
    public static void hardMaterialBranchScalesOnlyQualifiedHardBlocks(GameTestHelper helper) {
        var level = helper.getLevel();
        var pos = helper.absolutePos(MARK);
        var hard = Blocks.IRON_ORE.defaultBlockState();
        var soft = Blocks.STONE.defaultBlockState();
        ItemStack beginning = tool(helper, Items.DIAMOND_PICKAXE, 0, 50);
        ItemStack complete = tool(helper, Items.DIAMOND_PICKAXE, 0, 100);
        ItemStack historical = tool(helper, Items.DIAMOND_PICKAXE, 0, 10000);
        if (!close(EfficiencyMasteryService.speed(beginning, hard, level, pos, 10.0F, 100), 10.5F)
                || !close(EfficiencyMasteryService.speed(complete, hard, level, pos, 10.0F, 100), 11.5F)
                || !close(EfficiencyMasteryService.speed(historical, hard, level, pos, 10.0F, 100), 11.5F)
                || !close(EfficiencyMasteryService.speed(complete, soft, level, pos, 10.0F, 100), 10.0F)
                || !close(EfficiencyMasteryService.speed(complete, Blocks.BEDROCK.defaultBlockState(),
                    level, pos, 10.0F, 100), 10.0F)) {
            helper.fail("Hard-material specialization ignores qualification or mastery cap", MARK);
            return;
        }
        helper.succeed();
    }

    @GameTest(template = "empty3x3x3", batch = "efficiency_mastery")
    public static void miningRhythmRequiresRealBreaksAndExpiresPerTool(GameTestHelper helper) {
        var level = helper.getLevel();
        var pos = helper.absolutePos(MARK);
        var stone = Blocks.STONE.defaultBlockState();
        ItemStack rhythm = tool(helper, Items.DIAMOND_PICKAXE, 1, 100);
        ItemStack untouched = tool(helper, Items.DIAMOND_PICKAXE, 1, 100);
        if (!close(EfficiencyMasteryService.speed(rhythm, stone, level, pos, 10.0F, 100), 10.0F)) {
            helper.fail("Merely holding a rhythm tool manufactured a streak", MARK);
            return;
        }
        for (int i = 0; i < 6; i++)
            EfficiencyMasteryService.recordBreak(rhythm, stone, level, pos, 100 + i * 5);
        ItemStack savedCopy = rhythm.copy();
        if (!close(EfficiencyMasteryService.speed(savedCopy, stone, level, pos, 10.0F, 129), 12.5F)
                || !close(EfficiencyMasteryService.speed(untouched, stone, level, pos, 10.0F, 129), 10.0F)
                || !close(EfficiencyMasteryService.speed(savedCopy, stone, level, pos, 10.0F, 156), 10.0F)) {
            helper.fail("Rhythm cap, item-local persistence, or 30-tick expiry failed", MARK);
            return;
        }
        EfficiencyMasteryService.recordBreak(savedCopy, stone, level, pos, 157);
        if (!close(EfficiencyMasteryService.speed(savedCopy, stone, level, pos, 10.0F, 157), 10.5F)) {
            helper.fail("A broken rhythm must restart at one stack", MARK);
            return;
        }
        helper.succeed();
    }

    @GameTest(template = "empty3x3x3", batch = "efficiency_mastery")
    public static void generalistRecoversOnlyPenaltyAndNeverHarvestPermission(GameTestHelper helper) {
        var level = helper.getLevel();
        var pos = helper.absolutePos(MARK);
        ItemStack generalist = tool(helper, Items.DIAMOND_PICKAXE, 2, 100);
        ItemStack novice = tool(helper, Items.DIAMOND_PICKAXE, 2, 50);
        var dirt = Blocks.DIRT.defaultBlockState();
        var stone = Blocks.STONE.defaultBlockState();
        if (!close(EfficiencyMasteryService.speed(generalist, dirt, level, pos, 1.0F, 100), 4.5F)
                || !close(EfficiencyMasteryService.speed(novice, dirt, level, pos, 1.0F, 100), 2.05F)
                || !close(EfficiencyMasteryService.speed(generalist, dirt, level, pos, 0.2F, 100), 0.9F)
                || !close(EfficiencyMasteryService.speed(generalist, stone, level, pos, 8.0F, 100), 8.0F)) {
            helper.fail("Generalist boosted suitable blocks or ignored other mining penalties", MARK);
            return;
        }
        ItemStack wrongTool = tool(helper, Items.DIAMOND_SHOVEL, 2, 100);
        var ore = Blocks.DIAMOND_ORE.defaultBlockState();
        boolean allowedBefore = wrongTool.isCorrectToolForDrops(ore);
        float speed = EfficiencyMasteryService.speed(wrongTool, ore, level, pos, 1.0F, 100);
        if (allowedBefore || wrongTool.isCorrectToolForDrops(ore) || speed <= 1.0F) {
            helper.fail("Generalist must improve unsuitable speed without granting invalid ore drops", MARK);
            return;
        }
        helper.succeed();
    }

    private static ItemStack tool(GameTestHelper helper, Item item, int branch, int mastery) {
        ItemStack tool = new ItemStack(item);
        var efficiency = helper.getLevel().registryAccess().lookupOrThrow(Registries.ENCHANTMENT)
                .getOrThrow(Enchantments.EFFICIENCY);
        tool.enchant(efficiency, 1);
        EnchantmentMasteryData.addMastery(tool, efficiency, mastery);
        for (int i = 0; i <= branch; i++) EnchantmentMasteryData.cycleBranch(tool, efficiency);
        return tool;
    }

    private static boolean close(float a, float b) { return Math.abs(a - b) < 0.001F; }
}
