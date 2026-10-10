package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaks;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.gametest.framework.GameTest;
import net.minecraft.gametest.framework.GameTestHelper;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.item.ItemEntity;
import net.minecraft.world.entity.npc.Villager;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.level.block.BedBlock;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.properties.BedPart;
import net.minecraft.world.phys.AABB;
import net.neoforged.neoforge.gametest.GameTestHolder;
import net.neoforged.neoforge.gametest.PrefixGameTestTemplate;

@GameTestHolder(AsobibaTweaks.MOD_ID)
@PrefixGameTestTemplate(false)
public final class VillageHouseCirculationGameTests {
    private VillageHouseCirculationGameTests() {}

    @GameTest(template = "empty16x14x9", timeoutTicks = 80, batch = "house_circulation_materials")
    public static void legacyBedsMoveWithConservedRealMaterials(GameTestHelper helper) {
        Fixture f = setup(helper, 2, false);
        ItemEntity unrelated = new ItemEntity(f.level(), f.base().getX() + 2.5,
                f.base().getY() + 1, f.base().getZ() + 2.5, new ItemStack(Items.WHITE_BED, 7));
        f.level().addFreshEntity(unrelated);
        helper.runAtTickTime(2, () -> {
            finish(helper, f, f.source());
            helper.assertTrue("true".equals(f.source().parameter(VillageHouseCirculationService.VERIFIED)), "Physical migration not verified");
            helper.assertTrue(beds(f) == 3, "Expected three usable physical beds");
            helper.assertTrue(VillagerSimData.workCargoCount(f.worker(), f.level().registryAccess(), 8, Items.WHITE_BED) == 1,
                    "Four real old beds must become three beds plus one real spare");
            helper.assertTrue(unrelated.isAlive() && unrelated.getItem().getCount() == 7, "Player drop was collected");
            helper.assertTrue(f.source().workCursor() == f.originalCursor(), "Raw construction cursor was reinterpreted");
            helper.succeed();
        });
    }

    @GameTest(template = "empty16x14x9", timeoutTicks = 80, batch = "house_circulation_player")
    public static void playerEditedOwnedPlankPausesBeforeAnyDemolition(GameTestHelper helper) {
        Fixture f = setup(helper, 2, false);
        BlockPos edited = f.base().offset(4, 1, 1);
        f.level().setBlock(edited, Blocks.DIAMOND_BLOCK.defaultBlockState(), Block.UPDATE_CLIENTS);
        helper.runAtTickTime(2, () -> {
            helper.assertTrue(!VillageHouseCirculationService.ensure(f.worker(), f.level(), f.source()), "Player edit permitted migration");
            helper.assertTrue(f.level().getBlockState(edited).is(Blocks.DIAMOND_BLOCK) && beds(f) == 4,
                    "Player block or original beds were demolished");
            helper.assertTrue(f.source().parameter(VillageHouseCirculationService.CURSOR).isEmpty(), "Blocked migration advanced cursor");
            helper.succeed();
        });
    }

    @GameTest(template = "empty16x14x9", timeoutTicks = 80, batch = "house_circulation_replay")
    public static void savedMigrationCursorAndLaggingRemovalReplayConserveBeds(GameTestHelper helper) {
        Fixture f = setup(helper, 3, false);
        helper.runAtTickTime(2, () -> {
            for (int i = 0; i < 12 && VillagerSimData.workCargoCount(f.worker(), f.level().registryAccess(), 8, Items.WHITE_BED) == 0; i++)
                VillageHouseCirculationService.ensure(f.worker(), f.level(), f.source());
            int paidItems = VillagerSimData.workCargoCount(f.worker(), f.level().registryAccess(), 8, Items.WHITE_BED);
            helper.assertTrue(paidItems == 1, "First old bed did not produce exactly one real item");
            int savedCursor = Integer.parseInt(f.source().parameter(VillageHouseCirculationService.CURSOR));
            f.source().setParameter(VillageHouseCirculationService.CURSOR, Integer.toString(savedCursor - 1));
            var loaded = VillageSavedData.load(f.data().save(new CompoundTag(), f.level().registryAccess()), f.level().registryAccess());
            var restored = loaded.project(f.source().id()).orElseThrow();
            helper.assertTrue(restored.workCursor() == f.originalCursor(), "NBT lost the independent original cursor");
            VillageHouseCirculationService.ensure(f.worker(), f.level(), restored);
            helper.assertTrue(VillagerSimData.workCargoCount(f.worker(), f.level().registryAccess(), 8, Items.WHITE_BED) == paidItems,
                    "Lagging removal replay duplicated a real bed");
            finish(helper, f, restored);
            helper.assertTrue(beds(f) == 4 && VillagerSimData.workCargoCount(f.worker(), f.level().registryAccess(), 8, Items.WHITE_BED) == 1,
                    "Saved third-storey migration failed conservation");
            helper.assertTrue(restored.workCursor() == f.originalCursor(), "Resumed migration changed source cursor");
            helper.succeed();
        });
    }

