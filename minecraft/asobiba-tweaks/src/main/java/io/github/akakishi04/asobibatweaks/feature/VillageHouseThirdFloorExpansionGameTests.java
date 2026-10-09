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
import net.minecraft.world.entity.item.ItemEntity;
import net.minecraft.world.entity.npc.Villager;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.block.BedBlock;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.phys.AABB;
import net.neoforged.neoforge.gametest.GameTestHolder;
import net.neoforged.neoforge.gametest.PrefixGameTestTemplate;

/** Physical two-to-three-storey work, real demolition drops and ID durability. */
@GameTestHolder(AsobibaTweaks.MOD_ID)
@PrefixGameTestTemplate(false)
public final class VillageHouseThirdFloorExpansionGameTests {
    private static final BlockPos MARK = new BlockPos(8, 8, 4);

    private VillageHouseThirdFloorExpansionGameTests() {}

    @GameTest(template = "empty16x14x9", timeoutTicks = 65)
    public static void skilledOriginalSecondFloorSchedulesPersistentThirdFloor(
            GameTestHelper helper) {
        Fixture f = setup(helper);
        helper.runAtTickTime(4, () -> {
            if (!VillageHouseThirdFloorExpansionService.tryPlan(
                    f.builder(), f.level(), f.villageId())) {
                helper.fail("Master Carpenter with original two-storey home must plan third floor", MARK);
                return;
            }
            var p = active(f);
            if (p == null || p.workCursor() != 0
                    || !f.house().id().toString().equals(p.parameter("third_building"))
                    || p.reservations().getOrDefault("minecraft:oak_planks", 0) != 71
                    || f.village().buildingIds().size() != 1) {
                helper.fail("Third-floor project failed to preserve original house identity", MARK);
                return;
            }
            var saved = f.data().save(new CompoundTag(), f.level().registryAccess());
            var loaded = VillageSavedData.load(saved, f.level().registryAccess());
            var original = loaded.building(f.house().id()).orElse(null);
            var task = loaded.project(p.id()).orElse(null);
            if (original == null || task == null
                    || !"house_2story_5x5".equals(original.templateId())
                    || !f.house().id().toString().equals(task.parameter("third_building"))) {
                helper.fail("Third-floor plan or original building disappeared after world NBT", MARK);
                return;
            }
            helper.succeed();
        });
    }

    @GameTest(template = "empty16x14x9", timeoutTicks = 65)
    public static void playerEditedThirdFloorCannotTriggerDemolition(GameTestHelper helper) {
        Fixture f = setup(helper);
        BlockPos blocker = f.base().offset(0, 10, 1);
        f.level().setBlock(blocker, Blocks.OBSIDIAN.defaultBlockState(), Block.UPDATE_ALL);
        // Check at the setup tick: unrelated worker AI may move real cargo
        // in the shared GameTestServer after the preflight was already done.
        int before = count(f.storage(), Items.OAK_PLANKS);
        boolean planned = VillageHouseThirdFloorExpansionService.tryPlan(
                f.builder(), f.level(), f.villageId());
        int after = count(f.storage(), Items.OAK_PLANKS);
        if (planned || !f.data().activeProjectsForVillage(f.villageId()).isEmpty()
                || !f.level().getBlockState(blocker).is(Blocks.OBSIDIAN)
                || before != after
                || f.level().getBlockState(f.base().offset(2, 5, 1))
                    .getBlock() != Blocks.WHITE_BED) {
            helper.fail("Edited upper space: planned=" + planned
                    + ", projects=" + f.data().activeProjectsForVillage(f.villageId()).size()
                    + ", block=" + f.level().getBlockState(blocker)
                    + ", plankBefore=" + before + ", plankAfter=" + after
                    + ", bed=" + f.level().getBlockState(f.base().offset(2, 5, 1)), MARK);
            return;
        }
        helper.succeed();
    }

