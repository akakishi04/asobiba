package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import java.util.ArrayList;
import java.util.List;
import net.minecraft.core.BlockPos;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.chunk.ChunkAccess;
import net.minecraft.world.level.levelgen.Heightmap;

/**
 * Deterministic macro drainage for the optional continental world-generation mode.
 *
 * <p>River topology is derived only from seed/world coordinates. Neighboring chunks therefore
 * agree on the same channels without storing a runtime flow graph or simulating currents.</p>
 */
public final class ContinentalRiverGenerator {
    private ContinentalRiverGenerator() {
    }

    public static void carveChunk(ServerLevel level, ChunkAccess chunk) {
        if (!AsobibaTweaksConfig.CONTINENTAL_RIVERS_ENABLED.getAsBoolean()) return;

        double density = AsobibaTweaksConfig.RIVER_DENSITY.getAsDouble();
        int cellSize = clamp((int)Math.round(224.0D / density), 96, 896);
        double widthScale = AsobibaTweaksConfig.RIVER_WIDTH_SCALE.getAsDouble();
        double meander = AsobibaTweaksConfig.RIVER_MEANDER_STRENGTH.getAsDouble();
        double majorFrequency = AsobibaTweaksConfig.MAJOR_RIVER_FREQUENCY.getAsDouble();
        double lakeFrequency = AsobibaTweaksConfig.RIVER_LAKE_FREQUENCY.getAsDouble();
        double waterfallFrequency = AsobibaTweaksConfig.RIVER_WATERFALL_FREQUENCY.getAsDouble();
        double deltaFrequency = AsobibaTweaksConfig.RIVER_DELTA_FREQUENCY.getAsDouble();

        long seed = level.getSeed();
        int sea = level.getSeaLevel();
        int continentScale = AsobibaTweaksConfig.CONTINENT_SCALE.getAsInt();
        double continentThreshold = AsobibaTweaksConfig.OCEAN_BIAS.getAsDouble()
                + AsobibaTweaksConfig.LANDMASS_SEPARATION_BIAS.getAsDouble();

        int baseX = chunk.getPos().getMinBlockX();
        int baseZ = chunk.getPos().getMinBlockZ();

        int minGX = Math.floorDiv(baseX, cellSize) - 2;
        int maxGX = Math.floorDiv(baseX + 15, cellSize) + 2;
        int minGZ = Math.floorDiv(baseZ, cellSize) - 2;
        int maxGZ = Math.floorDiv(baseZ + 15, cellSize) + 2;

        List<DrainageCell> nearbyCells = new ArrayList<>();
        for (int gx = minGX; gx <= maxGX; gx++) {
            for (int gz = minGZ; gz <= maxGZ; gz++) {
                nearbyCells.add(drainageCell(
                        seed, gx, gz, cellSize, continentScale, continentThreshold,
                        widthScale, meander, majorFrequency, lakeFrequency, deltaFrequency));
            }
        }

        for (int lx = 0; lx < 16; lx++) {
            for (int lz = 0; lz < 16; lz++) {
                int x = baseX + lx;
                int z = baseZ + lz;

                RiverSample sample = sampleAt(x, z, continentThreshold, nearbyCells);
                if (!sample.active) continue;

                int top = chunk.getHeight(Heightmap.Types.WORLD_SURFACE_WG, x, z);
                if (top <= level.getMinBuildHeight() + 7 || top < sea - 1) continue;

                double edge = clamp(sample.distance / Math.max(0.75D, sample.halfWidth), 0.0D, 1.0D);
                int centerDepth = clamp(2 + (int)Math.round(sample.halfWidth / 3.5D), 2, 8);
                int depth = Math.max(1, (int)Math.round(centerDepth * (1.0D - edge * 0.65D)));

                int surface = top - 1;
                if (top <= sea + 4 || sample.delta) surface = Math.min(top - 1, sea);

                if (sample.drop > 0.16D
                        && unit01(seed ^ 0x44FA11L, x >> 2, z >> 2) < waterfallFrequency) {
                    surface -= 1 + Math.floorMod(hash(seed ^ 0xA17EL, x, z), 2);
                }

                int bed = Math.max(level.getMinBuildHeight() + 5, surface - depth);
                for (int y = top; y > bed; y--) {
                    BlockPos pos = new BlockPos(x, y, z);
                    if (y <= surface) chunk.setBlockState(pos, Blocks.WATER.defaultBlockState(), false);
                    else chunk.setBlockState(pos, Blocks.AIR.defaultBlockState(), false);
                    chunk.removeBlockEntity(pos);
                }

                BlockPos bedPos = new BlockPos(x, bed, z);
                long sediment = hash(seed ^ 0x77D3L, x, z);
                if (Math.floorMod(sediment, 7) == 0) {
                    chunk.setBlockState(bedPos, Blocks.CLAY.defaultBlockState(), false);
                } else if (Math.floorMod(sediment, 3) == 0) {
                    chunk.setBlockState(bedPos, Blocks.GRAVEL.defaultBlockState(), false);
                } else {
                    chunk.setBlockState(bedPos, Blocks.SAND.defaultBlockState(), false);
                }
            }
        }
    }

