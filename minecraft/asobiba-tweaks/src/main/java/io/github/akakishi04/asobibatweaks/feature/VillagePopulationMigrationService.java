package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import net.minecraft.core.BlockPos;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.tags.ItemTags;
import net.minecraft.world.entity.npc.Villager;
import net.minecraft.world.entity.npc.VillagerProfession;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.phys.AABB;
import net.neoforged.bus.api.SubscribeEvent;
import net.neoforged.neoforge.event.entity.living.LivingDeathEvent;
import net.neoforged.neoforge.event.tick.EntityTickEvent;

/**
 * Sustainable-population, migration, refugee and return lifecycle built on persistent VillageRecords.
 */
public final class VillagePopulationMigrationService {
    private static final long DAY = 24_000L;
    private static final long PLANNED_MIGRATION_COOLDOWN = 5L * DAY;
    private static final long PLANNED_REMIGRATION_COOLDOWN = 7L * DAY;
    private static final long REFUGEE_RETURN_GRACE = 2L * DAY;
    private static final long PERMANENT_DISPLACED_ACTIVE = 7L * DAY;

    public VillagePopulationMigrationService() {
    }

    @SubscribeEvent
    public void onVillagerDeath(LivingDeathEvent event) {
        if (!(event.getEntity() instanceof Villager villager)
                || villager.level().isClientSide()
                || !(villager.level() instanceof ServerLevel level)) {
            return;
        }

        VillageSavedData data = VillageSavedData.get(level);
        VillagerSimData.villageId(villager)
                .ifPresent(villageId -> data.unregisterResident(villageId, villager.getUUID()));

        VillagerSimData.migrationId(villager).ifPresent(migrationId -> {
            VillageSavedData.MigrationRecord migration = data.migration(migrationId).orElse(null);
            if (migration == null) return;
            migration.removeMember(villager.getUUID());
            migration.setUpdatedGameTime(level.getGameTime());
            if (migration.members().isEmpty()) data.removeMigration(migrationId);
            else data.touch();
        });
    }

    @SubscribeEvent
    public void onVillagerTick(EntityTickEvent.Post event) {
        if (!AsobibaTweaksConfig.VILLAGE_SIMULATION_ENABLED.getAsBoolean()
                || !(event.getEntity() instanceof Villager villager)
                || villager.level().isClientSide()
                || villager.tickCount % 200 != Math.floorMod(villager.getId(), 200)) {
            return;
        }

        ServerLevel level = (ServerLevel)villager.level();
        VillageIdentityBootstrap.ensure(villager, level);

        if (AsobibaTweaksConfig.VILLAGE_REFUGEES_ENABLED.getAsBoolean()) {
            tickTraveler(villager, level);
            tickDisplacedLifecycle(villager, level);
        }

        VillagerSimData.villageId(villager).ifPresent(villageId -> scheduleDaily(level, villageId));
    }

    public static boolean startFoundingGroup(ServerLevel level, Villager carpenter,
                                             UUID destinationVillageId, int requestedSize) {
        Optional<UUID> sourceId = VillagerSimData.villageId(carpenter);
        if (sourceId.isEmpty() || sourceId.get().equals(destinationVillageId)) return false;

        VillageSavedData data = VillageSavedData.get(level);
        VillageSavedData.VillageRecord source = data.village(sourceId.get()).orElse(null);
        VillageSavedData.VillageRecord destination = data.village(destinationVillageId).orElse(null);
        if (source == null || destination == null) return false;
        if (hasOpenMigration(data, source.id())) return false;

        List<Villager> candidates = loadedResidents(level, source);
        candidates.removeIf(v -> v.isBaby() || VillagerSimData.migrationId(v).isPresent());
        if (candidates.size() < 4) return false;

        candidates.sort(Comparator
                .comparingInt(VillagePopulationMigrationService::founderPriority)
                .thenComparing(v -> v.getUUID().toString()));

        int sourcePopulation = Math.max(source.lastKnownPopulation(), source.residentIds().size());
        int size = Math.max(4, Math.min(6, requestedSize));
        size = Math.min(size, candidates.size());
        size = Math.min(size, Math.max(0, sourcePopulation - 4));
        if (size < 4) return false;

        List<Villager> selected = new ArrayList<>(candidates.subList(0, size));
        VillageSavedData.MigrationRecord migration = data.createMigration(
                source.id(), destinationVillageId, selected.stream().map(Villager::getUUID).toList());
        migration.setKind("founding");
        migration.setTarget(destination.center());
        migration.setState("travelling");
        migration.setCreatedGameTime(level.getGameTime());
        migration.setUpdatedGameTime(level.getGameTime());

        for (Villager villager : selected) {
            VillagerSimData.setMigrationId(villager, migration.id());
            VillagerSimData.setRemigrationCooldownUntil(villager,
                    level.getGameTime() + PLANNED_REMIGRATION_COOLDOWN);
        }

        loadTravelFood(selected, level);
        loadFoundingSupplies(selected, level);

        source.setNextFissionGameTime(level.getGameTime() + 30L * DAY);
        destination.setNextFissionGameTime(level.getGameTime() + 30L * DAY);
        data.touch();
        return true;
    }