    @GameTest(template = "empty16x14x9", timeoutTicks = 80)
    public static void secondStoreyBedDemolishesOnceAndDropsRealItem(GameTestHelper helper) {
        Fixture f = setup(helper);
        var project = project(f);
        List<VillageHouseThirdFloorExpansionService.Step> steps =
                VillageHouseThirdFloorExpansionService.steps(project);
        int salvageIndex = -1;
        for (int i = 0; i < steps.size(); i++) {
            if (steps.get(i).kind() == VillageHouseThirdFloorExpansionService.SALVAGE_BED) {
                salvageIndex = i;
                break;
            }
        }
        if (salvageIndex < 0) {
            helper.fail("No physical former-bedroom salvage task", MARK);
            return;
        }
        final int oldCursor = salvageIndex;
        var foot = steps.get(salvageIndex).pos();
        int beforeDrops = f.level().getEntitiesOfClass(ItemEntity.class,
                new AABB(foot).inflate(3.0D),
                x -> x.isAlive() && x.getItem().is(Items.WHITE_BED))
                .stream().mapToInt(e -> e.getItem().getCount()).sum();
        f.builder().setPos(foot.getX() + 0.5D, foot.getY() + 1, foot.getZ() + 0.5D);
        project.setWorkCursor(oldCursor);
        VillageHouseThirdFloorExpansionService.advance(f.builder(), f.level(), project);
        if (project.workCursor() != oldCursor + 1
                || !f.level().getBlockState(foot).isAir()
                || f.level().getBlockState(f.base().offset(1, 5, 1)).is(Blocks.WHITE_BED)) {
            helper.fail("Original complete second-floor bed was not physically demolished", MARK);
            return;
        }
        project.setWorkCursor(oldCursor);
        VillageHouseThirdFloorExpansionService.advance(f.builder(), f.level(), project);
        if (project.workCursor() != oldCursor + 1) {
            helper.fail("A removed bed cannot be charged or destroyed twice", MARK);
            return;
        }
        helper.runAtTickTime(5, () -> {
            List<ItemEntity> drops = f.level().getEntitiesOfClass(ItemEntity.class,
                    new AABB(foot).inflate(3.0D),
                    x -> x.isAlive() && x.getItem().is(Items.WHITE_BED));
            int units = drops.stream().mapToInt(e -> e.getItem().getCount()).sum();
            if (units - beforeDrops != 1) {
                String detail = drops.stream().map(e -> e.getItem().getCount()
                        + "@" + e.blockPosition()).toList().toString();
                helper.fail("One physical recovered Bed expected; before=" + beforeDrops
                        + ", after=" + units + ", drops=" + detail, MARK);
                return;
            }
            helper.succeed();
        });
    }

