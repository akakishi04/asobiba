package io.github.akakishi04.asobibatweaks.feature;

import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.PriorityQueue;
import net.minecraft.core.BlockPos;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.tags.BlockTags;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.levelgen.Heightmap;

/**
 * Bounded road geometry planner.
 *
 * <p>The search is intentionally coarse and only reads already-loaded chunks. If the complete
 * bounded corridor is not loaded, callers receive no route. They MUST retry once the
 * required chunks become naturally loaded instead of constructing an unchecked straight-line
 * replacement route. The search prefers existing roads, flat ground and gentle
 * slopes, while penalizing water and steep terrain enough that short bridges can win over large
 * detours but long crossings usually do not.</p>
 */
public final class VillageRoadPlanner {
    private static final int GRID = 4;
    private static final int MARGIN = 24;
    private static final int MAX_EXPANSIONS = 6_000;

    private VillageRoadPlanner() {
    }

    public static List<BlockPos> planLoaded(ServerLevel level, BlockPos from, BlockPos to) {
        int minX = Math.min(from.getX(), to.getX()) - MARGIN;
        int maxX = Math.max(from.getX(), to.getX()) + MARGIN;
        int minZ = Math.min(from.getZ(), to.getZ()) - MARGIN;
        int maxZ = Math.max(from.getZ(), to.getZ()) + MARGIN;

        BlockPos areaMin = new BlockPos(minX, level.getMinBuildHeight(), minZ);
        BlockPos areaMax = new BlockPos(maxX, level.getMinBuildHeight(), maxZ);
        if (!VillageSimulationScheduler.isAreaLoaded(level, areaMin, areaMax)) {
            return List.of();
        }

        int targetGx = (int)Math.round((to.getX() - from.getX()) / (double)GRID);
        int targetGz = (int)Math.round((to.getZ() - from.getZ()) / (double)GRID);
        Cell start = new Cell(0, 0);
        Cell goal = new Cell(targetGx, targetGz);
        if (start.equals(goal)) return List.of(from.immutable(), to.immutable());

        int marginCells = Math.max(2, MARGIN / GRID);
        int minGx = Math.min(0, targetGx) - marginCells;
        int maxGx = Math.max(0, targetGx) + marginCells;
        int minGz = Math.min(0, targetGz) - marginCells;
        int maxGz = Math.max(0, targetGz) + marginCells;

        PriorityQueue<SearchNode> open =
                new PriorityQueue<>(Comparator.comparingDouble(SearchNode::fScore));
        Map<Cell, Double> best = new HashMap<>();
        Map<Cell, Cell> previous = new HashMap<>();
        Map<Cell, Integer> heights = new HashMap<>();

        int startY = surfaceY(level, from.getX(), from.getZ());
        heights.put(start, startY);
        best.put(start, 0.0D);
        open.add(new SearchNode(start, 0.0D, heuristic(start, goal)));

        Cell reached = null;
        int expansions = 0;
        int[][] directions = {
                {1, 0}, {-1, 0}, {0, 1}, {0, -1},
                {1, 1}, {1, -1}, {-1, 1}, {-1, -1}
        };

        while (!open.isEmpty() && expansions++ < MAX_EXPANSIONS) {
            SearchNode currentNode = open.poll();
            Cell current = currentNode.cell();
            double known = best.getOrDefault(current, Double.POSITIVE_INFINITY);
            if (currentNode.gScore() > known + 1.0E-6D) continue;
            if (current.equals(goal)) {
                reached = current;
                break;
            }

            int currentY = heights.computeIfAbsent(
                    current, cell -> surfaceY(level, worldX(from, cell), worldZ(from, cell)));

            for (int[] direction : directions) {
                Cell next = new Cell(current.gx() + direction[0], current.gz() + direction[1]);
                if (next.gx() < minGx || next.gx() > maxGx
                        || next.gz() < minGz || next.gz() > maxGz) {
                    continue;
                }

                int worldX = worldX(from, next);
                int worldZ = worldZ(from, next);
                BlockPos column = new BlockPos(worldX, level.getMinBuildHeight(), worldZ);
                if (!VillageSimulationScheduler.isChunkLoaded(level, column)) continue;

                Terrain terrain = terrain(level, worldX, worldZ, currentY);
                heights.put(next, terrain.surfaceY());
                double diagonal = direction[0] != 0 && direction[1] != 0 ? 1.41421356237D : 1.0D;
                double candidate = known + terrain.cost() * diagonal;
                if (candidate + 1.0E-6D >= best.getOrDefault(next, Double.POSITIVE_INFINITY)) continue;

                best.put(next, candidate);
                previous.put(next, current);
                double f = candidate + heuristic(next, goal);
                open.add(new SearchNode(next, candidate, f));
            }
        }

        if (reached == null) return List.of();

        List<Cell> cells = new ArrayList<>();
        for (Cell cursor = reached; cursor != null; cursor = previous.get(cursor)) {
            cells.add(cursor);
            if (cursor.equals(start)) break;
        }
        Collections.reverse(cells);
        if (cells.isEmpty() || !cells.get(0).equals(start)) {
            return List.of();
        }

        return compress(from, to, cells);
    }

