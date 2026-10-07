package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaRegistries;
import java.util.ArrayDeque;
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
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.state.properties.BedPart;

/**
 * Bounded semantic adoption for player-built village structures.
 *
 * <p>Only local placement events can trigger adoption. The service never scans the whole
 * village/world and never edits the physical structure.</p>
 */
public final class VillageBuildingAdoptionService {
    private static final int SEARCH_RADIUS = 8;
    private static final int MAX_INTERIOR_CELLS = 128;
    private static final int MAX_ROOF_HEIGHT = 6;

    private VillageBuildingAdoptionService() {
    }

    public static void tryAdoptNear(ServerLevel level, BlockPos anchor) {
        if (!VillageSimulationScheduler.isChunkLoaded(level, anchor)) return;
        if (!isSemanticAnchor(level, anchor)) return;

        VillageSavedData data = VillageSavedData.get(level);
        UUID villageId = nearestVillage(data, anchor, 96);
        if (villageId == null || alreadyInsideBuilding(data, anchor)) return;

        BlockPos start = findInteriorStart(level, anchor);
        if (start == null) return;

        Candidate candidate = floodCoveredInterior(level, start);
        if (candidate == null || candidate.cells < 4 || candidate.accessPoints <= 0) return;

        Semantic semantic = inspectSemantics(level, candidate.min, candidate.max);
        if (!semantic.meaningful()) return;

        String classification = classify(semantic);
        int capacity = switch (classification) {
            case "residential", "mixed_use" -> semantic.beds;
            case "workshop" -> semantic.workstations;
            default -> 0;
        };

        VillageSavedData.BuildingRecord building =
                data.createBuilding(villageId, candidate.min, candidate.max, false);
        building.setTemplateId("player_adopted");
        building.setClassification(classification);
        building.setValidatedCapacity(Math.max(0, capacity));
        building.setValidationState("valid");
        building.setLastValidatedGameTime(level.getGameTime());

        // A clearly storage-dominant player building is considered intentionally integrated.
        // Personal containers in ordinary houses/mixed-use buildings are not auto-enrolled.
        if ("storage".equals(classification)) {
            for (BlockPos pos : BlockPos.betweenClosed(candidate.min, candidate.max)) {
                if (!VillageSimulationScheduler.tryConsumeBlockProbe(level)) break;
                if (!(level.getBlockEntity(pos) instanceof Container)) continue;
                if (data.storageAt(villageId, pos).isPresent()) continue;

                VillageSavedData.StorageRecord storage = data.createStorage(villageId, pos, "general");
                storage.setValidationState("valid");
                storage.setLastValidatedGameTime(level.getGameTime());
            }
            VillageStorageService.reconcileVillage(villageId, level);
        }

        data.touch();
        VillagePublicWorksService.schedule(level, villageId);
    }

    private static UUID nearestVillage(VillageSavedData data, BlockPos anchor, int maxDistance) {
        VillageSavedData.VillageRecord best = null;
        int bestDistance = Integer.MAX_VALUE;
        for (VillageSavedData.VillageRecord village : data.villagesView().values()) {
            if ("merged".equals(village.lifecycle()) || "abandoned".equals(village.lifecycle())) continue;

            int distance = village.center().distManhattan(anchor);
            for (Long packed : village.districtCenters()) {
                distance = Math.min(distance, BlockPos.of(packed).distManhattan(anchor));
            }
            if (distance <= maxDistance && distance < bestDistance) {
                bestDistance = distance;
                best = village;
            }
        }
        return best == null ? null : best.id();
    }

    private static boolean alreadyInsideBuilding(VillageSavedData data, BlockPos anchor) {
        Set<UUID> candidates = new HashSet<>();
        ChunkPos chunk = new ChunkPos(anchor);
        for (int dx = -1; dx <= 1; dx++) {
            for (int dz = -1; dz <= 1; dz++) {
                candidates.addAll(data.recordsForChunk(new ChunkPos(chunk.x + dx, chunk.z + dz)).buildingIds());
            }
        }

        for (UUID id : candidates) {
            VillageSavedData.BuildingRecord building = data.building(id).orElse(null);
            if (building == null) continue;
            if (inside(anchor, building.min().offset(-1, -1, -1), building.max().offset(1, 1, 1))) return true;
        }
        return false;
    }

