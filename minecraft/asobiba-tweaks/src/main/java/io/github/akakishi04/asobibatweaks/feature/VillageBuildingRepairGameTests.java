package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaks;
import net.minecraft.core.BlockPos;
import net.minecraft.gametest.framework.GameTest;
import net.minecraft.gametest.framework.GameTestHelper;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.tags.BlockTags;
import net.minecraft.world.Container;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.npc.Villager;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.level.block.Blocks;
import net.neoforged.neoforge.gametest.GameTestHolder;
import net.neoforged.neoforge.gametest.PrefixGameTestTemplate;

/** Physical village-owned shell repair without block duplication or bulldozing. */
@GameTestHolder(AsobibaTweaks.MOD_ID)
@PrefixGameTestTemplate(false)
public final class VillageBuildingRepairGameTests {
    private VillageBuildingRepairGameTests() {}

    @GameTest(template = "empty16x6x9", batch = "village_shell_repair_1", timeoutTicks = 80)
    public static void repairsOnlyMissingVillageBlockForOneRealPlank(GameTestHelper helper) {
        Fixture sample = prepare(helper);
        helper.runAtTickTime(4, () -> {
            if (!VillageBuildingRepairService.tryPlan(
                    sample.builder(), sample.level(), sample.building().villageId())) {
                helper.fail("One missing village-owned roof plank must produce a repair project",
                        new BlockPos(7, 5, 4));
                return;
            }
            VillageSavedData.ProjectRecord repair = activeRepair(sample);
            if (repair == null || repair.workCursor() != 0
                    || repair.reservations().getOrDefault(
                            VillageStorageService.itemKey(Items.OAK_PLANKS), 0) != 1) {
                helper.fail("Repair must persist one exact outstanding block and material",
                        new BlockPos(7, 5, 4));
                return;
            }
            VillageBuildingRepairService.advance(sample.builder(), sample.level(), repair);
            if (!sample.level().getBlockState(sample.hole()).is(Blocks.OAK_PLANKS)
                    || sample.stock().getItem(0).getCount() != 3
                    || !"complete".equals(repair.phase())
                    || !repair.reservations().isEmpty()) {
                helper.fail("One physical plank must repair one existing roof hole, with no duplicates",
                        new BlockPos(7, 5, 4));
                return;
            }
            CompoundTag encoded = sample.data().save(new CompoundTag(),
                    sample.level().registryAccess());
            VillageSavedData decoded = VillageSavedData.load(
                    encoded, sample.level().registryAccess());
            if (!"complete".equals(decoded.project(repair.id()).orElseThrow().phase())
                    || !decoded.project(repair.id()).orElseThrow().reservations().isEmpty()) {
                helper.fail("Repair project cursor/completion was not persisted",
                        new BlockPos(7, 5, 4));
                return;
            }
            helper.succeed();
        });
    }

    @GameTest(template = "empty16x6x9", batch = "village_shell_repair_2", timeoutTicks = 80)
    public static void neverOverwritesPlayerReplacementOrChargesMaterial(GameTestHelper helper) {
        Fixture sample = prepare(helper);
        helper.runAtTickTime(4, () -> {
            if (!VillageBuildingRepairService.tryPlan(
                    sample.builder(), sample.level(), sample.building().villageId())) {
                helper.fail("Test village structure did not plan its initial roof repair",
                        new BlockPos(7, 5, 4));
                return;
            }
            VillageSavedData.ProjectRecord repair = activeRepair(sample);
            if (repair == null) {
                helper.fail("Required shell repair was not persisted",
                        new BlockPos(7, 5, 4));
                return;
            }
            // A player edits that site while the Carpenter is travelling.
            sample.level().setBlock(sample.hole(), Blocks.GLASS.defaultBlockState(), 3);
            VillageBuildingRepairService.advance(sample.builder(), sample.level(), repair);
            if (!sample.level().getBlockState(sample.hole()).is(Blocks.GLASS)
                    || sample.stock().getItem(0).getCount() != 4
                    || !"complete".equals(repair.phase())) {
                helper.fail("Repair destroyed a newer player block or consumed an unplaced plank",
                        new BlockPos(7, 5, 4));
                return;
            }
            helper.succeed();
        });
    }


