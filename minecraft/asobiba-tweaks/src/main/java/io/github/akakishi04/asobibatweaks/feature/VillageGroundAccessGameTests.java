package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaks;
import net.minecraft.core.BlockPos;
import net.minecraft.gametest.framework.GameTest;
import net.minecraft.gametest.framework.GameTestHelper;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.block.Blocks;
import net.neoforged.neoforge.gametest.GameTestHolder;
import net.neoforged.neoforge.gametest.PrefixGameTestTemplate;

@GameTestHolder(AsobibaTweaks.MOD_ID)
@PrefixGameTestTemplate(false)
public final class VillageGroundAccessGameTests {
    private static final BlockPos MARK = new BlockPos(5, 1, 2);
    private VillageGroundAccessGameTests() {}

    @GameTest(template = "empty16x6x9", batch = "village_ground_access", timeoutTicks = 100)
    public static void blockedRealHomeEntranceRemovesAndRestoresCapacity(GameTestHelper helper) {
        var home = setup(helper, "house_5x5", "residential");
        BlockPos door = home.min().offset(2, 1, 0);
        helper.runAtTickTime(4, () -> revalidate(helper, home));
        helper.runAtTickTime(8, () -> {
            if (!"valid".equals(home.validationState()) || home.validatedCapacity() != 1)
                throw new IllegalStateException("Fixture genuine open one-bed house was not usable");
            helper.getLevel().setBlock(door, Blocks.OBSIDIAN.defaultBlockState(), 3);
            revalidate(helper, home);
        });
        helper.runAtTickTime(12, () -> {
            if (!"invalid".equals(home.validationState()) || home.validatedCapacity() != 0) {
                helper.fail("Sealed village home still counted an unreachable real Bed", MARK);
                return;
            }
            if (!helper.getLevel().getBlockState(door).is(Blocks.OBSIDIAN)) {
                helper.fail("Validation overwrote a player obstruction", MARK);
                return;
            }
            helper.getLevel().setBlock(door, Blocks.AIR.defaultBlockState(), 3);
            revalidate(helper, home);
        });
        helper.runAtTickTime(16, () -> {
            if (!"valid".equals(home.validationState()) || home.validatedCapacity() != 1) {
                helper.fail("Reopened original home did not regain its same usable capacity", MARK);
                return;
            }
            helper.succeed();
        });
    }

    @GameTest(template = "empty16x14x9", batch = "village_ground_access", timeoutTicks = 100)
    public static void craftHallCountsOnlyEntranceReachableInteractionFaces(GameTestHelper helper) {
        var home = setup(helper, VillageCraftHallPlanner.TEMPLATE, "workshop");
        helper.runAtTickTime(24, () -> revalidate(helper, home));
        helper.runAtTickTime(28, () -> {
            if (!"valid".equals(home.validationState()) || home.validatedCapacity() != 2)
                throw new IllegalStateException("Fixture two-station craft hall did not validate");
            // Seal all three interior faces of the left Smithing Table.
            for (BlockPos relative : new BlockPos[]{new BlockPos(1, 1, 1),
                    new BlockPos(2, 1, 2), new BlockPos(1, 1, 3)}) {
                helper.getLevel().setBlock(home.min().offset(relative), Blocks.OBSIDIAN.defaultBlockState(), 3);
            }
            revalidate(helper, home);
        });
        helper.runAtTickTime(32, () -> {
            if (!"valid".equals(home.validationState()) || home.validatedCapacity() != 1
                    || !helper.getLevel().getBlockState(home.min().offset(1, 1, 2)).is(Blocks.SMITHING_TABLE)) {
                helper.fail("Intact but isolated Smithing Table must not contribute a phantom job slot", MARK);
                return;
            }
            helper.succeed();
        });
    }

