package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaks;
import net.minecraft.core.BlockPos;
import net.minecraft.gametest.framework.GameTest;
import net.minecraft.gametest.framework.GameTestHelper;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.LiquidBlock;
import net.minecraft.world.level.block.state.properties.BlockStateProperties;
import net.neoforged.neoforge.gametest.GameTestHolder;
import net.neoforged.neoforge.gametest.PrefixGameTestTemplate;

@GameTestHolder(AsobibaTweaks.MOD_ID)
@PrefixGameTestTemplate(false)
public final class FrostWalkerExtensionGameTests {
    private static final BlockPos MARK = new BlockPos(4, 1, 4);
    private FrostWalkerExtensionGameTests() {}

    @GameTest(template = "empty16x6x9", batch = "frost_extension")
    public static void narrowPathPreservesWaterloggedPlayerBlocksAndFlowingWater(GameTestHelper helper) {
        var level = helper.getLevel();
        BlockPos slab = helper.absolutePos(MARK);
        BlockPos flowing = slab.offset(2, 0, 0);
        var waterlogged = Blocks.OAK_SLAB.defaultBlockState().setValue(BlockStateProperties.WATERLOGGED, true);
        var flowingWater = Blocks.WATER.defaultBlockState().setValue(LiquidBlock.LEVEL, 3);
        level.setBlockAndUpdate(slab, waterlogged);
        level.setBlockAndUpdate(flowing, flowingWater);
        if (FrostWalkerMasteryEvents.extendSourceWater(level, slab)
                || FrostWalkerMasteryEvents.extendSourceWater(level, flowing)
                || !level.getBlockState(slab).equals(waterlogged)
                || !level.getBlockState(flowing).equals(flowingWater)) {
            helper.fail("Narrow Path replaced a player-owned waterlogged block or non-source water", MARK);
            return;
        }
        helper.succeed();
    }

    @GameTest(template = "empty16x6x9", batch = "frost_extension")
    public static void narrowPathSchedulesMeltAndNeverLoadsDistantTerrain(GameTestHelper helper) {
        var level = helper.getLevel();
        BlockPos water = helper.absolutePos(MARK);
        level.setBlockAndUpdate(water, Blocks.WATER.defaultBlockState());
        if (!FrostWalkerMasteryEvents.extendSourceWater(level, water)
                || !level.getBlockState(water).is(Blocks.FROSTED_ICE)
                || !level.getBlockTicks().hasScheduledTick(water, Blocks.FROSTED_ICE)) {
            helper.fail("New directional ice must receive ordinary frost melt scheduling", MARK);
            return;
        }
        BlockPos remote = water.offset(1_000_000, 0, 1_000_000);
        if (level.hasChunkAt(remote)) {
            helper.fail("Distant no-force-load test requires an unobserved chunk", MARK);
            return;
        }
        if (FrostWalkerMasteryEvents.extendSourceWater(level, remote) || level.hasChunkAt(remote)) {
            helper.fail("Narrow Path inspected/generated unknown terrain", MARK);
            return;
        }
        helper.succeed();
    }
}