    private static int founderPriority(Villager villager) {
        VillagerProfession profession = villager.getVillagerData().getProfession();
        if (profession == VillagerProfession.FARMER) return 0;
        if ("carpenter".equals(VillagerSimData.duty(villager))) return 1;
        if (profession == VillagerProfession.NONE) return 2;
        if (profession == VillagerProfession.FISHERMAN) return 3;
        if (profession == VillagerProfession.MASON || profession == VillagerProfession.FLETCHER) return 4;
        if (profession == VillagerProfession.NITWIT) return 9;
        return 5;
    }

    public static boolean allowBirth(Villager parentA, Villager parentB, ServerLevel level) {
        VillageIdentityBootstrap.ensure(parentA, level);
        VillageIdentityBootstrap.ensure(parentB, level);

        Optional<UUID> villageId = VillagerSimData.villageId(parentA);
        if (villageId.isEmpty() || !villageId.equals(VillagerSimData.villageId(parentB))) return false;

        VillageSavedData data = VillageSavedData.get(level);
        VillageSavedData.VillageRecord village = data.village(villageId.get()).orElse(null);
        if (village == null || "evacuating".equals(village.lifecycle()) || "abandoned".equals(village.lifecycle())) {
            return false;
        }

        long now = level.getGameTime();
        if (now < village.nextBirthGameTime()) return false;
        if (village.settlementViability() < 60) return false;
        if (VillagerSimData.welfare(parentA) < 60 || VillagerSimData.welfare(parentB) < 60) return false;

        int population = Math.max(village.lastKnownPopulation(), village.residentIds().size());
        int sustainable = village.sustainablePopulation();
        if (sustainable <= 0 || population * 10 >= sustainable * 9) return false;

        int housing = housingCapacity(data, village);
        if (housing < population + 2) return false;

        int food = foodCount(village);
        if (food < Math.max(12, population * 12)) return false;

        boolean recovering = now < village.recoveryGrowthUntil();
        village.setNextBirthGameTime(now + (recovering ? 2L : 3L) * DAY);
        data.touch();
        return true;
    }

    private static void scheduleDaily(ServerLevel level, UUID villageId) {
        VillageSavedData data = VillageSavedData.get(level);
        VillageSavedData.VillageRecord village = data.village(villageId).orElse(null);
        if (village == null) return;

        long now = level.getGameTime();
        if (now < village.nextDemographicUpdateGameTime()) return;
        village.setNextDemographicUpdateGameTime(now + DAY);
        data.touch();

        VillageSimulationScheduler.enqueuePlanning(
                level,
                "demographic:" + villageId,
                () -> refreshVillage(level, villageId)
        );
    }

