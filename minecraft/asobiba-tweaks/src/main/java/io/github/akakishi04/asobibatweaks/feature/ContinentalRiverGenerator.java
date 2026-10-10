package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import net.minecraft.core.BlockPos;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.chunk.ChunkAccess;
import net.minecraft.world.level.levelgen.Heightmap;

/** Seed-defined, chunk-order-independent drainage; no chunk queries or fluid-current simulation. */
public final class ContinentalRiverGenerator {
    static final int MAX_CATCHMENT = 32;
    private ContinentalRiverGenerator() {}

    public static void carveChunk(ServerLevel level, ChunkAccess chunk) {
        if (!AsobibaTweaksConfig.CONTINENTAL_RIVERS_ENABLED.getAsBoolean()) return;
        Settings settings = new Settings(
                clamp((int)Math.round(224.0D / AsobibaTweaksConfig.RIVER_DENSITY.getAsDouble()), 96, 896),
                AsobibaTweaksConfig.CONTINENT_SCALE.getAsInt(),
                AsobibaTweaksConfig.OCEAN_BIAS.getAsDouble()
                        + AsobibaTweaksConfig.LANDMASS_SEPARATION_BIAS.getAsDouble(),
                AsobibaTweaksConfig.RIVER_WIDTH_SCALE.getAsDouble(),
                AsobibaTweaksConfig.RIVER_MEANDER_STRENGTH.getAsDouble(),
                AsobibaTweaksConfig.MAJOR_RIVER_FREQUENCY.getAsDouble(),
                AsobibaTweaksConfig.RIVER_LAKE_FREQUENCY.getAsDouble(),
                AsobibaTweaksConfig.RIVER_WATERFALL_FREQUENCY.getAsDouble(),
                AsobibaTweaksConfig.RIVER_DELTA_FREQUENCY.getAsDouble());
        Drainage drainage = new Drainage(level.getSeed(), level.getSeaLevel(), settings);
        int baseX = chunk.getPos().getMinBlockX();
        int baseZ = chunk.getPos().getMinBlockZ();
        carveChunk(level, chunk, drainage.nearChunk(baseX, baseZ));
    }

    /** Shared production carving loop; package access also permits bounded real-world fixtures. */
    static void carveChunk(ServerLevel level, ChunkAccess chunk, List<DrainageCell> nearbyCells) {
        int baseX = chunk.getPos().getMinBlockX();
        int baseZ = chunk.getPos().getMinBlockZ();
        for (int lx = 0; lx < 16; lx++) {
            for (int lz = 0; lz < 16; lz++) {
                int x = baseX + lx;
                int z = baseZ + lz;
                RiverSample sample = sampleAt(x, z, nearbyCells);
                if (!sample.active) continue;
                // ChunkEvent.Load supplies a LevelChunk. Its live WORLD_SURFACE
                // is updated by the preceding ocean pass; WORLD_SURFACE_WG is
                // not, and would let a river refill already-lowered terrain.
                int top = chunk.getHeight(Heightmap.Types.WORLD_SURFACE, x, z);
                int surface = sample.surface;
                // Never raise water above existing low terrain or create a
                // hanging aqueduct. Such exceptional terrain breaks remain
                // real navigation obstacles; structures are guarded by caller.
                if (!canCarve(top, surface, level.getSeaLevel(), level.getMinBuildHeight())) continue;
                double edge = clamp(sample.distance / Math.max(0.75D, sample.halfWidth), 0.0D, 1.0D);
                int centerDepth = clamp(2 + (int)Math.round(sample.halfWidth / 3.5D), 2, 8);
                int depth = Math.max(1, (int)Math.round(centerDepth * (1.0D - edge * 0.65D)));
                int bed = Math.max(level.getMinBuildHeight() + 5, surface - depth);
                for (int y = top; y > bed; y--) {
                    BlockPos pos = new BlockPos(x, y, z);
                    chunk.setBlockState(pos, y <= surface
                            ? Blocks.WATER.defaultBlockState() : Blocks.AIR.defaultBlockState(), false);
                    chunk.removeBlockEntity(pos);
                }
                long sediment = hash(level.getSeed() ^ 0x77D3L, x, z);
                chunk.setBlockState(new BlockPos(x, bed, z), Math.floorMod(sediment, 7) == 0
                        ? Blocks.CLAY.defaultBlockState() : Math.floorMod(sediment, 3) == 0
                        ? Blocks.GRAVEL.defaultBlockState() : Blocks.SAND.defaultBlockState(), false);
            }
        }
    }

