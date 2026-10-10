package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaks;
import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
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
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.properties.BlockStateProperties;
import net.neoforged.neoforge.gametest.GameTestHolder;
import net.neoforged.neoforge.gametest.PrefixGameTestTemplate;

@GameTestHolder(AsobibaTweaks.MOD_ID)
@PrefixGameTestTemplate(false)
public final class VillageResourceSiteGameTests {
    private VillageResourceSiteGameTests() {}

    @GameTest(template = "empty16x80x16", skyAccess = true, batch = "resource_site_bounds")
    public static void movingWorkerCannotMoveQuarryBoundaryOrInitialFloor(GameTestHelper helper) {
        Fixture f = fixture(helper, "quarry");
        BlockPos outside = f.base().offset(4, 0, 0);
        f.level().setBlock(outside, Blocks.STONE.defaultBlockState(), Block.UPDATE_CLIENTS);
        move(f, outside);
        helper.assertTrue(!VillageResourceSiteService.harvestQuarry(f.worker(), f.level(), f.site(), outside),
                "A moving worker extended its site");
        helper.assertTrue(f.level().getBlockState(outside).is(Blocks.STONE), "Out-of-bounds stone was removed");
        helper.assertTrue(!VillageResourceSiteService.mayHarvest(f.worker(), f.level(), f.site(), f.base().below(13)),
                "Quarry followed excavation below its initial twelve-block floor");
        helper.assertTrue(VillageResourceSiteService.overlapsExistingFootprint("quarry",
                f.site().max().offset(-1, -20, -1), f.site().max().offset(10, -10, 10), java.util.List.of(f.site())),
                "An adjacent replacement could overlap and rebase a previously excavated quarry");
        var negative = f.data().createWorkSite(f.village().id(), "quarry",
                new BlockPos(f.base().getX(), -16, f.base().getZ()), new BlockPos(f.base().getX(), 4, f.base().getZ()));
        VillagerSimData.setWorkSiteId(f.worker(), negative.id());
        helper.assertTrue(!VillageResourceSiteService.mayHarvest(f.worker(), f.level(), negative,
                new BlockPos(f.base().getX(), -1, f.base().getZ())), "Negative-Y quarry was accepted");
        helper.succeed();
    }

    @GameTest(template = "empty16x80x16", skyAccess = true, batch = "resource_site_stock")
    public static void physicalReserveCapOverridesStaleLedgerAndPreservesGraniteDrop(GameTestHelper helper) {
        Fixture f = fixture(helper, "quarry");
        f.store().setItem(0, new ItemStack(Items.COBBLESTONE, 64));
        f.store().setItem(1, new ItemStack(Items.COBBLESTONE, 32));
        f.village().replaceLedger(java.util.Map.of());
        f.level().setBlock(f.base(), Blocks.GRANITE.defaultBlockState(), Block.UPDATE_CLIENTS);
        helper.assertTrue(!VillageResourceSiteService.harvestQuarry(f.worker(), f.level(), f.site(), f.base()),
                "Stale empty ledger bypassed the physical reserve cap");
        var project = f.data().createProject(f.village().id(), "building", 50, f.base().offset(30, 0, 30));
        project.setReservation("minecraft:cobblestone", 500);
        helper.assertTrue(VillageResourceSiteService.hasDemand(f.level(), f.village(), "quarry"),
                "Actual unpaid construction bill did not increase gathering demand");
        project.setPhase("complete");
        helper.assertTrue(!VillageResourceSiteService.hasDemand(f.level(), f.village(), "quarry"),
                "Completed construction bill kept gathering past its reserve target");
        f.store().clearContent();
        f.village().replaceLedger(java.util.Map.of("minecraft:cobblestone", 999));
        helper.assertTrue(VillageResourceSiteService.harvestQuarry(f.worker(), f.level(), f.site(), f.base()),
                "Real empty storage could not resume mining");
        helper.assertTrue(f.level().getBlockState(f.base()).isAir()
                && VillagerSimData.workCargoCount(f.worker(), f.level().registryAccess(), 8, Items.GRANITE) == 1
                && VillagerSimData.workCargoCount(f.worker(), f.level().registryAccess(), 8, Items.COBBLESTONE) == 0,
                "Quarry synthesized cobblestone instead of retaining actual granite loot");
        helper.succeed();
    }

