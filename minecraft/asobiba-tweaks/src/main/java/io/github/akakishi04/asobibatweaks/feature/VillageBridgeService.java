package io.github.akakishi04.asobibatweaks.feature;

import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.tags.FluidTags;
import net.minecraft.world.entity.npc.Villager;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.HorizontalDirectionalBlock;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.state.properties.BlockStateProperties;
import net.minecraft.world.level.levelgen.Heightmap;

/**
 * V88: physically constructed, raised, passable bridge for a genuine short
 * water crossing selected by the existing terrain-cost route planner.
 *
 * Geometry is snapshotted into an ordinary saved Road ProjectRecord, NOT
 * reconstructed from mutable terrain after reload. Supports (including
 * WATERLOGGED piers outside the boat channel) -> bank stair approaches ->
 * elevated deck -> outboard handrails are built progressively from real
 * Carpenter cargo. Missing chunks and player blocks pause safely.
 *
 * This handles aligned, already surveyed 2..12-block crossings only.
 * Unhandled long, diagonal or unsupported water segments are not bulldozed.
 */
public final class VillageBridgeService {
    public static final String TEMPLATE = "bridge_span_v1";
    private static final int MAX_SPAN = 12;
    private static final int MIN_SPAN = 2;
    private static final int MAX_SEGMENT = 96;
    private static final int MAX_STEPS = 256;
    private static final int CARGO_SLOTS = 8;
    private static final String SOURCE = "bridge_first_water";
    private static final String FACING = "bridge_facing";
    private static final String SPAN = "bridge_length";
    private static final String WATER_Y = "bridge_water_y";
    private static final String WIDTH = "bridge_width";
    private static final String STYLE = "bridge_style";
    private static final String PARENT = "bridge_parent_road";
    private static final String PLANK = "bridge_plank";
    private static final String WOOD = "wood";
    private static final String MIXED = "mixed";
    private static final String STONE = "stone";

    private VillageBridgeService() {}

    /** A selected crossing is eligible only when both shore ramps are safe. */
    static Candidate findLoadedCrossing(
            ServerLevel level, List<BlockPos> waypoints, int width) {
        if (waypoints == null || waypoints.size() < 2
                || width < 1 || width > 3) return null;

        for (int segment = 1; segment < waypoints.size(); segment++) {
            BlockPos a = waypoints.get(segment - 1);
            BlockPos b = waypoints.get(segment);
            int dx = b.getX() - a.getX();
            int dz = b.getZ() - a.getZ();
            if ((dx == 0) == (dz == 0)) continue; // cardinal, nonzero only
            int distance = Math.abs(dx) + Math.abs(dz);
            if (distance < MIN_SPAN + 6 || distance > MAX_SEGMENT) continue;
            Direction direction = dx > 0 ? Direction.EAST
                    : dx < 0 ? Direction.WEST : dz > 0
                    ? Direction.SOUTH : Direction.NORTH;
            int run = -1;
            for (int i = 0; i <= distance; i++) {
                BlockPos column = new BlockPos(
                        a.getX() + direction.getStepX() * i,
                        level.getMinBuildHeight(),
                        a.getZ() + direction.getStepZ() * i);
                if (!VillageSimulationScheduler.isChunkLoaded(level, column)
                        || !VillageSimulationScheduler.tryConsumeBlockProbe(level)) break;
                int y = level.getHeight(Heightmap.Types.MOTION_BLOCKING_NO_LEAVES,
                        column.getX(), column.getZ()) - 1;
                BlockPos surface = new BlockPos(column.getX(), y, column.getZ());
                boolean water = sourceWater(level, surface);
                if (water && run < 0) run = i;
                if (!water && run >= 0) {
                    int count = i - run;
                    if (count >= MIN_SPAN && count <= MAX_SPAN
                            && run >= 3 && distance - i >= 2) {
                        BlockPos first = new BlockPos(
                                a.getX() + direction.getStepX() * run, y,
                                a.getZ() + direction.getStepZ() * run);
                        // y at the first actual water, not the bank.
                        int waterY = level.getHeight(
                                Heightmap.Types.MOTION_BLOCKING_NO_LEAVES,
                                first.getX(), first.getZ()) - 1;
                        Candidate checked = validate(level, new Candidate(
                                new BlockPos(first.getX(), waterY, first.getZ()),
                                direction, count, waterY, width));
                        if (checked != null) return checked;
                    }
                    run = -1;
                }
            }
        }
        return null;
    }

