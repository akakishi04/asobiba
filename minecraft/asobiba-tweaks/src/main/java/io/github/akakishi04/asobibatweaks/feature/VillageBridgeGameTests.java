package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaks;
import java.util.List;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.gametest.framework.GameTest;
import net.minecraft.gametest.framework.GameTestHelper;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.tags.FluidTags;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.npc.Villager;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.properties.BlockStateProperties;
import net.neoforged.neoforge.gametest.GameTestHolder;
import net.neoforged.neoforge.gametest.PrefixGameTestTemplate;

/** Real-water crossing fixtures, with server-side paid bridge construction. */
@GameTestHolder(AsobibaTweaks.MOD_ID)
@PrefixGameTestTemplate(false)
public final class VillageBridgeGameTests {
    private static final BlockPos LEFT = new BlockPos(2, 1, 3);
    private static final BlockPos RIGHT = new BlockPos(13, 1, 3);
    private static final BlockPos FIRST = new BlockPos(5, 1, 3);
    private static final BlockPos MARKER = new BlockPos(7, 3, 3);

    private VillageBridgeGameTests() {}

    @GameTest(skyAccess = true, template = "empty16x6x9", batch = "village_bridges")
    public static void physicalRaisedBridgeIsBuiltFromPaidStockAndPreservesWater(
            GameTestHelper helper) {
        Fixture test = prepare(helper);
        VillageBridgeService.Candidate crossing = VillageBridgeService.findLoadedCrossing(
                test.level(), List.of(helper.absolutePos(LEFT),
                        helper.absolutePos(RIGHT)), 2);
        if (crossing == null || crossing.length() != 6
                || crossing.width() != 2) {
            helper.fail("Verified six-block source-water crossing was not surveyed", MARKER);
            return;
        }
        VillageSavedData.ProjectRecord bridge = queue(test);
        if (bridge == null || !"waiting_for_bridge".equals(test.parent().phase())) {
            helper.fail("Persisted road project did not queue a physical bridge", MARKER);
            return;
        }
        List<VillageBridgeService.Step> steps = VillageBridgeService.steps(bridge);
        if (steps.isEmpty() || steps.stream().noneMatch(
                s -> "piers".equals(s.stage()) && s.waterlogged())
                || steps.stream().noneMatch(s -> "approach_stairs".equals(s.stage()))
                || steps.stream().noneMatch(s -> "deck".equals(s.stage()))
                || steps.stream().noneMatch(s -> "railings".equals(s.stage()))) {
            helper.fail("Bridge plan missing real four-stage construction components", MARKER);
            return;
        }

        // All three material families enter the genuine persistent 8-slot
        // Carpenter cargo before work. The Wall remains an exact 6:6 craft.
        VillagerSimData.insertWorkCargo(test.worker(), test.level().registryAccess(),
                new ItemStack(Items.COBBLESTONE, 36), 8);
        VillagerSimData.insertWorkCargo(test.worker(), test.level().registryAccess(),
                new ItemStack(Items.OAK_PLANKS, 16), 8);
        VillagerSimData.insertWorkCargo(test.worker(), test.level().registryAccess(),
                new ItemStack(Items.OAK_STAIRS, 8), 8);

        for (int i = 0; i < steps.size(); i++) {
            VillageBridgeService.Step next = steps.get(i);
            test.worker().setPos(next.position().getX() + 0.5D,
                    next.position().getY() + 1.0D,
                    next.position().getZ() + 0.5D);
            VillageBridgeService.advance(test.worker(), test.level(), bridge);
            if (bridge.workCursor() != i + 1) {
                helper.fail("Paid bridge step " + i + " did not advance: "
                        + bridge.pausedReason(), MARKER);
                return;
            }
        }
        if (!"complete".equals(bridge.phase())
                || !"bridge_survey".equals(test.parent().phase())
                || !bridge.reservations().isEmpty()
                || VillagerSimData.hasWorkCargo(test.worker(),
                        test.level().registryAccess(), 8)) {
            helper.fail("Complete raised bridge left an unpaid bill or lost its parent route", MARKER);
            return;
        }

        BlockPos first = helper.absolutePos(FIRST);
        for (int i = 0; i < 6; i++) {
            for (int z = 0; z < 2; z++) {
                BlockPos center = first.offset(i, 0, z);
                if (!test.level().getFluidState(center).is(FluidTags.WATER)
                        || !test.level().getFluidState(center).isSource()
                        || !test.level().getBlockState(center.above(3)).is(Blocks.OAK_PLANKS)
                        || !test.level().getBlockState(center.above(1)).isAir()
                        || !test.level().getBlockState(center.above(2)).isAir()) {
                    helper.fail("Raised deck blocked the source-water boat corridor", MARKER);
                    return;
                }
            }
        }
        BlockPos outerPier = first.offset(0, 0, -1);
        if (!test.level().getBlockState(outerPier).is(Blocks.COBBLESTONE_WALL)
                || !test.level().getBlockState(outerPier).getValue(
                        BlockStateProperties.WATERLOGGED)
                || !test.level().getFluidState(outerPier).isSource()) {
            helper.fail("Support pier replaced river water instead of waterlogging", MARKER);
            return;
        }

        CompoundTag encoded = test.data().save(
                new CompoundTag(), test.level().registryAccess());
        VillageSavedData restored = VillageSavedData.load(
                encoded, test.level().registryAccess());
        var copy = restored.project(bridge.id()).orElse(null);
        if (copy == null || !"complete".equals(copy.phase())
                || VillageBridgeService.steps(copy).size() != steps.size()) {
            helper.fail("Bridge blueprint or completed project lost across SavedData NBT roundtrip",
                    MARKER);
            return;
        }
        helper.succeed();
    }