    @GameTest(template = "empty16x80x16", skyAccess = true, batch = "resource_site_fluids")
    public static void exposedWaterSuspendsFaceBeforeAnyExcavation(GameTestHelper helper) {
        Fixture f = fixture(helper, "quarry");
        f.level().setBlock(f.base(), Blocks.STONE.defaultBlockState(), Block.UPDATE_CLIENTS);
        f.level().setBlock(f.base().east(), Blocks.WATER.defaultBlockState(), Block.UPDATE_CLIENTS);
        helper.assertTrue(!VillageResourceSiteService.harvestQuarry(f.worker(), f.level(), f.site(), f.base()),
                "Quarry knowingly opened a water ingress face");
        helper.assertTrue("flooded".equals(f.site().state()) && f.level().getBlockState(f.base()).is(Blocks.STONE),
                "Flooded work face was not persisted as suspended");
        helper.assertTrue(!VillagerSimData.hasWorkCargo(f.worker(), f.level().registryAccess(), 8), "Suspended face yielded cargo");
        helper.succeed();
    }

    @GameTest(template = "empty16x80x16", skyAccess = true, batch = "resource_site_protection")
    public static void playerPlacedNaturalBlocksAndRoadColumnsAreProtected(GameTestHelper helper) {
        Fixture f = fixture(helper, "quarry");
        f.level().setBlock(f.base(), Blocks.STONE.defaultBlockState(), Block.UPDATE_CLIENTS);
        VillageResourceSiteService.playerPlaced(f.level(), f.base());
        helper.assertTrue(!VillageResourceSiteService.harvestQuarry(f.worker(), f.level(), f.site(), f.base()),
                "Player-placed stone masqueraded as a natural deposit");
        var loaded = VillageSavedData.load(f.data().save(new CompoundTag(), f.level().registryAccess()), f.level().registryAccess());
        helper.assertTrue(loaded.isPlayerResourceBlock(f.base()), "Player resource protection disappeared after save/reload");
        f.data().setPlayerResourceBlock(f.base(), false);
        var route = f.data().createRoute(f.village().id(), "path", f.base().offset(-3, 8, 0), f.base().offset(3, 8, 0));
        route.setState("active");
        helper.assertTrue(!VillageResourceSiteService.harvestQuarry(f.worker(), f.level(), f.site(), f.base()),
                "Quarry tunnelled beneath an indexed road");
        helper.succeed();
    }

    @GameTest(template = "empty16x14x16", skyAccess = true, batch = "resource_site_forestry")
    public static void simpleTreeKeepsRealLogsPaysMatchingSeedAndRests(GameTestHelper helper) {
        Fixture f = fixture(helper, "forestry");
        plantTree(f, f.base()); plantTree(f, f.base().west(4)); plantTree(f, f.base().east(4));
        VillagerSimData.insertWorkCargo(f.worker(), f.level().registryAccess(), new ItemStack(Items.OAK_SAPLING), 8);
        helper.assertTrue(VillageResourceSiteService.harvestTree(f.worker(), f.level(), f.site(), f.base()),
                "Approved renewable tree did not harvest");
        helper.assertTrue(VillagerSimData.workCargoCount(f.worker(), f.level().registryAccess(), 8, Items.OAK_LOG) == 4,
                "Real log loot was not conserved");
        helper.assertTrue(f.level().getBlockState(f.base()).is(Blocks.OAK_SAPLING)
                && VillagerSimData.workCargoCount(f.worker(), f.level().registryAccess(), 8, Items.OAK_SAPLING) == 0,
                "Replanting did not consume its actual same-family sapling");
        for (int y = 1; y < 4; y++) helper.assertTrue(f.level().getBlockState(f.base().above(y)).isAir(), "Floating trunk remained");
        helper.assertTrue(f.level().getBlockState(f.base().above(4)).is(Blocks.OAK_LEAVES), "Leaves were harvested unnecessarily");
        helper.assertTrue("resting".equals(f.site().state()) && f.site().nextHarvestGameTime() > f.level().getGameTime(),
                "Regrowth cooldown was not persisted");
        helper.assertTrue(f.level().getBlockState(f.base().west(4)).is(Blocks.OAK_LOG)
                && f.level().getBlockState(f.base().east(4)).is(Blocks.OAK_LOG), "Standing tree reserve was clear-cut");
        helper.succeed();
    }

