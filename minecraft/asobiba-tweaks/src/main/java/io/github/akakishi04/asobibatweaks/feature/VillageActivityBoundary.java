package io.github.akakishi04.asobibatweaks.feature;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;
import java.util.UUID;
import net.minecraft.core.BlockPos;
import net.minecraft.core.GlobalPos;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.entity.ai.memory.MemoryModuleType;
import net.minecraft.world.entity.npc.Villager;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.phys.AABB;

/**
 * Shared horizontal activity envelope. An envelope is never a property claim.
 * Only existing indexed village assets and resident-owned POI memories may grow it;
 * looking inside the envelope never adopts blocks, containers or player buildings.
 * Freight recovery and explicit satellite travel deliberately retain their own bounds.
 */
public final class VillageActivityBoundary {
    public static final int INITIAL_RADIUS = 48;
    public static final int MAX_RADIUS = 128;
    public static final int ANCHOR_RADIUS = 16;
    public static final int MAX_ANCHORS = 128;
    private static final int MAX_CANDIDATES = 512;
    private static final int MAX_NEW_ANCHORS = 8;
    private static final long REFRESH_ACTIVE_TICKS = 1_200L;

    private VillageActivityBoundary() {}

    public static boolean contains(VillageSavedData.VillageRecord village, BlockPos pos) {
        if (village == null || pos == null || !withinHorizontal(village.center(), pos, MAX_RADIUS)) return false;
        if (withinHorizontal(village.center(), pos, INITIAL_RADIUS)) return true;
        for (long packed : village.activityAnchors()) {
            if (withinHorizontal(BlockPos.of(packed), pos, ANCHOR_RADIUS)) return true;
        }
        return false;
    }

    /** Bounding box for loaded-entity queries; callers must also apply contains. */
    public static AABB searchBounds(VillageSavedData.VillageRecord village) {
        return new AABB(village.center()).inflate(MAX_RADIUS, 64.0D, MAX_RADIUS);
    }

    /** Whole ordinary building footprint must fit. Height is independent of terrain altitude. */
    public static boolean containsFootprint(VillageSavedData.VillageRecord village, BlockPos min, BlockPos max) {
        long width = (long)max.getX() - min.getX() + 1;
        long depth = (long)max.getZ() - min.getZ() + 1;
        if (width <= 0 || depth <= 0 || width > 32 || depth > 32) return false;
        for (int x = 0; x < width; x++) for (int z = 0; z < depth; z++) {
            if (!contains(village, min.offset(x, 0, z))) return false;
        }
        return true;
    }

    public static boolean withinHorizontal(BlockPos a, BlockPos b, int radius) {
        long dx = (long)a.getX() - b.getX();
        long dz = (long)a.getZ() - b.getZ();
        return Math.abs(dx) <= radius && Math.abs(dz) <= radius
                && dx * dx + dz * dz <= (long)radius * radius;
    }

    /** Triggered only by a loaded resident, never a global historical-village scan. */
    public static void observe(Villager resident, ServerLevel level) {
        VillageSavedData data = VillageSavedData.get(level);
        VillageSavedData.VillageRecord village = VillagerSimData.villageId(resident)
                .flatMap(data::village).orElse(null);
        if (village == null || !resident.isAlive()) return;
        village.observeActive(level.getGameTime());
        if (village.activeObservedTicks() >= village.nextBoundaryActiveTick()) {
            village.setNextBoundaryActiveTick(village.activeObservedTicks() + REFRESH_ACTIVE_TICKS);
            VillageSimulationScheduler.enqueueReconciliation(level, "activity_boundary:" + village.id(),
                    () -> refresh(level, data, village));
        }
        VillageHistoryMaintenance.schedule(level, data, village);
        data.touch();
    }