    /** Pure bounded geometry check, useful for in-engine GameTests as well. */
    static Candidate validate(ServerLevel level, Candidate candidate) {
        if (candidate == null || candidate.length() < MIN_SPAN
                || candidate.length() > MAX_SPAN || candidate.width() < 1
                || candidate.width() > 3) return null;
        Direction face = candidate.facing();
        if (face.getAxis() == Direction.Axis.Y) return null;
        BlockPos first = candidate.firstWater();
        BlockPos last = first.relative(face, candidate.length() - 1);
        BlockPos start = first.relative(face.getOpposite(), 3);
        BlockPos end = last.relative(face, 3);
        if (!VillageSimulationScheduler.isAreaLoaded(level,
                start.offset(-2, 0, -2), end.offset(2, 0, 2))) return null;
        int waterY = candidate.waterY();

        for (int i = 0; i < candidate.length(); i++) {
            BlockPos center = first.relative(face, i);
            for (int lane = 0; lane < candidate.width(); lane++) {
                BlockPos sample = withY(side(center, face, laneOffset(candidate.width(), lane)), waterY);
                if (!VillageSimulationScheduler.tryConsumeBlockProbe(level)
                        || !sourceWater(level, sample)
                        || !clearHeadroom(level, sample, 4)) return null;
            }
            if (i % 3 == 0 || i == candidate.length() - 1) {
                for (int edge : new int[]{-1, candidate.width()}) {
                    BlockPos sample = withY(side(center, face, edge + laneOffsetBase(candidate.width())), waterY);
                    if (!VillageSimulationScheduler.tryConsumeBlockProbe(level)
                            || !sourceWater(level, sample)
                            || !clearHeadroom(level, sample, 4)) return null;
                }
            }
        }
        for (int shore : new int[]{-1, 1}) {
            for (int n = 1; n <= 3; n++) {
                BlockPos land = shore < 0
                        ? first.relative(face.getOpposite(), n)
                        : last.relative(face, n);
                for (int lane = 0; lane < candidate.width(); lane++) {
                    BlockPos pos = withY(side(land, face, laneOffset(candidate.width(), lane)), waterY);
                    if (!VillageSimulationScheduler.tryConsumeBlockProbe(level)
                            || !naturalBank(level.getBlockState(pos))
                            || !clearHeadroom(level, pos, 4)) return null;
                }
            }
        }
        return candidate;
    }

    /**
     * A route planner has already chosen a water crossing at its actual
     * water/slope construction cost. Only then may a bounded bridge be
     * reserved. Nearby cheap land detours are preferred by that A* search.
     */
    static boolean queueBridge(
            ServerLevel level, VillageSavedData data,
            VillageSavedData.RouteRecord route,
            VillageSavedData.ProjectRecord parent, List<BlockPos> routeNodes) {
        if (route == null || parent == null || routeNodes.size() < 2
                || !parent.parameter("bridge_project_id").isBlank()) return false;
        int width = Math.max(1, Math.min(3, route.width()));
        Candidate candidate = findLoadedCrossing(level, routeNodes, width);
        return queueValidatedBridge(level, data, route, parent, candidate);
    }

