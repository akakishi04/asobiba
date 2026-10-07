package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.UUID;
import net.minecraft.core.BlockPos;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.util.RandomSource;
import net.minecraft.world.entity.npc.Villager;
import net.minecraft.world.entity.npc.VillagerProfession;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.tags.BlockTags;
import net.neoforged.bus.api.SubscribeEvent;
import net.neoforged.neoforge.event.tick.EntityTickEvent;

/**
 * Daily lifecycle and worker assignment for parent-linked remote Outposts.
 */
public final class VillageOutpostLifecycleService {
    private static final long DAY = 24_000L;
    private static final long ESTABLISHING_GRACE = 3L * DAY;
    private static final int INACTIVE_AFTER_IDLE_DAYS = 3;
    private static final int ABANDON_AFTER_IDLE_DAYS = 10;

    public VillageOutpostLifecycleService() {
    }

    @SubscribeEvent
    public void onVillagerTick(EntityTickEvent.Post event) {
        if (!AsobibaTweaksConfig.VILLAGE_SIMULATION_ENABLED.getAsBoolean()
                || !AsobibaTweaksConfig.VILLAGE_OUTPOSTS_ENABLED.getAsBoolean()
                || !(event.getEntity() instanceof Villager villager)
                || villager.level().isClientSide()
                || villager.tickCount % 200 != Math.floorMod(villager.getId(), 200)) {
            return;
        }

        ServerLevel level = (ServerLevel)villager.level();
        VillageIdentityBootstrap.ensure(villager, level);
        VillagerSimData.villageId(villager).ifPresent(villageId ->
                VillageSimulationScheduler.enqueuePlanning(
                        level,
                        "outpost_lifecycle:" + villageId,
                        () -> refreshVillage(level, villageId)
                )
        );
    }

    /**
     * @return true while Outpost travel/return-to-core should suppress ordinary Duty work.
     */
    public static boolean handleAssignedWorker(Villager villager, ServerLevel level) {
        var siteId = VillagerSimData.outpostSiteId(villager);
        if (siteId.isEmpty()) return false;

        VillageSavedData data = VillageSavedData.get(level);
        VillageSavedData.WorkSiteRecord site = data.workSite(siteId.get()).orElse(null);
        var villageId = VillagerSimData.villageId(villager);
        if (site == null || villageId.isEmpty() || !site.villageId().equals(villageId.get())
                || !"outpost".equals(site.type())) {
            VillagerSimData.clearOutpostSiteId(villager);
            return false;
        }

        VillageSavedData.VillageRecord village = data.village(villageId.get()).orElse(null);
        if (village == null) {
            VillagerSimData.clearOutpostSiteId(villager);
            return false;
        }

        if (!"active".equals(site.state())) {
            if (moveTowardLoaded(villager, level, village.center(), 0.78D)) return true;
            if (villager.blockPosition().distManhattan(village.center()) <= 32) {
                VillagerSimData.clearOutpostSiteId(villager);
            }
            return true;
        }

        BlockPos center = center(site);
        if (villager.blockPosition().distManhattan(center) > 20) {
            moveTowardLoaded(villager, level, center, 0.80D);
            return true;
        }

        site.setLastUsedGameTime(level.getGameTime());
        data.touch();
        return false;
    }

    public static boolean isOperational(
            ServerLevel level,
            VillageSavedData data,
            VillageSavedData.VillageRecord village,
            VillageSavedData.WorkSiteRecord site) {
        if (site == null || village == null
                || !"outpost".equals(site.type())
                || !"active".equals(site.state())
                || site.purpose().isBlank()) {
            return false;
        }

        int demand = purposeDemandPermille(village, site.purpose());
        if (demand <= 1000) return false;
        if (!hasActiveRoute(data, village, site)) return false;

        ResourceState resource = localResourceState(level, site);
        return resource != ResourceState.DEPLETED;
    }