    static boolean canCarve(int terrainTop, int surface, int sea, int minHeight) {
        return terrainTop > minHeight + 7 && terrainTop >= sea - 1 && surface < terrainTop;
    }

    /** Immutable inputs allow seeded tests without changing server config. */
    record Settings(int cellSize, int continentScale, double continentThreshold,
                    double widthScale, double meander, double majorFrequency,
                    double lakeFrequency, double waterfallFrequency, double deltaFrequency) {}

    /** Per-chunk memoization only. No global growing cache or persisted terrain graph. */
    static final class Drainage {
        private final long seed;
        private final int sea;
        private final Settings settings;
        private final Map<Grid, Node> nodes = new HashMap<>();
        private final Map<Grid, Integer> catchments = new HashMap<>();

        Drainage(long seed, int sea, Settings settings) {
            this.seed = seed;
            this.sea = sea;
            this.settings = settings;
        }

        List<DrainageCell> nearChunk(int baseX, int baseZ) {
            List<DrainageCell> result = new ArrayList<>();
            // Reach endpoints are at most one grid step apart; +/-2 also
            // covers bounded meanders and the widest configured lake/channel.
            for (int gx = Math.floorDiv(baseX, settings.cellSize) - 2;
                    gx <= Math.floorDiv(baseX + 15, settings.cellSize) + 2; gx++) {
                for (int gz = Math.floorDiv(baseZ, settings.cellSize) - 2;
                        gz <= Math.floorDiv(baseZ + 15, settings.cellSize) + 2; gz++) {
                    result.add(cell(gx, gz));
                }
            }
            return result;
        }

        private Node node(Grid grid) {
            Node present = nodes.get(grid);
            if (present != null) return present;
            int x = cellCenter(seed, grid.x, grid.z, settings.cellSize, true);
            int z = cellCenter(seed, grid.x, grid.z, settings.cellSize, false);
            double potential = drainagePotential(seed, x, z, settings.continentScale);
            Grid downstream = grid;
            double best = potential;
            for (int dx = -1; dx <= 1; dx++) {
                for (int dz = -1; dz <= 1; dz++) {
                    if (dx == 0 && dz == 0) continue;
                    int nx = cellCenter(seed, grid.x + dx, grid.z + dz, settings.cellSize, true);
                    int nz = cellCenter(seed, grid.x + dx, grid.z + dz, settings.cellSize, false);
                    double candidate = drainagePotential(seed, nx, nz, settings.continentScale);
                    if (candidate < best - 0.012D) {
                        best = candidate;
                        downstream = new Grid(grid.x + dx, grid.z + dz);
                    }
                }
            }
            Node result = new Node(grid, x, z, potential, downstream);
            nodes.put(grid, result);
            return result;
        }

        /**
         * Count actual upstream cells, saturating at 32. Each visited node
         * contributes one, so traversal itself visits at most 32 nodes and
         * probes at most 8 neighbor edges per node. Strict downhill potential
         * forbids cycles. A downstream catchment cannot be smaller than an
         * upstream catchment, including when both saturate at the limit.
         */
        int catchment(int gx, int gz) {
            Grid start = new Grid(gx, gz);
            Integer cached = catchments.get(start);
            if (cached != null) return cached;
            Set<Grid> found = new HashSet<>();
            ArrayDeque<Grid> queue = new ArrayDeque<>();
            found.add(start);
            queue.add(start);
            while (!queue.isEmpty() && found.size() < MAX_CATCHMENT) {
                Grid target = queue.removeFirst();
                for (int dx = -1; dx <= 1 && found.size() < MAX_CATCHMENT; dx++) {
                    for (int dz = -1; dz <= 1 && found.size() < MAX_CATCHMENT; dz++) {
                        if (dx == 0 && dz == 0) continue;
                        Grid candidate = new Grid(target.x + dx, target.z + dz);
                        if (node(candidate).downstream.equals(target) && found.add(candidate)) {
                            queue.addLast(candidate);
                        }
                    }
                }
            }
            catchments.put(start, found.size());
            return found.size();
        }

