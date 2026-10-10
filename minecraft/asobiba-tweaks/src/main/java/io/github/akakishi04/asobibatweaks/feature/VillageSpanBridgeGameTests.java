package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaks;
import java.util.List;
import java.util.UUID;
import net.minecraft.core.BlockPos;
import net.minecraft.gametest.framework.GameTest;
import net.minecraft.gametest.framework.GameTestHelper;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.tags.FluidTags;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.npc.Villager;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.level.block.Blocks;
import net.neoforged.neoforge.gametest.GameTestHolder;
import net.neoforged.neoforge.gametest.PrefixGameTestTemplate;

@GameTestHolder(AsobibaTweaks.MOD_ID)
@PrefixGameTestTemplate(false)
public final class VillageSpanBridgeGameTests {
    private static final BlockPos MARKER = new BlockPos(6, 5, 6);
    private VillageSpanBridgeGameTests() {}

    @GameTest(skyAccess = true, template = "empty16x14x16", batch = "village_spans")
    public static void diagonalWaterBridgeHasPaidConnectedDeckAndOpenChannel(GameTestHelper helper) {
        // Stagger shared server-probe budgets across fixtures in this batch.
        helper.runAfterDelay(10L, () -> {
            Fixture test = prepare(helper, true);
            var bridge = queue(test);
            if (bridge == null || !"3".equals(bridge.parameter("bridge_width")) || !build(test, bridge)) {
                helper.fail("Diagonal selected crossing did not build a paid three-wide strip", MARKER);
                return;
            }
            for (int n = 0; n < 3; n++) {
                for (int lane = -1; lane <= 1; lane++) {
                    BlockPos water = helper.absolutePos(new BlockPos(6 + n, 4, 6 + n + lane));
                    if (!test.level().getFluidState(water).is(FluidTags.WATER)
                            || !test.level().getFluidState(water).isSource()
                            || !test.level().getBlockState(water.above()).isAir()
                            || !test.level().getBlockState(water.above(2)).isAir()
                            || !test.level().getBlockState(water.above(3)).is(Blocks.OAK_PLANKS)) {
                        helper.fail("Diagonal bridge lost its real open water channel/deck", MARKER);
                        return;
                    }
                }
                if (n < 2) {
                    BlockPos shared = helper.absolutePos(new BlockPos(6 + n, 7, 7 + n));
                    if (!test.level().getBlockState(shared).is(Blocks.OAK_PLANKS)
                            || !test.level().getBlockState(shared.east()).is(Blocks.OAK_PLANKS)) {
                        helper.fail("Diagonal deck rows only touch at corners", MARKER);
                        return;
                    }
                }
            }
            VillageSavedData restored = VillageSavedData.load(test.data().save(
                    new CompoundTag(), test.level().registryAccess()), test.level().registryAccess());
            var copy = restored.project(bridge.id()).orElseThrow();
            if (!VillageBridgeService.steps(copy).equals(VillageBridgeService.steps(bridge))
                    || !"complete".equals(copy.phase()) || !bridge.reservations().isEmpty()) {
                helper.fail("Paid diagonal blueprint changed on SavedData reload", MARKER);
                return;
            }
            helper.succeed();
        });
    }

    @GameTest(skyAccess = true, template = "empty16x14x16", batch = "village_spans")
    public static void northwestDiagonalRetainsConnectedPaidGeometry(GameTestHelper helper) {
        // Stagger shared server-probe budgets across fixtures in this batch.
        helper.runAfterDelay(20L, () -> {
            Fixture test = prepare(helper, true);
            test.route().setWaypoints(List.of(test.route().to(), test.route().from()));
            var bridge = queue(test);
            if (bridge == null || !"-1".equals(bridge.parameter("span_dx"))
                    || !"-1".equals(bridge.parameter("span_dz")) || !build(test, bridge)) {
                helper.fail("Reverse diagonal failed loaded survey or physical paid construction", MARKER);
                return;
            }
            BlockPos shared = helper.absolutePos(new BlockPos(7, 7, 7));
            if (!test.level().getBlockState(shared).is(Blocks.OAK_PLANKS)
                    || !test.level().getBlockState(shared.east()).is(Blocks.OAK_PLANKS)) {
                helper.fail("Northwest rows lost their orthogonal connection", MARKER);
                return;
            }
            helper.succeed();
        });
    }