    @GameTest(template = "empty16x14x9", timeoutTicks = 80, batch = "house_circulation_identity")
    public static void completedHouseRetrofitPreservesBuildingId(GameTestHelper helper) {
        Fixture f = setup(helper, 2, false);
        helper.runAtTickTime(2, () -> {
            helper.assertTrue(VillageHouseCirculationService.tryPlan(f.worker(), f.level(), f.source().villageId()), "Original legacy house not queued");
            var retrofit = f.data().activeProjectsForVillage(f.source().villageId()).stream()
                    .filter(p -> VillageHouseCirculationService.TEMPLATE.equals(p.templateId())).findFirst().orElseThrow();
            for (int i = 0; i < 30 && !"complete".equals(retrofit.phase()); i++)
                VillageHouseCirculationService.advance(f.worker(), f.level(), retrofit);
            helper.assertTrue("complete".equals(retrofit.phase()), "Same-ID retrofit failed: " + retrofit.pausedReason());
            helper.assertTrue(f.data().building(f.home().id()).orElseThrow() == f.home()
                    && f.data().village(f.source().villageId()).orElseThrow().buildingIds().size() == 1, "Retrofit replaced building identity");
            helper.assertTrue(!VillageHouseCirculationService.tryPlan(f.worker(), f.level(), f.source().villageId()), "Verified home queued again");
            helper.succeed();
        });
    }

    @GameTest(template = "empty16x14x9", timeoutTicks = 80, batch = "house_circulation_v2")
    public static void nativeV2HouseVerifiesWithoutDemolitionOrPayment(GameTestHelper helper) {
        Fixture f = setup(helper, 3, true);
        helper.runAtTickTime(2, () -> {
            helper.assertTrue(VillageHouseCirculationService.ensure(f.worker(), f.level(), f.source()), "Native v2 should verify immediately: " + f.source().pausedReason());
            helper.assertTrue(beds(f) == 4 && f.source().parameter(VillageHouseCirculationService.CURSOR).isEmpty(), "Native v2 was unnecessarily migrated");
            helper.assertTrue(f.level().getEntitiesOfClass(ItemEntity.class, new AABB(f.base()).expandTowards(5, 13, 5)).isEmpty(), "Native v2 dropped materials");
            helper.succeed();
        });
    }

    @GameTest(template = "empty16x14x9", timeoutTicks = 80, batch = "house_circulation_adopted")
    public static void adoptedHouseIsNeverOfferedCirculationRetrofit(GameTestHelper helper) {
        Fixture f = setup(helper, 2, false);
        // No original source in the adopted village, even if an arbitrary home
        // happens to have the same familiar template and physical dimensions.
        var other = f.data().createVillage(f.base().offset(20, 0, 0), f.level().getGameTime());
        var adopted = f.data().createBuilding(other.id(), f.base(), f.base().offset(4, 8, 4), false);
        adopted.setTemplateId("house_2story_5x5");
        adopted.setClassification("residential");
        helper.assertTrue(!VillageHouseCirculationService.tryPlan(f.worker(), f.level(), other.id()), "Adopted arbitrary house queued");
        helper.succeed();
    }

    @GameTest(template = "empty16x14x9", timeoutTicks = 80, batch = "house_circulation_damage")
    public static void lostPaidBedCannotBeRecreatedByCursorReplay(GameTestHelper helper) {
        Fixture f = setup(helper, 2, false);
        helper.runAtTickTime(2, () -> {
            finish(helper, f, f.source());
            BlockPos foot = f.base().offset(1, 1, 3);
            f.level().destroyBlock(foot, true, f.worker());
            int before = VillagerSimData.workCargoCount(f.worker(), f.level().registryAccess(), 8, Items.WHITE_BED);
            helper.assertTrue(!VillageHouseCirculationService.ensure(f.worker(), f.level(), f.source()), "Verified broken bed silently regenerated");
            helper.assertTrue(f.level().getBlockState(foot).isAir(), "Lost physical bed recreated from old payment");
            // Explicitly simulate a lagging migration record. Only a new real
            // spare item can pay for the now-missing placement.
            f.source().setParameter(VillageHouseCirculationService.VERIFIED, "");
            f.source().setParameter(VillageHouseCirculationService.CURSOR, "0");
            finish(helper, f, f.source());
            helper.assertTrue(VillagerSimData.workCargoCount(f.worker(), f.level().registryAccess(), 8, Items.WHITE_BED) == before - 1,
                    "Cursor replay reused a spent Bed entitlement");
            helper.succeed();
        });
    }