    @GameTest(template = "empty16x14x9", timeoutTicks = 95)
    public static void completeThirdFloorMaintainsOriginalIdAndFiveRealBeds(GameTestHelper helper) {
        Fixture f = setup(helper);
        var project = project(f);
        List<VillageHouseThirdFloorExpansionService.Step> planned =
                VillageHouseThirdFloorExpansionService.steps(project);
        for (var step : planned) {
            if (step.kind() == VillageHouseThirdFloorExpansionService.SALVAGE_BED) {
                // The full geometry fixture is not a material-transaction test;
                // GT58 covers the genuine recovered item.
                f.level().destroyBlock(step.pos(), false);
            } else if (step.kind() == VillageHouseThirdFloorExpansionService.REMOVE_ROOF) {
                f.level().setBlock(step.pos(), Blocks.AIR.defaultBlockState(), Block.UPDATE_CLIENTS);
            } else if (step.kind() == VillageHouseThirdFloorExpansionService.PLACE_BED) {
                f.level().setBlock(step.pos(), step.state(), Block.UPDATE_CLIENTS);
                var head = step.state().setValue(
                        BedBlock.PART, net.minecraft.world.level.block.state.properties.BedPart.HEAD);
                f.level().setBlock(step.pos().relative(
                        step.state().getValue(BedBlock.FACING)), head, Block.UPDATE_CLIENTS);
            } else {
                f.level().setBlock(step.pos(), step.state(), Block.UPDATE_CLIENTS);
            }
        }
        if (!VillageHouseThirdFloorExpansionService.allComplete(f.level(), project)
                || !VillageBuildingService.connectedUpperStories(f.level(), f.base(), 2)) {
            helper.fail("Third-floor bedroom geometry and stairwell failed physical verification", MARK);
            return;
        }
        project.setWorkCursor(planned.size());
        VillageHouseThirdFloorExpansionService.advance(f.builder(), f.level(), project);
        if (!"complete".equals(project.phase())
                || f.village().buildingIds().size() != 1
                || !f.house().max().equals(f.base().offset(4, 12, 4))
                || !"house_3story_5x5".equals(f.house().templateId())) {
            helper.fail("Full third floor did not safely upgrade original BuildingRecord", MARK);
            return;
        }
        helper.runAtTickTime(40, () -> {
            VillageBuildingService.revalidateChunk(
                    f.level(), new ChunkPos(f.base()));
            var nbt = f.data().save(new CompoundTag(), f.level().registryAccess());
            var loaded = VillageSavedData.load(nbt, f.level().registryAccess());
            var home = loaded.building(f.house().id()).orElse(null);
            if (home == null || !"valid".equals(home.validationState())
                    || home.validatedCapacity() != 5
                    || !home.max().equals(f.base().offset(4, 12, 4))
                    || loaded.village(f.villageId()).orElseThrow().buildingIds().size() != 1) {
                StringBuilder rooms = new StringBuilder();
                for (BlockPos local : List.of(
                        new BlockPos(2, 1, 2), new BlockPos(3, 1, 2),
                        new BlockPos(1, 5, 2), new BlockPos(1, 9, 2),
                        new BlockPos(2, 9, 1))) {
                    BlockPos foot = f.base().offset(local);
                    var block = f.level().getBlockState(foot);
                    var direction = block.hasProperty(BedBlock.FACING)
                            ? block.getValue(BedBlock.FACING) : net.minecraft.core.Direction.NORTH;
                    var head = f.level().getBlockState(foot.relative(direction));
                    rooms.append(local).append("=").append(block)
                            .append("/head=").append(head)
                            .append("/standing=")
                            .append(VillageBuildingAdoptionService.hasAdjacentStandingSpace(
                                    f.level(), foot, f.base(), f.base().offset(4, 12, 4)))
                            .append(";");
                }
                helper.fail("Upper housing invalid: rooms=" + rooms
                        + ", home=" + (home == null ? "null"
                        : home.validationState() + "/capacity=" + home.validatedCapacity()
                        + "/template=" + home.templateId() + "/max=" + home.max())
                        + ", expected=" + f.base().offset(4, 12, 4)
                        + ", count=" + loaded.village(f.villageId())
                            .orElseThrow().buildingIds().size()
                        + ", stairs=" + VillageBuildingService.connectedUpperStories(
                            f.level(), f.base(), 2), MARK);
                return;
            }
            helper.succeed();
        });
    }

    private static VillageSavedData.ProjectRecord project(Fixture f) {
        var p = f.data().createProject(f.villageId(), "building", 87, f.base());
        p.setTemplateId(VillageHouseThirdFloorExpansionService.TEMPLATE);
        p.setParameter("third_building", f.house().id().toString());
        p.setParameter("third_source", f.original().id().toString());
        p.setParameter("third_plank", "oak");
        p.setPhase("third_shell");
        p.setWorkCursor(0);
        f.data().touch();
        return p;
    }

    private static VillageSavedData.ProjectRecord active(Fixture f) {
        return f.data().activeProjectsForVillage(f.villageId()).stream()
                .filter(p -> VillageHouseThirdFloorExpansionService.TEMPLATE.equals(p.templateId()))
                .findFirst().orElse(null);
    }

