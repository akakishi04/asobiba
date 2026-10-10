package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaks;
import java.util.List;
import java.util.UUID;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
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
import net.minecraft.world.level.block.HorizontalDirectionalBlock;
import net.neoforged.neoforge.gametest.GameTestHolder;
import net.neoforged.neoforge.gametest.PrefixGameTestTemplate;

/** Durable, physical repair of missing staircase treads in real village homes. */
@GameTestHolder(AsobibaTweaks.MOD_ID)
@PrefixGameTestTemplate(false)
public final class VillageStairRepairGameTests {
    private static final BlockPos MARK = new BlockPos(8, 5, 4);
    private VillageStairRepairGameTests() {}

    @GameTest(template = "empty16x14x9", timeoutTicks = 100,
            batch = "village_stair_repair_1")
    public static void missingSecondStoreyStairCostsOneRealItemAndRestoresRoute(
            GameTestHelper helper) {
        Fixture f = setup(helper, 2);
        BlockPos missing = f.base().offset(2, 2, 1);
        f.level().setBlock(missing, Blocks.AIR.defaultBlockState(), Block.UPDATE_ALL);
        helper.runAtTickTime(4, () -> {
            if (!VillageStairRepairService.tryPlan(
                    f.builder(), f.level(), f.villageId())) {
                helper.fail("Real missing two-storey tread did not schedule a repair", MARK);
                return;
            }
            var repair = active(f);
            if (repair == null || !"stair_repair".equals(repair.phase())
                    || repair.reservations().getOrDefault("minecraft:oak_stairs", 0) != 1
                    || VillageBuildingService.connectedUpperStories(f.level(), f.base(), 1)) {
                helper.fail("Missing stair was counted as connected or did not reserve one item", MARK);
                return;
            }
            VillageStairRepairService.advance(f.builder(), f.level(), repair);
            if (!"complete".equals(repair.phase())
                    || !f.level().getBlockState(missing).is(Blocks.OAK_STAIRS)
                    || f.level().getBlockState(missing)
                            .getValue(HorizontalDirectionalBlock.FACING) != Direction.EAST
                    || count(f.storage(), Items.OAK_STAIRS) != 3
                    || !VillageBuildingService.connectedUpperStories(f.level(), f.base(), 1)
                    || f.village().buildingIds().size() != 1) {
                helper.fail("Actual paid stair was not restored with correct facing", MARK);
                return;
            }

            // A lagging project cursor must never buy a second identical item.
            repair.setWorkCursor(0);
            repair.setPhase("stair_repair");
            VillageStairRepairService.advance(f.builder(), f.level(), repair);
            var restored = VillageSavedData.load(
                    f.data().save(new CompoundTag(), f.level().registryAccess()),
                    f.level().registryAccess());
            if (repair.workCursor() != 1 || count(f.storage(), Items.OAK_STAIRS) != 3
                    || restored.building(f.home().id()).isEmpty()
                    || !"complete".equals(restored.project(repair.id()).orElseThrow().phase())) {
                helper.fail("Saved stair identity or idempotent cursor reconciliation failed", MARK);
                return;
            }
            helper.succeed();
        });
    }

    @GameTest(template = "empty16x14x9", timeoutTicks = 70,
            batch = "village_stair_repair_2")
    public static void playerRotatedStairCannotBeOverwrittenEvenWithMissingNeighbor(
            GameTestHelper helper) {
        Fixture f = setup(helper, 2);
        BlockPos missing = f.base().offset(1, 1, 1);
        BlockPos rotated = f.base().offset(2, 2, 1);
        f.level().setBlock(missing, Blocks.AIR.defaultBlockState(), Block.UPDATE_ALL);
        f.level().setBlock(rotated, Blocks.OAK_STAIRS.defaultBlockState()
                .setValue(HorizontalDirectionalBlock.FACING, Direction.NORTH), Block.UPDATE_ALL);
        helper.runAtTickTime(4, () -> {
            if (VillageStairRepairService.tryPlan(
                    f.builder(), f.level(), f.villageId())
                    || !f.data().activeProjectsForVillage(f.villageId()).isEmpty()
                    || !f.level().getBlockState(missing).isAir()
                    || f.level().getBlockState(rotated)
                            .getValue(HorizontalDirectionalBlock.FACING) != Direction.NORTH
                    || count(f.storage(), Items.OAK_STAIRS) != 4) {
                helper.fail("Player-rotated stair must veto uncontrolled reconstruction", MARK);
                return;
            }
            helper.succeed();
        });
    }