    @GameTest(template = "empty16x14x16", skyAccess = true, batch = "resource_site_no_free_seed")
    public static void forestryNeverSynthesizesSaplingAndRefusesPlayerLogs(GameTestHelper helper) {
        Fixture f = fixture(helper, "forestry");
        plantTree(f, f.base()); plantTree(f, f.base().west(4)); plantTree(f, f.base().east(4));
        VillageResourceSiteService.playerPlaced(f.level(), f.base().above());
        helper.assertTrue(VillageResourceSiteService.simpleTree(f.level(), f.site(), f.base()).isEmpty(),
                "Player log with natural leaves was accepted");
        f.data().setPlayerResourceBlock(f.base().above(), false);
        helper.assertTrue(VillageResourceSiteService.harvestTree(f.worker(), f.level(), f.site(), f.base()), "Unprotected simple tree not harvested");
        helper.assertTrue(f.level().getBlockState(f.base()).isAir(), "A free sapling was invented without inventory payment");
        helper.succeed();
    }

    @GameTest(template = "empty16x14x16", skyAccess = true, batch = "resource_site_giant")
    public static void boundaryCrossingBranchAndLastStandingTreesAreSkipped(GameTestHelper helper) {
        Fixture f = fixture(helper, "forestry");
        plantTree(f, f.base());
        helper.assertTrue(!VillageResourceSiteService.harvestTree(f.worker(), f.level(), f.site(), f.base()),
                "Last standing tree was deliberately clear-cut");
        plantTree(f, f.base().west(4)); plantTree(f, f.base().east(4));
        f.level().setBlock(f.base().above(2).east(), Blocks.OAK_LOG.defaultBlockState(), Block.UPDATE_CLIENTS);
        helper.assertTrue(VillageResourceSiteService.simpleTree(f.level(), f.site(), f.base()).isEmpty(),
                "Complex branched tree was partially harvested");
        var shortSite = f.data().createWorkSite(f.village().id(), "forestry", f.base().offset(-1, 0, -1), f.base().offset(1, 1, 1));
        helper.assertTrue(VillageResourceSiteService.simpleTree(f.level(), shortSite, f.base()).isEmpty(),
                "Trunk extending outside its site's vertical boundary was accepted");
        BlockPos originalMin = f.site().min(), originalMax = f.site().max();
        f.site().setState("depleted"); f.site().setIdleDays(3);
        f.site().setNextHarvestGameTime(f.level().getGameTime() + 7 * 24_000L);
        f.site().setLastLifecycleGameTime(f.level().getGameTime() - 24_000L);
        VillageResourceSiteService.refreshSite(f.level(), f.data(), f.site());
        helper.assertTrue("depleted".equals(f.site().state()), "Forestry ignored its extended regrowth wait");
        f.site().setNextHarvestGameTime(f.level().getGameTime());
        f.site().setLastLifecycleGameTime(f.level().getGameTime() - 24_000L);
        VillageResourceSiteService.refreshSite(f.level(), f.data(), f.site());
        helper.assertTrue("active".equals(f.site().state()) && f.site().idleDays() == 0
                && originalMin.equals(f.site().min()) && originalMax.equals(f.site().max()),
                "Regrowth reapproval moved or permanently abandoned the original forestry footprint");
        helper.succeed();
    }

