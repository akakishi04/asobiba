package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaks;
import java.util.List;
import net.minecraft.core.BlockPos;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.gametest.framework.GameTest;
import net.minecraft.gametest.framework.GameTestHelper;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.Container;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.npc.Villager;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.neoforged.neoforge.gametest.GameTestHolder;
import net.neoforged.neoforge.gametest.PrefixGameTestTemplate;

/**
 * Small server-world GameTests for actual physical worker stock conversions
 * and for deterministic, semantically distinct specialist blueprints.
 */
@GameTestHolder(AsobibaTweaks.MOD_ID)
@PrefixGameTestTemplate(false)
public final class VillageSpecialistWorkshopGameTests {
    private static final BlockPos CENTER = new BlockPos(1, 1, 1);

    private VillageSpecialistWorkshopGameTests() {}

    @GameTest(template = "empty3x3x3", batch = "specialist_crafting")
    public static void loomConsumesRealPlanksAndString(GameTestHelper helper) {
        Fixture fixture = setup(helper);
        fixture.storage().setItem(0, new ItemStack(Items.OAK_PLANKS, 4));
        fixture.storage().setItem(1, new ItemStack(Items.STRING, 2));
        if (!VillageCarpenterCraftingService.ensureFixture(
                fixture.carpenter(), fixture.level(),
                Items.LOOM, Blocks.OAK_PLANKS, 8)) {
            helper.fail("Available exact Loom ingredients did not assemble", CENTER);
            return;
        }
        if (count(fixture.storage(), Items.OAK_PLANKS) != 2
                || count(fixture.storage(), Items.STRING) != 0
                || VillagerSimData.workCargoCount(
                        fixture.carpenter(), fixture.level().registryAccess(),
                        8, Items.LOOM) != 1
                || VillagerSimData.workCargoCount(
                        fixture.carpenter(), fixture.level().registryAccess(),
                        8, Items.OAK_PLANKS) != 0) {
            helper.fail("Loom craft invented or lost physical recipe inputs", CENTER);
            return;
        }
        helper.succeed();
    }

    @GameTest(template = "empty3x3x3", batch = "specialist_crafting")
    public static void lecternCraftsBookshelfWithExactPhysicalInputs(GameTestHelper helper) {
        Fixture fixture = setup(helper);
        fixture.storage().setItem(0, new ItemStack(Items.OAK_PLANKS, 15));
        fixture.storage().setItem(1, new ItemStack(Items.PAPER, 9));
        fixture.storage().setItem(2, new ItemStack(Items.LEATHER, 3));
        if (!VillageCarpenterCraftingService.ensureFixture(
                fixture.carpenter(), fixture.level(),
                Items.LECTERN, Blocks.OAK_PLANKS, 8)) {
            helper.fail("Lectern must craft from real paper, leather and planks", CENTER);
            return;
        }
        if (count(fixture.storage(), Items.OAK_PLANKS) != 6
                || count(fixture.storage(), Items.PAPER) != 0
                || count(fixture.storage(), Items.LEATHER) != 0
                || VillagerSimData.workCargoCount(fixture.carpenter(),
                        fixture.level().registryAccess(), 8, Items.LECTERN) != 1
                || VillagerSimData.workCargoCount(fixture.carpenter(),
                        fixture.level().registryAccess(), 8, Items.OAK_SLAB) != 2) {
            helper.fail("Lectern, books, bookshelf or slabs broke exact recipe accounting", CENTER);
            return;
        }
        helper.succeed();
    }

    @GameTest(template = "empty3x3x3", batch = "specialist_crafting")
    public static void specialistBlueprintsOwnDifferentRoofsAndRealWorkstations(GameTestHelper helper) {
        Fixture fixture = setup(helper);
        var data = VillageSavedData.get(fixture.level());
        var villageId = VillagerSimData.villageId(fixture.carpenter()).orElseThrow();
        String[] templates = {"village_library_5x5", "village_armory_5x5",
                "village_fishery_5x5"};
        Block[] stations = {Blocks.LECTERN, Blocks.BLAST_FURNACE, Blocks.BARREL};
        BlockPos foundation = helper.absolutePos(CENTER);
        for (int i = 0; i < templates.length; i++) {
            var project = data.createProject(villageId, "building", 65, foundation);
            project.setTemplateId(templates[i]);
            project.setParameter("plank", "oak");
            List<VillageSimulationEvents.BuildStep> steps =
                    VillageSimulationEvents.projectPlan(project);
            Block expected = stations[i];
            boolean primary = steps.stream().anyMatch(s ->
                    s.pos().equals(foundation.offset(2, 1, 2))
                            && s.state().is(expected)
                            && s.cost() == expected.asItem());
            boolean storage = steps.stream().anyMatch(s ->
                    s.pos().equals(foundation.offset(3, 1, 3))
                            && s.state().is(Blocks.BARREL)
                            && s.cost() == Items.BARREL);
            boolean hasHighRoof = steps.stream().anyMatch(s ->
                    s.pos().getY() == foundation.getY() + 6);
            boolean stoneRoof = steps.stream().anyMatch(s ->
                    s.pos().equals(foundation.offset(2, 4, 2))
                            && s.state().is(Blocks.COBBLESTONE));
            if (!primary || !storage || (i == 0 && !hasHighRoof)
                    || (i == 1 && !stoneRoof)
                    || (i == 2 && (hasHighRoof || stoneRoof))) {
                helper.fail("Specialist workstations, stock Barrels or roof families are wrong",
                        CENTER);
                return;
            }
        }
        helper.succeed();
    }

