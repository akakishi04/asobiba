package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaks;
import java.util.List;
import java.util.Set;
import java.util.UUID;
import net.minecraft.core.BlockPos;
import net.minecraft.gametest.framework.GameTest;
import net.minecraft.gametest.framework.GameTestHelper;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.world.level.ChunkPos;
import net.neoforged.neoforge.gametest.GameTestHolder;
import net.neoforged.neoforge.gametest.PrefixGameTestTemplate;

@GameTestHolder(AsobibaTweaks.MOD_ID)
@PrefixGameTestTemplate(false)
public final class VillageHistoryMaintenanceGameTests {
    private VillageHistoryMaintenanceGameTests() {}

    @GameTest(template = "empty16x6x9", batch = "history_maintenance")
    public static void trimsEphemeralHistoryButKeepsPhysicalBlueprintsAndActiveBills(GameTestHelper helper) {
        var data = new VillageSavedData();
        var village = data.createVillage(BlockPos.ZERO, 0L);
        UUID oldest = null;
        for (int i = 0; i < 100; i++) {
            var road = data.createProject(village.id(), "road", 1, BlockPos.ZERO);
            road.setPhase("complete"); if (oldest == null) oldest = road.id();
        }
        for (String template : List.of("house_5x5", "house_2story_5x5", "expand_house_second_floor_v1",
                "expand_house_third_floor_v1", "reuse_house_v1", "retrofit_house_circulation_v2")) {
            var blueprint = data.createProject(village.id(), "building", 1, BlockPos.ZERO);
            blueprint.setTemplateId(template); blueprint.setPhase("complete");
        }
        var building = data.createBuilding(village.id(), BlockPos.ZERO, new BlockPos(4, 4, 4), true);
        var active = data.createProject(village.id(), "building", 1, BlockPos.ZERO);
        active.setReservation("minecraft:stone", 32);
        var cancelled = data.createProject(village.id(), "road", 1, BlockPos.ZERO);
        cancelled.setReservation("minecraft:stone", 8); cancelled.setPhase("cancelled");
        helper.assertTrue(cancelled.reservations().isEmpty(), "Cancellation retained a material bill");
        data.compactTerminalHistory(village.id(), Set.of(), 64);
        helper.assertTrue(data.project(oldest).isEmpty()
                && !data.recordsForChunk(new ChunkPos(BlockPos.ZERO)).projectIds().contains(oldest), "History left stale project indexes");
        helper.assertTrue(village.projectIds().size() == 64 + 6 + 1
                && data.building(building.id()).isPresent() && active.reservations().get("minecraft:stone") == 32,
                "Compaction lost a blueprint, asset, or live reservation");
        helper.succeed();
    }

    @GameTest(template = "empty16x6x9", batch = "history_maintenance")
    public static void retainsReferencedJobsUnloadedOwnersAndOwnedConstructionMaterials(GameTestHelper helper) {
        var data = new VillageSavedData();
        var village = data.createVillage(BlockPos.ZERO, 0L);
        UUID absentResident = UUID.randomUUID(); data.registerResident(village.id(), absentResident);
        var referenced = data.createProject(village.id(), "road", 1, BlockPos.ZERO); referenced.setPhase("complete");
        var active = data.createProject(village.id(), "road", 1, BlockPos.ZERO);
        active.setParameter("bridge_project_id", referenced.id().toString());
        var owned = data.createProject(village.id(), "road", 1, BlockPos.ZERO); owned.setPhase("cancelled");
        owned.setLeadCarpenterId(absentResident);
        var scaffolding = data.createProject(village.id(), "building", 1, BlockPos.ZERO);
        scaffolding.setPhase("cancelled"); scaffolding.setParameter("access_ramp_height", "4");
        scaffolding.setParameter("access_ramp_placed", "3");
        var dock = data.createProject(village.id(), "generic", 1, BlockPos.ZERO); dock.setPhase("complete");
        var site = data.createWorkSite(village.id(), "dock", BlockPos.ZERO, new BlockPos(3, 3, 3));
        site.setPurpose("dock:" + dock.id());
        var migration = data.createMigration(village.id(), null, List.of(absentResident)); migration.setState("cancelled");
        var disposable = data.createProject(village.id(), "road", 1, BlockPos.ZERO); disposable.setPhase("cancelled");
        data.compactTerminalHistory(village.id(), Set.of(), 0);
        for (var retained : List.of(referenced, active, owned, scaffolding, dock))
            helper.assertTrue(data.project(retained.id()).isPresent(), "Live reference/ownership was lost");
        helper.assertTrue(data.project(disposable.id()).isEmpty() && village.residentIds().contains(absentResident)
                && data.migration(migration.id()).isPresent() && data.workSite(site.id()).isPresent(),
                "Unloaded resident, migration member, or physical site was garbage-collected");
        helper.succeed();
    }

