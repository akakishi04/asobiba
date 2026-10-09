package io.github.akakishi04.asobibatweaks.feature;

import java.util.HashSet;
import java.util.Set;
import java.util.UUID;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.tags.BlockTags;
import net.minecraft.world.Container;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.block.BedBlock;
import net.minecraft.world.level.block.StairBlock;
import net.minecraft.world.level.block.HorizontalDirectionalBlock;
import net.minecraft.world.level.block.Block;
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

    // A finite retry budget keeps crowded chunks from losing their validated
    // building capacity forever when unrelated work exhausts the shared
    // background probe allowance at the instant of dirty-chunk processing.
    private static final int MAX_BUDGET_RETRIES = 16;

    public static void revalidateChunk(ServerLevel level, ChunkPos chunk) {
        revalidateChunk(level, chunk, 0);
    }

    private static void revalidateChunk(ServerLevel level, ChunkPos chunk, int budgetRetries) {
        VillageSavedData data = VillageSavedData.get(level);
        VillageSavedData.ChunkIndexView indexed = data.recordsForChunk(chunk);
        if (indexed.buildingIds().isEmpty() && indexed.storageIds().isEmpty()) return;

        Set<UUID> touchedVillages = new HashSet<>();
        boolean budgetExhausted = false;
        for (UUID buildingId : indexed.buildingIds()) {
            VillageSavedData.BuildingRecord building = data.building(buildingId).orElse(null);
            if (building == null) continue;
            if (!VillageSimulationScheduler.isAreaLoaded(level, building.min(), building.max())) continue;

            if (!revalidateBuilding(level, building)) {
                // Validation must not lose this building permanently merely
                // because another job consumed this tick's finite probe
                // budget. The building's cached state remains unmodified.
                budgetExhausted = true;
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
        if (budgetExhausted && budgetRetries < MAX_BUDGET_RETRIES) {
            // Queue for another bounded server tick. The same stable key
            // deduplicates overlapping invalidation sources. No chunk is
            // force-loaded, and a permanently undersized user-configured
            // budget cannot create an infinite retry storm.
            VillageSimulationScheduler.enqueueValidation(level,
                    "budget_revalidate:" + chunk.toLong(),
                    () -> revalidateChunk(level, chunk, budgetRetries + 1));
        }
    }

    /**
     * V89: direct, bounded validation of the intentionally supported 5x5
     * staircase family. Three rising EAST treads and a SOUTH turning tread
     * connect each floor, with real upper landing support and headroom.
     * Missing or rotated physical stairs fail closed; no upper-floor capacity
     * is inferred from the mere presence of higher beds.
     */
    static boolean connectedUpperStories(ServerLevel level, BlockPos base, int stories) {
        if (stories < 1 || stories > 2) return false;
        for (int floor = 0; floor < stories; floor++) {
            int offsetY = floor * 4;
            for (int x = 1; x <= 3; x++) {
                BlockPos tread = base.offset(x, x + offsetY, 1);
                if (!VillageSimulationScheduler.isChunkLoaded(level, tread)
                        || !isStairFacing(level.getBlockState(tread), Direction.EAST)
                        || !level.getBlockState(tread.above()).isAir()) return false;
            }
            BlockPos turn = base.offset(3, 4 + offsetY, 2);
            BlockPos opening = base.offset(3, 4 + offsetY, 1);
            BlockPos upperLanding = base.offset(3, 5 + offsetY, 3);
            if (!VillageSimulationScheduler.isChunkLoaded(level, turn)
                    || !VillageSimulationScheduler.isChunkLoaded(level, upperLanding)
                    || !isStairFacing(level.getBlockState(turn), Direction.SOUTH)
                    || !level.getBlockState(turn.above()).isAir()
                    || !level.getBlockState(opening).isAir()
                    || !level.getBlockState(opening.above()).isAir()
                    || !level.getBlockState(upperLanding).isAir()
                    || !level.getBlockState(upperLanding.above()).isAir()
                    || !level.getBlockState(upperLanding.below()).isFaceSturdy(
                            level, upperLanding.below(), Direction.UP)) return false;
        }
        return true;
    }

    static boolean templateInteriorCell(BlockPos base, BlockPos pos, int floors) {
        int x = pos.getX() - base.getX();
        int y = pos.getY() - base.getY();
        int z = pos.getZ() - base.getZ();
        if (x < 1 || x > 3 || z < 1 || z > 3) return false;
        return y >= 1 && y <= 3 || y >= 5 && y <= 7
                || floors == 3 && y >= 9 && y <= 11;
    }

    private static boolean isStairFacing(BlockState state, Direction direction) {
        return state.getBlock() instanceof StairBlock
                && state.hasProperty(HorizontalDirectionalBlock.FACING)
                && state.getValue(HorizontalDirectionalBlock.FACING) == direction;
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
        boolean twoStoryTemplate = building.villageBuilt()
                && ("house_2story_5x5".equals(building.templateId())
                    || "house_3story_5x5".equals(building.templateId()));
        boolean secondStoryAccessible = twoStoryTemplate
                && connectedUpperStories(level, min, 1);
        boolean thirdStoryAccessible = secondStoryAccessible
                && "house_3story_5x5".equals(building.templateId())
                && connectedUpperStories(level, min, 2);
        for (BlockPos pos : BlockPos.betweenClosed(min, max)) {
            // A 5x13x5 three-storey shell exceeds the default 256-probe
            // budget before reaching its third floor. Its recognized vanilla
            // beds and safe standing places all belong to the small bounded
            // 3x3 interiors, not the outer roof/wall block volume.
            if (twoStoryTemplate && !templateInteriorCell(min, pos,
                    "house_3story_5x5".equals(building.templateId()) ? 3 : 2)) continue;
            if (!VillageSimulationScheduler.tryConsumeBuildingValidationProbe(level)) return false;

            BlockState state = level.getBlockState(pos);
            boolean usableAnchor = building.villageBuilt()
                    || VillageBuildingAdoptionService.hasAdjacentStandingSpace(
                            level, pos, min, max);

            if (usableAnchor && state.getBlock() instanceof BedBlock
                    && state.hasProperty(BedBlock.PART)
                    && state.getValue(BedBlock.PART) == BedPart.FOOT) {
                Direction facing = state.getValue(BedBlock.FACING);
                BlockState head = level.getBlockState(pos.relative(facing));
                // A detached Bed foot is never housing capacity. For new
                // multistorey village shells, count only physically connected
                // and reachable upper rooms, not any bed in a cuboid.
                boolean wholeBed = head.getBlock() == state.getBlock()
                        && head.hasProperty(BedBlock.PART)
                        && head.getValue(BedBlock.PART) == BedPart.HEAD
                        && head.getValue(BedBlock.FACING) == facing;
                boolean routeValid = !twoStoryTemplate
                        || (pos.getY() < min.getY() + 5
                            || pos.getY() < min.getY() + 9 && secondStoryAccessible
                            || thirdStoryAccessible)
                        && VillageBuildingAdoptionService.hasAdjacentStandingSpace(
                                level, pos, min, max);
                if (wholeBed && routeValid) beds++;
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
            // In purpose-built specialist workshops, the explicit primary
            // job-site anchor must physically survive. The fishing Barrel
            // must never be confused with the separately registered storage
            // Barrel when recalculating functional workstation capacity.
            Block expected = VillageSpecialistWorkshopService.primaryStation(
                    building.templateId());
            if (expected != null) {
                valid = level.getBlockState(min.offset(2, 1, 2)).is(expected)
                        && usableInteriorCells >= 2;
                building.setValidatedCapacity(valid ? 1 : 0);
            } else {
                valid = nonStorageWorkstations > 0 && usableInteriorCells >= 2;
                building.setValidatedCapacity(valid ? nonStorageWorkstations : 0);
            }
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