    private static List<BlockPos> compress(BlockPos from, BlockPos to, List<Cell> cells) {
        List<BlockPos> result = new ArrayList<>();
        result.add(from.immutable());
        int previousDx = 0;
        int previousDz = 0;

        for (int i = 1; i < cells.size(); i++) {
            Cell before = cells.get(i - 1);
            Cell current = cells.get(i);
            int dx = Integer.signum(current.gx() - before.gx());
            int dz = Integer.signum(current.gz() - before.gz());

            if (i > 1 && (dx != previousDx || dz != previousDz)) {
                int x = worldX(from, before);
                int z = worldZ(from, before);
                result.add(new BlockPos(x, 0, z));
            }
            previousDx = dx;
            previousDz = dz;
        }

        BlockPos last = result.get(result.size() - 1);
        if (last.getX() != to.getX() || last.getZ() != to.getZ()) result.add(to.immutable());
        return result;
    }

    private static Terrain terrain(ServerLevel level, int x, int z, int previousY) {
        int y = surfaceY(level, x, z);
        BlockPos surface = new BlockPos(x, y, z);
        BlockState state = level.getBlockState(surface);

        double base;
        if (state.is(Blocks.DIRT_PATH) || state.is(Blocks.GRAVEL)
                || state.is(Blocks.COBBLESTONE) || state.is(Blocks.STONE)
                || state.is(Blocks.STONE_BRICKS)) {
            base = 0.35D;
        } else if (level.getFluidState(surface).is(net.minecraft.tags.FluidTags.WATER)) {
            base = 8.0D;
        } else if (state.is(Blocks.GRASS_BLOCK) || state.is(Blocks.DIRT)
                || state.is(Blocks.COARSE_DIRT) || state.is(Blocks.SAND)
                || state.is(Blocks.RED_SAND) || state.is(Blocks.MUD)) {
            base = 1.0D;
        } else if (state.is(BlockTags.LOGS) || state.is(BlockTags.LEAVES)) {
            base = 6.0D;
        } else {
            base = 3.0D;
        }

        int slope = Math.abs(y - previousY);
        double slopeCost = slope <= 1 ? slope * 0.8D
                : slope == 2 ? 4.0D
                : 12.0D + (slope - 3) * 5.0D;
        return new Terrain(y, base + slopeCost);
    }

    private static int surfaceY(ServerLevel level, int x, int z) {
        return level.getHeight(Heightmap.Types.MOTION_BLOCKING_NO_LEAVES, x, z) - 1;
    }

    private static int worldX(BlockPos from, Cell cell) {
        return from.getX() + cell.gx() * GRID;
    }

    private static int worldZ(BlockPos from, Cell cell) {
        return from.getZ() + cell.gz() * GRID;
    }

    private static double heuristic(Cell a, Cell b) {
        return Math.hypot(a.gx() - b.gx(), a.gz() - b.gz()) * 0.75D;
    }

    private record Cell(int gx, int gz) {
    }

    private record SearchNode(Cell cell, double gScore, double fScore) {
    }

    private record Terrain(int surfaceY, double cost) {
    }
}