    static void refresh(ServerLevel level, VillageSavedData data, VillageSavedData.VillageRecord village) {
        Set<BlockPos> candidates = new LinkedHashSet<>();
        // Previous resident POIs remain last-known anchors when their residents unload.
        // Absence of a loaded entity is never evidence that its home disappeared.
        for (long packed : village.activityAnchors()) candidates.add(BlockPos.of(packed));
        Set<UUID> buildings = new LinkedHashSet<>();
        Set<UUID> storages = new LinkedHashSet<>();
        Set<UUID> sites = new LinkedHashSet<>();
        Set<UUID> routes = new LinkedHashSet<>();
        int cx = village.center().getX() >> 4;
        int cz = village.center().getZ() >> 4;
        // Derived chunk index only: no block reads and no chunk requests.
        for (int x = -8; x <= 8; x++) for (int z = -8; z <= 8; z++) {
            var indexed = data.recordsForChunk(new ChunkPos(cx + x, cz + z));
            addBounded(buildings, indexed.buildingIds());
            addBounded(storages, indexed.storageIds());
            addBounded(sites, indexed.workSiteIds());
            addBounded(routes, indexed.routeIds());
        }
        Set<BlockPos> retired = new LinkedHashSet<>();
        for (UUID id : storages) {
            var storage = data.storage(id).orElse(null);
            if (storage != null && village.id().equals(storage.villageId())
                    && "invalid".equals(storage.validationState())) retired.add(storage.pos());
        }
        for (UUID id : buildings) {
            var building = data.building(id).orElse(null);
            if (building != null && village.id().equals(building.villageId())
                    && "invalid".equals(building.validationState())) retired.add(midpoint(building.min(), building.max()));
        }
        if (!retired.isEmpty()) {
            candidates.removeAll(retired);
            village.replaceActivityAnchors(candidates);
        }
        for (UUID id : storages) {
            var storage = data.storage(id).orElse(null);
            if (storage != null && village.id().equals(storage.villageId())
                    && "valid".equals(storage.validationState())) addCandidate(candidates, storage.pos());
        }
        for (UUID id : buildings) {
            var building = data.building(id).orElse(null);
            if (building == null || !village.id().equals(building.villageId())
                    || !"valid".equals(building.validationState())
                    || "unassigned".equals(building.classification())) continue;
            addCandidate(candidates, midpoint(building.min(), building.max()));
        }
        for (UUID id : sites) {
            var site = data.workSite(id).orElse(null);
            if (site == null || !village.id().equals(site.villageId()) || !"active".equals(site.state())
                    || site.parentWorkSiteId() != null || "outpost".equals(site.type())
                    || "satellite".equals(site.type()) || "dock".equals(site.type())
                    || "river_dock".equals(site.type())) continue;
            addCandidate(candidates, midpoint(site.min(), site.max()));
        }
        for (UUID id : routes) {
            var route = data.route(id).orElse(null);
            if (route == null || !village.id().equals(route.villageId()) || !"active".equals(route.state())
                    || route.trafficScore() <= 0
                    || !("road".equals(route.type()) || "path".equals(route.type()))) continue;
            // Only surveyed physical waypoints qualify, not a straight imagined route to a remote site.
            for (BlockPos point : route.waypoints()) addCandidate(candidates, point);
        }
        int observed = 0;
        for (Villager resident : level.getEntitiesOfClass(Villager.class, searchBounds(village),
                v -> v.isAlive() && VillagerSimData.villageId(v).filter(village.id()::equals).isPresent())) {
            if (++observed > 128) break;
            addMemory(candidates, resident, level, MemoryModuleType.HOME);
            addMemory(candidates, resident, level, MemoryModuleType.JOB_SITE);
            addMemory(candidates, resident, level, MemoryModuleType.MEETING_POINT);
        }
        grow(village, candidates);
        data.touch();
    }