    private static Fixture setup(GameTestHelper helper) {
        ServerLevel level = helper.getLevel();
        BlockPos base = helper.absolutePos(new BlockPos(5, 1, 2));
        // The blank NBT template holds a size/palette, but does not paste
        // AIR over every underlying server-world block. Explicitly clear the
        // complete test-only house volume BEFORE reconstructing its physical
        // blueprint. Otherwise natural stone can invisibly obstruct the
        // ground-floor standing cells while upper beds remain accessible.
        for (int x = 0; x < 5; x++) for (int z = 0; z < 5; z++)
            for (int y = 0; y <= 12; y++)
                level.setBlock(base.offset(x, y, z),
                        Blocks.AIR.defaultBlockState(), Block.UPDATE_CLIENTS);
        var data = VillageSavedData.get(level);
        var village = data.createVillage(base, level.getGameTime());
        var original = data.createProject(village.id(), "building", 75, base);
        original.setTemplateId("house_2story_5x5");
        original.setParameter("plank", "oak");
        original.setParameter("outpost", "false");
        original.setParameter("lead_skill", "100");
        original.setVariantSeed(13L);
        original.setPhase("complete");

        List<VillageSimulationEvents.BuildStep> blueprint =
                VillageSimulationEvents.projectPlan(original);
        // The foundation and both physical floors precede beds, so place all
        // supports first and actual two-half beds after the room is standing.
        for (var step : blueprint) {
            if (step.state().getBlock() instanceof BedBlock) continue;
            if (!step.state().isAir())
                level.setBlock(step.pos(), step.state(), Block.UPDATE_CLIENTS);
        }
        for (var step : blueprint) {
            if (step.state().getBlock() instanceof BedBlock)
                level.setBlock(step.pos(), step.state(), Block.UPDATE_CLIENTS);
        }
        level.updateNeighborsAt(base.offset(2, 1, 2), Blocks.WHITE_BED);
        level.updateNeighborsAt(base.offset(1, 5, 2), Blocks.WHITE_BED);

        for (int x = 0; x < 5; x++) for (int z = 0; z < 5; z++)
            for (int y = 9; y <= 13; y++)
                level.setBlock(base.offset(x, y, z),
                        Blocks.AIR.defaultBlockState(), Block.UPDATE_CLIENTS);

        var house = data.createBuilding(village.id(), base, base.offset(4, 8, 4), true);
        house.setClassification("residential");
        house.setTemplateId("house_2story_5x5");
        house.setValidationState("valid");
        house.setValidatedCapacity(4);
        // Keep the material Barrel OUTSIDE the completed house. Placing it
        // at (3,1,1) blocked the only standing cell beside a real ground bed,
        // erroneously removing valid housing capacity from the fixture.
        var storePos = base.offset(5, 1, 1);
        level.setBlock(storePos.below(), Blocks.COBBLESTONE.defaultBlockState(),
                Block.UPDATE_ALL);
        level.setBlock(storePos, Blocks.BARREL.defaultBlockState(), Block.UPDATE_ALL);
        var savedStore = data.createStorage(village.id(), storePos, "construction");
        savedStore.setValidationState("valid");
        if (!(level.getBlockEntity(storePos) instanceof Container storage))
            throw new IllegalStateException("Third-storey GameTest missing real Barrel");
        storage.setItem(0, new ItemStack(Items.OAK_PLANKS, 64));
        storage.setItem(1, new ItemStack(Items.OAK_PLANKS, 64));
        storage.setItem(2, new ItemStack(Items.OAK_STAIRS, 4));
        storage.setItem(3, new ItemStack(Items.WHITE_BED, 2));

        Villager worker = EntityType.VILLAGER.create(level);
        if (worker == null) throw new IllegalStateException("Third-storey worker factory failed");
        worker.setPos(base.getX() + 2.5D, base.getY() + 2,
                base.getZ() + 0.5D);
        worker.setNoAi(true);
        if (!level.addFreshEntity(worker)) throw new IllegalStateException("Worker spawn failed");
        VillagerSimData.setVillageId(worker, village.id());
        VillagerSimData.setDuty(worker, "carpenter", level.getGameTime());
        VillagerSimData.setCarpentrySkill(worker, 90);
        VillageStorageService.reconcileVillage(village.id(), level);
        return new Fixture(level, data, village, original, house, worker, storage, base);
    }

    private static int count(Container storage, net.minecraft.world.item.Item item) {
        int total = 0;
        for (int i = 0; i < storage.getContainerSize(); i++)
            if (storage.getItem(i).is(item)) total += storage.getItem(i).getCount();
        return total;
    }

    private record Fixture(ServerLevel level, VillageSavedData data,
                           VillageSavedData.VillageRecord village,
                           VillageSavedData.ProjectRecord original,
                           VillageSavedData.BuildingRecord house,
                           Villager builder, Container storage, BlockPos base) {
        UUID villageId() { return village.id(); }
    }
}
