package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaks;
import java.util.List;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.gametest.framework.GameTest;
import net.minecraft.gametest.framework.GameTestHelper;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.BedBlock;
import net.minecraft.world.level.block.HorizontalDirectionalBlock;
import net.minecraft.world.level.block.state.properties.BedPart;
import net.neoforged.neoforge.gametest.GameTestHolder;
import net.neoforged.neoforge.gametest.PrefixGameTestTemplate;

/** Restart-safe physical construction payment checks for P0 world conservation. */
@GameTestHolder(AsobibaTweaks.MOD_ID)
@PrefixGameTestTemplate(false)
public final class VillageConstructionRecoveryGameTests {
    private static final BlockPos MARKER = new BlockPos(8, 3, 4);
    private VillageConstructionRecoveryGameTests() {}

    @GameTest(template = "empty16x6x9", batch = "building_recovery")
    public static void alreadyPresentFoundationAdvancesWithoutPayingAgain(GameTestHelper helper) {
        Fixture f = prepare(helper);
        var step = f.plan().getFirst();
        helper.getLevel().setBlock(step.pos(), step.state(), Block.UPDATE_CLIENTS);
        f.project().setReservation(VillageStorageService.itemKey(step.cost()), 1);
        if (!VillageSimulationEvents.reconcileCompletedBuildingStep(
                f.level(), f.project(), f.plan())
                || f.project().workCursor() != 1
                || !f.project().reservations().isEmpty()
                || !f.level().getBlockState(step.pos()).equals(step.state())) {
            helper.fail("Identical existing foundation should reconcile cursor without material debit",
                    MARKER);
            return;
        }
        // A second application must not acknowledge the same physical step.
        if (VillageSimulationEvents.reconcileCompletedBuildingStep(
                f.level(), f.project(), f.plan())
                || f.project().workCursor() != 1) {
            helper.fail("Unexpected construction cursor after repeated acknowledgement", MARKER);
            return;
        }
        var serialized = f.data().save(new CompoundTag(), f.level().registryAccess());
        var reloaded = VillageSavedData.load(serialized, f.level().registryAccess());
        if (reloaded.project(f.project().id()).orElseThrow().workCursor() != 1) {
            helper.fail("Reconciled building cursor did not persist", MARKER);
            return;
        }
        helper.succeed();
    }

    @GameTest(template = "empty16x6x9", batch = "building_recovery")
    public static void completedTwoHalfBedReconcilesExactlyOneUnpaidCursor(GameTestHelper helper) {
        Fixture f = prepare(helper);
        int index = footIndex(f.plan());
        var step = f.plan().get(index);
        var foot = step.pos();
        var head = foot.relative(step.state().getValue(HorizontalDirectionalBlock.FACING));
        f.level().setBlock(foot.below(), Blocks.OAK_PLANKS.defaultBlockState(), Block.UPDATE_CLIENTS);
        f.level().setBlock(head.below(), Blocks.OAK_PLANKS.defaultBlockState(), Block.UPDATE_CLIENTS);
        f.level().setBlock(foot, step.state(), Block.UPDATE_CLIENTS);
        f.level().setBlock(head, step.state().setValue(BedBlock.PART, BedPart.HEAD),
                Block.UPDATE_CLIENTS);
        f.project().setWorkCursor(index);
        f.project().setReservation("tag:minecraft:wool", 3);
        f.project().setReservation("tag:minecraft:planks", 3);
        if (!VillageSimulationEvents.reconcileCompletedBuildingStep(
                f.level(), f.project(), f.plan())
                || f.project().workCursor() != index + 2
                || !f.project().reservations().isEmpty()) {
            helper.fail("One completed double-block bed must not consume a second wool/plank recipe",
                    MARKER);
            return;
        }
        helper.succeed();
    }

    @GameTest(template = "empty16x6x9", batch = "building_recovery")
    public static void brokenBedHalfNeverApprovesFreeCompletedBed(GameTestHelper helper) {
        Fixture f = prepare(helper);
        int index = footIndex(f.plan());
        var step = f.plan().get(index);
        var foot = step.pos();
        var head = foot.relative(step.state().getValue(HorizontalDirectionalBlock.FACING));
        f.level().setBlock(foot.below(), Blocks.OAK_PLANKS.defaultBlockState(), Block.UPDATE_CLIENTS);
        f.level().setBlock(head.below(), Blocks.OAK_PLANKS.defaultBlockState(), Block.UPDATE_CLIENTS);
        f.level().setBlock(foot, step.state(), Block.UPDATE_CLIENTS);
        f.level().setBlock(head, Blocks.OBSIDIAN.defaultBlockState(), Block.UPDATE_CLIENTS);
        f.project().setWorkCursor(index);
        f.project().setReservation("tag:minecraft:wool", 3);
        f.project().setReservation("tag:minecraft:planks", 3);
        if (VillageSimulationEvents.reconcileCompletedBuildingStep(
                f.level(), f.project(), f.plan())
                || f.project().workCursor() != index
                || f.project().reservations().size() != 2
                || !f.level().getBlockState(head).is(Blocks.OBSIDIAN)) {
            helper.fail("Existing partial bed/foreign obstruction must not count as completed", MARKER);
            return;
        }
        helper.succeed();
    }

    private static int footIndex(List<VillageSimulationEvents.BuildStep> plan) {
        for (int i = 0; i < plan.size(); i++) {
            var state = plan.get(i).state();
            if (state.hasProperty(BedBlock.PART)
                    && state.getValue(BedBlock.PART) == BedPart.FOOT) return i;
        }
        throw new IllegalStateException("The original village house has no bed foot");
    }

    private static Fixture prepare(GameTestHelper helper) {
        var level = helper.getLevel();
        var data = VillageSavedData.get(level);
        BlockPos base = helper.absolutePos(new BlockPos(5, 1, 2));
        var village = data.createVillage(base, level.getGameTime());
        var project = data.createProject(village.id(), "building", 75, base);
        project.setTemplateId("house_5x5");
        project.setParameter("plank", "oak");
        project.setParameter("lead_skill", "100");
        project.setVariantSeed(13L);
        return new Fixture(level, data, project, VillageSimulationEvents.projectPlan(project));
    }

    private record Fixture(net.minecraft.server.level.ServerLevel level,
                           VillageSavedData data, VillageSavedData.ProjectRecord project,
                           List<VillageSimulationEvents.BuildStep> plan) {}
}
