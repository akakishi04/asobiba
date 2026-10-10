package io.github.akakishi04.asobibatweaks.feature;

import java.util.ArrayList;
import java.util.List;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.tags.FluidTags;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.HorizontalDirectionalBlock;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.state.properties.BlockStateProperties;
import net.minecraft.world.level.levelgen.Heightmap;

/** Bounded diagonal water strips and naturally founded, short dry ravine spans. */
final class VillageSpanBridgeService {
    static final String TEMPLATE = "supported_span_v1";
    private static final int MAX_LENGTH = 12;
    private static final int MAX_DEPTH = 8;

    private VillageSpanBridgeService() {}

    record Geometry(BlockPos first, int dx, int dz, int length, int width, boolean water) {
        int deckY() { return first.getY() + (water ? 3 : 0); }
        boolean diagonal() { return dx != 0 && dz != 0; }
        BlockPos row(int n) { return first.offset(dx * n, 0, dz * n); }
        BlockPos lane(int n, int offset) {
            BlockPos row = row(n);
            // Match the parent road's lane axis, including negative directions.
            return dx != 0 ? row.offset(0, 0, offset) : row.offset(offset, 0, 0);
        }
        int base() { return width == 3 ? -1 : 0; }
    }

    /** Returns the first index beyond a queued gap, zero for ordinary dry terrain,
     * or -1 for an observed but unsafe/unknown gap. Never loads a chunk. */
    static int queueGapAt(ServerLevel level, VillageSavedData data,
                          VillageSavedData.RouteRecord route,
                          VillageSavedData.ProjectRecord parent, BlockPos start,
                          int dx, int dz, int index, int distance) {
        if (index < 1) return 0;
        BlockPos previous = start.offset(dx * (index - 1), 0, dz * (index - 1));
        BlockPos current = start.offset(dx * index, 0, dz * index);
        Integer bankY = surfaceY(level, previous), currentY = surfaceY(level, current);
        if (bankY == null || currentY == null) return -1;
        if (currentY >= bankY - 1) return 0;
        BlockPos bank = atY(previous, bankY);
        if (!natural(level.getBlockState(bank))) return -1;
        for (int n = 1; n <= MAX_LENGTH && index + n <= distance; n++) {
            BlockPos ahead = start.offset(dx * (index + n), 0, dz * (index + n));
            Integer y = surfaceY(level, ahead);
            if (y == null) return -1;
            if (y < bankY - 1) continue;
            if (y != bankY || n < 2 || index < 3 || distance - index - n < 2) return -1;
            Geometry shape = new Geometry(atY(current, bankY), dx, dz, n,
                    dx != 0 && dz != 0 ? Math.max(2, route.width()) : route.width(), false);
            return queue(level, data, route, parent, shape) ? index + n + 3 : -1;
        }
        return -1;
    }

