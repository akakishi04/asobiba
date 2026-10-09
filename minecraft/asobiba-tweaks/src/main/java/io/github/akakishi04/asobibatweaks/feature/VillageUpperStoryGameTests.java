package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaks;
import java.util.List;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.gametest.framework.GameTest;
import net.minecraft.gametest.framework.GameTestHelper;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.HorizontalDirectionalBlock;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.state.properties.BedPart;
import net.minecraft.world.level.block.BedBlock;
import net.neoforged.neoforge.gametest.GameTestHolder;
import net.neoforged.neoforge.gametest.PrefixGameTestTemplate;

/** V89 physically navigable stairs and non-overlapping bed/floor templates. */
@GameTestHolder(AsobibaTweaks.MOD_ID)
@PrefixGameTestTemplate(false)
public final class VillageUpperStoryGameTests {
    private static final BlockPos MARK = new BlockPos(8, 3, 4);
    private VillageUpperStoryGameTests() {}

    @GameTest(template = "empty16x6x9", timeoutTicks = 45)
    public static void upperFloorRequiresPhysicalOrientedStairsAndSafeLanding(
            GameTestHelper helper) {
        // Place the whole 4-tread flight within the real GameTest fixture;
        // base is one below local zero so upper headroom remains in its bounds.
        BlockPos base = new BlockPos(5, -1, 2);
        BlockState east = Blocks.OAK_STAIRS.defaultBlockState()
                .setValue(HorizontalDirectionalBlock.FACING, Direction.EAST);
        BlockState south = Blocks.OAK_STAIRS.defaultBlockState()
                .setValue(HorizontalDirectionalBlock.FACING, Direction.SOUTH);
        for (int x = 1; x <= 3; x++) {
            BlockPos step = base.offset(x, x, 1);
            helper.getLevel().setBlock(helper.absolutePos(step), east, Block.UPDATE_ALL);
            helper.setBlock(step.above(), Blocks.AIR);
        }
        BlockPos turn = base.offset(3, 4, 2);
        BlockPos opening = base.offset(3, 4, 1);
        BlockPos landing = base.offset(3, 5, 3);
        helper.getLevel().setBlock(helper.absolutePos(turn), south, Block.UPDATE_ALL);
        helper.setBlock(turn.above(), Blocks.AIR);
        helper.setBlock(opening, Blocks.AIR);
        helper.setBlock(opening.above(), Blocks.AIR);
        helper.setBlock(landing.below(), Blocks.OAK_PLANKS);
        helper.setBlock(landing, Blocks.AIR);
        helper.setBlock(landing.above(), Blocks.AIR);
        helper.runAtTickTime(4, () -> {
            BlockPos worldBase = helper.absolutePos(base);
            if (!VillageBuildingService.connectedUpperStories(
                    helper.getLevel(), worldBase, 1)) {
                helper.fail("A continuous, correctly faced real stair flight should connect floors", MARK);
                return;
            }
            helper.getLevel().setBlock(helper.absolutePos(base.offset(2, 2, 1)),
                    east.setValue(HorizontalDirectionalBlock.FACING, Direction.NORTH),
                    Block.UPDATE_ALL);
            if (VillageBuildingService.connectedUpperStories(helper.getLevel(), worldBase, 1)) {
                helper.fail("A rotated middle tread cannot count as connected stairs", MARK);
                return;
            }
            helper.getLevel().setBlock(helper.absolutePos(base.offset(2, 2, 1)),
                    east, Block.UPDATE_ALL);
            helper.setBlock(opening, Blocks.OBSIDIAN);
            if (VillageBuildingService.connectedUpperStories(helper.getLevel(), worldBase, 1)) {
                helper.fail("A player-blocked stair opening must veto upper occupancy", MARK);
                return;
            }
            helper.succeed();
        });
    }

    @GameTest(template = "empty3x3x3", timeoutTicks = 35)
    public static void threeStoryRevalidationFitsDefaultBoundedProbeBudget(
            GameTestHelper helper) {
        BlockPos base = helper.absolutePos(new BlockPos(1, 1, 1));
        int second = 0;
        int third = 0;
        for (int y = 0; y <= 12; y++) {
            for (int x = 0; x < 5; x++) {
                for (int z = 0; z < 5; z++) {
                    BlockPos candidate = base.offset(x, y, z);
                    if (VillageBuildingService.templateInteriorCell(base, candidate, 2)) second++;
                    if (VillageBuildingService.templateInteriorCell(base, candidate, 3)) third++;
                }
            }
        }
        if (second != 54 || third != 81 || third > 256) {
            helper.fail("Multistorey validation tried to scan the whole 325-block shell",
                    new BlockPos(1, 1, 1));
            return;
        }
        helper.succeed();
    }

    @GameTest(template = "empty3x3x3", timeoutTicks = 40)
    public static void multistoryBlueprintKeepsUpperLandingFreeOfBeds(
            GameTestHelper helper) {
        var level = helper.getLevel();
        var data = VillageSavedData.get(level);
        var village = data.createVillage(helper.absolutePos(new BlockPos(1, 1, 1)),
                level.getGameTime());
        for (String template : List.of("house_2story_5x5", "house_3story_5x5")) {
            var project = data.createProject(village.id(), "building", 75,
                    helper.absolutePos(new BlockPos(1, 1, 1)));
            project.setTemplateId(template);
            project.setParameter("plank", "oak");
            project.setParameter("outpost", "false");
            project.setParameter("lead_skill", "100");
            var plan = VillageSimulationEvents.projectPlan(project);
            var base = project.site();
            boolean multiThird = "house_3story_5x5".equals(template);
            int expectedBeds = multiThird ? 5 : 4;
            long feet = plan.stream().filter(step ->
                    step.state().hasProperty(BedBlock.PART)
                            && step.state().getValue(BedBlock.PART) == BedPart.FOOT).count();
            if (feet != expectedBeds
                    || plan.stream().noneMatch(step -> step.pos().equals(base.offset(3, 4, 2))
                        && step.state().is(Blocks.OAK_STAIRS))
                    || plan.stream().anyMatch(step -> step.pos().equals(base.offset(3, 5, 3))
                        && !step.state().isAir())
                    || multiThird && plan.stream().anyMatch(step ->
                        step.pos().equals(base.offset(3, 9, 3)) && !step.state().isAir())) {
                helper.fail("Upper stairwell blocked or phantom bed/roof capacity in " + template,
                        new BlockPos(1, 1, 1));
                return;
            }
        }
        helper.succeed();
    }
}
