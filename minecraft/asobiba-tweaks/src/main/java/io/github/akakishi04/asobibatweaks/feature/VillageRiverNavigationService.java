package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.PriorityQueue;
import java.util.UUID;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.tags.FluidTags;

/**
 * Strict, loaded-only river navigation between two ALREADY-BUILT docks.
 *
 * This represents actual checked source-water cells, not interpolated land
 * endpoints or an abstract instant-transfer connection. No item, boat or
 * village entity is created here: use the saved waterway RouteRecord for
 * later physical transportation only.
 */
public final class VillageRiverNavigationService {
    private static final int MAX_ROUTE_DISTANCE = 192;
    private static final int MAX_EXPANSIONS = 1600;
    private static final int MAX_PROBES = 6500;
    private static final int MAX_PATH_CELLS = 512;
    private static final int MAX_WAYPOINTS = 128;
    private static final int DETOUR_MARGIN = 24;
    private static final int[][] CARDINAL = {{1, 0}, {0, 1}, {-1, 0}, {0, -1}};

    private VillageRiverNavigationService() {}

    public static void schedule(ServerLevel level, UUID villageId) {
        if (!enabled()) return;
        VillageSimulationScheduler.enqueueRouteSearch(level,
                "river_route:" + villageId, () -> refresh(level, villageId));
    }

    private static void refresh(ServerLevel level, UUID villageId) {
        if (!enabled()) return;
        VillageSavedData data = VillageSavedData.get(level);
        VillageSavedData.VillageRecord village = data.village(villageId).orElse(null);
        if (village == null || !"active".equals(village.lifecycle())) return;

        List<VillageSavedData.WorkSiteRecord> docks = data.workSitesForVillage(villageId)
                .stream()
                .filter(s -> "river_dock".equals(s.type()) && "active".equals(s.state()))
                .sorted(Comparator.comparing(s -> s.id().toString()))
                .limit(2).toList();
        if (docks.size() != 2) return;

        BlockPos first = dockWater(level, data, docks.get(0));
        BlockPos second = dockWater(level, data, docks.get(1));
        if (first == null || second == null || first.getY() != second.getY()
                || first.distManhattan(second) > MAX_ROUTE_DISTANCE) return;

        VillageSavedData.RouteRecord existing = null;
        for (UUID routeId : village.routeIds()) {
            VillageSavedData.RouteRecord route = data.route(routeId).orElse(null);
            if (route == null || !"river".equals(route.type())) continue;
            boolean matches = (route.from().equals(first) && route.to().equals(second))
                    || (route.from().equals(second) && route.to().equals(first));
            if (matches) {
                existing = route;
                break;
            }
        }

        if (existing != null && !existing.waypoints().isEmpty()) {
            Boolean valid = routeStillNavigable(level, existing.waypoints());
            if (Boolean.TRUE.equals(valid)) {
                if (!"active".equals(existing.state())) {
                    existing.setState("active");
                    data.touch();
                }
                return;
            }
            // An unloaded chunk makes the path unknown, not geographically
            // impossible. Suspend boat assignment without inventing repairs.
            if (valid == null) {
                existing.setState("suspended");
                data.touch();
                return;
            }
            existing.setState("inactive");
            data.touch();
        }

        List<BlockPos> path = findLoadedPath(level, first, second);
        if (path.isEmpty()) return;
        if (existing == null) {
            existing = data.createRoute(villageId, "river", first, second);
        }
        data.setRouteWaypoints(existing.id(), path);
        existing.setState("active");
        data.touch();
    }

    private static BlockPos dockWater(ServerLevel level, VillageSavedData data,
                                      VillageSavedData.WorkSiteRecord dock) {
        String text = dock.purpose();
        if (!text.startsWith("dock:")) return null;
        UUID projectId;
        try {
            projectId = UUID.fromString(text.substring("dock:".length()));
        } catch (IllegalArgumentException ignored) {
            return null;
        }
        VillageSavedData.ProjectRecord project = data.project(projectId).orElse(null);
        if (project == null || !VillageRiverDockService.TEMPLATE.equals(project.templateId())
                || !"complete".equals(project.phase())) return null;

        Direction facing = switch (project.parameter("dock_direction")) {
            case "north" -> Direction.NORTH;
            case "south" -> Direction.SOUTH;
            case "east" -> Direction.EAST;
            case "west" -> Direction.WEST;
            default -> null;
        };
        if (facing == null) return null;
        int y;
        try {
            y = Integer.parseInt(project.parameter("dock_water_y"));
        } catch (NumberFormatException ignored) {
            return null;
        }
        BlockPos bank = project.site();
        BlockPos start = new BlockPos(bank.getX() + facing.getStepX() * 3,
                y, bank.getZ() + facing.getStepZ() * 3);
        // A real boat berth must be in open source water, not beneath planks.
        if (!navigable(level, start)) return null;
        return start;
    }