    static boolean queue(ServerLevel level, VillageSavedData data,
                         VillageSavedData.RouteRecord route,
                         VillageSavedData.ProjectRecord parent, Geometry shape) {
        if (!parent.parameter("bridge_project_id").isBlank() || !valid(shape)) return false;
        // Foundation elevations are surveyed now and persisted. Reload never
        // rebuilds a blueprint from terrain that construction has already changed.
        List<Integer> foundations = new ArrayList<>();
        for (int row = 0; row < shape.length(); row++) {
            for (int lane = 0; lane < shape.width(); lane++) {
                BlockPos cell = shape.lane(row, shape.base() + lane);
                if (!loadedProbe(level, cell)) return false;
                if (shape.water()) {
                    if (!water(level, cell) || !airAbove(level, cell, 4)) return false;
                } else {
                    Integer floorY = surfaceY(level, cell);
                    if (floorY == null || floorY >= shape.deckY() - 1
                            || shape.deckY() - floorY > MAX_DEPTH
                            || !natural(level.getBlockState(atY(cell, floorY)))
                            || !level.getFluidState(atY(cell, floorY)).isEmpty()
                            || !air(level, atY(cell, shape.deckY()))
                            || !airAbove(level, atY(cell, shape.deckY()), 2)) return false;
                }
            }
            for (int edge : new int[]{shape.base() - 1, shape.base() + shape.width()}) {
                BlockPos outer = shape.lane(row, edge);
                if (!loadedProbe(level, outer)
                        || !air(level, atY(outer, shape.deckY() + 1))) return false;
                if (row % 3 != 0 && row != shape.length() - 1) continue;
                int bottom;
                if (shape.water()) {
                    if (!water(level, outer) || !airAbove(level, outer, 4)) return false;
                    bottom = shape.first().getY();
                } else {
                    Integer groundY = surfaceY(level, outer);
                    if (groundY == null || groundY >= shape.deckY()
                            || shape.deckY() - groundY > MAX_DEPTH
                            || !natural(level.getBlockState(atY(outer, groundY)))) return false;
                    bottom = groundY + 1;
                    for (int y = bottom; y <= shape.deckY(); y++)
                        if (!air(level, atY(outer, y))) return false;
                }
                foundations.add(bottom);
            }
        }
        for (int side : new int[]{-1, 1}) {
            for (int n = 1; n <= 3; n++) {
                int row = side < 0 ? -n : shape.length() - 1 + n;
                for (int lane = 0; lane < shape.width(); lane++) {
                    BlockPos bank = shape.lane(row, shape.base() + lane);
                    if (!loadedProbe(level, bank) || !natural(level.getBlockState(bank))
                            || !airAbove(level, bank, shape.water() ? 4 : 2)) return false;
                }
            }
        }
        var bridge = data.createProject(parent.villageId(), "road", 55, shape.row(-3));
        bridge.setTemplateId(TEMPLATE);
        bridge.setAnchor(shape.row(shape.length() + 2));
        bridge.setLeadCarpenterId(parent.leadCarpenterId());
        bridge.setParameter("bridge_first_water", Long.toString(shape.first().asLong()));
        bridge.setParameter("span_dx", Integer.toString(shape.dx()));
        bridge.setParameter("span_dz", Integer.toString(shape.dz()));
        bridge.setParameter("bridge_length", Integer.toString(shape.length()));
        bridge.setParameter("bridge_width", Integer.toString(shape.width()));
        bridge.setParameter("span_water", Boolean.toString(shape.water()));
        bridge.setParameter("bridge_plank", parent.parameter("plank"));
        bridge.setParameter("bridge_style", "stone".equals(parent.parameter("road_quality"))
                ? "stone" : shape.width() >= 2 ? "mixed" : "wood");
        bridge.setParameter("bridge_parent_road", parent.id().toString());
        bridge.setParameter("route_id", route.id().toString());
        for (int n = 0; n < foundations.size(); n++)
            bridge.setParameter("span_foundation_" + n, Integer.toString(foundations.get(n)));
        List<VillageBridgeService.Step> plan = steps(bridge);
        if (plan.isEmpty()) {
            bridge.setPhase("cancelled");
            data.touch();
            return false;
        }
        for (var step : plan) {
            String key = VillageStorageService.itemKey(step.material());
            bridge.setReservation(key, bridge.reservations().getOrDefault(key, 0) + 1);
        }
        bridge.setPhase("piers");
        parent.setParameter("bridge_project_id", bridge.id().toString());
        parent.setPhase("waiting_for_bridge");
        parent.setPausedReason("constructing supported crossing");
        data.touch();
        return true;
    }

    static List<VillageBridgeService.Step> steps(VillageSavedData.ProjectRecord project) {
        Geometry shape = geometry(project);
        if (shape == null) return List.of();
        Block wood = VillageBridgeService.plank(project.parameter("bridge_plank"));
        boolean stone = "stone".equals(project.parameter("bridge_style"));
        Block deck = stone ? Blocks.COBBLESTONE : wood;
        Block wall = "wood".equals(project.parameter("bridge_style"))
                ? VillageBridgeService.fenceForPlank(wood) : Blocks.COBBLESTONE_WALL;
        Block stairs = stone ? Blocks.COBBLESTONE_STAIRS : VillageSimulationEvents.stairsForPlank(wood);
        List<VillageBridgeService.Step> result = new ArrayList<>();
        int foundation = 0;
        for (int row = 0; row < shape.length(); row++) {
            if (row % 3 != 0 && row != shape.length() - 1) continue;
            for (int edge : new int[]{shape.base() - 1, shape.base() + shape.width()}) {
                int bottom = number(project.parameter("span_foundation_" + foundation++), Integer.MIN_VALUE);
                if (bottom > shape.deckY() || bottom < shape.deckY() - MAX_DEPTH
                        || shape.water() && bottom != shape.first().getY()) return List.of();
                for (int y = bottom; y <= shape.deckY(); y++) {
                    boolean wet = shape.water() && y == shape.first().getY();
                    BlockState state = wall.defaultBlockState();
                    if (wet) state = state.setValue(BlockStateProperties.WATERLOGGED, true);
                    result.add(new VillageBridgeService.Step(atY(shape.lane(row, edge), y),
                            state, wall.asItem(), "piers", wet));
                }
            }
        }
        if (shape.water()) {
            Direction along = shape.dx() > 0 ? Direction.EAST : shape.dx() < 0 ? Direction.WEST
                    : shape.dz() > 0 ? Direction.SOUTH : Direction.NORTH;
            for (boolean far : new boolean[]{false, true}) {
                for (int n = 2; n >= 1; n--) {
                    int row = far ? shape.length() - 1 + n : -n;
                    int top = shape.first().getY() + (n == 2 ? 1 : 2);
                    for (int lane = 0; lane < shape.width(); lane++) {
                        BlockPos cell = shape.lane(row, shape.base() + lane);
                        for (int y = shape.first().getY() + 1; y < top; y++)
                            result.add(step(atY(cell, y), deck.defaultBlockState(), "approach_foundation"));
                        result.add(step(atY(cell, top), stairs.defaultBlockState().setValue(
                                HorizontalDirectionalBlock.FACING, far ? along.getOpposite() : along), "approach_stairs"));
                    }
                }
            }
        }
        for (int row = 0; row < shape.length(); row++) {
            for (int lane = 0; lane < shape.width(); lane++)
                result.add(step(atY(shape.lane(row, shape.base() + lane), shape.deckY()),
                        deck.defaultBlockState(), "deck"));
        }
        for (int row = 0; row < shape.length(); row++) {
            for (int edge : new int[]{shape.base() - 1, shape.base() + shape.width()})
                result.add(step(atY(shape.lane(row, edge), shape.deckY() + 1),
                        wall.defaultBlockState(), "railings"));
        }
        return result.size() <= 256 ? List.copyOf(result) : List.of();
    }