    static boolean queueValidatedBridge(
            ServerLevel level, VillageSavedData data,
            VillageSavedData.RouteRecord route,
            VillageSavedData.ProjectRecord parent, Candidate candidate) {
        if (route == null || parent == null || candidate == null
                || !parent.parameter("bridge_project_id").isBlank()) return false;
        VillageSavedData.ProjectRecord bridge = data.createProject(
                parent.villageId(), "road", 55,
                candidate.firstWater().relative(candidate.facing().getOpposite(), 3));
        bridge.setTemplateId(TEMPLATE);
        bridge.setPhase("piers");
        bridge.setWorkCursor(0);
        bridge.setLeadCarpenterId(parent.leadCarpenterId());
        bridge.setAnchor(candidate.firstWater().relative(
                candidate.facing(), candidate.length() + 2));
        bridge.setParameter(SOURCE, Long.toString(candidate.firstWater().asLong()));
        bridge.setParameter(FACING, candidate.facing().getName());
        bridge.setParameter(SPAN, Integer.toString(candidate.length()));
        bridge.setParameter(WATER_Y, Integer.toString(candidate.waterY()));
        bridge.setParameter(WIDTH, Integer.toString(candidate.width()));
        bridge.setParameter(PLANK, parent.parameter("plank"));
        bridge.setParameter(STYLE, "stone".equals(parent.parameter("road_quality"))
                ? STONE : candidate.width() >= 2 ? MIXED : WOOD);
        bridge.setParameter(PARENT, parent.id().toString());
        bridge.setParameter("route_id", route.id().toString());
        parent.setParameter("bridge_project_id", bridge.id().toString());
        parent.setPhase("waiting_for_bridge");
        parent.setPausedReason("constructing raised water crossing");
        List<Step> plan = steps(bridge);
        if (plan.isEmpty()) {
            // Fail safely; do not launch an impossible persistent bridge.
            bridge.setPhase("cancelled");
            parent.setPhase("route_planning");
            parent.setParameter("bridge_project_id", "");
            data.touch();
            return false;
        }
        for (Step step : plan) {
            String key = VillageStorageService.itemKey(step.material());
            bridge.setReservation(key,
                    bridge.reservations().getOrDefault(key, 0) + 1);
        }
        data.touch();
        return true;
    }

    /**
     * Direct short bridges win only when a real loaded land detour would be
     * substantially longer. The route planner already charges elevated
     * water penalties; this threshold avoids building a bridge for a trivial
     * flat-road detour that happens to have equal route cost.
     */
    static boolean preferableToDetour(int directBlocks, int landDetourBlocks) {
        return directBlocks >= 8 && directBlocks <= 48
                && landDetourBlocks >= directBlocks + Math.max(8, directBlocks / 3);
    }

    /**
     * The full shortcut is checked against actual unmodified loaded terrain,
     * not just the small water span. Nothing is acquired or destroyed.
     *
     * Only ordinary natural/road ground and <=1-block slopes are accepted on
     * both dry approaches. Existing buildings/player decorations veto this
     * shortcut, and an unloaded/unknown column is never considered clear.
     */
    static boolean directShortcutSafe(ServerLevel level,
                                      BlockPos from, BlockPos to,
                                      Candidate crossing) {
        if (crossing == null) return false;
        int dx = to.getX() - from.getX();
        int dz = to.getZ() - from.getZ();
        if ((dx == 0) == (dz == 0)) return false;
        int length = Math.abs(dx) + Math.abs(dz);
        if (length < 8 || length > 48 || crossing.width() > 3) return false;
        Direction dir = dx > 0 ? Direction.EAST
                : dx < 0 ? Direction.WEST
                : dz > 0 ? Direction.SOUTH : Direction.NORTH;
        if (dir != crossing.facing()) return false;

        int previousY = Integer.MIN_VALUE;
        boolean reachedWater = false;
        boolean passedWater = false;
        for (int i = 0; i <= length; i++) {
            BlockPos pos = from.relative(dir, i);
            BlockPos column = new BlockPos(pos.getX(),
                    level.getMinBuildHeight(), pos.getZ());
            if (!VillageSimulationScheduler.isChunkLoaded(level, column)
                    || !VillageSimulationScheduler.tryConsumeBlockProbe(level)) return false;
            int y = level.getHeight(Heightmap.Types.MOTION_BLOCKING_NO_LEAVES,
                    pos.getX(), pos.getZ()) - 1;
            BlockPos surface = withY(pos, y);
            boolean wet = sourceWater(level, surface);
            if (wet) {
                if (passedWater || y != crossing.waterY()) return false;
                reachedWater = true;
            } else {
                if (reachedWater) passedWater = true;
                if (Math.abs(y - crossing.waterY()) > 1) return false;
                for (int lane = 0; lane < crossing.width(); lane++) {
                    BlockPos other = side(surface, dir,
                            laneOffset(crossing.width(), lane));
                    if (!VillageSimulationScheduler.isChunkLoaded(level, other)
                            || !VillageSimulationScheduler.tryConsumeBlockProbe(level))
                        return false;
                    int laneY = level.getHeight(
                            Heightmap.Types.MOTION_BLOCKING_NO_LEAVES,
                            other.getX(), other.getZ()) - 1;
                    if (Math.abs(laneY - y) > 1) return false;
                    BlockPos ground = withY(other, laneY);
                    BlockState groundState = level.getBlockState(ground);
                    if (!naturalBank(groundState)
                            && !groundState.is(Blocks.DIRT_PATH)
                            && !groundState.is(Blocks.STONE_BRICKS))
                        return false;
                    if (!clearHeadroom(level, ground, 2)) return false;
                }
            }
            if (previousY != Integer.MIN_VALUE
                    && Math.abs(y - previousY) > 1) return false;
            previousY = y;
        }
        return reachedWater && passedWater;
    }