    /** Snapshot-based one-hop growth prevents a long chain being swallowed in one refresh. */
    static void grow(VillageSavedData.VillageRecord village, java.util.Collection<BlockPos> candidates) {
        BlockPos oldCenter = village.center();
        List<BlockPos> ordered = candidates.stream().filter(p -> p != null
                        && withinHorizontal(oldCenter, p, MAX_RADIUS))
                .distinct().sorted(Comparator.comparingLong((BlockPos p) -> horizontalDistance(oldCenter, p))
                        .thenComparingLong(BlockPos::asLong)).limit(MAX_CANDIDATES).toList();
        List<BlockPos> next = new ArrayList<>();
        List<BlockPos> previous = village.activityAnchors().stream().map(BlockPos::of)
                .filter(p -> withinHorizontal(oldCenter, p, MAX_RADIUS)).toList();
        for (BlockPos pos : previous) if (withinHorizontal(oldCenter, pos, INITIAL_RADIUS)) next.add(pos);
        // Remove disconnected cached islands when a definitely invalid indexed anchor was retired.
        // At most 128 nodes: this bounded closure never probes the physical world.
        Set<BlockPos> connected = new java.util.HashSet<>(next);
        for (int cursor = 0; cursor < next.size(); cursor++) {
            BlockPos anchor = next.get(cursor);
            for (BlockPos pos : previous) {
                if (!connected.contains(pos) && withinHorizontal(anchor, pos, ANCHOR_RADIUS * 2)) {
                    connected.add(pos); next.add(pos);
                }
            }
        }
        village.replaceActivityAnchors(next);
        int added = 0;
        for (BlockPos pos : ordered) {
            if (next.contains(pos) || next.size() >= MAX_ANCHORS) continue;
            if (!contains(village, pos) || added >= MAX_NEW_ANCHORS) continue;
            // Deduplicate dense POIs so a single multi-bed house cannot consume the entire envelope.
            if (next.stream().anyMatch(existing -> withinHorizontal(existing, pos, 6))) continue;
            next.add(pos.immutable());
            added++;
        }
        // Median of the original local concentration is resistant to one remote warehouse.
        // The seed may adjust gently, but cannot walk the whole core toward a satellite.
        List<BlockPos> core = ordered.stream().filter(p -> withinHorizontal(village.activityOrigin(), p,
                INITIAL_RADIUS)).toList();
        if (!core.isEmpty()) {
            int mx = median(core.stream().map(BlockPos::getX).sorted().toList());
            int my = median(core.stream().map(BlockPos::getY).sorted().toList());
            int mz = median(core.stream().map(BlockPos::getZ).sorted().toList());
            int targetX = clamp(mx, village.activityOrigin().getX() - 16, village.activityOrigin().getX() + 16);
            int targetZ = clamp(mz, village.activityOrigin().getZ() - 16, village.activityOrigin().getZ() + 16);
            village.setCenter(new BlockPos(clamp(targetX, oldCenter.getX() - 4, oldCenter.getX() + 4),
                    clamp(my, oldCenter.getY() - 4, oldCenter.getY() + 4),
                    clamp(targetZ, oldCenter.getZ() - 4, oldCenter.getZ() + 4)));
        }
        next.removeIf(p -> !withinHorizontal(village.center(), p, MAX_RADIUS));
        village.replaceActivityAnchors(next);
    }

    private static void addBounded(Set<UUID> target, Set<UUID> values) {
        for (UUID id : values) { if (target.size() >= MAX_CANDIDATES) break; target.add(id); }
    }
    private static void addCandidate(Set<BlockPos> candidates, BlockPos pos) {
        if (candidates.size() < MAX_CANDIDATES) candidates.add(pos.immutable());
    }
    private static void addMemory(Set<BlockPos> candidates, Villager resident, ServerLevel level,
            MemoryModuleType<GlobalPos> memory) {
        resident.getBrain().getMemory(memory).filter(pos -> pos.dimension().equals(level.dimension()))
                .ifPresent(pos -> addCandidate(candidates, pos.pos()));
    }
    private static BlockPos midpoint(BlockPos a, BlockPos b) {
        return new BlockPos(a.getX() + (b.getX() - a.getX()) / 2,
                a.getY() + (b.getY() - a.getY()) / 2, a.getZ() + (b.getZ() - a.getZ()) / 2);
    }
    private static long horizontalDistance(BlockPos a, BlockPos b) {
        long dx = (long)a.getX() - b.getX(), dz = (long)a.getZ() - b.getZ();
        return dx * dx + dz * dz;
    }
    private static int median(List<Integer> values) { return values.get(values.size() / 2); }
    private static int clamp(int value, int min, int max) { return Math.max(min, Math.min(max, value)); }
}