        DrainageCell cell(int gx, int gz) {
            Node source = node(new Grid(gx, gz));
            Node downstream = node(source.downstream);
            boolean hasDownstream = !source.grid.equals(source.downstream);
            int flow = catchment(gx, gz);
            // Flow-based, monotone width replaces an independent random major
            // river roll at every node. majorFrequency tunes widening onset.
            double width = (3.0D + 2.25D * (Math.sqrt(flow) - 1.0D)
                    + 11.0D * clamp((flow - 1) * settings.majorFrequency / 4.0D, 0.0D, 1.0D))
                    * settings.widthScale;
            width = clamp(width, 2.0D, 32.0D);
            boolean delta = hasDownstream && downstream.potential < settings.continentThreshold - 0.02D
                    && unit01(seed ^ 0xD311A9L, gx, gz) < settings.deltaFrequency;
            if (delta) width = Math.min(36.0D, width * 1.45D);
            double length = Math.max(1.0D, Math.hypot(downstream.x - source.x, downstream.z - source.z));
            double meander = clamp(unit(seed ^ 0xA87C11L, gx, gz) * settings.cellSize * 0.18D
                    * settings.meander, -length * 0.35D, length * 0.35D);
            // A receiving terminal always has a real sink. lakeFrequency only
            // controls optional isolated lakes and the additional lake area.
            boolean sink = !hasDownstream && (flow > 1
                    || unit01(seed ^ 0x1A6E55L, gx, gz) < settings.lakeFrequency);
            double lakeRadius = sink ? clamp((8.0D + Math.sqrt(flow) * 2.0D
                    + unit01(seed ^ 0x1A6E77L, gx, gz) * 18.0D * settings.lakeFrequency)
                    * settings.widthScale, 6.0D, 34.0D) : 0.0D;
            int sourceY = elevation(source.potential);
            int destinationY = elevation(downstream.potential);
            boolean rapids = hasDownstream && sourceY - destinationY >= 3
                    && unit01(seed ^ 0x44FA11L, gx, gz) < settings.waterfallFrequency;
            return new DrainageCell(source.x, source.z, source.potential, hasDownstream,
                    downstream.x, downstream.z, source.downstream.x, source.downstream.z,
                    width * 0.5D, meander, delta, sink, lakeRadius,
                    sourceY, destinationY, rapids, flow);
        }

        private int elevation(double potential) {
            // Shared immutable elevation at every confluence; no dependency
            // on independently decorated column heights or chunk load order.
            return sea - 1 + (int)Math.round(clamp((potential - settings.continentThreshold) * 24.0D, 0.0D, 32.0D));
        }
    }

    static RiverSample sampleAt(int x, int z, List<DrainageCell> cells) {
        RiverSample best = RiverSample.NONE;
        for (DrainageCell cell : cells) {
            if (cell.sinkLake) {
                double distance = Math.hypot(x - cell.x, z - cell.z);
                if (distance <= cell.lakeRadius && better(distance, cell.lakeRadius, cell.sourceY, best)) {
                    best = new RiverSample(true, distance, cell.lakeRadius, cell.sourceY, true);
                }
            }
        }
        // A terminal basin has one water plane throughout its footprint;
        // incoming channel centerlines must not stripe it with higher water.
        if (best.active) return best;
        for (DrainageCell cell : cells) {
            if (!cell.hasDownstream) continue;
            CurveSample curve = curveSample(x, z, cell);
            if (curve.distance > cell.halfWidth) continue;
            int surface = grade(cell, curve.progress);
            if (better(curve.distance, cell.halfWidth, surface, best)) {
                best = new RiverSample(true, curve.distance, cell.halfWidth, surface, false);
            }
        }
        return best;
    }

    private static boolean better(double distance, double width, int surface, RiverSample best) {
        return !best.active || distance < best.distance - 0.00001D
                || (Math.abs(distance - best.distance) < 0.00001D
                    && (surface < best.surface || (surface == best.surface && width > best.halfWidth)));
    }

    static int grade(DrainageCell cell, double progress) {
        double t = clamp(progress, 0.0D, 1.0D);
        if (cell.rapids) {
            int steps = Math.max(1, (cell.sourceY - cell.destinationY + 1) / 2);
            t = Math.floor(t * steps) / steps;
        }
        return (int)Math.round(lerp(cell.sourceY, cell.destinationY, t));
    }