    @GameTest(skyAccess = true, template = "empty16x14x16", batch = "village_spans")
    public static void dryRavineBuildsNaturalFoundedPaidPiersWithoutChangingBanks(GameTestHelper helper) {
        // Stagger shared server-probe budgets across fixtures in this batch.
        helper.runAfterDelay(30L, () -> {
            Fixture test = prepare(helper, false);
            var bridge = queue(test);
            if (bridge == null || !build(test, bridge)) {
                helper.fail("Short dry ravine was not physically bridged", MARKER);
                return;
            }
            BlockPos foundation = helper.absolutePos(new BlockPos(6, 1, 4));
            BlockPos deck = helper.absolutePos(new BlockPos(6, 4, 5));
            if (!test.level().getBlockState(foundation).is(Blocks.STONE)
                    || !test.level().getBlockState(foundation.above()).is(Blocks.COBBLESTONE_WALL)
                    || !test.level().getBlockState(deck).is(Blocks.OAK_PLANKS)
                    || !test.level().getBlockState(deck.west()).is(Blocks.STONE)
                    || !bridge.reservations().isEmpty()) {
                helper.fail("Ravine bridge floated, destroyed a bank, or retained a material bill", MARKER);
                return;
            }
            VillageSavedData restored = VillageSavedData.load(test.data().save(
                    new CompoundTag(), test.level().registryAccess()), test.level().registryAccess());
            if (!VillageBridgeService.steps(restored.project(bridge.id()).orElseThrow())
                    .equals(VillageBridgeService.steps(bridge))) {
                helper.fail("Ravine foundation elevations were reconstructed from modified terrain", MARKER);
                return;
            }
            VillageBridgeService.queueBridge(test.level(), test.data(), test.route(),
                    test.parent(), test.route().waypoints());
            if (!"roadwork".equals(test.parent().phase())) {
                helper.fail("Finished dry gap did not resume the original route", MARKER);
                return;
            }
            helper.succeed();
        });
    }

    @GameTest(skyAccess = true, template = "empty16x14x16", batch = "village_spans")
    public static void changedRavineFoundationPausesWithoutDebitingOrFloating(GameTestHelper helper) {
        // Stagger shared server-probe budgets across fixtures in this batch.
        helper.runAfterDelay(40L, () -> {
            Fixture test = prepare(helper, false);
            var bridge = queue(test);
            if (bridge == null) {
                helper.fail("Cannot prepare supported ravine blueprint", MARKER);
                return;
            }
            var first = VillageBridgeService.steps(bridge).getFirst();
            test.level().setBlock(first.position().below(), Blocks.AIR.defaultBlockState(), 3);
            VillagerSimData.insertWorkCargo(test.worker(), test.level().registryAccess(),
                    new ItemStack(first.material()), 8);
            test.worker().setPos(first.position().getX(), first.position().getY(), first.position().getZ());
            VillageBridgeService.advance(test.worker(), test.level(), bridge);
            if (bridge.workCursor() != 0 || !test.level().getBlockState(first.position()).isAir()
                    || !VillagerSimData.hasWorkCargo(test.worker(), test.level().registryAccess(), 8)
                    || bridge.pausedReason().isBlank()) {
                helper.fail("A removed foundation allowed an unpaid/floating pier", MARKER);
                return;
            }
            helper.succeed();
        });
    }