    @GameTest(template = "empty16x80x16", skyAccess = true, batch = "resource_site_reload")
    public static void fixedBoundsAssignmentAndParentPersistAcrossReload(GameTestHelper helper) {
        Fixture f = fixture(helper, "quarry");
        var parent = f.data().createWorkSite(f.village().id(), "outpost", f.base().offset(20, 0, 0), f.base().offset(24, 4, 4));
        parent.setPurpose("quarry");
        f.site().setParentWorkSiteId(parent.id());
        f.site().setResourceCursor(71); f.site().setNextHarvestGameTime(91_000);
        VillagerSimData.setOutpostSiteId(f.worker(), parent.id());
        CompoundTag workerTag = new CompoundTag(); f.worker().saveWithoutId(workerTag);
        Villager restoredWorker = EntityType.VILLAGER.create(f.level());
        helper.assertTrue(restoredWorker != null, "Could not make reload fixture");
        restoredWorker.load(workerTag);
        helper.assertTrue(VillagerSimData.workSiteId(restoredWorker).filter(f.site().id()::equals).isPresent(), "Worker lost stable site ID");
        var loaded = VillageSavedData.load(f.data().save(new CompoundTag(), f.level().registryAccess()), f.level().registryAccess());
        var site = loaded.workSite(f.site().id()).orElseThrow();
        helper.assertTrue(site.min().equals(f.site().min()) && site.max().equals(f.site().max())
                && parent.id().equals(site.parentWorkSiteId()) && site.resourceCursor() == 71
                && site.nextHarvestGameTime() == 91_000, "Reload changed footprint/original floor or planner state");
        helper.succeed();
    }

    @GameTest(template = "empty16x80x16", skyAccess = true, batch = "resource_site_unloaded")
    public static void foreignMissingAndUnloadedAssignmentsNeverFallBackAroundWorker(GameTestHelper helper) {
        Fixture f = fixture(helper, "quarry");
        f.level().setBlock(f.base(), Blocks.STONE.defaultBlockState(), Block.UPDATE_CLIENTS);
        VillagerSimData.setWorkSiteId(f.worker(), UUID.randomUUID());
        VillageResourceSiteService.gather(f.worker(), f.level(), "quarry");
        helper.assertTrue(f.level().getBlockState(f.base()).is(Blocks.STONE), "Missing site fell back to nearby stone");
        var other = f.data().createVillage(f.base().offset(100, 0, 0), f.level().getGameTime());
        var foreign = f.data().createWorkSite(other.id(), "quarry", f.base().offset(-2, -12, -2), f.base().offset(2, 0, 2));
        VillagerSimData.setWorkSiteId(f.worker(), foreign.id());
        helper.assertTrue(VillageResourceSiteService.assignedSite(f.worker(), f.level(), "quarry") == null, "Foreign site accepted");
        BlockPos far = f.base().offset(2048, 0, 0);
        helper.assertTrue(!VillageSimulationScheduler.isChunkLoaded(f.level(), far), "Unloaded fixture unexpectedly loaded");
        var remote = f.data().createWorkSite(f.village().id(), "quarry", far.offset(-2, -12, -2), far.offset(2, 0, 2));
        VillagerSimData.setWorkSiteId(f.worker(), remote.id());
        VillageResourceSiteService.gather(f.worker(), f.level(), "quarry");
        helper.assertTrue(!VillageSimulationScheduler.isChunkLoaded(f.level(), far)
                && f.level().getBlockState(f.base()).is(Blocks.STONE), "Resource worker loaded chunks or used a local fallback");
        helper.succeed();
    }

