package io.github.akakishi04.asobibatweaks.feature;

import java.util.HashSet;
import java.util.Set;
import java.util.UUID;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.entity.npc.Villager;

/** Low-frequency, active-resident-triggered history and rolling-stat maintenance. */
public final class VillageHistoryMaintenance {
    public static final int MAX_TERMINAL_HISTORY = 64;
    public static final int MAX_RECORDS_PER_PASS = 2_048;
    private static final int MAX_ROUTES_PER_PASS = 512;
    private static final long MAINTENANCE_INTERVAL = 1_200L;
    private static final long ACTIVE_DAY = 24_000L;
    private VillageHistoryMaintenance() {}

    static void schedule(ServerLevel level, VillageSavedData data, VillageSavedData.VillageRecord village) {
        if (village.activeObservedTicks() < village.nextMaintenanceActiveTick()) return;
        village.setNextMaintenanceActiveTick(village.activeObservedTicks() + MAINTENANCE_INTERVAL);
        VillageSimulationScheduler.enqueueReconciliation(level, "history_maintenance:" + village.id(), () -> {
            Set<UUID> safeOwners = new HashSet<>();
            // Observe only nearby loaded owners. Unloaded entities are deliberately not considered safe.
            int examined = 0;
            for (Villager worker : level.getEntitiesOfClass(Villager.class,
                    VillageActivityBoundary.searchBounds(village),
                    v -> v.isAlive() && VillagerSimData.villageId(v).filter(village.id()::equals).isPresent())) {
                if (++examined > 256) break;
                if (worker.getPersistentData().getBoolean("asobibatweaks_build_active")
                        || VillagerSimData.migrationId(worker).isPresent()
                        || !"none".equals(VillagerSimData.emergencyDuty(worker))
                        || VillagerSimData.hasWorkCargo(worker, level.registryAccess(), 16)) continue;
                safeOwners.add(worker.getUUID());
            }
            data.compactTerminalHistory(village.id(), safeOwners, MAX_TERMINAL_HISTORY);
            decayTraffic(data, village);
        });
    }

    static boolean isTerminal(String phase) {
        return "complete".equals(phase) || "cancelled".equals(phase);
    }

    static boolean isEphemeral(VillageSavedData.ProjectRecord project) {
        if (!isTerminal(project.phase())) return false;
        if ("cancelled".equals(project.phase())) return true;
        // Completed construction/reuse/expansion records are physical repair blueprints.
        // Unknown future building templates are retained by default, never guessed disposable.
        if (!"building".equals(project.type())) return !"dock".equals(project.type())
                && !"bridge".equals(project.type());
        return switch (project.templateId()) {
            case "repair_village_shell_v1", "repair_village_bed_v1", "repair_village_stairs_v1",
                    "retrofit_workstation_v1" -> true;
            default -> false;
        };
    }

    static boolean retainsPhysicalOwnership(VillageSavedData.ProjectRecord project) {
        if (!project.parameter("access_ramp_height").isBlank()) {
            try {
                if (Integer.parseInt(project.parameter("access_ramp_placed")) > 0
                        && (project.parameter("access_ramp_clean_cursor").isBlank()
                            || Integer.parseInt(project.parameter("access_ramp_clean_cursor")) >= 0)) return true;
            } catch (NumberFormatException malformed) { return true; }
        }
        // Known freight/work requests remain live ownership even if their outer phase is terminal.
        return project.parameters().keySet().stream().anyMatch(key -> key.startsWith("cargo_")
                || key.startsWith("freight_") || key.startsWith("carrier_"));
    }

    static void decayTraffic(VillageSavedData data, VillageSavedData.VillageRecord village) {
        long days = Math.max(0L, village.activeObservedTicks() - village.lastTrafficDecayActiveTick()) / ACTIVE_DAY;
        if (days <= 0L) return;
        int boundedDays = (int)Math.min(64L, days);
        if (village.routeIds().size() > MAX_ROUTES_PER_PASS) return;
        for (UUID id : village.routeIds()) {
            var route = data.route(id).orElse(null);
            if (route == null) continue;
            int score = route.trafficScore();
            for (int day = 0; day < boundedDays && score > 0; day++) score -= Math.max(1, score / 8);
            route.setTrafficScore(score);
            // Carrier IDs, waypoint geometry and outstanding real dock receipts are not statistics.
        }
        village.setLastTrafficDecayActiveTick(village.activeObservedTicks());
        data.touch();
    }
}