    static void advance(Villager worker, ServerLevel level,
                        VillageSavedData.ProjectRecord project) {
        VillageSavedData data = VillageSavedData.get(level);
        List<Step> plan = steps(project);
        if (plan.isEmpty()) {
            cancel(data, project, "bridge spec invalid");
            return;
        }
        int index = project.workCursor();
        if (index >= plan.size()) {
            finish(data, level, project, plan);
            return;
        }
        Step step = plan.get(index);
        if (!VillageSimulationScheduler.isChunkLoaded(level, step.position())
                || !VillageSimulationScheduler.tryConsumeWorkerProbe(level)) {
            pause(data, project, "bridge step unloaded/budget unavailable");
            return;
        }

        BlockState old = level.getBlockState(step.position());
        if (old.is(step.state().getBlock())) {
            // Existing water piers count as already complete only if they
            // genuinely remain waterlogged with a real source fluid.
            if (step.waterlogged() && (!old.hasProperty(
                    BlockStateProperties.WATERLOGGED)
                    || !old.getValue(BlockStateProperties.WATERLOGGED)
                    || !sourceWater(level, step.position()))) {
                pause(data, project, "existing pier not waterlogged");
                return;
            }
            advanceCursor(data, level, project, plan, null);
            return;
        }
        if (step.waterlogged()) {
            if (!sourceWater(level, step.position())) {
                pause(data, project, "support water source changed");
                return;
            }
        } else if (!old.isAir() || !level.getFluidState(step.position()).isEmpty()) {
            // Existing soil, player block, or any fluid cannot be replaced.
            pause(data, project, "occupied bridge step; never bulldoze");
            return;
        }
        if (!step.state().canSurvive(level, step.position())) {
            pause(data, project, "bridge structural support changed");
            return;
        }

        // Remain within physical working distance; navigation may move around
        // the shoreline as construction progresses. No block appears at range.
        if (worker.distanceToSqr(step.position().getCenter()) > 7.0D * 7.0D) {
            worker.getNavigation().moveTo(step.position().getX() + 0.5D,
                    step.position().getY() + 0.5D,
                    step.position().getZ() + 0.5D, 0.75D);
            pause(data, project, "carpenter travelling to bridge");
            return;
        }
        Item item = step.material();
        boolean ready = VillageCarpenterCraftingService.isCraftedFixture(
                item, plank(project.parameter(PLANK)))
                ? VillageCarpenterCraftingService.ensureFixture(
                        worker, level, item, plank(project.parameter(PLANK)), CARGO_SLOTS)
                : VillageSimulationEvents.ensureCargoItem(
                        worker, level, item, 1, CARGO_SLOTS);
        if (!ready || !VillagerSimData.takeWorkCargo(
                worker, level.registryAccess(), CARGO_SLOTS, item, 1)) {
            pause(data, project, "missing physical bridge materials");
            return;
        }
        if (!level.setBlock(step.position(), step.state(), Block.UPDATE_ALL)) {
            ItemStack overflow = VillagerSimData.insertWorkCargo(
                    worker, level.registryAccess(), new ItemStack(item), CARGO_SLOTS);
            if (!overflow.isEmpty()) worker.spawnAtLocation(overflow);
            pause(data, project, "bridge placement rejected and refunded");
            return;
        }
        advanceCursor(data, level, project, plan, item);
    }