    @GameTest(template = "empty16x14x16", skyAccess = true, batch = "resource_site_fishing")
    public static void coreFisherUsesIndependentPersistentSiteAndPhysicalDemand(GameTestHelper helper) {
        Fixture f = fixture(helper, "fishing");
        helper.assertTrue(VillagerSimData.outpostSiteId(f.worker()).isEmpty()
                && VillageResourceSiteService.assignedSite(f.worker(), f.level(), "fishing") == f.site(),
                "Core fishing still requires a remote outpost identity");
        f.level().setBlock(f.base(), Blocks.WATER.defaultBlockState(), Block.UPDATE_CLIENTS);
        f.data().createRoute(f.village().id(), "river", f.base().west(3), f.base().east(3));
        helper.assertTrue(VillageResourceSiteService.mayHarvest(f.worker(), f.level(), f.site(), f.base()), "Core fishing site is unavailable");
        f.store().setItem(0, new ItemStack(Items.COD, 24));
        helper.assertTrue(!VillageResourceSiteService.mayHarvest(f.worker(), f.level(), f.site(), f.base()), "Fishing ignored actual fish reserve target");
        f.store().clearContent();
        f.data().createWorkSite(f.village().id(), "river_dock", f.base(), f.base().above(4));
        helper.assertTrue(!VillageResourceSiteService.mayHarvest(f.worker(), f.level(), f.site(), f.base()), "Fishing infringed a recognized dock");
        helper.succeed();
    }

    @GameTest(template = "empty16x14x16", skyAccess = true, batch = "resource_site_low_budget")
    public static void lowConfiguredBudgetPausesSafelyAndResumesAfterRestore(GameTestHelper helper) {
        Fixture f = fixture(helper, "forestry");
        plantTree(f, f.base()); plantTree(f, f.base().west(4)); plantTree(f, f.base().east(4));
        int original = AsobibaTweaksConfig.VILLAGE_WORKER_PROBES_PER_TICK.getAsInt();
        try {
            AsobibaTweaksConfig.VILLAGE_WORKER_PROBES_PER_TICK.set(64);
            helper.assertTrue(!VillageResourceSiteService.harvestTree(f.worker(), f.level(), f.site(), f.base()),
                    "Insufficient safety budget allowed destructive tree work");
            helper.assertTrue(f.site().resourcePauseReason().contains("800")
                    && "active".equals(f.site().state()) && f.site().resourceCursor() == 0,
                    "Configuration hold silently depleted or abandoned the site");
            helper.assertTrue(f.level().getBlockState(f.base()).is(Blocks.OAK_LOG)
                    && !VillagerSimData.hasWorkCargo(f.worker(), f.level().registryAccess(), 8), "Budget hold mutated world/cargo");
            var snapshot = VillageStatusNetworking.buildSnapshot(f.level(), f.data(), f.village());
            helper.assertTrue(snapshot.projects().stream().anyMatch(line -> line.contains("probe budget")),
                    "Configuration blocker was not shown in village status");
        } finally {
            AsobibaTweaksConfig.VILLAGE_WORKER_PROBES_PER_TICK.set(original);
        }
        helper.assertTrue(VillageResourceSiteService.harvestTree(f.worker(), f.level(), f.site(), f.base()),
                "Restoring normal budget did not resume the same site");
        helper.assertTrue(f.site().resourcePauseReason().isEmpty(), "Resolved budget blocker stayed persisted");
        helper.succeed();
    }

