package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaks;
import java.util.List;
import net.minecraft.core.BlockPos;
import net.minecraft.gametest.framework.GameTest;
import net.minecraft.gametest.framework.GameTestHelper;
import net.minecraft.world.level.block.Blocks;
import net.neoforged.neoforge.gametest.GameTestHolder;
import net.neoforged.neoforge.gametest.PrefixGameTestTemplate;

/**
 * Real server-world water routing tests. A returned waterway must connect
 * real source-water cells, never jump over missing or solid intermediate water.
 */
@GameTestHolder(AsobibaTweaks.MOD_ID)
@PrefixGameTestTemplate(false)
public final class VillageRiverNavigationGameTests {
    private static final BlockPos START = new BlockPos(0, 1, 1);
    private static final BlockPos END = new BlockPos(2, 1, 1);

    private VillageRiverNavigationGameTests() {}

    @GameTest(template = "empty3x3x3", batch = "river_navigation")
    public static void connectedSourceWaterIsNavigable(GameTestHelper helper) {
        for (int x = 0; x < 3; x++) {
            for (int z = 0; z < 3; z++) {
                helper.setBlock(new BlockPos(x, 1, z), Blocks.WATER);
            }
        }
        var level = helper.getLevel();
        BlockPos a = helper.absolutePos(START);
        BlockPos b = helper.absolutePos(END);
        List<BlockPos> route = VillageRiverNavigationService.findLoadedPath(level, a, b);
        if (route.size() != 2 || !route.getFirst().equals(a)
                || !route.getLast().equals(b)) {
            helper.fail("Contiguous loaded two-wide source water must produce a direct route",
                    START);
            return;
        }
        helper.succeed();
    }

    @GameTest(template = "empty3x3x3", batch = "river_navigation")
    public static void solidBarrierRequiresRealWaterDetour(GameTestHelper helper) {
        for (int x = 0; x < 3; x++) {
            for (int z = 0; z < 3; z++) {
                helper.setBlock(new BlockPos(x, 1, z), Blocks.WATER);
            }
        }
        for (int z = 0; z < 3; z++) {
            helper.setBlock(new BlockPos(1, 1, z), Blocks.STONE);
        }
        // The real GameTest world can contain other loaded water outside this
        // 3x3 structure (including neighboring tests). Such a real detour is
        // legal; the required invariant is that no reported segment crosses
        // an obstructed/unloaded/non-water cell.
        var level = helper.getLevel();
        var route = VillageRiverNavigationService.findLoadedPath(
                level, helper.absolutePos(START), helper.absolutePos(END));
        for (int i = 1; i < route.size(); i++) {
            BlockPos from = route.get(i - 1);
            BlockPos to = route.get(i);
            int dx = Integer.signum(to.getX() - from.getX());
            int dz = Integer.signum(to.getZ() - from.getZ());
            if (from.getY() != to.getY() || (dx != 0 && dz != 0)) {
                helper.fail("Waterway crossed diagonally or changed elevation", START);
                return;
            }
            int length = Math.abs(to.getX() - from.getX())
                    + Math.abs(to.getZ() - from.getZ());
            for (int step = 0; step <= length; step++) {
                BlockPos pos = from.offset(dx * step, 0, dz * step);
                if (!VillageRiverNavigationService.navigable(level, pos)) {
                    helper.fail("Waterway jumped through a solid or unnavigable block", START);
                    return;
                }
            }
        }
        helper.succeed();
    }
}
