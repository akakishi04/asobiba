package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import net.minecraft.core.BlockPos;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.chunk.ChunkAccess;
import net.minecraft.world.level.levelgen.Heightmap;
import net.neoforged.bus.api.SubscribeEvent;
import net.neoforged.neoforge.event.level.ChunkEvent;

public final class ContinentalWorldgenEvents {
    @SubscribeEvent
    public void onChunkLoad(ChunkEvent.Load event) {
        if (!AsobibaTweaksConfig.CONTINENTAL_WORLDGEN_ENABLED.getAsBoolean()
                || !event.isNewChunk()
                || !(event.getLevel() instanceof ServerLevel level)
                || level.dimension() != Level.OVERWORLD) {
            return;
        }

        ChunkAccess chunk = event.getChunk();
        if (!chunk.getAllStarts().isEmpty() || !chunk.getAllReferences().isEmpty()) {
            return;
        }

        int sea = level.getSeaLevel();
        int continentScale = AsobibaTweaksConfig.CONTINENT_SCALE.getAsInt();
        int islandScale = AsobibaTweaksConfig.ISLAND_SCALE.getAsInt();
        double oceanBias = AsobibaTweaksConfig.OCEAN_BIAS.getAsDouble();
        double islandThreshold = AsobibaTweaksConfig.ISLAND_THRESHOLD.getAsDouble();
        long seed = level.getSeed();
        int baseX = chunk.getPos().getMinBlockX();
        int baseZ = chunk.getPos().getMinBlockZ();

        for (int lx = 0; lx < 16; lx++) {
            for (int lz = 0; lz < 16; lz++) {
                int x = baseX + lx;
                int z = baseZ + lz;

                double continent = valueNoise(seed ^ 0x5DA77A9B2C13L, x, z, continentScale);
                double island = valueNoise(seed ^ 0x1F123BB5D91EL, x, z, islandScale);

                if (continent >= oceanBias || island >= islandThreshold) {
                    continue;
                }

                double depthFactor = clamp((oceanBias - continent) / 0.42D, 0.0D, 1.0D);
                double shelfNoise = valueNoise(seed ^ 0x741B8AA19EL, x, z, 96);
                int targetFloor = sea - 7 - (int)Math.round(depthFactor * 17.0D + shelfNoise * 3.0D);
                targetFloor = Math.max(level.getMinBuildHeight() + 8, Math.min(sea - 4, targetFloor));

                int top = chunk.getHeight(Heightmap.Types.WORLD_SURFACE_WG, x, z);
                if (top <= targetFloor + 1) {
                    continue;
                }

                for (int y = top; y > targetFloor; y--) {
                    BlockPos pos = new BlockPos(x, y, z);
                    if (y < sea) {
                        chunk.setBlockState(pos, Blocks.WATER.defaultBlockState(), false);
                    } else {
                        chunk.setBlockState(pos, Blocks.AIR.defaultBlockState(), false);
                    }
                    chunk.removeBlockEntity(pos);
                }

                BlockPos floorPos = new BlockPos(x, targetFloor, z);
                BlockState floor = Math.floorMod(hash(seed ^ 0xCC17L, x, z), 5) == 0
                        ? Blocks.GRAVEL.defaultBlockState()
                        : Blocks.SAND.defaultBlockState();
                chunk.setBlockState(floorPos, floor, false);
            }
        }

        chunk.setUnsaved(true);
    }

    private static double valueNoise(long seed, int x, int z, int scale) {
        int gx = Math.floorDiv(x, scale);
        int gz = Math.floorDiv(z, scale);
        double fx = Math.floorMod(x, scale) / (double)scale;
        double fz = Math.floorMod(z, scale) / (double)scale;
        fx = smooth(fx);
        fz = smooth(fz);

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

    private static double clamp(double value, double min, double max) {
        return Math.max(min, Math.min(max, value));
    }
}
