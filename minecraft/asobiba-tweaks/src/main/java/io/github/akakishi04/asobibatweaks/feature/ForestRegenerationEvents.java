package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import net.minecraft.core.BlockPos;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.tags.BlockTags;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.Blocks;
import net.neoforged.bus.api.SubscribeEvent;
import net.neoforged.neoforge.event.tick.PlayerTickEvent;

public final class ForestRegenerationEvents {
    @SubscribeEvent
    public void onPlayerTick(PlayerTickEvent.Post event) {
        if (!AsobibaTweaksConfig.FOREST_REGENERATION_ENABLED.getAsBoolean()
                || !(event.getEntity() instanceof ServerPlayer player)
                || player.tickCount % 2400 != Math.floorMod(player.getId(), 2400)
                || player.getRandom().nextDouble() > 0.12D) {
            return;
        }

        ServerLevel level = player.serverLevel();
        VillageSimulationScheduler.enqueueValidation(
                level,
                "forest_regen:" + player.getUUID(),
                () -> {
                    if (!player.isAlive() || player.isRemoved() || player.level() != level) return;
                    regenerateNearPlayer(player, level);
                }
        );
    }

    private static void regenerateNearPlayer(ServerPlayer player, ServerLevel level) {
        for (int attempt = 0; attempt < 12; attempt++) {
            int dx = player.getRandom().nextInt(65) - 32;
            int dz = player.getRandom().nextInt(65) - 32;
            int x = player.blockPosition().getX() + dx;
            int z = player.blockPosition().getZ() + dz;
            BlockPos column = new BlockPos(x, level.getMinBuildHeight(), z);
            if (!VillageSimulationScheduler.isChunkLoaded(level, column)) continue;
            if (!VillageSimulationScheduler.tryConsumeBlockProbe(level)) return;

            int y = level.getHeight(net.minecraft.world.level.levelgen.Heightmap.Types.MOTION_BLOCKING_NO_LEAVES, x, z);
            BlockPos ground = new BlockPos(x, y - 1, z);
            BlockPos plant = ground.above();

            if (VillageBuildingService.isMaintainedVillageSpace(level, plant, 5)) continue;

            if (!level.getBlockState(plant).isAir()
                    || !(level.getBlockState(ground).is(Blocks.GRASS_BLOCK)
                    || level.getBlockState(ground).is(Blocks.DIRT)
                    || level.getBlockState(ground).is(Blocks.COARSE_DIRT))) {
                continue;
            }

            if (!safeRegrowthSite(level, plant)) continue;
            Block sapling = nearbyTreeSapling(level, plant, player);
            if (sapling == null) continue;

            String biome = level.getBiome(plant).unwrapKey()
                    .map(k -> k.location().getPath()).orElse("");
            if (!(biome.contains("forest") || biome.contains("taiga")
                    || biome.contains("grove") || biome.contains("wood"))) {
                continue;
            }

            level.setBlockAndUpdate(plant, sapling.defaultBlockState());
            return;
        }
    }

    /**
     * A bounded loaded-only check prevents unmanaged background forest growth
     * from invading player gardens, roads and workshops outside recognized
     * villages. The visual signal is intentionally conservative: this is not
     * an ownership claim on every natural dirt or stone block.
     */
    static boolean safeRegrowthSite(ServerLevel level, BlockPos plant) {
        if (!VillageSimulationScheduler.isAreaLoaded(level,
                plant.offset(-2, -1, -2), plant.offset(2, 2, 2))
                || !level.getBlockState(plant).isAir()) return false;
        BlockState soil = level.getBlockState(plant.below());
        if (!soil.is(Blocks.GRASS_BLOCK) && !soil.is(Blocks.DIRT)
                && !soil.is(Blocks.COARSE_DIRT)) return false;

        for (int dx = -2; dx <= 2; dx++) {
            for (int dz = -2; dz <= 2; dz++) {
                for (int dy = -1; dy <= 2; dy++) {
                    if (!VillageSimulationScheduler.tryConsumeBlockProbe(level))
                        return false; // exhausted shared background budget
                    BlockState state = level.getBlockState(plant.offset(dx, dy, dz));
                    if (isMaintainedSurface(state)) return false;
                }
            }
        }
        return true;
    }

    /** Pure maintained-surface classification, independent of scheduling budgets. */
    static boolean isMaintainedSurface(BlockState state) {
        return state.is(BlockTags.PLANKS)
                || state.is(BlockTags.FENCES)
                || state.is(BlockTags.DOORS)
                || state.is(Blocks.COBBLESTONE)
                || state.is(Blocks.STONE_BRICKS)
                || state.is(Blocks.DIRT_PATH)
                || state.is(Blocks.FARMLAND)
                || state.is(Blocks.CRAFTING_TABLE)
                || state.is(Blocks.CHEST)
                || state.is(Blocks.BARREL)
                || state.is(Blocks.FURNACE)
                || state.is(Blocks.TORCH)
                || state.is(Blocks.LANTERN)
                || state.is(Blocks.CAMPFIRE)
                || state.is(Blocks.RAIL)
                || state.is(Blocks.GLASS)
                || state.is(Blocks.GLASS_PANE);
    }

    private static Block nearbyTreeSapling(ServerLevel level, BlockPos center, ServerPlayer player) {
        BlockPos min = center.offset(-7, -2, -7);
        BlockPos max = center.offset(7, 8, 7);
        if (!VillageSimulationScheduler.isAreaLoaded(level, min, max)) return null;

        Block seenLog = null;
        int leaves = 0;

        // Sampling is intentionally bounded; this is background ecology, not a full forest census.
        for (int sample = 0; sample < 96; sample++) {
            if (!VillageSimulationScheduler.tryConsumeBlockProbe(level)) return null;
            BlockPos pos = center.offset(
                    player.getRandom().nextInt(15) - 7,
                    player.getRandom().nextInt(11) - 2,
                    player.getRandom().nextInt(15) - 7
            );
            var state = level.getBlockState(pos);
            if (state.is(BlockTags.LEAVES)) {
                leaves++;
            } else if (state.is(BlockTags.LOGS) && seenLog == null) {
                seenLog = state.getBlock();
            }
        }

        if (seenLog == null || leaves < 4) return null;
        if (seenLog == Blocks.SPRUCE_LOG) return Blocks.SPRUCE_SAPLING;
        if (seenLog == Blocks.BIRCH_LOG) return Blocks.BIRCH_SAPLING;
        if (seenLog == Blocks.JUNGLE_LOG) return Blocks.JUNGLE_SAPLING;
        if (seenLog == Blocks.ACACIA_LOG) return Blocks.ACACIA_SAPLING;
        if (seenLog == Blocks.DARK_OAK_LOG) return Blocks.DARK_OAK_SAPLING;
        if (seenLog == Blocks.MANGROVE_LOG) return Blocks.MANGROVE_PROPAGULE;
        if (seenLog == Blocks.CHERRY_LOG) return Blocks.CHERRY_SAPLING;
        if (seenLog == Blocks.OAK_LOG) return Blocks.OAK_SAPLING;
        return null;
    }
}