    private static void advanceCursor(VillageSavedData data, ServerLevel level,
                                      VillageSavedData.ProjectRecord project,
                                      List<Step> plan, Item spent) {
        if (spent != null) {
            String key = VillageStorageService.itemKey(spent);
            project.setReservation(key,
                    project.reservations().getOrDefault(key, 0) - 1);
        }
        project.setWorkCursor(project.workCursor() + 1);
        project.setPhase(plan.get(Math.min(project.workCursor(), plan.size() - 1)).stage());
        project.setPausedReason("");
        data.touch();
        if (project.workCursor() >= plan.size()) finish(data, level, project, plan);
    }

    private static void finish(VillageSavedData data, ServerLevel level,
                               VillageSavedData.ProjectRecord project, List<Step> plan) {
        for (Step step : plan) {
            if (!VillageSimulationScheduler.isChunkLoaded(level, step.position())
                    || !level.getBlockState(step.position()).is(step.state().getBlock())
                    || step.waterlogged() && (!level.getBlockState(step.position())
                            .hasProperty(BlockStateProperties.WATERLOGGED)
                            || !level.getBlockState(step.position())
                                    .getValue(BlockStateProperties.WATERLOGGED)
                            || !sourceWater(level, step.position()))) {
                pause(data, project, "physical bridge incomplete");
                return;
            }
        }
        Direction face = direction(project.parameter(FACING));
        BlockPos first = BlockPos.of(Long.parseLong(project.parameter(SOURCE)));
        int waterY = number(project.parameter(WATER_Y), Integer.MIN_VALUE);
        int span = number(project.parameter(SPAN), 0);
        int width = number(project.parameter(WIDTH), 0);
        if (face == null) {
            pause(data, project, "bridge facing missing");
            return;
        }
        for (int i = 0; i < span; i++) {
            for (int lane = 0; lane < width; lane++) {
                BlockPos actual = withY(side(first.relative(face, i), face,
                        laneOffset(width, lane)), waterY);
                if (!sourceWater(level, actual)) {
                    pause(data, project, "boat channel under bridge changed");
                    return;
                }
            }
        }
        project.clearReservations();
        project.setPhase("complete");
        project.setPausedReason("");
        UUID parentId = parseId(project.parameter(PARENT));
        if (parentId != null) {
            VillageSavedData.ProjectRecord parent = data.project(parentId).orElse(null);
            if (parent != null && "waiting_for_bridge".equals(parent.phase())
                    && project.id().toString().equals(parent.parameter("bridge_project_id"))) {
                parent.setPhase("roadwork");
                parent.setPausedReason("");
            }
        }
        data.touch();
    }