    /**
     * A physically distant repair roof must never summon an empty Carpenter
     * away from its recognized real ground-floor building material Barrel.
     */
    @GameTest(template = "empty16x6x9", batch = "repair_material_preflight",
            timeoutTicks = 80)
    public static void carpenterPaysOnePlankBeforeTravelingToDistantRoof(
            GameTestHelper helper) {
        // Put the real Barrel at the far western side of the loaded test
        // structure so the genuine missing roof plank lies >7 blocks away.
        Fixture sample = prepare(helper, -5);
        helper.runAtTickTime(4, () -> {
            if (!VillageBuildingRepairService.tryPlan(
                    sample.builder(), sample.level(), sample.building().villageId())) {
                helper.fail("Distant physical roof hole must schedule a repair",
                        new BlockPos(7, 5, 4));
                return;
            }
            VillageSavedData.ProjectRecord repair = activeRepair(sample);
            if (repair == null) {
                helper.fail("No persistent roof repair project", new BlockPos(7, 5, 4));
                return;
            }
            VillageBuildingRepairService.advance(
                    sample.builder(), sample.level(), repair);
            if (repair.workCursor() != 0
                    || !sample.level().getBlockState(sample.hole()).isAir()
                    || sample.stock().getItem(0).getCount() != 3
                    || VillagerSimData.workCargoCount(sample.builder(),
                        sample.level().registryAccess(), 8, Items.OAK_PLANKS) != 1) {
                helper.fail("Carpenter navigated to roof before loading a real plank",
                        new BlockPos(7, 5, 4));
                return;
            }

            // Emulate completion of ONLY the travel leg; the same physical
            // cargo must be paid at the real upper roof work position once.
            sample.builder().setPos(sample.hole().getX() + 0.5D,
                    sample.hole().getY(), sample.hole().getZ() + 0.5D);
            VillageBuildingRepairService.advance(
                    sample.builder(), sample.level(), repair);
            if (!sample.level().getBlockState(sample.hole()).is(Blocks.OAK_PLANKS)
                    || sample.stock().getItem(0).getCount() != 3
                    || VillagerSimData.hasWorkCargo(
                        sample.builder(), sample.level().registryAccess(), 8)
                    || !"complete".equals(repair.phase())
                    || !repair.reservations().isEmpty()) {
                helper.fail("Paid roof repair lost or duplicated real Carpenter cargo",
                        new BlockPos(7, 5, 4));
                return;
            }
            helper.succeed();
        });
    }

    private static Fixture prepare(GameTestHelper helper) {
        return prepare(helper, 2);
    }

    private static Fixture prepare(GameTestHelper helper, int warehouseX) {
        ServerLevel level = helper.getLevel();
        BlockPos base = helper.absolutePos(new BlockPos(5, 1, 2));
        VillageSavedData data = VillageSavedData.get(level);
        VillageSavedData.VillageRecord village =
                data.createVillage(base, level.getGameTime());
        VillageSavedData.ProjectRecord source = data.createProject(
                village.id(), "building", 70, base);
        source.setTemplateId("house_5x5");
        source.setVariantSeed(25);
        source.setParameter("plank", "oak");
        source.setParameter("lead_skill", "100");
        source.setPhase("complete");

        // Rebuild the exact original shell as real world blocks (no mock
        // structure values), then remove precisely one roof plank.
        for (var step : VillageSimulationEvents.projectPlan(source)) {
            if (step.cost() == null) continue;
            if (step.state().is(Blocks.COBBLESTONE) || step.state().is(BlockTags.PLANKS)) {
                level.setBlock(step.pos(), step.state(), 3);
            }
        }
        BlockPos hole = base.offset(2, 4, 2);
        level.setBlock(hole, Blocks.AIR.defaultBlockState(), 3);
        VillageSavedData.BuildingRecord building = data.createBuilding(
                village.id(), base, base.offset(4, 4, 4), true);
        building.setTemplateId("house_5x5");
        building.setClassification("residential");
        building.setValidationState("invalid");
        building.setValidatedCapacity(0);

        BlockPos supply = base.offset(warehouseX, 1, 1);
        level.setBlock(supply, Blocks.BARREL.defaultBlockState(), 3);
        VillageSavedData.StorageRecord storage =
                data.createStorage(village.id(), supply, "construction");
        storage.setValidationState("valid");
        if (!(level.getBlockEntity(supply) instanceof Container barrel))
            throw new IllegalStateException("Repair materials Barrel did not spawn");
        barrel.setItem(0, new ItemStack(Items.OAK_PLANKS, 4));

        Villager builder = EntityType.VILLAGER.create(level);
        if (builder == null) throw new IllegalStateException("Cannot create real Carpenter");
        if (warehouseX == 2) {
            builder.setPos(base.getX() + 2.5D, base.getY() + 2.0D, base.getZ() + 2.5D);
        } else {
            builder.setPos(supply.getX() + 0.5D, base.getY() + 2.0D,
                    supply.getZ() + 0.5D);
        }
        builder.setNoAi(true);
        if (!level.addFreshEntity(builder)) throw new IllegalStateException("Cannot spawn Carpenter");
        VillagerSimData.setVillageId(builder, village.id());
        VillagerSimData.setDuty(builder, "carpenter", level.getGameTime());
        VillageStorageService.reconcileVillage(village.id(), level);
        return new Fixture(level, data, building, builder, barrel, hole);
    }

    private static VillageSavedData.ProjectRecord activeRepair(Fixture sample) {
        return sample.data().activeProjectsForVillage(sample.building().villageId())
                .stream().filter(p -> VillageBuildingRepairService.TEMPLATE.equals(p.templateId()))
                .findFirst().orElse(null);
    }

    private record Fixture(ServerLevel level, VillageSavedData data,
                           VillageSavedData.BuildingRecord building,
                           Villager builder, Container stock, BlockPos hole) {}
}