    @GameTest(skyAccess = true, template = "empty16x14x16", batch = "village_spans")
    public static void diagonalPlayerObstructionRejectsBeforeReservingMaterials(GameTestHelper helper) {
        // Stagger shared server-probe budgets across fixtures in this batch.
        helper.runAfterDelay(50L, () -> {
            Fixture test = prepare(helper, true);
            BlockPos obstruction = helper.absolutePos(new BlockPos(5, 5, 5));
            test.level().setBlock(obstruction, Blocks.OBSIDIAN.defaultBlockState(), 3);
            int count = test.data().projectsView().size();
            if (queue(test) != null || count != test.data().projectsView().size()
                    || !test.level().getBlockState(obstruction).is(Blocks.OBSIDIAN)
                    || !"bridge_survey".equals(test.parent().phase())) {
                helper.fail("Diagonal ramp survey overwrote/accepted a player obstruction", MARKER);
                return;
            }
            helper.succeed();
        });
    }

    private static Fixture prepare(GameTestHelper helper, boolean diagonal) {
        ServerLevel level = helper.getLevel();
        for (int x = 0; x < 16; x++) for (int z = 0; z < 16; z++) {
            for (int y = 0; y < 14; y++)
                helper.setBlock(new BlockPos(x, y, z), y <= 4 ? Blocks.STONE : Blocks.AIR);
        }
        if (diagonal) {
            for (int row = 0; row < 3; row++) for (int lane = -2; lane <= 2; lane++)
                helper.setBlock(new BlockPos(6 + row, 4, 6 + row + lane), Blocks.WATER);
        } else {
            for (int x = 6; x <= 9; x++) for (int z = 3; z <= 8; z++)
                for (int y = 2; y <= 4; y++) helper.setBlock(new BlockPos(x, y, z), Blocks.AIR);
        }
        BlockPos from = helper.absolutePos(diagonal ? new BlockPos(3, 4, 3) : new BlockPos(3, 4, 5));
        BlockPos to = helper.absolutePos(diagonal ? new BlockPos(11, 4, 11) : new BlockPos(12, 4, 5));
        var data = VillageSavedData.get(level);
        var village = data.createVillage(from, level.getGameTime());
        var route = data.createRoute(village.id(), "road", from, to);
        route.setWidth(2);
        route.setWaypoints(List.of(from, to));
        var parent = data.createProject(village.id(), "road", 30, from);
        parent.setTemplateId("road_path_v2");
        parent.setAnchor(to);
        parent.setParameter("route_id", route.id().toString());
        parent.setParameter("plank", "oak");
        parent.setParameter("road_quality", "dirt");
        parent.setPhase("bridge_survey");
        Villager worker = EntityType.VILLAGER.create(level);
        if (worker == null) throw new IllegalStateException("Cannot make test Carpenter");
        worker.setNoAi(true);
        worker.setPos(from.getX(), from.getY() + 1, from.getZ());
        if (!level.addFreshEntity(worker)) throw new IllegalStateException("Cannot spawn test Carpenter");
        VillagerSimData.setVillageId(worker, village.id());
        VillagerSimData.setDuty(worker, "carpenter", level.getGameTime());
        return new Fixture(level, data, parent, route, worker);
    }
    private static VillageSavedData.ProjectRecord queue(Fixture test) {
        if (!VillageBridgeService.queueBridge(test.level(), test.data(), test.route(),
                test.parent(), test.route().waypoints())) return null;
        return test.data().project(UUID.fromString(test.parent().parameter("bridge_project_id"))).orElse(null);
    }
    private static boolean build(Fixture test, VillageSavedData.ProjectRecord bridge) {
        var plan = VillageBridgeService.steps(bridge);
        for (int n = 0; n < plan.size(); n++) {
            var step = plan.get(n);
            VillagerSimData.insertWorkCargo(test.worker(), test.level().registryAccess(), new ItemStack(step.material()), 8);
            test.worker().setPos(step.position().getX() + 0.5, step.position().getY() + 1, step.position().getZ() + 0.5);
            VillageBridgeService.advance(test.worker(), test.level(), bridge);
            if (bridge.workCursor() != n + 1) return false;
        }
        return "complete".equals(bridge.phase())
                && !VillagerSimData.hasWorkCargo(test.worker(), test.level().registryAccess(), 8);
    }
    private record Fixture(ServerLevel level, VillageSavedData data,
                           VillageSavedData.ProjectRecord parent,
                           VillageSavedData.RouteRecord route, Villager worker) {}
}