    private static CurveSample curveSample(double px, double pz, DrainageCell cell) {
        double vx = cell.downX - cell.x;
        double vz = cell.downZ - cell.z;
        double length = Math.max(1.0D, Math.hypot(vx, vz));
        double previousX = cell.x;
        double previousZ = cell.z;
        CurveSample best = new CurveSample(Double.MAX_VALUE, 0.0D);
        for (int i = 1; i <= 8; i++) {
            double t = i / 8.0D;
            double curve = Math.sin(Math.PI * t) * cell.meanderOffset;
            double x = lerp(cell.x, cell.downX, t) - vz / length * curve;
            double z = lerp(cell.z, cell.downZ, t) + vx / length * curve;
            double dx = x - previousX;
            double dz = z - previousZ;
            double len2 = dx * dx + dz * dz;
            double fraction = len2 < 0.0001D ? 0.0D
                    : clamp(((px - previousX) * dx + (pz - previousZ) * dz) / len2, 0.0D, 1.0D);
            double distance = Math.hypot(px - previousX - dx * fraction, pz - previousZ - dz * fraction);
            if (distance < best.distance) best = new CurveSample(distance, ((i - 1) + fraction) / 8.0D);
            previousX = x;
            previousZ = z;
        }
        return best;
    }

    private record Grid(int x, int z) {}
    private record Node(Grid grid, int x, int z, double potential, Grid downstream) {}
    private record CurveSample(double distance, double progress) {}
    record DrainageCell(int x, int z, double sourcePotential, boolean hasDownstream,
                        int downX, int downZ, int downGX, int downGZ,
                        double halfWidth, double meanderOffset, boolean delta,
                        boolean sinkLake, double lakeRadius, int sourceY,
                        int destinationY, boolean rapids, int catchment) {}
    record RiverSample(boolean active, double distance, double halfWidth, int surface, boolean lake) {
        private static final RiverSample NONE = new RiverSample(false, Double.MAX_VALUE, 0.0D, 0, false);
    }

    private static double drainagePotential(long seed, int x, int z, int continentScale) {
        double continent = valueNoise(seed ^ 0x5DA77A9B2C13L, x, z, continentScale);
        double relief = valueNoise(seed ^ 0xA7D95E11L, x, z, Math.max(96, continentScale / 5));
        double basin = valueNoise(seed ^ 0x61B3A7D1L, x, z, Math.max(160, continentScale / 2));
        return continent * 0.72D + relief * 0.18D + basin * 0.10D;
    }

    private static int cellCenter(long seed, int gx, int gz, int cellSize, boolean xAxis) {
        long h = hash(seed ^ (xAxis ? 0xC119L : 0xDA31L), gx, gz);
        double jitter = (((h >>> 11) * 0x1.0p-53) - 0.5D) * 0.52D;
        double center = (xAxis ? gx : gz) * (double)cellSize + cellSize * (0.5D + jitter);
        return (int)Math.floor(center);
    }

    private static double valueNoise(long seed, int x, int z, int scale) {
        int gx = Math.floorDiv(x, scale);
        int gz = Math.floorDiv(z, scale);
        double fx = smooth(Math.floorMod(x, scale) / (double)scale);
        double fz = smooth(Math.floorMod(z, scale) / (double)scale);

        double a = unit(seed, gx, gz);
        double b = unit(seed, gx + 1, gz);
        double c = unit(seed, gx, gz + 1);
        double d = unit(seed, gx + 1, gz + 1);
        return lerp(lerp(a, b, fx), lerp(c, d, fx), fz);
    }

    private static double unit(long seed, int x, int z) {
        long h = hash(seed, x, z);
        return ((h >>> 11) * 0x1.0p-53) * 2.0D - 1.0D;
    }

    private static double unit01(long seed, int x, int z) {
        return (unit(seed, x, z) + 1.0D) * 0.5D;
    }

    private static long hash(long seed, int x, int z) {
        long h = seed;
        h ^= (long)x * 0x9E3779B97F4A7C15L;
        h ^= (long)z * 0xC2B2AE3D27D4EB4FL;
        h ^= h >>> 30;
        h *= 0xBF58476D1CE4E5B9L;
        h ^= h >>> 27;
        h *= 0x94D049BB133111EBL;
        h ^= h >>> 31;
        return h;
    }

    private static double smooth(double t) {
        return t * t * (3.0D - 2.0D * t);
    }

    private static double lerp(double a, double b, double t) {
        return a + (b - a) * t;
    }

    private static int clamp(int value, int min, int max) {
        return Math.max(min, Math.min(max, value));
    }

    private static double clamp(double value, double min, double max) {
        return Math.max(min, Math.min(max, value));
    }

}
