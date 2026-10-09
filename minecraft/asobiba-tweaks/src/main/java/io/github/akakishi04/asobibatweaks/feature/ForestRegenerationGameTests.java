package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaks;
import net.minecraft.core.BlockPos;
import net.minecraft.gametest.framework.GameTest;
import net.minecraft.gametest.framework.GameTestHelper;
import net.minecraft.world.level.block.Blocks;
import net.neoforged.neoforge.gametest.GameTestHolder;
import net.neoforged.neoforge.gametest.PrefixGameTestTemplate;

/** In-world forestry checks for protected player surfaces outside village records. */
@GameTestHolder(AsobibaTweaks.MOD_ID)
@PrefixGameTestTemplate(false)
public final class ForestRegenerationGameTests {
    private static final BlockPos CENTER = new BlockPos(8, 2, 4);
    private ForestRegenerationGameTests() {}

    @GameTest(template = "empty16x6x9", timeoutTicks = 35)
    public static void unmodifiedClearingCanRegrowButFarmCannot(GameTestHelper helper) {
        prepare(helper);
        helper.runAtTickTime(4, () -> {
            var level = helper.getLevel();
            BlockPos plant = helper.absolutePos(CENTER);
            // Reset the candidate at the exact assertion tick: another
            // GameTest or ambient world activity can mutate the physical
            // GameTest fixture after its initial placement.
            helper.setBlock(CENTER.below(), Blocks.DIRT);
            helper.setBlock(CENTER, Blocks.AIR);
            var air = level.getBlockState(plant);
            var dirt = level.getBlockState(plant.below());
            if (!air.isAir() || !dirt.is(Blocks.DIRT)
                    || ForestRegenerationEvents.isMaintainedSurface(air)
                    || ForestRegenerationEvents.isMaintainedSurface(dirt)) {
                helper.fail("Natural candidate precondition failed: plant=" + air
                        + ", ground=" + dirt, CENTER);
                return;
            }
            helper.setBlock(CENTER.offset(1, -1, 0), Blocks.FARMLAND);
            if (!ForestRegenerationEvents.isMaintainedSurface(
                        level.getBlockState(helper.absolutePos(CENTER.offset(1, -1, 0))))
                    || ForestRegenerationEvents.safeRegrowthSite(level, plant)) {
                helper.fail("Nearby farm ground must veto autonomous saplings", CENTER);
                return;
            }
            helper.succeed();
        });
    }

    @GameTest(template = "empty16x6x9", timeoutTicks = 35)
    public static void roadAndStorageNearSaplingAreProtected(GameTestHelper helper) {
        prepare(helper);
        helper.runAtTickTime(9, () -> {
            var level = helper.getLevel();
            BlockPos plant = helper.absolutePos(CENTER);
            helper.setBlock(CENTER.offset(2, -1, 0), Blocks.COBBLESTONE);
            if (!ForestRegenerationEvents.isMaintainedSurface(
                        level.getBlockState(helper.absolutePos(CENTER.offset(2, -1, 0))))
                    || ForestRegenerationEvents.safeRegrowthSite(level, plant)) {
                helper.fail("Player cobble footpath must veto sapling", CENTER);
                return;
            }
            helper.setBlock(CENTER.offset(2, -1, 0), Blocks.DIRT);
            helper.setBlock(CENTER.offset(-1, 0, 1), Blocks.BARREL);
            if (!ForestRegenerationEvents.isMaintainedSurface(
                        level.getBlockState(helper.absolutePos(CENTER.offset(-1, 0, 1))))
                    || ForestRegenerationEvents.safeRegrowthSite(level, plant)) {
                helper.fail("Recognizable player storage must veto sapling", CENTER);
                return;
            }
            helper.succeed();
        });
    }

    @GameTest(template = "empty16x6x9", timeoutTicks = 35)
    public static void nonVanillaLikeBlockEntitiesProtectPlayerLand(GameTestHelper helper) {
        prepare(helper);
        helper.runAtTickTime(12, () -> {
            var level = helper.getLevel();
            BlockPos local = CENTER.offset(1, 0, 0);
            BlockPos actual = helper.absolutePos(local);
            // Hopper is a vanilla BlockEntity not included in the old
            // hardcoded protected-surface list, modeling the same conservative
            // discovery mechanism used for modded storage and machines.
            helper.setBlock(local, Blocks.HOPPER);
            if (level.getBlockEntity(actual) == null
                    || ForestRegenerationEvents.isMaintainedSurface(
                            level.getBlockState(actual))
                    || !ForestRegenerationEvents.isProtectedSurface(level, actual)
                    || ForestRegenerationEvents.safeRegrowthSite(
                            level, helper.absolutePos(CENTER))) {
                helper.fail("A physical block entity must protect natural land even "
                        + "without explicit vanilla/modded block allowlists", CENTER);
                return;
            }
            helper.succeed();
        });
    }

    private static void prepare(GameTestHelper helper) {
        for (int x = 5; x <= 11; x++) {
            for (int z = 1; z <= 7; z++) {
                helper.setBlock(new BlockPos(x, 1, z), Blocks.DIRT);
                for (int y = 2; y <= 4; y++)
                    helper.setBlock(new BlockPos(x, y, z), Blocks.AIR);
            }
        }
    }
}