    private static void refreshVillage(ServerLevel level, UUID villageId) {
        VillageEconomyService.refreshVillage(level, villageId);

        VillageSavedData data = VillageSavedData.get(level);
        VillageSavedData.VillageRecord village = data.village(villageId).orElse(null);
        if (village == null) return;

        int population = Math.max(village.lastKnownPopulation(), village.residentIds().size());
        int sustainable = village.sustainablePopulation();
        int viability = village.settlementViability();

        boolean overpopulated = sustainable > 0 && population * 100 > sustainable * 110;
        village.recordDemographicDay(viability < 40, viability < 25, overpopulated, viability >= 60);

        if (village.collapsePressure5Of7()) {
            village.setLifecycle("evacuating");
        } else if (viability < 40) {
            village.setLifecycle("strained");
        } else if (village.stableViabilityDays() >= 3
                && ("strained".equals(village.lifecycle()) || "evacuating".equals(village.lifecycle()))) {
            village.setLifecycle("active");
        }

        long now = level.getGameTime();
        boolean pressure = village.migrationPressure3Of5() || village.overpopulationPressure3Of5();
        boolean emergency = village.collapsePressure5Of7() || viability <= 19;

        if (AsobibaTweaksConfig.VILLAGE_REFUGEES_ENABLED.getAsBoolean()
                && (pressure || emergency)
                && now >= village.nextMigrationGameTime()
                && !hasOpenMigration(data, villageId)) {
            startMigrationWave(level, data, village, emergency);
        }

        if (population <= 0 && "evacuating".equals(village.lifecycle())) {
            village.setLifecycle("abandoned");
        }

        retryFoundingChildren(level, data, village);
        updateMergeEvidence(level, data, village);
        data.touch();
    }

    private static void retryFoundingChildren(ServerLevel level, VillageSavedData data,
                                              VillageSavedData.VillageRecord parent) {
        if (parent.settlementViability() < 60 || "evacuating".equals(parent.lifecycle())
                || "abandoned".equals(parent.lifecycle()) || "merged".equals(parent.lifecycle())) {
            return;
        }

        List<Villager> loadedParents = loadedResidents(level, parent);
        if (loadedParents.size() < 5) return;

        Villager representative = loadedParents.stream()
                .filter(v -> !v.isBaby())
                .filter(v -> VillagerSimData.migrationId(v).isEmpty())
                .min(Comparator
                        .comparingInt((Villager v) -> "carpenter".equals(VillagerSimData.duty(v)) ? 0 : 1)
                        .thenComparing(v -> v.getUUID().toString()))
                .orElse(null);
        if (representative == null) return;

        for (VillageSavedData.VillageRecord child : data.villagesView().values()) {
            if (!parent.id().equals(child.parentVillageId())) continue;
            if (!"founding".equals(child.lifecycle())) continue;
            if (!child.residentIds().isEmpty()) continue;
            if (hasOpenMigrationToDestination(data, child.id())) continue;

            startFoundingGroup(level, representative, child.id(), 4);
            return;
        }
    }

    private static boolean hasOpenMigrationToDestination(VillageSavedData data, UUID destinationVillageId) {
        for (VillageSavedData.MigrationRecord migration : data.migrationsView().values()) {
            if (!destinationVillageId.equals(migration.destinationVillageId())) continue;
            if (!"complete".equals(migration.state()) && !"cancelled".equals(migration.state())) return true;
        }
        return false;
    }

    private static void updateMergeEvidence(ServerLevel level, VillageSavedData data,
                                            VillageSavedData.VillageRecord village) {
        if (!"active".equals(village.lifecycle()) || village.settlementViability() < 60) return;

        for (VillageSavedData.VillageRecord other : data.villagesView().values()) {
            if (other.id().equals(village.id())) continue;
            if (!"active".equals(other.lifecycle()) || other.settlementViability() < 60) continue;
            if (village.center().distManhattan(other.center()) > 192) {
                village.setMergeEvidenceDays(other.id(), 0);
                continue;
            }

            boolean roadConnected = roadNetworksTouch(data, village, other);
            boolean livedCrossing = hasCrossBoundaryResident(level, village, other);
            int days = roadConnected && livedCrossing
                    ? village.mergeEvidenceDays(other.id()) + 1
                    : 0;
            village.setMergeEvidenceDays(other.id(), days);

            if (days < 5) continue;

            VillageSavedData.VillageRecord target = chooseMergeTarget(village, other);
            VillageSavedData.VillageRecord source = target.id().equals(village.id()) ? other : village;
            if (data.mergeVillageInto(source.id(), target.id())) {
                for (Villager resident : loadedResidents(level, source)) {
                    VillagerSimData.setVillageId(resident, target.id());
                    data.registerResident(target.id(), resident.getUUID());
                }
                return;
            }
        }
    }

    private static VillageSavedData.VillageRecord chooseMergeTarget(
            VillageSavedData.VillageRecord a, VillageSavedData.VillageRecord b) {
        int popA = Math.max(a.lastKnownPopulation(), a.residentIds().size());
        int popB = Math.max(b.lastKnownPopulation(), b.residentIds().size());
        if (popA != popB) return popA > popB ? a : b;
        if (a.createdGameTime() != b.createdGameTime()) {
            return a.createdGameTime() < b.createdGameTime() ? a : b;
        }
        return a.id().toString().compareTo(b.id().toString()) <= 0 ? a : b;
    }

