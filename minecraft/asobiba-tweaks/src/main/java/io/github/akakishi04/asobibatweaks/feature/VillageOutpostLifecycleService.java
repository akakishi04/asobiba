package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.UUID;
import net.minecraft.core.BlockPos;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.util.RandomSource;
import net.minecraft.world.Container;
import net.minecraft.world.entity.npc.Villager;
import net.minecraft.world.entity.npc.VillagerProfession;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.tags.BlockTags;
import net.minecraft.tags.ItemTags;
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
    private static final int PORTER_CARGO_SLOTS = 16;
    private static final int LOCAL_OUTPUT_BUFFER = 8;
    private static final int LOCAL_FOOD_TARGET = 24;
    private static final int FOUNDING_FOOD_TARGET = 48;
    private static final int FARM_PLANTING_TARGET = 8;

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

        if ("porter".equals(VillagerSimData.duty(villager))) {
            return handleOutpostPorter(villager, level, data, village, site);
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
            VillageSavedData.RouteRecord activeRoute = findActiveRoute(data, village, site);
            boolean route = activeRoute != null;
            ResourceState resources = localResourceState(level, site);

            if (demand && route && resources != ResourceState.DEPLETED) {
                activeRoute.setTrafficScore(Math.min(100, activeRoute.trafficScore() + 1));
                ensureRoadUpgradeProject(data, village, activeRoute);
                site.setState("active");
                site.setIdleDays(0);
                assignWorkers(level, village, site);
                assignPorter(level, village, site);
                continue;
            }

            if (activeRoute != null && activeRoute.trafficScore() > 0) {
                activeRoute.setTrafficScore(activeRoute.trafficScore() - 1);
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
            case "fishing" -> "fisher";
            case "farm" -> "farmer";
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
                .filter(v -> requiredDuty.equals(VillagerSimData.duty(v)))
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

    private static void assignPorter(ServerLevel level, VillageSavedData.VillageRecord village,
                                     VillageSavedData.WorkSiteRecord site) {
        VillageSavedData data = VillageSavedData.get(level);
        boolean needsOutputHaul = localOutputCount(data, site) >= 16;
        boolean needsFoodSupply = localFoodCount(data, site) < foodTarget(site);
        boolean needsFarmSupply = needsFarmPlantingSupply(data, site);
        if (!needsOutputHaul && !needsFoodSupply && !needsFarmSupply) return;

        List<Villager> residents = level.getEntitiesOfClass(
                Villager.class,
                new net.minecraft.world.phys.AABB(village.center()).inflate(384.0D, 96.0D, 384.0D),
                v -> v.isAlive()
                        && !v.isBaby()
                        && "porter".equals(VillagerSimData.duty(v))
                        && VillagerSimData.villageId(v).filter(village.id()::equals).isPresent()
                        && VillagerSimData.migrationId(v).isEmpty()
        );

        boolean assigned = residents.stream()
                .anyMatch(v -> VillagerSimData.outpostSiteId(v).filter(site.id()::equals).isPresent());
        if (assigned) return;

        residents.stream()
                .filter(v -> VillagerSimData.outpostSiteId(v).isEmpty())
                .min(Comparator.comparing(v -> v.getUUID().toString()))
                .ifPresent(v -> {
                    VillagerSimData.setOutpostSiteId(v, site.id());
                    VillagerSimData.setOutpostHaulMode(v,
                            needsFoodSupply ? "supply_pickup"
                                    : needsFarmSupply ? "farm_supply_pickup" : "output_pickup");
                });
    }

    private static boolean handleOutpostPorter(
            Villager villager,
            ServerLevel level,
            VillageSavedData data,
            VillageSavedData.VillageRecord village,
            VillageSavedData.WorkSiteRecord site) {
        String mode = VillagerSimData.outpostHaulMode(villager);
        boolean hasCargo = VillagerSimData.hasWorkCargo(
                villager, level.registryAccess(), PORTER_CARGO_SLOTS);

        if (mode.isBlank()) {
            if (hasCargo) {
                mode = "output_delivery";
            } else if (localFoodCount(data, site) < foodTarget(site)) {
                mode = "supply_pickup";
            } else if (needsFarmPlantingSupply(data, site)) {
                mode = "farm_supply_pickup";
            } else if (localOutputCount(data, site) >= 16) {
                mode = "output_pickup";
            } else {
                VillagerSimData.clearOutpostSiteId(villager);
                return true;
            }
            VillagerSimData.setOutpostHaulMode(villager, mode);
        }

        switch (mode) {
            case "supply_pickup" -> {
                VillageStorageService.LocatedContainer core =
                        nearestCoreFoodStorage(level, data, village, site);
                if (core == null) return true;

                BlockPos target = core.record().pos();
                if (villager.distanceToSqr(target.getCenter()) > 4.5D * 4.5D) {
                    moveTowardLoaded(villager, level, target, 0.80D);
                    return true;
                }

                int need = Math.min(16, Math.max(0, foodTarget(site) - localFoodCount(data, site)));
                if (need <= 0) {
                    VillagerSimData.setOutpostHaulMode(villager,
                            localOutputCount(data, site) >= 16 ? "output_pickup" : "");
                    return true;
                }

                if (loadFoodFromContainer(villager, level, core.container(), need)) {
                    VillageStorageService.reconcileVillage(village.id(), level);
                    VillagerSimData.setOutpostHaulMode(villager, "supply_delivery");
                }
                return true;
            }
            case "farm_supply_pickup" -> {
                VillageStorageService.LocatedContainer core =
                        nearestCoreFarmSupplyStorage(level, data, village, site);
                if (core == null) return true;

                BlockPos target = core.record().pos();
                if (villager.distanceToSqr(target.getCenter()) > 4.5D * 4.5D) {
                    moveTowardLoaded(villager, level, target, 0.80D);
                    return true;
                }

                int need = Math.min(8,
                        Math.max(0, FARM_PLANTING_TARGET - localFarmPlantingCount(data, site)));
                if (need <= 0) {
                    VillagerSimData.setOutpostHaulMode(villager, "");
                    return true;
                }

                if (loadFarmSupplyFromContainer(villager, level, core.container(), need)) {
                    VillageStorageService.reconcileVillage(village.id(), level);
                    VillagerSimData.setOutpostHaulMode(villager, "supply_delivery");
                }
                return true;
            }
            case "supply_delivery" -> {
                VillageStorageService.LocatedContainer local = localOutpostStorage(level, data, site);
                if (local == null) return true;

                BlockPos target = local.record().pos();
                if (villager.distanceToSqr(target.getCenter()) > 4.5D * 4.5D) {
                    moveTowardLoaded(villager, level, target, 0.80D);
                    return true;
                }

                depositCargo(villager, level, local.container());
                VillageStorageService.reconcileVillage(village.id(), level);
                site.setLastUsedGameTime(level.getGameTime());
                data.touch();
                VillagerSimData.setOutpostHaulMode(villager,
                        localOutputCount(data, site) >= 16 ? "output_pickup"
                                : needsFarmPlantingSupply(data, site) ? "farm_supply_pickup" : "");
                return true;
            }
            case "output_pickup" -> {
                BlockPos siteCenter = center(site);
                if (villager.blockPosition().distManhattan(siteCenter) > 20) {
                    moveTowardLoaded(villager, level, siteCenter, 0.80D);
                    return true;
                }

                if (loadOutpostCargo(villager, level, data, site)) {
                    site.setLastUsedGameTime(level.getGameTime());
                    data.touch();
                    VillagerSimData.setOutpostHaulMode(villager, "output_delivery");
                } else {
                    VillagerSimData.setOutpostHaulMode(villager, "");
                }
                return true;
            }
            case "output_delivery" -> {
                VillageStorageService.LocatedContainer core =
                        nearestCoreStorage(level, data, village, site);
                if (core == null) return true;

                BlockPos target = core.record().pos();
                if (villager.distanceToSqr(target.getCenter()) > 4.5D * 4.5D) {
                    moveTowardLoaded(villager, level, target, 0.80D);
                    return true;
                }

                depositCargo(villager, level, core.container());
                VillageStorageService.reconcileVillage(village.id(), level);
                VillagerSimData.setOutpostHaulMode(villager,
                        localFoodCount(data, site) < foodTarget(site) ? "supply_pickup"
                                : needsFarmPlantingSupply(data, site) ? "farm_supply_pickup" : "");
                return true;
            }
            default -> {
                VillagerSimData.setOutpostHaulMode(villager, "");
                return true;
            }
        }
    }

    private static boolean loadOutpostCargo(Villager villager, ServerLevel level,
                                            VillageSavedData data,
                                            VillageSavedData.WorkSiteRecord site) {
        int available = localOutputCount(data, site);
        int movable = Math.min(32, Math.max(0, available - localOutputReserve(site)));
        if (movable <= 0) return false;

        int remaining = movable;
        boolean moved = false;
        for (VillageSavedData.StorageRecord storage : data.storagesForVillage(site.villageId())) {
            if (!inside(storage.pos(), site.min(), site.max())) continue;
            if (!VillageSimulationScheduler.isChunkLoaded(level, storage.pos())) continue;
            if (!(level.getBlockEntity(storage.pos()) instanceof Container container)) continue;

            for (int slot = 0; slot < container.getContainerSize() && remaining > 0; slot++) {
                ItemStack stack = container.getItem(slot);
                if (!isOutpostOutput(stack, site.purpose())) continue;

                int take = Math.min(remaining, stack.getCount());
                ItemStack candidate = stack.copyWithCount(take);
                if (!VillagerSimData.canInsertWorkCargo(
                        villager, level.registryAccess(), candidate, PORTER_CARGO_SLOTS)) {
                    continue;
                }

                ItemStack remainder = VillagerSimData.insertWorkCargo(
                        villager, level.registryAccess(), candidate, PORTER_CARGO_SLOTS);
                int inserted = take - remainder.getCount();
                if (inserted <= 0) continue;

                stack.shrink(inserted);
                container.setChanged();
                remaining -= inserted;
                moved = true;
            }
            if (remaining <= 0) break;
        }

        if (moved) VillageStorageService.reconcileVillage(site.villageId(), level);
        return moved;
    }

    private static int foodTarget(VillageSavedData.WorkSiteRecord site) {
        return site.foundingPrepared() ? FOUNDING_FOOD_TARGET : LOCAL_FOOD_TARGET;
    }

    private static int localFoodCount(VillageSavedData data, VillageSavedData.WorkSiteRecord site) {
        int total = 0;
        for (VillageSavedData.StorageRecord storage : data.storagesForVillage(site.villageId())) {
            if (!inside(storage.pos(), site.min(), site.max())) continue;
            total += storage.cachedCounts().getOrDefault(VillageStorageService.itemKey(Items.BREAD), 0);
            total += storage.cachedCounts().getOrDefault(VillageStorageService.itemKey(Items.CARROT), 0);
            total += storage.cachedCounts().getOrDefault(VillageStorageService.itemKey(Items.POTATO), 0);
            total += storage.cachedCounts().getOrDefault(VillageStorageService.itemKey(Items.BEETROOT), 0);
            total += storage.cachedCounts().getOrDefault(VillageStorageService.itemKey(Items.WHEAT), 0);
            total += storage.cachedCounts().getOrDefault(VillageStorageService.itemKey(Items.COD), 0);
            total += storage.cachedCounts().getOrDefault(VillageStorageService.itemKey(Items.SALMON), 0);
        }
        return total;
    }

    private static int localOutputReserve(VillageSavedData.WorkSiteRecord site) {
        return ("farm".equals(site.purpose()) || "fishing".equals(site.purpose()))
                ? Math.max(LOCAL_OUTPUT_BUFFER, foodTarget(site))
                : LOCAL_OUTPUT_BUFFER;
    }

    private static boolean needsFarmPlantingSupply(
            VillageSavedData data, VillageSavedData.WorkSiteRecord site) {
        return "farm".equals(site.purpose()) && localFarmPlantingCount(data, site) < FARM_PLANTING_TARGET;
    }

    private static int localFarmPlantingCount(
            VillageSavedData data, VillageSavedData.WorkSiteRecord site) {
        int total = 0;
        for (VillageSavedData.StorageRecord storage : data.storagesForVillage(site.villageId())) {
            if (!inside(storage.pos(), site.min(), site.max())) continue;
            total += storage.cachedCounts().getOrDefault(
                    VillageStorageService.itemKey(Items.WHEAT_SEEDS), 0);
            total += storage.cachedCounts().getOrDefault(
                    VillageStorageService.itemKey(Items.BEETROOT_SEEDS), 0);
        }
        return total;
    }

    private static boolean isFood(ItemStack stack) {
        return stack.is(Items.BREAD) || stack.is(Items.CARROT)
                || stack.is(Items.POTATO) || stack.is(Items.BEETROOT);
    }

    private static boolean loadFoodFromContainer(Villager villager, ServerLevel level,
                                                 Container container, int requested) {
        int remaining = requested;
        boolean moved = false;
        for (int slot = 0; slot < container.getContainerSize() && remaining > 0; slot++) {
            ItemStack stack = container.getItem(slot);
            if (!isFood(stack)) continue;

            int take = Math.min(remaining, stack.getCount());
            ItemStack candidate = stack.copyWithCount(take);
            if (!VillagerSimData.canInsertWorkCargo(
                    villager, level.registryAccess(), candidate, PORTER_CARGO_SLOTS)) {
                continue;
            }

            ItemStack remainder = VillagerSimData.insertWorkCargo(
                    villager, level.registryAccess(), candidate, PORTER_CARGO_SLOTS);
            int inserted = take - remainder.getCount();
            if (inserted <= 0) continue;

            stack.shrink(inserted);
            container.setChanged();
            remaining -= inserted;
            moved = true;
        }
        return moved;
    }

    private static void depositCargo(Villager villager, ServerLevel level, Container container) {
        List<ItemStack> cargo = VillagerSimData.workCargo(
                villager, level.registryAccess(), PORTER_CARGO_SLOTS);
        for (int slot = 0; slot < cargo.size(); slot++) {
            ItemStack stack = cargo.get(slot);
            if (stack.isEmpty()) continue;
            cargo.set(slot, insertIntoContainer(container, stack));
        }
        VillagerSimData.setWorkCargo(villager, level.registryAccess(), cargo, PORTER_CARGO_SLOTS);
    }

    private static VillageStorageService.LocatedContainer localOutpostStorage(
            ServerLevel level, VillageSavedData data, VillageSavedData.WorkSiteRecord site) {
        for (VillageStorageService.LocatedContainer located :
                VillageStorageService.containers(site.villageId(), level)) {
            if (inside(located.record().pos(), site.min(), site.max())) return located;
        }
        return null;
    }

    private static VillageStorageService.LocatedContainer nearestCoreFoodStorage(
            ServerLevel level,
            VillageSavedData data,
            VillageSavedData.VillageRecord village,
            VillageSavedData.WorkSiteRecord outpost) {
        VillageStorageService.LocatedContainer best = null;
        int bestDistance = Integer.MAX_VALUE;

        for (VillageStorageService.LocatedContainer located :
                VillageStorageService.containers(village.id(), level)) {
            BlockPos pos = located.record().pos();
            if (inside(pos, outpost.min(), outpost.max())) continue;

            boolean hasFood = false;
            Container container = located.container();
            for (int slot = 0; slot < container.getContainerSize(); slot++) {
                if (isFood(container.getItem(slot))) {
                    hasFood = true;
                    break;
                }
            }
            if (!hasFood) continue;

            int distance = pos.distManhattan(village.center());
            if (distance < bestDistance) {
                bestDistance = distance;
                best = located;
            }
        }
        return best;
    }

    private static VillageStorageService.LocatedContainer nearestCoreFarmSupplyStorage(
            ServerLevel level,
            VillageSavedData data,
            VillageSavedData.VillageRecord village,
            VillageSavedData.WorkSiteRecord outpost) {
        VillageStorageService.LocatedContainer best = null;
        int bestDistance = Integer.MAX_VALUE;

        for (VillageStorageService.LocatedContainer located :
                VillageStorageService.containers(village.id(), level)) {
            BlockPos pos = located.record().pos();
            if (inside(pos, outpost.min(), outpost.max())) continue;

            boolean hasSeed = false;
            Container container = located.container();
            for (int slot = 0; slot < container.getContainerSize(); slot++) {
                ItemStack stack = container.getItem(slot);
                if (stack.is(Items.WHEAT_SEEDS) || stack.is(Items.BEETROOT_SEEDS)) {
                    hasSeed = true;
                    break;
                }
            }
            if (!hasSeed) continue;

            int distance = pos.distManhattan(village.center());
            if (distance < bestDistance) {
                bestDistance = distance;
                best = located;
            }
        }
        return best;
    }

    private static boolean loadFarmSupplyFromContainer(
            Villager villager, ServerLevel level, Container container, int requested) {
        int remaining = requested;
        boolean moved = false;
        for (int slot = 0; slot < container.getContainerSize() && remaining > 0; slot++) {
            ItemStack stack = container.getItem(slot);
            if (!(stack.is(Items.WHEAT_SEEDS) || stack.is(Items.BEETROOT_SEEDS))) continue;

            int take = Math.min(remaining, stack.getCount());
            ItemStack candidate = stack.copyWithCount(take);
            if (!VillagerSimData.canInsertWorkCargo(
                    villager, level.registryAccess(), candidate, PORTER_CARGO_SLOTS)) {
                continue;
            }

            ItemStack remainder = VillagerSimData.insertWorkCargo(
                    villager, level.registryAccess(), candidate, PORTER_CARGO_SLOTS);
            int inserted = take - remainder.getCount();
            if (inserted <= 0) continue;

            stack.shrink(inserted);
            container.setChanged();
            remaining -= inserted;
            moved = true;
        }
        return moved;
    }

    private static int localOutputCount(VillageSavedData data, VillageSavedData.WorkSiteRecord site) {
        int total = 0;
        for (VillageSavedData.StorageRecord storage : data.storagesForVillage(site.villageId())) {
            if (!inside(storage.pos(), site.min(), site.max())) continue;
            for (var entry : storage.cachedCounts().entrySet()) {
                if (isOutpostOutputKey(entry.getKey(), site.purpose())) total += entry.getValue();
            }
        }
        return total;
    }

    private static boolean isOutpostOutput(ItemStack stack, String purpose) {
        if (stack.isEmpty()) return false;
        if ("forestry".equals(purpose)) return stack.is(ItemTags.LOGS);
        if ("quarry".equals(purpose)) {
            return stack.is(Items.COBBLESTONE) || stack.is(Items.STONE)
                    || stack.is(Items.ANDESITE) || stack.is(Items.DIORITE)
                    || stack.is(Items.GRANITE);
        }
        if ("fishing".equals(purpose)) {
            return stack.is(Items.COD) || stack.is(Items.SALMON);
        }
        if ("farm".equals(purpose)) {
            return stack.is(Items.WHEAT) || stack.is(Items.CARROT)
                    || stack.is(Items.POTATO) || stack.is(Items.BEETROOT);
        }
        return false;
    }

    private static boolean isOutpostOutputKey(String key, String purpose) {
        if ("forestry".equals(purpose)) {
            return key.endsWith("_log") || key.endsWith("_stem") || key.endsWith(":bamboo_block");
        }
        if ("quarry".equals(purpose)) {
            return key.endsWith(":cobblestone") || key.endsWith(":stone")
                    || key.endsWith(":andesite") || key.endsWith(":diorite")
                    || key.endsWith(":granite");
        }
        if ("fishing".equals(purpose)) {
            return key.endsWith(":cod") || key.endsWith(":salmon");
        }
        if ("farm".equals(purpose)) {
            return key.endsWith(":wheat") || key.endsWith(":carrot")
                    || key.endsWith(":potato") || key.endsWith(":beetroot");
        }
        return false;
    }

    private static VillageStorageService.LocatedContainer nearestCoreStorage(
            ServerLevel level,
            VillageSavedData data,
            VillageSavedData.VillageRecord village,
            VillageSavedData.WorkSiteRecord outpost) {
        VillageStorageService.LocatedContainer best = null;
        int bestDistance = Integer.MAX_VALUE;

        for (VillageStorageService.LocatedContainer located :
                VillageStorageService.containers(village.id(), level)) {
            BlockPos pos = located.record().pos();
            if (inside(pos, outpost.min(), outpost.max())) continue;

            int distance = pos.distManhattan(village.center());
            if (distance < bestDistance) {
                bestDistance = distance;
                best = located;
            }
        }
        return best;
    }

    private static ItemStack insertIntoContainer(Container container, ItemStack incoming) {
        ItemStack work = incoming.copy();

        for (int slot = 0; slot < container.getContainerSize() && !work.isEmpty(); slot++) {
            ItemStack current = container.getItem(slot);
            if (current.isEmpty() || !ItemStack.isSameItemSameComponents(current, work)
                    || current.getCount() >= current.getMaxStackSize()) {
                continue;
            }
            int move = Math.min(work.getCount(), current.getMaxStackSize() - current.getCount());
            current.grow(move);
            work.shrink(move);
            container.setChanged();
        }

        for (int slot = 0; slot < container.getContainerSize() && !work.isEmpty(); slot++) {
            if (!container.getItem(slot).isEmpty()) continue;
            int move = Math.min(work.getCount(), work.getMaxStackSize());
            container.setItem(slot, work.copyWithCount(move));
            work.shrink(move);
            container.setChanged();
        }
        return work;
    }

    private static boolean inside(BlockPos pos, BlockPos min, BlockPos max) {
        return pos.getX() >= min.getX() && pos.getX() <= max.getX()
                && pos.getY() >= min.getY() && pos.getY() <= max.getY()
                && pos.getZ() >= min.getZ() && pos.getZ() <= max.getZ();
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
            case "fishing" -> village.marketPermille("fishing");
            case "farm" -> village.marketPermille("food");
            default -> 1000;
        };
    }

    private static boolean hasActiveRoute(
            VillageSavedData data,
            VillageSavedData.VillageRecord village,
            VillageSavedData.WorkSiteRecord site) {
        return findActiveRoute(data, village, site) != null;
    }

    private static VillageSavedData.RouteRecord findActiveRoute(
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
                    return route;
                }
            }
        }
        return null;
    }

    private static void ensureRoadUpgradeProject(
            VillageSavedData data,
            VillageSavedData.VillageRecord village,
            VillageSavedData.RouteRecord route) {
        if (!AsobibaTweaksConfig.VILLAGE_ROADS_ENABLED.getAsBoolean()) return;

        String desiredQuality = route.quality();
        if (route.trafficScore() >= 18) desiredQuality = "stone";
        else if (route.trafficScore() >= 6 && "dirt".equals(desiredQuality)) desiredQuality = "gravel";

        int desiredWidth = route.width();
        if (route.trafficScore() >= 30) desiredWidth = Math.max(desiredWidth, 3);
        else if (route.trafficScore() >= 10) desiredWidth = Math.max(desiredWidth, 2);

        if (desiredQuality.equals(route.quality()) && desiredWidth <= route.width()) return;

        for (VillageSavedData.ProjectRecord project : data.activeProjectsForVillage(village.id())) {
            if (!"road".equals(project.type())) continue;
            if (route.id().toString().equals(project.parameter("route_id"))) return;
        }

        VillageSavedData.ProjectRecord project =
                data.createProject(village.id(), "road", 15, route.from());
        project.setTemplateId("road_upgrade_v1");
        project.setVariantSeed(route.id().getLeastSignificantBits() ^ route.trafficScore());
        project.setAnchor(route.to());
        project.setParameter("route_id", route.id().toString());
        project.setParameter("road_quality", desiredQuality);
        project.setParameter("road_width", Integer.toString(desiredWidth));
        project.setParameter("bridge_details", "parapet_v1");
        project.setParameter("plank", dominantPlankName(village));
        project.setPhase("planned");
        project.setWorkCursor(0);
    }

    private static String dominantPlankName(VillageSavedData.VillageRecord village) {
        String[] names = {"oak", "spruce", "birch", "jungle", "acacia", "dark_oak", "mangrove", "cherry"};
        String best = "oak";
        int bestWeight = 0;
        for (String name : names) {
            int weight = village.cultureWeight("plank:" + name);
            if (weight > bestWeight) {
                bestWeight = weight;
                best = name;
            }
        }
        return best;
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
            } else if ("fishing".equals(site.purpose())) {
                if (level.getFluidState(surface).is(net.minecraft.tags.FluidTags.WATER)
                        || level.getFluidState(surface.above()).is(net.minecraft.tags.FluidTags.WATER)
                        || level.getFluidState(surface.below()).is(net.minecraft.tags.FluidTags.WATER)) {
                    useful++;
                }
            } else if ("farm".equals(site.purpose())) {
                var state = level.getBlockState(surface);
                if ((state.is(Blocks.GRASS_BLOCK) || state.is(Blocks.DIRT)
                        || state.is(Blocks.COARSE_DIRT) || state.is(Blocks.FARMLAND))
                        && hasIrrigationWater(level, surface)) {
                    useful++;
                }
            }

            if (useful >= 4) return ResourceState.AVAILABLE;
        }
        return ResourceState.DEPLETED;
    }

    private static boolean hasIrrigationWater(ServerLevel level, BlockPos soil) {
        int[][] directions = {
                {1, 0}, {-1, 0}, {0, 1}, {0, -1},
                {1, 1}, {1, -1}, {-1, 1}, {-1, -1}
        };
        for (int distance = 1; distance <= 4; distance++) {
            for (int[] direction : directions) {
                BlockPos probe = soil.offset(direction[0] * distance, 0, direction[1] * distance);
                if (level.getFluidState(probe).is(net.minecraft.tags.FluidTags.WATER)
                        || level.getFluidState(probe.above()).is(net.minecraft.tags.FluidTags.WATER)
                        || level.getFluidState(probe.below()).is(net.minecraft.tags.FluidTags.WATER)) {
                    return true;
                }
            }
        }
        return false;
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