    @GameTest(template = "empty16x14x9", timeoutTicks = 80, batch = "house_circulation_shell_repair")
    public static void legacyShellRepairKeepsVerifiedDoorwayAndHeadroomOpen(GameTestHelper helper) {
        Fixture f = setup(helper, 2, false);
        helper.runAtTickTime(2, () -> {
            finish(helper, f, f.source());
            BlockPos damaged = f.base().offset(0, 2, 0);
            f.level().setBlock(damaged, Blocks.AIR.defaultBlockState(), Block.UPDATE_CLIENTS);
            VillagerSimData.insertWorkCargo(f.worker(), f.level().registryAccess(), new ItemStack(Items.OAK_PLANKS, 8), 8);
            helper.assertTrue(VillageBuildingRepairService.tryPlan(f.worker(), f.level(), f.source().villageId()), "Missing original wall not scheduled");
            var repair = f.data().activeProjectsForVillage(f.source().villageId()).stream()
                    .filter(p -> VillageBuildingRepairService.TEMPLATE.equals(p.templateId())).findFirst().orElseThrow();
            helper.assertTrue(repair.reservations().getOrDefault("minecraft:oak_planks", 0) == 1,
                    "Repair incorrectly billed deliberate circulation openings");
            for (int i = 0; i < 16 && !"complete".equals(repair.phase()); i++) VillageBuildingRepairService.advance(f.worker(), f.level(), repair);
            helper.assertTrue("complete".equals(repair.phase()) && f.level().getBlockState(damaged).is(Blocks.OAK_PLANKS),
                    "Paid original wall repair failed: " + repair.pausedReason());
            helper.assertTrue(f.level().getBlockState(f.base().offset(4, 1, 1)).isAir()
                    && f.level().getBlockState(f.base().offset(4, 2, 1)).isAir()
                    && f.level().getBlockState(f.base().offset(2, 4, 1)).isAir(), "Shell repair sealed circulation openings");
            helper.assertTrue(VillageHouseCirculationService.ensure(f.worker(), f.level(), f.source()), "Repaired shell no longer verifies");
            helper.succeed();
        });
    }

    private static void finish(GameTestHelper helper, Fixture f, VillageSavedData.ProjectRecord source) {
        for (int i = 0; i < 30; i++) if (VillageHouseCirculationService.ensure(f.worker(), f.level(), source)) return;
        helper.fail("Migration did not finish: " + source.pausedReason());
    }
    private static int beds(Fixture f) {
        int result = 0;
        for (BlockPos pos : BlockPos.betweenClosed(f.base(), f.base().offset(4, 12, 4))) {
            var state = f.level().getBlockState(pos);
            if (state.is(Blocks.WHITE_BED) && state.getValue(BedBlock.PART) == BedPart.FOOT) result++;
        }
        return result;
    }
    private static Fixture setup(GameTestHelper helper, int floors, boolean v2) {
        ServerLevel level = helper.getLevel();
        BlockPos base = helper.absolutePos(new BlockPos(5, 1, 2));
        VillageSavedData data = VillageSavedData.get(level);
        var village = data.createVillage(base, level.getGameTime());
        var source = data.createProject(village.id(), "building", 75, base);
        source.setTemplateId(floors == 3 ? "house_3story_5x5" : "house_2story_5x5");
        source.setParameter("plank", "oak");
        source.setParameter("lead_skill", "100");
        source.setVariantSeed(13L);
        if (v2) source.setParameter("circulation_version", "2");
        var plan = VillageSimulationEvents.projectPlan(source);
        for (var step : plan) if (!(step.state().getBlock() instanceof BedBlock)) level.setBlock(step.pos(), step.state(), Block.UPDATE_CLIENTS);
        for (var step : plan) if (step.state().getBlock() instanceof BedBlock) level.setBlock(step.pos(), step.state(), Block.UPDATE_CLIENTS);
        source.setWorkCursor(plan.size());
        source.setPhase("complete");
        var home = data.createBuilding(village.id(), base, base.offset(4, floors * 4, 4), true);
        home.setTemplateId(source.templateId());
        home.setClassification("residential");
        home.setValidationState("valid");
        home.setValidatedCapacity(floors == 3 ? 5 : 4);
        Villager worker = EntityType.VILLAGER.create(level);
        if (worker == null) throw new IllegalStateException("Missing carpenter");
        worker.setPos(base.getX() + 2.5, base.getY() + 5, base.getZ() + 2.5);
        worker.setNoAi(true);
        worker.setNoGravity(true);
        level.addFreshEntity(worker);
        VillagerSimData.setVillageId(worker, village.id());
        VillagerSimData.setDuty(worker, "carpenter", level.getGameTime());
        VillagerSimData.setCarpentrySkill(worker, 90);
        data.touch();
        return new Fixture(level, data, source, home, worker, base, plan.size());
    }
    private record Fixture(ServerLevel level, VillageSavedData data, VillageSavedData.ProjectRecord source,
            VillageSavedData.BuildingRecord home, Villager worker, BlockPos base, int originalCursor) {}
}