    private static RiverSample sampleAt(
            int x,
            int z,
            double continentThreshold,
            List<DrainageCell> nearbyCells) {

        RiverSample best = RiverSample.NONE;
        for (DrainageCell cell : nearbyCells) {
            if (cell.sourcePotential < continentThreshold - 0.08D) continue;

            if (cell.sinkLake) {
                double dx = x - cell.x;
                double dz = z - cell.z;
                double distance = Math.sqrt(dx * dx + dz * dz);
                if (distance <= cell.lakeRadius && (!best.active || distance < best.distance)) {
                    best = new RiverSample(
                            true, distance, cell.lakeRadius, 0.0D, false, true);
                }
            }

            if (!cell.hasDownstream) continue;
            double distance = curveDistance(
                    x, z, cell.x, cell.z, cell.downX, cell.downZ, cell.meanderOffset);
            if (distance > cell.halfWidth) continue;
            if (!best.active || distance < best.distance
                    || (Math.abs(distance - best.distance) < 0.01D && cell.halfWidth > best.halfWidth)) {
                best = new RiverSample(
                        true, distance, cell.halfWidth, cell.drop, cell.delta, false);
            }
        }
        return best;
    }

    private static DrainageCell drainageCell(
            long seed,
            int gx,
            int gz,
            int cellSize,
            int continentScale,
            double continentThreshold,
            double widthScale,
            double meanderStrength,
            double majorFrequency,
            double lakeFrequency,
            double deltaFrequency) {

        int x = cellCenter(seed, gx, gz, cellSize, true);
        int z = cellCenter(seed, gx, gz, cellSize, false);
        double potential = drainagePotential(seed, x, z, continentScale);

        int bestGX = gx;
        int bestGZ = gz;
        double bestPotential = potential;
        for (int dx = -1; dx <= 1; dx++) {
            for (int dz = -1; dz <= 1; dz++) {
                if (dx == 0 && dz == 0) continue;
                int nx = cellCenter(seed, gx + dx, gz + dz, cellSize, true);
                int nz = cellCenter(seed, gx + dx, gz + dz, cellSize, false);
                double candidate = drainagePotential(seed, nx, nz, continentScale);
                if (candidate < bestPotential - 0.012D) {
                    bestPotential = candidate;
                    bestGX = gx + dx;
                    bestGZ = gz + dz;
                }
            }
        }

        boolean hasDownstream = bestGX != gx || bestGZ != gz;
        int downX = hasDownstream ? cellCenter(seed, bestGX, bestGZ, cellSize, true) : x;
        int downZ = hasDownstream ? cellCenter(seed, bestGX, bestGZ, cellSize, false) : z;

        int incoming = directIncomingCount(seed, gx, gz, cellSize, continentScale);
        double majorRoll = unit01(seed ^ 0x991AC3L, gx, gz);
        boolean major = incoming >= 2
                && majorRoll < majorFrequency * Math.min(1.0D, 0.45D + incoming * 0.18D);

        double fullWidth = 3.0D + incoming * 2.25D + (major ? 11.0D : 0.0D);
        fullWidth = clamp(fullWidth * widthScale, 2.0D, 32.0D);

        boolean delta = hasDownstream
                && bestPotential < continentThreshold - 0.02D
                && unit01(seed ^ 0xD311A9L, gx, gz) < deltaFrequency;
        if (delta) fullWidth = Math.min(36.0D, fullWidth * 1.45D);

        double angleDx = downX - x;
        double angleDz = downZ - z;
        double length = Math.max(1.0D, Math.sqrt(angleDx * angleDx + angleDz * angleDz));
        double signed = unit(seed ^ 0xA87C11L, gx, gz);
        double meanderOffset = signed * cellSize * 0.18D * meanderStrength;
        if (hasDownstream) {
            // Prevent the curve from folding back over itself at very high settings.
            meanderOffset = clamp(meanderOffset, -length * 0.35D, length * 0.35D);
        }

        boolean sinkLake = !hasDownstream
                && potential > continentThreshold - 0.05D
                && unit01(seed ^ 0x1A6E55L, gx, gz) < lakeFrequency;
        double lakeRadius = sinkLake
                ? clamp((8.0D + unit01(seed ^ 0x1A6E77L, gx, gz) * 18.0D) * widthScale, 6.0D, 34.0D)
                : 0.0D;

        return new DrainageCell(
                x, z, potential,
                hasDownstream, downX, downZ,
                Math.max(1.0D, fullWidth * 0.5D),
                meanderOffset,
                Math.max(0.0D, potential - bestPotential),
                delta,
                sinkLake,
                lakeRadius
        );
    }