    private static boolean isSemanticAnchor(ServerLevel level, BlockPos pos) {
        BlockState state = level.getBlockState(pos);
        if (state.getBlock() instanceof BedBlock) return true;
        if (state.is(Blocks.CHEST) || state.is(Blocks.TRAPPED_CHEST) || state.is(Blocks.BARREL)) return true;
        return isWorkstation(state) || state.is(Blocks.BELL);
    }

    private static BlockPos findInteriorStart(ServerLevel level, BlockPos anchor) {
        for (int dy = -1; dy <= 1; dy++) {
            for (Direction direction : Direction.Plane.HORIZONTAL) {
                BlockPos candidate = anchor.relative(direction).offset(0, dy, 0);
                if (isUsableCoveredCell(level, candidate)) return candidate;
            }
        }
        BlockPos above = anchor.above();
        return isUsableCoveredCell(level, above) ? above : null;
    }

    private static Candidate floodCoveredInterior(ServerLevel level, BlockPos start) {
        ArrayDeque<BlockPos> queue = new ArrayDeque<>();
        Set<Long> visited = new HashSet<>();
        queue.add(start.immutable());

        int minX = start.getX();
        int minY = start.getY();
        int minZ = start.getZ();
        int maxX = start.getX();
        int maxY = start.getY();
        int maxZ = start.getZ();
        int cells = 0;
        int accessPoints = 0;

        while (!queue.isEmpty() && cells < MAX_INTERIOR_CELLS) {
            BlockPos pos = queue.removeFirst();
            if (!visited.add(pos.asLong())) continue;
            if (Math.abs(pos.getX() - start.getX()) > SEARCH_RADIUS
                    || Math.abs(pos.getZ() - start.getZ()) > SEARCH_RADIUS
                    || Math.abs(pos.getY() - start.getY()) > 5) {
                continue;
            }
            if (!isUsableCoveredCell(level, pos)) continue;

            cells++;
            minX = Math.min(minX, pos.getX());
            minY = Math.min(minY, pos.getY());
            minZ = Math.min(minZ, pos.getZ());
            maxX = Math.max(maxX, pos.getX());
            maxY = Math.max(maxY, pos.getY() + 1);
            maxZ = Math.max(maxZ, pos.getZ());

            for (Direction direction : Direction.Plane.HORIZONTAL) {
                BlockPos next = pos.relative(direction);
                if (isDoor(level.getBlockState(next))) {
                    accessPoints++;
                    continue;
                }
                if (isUsableCoveredCell(level, next)) {
                    queue.addLast(next.immutable());
                } else if (isWalkableOpenCell(level, next) && level.canSeeSky(next)) {
                    accessPoints++;
                }
            }

            // Allows stair-like vertical circulation without treating arbitrary open shafts
            // as a second floor.
            for (int yOffset : new int[]{-1, 1}) {
                BlockPos vertical = pos.offset(0, yOffset, 0);
                if (isUsableCoveredCell(level, vertical)) queue.addLast(vertical.immutable());
            }
        }

        if (cells <= 0) return null;

        BlockPos min = new BlockPos(minX - 1, minY - 1, minZ - 1);
        BlockPos max = new BlockPos(maxX + 1, maxY + MAX_ROOF_HEIGHT, maxZ + 1);
        if (!VillageSimulationScheduler.isAreaLoaded(level, min, max)) return null;

        // Keep adopted bounds compact; semantic scan does not need arbitrary roof volume.
        max = new BlockPos(maxX + 1, Math.min(max.getY(), maxY + 3), maxZ + 1);
        return new Candidate(min, max, cells, accessPoints);
    }

    private static boolean isUsableCoveredCell(ServerLevel level, BlockPos pos) {
        if (!VillageSimulationScheduler.isChunkLoaded(level, pos)) return false;
        if (!VillageSimulationScheduler.tryConsumeBlockProbe(level)) return false;
        if (!isWalkableOpenCell(level, pos)) return false;
        return hasCover(level, pos);
    }