    @GameTest(template = "empty16x14x9", timeoutTicks = 110,
            batch = "village_stair_repair_3")
    public static void threeStoreyRepairCarriesRealStairUpstairsAndRestoresBedAccess(
            GameTestHelper helper) {
        Fixture f = setup(helper, 3);
        BlockPos missing = f.base().offset(2, 6, 1);
        f.level().setBlock(missing, Blocks.AIR.defaultBlockState(), Block.UPDATE_ALL);
        helper.runAtTickTime(4, () -> {
            if (!VillageStairRepairService.tryPlan(
                    f.builder(), f.level(), f.villageId())) {
                helper.fail("Third-storey original route did not detect missing upper tread", MARK);
                return;
            }
            var repair = active(f);
            // Near the actual ground-floor Barrel but far from the upper tread.
            f.builder().setPos(f.base().getX() + 5.5D,
                    f.base().getY() - 1.0D, f.base().getZ() + 1.5D);
            VillageStairRepairService.advance(f.builder(), f.level(), repair);
            if (repair.workCursor() != 0
                    || VillagerSimData.workCargoCount(
                            f.builder(), f.level().registryAccess(), 8, Items.OAK_STAIRS) != 1
                    || count(f.storage(), Items.OAK_STAIRS) != 3) {
                helper.fail("Worker failed to carry the real Stair before climbing upstairs", MARK);
                return;
            }
            f.builder().setPos(missing.getX() + 0.5D,
                    missing.getY() + 0.8D, missing.getZ() + 0.5D);
            VillageStairRepairService.advance(f.builder(), f.level(), repair);
            if (!"complete".equals(repair.phase())
                    || VillagerSimData.hasWorkCargo(f.builder(), f.level().registryAccess(), 8)
                    || count(f.storage(), Items.OAK_STAIRS) != 3
                    || !VillageBuildingService.connectedUpperStories(f.level(), f.base(), 2)) {
                helper.fail("Real third-floor stair was not actually delivered or connected", MARK);
                return;
            }
            helper.runAtTickTime(32, () -> {
                VillageBuildingService.revalidateChunk(f.level(), new ChunkPos(f.base()));
                if (f.home().validatedCapacity() != 4
                        || !"valid".equals(f.home().validationState())) {
                    helper.fail("Five real upper/lower beds were not revalidated", MARK);
                    return;
                }
                helper.succeed();
            });
        });
    }

    private static Fixture setup(GameTestHelper helper, int floors) {
        ServerLevel level = helper.getLevel();
        BlockPos base = helper.absolutePos(new BlockPos(5, 1, 2));
        VillageSavedData data = VillageSavedData.get(level);
        var village = data.createVillage(base, level.getGameTime());
        var source = data.createProject(village.id(), "building", 75, base);
        source.setTemplateId(floors == 3 ? "house_3story_5x5" : "house_2story_5x5");
        source.setParameter("circulation_version", "2");
        source.setParameter("plank", "oak");
        source.setParameter("lead_skill", "100");
        source.setParameter("outpost", "false");
        source.setVariantSeed(13L);
        source.setPhase("complete");

        List<VillageSimulationEvents.BuildStep> blueprint =
                VillageSimulationEvents.projectPlan(source);
        for (var step : blueprint) {
            if (!(step.state().getBlock() instanceof BedBlock) && !step.state().isAir()) {
                level.setBlock(step.pos(), step.state(), Block.UPDATE_CLIENTS);
            }
        }
        for (var step : blueprint) {
            if (step.state().getBlock() instanceof BedBlock) {
                level.setBlock(step.pos(), step.state(), Block.UPDATE_CLIENTS);
            }
        }
        level.updateNeighborsAt(base.offset(2, 1, 2), Blocks.WHITE_BED);
        level.updateNeighborsAt(base.offset(1, 5, 2), Blocks.WHITE_BED);

        var home = data.createBuilding(village.id(), base,
                base.offset(4, floors == 3 ? 12 : 8, 4), true);
        home.setTemplateId(source.templateId());
        home.setClassification("residential");
        home.setValidationState("valid");
        home.setValidatedCapacity(floors == 3 ? 4 : 3);
        BlockPos stock = base.offset(5, 1, 0);
        level.setBlock(stock.below(), Blocks.COBBLESTONE.defaultBlockState(), Block.UPDATE_ALL);
        level.setBlock(base.offset(5, 0, 1), Blocks.COBBLESTONE.defaultBlockState(), Block.UPDATE_ALL);
        level.setBlock(stock, Blocks.BARREL.defaultBlockState(), Block.UPDATE_ALL);
        var stored = data.createStorage(village.id(), stock, "construction");
        stored.setValidationState("valid");
        if (!(level.getBlockEntity(stock) instanceof Container contents)) {
            throw new IllegalStateException("Stair repair fixture needs a real Barrel");
        }
        contents.setItem(0, new ItemStack(Items.OAK_STAIRS, 4));
        VillageStorageService.reconcileVillage(village.id(), level);
        Villager worker = EntityType.VILLAGER.create(level);
        if (worker == null) throw new IllegalStateException("Stair repair builder factory failed");
        worker.setPos(base.getX() + 5.5D, base.getY() + 1.0D,
                base.getZ() + 1.5D);
        worker.setNoAi(true);
        if (!level.addFreshEntity(worker)) throw new IllegalStateException("Carpenter spawn failed");
        VillagerSimData.setVillageId(worker, village.id());
        VillagerSimData.setDuty(worker, "carpenter", level.getGameTime());
        VillagerSimData.setCarpentrySkill(worker, 90);
        data.touch();
        return new Fixture(level, data, village, home, worker, contents, base);
    }

    private static VillageSavedData.ProjectRecord active(Fixture f) {
        return f.data().activeProjectsForVillage(f.villageId()).stream()
                .filter(p -> VillageStairRepairService.TEMPLATE.equals(p.templateId()))
                .findFirst().orElse(null);
    }

    private static int count(Container store, net.minecraft.world.item.Item item) {
        int amount = 0;
        for (int slot = 0; slot < store.getContainerSize(); slot++) {
            if (store.getItem(slot).is(item)) amount += store.getItem(slot).getCount();
        }
        return amount;
    }

    private record Fixture(ServerLevel level, VillageSavedData data,
                           VillageSavedData.VillageRecord village,
                           VillageSavedData.BuildingRecord home,
                           Villager builder, Container storage, BlockPos base) {
        UUID villageId() { return village.id(); }
    }
}