    private static int directIncomingCount(long seed, int gx, int gz, int cellSize, int continentScale) {
        int count = 0;
        for (int dx = -1; dx <= 1; dx++) {
            for (int dz = -1; dz <= 1; dz++) {
                if (dx == 0 && dz == 0) continue;

                int sx = gx + dx;
                int sz = gz + dz;
                int x = cellCenter(seed, sx, sz, cellSize, true);
                int z = cellCenter(seed, sx, sz, cellSize, false);
                double potential = drainagePotential(seed, x, z, continentScale);

                int bestGX = sx;
                int bestGZ = sz;
                double best = potential;
                for (int nx = -1; nx <= 1; nx++) {
                    for (int nz = -1; nz <= 1; nz++) {
                        if (nx == 0 && nz == 0) continue;
                        int cx = cellCenter(seed, sx + nx, sz + nz, cellSize, true);
                        int cz = cellCenter(seed, sx + nx, sz + nz, cellSize, false);
                        double candidate = drainagePotential(seed, cx, cz, continentScale);
                        if (candidate < best - 0.012D) {
                            best = candidate;
                            bestGX = sx + nx;
                            bestGZ = sz + nz;
                        }
                    }
                }
                if (bestGX == gx && bestGZ == gz) count++;
            }
        }
        return count;
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

    private static double curveDistance(
            double px, double pz,
            double ax, double az,
            double bx, double bz,
            double meanderOffset) {

        double vx = bx - ax;
        double vz = bz - az;
        double length = Math.max(1.0D, Math.sqrt(vx * vx + vz * vz));
        double nx = -vz / length;
        double nz = vx / length;

        double best = Double.MAX_VALUE;
        double previousX = ax;
        double previousZ = az;
        final int segments = 8;
        for (int i = 1; i <= segments; i++) {
            double t = i / (double)segments;
            double curve = Math.sin(Math.PI * t) * meanderOffset;
            double x = lerp(ax, bx, t) + nx * curve;
            double z = lerp(az, bz, t) + nz * curve;
            best = Math.min(best, pointSegmentDistance(px, pz, previousX, previousZ, x, z));
            previousX = x;
            previousZ = z;
        }
        return best;
    }

    private static double pointSegmentDistance(
            double px, double pz,
            double ax, double az,
            double bx, double bz) {
        double vx = bx - ax;
        double vz = bz - az;
        double len2 = vx * vx + vz * vz;
        if (len2 <= 0.0001D) {
            double dx = px - ax;
            double dz = pz - az;
            return Math.sqrt(dx * dx + dz * dz);
        }
        double t = ((px - ax) * vx + (pz - az) * vz) / len2;
        t = clamp(t, 0.0D, 1.0D);
        double qx = ax + vx * t;
        double qz = az + vz * t;
        double dx = px - qx;
        double dz = pz - qz;
        return Math.sqrt(dx * dx + dz * dz);
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

    private record DrainageCell(
            int x,
            int z,
            double sourcePotential,
            boolean hasDownstream,
            int downX,
            int downZ,
            double halfWidth,
            double meanderOffset,
            double drop,
            boolean delta,
            boolean sinkLake,
            double lakeRadius
    ) {
    }

    private record RiverSample(
            boolean active,
            double distance,
            double halfWidth,
            double drop,
            boolean delta,
            boolean lake
    ) {
        private static final RiverSample NONE =
                new RiverSample(false, Double.MAX_VALUE, 0.0D, 0.0D, false, false);
    }
}
