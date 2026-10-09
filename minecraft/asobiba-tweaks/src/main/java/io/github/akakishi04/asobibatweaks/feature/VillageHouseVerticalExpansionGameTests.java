package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaks;
import java.util.List;
import java.util.UUID;
import net.minecraft.core.BlockPos;
import net.minecraft.gametest.framework.GameTest;
import net.minecraft.gametest.framework.GameTestHelper;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.Container;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.npc.Villager;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.block.BedBlock;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.properties.BedPart;
import net.neoforged.neoforge.gametest.GameTestHolder;
import net.neoforged.neoforge.gametest.PrefixGameTestTemplate;

/**
 * Actual server-world checks for initial V89 in-place roof/floor conversion.
 * First tests use a genuinely built and registered ground-floor shelter.
 * The full-geometry test checks registration and accessibility independently
 * of long-lived NPC navigation; it is not an autonomous-play certification.
 */
@GameTestHolder(AsobibaTweaks.MOD_ID)
@PrefixGameTestTemplate(false)
public final class VillageHouseVerticalExpansionGameTests {
    private static final BlockPos MARK = new BlockPos(7, 5, 4);
    private VillageHouseVerticalExpansionGameTests() {}

    @GameTest(template = "empty16x14x9", timeoutTicks = 70)
    public static void originalPaidHouseSchedulesPersistedSecondFloor(GameTestHelper helper) {
        Fixture f = setup(helper);
        helper.runAtTickTime(4, () -> {
            if (!VillageHouseVerticalExpansionService.tryPlan(
                    f.builder(), f.level(), f.villageId())) {
                helper.fail("Original safe home with real materials was not selected", MARK);
                return;
            }
            var p = active(f);
            if (p == null || !p.site().equals(f.base()) || !"upper_shell".equals(p.phase())
                    || f.village().buildingIds().size() != 1) {
                helper.fail("In-place extension must retain the original house identity", MARK);
                return;
            }
            var saved = f.data().save(new CompoundTag(), f.level().registryAccess());
            var restored = VillageSavedData.load(saved, f.level().registryAccess());
            var again = restored.project(p.id()).orElse(null);
            if (again == null || !again.site().equals(f.base())
                    || !p.parameter("expand_building").equals(again.parameter("expand_building"))
                    || restored.building(f.house().id()).isEmpty()) {
                helper.fail("House/extension IDs disappeared in world SavedData roundtrip", MARK);
                return;
            }
            helper.succeed();
        });
    }

    @GameTest(template = "empty16x14x9", timeoutTicks = 70)
    public static void playerUpperShellEditBlocksExpansionWithoutPayment(GameTestHelper helper) {
        Fixture f = setup(helper);
        f.level().setBlock(f.base().offset(0, 6, 1),
                Blocks.OBSIDIAN.defaultBlockState(), Block.UPDATE_ALL);
        helper.runAtTickTime(4, () -> {
            if (VillageHouseVerticalExpansionService.tryPlan(
                    f.builder(), f.level(), f.villageId())
                    || !f.data().activeProjectsForVillage(f.villageId()).isEmpty()
                    || count(f.materials(), Items.OAK_PLANKS) != 128
                    || !f.level().getBlockState(f.base().offset(0, 6, 1)).is(Blocks.OBSIDIAN)) {
                helper.fail("Player-altered upper volume must veto paid expansion", MARK);
                return;
            }
            helper.succeed();
        });
    }