    private static void refreshVillage(ServerLevel level, UUID villageId) {
        VillageSavedData data = VillageSavedData.get(level);
        VillageSavedData.VillageRecord village = data.village(villageId).orElse(null);
        if (village == null || "abandoned".equals(village.lifecycle()) || "merged".equals(village.lifecycle())) {
            return;
        }

        long now = level.getGameTime();
        for (VillageSavedData.WorkSiteRecord site : data.workSitesForVillage(villageId)) {
            if (!"outpost".equals(site.type())) continue;
            if (now - site.lastLifecycleGameTime() < DAY) continue;
            site.setLastLifecycleGameTime(now);

            if ("abandoned".equals(site.state())) {
                releaseLoadedWorkers(level, village, site.id());
                continue;
            }

            boolean demand = purposeDemandPermille(village, site.purpose()) > 1000;
            boolean route = hasActiveRoute(data, village, site);
            ResourceState resources = localResourceState(level, site);

            if (demand && route && resources != ResourceState.DEPLETED) {
                site.setState("active");
                site.setIdleDays(0);
                assignWorkers(level, village, site);
                continue;
            }

            if (!route && now - site.createdGameTime() < ESTABLISHING_GRACE) {
                site.setState("establishing");
                releaseLoadedWorkers(level, village, site.id());
                continue;
            }

            // Do not count unloaded/unknown physical terrain as depletion.
            boolean realIdle = !demand || !route || resources == ResourceState.DEPLETED;
            if (!realIdle) continue;

            int idle = site.idleDays() + 1;
            site.setIdleDays(idle);
            if (idle >= ABANDON_AFTER_IDLE_DAYS) site.setState("abandoned");
            else if (idle >= INACTIVE_AFTER_IDLE_DAYS) site.setState("inactive");

            if (!"active".equals(site.state())) releaseLoadedWorkers(level, village, site.id());
        }
        data.touch();
    }

    private static void assignWorkers(ServerLevel level, VillageSavedData.VillageRecord village,
                                      VillageSavedData.WorkSiteRecord site) {
        String requiredDuty = switch (site.purpose()) {
            case "forestry" -> "forester";
            case "quarry" -> "quarry";
            default -> "";
        };
        if (requiredDuty.isBlank()) return;

        int demand = purposeDemandPermille(village, site.purpose());
        int target = demand >= 1350 ? 2 : 1;

        List<Villager> residents = level.getEntitiesOfClass(
                Villager.class,
                new net.minecraft.world.phys.AABB(village.center()).inflate(384.0D, 96.0D, 384.0D),
                v -> v.isAlive()
                        && !v.isBaby()
                        && v.getVillagerData().getProfession() != VillagerProfession.NITWIT
                        && VillagerSimData.villageId(v).filter(village.id()::equals).isPresent()
                        && VillagerSimData.migrationId(v).isEmpty()
        );

        List<Villager> already = residents.stream()
                .filter(v -> VillagerSimData.outpostSiteId(v).filter(site.id()::equals).isPresent())
                .toList();
        if (already.size() >= target) return;

        residents.stream()
                .filter(v -> requiredDuty.equals(VillagerSimData.duty(v)))
                .filter(v -> VillagerSimData.outpostSiteId(v).isEmpty())
                .sorted(Comparator.comparing(v -> v.getUUID().toString()))
                .limit(target - already.size())
                .forEach(v -> VillagerSimData.setOutpostSiteId(v, site.id()));
    }

    private static void releaseLoadedWorkers(ServerLevel level, VillageSavedData.VillageRecord village, UUID siteId) {
        for (Villager villager : level.getEntitiesOfClass(
                Villager.class,
                new net.minecraft.world.phys.AABB(village.center()).inflate(384.0D, 96.0D, 384.0D),
                v -> v.isAlive()
                        && VillagerSimData.villageId(v).filter(village.id()::equals).isPresent()
                        && VillagerSimData.outpostSiteId(v).filter(siteId::equals).isPresent())) {
            // Keep the assignment while returning so handleAssignedWorker can bring them home.
        }
    }

    private static int purposeDemandPermille(VillageSavedData.VillageRecord village, String purpose) {
        return switch (purpose) {
            case "forestry" -> village.marketPermille("wood");
            case "quarry" -> village.marketPermille("stone");
            default -> 1000;
        };
    }