    @GameTest(skyAccess = true, template = "empty16x6x9", batch = "village_bridges")
    public static void obstructedBridgeNeverConsumesOrOverwritesPlayerBlock(
            GameTestHelper helper) {
        Fixture test = prepare(helper);
        var bridge = queue(test);
        if (bridge == null) {
            helper.fail("Cannot test bridge obstruction without a valid saved project", MARKER);
            return;
        }
        var steps = VillageBridgeService.steps(bridge);
        // The first real pier (underwater) is already present and should
        // be accepted without spending resources. The following air pier
        // cell is occupied by an external player edit, which must survive.
        var first = steps.getFirst();
        test.level().setBlock(first.position(), first.state(), 3);
        var blocked = steps.get(1);
        test.level().setBlock(blocked.position(), Blocks.OBSIDIAN.defaultBlockState(), 3);
        test.worker().setPos(first.position().getX() + 0.5D,
                first.position().getY() + 1.0D,
                first.position().getZ() + 0.5D);
        VillageBridgeService.advance(test.worker(), test.level(), bridge);
        if (bridge.workCursor() != 1) {
            helper.fail("Existing physical pier was charged a second time", MARKER);
            return;
        }
        VillageBridgeService.advance(test.worker(), test.level(), bridge);
        if (bridge.workCursor() != 1
                || !test.level().getBlockState(blocked.position()).is(Blocks.OBSIDIAN)
                || VillagerSimData.hasWorkCargo(test.worker(),
                        test.level().registryAccess(), 8)
                || !"piers".equals(bridge.phase())) {
            helper.fail("Bridge overwrote player Obsidian or spent materials for blocked work",
                    MARKER);
            return;
        }
        helper.succeed();
    }

    @GameTest(skyAccess = true, template = "empty16x6x9", batch = "village_bridges")
    public static void noBridgeForShortWaterOrObstructedBanks(
            GameTestHelper helper) {
        Fixture test = prepare(helper);
        BlockPos first = helper.absolutePos(FIRST);
        // A solid player block in the planned shore ramp forbids adoption.
        test.level().setBlock(first.relative(Direction.WEST), Blocks.OBSIDIAN.defaultBlockState(), 3);
        var blocked = VillageBridgeService.findLoadedCrossing(test.level(),
                List.of(helper.absolutePos(LEFT), helper.absolutePos(RIGHT)), 2);
        if (blocked != null) {
            helper.fail("Survey accepted an obstructed shore foundation", MARKER);
            return;
        }
        helper.succeed();
    }