    @GameTest(template = "empty16x14x16", skyAccess = true, batch = "resource_site_busy_budget", timeoutTicks = 20)
    public static void busyTickDoesNotAdvanceCursorOrDeclareDepletion(GameTestHelper helper) {
        Fixture f = fixture(helper, "forestry");
        plantTree(f, f.base()); plantTree(f, f.base().west(4)); plantTree(f, f.base().east(4));
        while (VillageSimulationScheduler.tryConsumeWorkerProbe(f.level())) { }
        VillageResourceSiteService.gather(f.worker(), f.level(), "forestry");
        helper.assertTrue("active".equals(f.site().state()) && f.site().resourceCursor() == 0
                && f.site().resourcePauseReason().contains("next tick"), "Busy tick consumed the site cursor/depletion state");
        helper.runAtTickTime(2, () -> {
            helper.assertTrue(VillageResourceSiteService.harvestTree(f.worker(), f.level(), f.site(), f.base()),
                    "A new tick did not retry the pending safety preflight");
            helper.succeed();
        });
    }

    private static Fixture fixture(GameTestHelper helper, String type) {
        ServerLevel level = helper.getLevel();
        int floor = "quarry".equals(type) ? 64 : 0;
        for (int x = 0; x < 16; x++) for (int z = 0; z < 16; z++) {
            helper.setBlock(new BlockPos(x, floor, z), Blocks.DIRT);
            for (int y = floor + 1; y < floor + 14; y++) helper.setBlock(new BlockPos(x, y, z), Blocks.AIR);
        }
        BlockPos base = helper.absolutePos(new BlockPos(7, floor + 1, 7));
        var data = VillageSavedData.get(level);
        var village = data.createVillage(base, level.getGameTime());
        village.setStorageBootstrapComplete(true);
        BlockPos storePos = helper.absolutePos(new BlockPos(14, floor + 1, 14));
        level.setBlock(storePos, Blocks.BARREL.defaultBlockState(), Block.UPDATE_CLIENTS);
        data.createStorage(village.id(), storePos, "general");
        var site = data.createWorkSite(village.id(), type,
                "quarry".equals(type) ? base.offset(-2, -12, -2) : helper.absolutePos(new BlockPos(1, 1, 1)),
                "quarry".equals(type) ? base.offset(2, 0, 2) : helper.absolutePos(new BlockPos(13, 12, 13)));
        site.setPurpose("forestry".equals(type) ? "wood" : "quarry".equals(type) ? "stone" : "fishing");
        Villager worker = EntityType.VILLAGER.create(level);
        helper.assertTrue(worker != null, "Could not create worker");
        worker.setNoAi(true); worker.setPersistenceRequired();
        worker.moveTo(base.getX() + 0.5, base.getY(), base.getZ() - 0.5, 0, 0);
        VillagerSimData.ensureInitialized(worker);
        VillagerSimData.setVillageId(worker, village.id());
        VillagerSimData.setDuty(worker, "forestry".equals(type) ? "forester" : "fishing".equals(type) ? "fisher" : "quarry", level.getGameTime());
        VillagerSimData.setWorkSiteId(worker, site.id());
        level.addFreshEntity(worker);
        return new Fixture(level, data, village, site, worker, base, (Container)level.getBlockEntity(storePos));
    }

    private static void plantTree(Fixture f, BlockPos base) {
        for (int y = 0; y < 4; y++) f.level().setBlock(base.above(y), Blocks.OAK_LOG.defaultBlockState(), Block.UPDATE_CLIENTS);
        for (int x = -1; x <= 1; x++) for (int z = -1; z <= 1; z++)
            f.level().setBlock(base.offset(x, 4, z), Blocks.OAK_LEAVES.defaultBlockState()
                    .setValue(BlockStateProperties.PERSISTENT, false).setValue(BlockStateProperties.DISTANCE, 1), Block.UPDATE_CLIENTS);
    }

    private static void move(Fixture f, BlockPos pos) {
        f.worker().moveTo(pos.getX() + 0.5, pos.getY(), pos.getZ() - 0.5, 0, 0);
    }

    private record Fixture(ServerLevel level, VillageSavedData data, VillageSavedData.VillageRecord village,
                           VillageSavedData.WorkSiteRecord site, Villager worker, BlockPos base, Container store) {}
}
