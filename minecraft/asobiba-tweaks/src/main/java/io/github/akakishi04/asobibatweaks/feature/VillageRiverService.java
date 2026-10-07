package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import java.util.ArrayDeque;
import java.util.HashSet;
import java.util.Set;
import java.util.UUID;
import net.minecraft.core.BlockPos;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.tags.FluidTags;
import net.minecraft.world.entity.npc.Villager;
import net.minecraft.world.level.levelgen.Heightmap;
import net.neoforged.bus.api.SubscribeEvent;
import net.neoforged.neoforge.event.tick.EntityTickEvent;

/**
 * Low-frequency recognition of real navigable surface-water corridors near villages.
 *
 * <p>This caches physical geography for planning. It does not create a current simulation,
 * force-load chunks or replace actual water continuity checks.</p>
 */
public final class VillageRiverService {
    private static final long SURVEY_INTERVAL = 3L * 24_000L;
    private static final int SEARCH_RADIUS = 48;
    private static final int GRID_STEP = 8;
    private static final int WALK_STEP = 4;
    private static final int MAX_COMPONENT_NODES = 144;

    public VillageRiverService() {
    }

    @SubscribeEvent
    public void onVillagerTick(EntityTickEvent.Post event) {
        if (!AsobibaTweaksConfig.VILLAGE_SIMULATION_ENABLED.getAsBoolean()
                || !(event.getEntity() instanceof Villager villager)
                || villager.level().isClientSide()
                || villager.tickCount % 400 != Math.floorMod(villager.getId(), 400)) {
            return;
        }

        ServerLevel level = (ServerLevel)villager.level();
        VillageIdentityBootstrap.ensure(villager, level);
        VillagerSimData.villageId(villager).ifPresent(villageId -> scheduleSurvey(level, villageId));
    }

    private static void scheduleSurvey(ServerLevel level, UUID villageId) {
        VillageSavedData data = VillageSavedData.get(level);
        VillageSavedData.VillageRecord village = data.village(villageId).orElse(null);
        if (village == null || "abandoned".equals(village.lifecycle()) || "merged".equals(village.lifecycle())) {
            return;
        }

        long now = level.getGameTime();
        if (now < village.nextRiverSurveyGameTime()) return;

        village.setNextRiverSurveyGameTime(now + SURVEY_INTERVAL);
        data.touch();
        VillageSimulationScheduler.enqueueRouteSearch(
                level,
                "river_survey:" + villageId,
                () -> survey(level, villageId)
        );
    }

    private static void survey(ServerLevel level, UUID villageId) {
        VillageSavedData data = VillageSavedData.get(level);
        VillageSavedData.VillageRecord village = data.village(villageId).orElse(null);
        if (village == null) return;

        VillageSavedData.WorkSiteRecord existing = null;
        for (VillageSavedData.WorkSiteRecord site : data.workSitesForVillage(villageId)) {
            if ("river_corridor".equals(site.type())) {
                existing = site;
                break;
            }
        }

        BlockPos start = findWaterStart(level, village.center());
        if (start == null) {
            if (existing != null) existing.setState("inactive");
            data.touch();
            return;
        }

        WaterComponent component = traceWater(level, start);
        if (component == null || !component.qualifies()) {
            if (existing != null) existing.setState("inactive");
            data.touch();
            return;
        }

        if (existing == null) {
            existing = data.createWorkSite(
                    villageId,
                    "river_corridor",
                    new BlockPos(component.minX, component.minY - 1, component.minZ),
                    new BlockPos(component.maxX, component.maxY + 1, component.maxZ)
            );
            existing.setCreatedGameTime(level.getGameTime());
        }

        existing.setState("active");
        existing.setLastUsedGameTime(level.getGameTime());
        data.touch();
    }

    private static BlockPos findWaterStart(ServerLevel level, BlockPos center) {
        for (int radius = 0; radius <= SEARCH_RADIUS; radius += GRID_STEP) {
            for (int dx = -radius; dx <= radius; dx += GRID_STEP) {
                BlockPos a = surfaceWater(level, center.getX() + dx, center.getZ() - radius);
                if (a != null) return a;
                BlockPos b = surfaceWater(level, center.getX() + dx, center.getZ() + radius);
                if (b != null) return b;
            }
            for (int dz = -radius + GRID_STEP; dz <= radius - GRID_STEP; dz += GRID_STEP) {
                BlockPos a = surfaceWater(level, center.getX() - radius, center.getZ() + dz);
                if (a != null) return a;
                BlockPos b = surfaceWater(level, center.getX() + radius, center.getZ() + dz);
                if (b != null) return b;
            }
        }
        return null;
    }

    private static WaterComponent traceWater(ServerLevel level, BlockPos start) {
        ArrayDeque<BlockPos> queue = new ArrayDeque<>();
        Set<Long> visited = new HashSet<>();
        queue.add(start);

        int minX = start.getX();
        int maxX = start.getX();
        int minY = start.getY();
        int maxY = start.getY();
        int minZ = start.getZ();
        int maxZ = start.getZ();
        int nodes = 0;

        int[][] directions = {
                {WALK_STEP, 0}, {-WALK_STEP, 0}, {0, WALK_STEP}, {0, -WALK_STEP},
                {WALK_STEP, WALK_STEP}, {WALK_STEP, -WALK_STEP},
                {-WALK_STEP, WALK_STEP}, {-WALK_STEP, -WALK_STEP}
        };

        while (!queue.isEmpty() && nodes < MAX_COMPONENT_NODES) {
            BlockPos current = queue.removeFirst();
            long key = key(current.getX(), current.getZ());
            if (!visited.add(key)) continue;
            nodes++;

            minX = Math.min(minX, current.getX());
            maxX = Math.max(maxX, current.getX());
            minY = Math.min(minY, current.getY());
            maxY = Math.max(maxY, current.getY());
            minZ = Math.min(minZ, current.getZ());
            maxZ = Math.max(maxZ, current.getZ());

            for (int[] direction : directions) {
                int x = current.getX() + direction[0];
                int z = current.getZ() + direction[1];
                if (visited.contains(key(x, z))) continue;

                BlockPos next = surfaceWater(level, x, z);
                if (next == null || Math.abs(next.getY() - current.getY()) > 3) continue;
                queue.addLast(next);
            }
        }

        return new WaterComponent(minX, maxX, minY, maxY, minZ, maxZ, nodes);
    }

    private static BlockPos surfaceWater(ServerLevel level, int x, int z) {
        BlockPos column = new BlockPos(x, level.getMinBuildHeight(), z);
        if (!VillageSimulationScheduler.isChunkLoaded(level, column)) return null;
        if (!VillageSimulationScheduler.tryConsumeBlockProbe(level)) return null;

        int y = level.getHeight(Heightmap.Types.MOTION_BLOCKING_NO_LEAVES, x, z);
        BlockPos surface = new BlockPos(x, y - 1, z);
        if (level.getFluidState(surface).is(FluidTags.WATER)) return surface;
        return null;
    }

    private static long key(int x, int z) {
        return ((long)x << 32) ^ (z & 0xffffffffL);
    }

    private record WaterComponent(
            int minX, int maxX,
            int minY, int maxY,
            int minZ, int maxZ,
            int nodes
    ) {
        private boolean qualifies() {
            int extentX = maxX - minX;
            int extentZ = maxZ - minZ;
            int major = Math.max(extentX, extentZ);
            int minor = Math.max(1, Math.min(extentX, extentZ));
            return nodes >= 12 && major >= 48 && major >= minor * 1.4D;
        }
    }
}