    /**
     * A bounded four-neighbor A* path; each cell is actual water with room
     * overhead and a two-block-wide water neighbor. No diagonal corner cuts.
     */
    static List<BlockPos> findLoadedPath(ServerLevel level, BlockPos start, BlockPos goal) {
        if (start.getY() != goal.getY()
                || start.distManhattan(goal) > MAX_ROUTE_DISTANCE
                || !navigable(level, start) || !navigable(level, goal)) {
            return List.of();
        }

        int minX = Math.min(start.getX(), goal.getX()) - DETOUR_MARGIN;
        int maxX = Math.max(start.getX(), goal.getX()) + DETOUR_MARGIN;
        int minZ = Math.min(start.getZ(), goal.getZ()) - DETOUR_MARGIN;
        int maxZ = Math.max(start.getZ(), goal.getZ()) + DETOUR_MARGIN;
        PriorityQueue<Node> open = new PriorityQueue<>(Comparator
                .comparingInt(Node::f).thenComparingLong(Node::packed));
        Map<Long, Integer> best = new HashMap<>();
        Map<Long, Long> previous = new HashMap<>();
        long initial = start.asLong();
        long destination = goal.asLong();
        best.put(initial, 0);
        open.add(new Node(initial, 0, heuristic(start, goal)));

        int expansions = 0;
        int probes = 0;
        boolean found = false;
        while (!open.isEmpty() && expansions++ < MAX_EXPANSIONS
                && probes < MAX_PROBES) {
            Node current = open.remove();
            int known = best.getOrDefault(current.packed(), Integer.MAX_VALUE);
            if (current.g() != known) continue;
            if (current.packed() == destination) {
                found = true;
                break;
            }

            BlockPos pos = BlockPos.of(current.packed());
            for (int[] direction : CARDINAL) {
                BlockPos next = pos.offset(direction[0], 0, direction[1]);
                if (next.getX() < minX || next.getX() > maxX
                        || next.getZ() < minZ || next.getZ() > maxZ) continue;
                probes++;
                if (!navigable(level, next)) continue;
                int cost = known + 1;
                long key = next.asLong();
                if (cost >= best.getOrDefault(key, Integer.MAX_VALUE)) continue;
                previous.put(key, current.packed());
                best.put(key, cost);
                open.add(new Node(key, cost, cost + heuristic(next, goal)));
            }
        }

        if (!found) return List.of();
        List<BlockPos> reversed = new ArrayList<>();
        long cursor = destination;
        while (reversed.size() <= MAX_PATH_CELLS) {
            reversed.add(BlockPos.of(cursor));
            if (cursor == initial) break;
            Long prior = previous.get(cursor);
            if (prior == null) return List.of();
            cursor = prior;
        }
        if (reversed.size() > MAX_PATH_CELLS || cursor != initial) return List.of();
        Collections.reverse(reversed);
        return compressCorners(reversed);
    }

    private static List<BlockPos> compressCorners(List<BlockPos> cells) {
        if (cells.size() < 2) return List.copyOf(cells);
        List<BlockPos> result = new ArrayList<>();
        result.add(cells.getFirst());
        int previousX = 0;
        int previousZ = 0;
        for (int i = 1; i < cells.size(); i++) {
            BlockPos before = cells.get(i - 1);
            BlockPos after = cells.get(i);
            int dx = after.getX() - before.getX();
            int dz = after.getZ() - before.getZ();
            if (i > 1 && (dx != previousX || dz != previousZ)) result.add(before);
            previousX = dx;
            previousZ = dz;
        }
        result.add(cells.getLast());
        return result.size() <= MAX_WAYPOINTS ? List.copyOf(result) : List.of();
    }

    /** null: unknown/unloaded, false: no longer navigable, true: still water. */
    private static Boolean routeStillNavigable(ServerLevel level, List<BlockPos> points) {
        int steps = 0;
        for (int i = 1; i < points.size(); i++) {
            BlockPos from = points.get(i - 1);
            BlockPos to = points.get(i);
            int dx = Integer.signum(to.getX() - from.getX());
            int dz = Integer.signum(to.getZ() - from.getZ());
            if (from.getY() != to.getY() || (dx != 0 && dz != 0)) return false;
            int count = Math.abs(to.getX() - from.getX())
                    + Math.abs(to.getZ() - from.getZ());
            for (int n = 0; n <= count; n++) {
                BlockPos at = from.offset(dx * n, 0, dz * n);
                if (!VillageSimulationScheduler.isChunkLoaded(level, at)) return null;
                if (!navigable(level, at)) return false;
                if (++steps > MAX_PATH_CELLS) return false;
            }
        }
        return points.size() >= 2;
    }

    private static boolean navigable(ServerLevel level, BlockPos pos) {
        if (!VillageSimulationScheduler.isChunkLoaded(level, pos)
                || !level.getFluidState(pos).is(FluidTags.WATER)
                || !level.getFluidState(pos).isSource()
                || !level.getBlockState(pos.above()).isAir()
                || !level.getBlockState(pos.above(2)).isAir()) return false;

        // The boat needs a continuous channel at least two blocks wide.
        for (int[] direction : CARDINAL) {
            BlockPos adjacent = pos.offset(direction[0], 0, direction[1]);
            if (VillageSimulationScheduler.isChunkLoaded(level, adjacent)
                    && level.getFluidState(adjacent).is(FluidTags.WATER)
                    && level.getFluidState(adjacent).isSource()
                    && level.getBlockState(adjacent.above()).isAir()) return true;
        }
        return false;
    }

    private static int heuristic(BlockPos one, BlockPos two) {
        return Math.abs(one.getX() - two.getX()) + Math.abs(one.getZ() - two.getZ());
    }

    private static boolean enabled() {
        return AsobibaTweaksConfig.VILLAGE_SIMULATION_ENABLED.getAsBoolean()
                && AsobibaTweaksConfig.VILLAGE_LOGISTICS_ENABLED.getAsBoolean()
                && AsobibaTweaksConfig.VILLAGE_RIVER_DOCKS_ENABLED.getAsBoolean();
    }

    private record Node(long packed, int g, int f) {}
}
