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

    public static BlockPos findIndexedShelter(ServerLevel level, BlockPos center, int radius) {
        VillageSavedData data = VillageSavedData.get(level);
        Set<UUID> candidates = new HashSet<>();

        int minChunkX = (center.getX() - radius) >> 4;
        int maxChunkX = (center.getX() + radius) >> 4;
        int minChunkZ = (center.getZ() - radius) >> 4;
        int maxChunkZ = (center.getZ() + radius) >> 4;

        for (int cx = minChunkX; cx <= maxChunkX; cx++) {
            for (int cz = minChunkZ; cz <= maxChunkZ; cz++) {
                candidates.addAll(data.recordsForChunk(new ChunkPos(cx, cz)).buildingIds());
            }
        }

        BlockPos best = null;
        int bestDistance = Integer.MAX_VALUE;
        for (UUID id : candidates) {
            VillageSavedData.BuildingRecord building = data.building(id).orElse(null);
            if (building == null || !"valid".equals(building.validationState())) continue;
            if (!VillageSimulationScheduler.isAreaLoaded(level, building.min(), building.max())) continue;
            if (distanceToBounds(center, building.min(), building.max()) > radius) continue;

            BlockPos cell = firstUsableShelterCell(level, building);
            if (cell == null) continue;
            int distance = center.distManhattan(cell);
            if (distance < bestDistance) {
                bestDistance = distance;
                best = cell;
            }
        }
        return best;
    }

    public static boolean isMaintainedVillageSpace(ServerLevel level, BlockPos pos, int margin) {
        VillageSavedData data = VillageSavedData.get(level);
        int chunkRadius = Math.max(1, (margin + 15) / 16 + 1);
        ChunkPos origin = new ChunkPos(pos);

        Set<UUID> buildingIds = new HashSet<>();
        Set<UUID> workSiteIds = new HashSet<>();
        Set<UUID> routeIds = new HashSet<>();
        for (int dx = -chunkRadius; dx <= chunkRadius; dx++) {
            for (int dz = -chunkRadius; dz <= chunkRadius; dz++) {
                VillageSavedData.ChunkIndexView indexed =
                        data.recordsForChunk(new ChunkPos(origin.x + dx, origin.z + dz));
                buildingIds.addAll(indexed.buildingIds());
                workSiteIds.addAll(indexed.workSiteIds());
                routeIds.addAll(indexed.routeIds());
            }
        }

        for (UUID id : buildingIds) {
            VillageSavedData.BuildingRecord building = data.building(id).orElse(null);
            if (building != null && distanceToBounds(pos, building.min(), building.max()) <= margin) return true;
        }
        for (UUID id : workSiteIds) {
            VillageSavedData.WorkSiteRecord site = data.workSite(id).orElse(null);
            if (site != null && distanceToBounds(pos, site.min(), site.max()) <= margin) return true;
        }
        for (UUID id : routeIds) {
            VillageSavedData.RouteRecord route = data.route(id).orElse(null);
            if (route != null && "active".equals(route.state())
                    && distanceToSegment2D(pos, route.from(), route.to()) <= margin + 2.0D) return true;
        }
        return false;
    }

    private static BlockPos firstUsableShelterCell(ServerLevel level, VillageSavedData.BuildingRecord building) {
        BlockPos min = building.min();
        BlockPos max = building.max();
        int probes = 0;

        for (int y = min.getY(); y <= max.getY(); y++) {
            for (int x = min.getX(); x <= max.getX(); x++) {
                for (int z = min.getZ(); z <= max.getZ(); z++) {
                    if (probes++ >= 96 || !VillageSimulationScheduler.tryConsumeBlockProbe(level)) return null;
                    BlockPos pos = new BlockPos(x, y, z);
                    if (!level.getBlockState(pos).isAir()
                            || !level.getBlockState(pos.above()).isAir()
                            || !level.getBlockState(pos.below()).isFaceSturdy(
                            level, pos.below(), net.minecraft.core.Direction.UP)
                            || level.canSeeSky(pos)) {
                        continue;
                    }
                    return pos;
                }
            }
        }
        return null;
    }

    private static int distanceToBounds(BlockPos pos, BlockPos min, BlockPos max) {
        int dx = pos.getX() < min.getX() ? min.getX() - pos.getX()
                : pos.getX() > max.getX() ? pos.getX() - max.getX() : 0;
        int dy = pos.getY() < min.getY() ? min.getY() - pos.getY()
                : pos.getY() > max.getY() ? pos.getY() - max.getY() : 0;
        int dz = pos.getZ() < min.getZ() ? min.getZ() - pos.getZ()
                : pos.getZ() > max.getZ() ? pos.getZ() - max.getZ() : 0;
        return dx + dy + dz;
    }

    private static double distanceToSegment2D(BlockPos p, BlockPos a, BlockPos b) {
        double ax = a.getX();
        double az = a.getZ();
        double bx = b.getX();
        double bz = b.getZ();
        double px = p.getX();
        double pz = p.getZ();

        double vx = bx - ax;
        double vz = bz - az;
        double len2 = vx * vx + vz * vz;
        if (len2 <= 0.0001D) {
            double dx = px - ax;
            double dz = pz - az;
            return Math.sqrt(dx * dx + dz * dz);
        }

        double t = ((px - ax) * vx + (pz - az) * vz) / len2;
        t = Math.max(0.0D, Math.min(1.0D, t));
        double qx = ax + vx * t;
        double qz = az + vz * t;
        double dx = px - qx;
        double dz = pz - qz;
        return Math.sqrt(dx * dx + dz * dz);
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
        int workstations = 0;
        int nonStorageWorkstations = 0;
        int usableInteriorCells = 0;
        int doors = 0;

        BlockPos min = building.min();
        BlockPos max = building.max();
        for (BlockPos pos : BlockPos.betweenClosed(min, max)) {
            if (!VillageSimulationScheduler.tryConsumeBlockProbe(level)) return false;

            BlockState state = level.getBlockState(pos);
            boolean usableAnchor = building.villageBuilt()
                    || VillageBuildingAdoptionService.hasAdjacentStandingSpace(
                            level, pos, min, max);

            if (usableAnchor && state.getBlock() instanceof BedBlock
                    && state.hasProperty(BedBlock.PART)
                    && state.getValue(BedBlock.PART) == BedPart.FOOT) {
                beds++;
            }
            if (state.is(BlockTags.DOORS)) doors++;
            if (usableAnchor && level.getBlockEntity(pos) instanceof Container) {
                containers++;
            }
            if (usableAnchor && VillageBuildingAdoptionService.isWorkstation(state)) {
                workstations++;
                if (!state.is(net.minecraft.world.level.block.Blocks.BARREL)) {
                    nonStorageWorkstations++;
                }
            }

            if (state.isAir()
                    && level.getBlockState(pos.above()).isAir()
                    && level.getBlockState(pos.below()).isFaceSturdy(level, pos.below(), net.minecraft.core.Direction.UP)) {
                usableInteriorCells++;
            }
        }

        String classification = building.classification();
        if (!building.villageBuilt()) {
            if (beds > 0 && nonStorageWorkstations > 0) classification = "mixed_use";
            else if (beds > 0) classification = "residential";
            else if (containers >= 2 && nonStorageWorkstations == 0) classification = "storage";
            else if (workstations > 0) classification = "workshop";
            else classification = "generic_shelter";
            building.setClassification(classification);
        }

        boolean valid;
        if ("residential".equals(classification) || "mixed_use".equals(classification)) {
            valid = beds > 0 && usableInteriorCells >= 2;
            building.setValidatedCapacity(valid ? beds : 0);
        } else if ("storage".equals(classification)) {
            valid = containers > 0 && usableInteriorCells >= 1;
            building.setValidatedCapacity(0);
        } else if ("workshop".equals(classification)) {
            // A workspace loses its functional capacity when its actual
            // professional stations are removed. Never perpetuate an old
            // positive capacity merely because floor/headroom still exist.
            valid = nonStorageWorkstations > 0 && usableInteriorCells >= 2;
            building.setValidatedCapacity(valid ? nonStorageWorkstations : 0);
        } else {
            valid = usableInteriorCells >= 1;
            building.setValidatedCapacity(0);
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

        if (valid && !building.villageBuilt() && "storage".equals(building.classification())) {
            VillageSavedData data = VillageSavedData.get(level);
            for (BlockPos pos : BlockPos.betweenClosed(building.min(), building.max())) {
                if (!VillageSimulationScheduler.tryConsumeBlockProbe(level)) break;
                if (!(level.getBlockEntity(pos) instanceof Container)
                        || !VillageBuildingAdoptionService.hasAdjacentStandingSpace(
                                level, pos, building.min(), building.max())) continue;
                if (data.storageAt(building.villageId(), pos).isPresent()) continue;

                VillageSavedData.StorageRecord storage =
                        data.createStorage(building.villageId(), pos, "general");
                storage.setValidationState("valid");
                storage.setLastValidatedGameTime(level.getGameTime());
            }
        }

        return true;
    }
}