    private static boolean isWalkableOpenCell(ServerLevel level, BlockPos pos) {
        return level.getBlockState(pos).isAir()
                && level.getBlockState(pos.above()).isAir()
                && level.getBlockState(pos.below()).isFaceSturdy(level, pos.below(), Direction.UP)
                && !level.getFluidState(pos).is(net.minecraft.tags.FluidTags.LAVA);
    }

    private static boolean hasCover(ServerLevel level, BlockPos pos) {
        for (int dy = 2; dy <= MAX_ROOF_HEIGHT; dy++) {
            BlockPos roof = pos.above(dy);
            if (!VillageSimulationScheduler.isChunkLoaded(level, roof)) return false;
            if (!VillageSimulationScheduler.tryConsumeBlockProbe(level)) return false;
            if (!level.getBlockState(roof).isAir()) return true;
        }
        return false;
    }

    private static Semantic inspectSemantics(ServerLevel level, BlockPos min, BlockPos max) {
        int beds = 0;
        int containers = 0;
        int workstations = 0;
        int nonStorageWorkstations = 0;
        int bells = 0;

        for (BlockPos pos : BlockPos.betweenClosed(min, max)) {
            if (!VillageSimulationScheduler.tryConsumeBlockProbe(level)) break;
            BlockState state = level.getBlockState(pos);

            if (state.getBlock() instanceof BedBlock
                    && state.hasProperty(BedBlock.PART)
                    && state.getValue(BedBlock.PART) == BedPart.FOOT) {
                beds++;
            }
            if (level.getBlockEntity(pos) instanceof Container) containers++;
            if (isWorkstation(state)) {
                workstations++;
                if (!state.is(Blocks.BARREL)) nonStorageWorkstations++;
            }
            if (state.is(Blocks.BELL)) bells++;
        }
        return new Semantic(beds, containers, workstations, nonStorageWorkstations, bells);
    }

    private static String classify(Semantic semantic) {
        if (semantic.beds > 0 && semantic.nonStorageWorkstations > 0) return "mixed_use";
        if (semantic.beds > 0) return "residential";
        if (semantic.containers >= 2 && semantic.nonStorageWorkstations == 0) return "storage";
        if (semantic.workstations > 0) return "workshop";
        if (semantic.bells > 0) return "public";
        return "generic_shelter";
    }

    private static boolean isWorkstation(BlockState state) {
        return state.is(AsobibaRegistries.CARPENTER_WORKBENCH.get())
                || state.is(Blocks.BLAST_FURNACE)
                || state.is(Blocks.SMOKER)
                || state.is(Blocks.CARTOGRAPHY_TABLE)
                || state.is(Blocks.BREWING_STAND)
                || state.is(Blocks.COMPOSTER)
                || state.is(Blocks.BARREL)
                || state.is(Blocks.FLETCHING_TABLE)
                || state.is(Blocks.LECTERN)
                || state.is(Blocks.STONECUTTER)
                || state.is(Blocks.LOOM)
                || state.is(Blocks.SMITHING_TABLE)
                || state.is(Blocks.GRINDSTONE);
    }

    private static boolean isDoor(BlockState state) {
        return state.is(BlockTags.DOORS);
    }

    private static boolean inside(BlockPos pos, BlockPos min, BlockPos max) {
        return pos.getX() >= min.getX() && pos.getX() <= max.getX()
                && pos.getY() >= min.getY() && pos.getY() <= max.getY()
                && pos.getZ() >= min.getZ() && pos.getZ() <= max.getZ();
    }

    private record Candidate(BlockPos min, BlockPos max, int cells, int accessPoints) {
    }

    private record Semantic(
            int beds,
            int containers,
            int workstations,
            int nonStorageWorkstations,
            int bells) {
        private boolean meaningful() {
            return beds > 0 || containers > 0 || workstations > 0 || bells > 0;
        }
    }
}