    private static boolean roadNetworksTouch(VillageSavedData data,
                                             VillageSavedData.VillageRecord a,
                                             VillageSavedData.VillageRecord b) {
        List<VillageSavedData.RouteRecord> routesA = new ArrayList<>();
        for (UUID id : a.routeIds()) {
            VillageSavedData.RouteRecord route = data.route(id).orElse(null);
            if (route != null && "active".equals(route.state())) routesA.add(route);
        }

        List<VillageSavedData.RouteRecord> routesB = new ArrayList<>();
        for (UUID id : b.routeIds()) {
            VillageSavedData.RouteRecord route = data.route(id).orElse(null);
            if (route != null && "active".equals(route.state())) routesB.add(route);
        }

        if (routesA.isEmpty() || routesB.isEmpty()) return false;
        for (VillageSavedData.RouteRecord ra : routesA) {
            for (VillageSavedData.RouteRecord rb : routesB) {
                if (routeEndpointNear(ra.from(), rb.from())
                        || routeEndpointNear(ra.from(), rb.to())
                        || routeEndpointNear(ra.to(), rb.from())
                        || routeEndpointNear(ra.to(), rb.to())) {
                    return true;
                }
            }
        }
        return false;
    }

    private static boolean routeEndpointNear(BlockPos a, BlockPos b) {
        return a.distManhattan(b) <= 24;
    }

    private static boolean hasCrossBoundaryResident(ServerLevel level,
                                                    VillageSavedData.VillageRecord a,
                                                    VillageSavedData.VillageRecord b) {
        for (Villager villager : loadedResidents(level, a)) {
            if (VillagerSimData.migrationId(villager).isPresent() || VillagerSimData.displaced(villager)) continue;
            if (villager.blockPosition().distManhattan(b.center()) <= 48) return true;
        }
        for (Villager villager : loadedResidents(level, b)) {
            if (VillagerSimData.migrationId(villager).isPresent() || VillagerSimData.displaced(villager)) continue;
            if (villager.blockPosition().distManhattan(a.center()) <= 48) return true;
        }
        return false;
    }

    private static boolean hasOpenMigration(VillageSavedData data, UUID originVillageId) {
        for (VillageSavedData.MigrationRecord migration : data.migrationsView().values()) {
            if (!originVillageId.equals(migration.originVillageId())) continue;
            if (!"complete".equals(migration.state()) && !"cancelled".equals(migration.state())) return true;
        }
        return false;
    }

    private static void startMigrationWave(ServerLevel level, VillageSavedData data,
                                           VillageSavedData.VillageRecord source, boolean emergency) {
        VillageSavedData.VillageRecord destination = chooseDestination(data, source, emergency);
        if (destination == null) return;

        List<Villager> candidates = loadedResidents(level, source);
        candidates.removeIf(v -> VillagerSimData.migrationId(v).isPresent()
                || (!emergency && level.getGameTime() < VillagerSimData.remigrationCooldownUntil(v)));
        if (candidates.isEmpty()) return;

        int population = Math.max(1, source.lastKnownPopulation());
        int desired = emergency
                ? Math.max(2, Math.min(6, Math.max(2, population / 4)))
                : Math.max(2, Math.min(6, Math.max(2, (population + 9) / 10)));
        if (!emergency) desired = Math.min(desired, Math.max(1, population - 1));
        desired = Math.min(desired, candidates.size());
        if (desired <= 0) return;

        List<Villager> selected = selectMigrationGroup(candidates, desired);
        if (selected.isEmpty()) return;

        List<UUID> memberIds = selected.stream().map(Villager::getUUID).toList();
        VillageSavedData.MigrationRecord migration =
                data.createMigration(source.id(), destination.id(), memberIds);
        migration.setKind(emergency ? "refugee" : "planned");
        migration.setTarget(destination.center());
        migration.setState("travelling");
        migration.setCreatedGameTime(level.getGameTime());
        migration.setUpdatedGameTime(level.getGameTime());

        for (Villager villager : selected) {
            VillagerSimData.setMigrationId(villager, migration.id());
            if (emergency) VillagerSimData.setDisplaced(villager, source.id());
        }

        loadTravelFood(selected, level);

        source.setNextMigrationGameTime(
                level.getGameTime() + (emergency ? DAY : PLANNED_MIGRATION_COOLDOWN)
        );
        data.touch();
    }