    @GameTest(skyAccess = true, template = "empty16x6x9", batch = "village_bridges")
    public static void twoPaidCrossingsResumeSavedRouteWithoutDuplicateBills(GameTestHelper helper) {
        // Stagger shared server-probe budgets across fixtures in this batch.
        helper.runAfterDelay(10L, () -> {
            Fixture test = prepareTwoCrossings(helper);
            var first = queue(test);
            if (first == null || !buildPaid(test, first)) {
                helper.fail("First crossing did not physically finish", MARKER);
                return;
            }
            BlockPos firstDeck = helper.absolutePos(new BlockPos(3, 4, 3));
            if (!VillageBridgeService.completedBridgeSurface(test.data(), test.parent(), firstDeck)
                    || !test.parent().parameter("bridge_project_id").isBlank()
                    || !"bridge_survey".equals(test.parent().phase())) {
                helper.fail("Paid first bridge was not preserved/released for continuation", MARKER);
                return;
            }
            int firstCursor = first.workCursor();
            VillageBridgeService.advance(test.worker(), test.level(), first);
            if (first.workCursor() != firstCursor
                    || VillagerSimData.hasWorkCargo(test.worker(), test.level().registryAccess(), 8)) {
                helper.fail("Completed crossing was charged or advanced again", MARKER);
                return;
            }

            // The continuation cursor, selected route, and completed-bridge ledger
            // all roundtrip through the real production SavedData codec.
            VillageSavedData restored = VillageSavedData.load(test.data().save(
                    new CompoundTag(), test.level().registryAccess()), test.level().registryAccess());
            var savedParent = restored.project(test.parent().id()).orElseThrow();
            var savedRoute = restored.route(test.route().id()).orElseThrow();
            if (!"8".equals(savedParent.parameter("bridge_survey_offset"))
                    || !savedRoute.waypoints().equals(test.route().waypoints())
                    || !VillageBridgeService.queueBridge(test.level(), restored,
                            savedRoute, savedParent, savedRoute.waypoints())) {
                helper.fail("Saved continuation did not resume at the second crossing", MARKER);
                return;
            }
            var savedSecond = restored.project(java.util.UUID.fromString(
                    savedParent.parameter("bridge_project_id"))).orElseThrow();
            if (!helper.absolutePos(new BlockPos(11, 1, 3)).equals(BlockPos.of(
                    Long.parseLong(savedSecond.parameter("bridge_first_water"))))) {
                helper.fail("Reload recreated the first crossing instead of the next one", MARKER);
                return;
            }
            int projectCount = restored.projectsView().size();
            if (VillageBridgeService.queueBridge(test.level(), restored, savedRoute,
                    savedParent, savedRoute.waypoints())
                    || projectCount != restored.projectsView().size()) {
                helper.fail("Pending bridge was queued twice after reload", MARKER);
                return;
            }

            var second = queue(test);
            if (second == null || second.id().equals(first.id()) || !buildPaid(test, second)) {
                helper.fail("Second paid crossing did not physically finish", MARKER);
                return;
            }
            projectCount = test.data().projectsView().size();
            VillageBridgeService.queueBridge(test.level(), test.data(), test.route(),
                    test.parent(), test.route().waypoints());
            VillageBridgeService.queueBridge(test.level(), test.data(), test.route(),
                    test.parent(), test.route().waypoints());
            if (!"roadwork".equals(test.parent().phase())
                    || !"true".equals(test.parent().parameter("bridge_survey_done"))
                    || projectCount != test.data().projectsView().size()
                    || !test.level().getBlockState(firstDeck).is(Blocks.OAK_PLANKS)
                    || !first.reservations().isEmpty() || !second.reservations().isEmpty()
                    || VillagerSimData.hasWorkCargo(test.worker(), test.level().registryAccess(), 8)) {
                helper.fail("Multiple crossings lost paid stock/geometry or queued duplicate work", MARKER);
                return;
            }
            helper.succeed();
        });
    }

