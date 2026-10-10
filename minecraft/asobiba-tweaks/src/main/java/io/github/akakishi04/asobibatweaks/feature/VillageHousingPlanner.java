package io.github.akakishi04.asobibatweaks.feature;

import java.util.List;
import java.util.UUID;
import net.minecraft.core.BlockPos;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.entity.ai.memory.MemoryModuleType;
import net.minecraft.world.entity.npc.Villager;
import net.minecraft.world.item.Items;
import net.minecraft.world.phys.AABB;

/**
 * V89: village-wide pressure-based housing decision instead of a raw
 * "beds <= population + 1" rule.
 *
 * Validated accessible BuildingRecords (including cached unloaded buildings)
 * are authoritative. A small bounded allowance for nearby vanilla beds
 * permits gradual adoption, without treating every unrecognized bed in a
 * region as free capacity. Persistent VillageRecord cooldown prevents
 * speculative house spam. Acute actual overcrowding/fire can bypass it.
 */
public final class VillageHousingPlanner {
    private static final int MIN_RESERVE = 2;
    private static final long COOLDOWN_TICKS = 3L * 24_000L;

    private VillageHousingPlanner() {}

    public static Demand assess(ServerLevel level, VillageSavedData data,
                                UUID villageId, int observedPopulation,
                                int observedBeds) {
        VillageSavedData.VillageRecord village = data.village(villageId).orElse(null);
        if (village == null || !"active".equals(village.lifecycle())) {
            return Demand.none();
        }
        int recognized = 0;
        for (UUID id : village.buildingIds()) {
            VillageSavedData.BuildingRecord building = data.building(id).orElse(null);
            if (building == null || !building.villageId().equals(villageId)
                    || !VillageActivityBoundary.contains(village, building.min())
                    || !("residential".equals(building.classification())
                        || "mixed_use".equals(building.classification()))
                    || !"valid".equals(building.validationState())) continue;
            // If a building chunk is unloaded, preserve its cached capacity;
            // unloaded != empty or invalid. Dirty chunk records revalidate
            // lazily when the physical home becomes observable again.
            recognized = Math.min(512,
                    recognized + Math.max(0, building.validatedCapacity()));
        }

        List<Villager> residents = level.getEntitiesOfClass(
                Villager.class,
                VillageActivityBoundary.searchBounds(village),
                v -> v.isAlive() && VillageActivityBoundary.contains(village, v.blockPosition())
                        && VillagerSimData.villageId(v).filter(villageId::equals).isPresent());
        int loadedAdults = 0;
        int welfareSum = 0;
        int chronicallyWithoutHome = 0;
        for (Villager resident : residents) {
            if (resident.isBaby()) continue;
            loadedAdults++;
            welfareSum += VillagerSimData.welfare(resident);
            long observedActive = VillagerSimData.activeObservedTicks(resident);
            long lastSleep = VillagerSimData.lastSleepActive(resident);
            if (!resident.getBrain().hasMemoryValue(MemoryModuleType.HOME)
                    && observedActive >= 2L * 24_000L
                    && observedActive - lastSleep >= 24_000L) {
                chronicallyWithoutHome++;
            }
        }
        int welfare = loadedAdults == 0 ? 100 : welfareSum / loadedAdults;
        int population = Math.max(1, observedPopulation);
        // Only a modest number of nearby unadopted vanilla beds are admitted
        // when an indexed building catalog already exists. This prevents
        // random protected/private beds from suppressing all housing work.
        int usable = recognized > 0
                ? Math.max(recognized,
                        Math.min(Math.max(0, observedBeds),
                                recognized + Math.max(MIN_RESERVE, population / 6)))
                : Math.max(0, observedBeds);

        int food = 0;
        for (var item : new net.minecraft.world.item.Item[]{
                Items.BREAD, Items.CARROT, Items.POTATO, Items.BEETROOT,
                Items.WHEAT, Items.COD, Items.SALMON}) {
            food = Math.min(Integer.MAX_VALUE,
                    food + village.availableCount(VillageStorageService.itemKey(item)));
        }

        boolean activeResidentialProject = data.activeProjectsForVillage(villageId).stream()
                .anyMatch(p -> "building".equals(p.type())
                        && p.templateId().startsWith("house_"));
        return evaluate(population, usable, chronicallyWithoutHome,
                welfare, food, level.getGameTime(),
                village.nextHousingExpansionGameTime(),
                !"none".equals(village.fireEmergencyState()), activeResidentialProject);
    }

    /** Pure acceptance kernel: all inputs have explicit physical/cached origins. */
    static Demand evaluate(int population, int usableBeds, int chronicHomeless,
                           int welfare, int food, long now, long cooldownUntil,
                           boolean fireEmergency, boolean activeHouseProject) {
        int people = Math.max(1, population);
        int capacity = Math.max(0, usableBeds);
        int desired = people + Math.max(MIN_RESERVE, (people + 4) / 5);
        int shortage = Math.max(0, desired - capacity);
        if (shortage == 0) {
            return new Demand(false, false, 0, capacity, desired, "adequate reserve");
        }

        boolean acute = capacity <= people
                || chronicHomeless >= 2 && capacity < desired;
        boolean exceptional = fireEmergency && shortage > 0;
        int score = Math.min(100,
                shortage * 12 + (acute ? 40 : 0)
                        + Math.min(24, Math.max(0, chronicHomeless) * 8)
                        + (welfare < 45 ? 12 : 0)
                        + (exceptional ? 18 : 0));
        if (activeHouseProject) {
            return new Demand(false, acute, score, capacity, desired,
                    "home already under construction");
        }
        if (now < cooldownUntil && !acute && !exceptional) {
            return new Demand(false, false, score, capacity, desired,
                    "recent house cooldown");
        }
        if (food < Math.max(12, people * 2) && !acute && !exceptional) {
            return new Demand(false, false, score, capacity, desired,
                    "food reserve too low for discretionary expansion");
        }
        return new Demand(true, acute || exceptional, score, capacity, desired,
                acute ? "overcrowded" : exceptional ? "fire replacement" : "housing reserve");
    }

    public static void recordFinishedHouse(ServerLevel level,
                                           VillageSavedData data, UUID villageId) {
        data.village(villageId).ifPresent(village -> {
            village.setNextHousingExpansionGameTime(
                    level.getGameTime() + COOLDOWN_TICKS);
            data.touch();
        });
    }

    public record Demand(boolean build, boolean acute, int score,
                         int capacity, int desired, String reason) {
        static Demand none() {
            return new Demand(false, false, 0, 0, 0, "no active village");
        }
    }
}