    static boolean environmentIntact(ServerLevel level, VillageSavedData.ProjectRecord project) {
        Geometry shape = geometry(project);
        if (shape == null) return false;
        for (int row = 0; row < shape.length(); row++) {
            for (int lane = 0; lane < shape.width(); lane++) {
                BlockPos cell = shape.lane(row, shape.base() + lane);
                if (!VillageSimulationScheduler.isChunkLoaded(level, cell)) return false;
                if (!airAbove(level, atY(cell, shape.deckY()), 2)) return false;
                if (shape.water() && (!water(level, cell) || !airAbove(level, cell, 2))) return false;
            }
        }
        if (!shape.water()) {
            int foundation = 0;
            for (int row = 0; row < shape.length(); row++) {
                if (row % 3 != 0 && row != shape.length() - 1) continue;
                for (int edge : new int[]{shape.base() - 1, shape.base() + shape.width()}) {
                    int bottom = number(project.parameter("span_foundation_" + foundation++), Integer.MIN_VALUE);
                    BlockPos ground = atY(shape.lane(row, edge), bottom - 1);
                    if (!VillageSimulationScheduler.isChunkLoaded(level, ground)
                            || !natural(level.getBlockState(ground))) return false;
                }
            }
        }
        return true;
    }

    private static VillageBridgeService.Step step(BlockPos pos, BlockState state, String stage) {
        return new VillageBridgeService.Step(pos, state, state.getBlock().asItem(), stage, false);
    }
    private static Geometry geometry(VillageSavedData.ProjectRecord project) {
        if (!TEMPLATE.equals(project.templateId())) return null;
        try {
            Geometry result = new Geometry(BlockPos.of(Long.parseLong(project.parameter("bridge_first_water"))),
                    number(project.parameter("span_dx"), 0), number(project.parameter("span_dz"), 0),
                    number(project.parameter("bridge_length"), 0), number(project.parameter("bridge_width"), 0),
                    "true".equals(project.parameter("span_water")));
            return valid(result) ? result : null;
        } catch (NumberFormatException ignored) { return null; }
    }
    private static boolean valid(Geometry shape) {
        return shape != null && Math.abs(shape.dx()) <= 1 && Math.abs(shape.dz()) <= 1
                && (shape.dx() != 0 || shape.dz() != 0) && shape.length() >= 2
                && shape.length() <= MAX_LENGTH
                && shape.width() >= (shape.diagonal() && shape.water() ? 3 : shape.diagonal() ? 2 : 1)
                && shape.width() <= 3;
    }
    private static Integer surfaceY(ServerLevel level, BlockPos pos) {
        if (!loadedProbe(level, pos)) return null;
        return level.getHeight(Heightmap.Types.MOTION_BLOCKING_NO_LEAVES, pos.getX(), pos.getZ()) - 1;
    }
    private static boolean loadedProbe(ServerLevel level, BlockPos pos) {
        return VillageSimulationScheduler.isChunkLoaded(level, pos)
                && VillageSimulationScheduler.tryConsumeBlockProbe(level);
    }
    private static boolean air(ServerLevel level, BlockPos pos) {
        return level.getBlockState(pos).isAir() && level.getFluidState(pos).isEmpty();
    }
    private static boolean airAbove(ServerLevel level, BlockPos pos, int height) {
        for (int y = 1; y <= height; y++) if (!air(level, pos.above(y))) return false;
        return true;
    }
    private static boolean water(ServerLevel level, BlockPos pos) {
        return level.getFluidState(pos).is(FluidTags.WATER) && level.getFluidState(pos).isSource();
    }
    private static BlockPos atY(BlockPos pos, int y) { return new BlockPos(pos.getX(), y, pos.getZ()); }
    private static boolean natural(BlockState state) {
        return state.is(Blocks.STONE) || state.is(Blocks.COBBLESTONE) || state.is(Blocks.DIRT)
                || state.is(Blocks.GRASS_BLOCK) || state.is(Blocks.GRAVEL) || state.is(Blocks.SAND)
                || state.is(Blocks.ANDESITE) || state.is(Blocks.DIORITE) || state.is(Blocks.GRANITE)
                || state.is(Blocks.COARSE_DIRT) || state.is(Blocks.RED_SAND);
    }
    private static int number(String value, int fallback) {
        try { return Integer.parseInt(value); } catch (NumberFormatException ignored) { return fallback; }
    }
}