    private static boolean hasActiveRoute(
            VillageSavedData data,
            VillageSavedData.VillageRecord village,
            VillageSavedData.WorkSiteRecord site) {
        BlockPos outpost = center(site);
        for (UUID routeId : village.routeIds()) {
            VillageSavedData.RouteRecord route = data.route(routeId).orElse(null);
            if (route == null || !"active".equals(route.state())) continue;

            boolean touchesOutpost = route.from().distManhattan(outpost) <= 24
                    || route.to().distManhattan(outpost) <= 24;
            if (!touchesOutpost) continue;

            for (Long packedCenter : village.districtCenters()) {
                BlockPos district = BlockPos.of(packedCenter);
                if (route.from().distManhattan(district) <= 64
                        || route.to().distManhattan(district) <= 64) {
                    return true;
                }
            }
        }
        return false;
    }

    private static ResourceState localResourceState(ServerLevel level, VillageSavedData.WorkSiteRecord site) {
        BlockPos siteCenter = center(site);
        BlockPos column = new BlockPos(siteCenter.getX(), level.getMinBuildHeight(), siteCenter.getZ());
        if (!VillageSimulationScheduler.isChunkLoaded(level, column)) return ResourceState.UNKNOWN;

        RandomSource random = RandomSource.create(
                site.id().getLeastSignificantBits() ^ (level.getGameTime() / DAY)
        );
        int useful = 0;
        for (int sample = 0; sample < 48; sample++) {
            if (!VillageSimulationScheduler.tryConsumeBlockProbe(level)) return ResourceState.UNKNOWN;

            int x = siteCenter.getX() + random.nextInt(41) - 20;
            int z = siteCenter.getZ() + random.nextInt(41) - 20;
            BlockPos probeColumn = new BlockPos(x, level.getMinBuildHeight(), z);
            if (!VillageSimulationScheduler.isChunkLoaded(level, probeColumn)) continue;

            int y = level.getHeight(net.minecraft.world.level.levelgen.Heightmap.Types.MOTION_BLOCKING_NO_LEAVES, x, z);
            BlockPos surface = new BlockPos(x, Math.max(level.getMinBuildHeight(), y - 1), z);

            if ("forestry".equals(site.purpose())) {
                for (int dy = 0; dy <= 7; dy++) {
                    var state = level.getBlockState(surface.above(dy));
                    if (state.is(BlockTags.LOGS) || state.is(BlockTags.LEAVES)) {
                        useful++;
                        break;
                    }
                }
            } else if ("quarry".equals(site.purpose())) {
                var state = level.getBlockState(surface);
                if (surface.getY() >= 0
                        && (state.is(Blocks.STONE) || state.is(Blocks.ANDESITE)
                        || state.is(Blocks.DIORITE) || state.is(Blocks.GRANITE))) {
                    useful++;
                }
            }

            if (useful >= 4) return ResourceState.AVAILABLE;
        }
        return ResourceState.DEPLETED;
    }

    private static boolean moveTowardLoaded(Villager villager, ServerLevel level, BlockPos target, double speed) {
        if (villager.blockPosition().distManhattan(target) <= 8) return false;

        double dx = target.getX() + 0.5D - villager.getX();
        double dz = target.getZ() + 0.5D - villager.getZ();
        double length = Math.max(0.001D, Math.sqrt(dx * dx + dz * dz));
        int wx = (int)Math.floor(villager.getX() + dx / length * Math.min(12.0D, length));
        int wz = (int)Math.floor(villager.getZ() + dz / length * Math.min(12.0D, length));
        BlockPos column = new BlockPos(wx, level.getMinBuildHeight(), wz);
        if (!VillageSimulationScheduler.isChunkLoaded(level, column)) return true;

        int wy = level.getHeight(net.minecraft.world.level.levelgen.Heightmap.Types.MOTION_BLOCKING_NO_LEAVES, wx, wz);
        villager.getNavigation().moveTo(wx + 0.5D, wy, wz + 0.5D, speed);
        return true;
    }

    private static BlockPos center(VillageSavedData.WorkSiteRecord site) {
        return new BlockPos(
                (site.min().getX() + site.max().getX()) / 2,
                (site.min().getY() + site.max().getY()) / 2,
                (site.min().getZ() + site.max().getZ()) / 2
        );
    }

    private enum ResourceState {
        UNKNOWN,
        AVAILABLE,
        DEPLETED
    }
}