    @GameTest(template = "empty16x14x9", timeoutTicks = 70)
    public static void placedUpperWallReconcilesWithoutSecondItemDebit(GameTestHelper helper) {
        Fixture f = setup(helper);
        helper.runAtTickTime(4, () -> {
            // GT51 separately validates the autonomous planner. This case
            // isolates the paid worker step from planner tick contention in
            // a shared GameTestServer with many simulated villages.
            var original = f.village().projectIds().stream()
                    .map(f.data()::project).flatMap(java.util.Optional::stream)
                    .filter(candidate -> "house_5x5".equals(candidate.templateId())
                            && "complete".equals(candidate.phase()))
                    .findFirst().orElseThrow();
            var p = f.data().createProject(
                    f.villageId(), "building", 86, f.base());
            p.setTemplateId(VillageHouseVerticalExpansionService.TEMPLATE);
            p.setParameter("expand_building", f.house().id().toString());
            p.setParameter("expand_original", original.id().toString());
            p.setParameter("expand_plank", "oak");
            p.setPhase("upper_shell");
            p.setWorkCursor(0);
            f.data().touch();
            var work = VillageHouseVerticalExpansionService.steps(p);
            VillageHouseVerticalExpansionService.Step first = work.getFirst();
            // Source the exact material from a real Barrel, then stage it in
            // the persistent worker cargo. GT53 isolates paid placement and
            // cursor crash-reconciliation from the separate navigation and
            // automatic supply planner exercised by other test families.
            ItemStack withdrawn = f.materials().removeItem(0, 1);
            if (!withdrawn.is(Items.OAK_PLANKS) || withdrawn.getCount() != 1
                    || !VillagerSimData.insertWorkCargo(
                            f.builder(), f.level().registryAccess(), withdrawn, 8).isEmpty()) {
                helper.fail("Could not physically stage the one real plank", MARK);
                return;
            }
            f.materials().setChanged();
            f.builder().setPos(first.pos().getX() + 0.5D,
                    first.pos().getY(), first.pos().getZ() + 0.5D);
            VillageHouseVerticalExpansionService.advance(f.builder(), f.level(), p);
            int afterFirst = count(f.materials(), Items.OAK_PLANKS);
            if (!f.level().getBlockState(first.pos()).equals(first.state())
                    || p.workCursor() != 1 || afterFirst != 127) {
                helper.fail("An upper wall must cost exactly one real plank", MARK);
                return;
            }
            // Simulate a project cursor save lag after the actual block was
            // placed. Existing identical physical work must not cost again.
            p.setWorkCursor(0);
            VillageHouseVerticalExpansionService.advance(f.builder(), f.level(), p);
            if (p.workCursor() != 1
                    || count(f.materials(), Items.OAK_PLANKS) != afterFirst
                    || f.village().buildingIds().size() != 1) {
                helper.fail("Already built expansion wall was double-charged", MARK);
                return;
            }
            helper.succeed();
        });
    }

    @GameTest(template = "empty16x14x9", timeoutTicks = 160)
    public static void physicallyCompleteSecondStoreyRetainsBuildingIdAndCountsBeds(
            GameTestHelper helper) {
        Fixture f = setup(helper);
        helper.runAtTickTime(5, () -> {
            if (!VillageHouseVerticalExpansionService.tryPlan(
                    f.builder(), f.level(), f.villageId())) {
                helper.fail("Cannot plan second-storey geometry review", MARK);
                return;
            }
            var p = active(f);
            List<VillageHouseVerticalExpansionService.Step> plan =
                    VillageHouseVerticalExpansionService.steps(p);

            // Build the expected physical world for a focused, independent
            // geometry/BuildingRecord acceptance check. GT53 separately tests
            // the real inventory withdrawal path for actual worker placement.
            for (var step : plan) {
                if (step.remove()) {
                    f.level().setBlock(step.pos(),
                            Blocks.AIR.defaultBlockState(), Block.UPDATE_CLIENTS);
                } else if (step.bed()) {
                    f.level().setBlock(step.pos(), step.state(), Block.UPDATE_CLIENTS);
                    f.level().setBlock(step.pos().relative(
                            step.state().getValue(BedBlock.FACING)),
                            step.state().setValue(BedBlock.PART, BedPart.HEAD),
                            Block.UPDATE_CLIENTS);
                } else {
                    f.level().setBlock(step.pos(), step.state(), Block.UPDATE_CLIENTS);
                }
            }
            if (!VillageHouseVerticalExpansionService.allComplete(f.level(), p)
                    || !VillageBuildingService.connectedUpperStories(f.level(), f.base(), 1)) {
                helper.fail("Correct two-storey staircase/roof/rooms were rejected", MARK);
                return;
            }
            p.setWorkCursor(plan.size());
            VillageHouseVerticalExpansionService.advance(f.builder(), f.level(), p);
            if (!"complete".equals(p.phase())
                    || f.village().buildingIds().size() != 1
                    || !f.house().max().equals(f.base().offset(4, 8, 4))
                    || !"house_2story_5x5".equals(f.house().templateId())) {
                helper.fail("Finished upper storey duplicated or failed to expand original record",
                        MARK);
                return;
            }
            helper.runAtTickTime(45, () -> {
                VillageBuildingService.revalidateChunk(
                        f.level(), new ChunkPos(f.base()));
                var saved = f.data().save(new CompoundTag(), f.level().registryAccess());
                var restored = VillageSavedData.load(saved, f.level().registryAccess());
                var home = restored.building(f.house().id()).orElse(null);
                if (home == null || !"valid".equals(home.validationState())
                        || home.validatedCapacity() != 3
                        || !home.max().equals(f.base().offset(4, 8, 4))
                        || restored.village(f.villageId()).orElseThrow().buildingIds().size() != 1) {
                    helper.fail("In-place upstairs housing count/bounds/ID were not durable",
                            MARK);
                    return;
                }
                helper.succeed();
            });
        });
    }