    private static VillageSavedData.VillageRecord chooseDestination(
            VillageSavedData data, VillageSavedData.VillageRecord source, boolean emergency) {
        return data.villagesView().values().stream()
                .filter(v -> !v.id().equals(source.id()))
                .filter(v -> !"abandoned".equals(v.lifecycle()) && !"evacuating".equals(v.lifecycle()))
                .filter(v -> v.settlementViability() >= (emergency ? 50 : 60))
                .filter(v -> {
                    int sustainable = v.sustainablePopulation();
                    int population = Math.max(v.lastKnownPopulation(), v.residentIds().size());
                    if (sustainable <= 0) return false;
                    return emergency
                            ? population * 100 < sustainable * 120
                            : population < sustainable;
                })
                .min(Comparator
                        .comparingInt((VillageSavedData.VillageRecord v) ->
                                source.center().distManhattan(v.center()))
                        .thenComparing(v -> v.id().toString()))
                .orElse(null);
    }

    private static List<Villager> loadedResidents(ServerLevel level, VillageSavedData.VillageRecord village) {
        return new ArrayList<>(level.getEntitiesOfClass(
                Villager.class,
                new AABB(village.center()).inflate(160.0D, 80.0D, 160.0D),
                v -> v.isAlive()
                        && VillagerSimData.villageId(v).filter(village.id()::equals).isPresent()
        ));
    }

    private static List<Villager> selectMigrationGroup(List<Villager> candidates, int desired) {
        candidates.sort(Comparator
                .comparingInt((Villager v) -> v.isBaby() ? 1 : 0)
                .thenComparing(v -> v.getUUID().toString()));

        List<Villager> selected = new ArrayList<>();
        for (Villager villager : candidates) {
            if (selected.size() >= desired) break;
            selected.add(villager);
        }

        // If a child is selected and an adult is still available, make sure at least one adult travels too.
        boolean hasChild = selected.stream().anyMatch(Villager::isBaby);
        boolean hasAdult = selected.stream().anyMatch(v -> !v.isBaby());
        if (hasChild && !hasAdult) {
            candidates.stream().filter(v -> !v.isBaby()).findFirst().ifPresent(adult -> {
                if (!selected.contains(adult)) {
                    if (selected.size() >= desired) selected.remove(selected.size() - 1);
                    selected.add(0, adult);
                }
            });
        }
        return selected;
    }

    private static void loadTravelFood(List<Villager> travelers, ServerLevel level) {
        if (travelers.isEmpty()) return;
        Villager sourceAccess = travelers.getFirst();
        int requested = Math.max(4, travelers.size() * 6);

        List<ItemStack> food = VillageStorageService.extractMatching(
                sourceAccess,
                level,
                stack -> stack.is(Items.BREAD) || stack.is(Items.CARROT)
                        || stack.is(Items.POTATO) || stack.is(Items.BEETROOT),
                Math.min(requested, VillageStorageService.countMatching(
                        sourceAccess, level,
                        stack -> stack.is(Items.BREAD) || stack.is(Items.CARROT)
                                || stack.is(Items.POTATO) || stack.is(Items.BEETROOT)))
        );

        int travelerIndex = 0;
        for (ItemStack stack : food) {
            ItemStack remainder = insertInventory(travelers.get(travelerIndex % travelers.size()), stack);
            travelerIndex++;
            if (!remainder.isEmpty()) {
                VillageStorageService.insert(sourceAccess, level, remainder);
            }
        }
    }

    private static void loadFoundingSupplies(List<Villager> travelers, ServerLevel level) {
        if (travelers.isEmpty()) return;
        Villager sourceAccess = travelers.getFirst();

        List<ItemStack> planks = VillageStorageService.extractMatching(
                sourceAccess, level, stack -> stack.is(ItemTags.PLANKS),
                Math.min(32, VillageStorageService.countMatching(
                        sourceAccess, level, stack -> stack.is(ItemTags.PLANKS))));
        List<ItemStack> stone = VillageStorageService.extract(
                sourceAccess, level, Items.COBBLESTONE,
                Math.min(16, VillageStorageService.count(sourceAccess, level, Items.COBBLESTONE)));

        int index = 0;
        for (ItemStack stack : planks) {
            ItemStack remainder = insertInventory(travelers.get(index++ % travelers.size()), stack);
            if (!remainder.isEmpty()) VillageStorageService.insert(sourceAccess, level, remainder);
        }
        for (ItemStack stack : stone) {
            ItemStack remainder = insertInventory(travelers.get(index++ % travelers.size()), stack);
            if (!remainder.isEmpty()) VillageStorageService.insert(sourceAccess, level, remainder);
        }
    }