    @GameTest(template = "empty16x6x9", batch = "village_ground_access", timeoutTicks = 100)
    public static void dangerousOrUnsupportedEntryCannotValidateWarehouse(GameTestHelper helper) {
        var home = setup(helper, "storage_5x5", "storage");
        helper.runAtTickTime(40, () -> revalidate(helper, home));
        helper.runAtTickTime(44, () -> {
            if (!"valid".equals(home.validationState()))
                throw new IllegalStateException("Fixture genuine warehouse did not validate");
            helper.getLevel().setBlock(home.min().offset(2, 0, 0), Blocks.MAGMA_BLOCK.defaultBlockState(), 3);
            revalidate(helper, home);
        });
        helper.runAtTickTime(48, () -> {
            if (!"invalid".equals(home.validationState())) {
                helper.fail("Unavoidable damaging entry floor retained usable warehouse status", MARK);
                return;
            }
            helper.getLevel().setBlock(home.min().offset(2, 0, 0), Blocks.AIR.defaultBlockState(), 3);
            revalidate(helper, home);
        });
        helper.runAtTickTime(52, () -> {
            if (!"invalid".equals(home.validationState())) {
                helper.fail("Unsupported entrance was treated as a safe loading path", MARK);
                return;
            }
            helper.succeed();
        });
    }

    @GameTest(template = "empty16x14x9", batch = "village_ground_access", timeoutTicks = 120)
    public static void v2EastEntryAndFullStairHeadroomControlRealUpperCapacity(GameTestHelper helper) {
        var home = setup(helper, "house_2story_5x5", "residential");
        BlockPos eastDoor = home.min().offset(4, 1, 1);
        BlockPos secondTreadHead = home.min().offset(2, 4, 1);
        helper.runAtTickTime(60, () -> revalidate(helper, home));
        helper.runAtTickTime(64, () -> {
            if (!"valid".equals(home.validationState()) || home.validatedCapacity() != 3) {
                helper.fail("V2 house needs one reachable ground and two supported upper Beds", MARK);
                return;
            }
            helper.getLevel().setBlock(eastDoor, Blocks.OBSIDIAN.defaultBlockState(), 3);
            revalidate(helper, home);
        });
        helper.runAtTickTime(68, () -> {
            if (!"invalid".equals(home.validationState()) || home.validatedCapacity() != 0) {
                helper.fail("Blocked east entrance must not be bypassed through low front stair headroom", MARK);
                return;
            }
            helper.getLevel().setBlock(eastDoor, Blocks.AIR.defaultBlockState(), 3);
            helper.getLevel().setBlock(secondTreadHead, Blocks.GLASS.defaultBlockState(), 3);
            revalidate(helper, home);
        });
        helper.runAtTickTime(72, () -> {
            if (!"valid".equals(home.validationState()) || home.validatedCapacity() != 1
                    || !helper.getLevel().getBlockState(secondTreadHead).is(Blocks.GLASS)) {
                helper.fail("Blocked second-tread headroom must exclude upper Beds while preserving usable ground housing", MARK);
                return;
            }
            helper.succeed();
        });
    }

    private static VillageSavedData.BuildingRecord setup(GameTestHelper helper, String template, String classification) {
        var level = helper.getLevel();
        BlockPos base = helper.absolutePos(MARK);
        int height = "house_2story_5x5".equals(template) ? 8
                : VillageCraftHallPlanner.TEMPLATE.equals(template) ? 6 : 4;
        for (int x = 0; x < 5; x++) for (int z = 0; z < 5; z++) for (int y = 1; y <= height; y++)
            level.setBlock(base.offset(x, y, z), Blocks.AIR.defaultBlockState(), 2);
        var data = VillageSavedData.get(level);
        var village = data.createVillage(base, level.getGameTime());
        var source = data.createProject(village.id(), "building", 70, base);
        source.setTemplateId(template); source.setPhase("complete");
        source.setParameter("plank", "oak"); source.setParameter("lead_skill", "100"); source.setVariantSeed(25);
        source.setParameter("circulation_version", "2");
        for (var step : VillageSimulationEvents.projectPlan(source)) level.setBlock(step.pos(), step.state(), 2);
        var home = data.createBuilding(village.id(), base, base.offset(4, height, 4), true);
        home.setTemplateId(template); home.setClassification(classification); home.setValidationState("unknown");
        data.touch();
        return home;
    }

    private static void revalidate(GameTestHelper helper, VillageSavedData.BuildingRecord home) {
        VillageBuildingService.revalidateChunk(helper.getLevel(), new ChunkPos(home.min()));
    }
}