    /** Recognized, physically traversable ground-floor POI stays functional. */
    @GameTest(template = "empty16x6x9", batch = "specialist_crafting", timeoutTicks = 45)
    public static void realSpecialistEntryMakesRegisteredStationReachable(
            GameTestHelper helper) {
        WorkshopFixture f = setupPhysicalWorkshop(helper);
        helper.runAtTickTime(7, () -> {
            VillageBuildingService.revalidateChunk(
                    f.level(), new ChunkPos(f.origin()));
            if (!f.level().getBlockState(f.origin().offset(2, 1, 2))
                        .is(Blocks.BLAST_FURNACE)
                    || !VillageBuildingService.specialistPrimaryStationAccessible(
                            f.level(), f.origin())
                    || !"valid".equals(f.building().validationState())
                    || f.building().validatedCapacity() != 1) {
                helper.fail("Physically open public hall did not expose its real job-site POI",
                        new BlockPos(7, 2, 4));
                return;
            }
            helper.succeed();
        });
    }

    /** A workstation can survive, yet be unreachable behind an edited wall. */
    @GameTest(template = "empty16x6x9", batch = "specialist_crafting", timeoutTicks = 55)
    public static void blockedSpecialistPassageCannotCountAsWorkingPoi(
            GameTestHelper helper) {
        WorkshopFixture f = setupPhysicalWorkshop(helper);
        BlockPos hallway = f.origin().offset(2, 1, 1);
        f.level().setBlock(hallway, Blocks.OBSIDIAN.defaultBlockState(), Block.UPDATE_ALL);
        helper.runAtTickTime(8, () -> {
            VillageBuildingService.revalidateChunk(f.level(), new ChunkPos(f.origin()));
            if (!f.level().getBlockState(hallway).is(Blocks.OBSIDIAN)
                    || !f.level().getBlockState(f.origin().offset(2, 1, 2))
                        .is(Blocks.BLAST_FURNACE)
                    || VillageBuildingService.specialistPrimaryStationAccessible(
                            f.level(), f.origin())
                    || !"invalid".equals(f.building().validationState())
                    || f.building().validatedCapacity() != 0) {
                helper.fail("Blocked real workstation corridor was wrongly considered usable",
                        new BlockPos(7, 2, 3));
                return;
            }
            f.level().setBlock(hallway, Blocks.AIR.defaultBlockState(), Block.UPDATE_ALL);
            helper.runAtTickTime(22, () -> {
                VillageBuildingService.revalidateChunk(
                        f.level(), new ChunkPos(f.origin()));
                if (!VillageBuildingService.specialistPrimaryStationAccessible(
                            f.level(), f.origin())
                        || !"valid".equals(f.building().validationState())
                        || f.building().validatedCapacity() != 1) {
                    helper.fail("Removing obstruction did not restore a genuine job-site POI",
                            new BlockPos(7, 2, 3));
                    return;
                }
                helper.succeed();
            });
        });
    }

    private static WorkshopFixture setupPhysicalWorkshop(GameTestHelper helper) {
        ServerLevel level = helper.getLevel();
        BlockPos base = helper.absolutePos(new BlockPos(5, 1, 2));
        VillageSavedData data = VillageSavedData.get(level);
        var village = data.createVillage(base, level.getGameTime());
        var source = data.createProject(village.id(), "building", 65, base);
        source.setTemplateId("village_armory_5x5");
        source.setParameter("plank", "oak");
        source.setPhase("complete");
        for (var part : VillageSimulationEvents.projectPlan(source)) {
            if (!part.state().isAir()) {
                level.setBlock(part.pos(), part.state(), Block.UPDATE_CLIENTS);
            }
        }
        var building = data.createBuilding(
                village.id(), base, base.offset(4, 4, 4), true);
        building.setTemplateId("village_armory_5x5");
        building.setClassification("workshop");
        building.setValidationState("unknown");
        building.setValidatedCapacity(0);
        data.touch();
        return new WorkshopFixture(level, base, building);
    }

    private record WorkshopFixture(ServerLevel level, BlockPos origin,
                                   VillageSavedData.BuildingRecord building) {}

    private static Fixture setup(GameTestHelper helper) {
        helper.setBlock(CENTER, Blocks.BARREL);
        ServerLevel level = helper.getLevel();
        BlockPos barrelPos = helper.absolutePos(CENTER);
        VillageSavedData data = VillageSavedData.get(level);
        var village = data.createVillage(barrelPos, level.getGameTime());
        var storage = data.createStorage(village.id(), barrelPos, "construction");
        storage.setValidationState("valid");
        if (!(level.getBlockEntity(barrelPos) instanceof Container physical))
            throw new IllegalStateException("GameTest did not create actual Barrel");
        Villager carpenter = EntityType.VILLAGER.create(level);
        if (carpenter == null) throw new IllegalStateException("Villager factory unavailable");
        carpenter.setPos(barrelPos.getX() + 1.5D,
                barrelPos.getY() + 0.5D, barrelPos.getZ() + 0.5D);
        carpenter.setNoAi(true);
        if (!level.addFreshEntity(carpenter)) throw new IllegalStateException("Carpenter spawn failed");
        VillagerSimData.setVillageId(carpenter, village.id());
        VillagerSimData.setDuty(carpenter, "carpenter", level.getGameTime());
        return new Fixture(level, carpenter, physical);
    }

    private static int count(Container c, Item item) {
        int count = 0;
        for (int i = 0; i < c.getContainerSize(); i++) {
            ItemStack stack = c.getItem(i);
            if (stack.is(item)) count += stack.getCount();
        }
        return count;
    }

    private record Fixture(ServerLevel level, Villager carpenter, Container storage) {}
}