    @GameTest(skyAccess = true, template = "empty16x6x9", batch = "village_bridges")
    public static void unsafeSecondCrossingKeepsPaidFirstAndSurveyPending(GameTestHelper helper) {
        // Stagger shared server-probe budgets across fixtures in this batch.
        helper.runAfterDelay(20L, () -> {
            Fixture test = prepareTwoCrossings(helper);
            var first = queue(test);
            if (first == null || !buildPaid(test, first)) {
                helper.fail("Cannot prepare paid first crossing", MARKER);
                return;
            }
            BlockPos obstruction = helper.absolutePos(new BlockPos(10, 2, 3));
            test.level().setBlock(obstruction, Blocks.OBSIDIAN.defaultBlockState(), 3);
            int projectCount = test.data().projectsView().size();
            if (queue(test) != null || !"bridge_survey".equals(test.parent().phase())
                    || projectCount != test.data().projectsView().size()
                    || !"complete".equals(first.phase())
                    || !test.level().getBlockState(obstruction).is(Blocks.OBSIDIAN)
                    || VillagerSimData.hasWorkCargo(test.worker(), test.level().registryAccess(), 8)) {
                helper.fail("Unsafe next crossing was paved, charged, or replaced prior bridge", MARKER);
                return;
            }
            helper.succeed();
        });
    }

    @GameTest(skyAccess = true, template = "empty16x6x9", batch = "village_bridges")
    public static void legacyCompletedSlotResumesOnceAndChangedRoutePauses(GameTestHelper helper) {
        // Stagger shared server-probe budgets across fixtures in this batch.
        helper.runAfterDelay(30L, () -> {
            Fixture test = prepareTwoCrossings(helper);
            var bridge = queue(test);
            if (bridge == null || !buildPaid(test, bridge)) {
                helper.fail("Cannot prepare legacy completed crossing", MARKER);
                return;
            }
            test.parent().setParameter("bridge_project_id", bridge.id().toString());
            test.parent().setParameter("bridge_completed_ids", "");
            test.parent().setPhase("roadwork");
            if (!VillageBridgeService.resumeCompletedBridge(test.data(), test.parent())
                    || VillageBridgeService.resumeCompletedBridge(test.data(), test.parent())
                    || !bridge.id().toString().equals(test.parent().parameter("bridge_completed_ids"))) {
                helper.fail("Legacy completed bridge slot was not released exactly once", MARKER);
                return;
            }
            List<BlockPos> altered = List.of(test.route().from(), test.route().to().south());
            int projects = test.data().projectsView().size();
            if (VillageBridgeService.queueBridge(test.level(), test.data(), test.route(),
                    test.parent(), altered)
                    || !"bridge_survey".equals(test.parent().phase())
                    || !test.parent().pausedReason().contains("route changed")
                    || projects != test.data().projectsView().size()) {
                helper.fail("Continuation silently replaced the already-selected paid route", MARKER);
                return;
            }
            helper.succeed();
        });
    }

    @GameTest(skyAccess = true, template = "empty16x6x9", batch = "village_bridges")
    public static void missingChunkContinuationNeverInventsSurveyedRoad(GameTestHelper helper) {
        // Stagger shared server-probe budgets across fixtures in this batch.
        helper.runAfterDelay(40L, () -> {
            Fixture test = prepare(helper);
            BlockPos absent = new BlockPos(29_999_000, 64, 29_999_000);
            if (VillageSimulationScheduler.isChunkLoaded(test.level(), absent)) {
                helper.fail("Missing-chunk fixture unexpectedly loaded", MARKER);
                return;
            }
            List<BlockPos> nodes = List.of(absent, absent.east(15));
            test.route().setWaypoints(nodes);
            int projects = test.data().projectsView().size();
            if (VillageBridgeService.queueBridge(test.level(), test.data(), test.route(),
                    test.parent(), nodes)
                    || !"bridge_survey".equals(test.parent().phase())
                    || "true".equals(test.parent().parameter("bridge_survey_done"))
                    || projects != test.data().projectsView().size()
                    || VillageSimulationScheduler.isChunkLoaded(test.level(), absent)) {
                helper.fail("Unknown continuation became a road/bridge or force-loaded a chunk", MARKER);
                return;
            }
            helper.succeed();
        });
    }