    /** Deterministic plan rebuilt only from the saved geometry and palette. */
    static List<Step> steps(VillageSavedData.ProjectRecord project) {
        if (!TEMPLATE.equals(project.templateId())) return List.of();
        Direction dir = direction(project.parameter(FACING));
        int count = number(project.parameter(SPAN), 0);
        int width = number(project.parameter(WIDTH), 0);
        int waterY = number(project.parameter(WATER_Y), Integer.MIN_VALUE);
        BlockPos first;
        try {
            first = BlockPos.of(Long.parseLong(project.parameter(SOURCE)));
        } catch (NumberFormatException ex) {
            return List.of();
        }
        if (dir == null || count < MIN_SPAN || count > MAX_SPAN
                || width < 1 || width > 3
                || waterY != first.getY()) return List.of();

        String family = project.parameter(STYLE);
        if (!STONE.equals(family) && !MIXED.equals(family)
                && !WOOD.equals(family)) return List.of();
        Block wood = plank(project.parameter(PLANK));
        Block deck = STONE.equals(family) ? Blocks.COBBLESTONE : wood;
        Block wall = WOOD.equals(family)
                ? fenceForPlank(wood) : Blocks.COBBLESTONE_WALL;
        Block staircase = STONE.equals(family)
                ? Blocks.COBBLESTONE_STAIRS : VillageSimulationEvents.stairsForPlank(wood);
        if (wall == null) return List.of();
        List<Step> result = new ArrayList<>();
        int deckY = waterY + 3;

        // Real piers in outboard water strips: waterlogged at the source
        // elevation and free above it. Never replace the central boat lane.
        for (int i = 0; i < count; i++) {
            if (i % 3 != 0 && i != count - 1) continue;
            BlockPos station = first.relative(dir, i);
            for (int edge : new int[]{-1, width}) {
                BlockPos outer = side(station, dir, edge + laneOffsetBase(width));
                for (int y = waterY; y <= deckY; y++) {
                    boolean waterlogged = y == waterY;
                    BlockState state = wall.defaultBlockState();
                    if (waterlogged) state = state.setValue(
                            BlockStateProperties.WATERLOGGED, true);
                    result.add(new Step(withY(outer, y), state,
                            wall.asItem(), "piers", waterlogged));
                }
            }
        }

        // Both bank ramps rise by one block per shore tile. Actual stairs are
        // paid as crafted items; natural ground remains unchanged beneath.
        for (boolean farBank : new boolean[]{false, true}) {
            BlockPos station = farBank ? first.relative(dir, count - 1) : first;
            Direction out = farBank ? dir : dir.getOpposite();
            Direction uphill = farBank ? dir.getOpposite() : dir;
            for (int n = 2; n >= 1; n--) {
                for (int lane = 0; lane < width; lane++) {
                    BlockPos column = side(station.relative(out, n), dir,
                            laneOffset(width, lane));
                    int top = waterY + (n == 2 ? 1 : 2);
                    for (int y = waterY + 1; y < top; y++) {
                        result.add(new Step(withY(column, y),
                                deck.defaultBlockState(), deck.asItem(),
                                "approach_foundation", false));
                    }
                    BlockState stair = staircase.defaultBlockState()
                            .setValue(HorizontalDirectionalBlock.FACING, uphill);
                    result.add(new Step(withY(column, top), stair,
                            staircase.asItem(), "approach_stairs", false));
                }
            }
        }

        for (int i = 0; i < count; i++) {
            BlockPos across = first.relative(dir, i);
            for (int lane = 0; lane < width; lane++) {
                BlockPos center = side(across, dir, laneOffset(width, lane));
                result.add(new Step(withY(center, deckY),
                        deck.defaultBlockState(), deck.asItem(), "deck", false));
            }
        }
        for (int i = 0; i < count; i++) {
            BlockPos across = first.relative(dir, i);
            for (int edge : new int[]{-1, width}) {
                BlockPos outer = side(across, dir, edge + laneOffsetBase(width));
                result.add(new Step(withY(outer, deckY + 1),
                        wall.defaultBlockState(), wall.asItem(), "railings", false));
            }
        }
        return result.size() <= MAX_STEPS ? List.copyOf(result) : List.of();
    }

    private static BlockPos withY(BlockPos pos, int y) {
        return new BlockPos(pos.getX(), y, pos.getZ());
    }