    private static ItemStack insertInventory(Villager villager, ItemStack incoming) {
        ItemStack work = incoming.copy();
        var inventory = villager.getInventory();

        for (int slot = 0; slot < inventory.getContainerSize() && !work.isEmpty(); slot++) {
            ItemStack current = inventory.getItem(slot);
            if (current.isEmpty() || !ItemStack.isSameItemSameComponents(current, work)
                    || current.getCount() >= current.getMaxStackSize()) continue;
            int move = Math.min(work.getCount(), current.getMaxStackSize() - current.getCount());
            current.grow(move);
            work.shrink(move);
            inventory.setChanged();
        }
        for (int slot = 0; slot < inventory.getContainerSize() && !work.isEmpty(); slot++) {
            if (!inventory.getItem(slot).isEmpty()) continue;
            int move = Math.min(work.getCount(), work.getMaxStackSize());
            inventory.setItem(slot, work.copyWithCount(move));
            work.shrink(move);
            inventory.setChanged();
        }
        return work;
    }

    private static void tickTraveler(Villager villager, ServerLevel level) {
        Optional<UUID> migrationId = VillagerSimData.migrationId(villager);
        if (migrationId.isEmpty()) return;

        VillageSavedData data = VillageSavedData.get(level);
        VillageSavedData.MigrationRecord migration = data.migration(migrationId.get()).orElse(null);
        if (migration == null || !migration.members().contains(villager.getUUID())) {
            VillagerSimData.clearMigrationId(villager);
            return;
        }

        BlockPos target = migration.target();
        if (target == null && migration.destinationVillageId() != null) {
            target = data.village(migration.destinationVillageId()).map(VillageSavedData.VillageRecord::center).orElse(null);
        }
        if (target == null) {
            migration.setState("cancelled");
            VillagerSimData.clearMigrationId(villager);
            data.touch();
            return;
        }

        if (villager.distanceToSqr(target.getCenter()) <= 8.0D * 8.0D) {
            arrive(villager, level, data, migration);
            return;
        }

        double dx = target.getX() + 0.5D - villager.getX();
        double dz = target.getZ() + 0.5D - villager.getZ();
        double length = Math.max(0.001D, Math.sqrt(dx * dx + dz * dz));
        int wx = (int)Math.floor(villager.getX() + dx / length * Math.min(12.0D, length));
        int wz = (int)Math.floor(villager.getZ() + dz / length * Math.min(12.0D, length));
        BlockPos waypointColumn = new BlockPos(wx, level.getMinBuildHeight(), wz);
        if (!VillageSimulationScheduler.isChunkLoaded(level, waypointColumn)) return;

        int wy = level.getHeight(net.minecraft.world.level.levelgen.Heightmap.Types.MOTION_BLOCKING_NO_LEAVES, wx, wz);
        villager.getNavigation().moveTo(wx + 0.5D, wy, wz + 0.5D, 0.82D);
        migration.setUpdatedGameTime(level.getGameTime());
        data.touch();
    }

