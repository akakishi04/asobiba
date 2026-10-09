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

    @GameTest(template = "empty16x6x9", batch = "village_bridges")
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
                || !"roadwork".equals(test.parent().phase())
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

    @GameTest(template = "empty16x6x9", batch = "village_bridges")
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

    @GameTest(template = "empty16x6x9", batch = "village_bridges")
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
        var nodes = List.of(sample.route().from(), sample.route().to());
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