    private static boolean sourceWater(ServerLevel level, BlockPos pos) {
        return VillageSimulationScheduler.isChunkLoaded(level, pos)
                && level.getFluidState(pos).is(FluidTags.WATER)
                && level.getFluidState(pos).isSource();
    }

    private static boolean clearHeadroom(ServerLevel level, BlockPos surface, int height) {
        for (int y = 1; y <= height; y++) {
            if (!level.getBlockState(surface.above(y)).isAir()) return false;
        }
        return true;
    }

    private static boolean naturalBank(BlockState state) {
        return state.is(Blocks.STONE) || state.is(Blocks.COBBLESTONE)
                || state.is(Blocks.GRASS_BLOCK) || state.is(Blocks.DIRT)
                || state.is(Blocks.COARSE_DIRT) || state.is(Blocks.GRAVEL)
                || state.is(Blocks.SAND) || state.is(Blocks.RED_SAND)
                || state.is(Blocks.ANDESITE) || state.is(Blocks.DIORITE)
                || state.is(Blocks.GRANITE);
    }

    private static int laneOffsetBase(int width) {
        return width == 3 ? -1 : 0;
    }

    private static int laneOffset(int width, int lane) {
        return lane + laneOffsetBase(width);
    }

    private static BlockPos side(BlockPos pos, Direction facing, int offset) {
        return pos.relative(facing.getClockWise(), offset);
    }

    static Block plank(String family) {
        return switch (family) {
            case "spruce" -> Blocks.SPRUCE_PLANKS;
            case "birch" -> Blocks.BIRCH_PLANKS;
            case "jungle" -> Blocks.JUNGLE_PLANKS;
            case "acacia" -> Blocks.ACACIA_PLANKS;
            case "dark_oak" -> Blocks.DARK_OAK_PLANKS;
            case "mangrove" -> Blocks.MANGROVE_PLANKS;
            case "cherry" -> Blocks.CHERRY_PLANKS;
            default -> Blocks.OAK_PLANKS;
        };
    }

    static Block fenceForPlank(Block plank) {
        if (plank == Blocks.SPRUCE_PLANKS) return Blocks.SPRUCE_FENCE;
        if (plank == Blocks.BIRCH_PLANKS) return Blocks.BIRCH_FENCE;
        if (plank == Blocks.JUNGLE_PLANKS) return Blocks.JUNGLE_FENCE;
        if (plank == Blocks.ACACIA_PLANKS) return Blocks.ACACIA_FENCE;
        if (plank == Blocks.DARK_OAK_PLANKS) return Blocks.DARK_OAK_FENCE;
        if (plank == Blocks.MANGROVE_PLANKS) return Blocks.MANGROVE_FENCE;
        if (plank == Blocks.CHERRY_PLANKS) return Blocks.CHERRY_FENCE;
        return Blocks.OAK_FENCE;
    }

    private static Direction direction(String raw) {
        return switch (raw) {
            case "east" -> Direction.EAST;
            case "west" -> Direction.WEST;
            case "north" -> Direction.NORTH;
            case "south" -> Direction.SOUTH;
            default -> null;
        };
    }

    private static int number(String raw, int fallback) {
        try {
            return Integer.parseInt(raw);
        } catch (NumberFormatException ignored) {
            return fallback;
        }
    }

    private static UUID parseId(String raw) {
        try {
            return UUID.fromString(raw);
        } catch (IllegalArgumentException | NullPointerException ignored) {
            return null;
        }
    }

    private static void pause(VillageSavedData data,
                              VillageSavedData.ProjectRecord project, String reason) {
        project.setPausedReason(reason);
        data.touch();
    }

    private static void cancel(VillageSavedData data,
                               VillageSavedData.ProjectRecord project, String reason) {
        project.setPhase("cancelled");
        project.clearReservations();
        project.setPausedReason(reason);
        data.touch();
    }

    record Candidate(BlockPos firstWater, Direction facing, int length, int waterY, int width) {}
    record Step(BlockPos position, BlockState state, Item material,
                String stage, boolean waterlogged) {}
}
