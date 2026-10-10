package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaks;
import java.util.List;
import net.minecraft.core.BlockPos;
import net.minecraft.gametest.framework.GameTest;
import net.minecraft.gametest.framework.GameTestHelper;
import net.minecraft.world.level.block.Blocks;
import net.neoforged.neoforge.gametest.GameTestHolder;
import net.neoforged.neoforge.gametest.PrefixGameTestTemplate;

/** Road/bridge selection must fail closed if geography is missing or unsafe. */
@GameTestHolder(AsobibaTweaks.MOD_ID)
@PrefixGameTestTemplate(false)
public final class VillageRoadSafetyGameTests {
    private VillageRoadSafetyGameTests() {}

    @GameTest(skyAccess = true, template = "empty3x3x3", batch = "village_road_safety")
    public static void unloadedRoadCorridorNeverBecomesStraightFallback(
            GameTestHelper helper) {
        BlockPos from = helper.absolutePos(new BlockPos(1, 1, 1));
        BlockPos far = from.offset(512, 0, 0);
        var level = helper.getLevel();
        if (VillageSimulationScheduler.isChunkLoaded(level, far)) {
            // It is a test error to presume this distant chunk is unknown.
            helper.fail("Unloaded route test unexpectedly has far chunk loaded",
                    new BlockPos(1, 1, 1));
            return;
        }
        List<BlockPos> route = VillageRoadPlanner.planLoaded(level, from, far);
        if (!route.isEmpty()
                || VillageSimulationScheduler.isChunkLoaded(level, far)) {
            helper.fail("Missing terrain generated a straight phantom route or loaded a chunk",
                    new BlockPos(1, 1, 1));
            return;
        }
        helper.succeed();
    }

    @GameTest(skyAccess = true, template = "empty16x6x9", batch = "village_road_safety")
    public static void materialDetoursAndProtectedBankCanVetoBridge(GameTestHelper helper) {
        for (int x = 0; x < 16; x++) for (int z = 0; z < 9; z++) {
            helper.setBlock(new BlockPos(x, 0, z), Blocks.STONE);
            helper.setBlock(new BlockPos(x, 1, z), Blocks.STONE);
            for (int y = 2; y <= 5; y++)
                helper.setBlock(new BlockPos(x, y, z), Blocks.AIR);
        }
        for (int x = 5; x <= 10; x++) for (int z = 2; z <= 5; z++)
            helper.setBlock(new BlockPos(x, 1, z), Blocks.WATER);

        BlockPos from = helper.absolutePos(new BlockPos(2, 1, 3));
        BlockPos to = helper.absolutePos(new BlockPos(13, 1, 3));
        var level = helper.getLevel();
        var bridge = VillageBridgeService.findLoadedCrossing(
                level, List.of(from, to), 2);
        if (bridge == null
                || !VillageBridgeService.preferableToDetour(11, 24)
                || VillageBridgeService.preferableToDetour(11, 14)
                || !VillageBridgeService.directShortcutSafe(
                        level, from, to, bridge)) {
            helper.fail("Bridge and detour costs or verified direct approach were incorrect",
                    new BlockPos(7, 3, 3));
            return;
        }

        // Do not accept an otherwise cheap crossing if a protected player
        // block occupies the secondary walking lane beyond the bridge.
        helper.setBlock(new BlockPos(2, 1, 4), Blocks.OBSIDIAN);
        if (VillageBridgeService.directShortcutSafe(level, from, to, bridge)) {
            helper.fail("Short bridge shortcut crossed a player-modified shore lane",
                    new BlockPos(2, 1, 4));
            return;
        }
        helper.succeed();
    }
}