    private static Fixture prepareTwoCrossings(GameTestHelper helper) {
        Fixture test = prepare(helper);
        for (int x = 0; x < 16; x++) {
            for (int z = 2; z <= 5; z++) {
                helper.setBlock(new BlockPos(x, 1, z),
                        x == 3 || x == 4 || x == 11 || x == 12 ? Blocks.WATER : Blocks.STONE);
            }
        }
        BlockPos from = helper.absolutePos(new BlockPos(0, 1, 3));
        BlockPos to = helper.absolutePos(new BlockPos(15, 1, 3));
        var route = test.data().createRoute(test.route().villageId(), "road", from, to);
        route.setWidth(2);
        route.setWaypoints(List.of(from, to));
        test.parent().setParameter("route_id", route.id().toString());
        test.parent().setAnchor(to);
        return new Fixture(test.level(), test.data(), test.parent(), route, test.worker());
    }

    private static boolean buildPaid(Fixture test, VillageSavedData.ProjectRecord bridge) {
        List<VillageBridgeService.Step> plan = VillageBridgeService.steps(bridge);
        for (int i = 0; i < plan.size(); i++) {
            var step = plan.get(i);
            VillagerSimData.insertWorkCargo(test.worker(), test.level().registryAccess(),
                    new ItemStack(step.material()), 8);
            test.worker().setPos(step.position().getX() + 0.5D,
                    step.position().getY() + 1.0D, step.position().getZ() + 0.5D);
            VillageBridgeService.advance(test.worker(), test.level(), bridge);
            if (bridge.workCursor() != i + 1) return false;
        }
        return "complete".equals(bridge.phase())
                && !VillagerSimData.hasWorkCargo(test.worker(), test.level().registryAccess(), 8);
    }

    private static Fixture prepare(GameTestHelper helper) {
        ServerLevel level = helper.getLevel();
        for (int x = 0; x < 16; x++) {
            for (int z = 0; z < 9; z++) {
                helper.setBlock(new BlockPos(x, 0, z), Blocks.STONE);
                helper.setBlock(new BlockPos(x, 1, z), Blocks.STONE);
                for (int y = 2; y < 6; y++)
                    helper.setBlock(new BlockPos(x, y, z), Blocks.AIR);
            }
        }
        for (int x = 5; x <= 10; x++)
            for (int z = 2; z <= 5; z++)
                helper.setBlock(new BlockPos(x, 1, z), Blocks.WATER);

        BlockPos base = helper.absolutePos(LEFT);
        VillageSavedData data = VillageSavedData.get(level);
        var village = data.createVillage(base, level.getGameTime());
        var route = data.createRoute(village.id(), "road",
                base, helper.absolutePos(RIGHT));
        route.setState("planned");
        route.setWidth(2);
        route.setQuality("dirt");
        var parent = data.createProject(village.id(), "road", 30, base);
        parent.setTemplateId("road_path_v2");
        parent.setAnchor(helper.absolutePos(RIGHT));
        parent.setParameter("route_id", route.id().toString());
        parent.setParameter("road_quality", "dirt");
        parent.setParameter("plank", "oak");
        parent.setParameter("road_width", "2");
        parent.setPhase("route_planning");

        Villager worker = EntityType.VILLAGER.create(level);
        if (worker == null) throw new IllegalStateException("Cannot make real test Carpenter");
        worker.setPos(base.getX() + 0.5D, base.getY() + 1.0D,
                base.getZ() + 0.5D);
        worker.setNoAi(true);
        if (!level.addFreshEntity(worker))
            throw new IllegalStateException("Cannot spawn real test Carpenter");
        VillagerSimData.setVillageId(worker, village.id());
        VillagerSimData.setDuty(worker, "carpenter", level.getGameTime());
        return new Fixture(level, data, parent, route, worker);
    }

    private static VillageSavedData.ProjectRecord queue(Fixture sample) {
        var nodes = sample.route().waypoints().size() >= 2 ? sample.route().waypoints()
                : List.of(sample.route().from(), sample.route().to());
        boolean created = VillageBridgeService.queueBridge(
                sample.level(), sample.data(), sample.route(), sample.parent(), nodes);
        if (!created) return null;
        return sample.data().activeProjectsForVillage(sample.route().villageId()).stream()
                .filter(p -> VillageBridgeService.TEMPLATE.equals(p.templateId()))
                .findFirst().orElse(null);
    }

    private record Fixture(ServerLevel level, VillageSavedData data,
                           VillageSavedData.ProjectRecord parent,
                           VillageSavedData.RouteRecord route, Villager worker) {}
}