    private static void arrive(Villager villager, ServerLevel level, VillageSavedData data,
                               VillageSavedData.MigrationRecord migration) {
        UUID destinationId = migration.destinationVillageId();
        if (destinationId == null || data.village(destinationId).isEmpty()) {
            migration.setState("cancelled");
            migration.removeMember(villager.getUUID());
            VillagerSimData.clearMigrationId(villager);
            data.touch();
            return;
        }

        UUID originId = migration.originVillageId();
        data.unregisterResident(originId, villager.getUUID());
        data.registerResident(destinationId, villager.getUUID());
        VillagerSimData.setVillageId(villager, destinationId);
        VillagerSimData.clearMigrationId(villager);

        if ("return".equals(migration.kind())) {
            VillagerSimData.clearDisplaced(villager);
            VillagerSimData.setRemigrationCooldownUntil(villager, level.getGameTime() + PLANNED_REMIGRATION_COOLDOWN);
        } else if ("refugee".equals(migration.kind())) {
            VillagerSimData.setRemigrationCooldownUntil(villager, level.getGameTime() + REFUGEE_RETURN_GRACE);
        } else {
            VillagerSimData.setRemigrationCooldownUntil(villager, level.getGameTime() + PLANNED_REMIGRATION_COOLDOWN);
        }

        migration.removeMember(villager.getUUID());
        migration.setUpdatedGameTime(level.getGameTime());
        if (migration.members().isEmpty()) {
            migration.setState("complete");
            if ("founding".equals(migration.kind())) {
                data.village(destinationId).ifPresent(destination -> destination.setLifecycle("active"));
            }
            data.removeMigration(migration.id());
        } else {
            data.touch();
        }
    }

    private static void tickDisplacedLifecycle(Villager villager, ServerLevel level) {
        if (!VillagerSimData.displaced(villager) || VillagerSimData.migrationId(villager).isPresent()) return;

        Optional<UUID> originId = VillagerSimData.originVillageId(villager);
        Optional<UUID> currentId = VillagerSimData.villageId(villager);
        if (originId.isEmpty() || currentId.isEmpty() || originId.equals(currentId)) {
            VillagerSimData.clearDisplaced(villager);
            return;
        }

        VillageSavedData data = VillageSavedData.get(level);
        VillageSavedData.VillageRecord origin = data.village(originId.get()).orElse(null);
        if (origin == null || "abandoned".equals(origin.lifecycle())) {
            if (VillagerSimData.activeObservedTicks(villager) - VillagerSimData.displacedSinceActive(villager)
                    >= PERMANENT_DISPLACED_ACTIVE) {
                VillagerSimData.clearDisplaced(villager);
            }
            return;
        }

        boolean recovered = origin.settlementViability() >= 60
                && origin.stableViabilityDays() >= 3
                && origin.sustainablePopulation() > origin.lastKnownPopulation();

        if (recovered && level.getGameTime() >= VillagerSimData.remigrationCooldownUntil(villager)) {
            // Stagger returns deterministically; recovery does not recall everyone on one tick.
            long day = level.getGameTime() / DAY;
            if (Math.floorMod(villager.getUUID().hashCode() + Long.hashCode(day), 3) == 0) {
                VillageSavedData.MigrationRecord migration =
                        data.createMigration(currentId.get(), origin.id(), List.of(villager.getUUID()));
                migration.setKind("return");
                migration.setTarget(origin.center());
                migration.setState("travelling");
                migration.setCreatedGameTime(level.getGameTime());
                migration.setUpdatedGameTime(level.getGameTime());
                VillagerSimData.setMigrationId(villager, migration.id());
                data.touch();
            }
            return;
        }

        long displacedActive = VillagerSimData.activeObservedTicks(villager)
                - VillagerSimData.displacedSinceActive(villager);
        if (!recovered && displacedActive >= PERMANENT_DISPLACED_ACTIVE) {
            VillagerSimData.clearDisplaced(villager);
            VillagerSimData.setRemigrationCooldownUntil(villager,
                    level.getGameTime() + PLANNED_REMIGRATION_COOLDOWN);
        }
    }

    private static int housingCapacity(VillageSavedData data, VillageSavedData.VillageRecord village) {
        int housing = 0;
        for (UUID buildingId : village.buildingIds()) {
            VillageSavedData.BuildingRecord building = data.building(buildingId).orElse(null);
            if (building != null && "valid".equals(building.validationState())
                    && "residential".equals(building.classification())) {
                housing += building.validatedCapacity();
            }
        }
        return housing > 0 ? housing : Math.max(village.lastKnownPopulation() + 2, village.sustainablePopulation());
    }

    private static int foodCount(VillageSavedData.VillageRecord village) {
        return village.ledgerCount(VillageStorageService.itemKey(Items.BREAD))
                + village.ledgerCount(VillageStorageService.itemKey(Items.CARROT))
                + village.ledgerCount(VillageStorageService.itemKey(Items.POTATO))
                + village.ledgerCount(VillageStorageService.itemKey(Items.BEETROOT))
                + village.ledgerCount(VillageStorageService.itemKey(Items.WHEAT));
    }
}