    @GameTest(template = "empty16x6x9", batch = "history_maintenance")
    public static void requestHistoryIsBoundedAcrossReloadWhileActiveRequestSurvives(GameTestHelper helper) {
        var data = new VillageSavedData();
        var village = data.createVillage(BlockPos.ZERO, 0L);
        for (int i = 0; i < 100; i++) {
            data.upsertPublicRequest(village.id(), "request_" + i, "normal", "minecraft:stone", 1, 1, "test", "", null, i);
            data.closeInactivePublicRequests(village.id(), Set.of(), i);
        }
        var active = data.upsertPublicRequest(village.id(), "live", "high", "minecraft:stone", 4, 4,
                "real demand", "", null, 200L);
        data.compactTerminalHistory(village.id(), Set.of(), 64);
        CompoundTag saved = data.save(new CompoundTag(), helper.getLevel().registryAccess());
        helper.assertTrue(saved.getList("public_requests", 10).size() == 65, "Closed request history exceeded bound");
        var loaded = VillageSavedData.load(saved, helper.getLevel().registryAccess());
        helper.assertTrue(loaded.publicRequest(active.id()).isPresent()
                && loaded.publicRequestsForVillage(village.id()).size() == 1, "Active request was compacted");
        helper.succeed();
    }

    @GameTest(template = "empty16x6x9", batch = "history_maintenance")
    public static void trafficDecaysOnlyWithObservedTimeAndNeverConsumesCargoReceipts(GameTestHelper helper) {
        var data = new VillageSavedData();
        var village = data.createVillage(BlockPos.ZERO, 0L);
        var route = data.createRoute(village.id(), "waterway", BlockPos.ZERO, new BlockPos(80, 0, 0));
        UUID carrier = UUID.randomUUID(); route.setCarrierEntityId(carrier);
        route.recordDockDelivery(true, "minecraft:stone", 64); route.setTrafficScore(Integer.MAX_VALUE);
        helper.assertTrue(route.trafficScore() == 10_000, "Traffic statistic is unbounded");
        for (long tick = 0; tick <= 24_000; tick += 40) village.observeActive(tick);
        VillageHistoryMaintenance.decayTraffic(data, village);
        helper.assertTrue(route.trafficScore() < 10_000 && route.trafficScore() > 0
                && route.carrierEntityId().equals(carrier) && route.dockReceipts(true).get("minecraft:stone") == 64,
                "Statistic decay changed real cargo ownership");
        int score = route.trafficScore(); long active = village.activeObservedTicks();
        village.observeActive(10_000_000L); VillageHistoryMaintenance.decayTraffic(data, village);
        helper.assertTrue(village.activeObservedTicks() == active + 40L && route.trafficScore() == score,
                "Unobserved elapsed time created offline maintenance");
        helper.succeed();
    }

    @GameTest(template = "empty16x6x9", batch = "history_maintenance")
    public static void referenceIndexesRebuildAndReleaseAfterReload(GameTestHelper helper) {
        var data = new VillageSavedData();
        var village = data.createVillage(BlockPos.ZERO, 0L);
        var road = data.createProject(village.id(), "road", 1, BlockPos.ZERO); road.setPhase("complete");
        var owner = data.createProject(village.id(), "building", 1, BlockPos.ZERO);
        owner.setParameter("bridge_project_id", road.id().toString());
        var loaded = VillageSavedData.load(data.save(new CompoundTag(), helper.getLevel().registryAccess()),
                helper.getLevel().registryAccess());
        loaded.compactTerminalHistory(village.id(), Set.of(), 0);
        helper.assertTrue(loaded.project(road.id()).isPresent(), "Reload lost reverse project references");
        loaded.project(owner.id()).orElseThrow().setParameter("bridge_project_id", "");
        loaded.compactTerminalHistory(village.id(), Set.of(), 0);
        helper.assertTrue(loaded.project(road.id()).isEmpty(), "Cleared project reference permanently pinned history");
        helper.succeed();
    }

    @GameTest(template = "empty16x6x9", batch = "history_maintenance")
    public static void oversizedLegacyHistoryFailsClosedAndDoesNotBlockLocalRequests(GameTestHelper helper) {
        var data = new VillageSavedData();
        var village = data.createVillage(BlockPos.ZERO, 0L);
        for (int i = 0; i <= VillageHistoryMaintenance.MAX_RECORDS_PER_PASS; i++) {
            var project = data.createProject(village.id(), "road", 1, BlockPos.ZERO); project.setPhase("cancelled");
        }
        var request = data.upsertPublicRequest(village.id(), "done", "normal", "minecraft:stone", 1, 1,
                "", "", null, 0L);
        data.closeInactivePublicRequests(village.id(), Set.of(), 1L);
        data.compactTerminalHistory(village.id(), Set.of(), 0);
        helper.assertTrue(village.projectIds().size() == VillageHistoryMaintenance.MAX_RECORDS_PER_PASS + 1,
                "Oversized legacy catalog was partially/unsafely scanned");
        helper.assertTrue(data.publicRequest(request.id()).isEmpty(), "Oversized projects blocked unrelated bounded request cleanup");
        helper.succeed();
    }

}