    private static Fixture setup(GameTestHelper helper) {
        ServerLevel level = helper.getLevel();
        BlockPos base = helper.absolutePos(new BlockPos(5, 1, 2));

        // A true one-storey 5x5 template, not a fake capacity-only record.
        VillageSavedData data = VillageSavedData.get(level);
        var village = data.createVillage(base, level.getGameTime());
        var source = data.createProject(village.id(), "building", 70, base);
        source.setTemplateId("house_5x5");
        source.setParameter("plank", "oak");
        source.setParameter("outpost", "false");
        source.setParameter("lead_skill", "100");
        source.setPhase("complete");
        source.setVariantSeed(13L);
        for (var step : VillageSimulationEvents.projectPlan(source)) {
            if (step.state().is(Blocks.WHITE_BED)
                    || step.state().is(Blocks.COBBLESTONE)
                    || step.state().is(Blocks.OAK_PLANKS)) {
                level.setBlock(step.pos(), step.state(), Block.UPDATE_CLIENTS);
            }
        }
        level.updateNeighborsAt(base.offset(2, 1, 2), Blocks.WHITE_BED);
        level.updateNeighborsAt(base.offset(2, 1, 3), Blocks.WHITE_BED);

        for (int x = 0; x < 5; x++) for (int z = 0; z < 5; z++)
            for (int y = 5; y <= 9; y++)
                level.setBlock(base.offset(x, y, z),
                        Blocks.AIR.defaultBlockState(), Block.UPDATE_CLIENTS);

        var building = data.createBuilding(village.id(), base, base.offset(4, 4, 4), true);
        building.setTemplateId("house_5x5");
        building.setClassification("residential");
        building.setValidationState("valid");
        building.setValidatedCapacity(1);

        BlockPos stock = base.offset(3, 1, 1);
        level.setBlock(stock, Blocks.BARREL.defaultBlockState(), Block.UPDATE_ALL);
        var registered = data.createStorage(village.id(), stock, "construction");
        registered.setValidationState("valid");
        if (!(level.getBlockEntity(stock) instanceof Container inventory))
            throw new IllegalStateException("GameTest must have a real material Barrel");
        inventory.setItem(0, new ItemStack(Items.OAK_PLANKS, 64));
        inventory.setItem(1, new ItemStack(Items.OAK_PLANKS, 64));
        inventory.setItem(2, new ItemStack(Items.OAK_STAIRS, 4));
        inventory.setItem(3, new ItemStack(Items.WHITE_BED, 2));

        Villager builder = EntityType.VILLAGER.create(level);
        if (builder == null) throw new IllegalStateException("Villager entity factory failed");
        builder.setPos(base.getX() + 2.5D, base.getY() + 2.0D,
                base.getZ() + 0.5D);
        builder.setNoAi(true);
        if (!level.addFreshEntity(builder)) throw new IllegalStateException("Carpenter spawn failed");
        VillagerSimData.setVillageId(builder, village.id());
        VillagerSimData.setDuty(builder, "carpenter", level.getGameTime());
        VillagerSimData.setCarpentrySkill(builder, 75);
        VillageStorageService.reconcileVillage(village.id(), level);
        return new Fixture(level, data, village, building, builder, inventory, base);
    }

    private static VillageSavedData.ProjectRecord active(Fixture f) {
        return f.data().activeProjectsForVillage(f.villageId()).stream()
                .filter(p -> VillageHouseVerticalExpansionService.TEMPLATE.equals(p.templateId()))
                .findFirst().orElse(null);
    }

    private static int count(Container container, net.minecraft.world.item.Item item) {
        int count = 0;
        for (int i = 0; i < container.getContainerSize(); i++)
            if (container.getItem(i).is(item)) count += container.getItem(i).getCount();
        return count;
    }

    private record Fixture(ServerLevel level, VillageSavedData data,
                           VillageSavedData.VillageRecord village,
                           VillageSavedData.BuildingRecord house,
                           Villager builder, Container materials, BlockPos base) {
        UUID villageId() { return village.id(); }
    }
}
