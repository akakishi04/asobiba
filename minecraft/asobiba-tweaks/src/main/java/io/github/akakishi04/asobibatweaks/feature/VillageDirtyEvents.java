package io.github.akakishi04.asobibatweaks.feature;

import net.minecraft.core.BlockPos;

import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.level.ChunkPos;
import net.neoforged.bus.api.SubscribeEvent;
import net.neoforged.neoforge.event.level.BlockEvent;
import net.neoforged.neoforge.event.level.ChunkEvent;

/**
 * Lightweight invalidation bridge from physical world edits into the persistent village index.
 *
 * <p>Chunk load callbacks can occur before FULL promotion, so they only enqueue invalidation
 * work for the next bounded level-tick pass.</p>
 */
public final class VillageDirtyEvents {
    @SubscribeEvent
    public void onBlockPlaced(BlockEvent.EntityPlaceEvent event) {
        if (!(event.getLevel() instanceof ServerLevel level)) return;
        enqueueChunkInvalidation(level, new ChunkPos(event.getPos()), "place");

        if (event.getEntity() instanceof Player) {
            BlockPos adoptionPos = event.getPos().immutable();
            VillageSimulationScheduler.enqueueValidation(
                    level,
                    "adopt_building:" + adoptionPos.asLong(),
                    () -> VillageBuildingAdoptionService.tryAdoptNear(level, adoptionPos)
            );
        }
    }

    @SubscribeEvent
    public void onBlockBroken(BlockEvent.BreakEvent event) {
        if (!(event.getLevel() instanceof ServerLevel level)) return;
        enqueueChunkInvalidation(level, new ChunkPos(event.getPos()), "break");
    }

    @SubscribeEvent
    public void onChunkLoaded(ChunkEvent.Load event) {
        if (!(event.getLevel() instanceof ServerLevel level)) return;
        ChunkPos chunk = event.getChunk().getPos();
        enqueueChunkInvalidation(level, chunk, "load");
    }

    private static void enqueueChunkInvalidation(ServerLevel level, ChunkPos chunk, String reason) {
        String key = "dirty_chunk:" + chunk.toLong();
        VillageSimulationScheduler.enqueueValidation(
                level,
                key,
                () -> {
                    VillageSavedData.get(level).invalidateChunk(chunk);
                    VillageBuildingService.revalidateChunk(level, chunk);
                }
        );
    }
}
