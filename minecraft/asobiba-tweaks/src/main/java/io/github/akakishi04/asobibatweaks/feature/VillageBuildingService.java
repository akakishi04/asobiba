package io.github.akakishi04.asobibatweaks.feature;

import java.util.HashSet;
import java.util.Set;
import java.util.UUID;
import net.minecraft.core.BlockPos;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.tags.BlockTags;
import net.minecraft.world.Container;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.block.BedBlock;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.state.properties.BedPart;

/**
 * Lazy physical revalidation for indexed BuildingRecords.
 */
public final class VillageBuildingService {
    private VillageBuildingService() {
    }

    public static void revalidateChunk(ServerLevel level, ChunkPos chunk) {
        VillageSavedData data = VillageSavedData.get(level);
        VillageSavedData.ChunkIndexView indexed = data.recordsForChunk(chunk);
        if (indexed.buildingIds().isEmpty() && indexed.storageIds().isEmpty()) return;

        Set<UUID> touchedVillages = new HashSet<>();
        for (UUID buildingId : indexed.buildingIds()) {
            VillageSavedData.BuildingRecord building = data.building(buildingId).orElse(null);
            if (building == null) continue;
            if (!VillageSimulationScheduler.isAreaLoaded(level, building.min(), building.max())) continue;

            if (!revalidateBuilding(level, building)) {
                // Probe budget exhausted; leave it dirty for a later scheduled validation.
                continue;
            }
            touchedVillages.add(building.villageId());
        }

        for (UUID storageId : indexed.storageIds()) {
            data.storage(storageId).ifPresent(storage -> touchedVillages.add(storage.villageId()));
        }
        for (UUID villageId : touchedVillages) {
            VillageStorageService.reconcileVillage(villageId, level);
        }
        if (!touchedVillages.isEmpty()) data.touch();
    }

    private static boolean revalidateBuilding(ServerLevel level, VillageSavedData.BuildingRecord building) {
        int beds = 0;
        int containers = 0;
        int usableInteriorCells = 0;
        int doors = 0;

        BlockPos min = building.min();
        BlockPos max = building.max();
        for (BlockPos pos : BlockPos.betweenClosed(min, max)) {
            if (!VillageSimulationScheduler.tryConsumeBlockProbe(level)) return false;

            BlockState state = level.getBlockState(pos);
            if (state.getBlock() instanceof BedBlock
                    && state.hasProperty(BedBlock.PART)
                    && state.getValue(BedBlock.PART) == BedPart.FOOT) {
                beds++;
            }
            if (state.is(BlockTags.DOORS)) doors++;
            if (level.getBlockEntity(pos) instanceof Container) containers++;

            if (state.isAir()
                    && level.getBlockState(pos.above()).isAir()
                    && level.getBlockState(pos.below()).isFaceSturdy(level, pos.below(), net.minecraft.core.Direction.UP)) {
                usableInteriorCells++;
            }
        }

        String classification = building.classification();
        boolean valid;
        if ("residential".equals(classification)) {
            valid = beds > 0 && usableInteriorCells >= 2;
            building.setValidatedCapacity(valid ? beds : 0);
        } else if ("storage".equals(classification)) {
            valid = containers > 0 && usableInteriorCells >= 1;
            building.setValidatedCapacity(0);
        } else if ("workshop".equals(classification)) {
            valid = usableInteriorCells >= 2;
        } else {
            valid = usableInteriorCells >= 1;
        }

        // Village-built enclosed structures normally have a doorway, but do not invalidate
        // open workshops/shelters solely for lacking a DoorBlock.
        if (building.villageBuilt()
                && ("residential".equals(classification) || "storage".equals(classification))
                && doors == 0) {
            // The current legacy templates intentionally use an open doorway. Treat a missing
            // door block as acceptable as long as usable interior still exists.
            valid &= usableInteriorCells > 0;
        }

        building.setValidationState(valid ? "valid" : "invalid");
        building.setLastValidatedGameTime(level.getGameTime());
        return true;
    }
}
