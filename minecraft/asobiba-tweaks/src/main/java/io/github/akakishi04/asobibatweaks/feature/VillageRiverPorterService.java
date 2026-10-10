package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.tags.ItemTags;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.Container;
import net.minecraft.world.entity.npc.Villager;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.phys.Vec3;

/**
 * V85: real first/last-mile freight between recognized village/Outpost
 * warehouses and the actual waterborne ChestBoat dock Barrels.
 *
 * A RiverHaul lives on the porter entity across save/reload, and physical
 * cargo lives in VillagerSimData's existing 16 slots. Receipt records only
 * describe actual items delivered by a boat: they are NOT an item pool.
 * Unknown/unloaded containers or missing path stop work without losing stock.
 */
public final class VillageRiverPorterService {
    private static final int SLOTS = 16;
    private static final int MAX_TRIP_ITEMS = 32;
    private static final int MAX_ROUTES_EXAMINED = 4;
    private static final double ACCESS_DISTANCE_SQR = 4.5D * 4.5D;
    private static final int DOCK_MAX_DISTANCE = 72;
    private static final int CORE_STORAGE_RADIUS = 72;
    private static final int MAX_WAREHOUSES = 16;

    private VillageRiverPorterService() {}

    /**
     * A remote dock with a real outstanding boat-delivery receipt is genuine
     * Porter demand even when ordinary Outpost production has gone quiet.
     * Unknown chunks do not count as available items.
     */
    public static boolean hasPendingDockDelivery(
            ServerLevel level, VillageSavedData data,
            VillageSavedData.VillageRecord village,
            VillageSavedData.WorkSiteRecord site) {
        if (village == null || site == null
                || !"outpost".equals(site.type()) || !"active".equals(site.state())) return false;
        BlockPos center = new BlockPos((site.min().getX() + site.max().getX()) / 2,
                (site.min().getY() + site.max().getY()) / 2,
                (site.min().getZ() + site.max().getZ()) / 2);
        int examined = 0;
        for (UUID routeId : village.routeIds()) {
            if (++examined > MAX_ROUTES_EXAMINED) break;
            VillageSavedData.RouteRecord route = data.route(routeId).orElse(null);
            if (route == null || !"river".equals(route.type())) continue;
            for (boolean atTo : new boolean[]{false, true}) {
                BlockPos berth = atTo ? route.to() : route.from();
                if (berth.distManhattan(center) > 48
                        || route.dockReceipts(atTo).isEmpty()) continue;
                Container dock = VillageRiverCargoService.dockBarrel(
                        level, data, village.id(), berth);
                if (dock == null) continue;
                for (int slot = 0; slot < dock.getContainerSize(); slot++) {
                    ItemStack stack = dock.getItem(slot);
                    if (!stack.isEmpty()
                            && VillageRiverCargoService.approved(stack)
                            && route.dockReceipts(atTo).getOrDefault(itemId(stack), 0) > 0) {
                        return true;
                    }
                }
            }
        }
        return false;
    }

    /**
     * @param assignedOutpost null for an ordinary core Porter; an explicit
     *                        active Outpost UUID for its assigned local Porter
     * @return whether a durable river transfer claimed this worker tick
     */
    public static boolean handlePorter(Villager porter, ServerLevel level, UUID assignedOutpost) {
        if (!"porter".equals(VillagerSimData.duty(porter))
                || VillagerSimData.villageId(porter).isEmpty()) return false;

        VillagerSimData.RiverHaul active = VillagerSimData.riverHaul(porter).orElse(null);
        if (active != null) return advance(porter, level,
                active.originVillageId() != null ? active.originVillageId()
                    : VillagerSimData.villageId(porter).get(), active);
        VillageSavedData.VillageRecord village = VillageSavedData.get(level)
                .village(VillagerSimData.villageId(porter).get()).orElse(null);
        if (village == null || !"active".equals(village.lifecycle())
                || village.storageIds().size() > 64) return false;

        if (!AsobibaTweaksConfig.VILLAGE_RIVER_CARGO_ENABLED.getAsBoolean()
                || !AsobibaTweaksConfig.VILLAGE_LOGISTICS_ENABLED.getAsBoolean()
                || !AsobibaTweaksConfig.VILLAGE_RIVER_DOCKS_ENABLED.getAsBoolean()
                || VillagerSimData.hasWorkCargo(porter, level.registryAccess(), SLOTS)
                || level.getDayTime() % 24_000L >= 12_000L) return false;

        VillageSavedData data = VillageSavedData.get(level);
        List<VillageStorageService.LocatedContainer> known =
                VillageStorageService.containers(village.id(), level);
        int examined = 0;
        for (UUID id : village.routeIds()) {
            if (++examined > MAX_ROUTES_EXAMINED) break;
            VillageSavedData.RouteRecord route = data.route(id).orElse(null);
            if (route == null || !"river".equals(route.type())
                    || !"active".equals(route.state())
                    || route.waypoints().size() < 2) continue;

            Container from = VillageRiverCargoService.dockBarrel(
                    level, data, village.id(), route.from());
            Container to = VillageRiverCargoService.dockBarrel(
                    level, data, village.id(), route.to());
            if (from == null || to == null) continue; // no phantom dock storage
            BlockPos fromPos = locate(known, from);
            BlockPos toPos = locate(known, to);
            if (fromPos == null || toPos == null) continue;

            // The nearer endpoint belongs to the core; the other must serve
            // an established Outpost. Do not let a core Porter claim remote
            // unrecognized chests or an Outpost Porter claim the home dock.
            boolean fromCore = fromPos.distManhattan(village.center())
                    <= toPos.distManhattan(village.center());
            boolean atTo = assignedOutpost == null ? !fromCore : fromCore;
            BlockPos dockPos = atTo ? toPos : fromPos;
            Container dock = atTo ? to : from;
            Container otherDock = atTo ? from : to;
            BlockPos otherDockPos = atTo ? fromPos : toPos;
            if (porter.blockPosition().distManhattan(dockPos) > DOCK_MAX_DISTANCE) continue;

            VillageSavedData.WorkSiteRecord outpost =
                    nearestOutpost(data, village.id(), fromCore ? toPos : fromPos);
            if (outpost == null) continue;
            if (assignedOutpost != null && !assignedOutpost.equals(outpost.id())) continue;
            if (assignedOutpost == null && dockPos.distManhattan(village.center()) > 96) continue;

            List<VillageStorageService.LocatedContainer> warehouses =
                    warehouses(known, data, village, assignedOutpost, from, to, dockPos);
            if (warehouses.isEmpty()) continue;
            List<VillageStorageService.LocatedContainer> remoteWarehouses =
                    warehouses(known, data, village,
                            assignedOutpost == null ? outpost.id() : null,
                            from, to, otherDockPos);
            if (remoteWarehouses.isEmpty()) continue;

            VillagerSimData.RiverHaul next = planInbound(route, atTo, dockPos,
                    dock, warehouses, village.id());
            if (next == null && assignedOutpost == null && route.carrierEntityId() == null
                    && count(dock, Items.OAK_CHEST_BOAT) == 0) {
                next = planBoatSupply(route, atTo, dockPos, warehouses, dock);
            }
            if (next == null) next = planOutbound(route, atTo, dockPos,
                    dock, warehouses, remoteWarehouses, assignedOutpost == null,
                    outpost.purpose(), village, VillageResourceReservations.capture(data, village));
            if (next == null) continue;

            VillagerSimData.setRiverHaul(porter, next);
            return advance(porter, level, village.id(), next);
        }
        return false;
    }

    private static VillagerSimData.RiverHaul planInbound(
            VillageSavedData.RouteRecord route, boolean atTo, BlockPos dockPos,
            Container dock, List<VillageStorageService.LocatedContainer> warehouses,
            UUID villageId) {
        for (Map.Entry<String, Integer> receipt : route.dockReceipts(atTo).entrySet()) {
            if (receipt.getValue() <= 0) continue;
            for (int slot = 0; slot < dock.getContainerSize(); slot++) {
                ItemStack stack = dock.getItem(slot);
                if (stack.isEmpty() || !VillageRiverCargoService.approved(stack)
                        || !itemId(stack).equals(receipt.getKey())) continue;
                int amount = Math.min(MAX_TRIP_ITEMS,
                        Math.min(receipt.getValue(), stack.getCount()));
                for (VillageStorageService.LocatedContainer warehouse : warehouses) {
                    if (canAccept(warehouse.container(), stack) >= amount) {
                        return new VillagerSimData.RiverHaul(route.id(), dockPos,
                                warehouse.record().pos(), receipt.getKey(), amount,
                                true, atTo, "pickup");
                    }
                }
            }
        }
        return null;
    }

    private static VillagerSimData.RiverHaul planBoatSupply(
            VillageSavedData.RouteRecord route, boolean atTo, BlockPos dockPos,
            List<VillageStorageService.LocatedContainer> warehouses, Container dock) {
        if (canAccept(dock, new ItemStack(Items.OAK_CHEST_BOAT)) < 1) return null;
        for (VillageStorageService.LocatedContainer warehouse : warehouses) {
            if (count(warehouse.container(), Items.OAK_CHEST_BOAT) > 0) {
                return new VillagerSimData.RiverHaul(route.id(),
                        warehouse.record().pos(), dockPos,
                        VillageStorageService.itemKey(Items.OAK_CHEST_BOAT),
                        1, false, atTo, "pickup");
            }
        }
        return null;
    }

    private static VillagerSimData.RiverHaul planOutbound(
            VillageSavedData.RouteRecord route, boolean atTo, BlockPos dockPos,
            Container dock, List<VillageStorageService.LocatedContainer> warehouses,
            List<VillageStorageService.LocatedContainer> remote,
            boolean fromCore, String outpostPurpose,
            VillageSavedData.VillageRecord village, VillageResourceReservations.Snapshot reservations) {
        for (VillageStorageService.LocatedContainer warehouse : warehouses) {
            Container source = warehouse.container();
            for (int slot = 0; slot < source.getContainerSize(); slot++) {
                ItemStack stack = source.getItem(slot);
                if (!VillageRiverCargoService.approved(stack)
                        || (!fromCore && !isOutpostOutput(stack, outpostPurpose))) continue;
                int dispatchable = dispatchable(reservations, warehouses, remote, stack, fromCore);
                if (dispatchable <= 0) continue;
                int reservedForLocalPorter = route.dockReceipts(atTo)
                        .getOrDefault(itemId(stack), 0);
                int dockFreeStock = countMatching(dock, stack) - reservedForLocalPorter;
                if (dockFreeStock >= 32) continue;

                int amount = Math.min(MAX_TRIP_ITEMS,
                        Math.min(stack.getCount(), dispatchable));
                amount = Math.min(amount, Math.max(0, 48 - dockFreeStock));
                if (amount <= 0 || canAccept(dock, stack) < amount) continue;

                return new VillagerSimData.RiverHaul(route.id(),
                        warehouse.record().pos(), dockPos, itemId(stack),
                        amount, false, atTo, "pickup");
            }
        }
        return null;
    }

    private static boolean advance(Villager porter, ServerLevel level,
                                   UUID villageId, VillagerSimData.RiverHaul haul) {
        VillageSavedData data = VillageSavedData.get(level);
        VillageSavedData.RouteRecord route = data.route(haul.routeId()).orElse(null);
        if ("recovery".equals(haul.phase())) return recover(porter, level, villageId, haul, route);
        if (route == null || !villageId.equals(route.villageId())
                || !"river".equals(route.type()) || !"active".equals(route.state())) {
            if ("pickup".equals(haul.phase())) VillagerSimData.clearRiverHaul(porter);
            else if (haul.originVillageId() != null) {
                VillagerSimData.setRiverHaulPhase(porter, "recovery");
                return recover(porter, level, villageId, haul, route);
            }
            // Old tickets lacking provenance remain physical and wait safely.
            return true;
        }
        if (haul.originVillageId() == null) {
            // Upgrade legacy tickets only from a matching live route, never by
            // guessing an absent route's origin after worker migration.
            VillagerSimData.setRiverHaul(porter, new VillagerSimData.RiverHaul(
                    haul.routeId(), haul.source(), haul.destination(), haul.itemId(),
                    haul.requested(), haul.incoming(), haul.receiptAtTo(), haul.phase(), villageId));
        }
        if ("pickup".equals(haul.phase())) {
            if (VillagerSimData.hasWorkCargo(porter, level.registryAccess(), SLOTS)) {
                // Another transfer has filled this Porter meanwhile: never
                // mix that cargo with a new preplanned river shipment.
                return true;
            }
            Container source = recognized(level, data, villageId, haul.source());
            Container destination = recognized(level, data, villageId, haul.destination());
            if (source == null || destination == null) {
                if (VillageSimulationScheduler.isChunkLoaded(level, haul.source())
                        && VillageSimulationScheduler.isChunkLoaded(level, haul.destination()))
                    VillagerSimData.clearRiverHaul(porter);
                return true;
            }
            if (porter.distanceToSqr(haul.source().getCenter()) > ACCESS_DISTANCE_SQR) {
                moveTowardLoaded(porter, level, haul.source());
                return true;
            }

            int allowed = haul.requested();
            // A ticket is only intent until physical pickup. Recheck current
            // reservations, all required warehouses and category demand after
            // travel, including tickets restored from older saves.
            if (!haul.incoming() && !haul.itemId().equals("minecraft:oak_chest_boat")) {
                allowed = Math.min(allowed, outboundAllowance(level, data, villageId, route, haul));
                if (allowed <= 0) {
                    VillagerSimData.clearRiverHaul(porter);
                    return true;
                }
            }
            if (haul.incoming()) {
                allowed = Math.min(allowed, route.dockReceipts(haul.receiptAtTo())
                        .getOrDefault(haul.itemId(), 0));
            }
            if (allowed <= 0) {
                VillagerSimData.clearRiverHaul(porter);
                return true;
            }
            for (int slot = 0; slot < source.getContainerSize(); slot++) {
                ItemStack stack = source.getItem(slot);
                if (stack.isEmpty() || !itemId(stack).equals(haul.itemId())
                        || (!stack.is(Items.OAK_CHEST_BOAT)
                            && !VillageRiverCargoService.approved(stack))) continue;
                int amount = Math.min(allowed, stack.getCount());
                ItemStack cargo = stack.copyWithCount(amount);
                if (!VillagerSimData.canInsertWorkCargo(
                        porter, level.registryAccess(), cargo, SLOTS)) continue;
                ItemStack remainder = VillagerSimData.insertWorkCargo(
                        porter, level.registryAccess(), cargo, SLOTS);
                int inserted = amount - remainder.getCount();
                if (inserted <= 0) continue;
                stack.shrink(inserted);
                source.setChanged();
                if (haul.incoming()) {
                    route.acknowledgeDockDelivery(haul.receiptAtTo(),
                            haul.itemId(), inserted);
                    data.touch();
                }
                VillageStorageService.reconcileVillage(villageId, level);
                VillagerSimData.setRiverHaulPhase(porter, "delivery");
                return true;
            }
            return true;
        }

        Container target = recognized(level, data, villageId, haul.destination());
        if (target == null) {
            if (VillageSimulationScheduler.isChunkLoaded(level, haul.destination())) {
                VillagerSimData.setRiverHaulPhase(porter, "recovery");
                return recover(porter, level, villageId, haul, route);
            }
            return true; // unknown is not destruction
        }
        if (porter.distanceToSqr(haul.destination().getCenter()) > ACCESS_DISTANCE_SQR) {
            moveTowardLoaded(porter, level, haul.destination());
            return true;
        }
        List<ItemStack> cargo = VillagerSimData.workCargo(
                porter, level.registryAccess(), SLOTS);
        boolean moved = false;
        for (int i = 0; i < cargo.size(); i++) {
            ItemStack stack = cargo.get(i);
            if (stack.isEmpty() || !haul.itemId().equals(itemId(stack))) continue;
            ItemStack left = insert(target, stack);
            if (left.getCount() < stack.getCount()) moved = true;
            cargo.set(i, left);
        }
        VillagerSimData.setWorkCargo(porter, level.registryAccess(), cargo, SLOTS);
        if (moved) VillageStorageService.reconcileVillage(villageId, level);
        if (cargo.stream().noneMatch(s -> !s.isEmpty()
                && haul.itemId().equals(itemId(s)))) {
            VillagerSimData.clearRiverHaul(porter);
        }
        return true;
    }

    /** Physically return paid freight after route/destination loss; never refund abstract stock. */
    private static boolean recover(Villager porter, ServerLevel level, UUID villageId,
                                   VillagerSimData.RiverHaul haul, VillageSavedData.RouteRecord route) {
        List<ItemStack> cargo = VillagerSimData.workCargo(porter, level.registryAccess(), SLOTS);
        ItemStack sample = cargo.stream().filter(s -> !s.isEmpty() && haul.itemId().equals(itemId(s)))
                .findFirst().orElse(ItemStack.EMPTY);
        if (sample.isEmpty()) { VillagerSimData.clearRiverHaul(porter); return true; }
        VillageSavedData data = VillageSavedData.get(level);
        BlockPos destination = haul.source();
        // Unloaded original storage stays unknown. Do not select a different
        // owner or warehouse based on an absent entity/chunk observation.
        if (!VillageSimulationScheduler.isChunkLoaded(level, destination)) return true;
        Container target = recognized(level, data, villageId, destination);
        if (target == null || canAccept(target, sample) == 0) {
            var origin = data.village(villageId).orElse(null);
            if (origin == null || origin.storageIds().size() > 64) return true;
            for (var candidate : data.storagesForVillage(villageId).stream()
                    .filter(r -> r.pos().distManhattan(haul.source()) <= 24)
                    .sorted(Comparator.comparingInt((VillageSavedData.StorageRecord r) ->
                        r.pos().distManhattan(haul.source())).thenComparing(r -> r.id().toString()))
                    .limit(MAX_WAREHOUSES).toList()) {
                if (!"valid".equals(candidate.validationState())
                        || !VillageSimulationScheduler.isAreaLoaded(level, porter.blockPosition(), candidate.pos())) continue;
                Container alternative = recognized(level, data, villageId, candidate.pos());
                if (alternative != null && canAccept(alternative, sample) > 0) {
                    destination = candidate.pos(); target = alternative; break;
                }
            }
        }
        if (target == null || !VillageSimulationScheduler.isAreaLoaded(
                level, porter.blockPosition(), destination)) return true;
        if (porter.distanceToSqr(destination.getCenter()) > ACCESS_DISTANCE_SQR) {
            moveTowardLoaded(porter, level, destination); return true;
        }
        int returned = 0;
        for (int i = 0; i < cargo.size(); i++) {
            ItemStack stack = cargo.get(i);
            if (stack.isEmpty() || !haul.itemId().equals(itemId(stack))) continue;
            ItemStack leftover = insert(target, stack);
            returned += stack.getCount() - leftover.getCount();
            cargo.set(i, leftover);
        }
        if (returned > 0) {
            VillagerSimData.setWorkCargo(porter, level.registryAccess(), cargo, SLOTS);
            // Incoming receipt was consumed at pickup. Restore only for actual
            // goods physically returned to that same dock, never alternatives.
            if (haul.incoming() && destination.equals(haul.source()) && route != null
                    && "river".equals(route.type()) && route.villageId().equals(villageId)) {
                route.recordDockDelivery(haul.receiptAtTo(), haul.itemId(), returned);
                data.touch();
            }
            VillageStorageService.reconcileVillage(villageId, level);
        }
        if (cargo.stream().noneMatch(s -> !s.isEmpty() && haul.itemId().equals(itemId(s))))
            VillagerSimData.clearRiverHaul(porter);
        return true;
    }

    private static boolean moveTowardLoaded(Villager villager, ServerLevel level, BlockPos target) {
        if (!VillageSimulationScheduler.isChunkLoaded(level, target)) return false;
        Vec3 point = target.getCenter();
        villager.getNavigation().moveTo(point.x, point.y, point.z, 0.8D);
        return true;
    }

    private static List<VillageStorageService.LocatedContainer> warehouses(
            List<VillageStorageService.LocatedContainer> known,
            VillageSavedData data, VillageSavedData.VillageRecord village,
            UUID assignedOutpost, Container dockA, Container dockB, BlockPos dockPos) {
        VillageSavedData.WorkSiteRecord outpost = assignedOutpost == null ? null
                : data.workSite(assignedOutpost).orElse(null);
        List<VillageStorageService.LocatedContainer> result = new ArrayList<>();
        // Iterate registrations rather than the loaded-only container list:
        // an unknown warehouse must not appear empty and create false demand.
        for (VillageSavedData.StorageRecord record : data.storagesForVillage(village.id())) {
            BlockPos pos = record.pos();
            if (assignedOutpost == null) {
                if (pos.distManhattan(village.center()) > CORE_STORAGE_RADIUS) continue;
                boolean insideOutpost = data.workSitesForVillage(village.id()).stream()
                        .anyMatch(site -> "outpost".equals(site.type())
                                && inside(pos, site.min(), site.max()));
                if (insideOutpost) continue;
            } else {
                if (outpost == null || !"outpost".equals(outpost.type())
                        || !"active".equals(outpost.state())
                        || !inside(pos, outpost.min(), outpost.max())) continue;
            }
            VillageStorageService.LocatedContainer located = null;
            for (VillageStorageService.LocatedContainer candidate : known) {
                if (candidate.record().id().equals(record.id())) {
                    located = candidate;
                    break;
                }
            }
            if (located != null && (located.container() == dockA || located.container() == dockB)) continue;
            if (!"valid".equals(record.validationState()) || located == null
                    || result.size() >= MAX_WAREHOUSES) return List.of();
            if (located.container().getContainerSize() > 128) return List.of();
            result.add(located);
        }
        result.sort(Comparator.comparingInt(
                located -> located.record().pos().distManhattan(dockPos)));
        return result;
    }

    private static int outboundAllowance(ServerLevel level, VillageSavedData data,
            UUID villageId, VillageSavedData.RouteRecord route, VillagerSimData.RiverHaul haul) {
        VillageSavedData.VillageRecord village = data.village(villageId).orElse(null);
        if (village == null || !"active".equals(route.state())
                || village.storageIds().size() > 64) return 0;
        List<VillageStorageService.LocatedContainer> known = VillageStorageService.containers(villageId, level);
        Container from = VillageRiverCargoService.dockBarrel(level, data, villageId, route.from());
        Container to = VillageRiverCargoService.dockBarrel(level, data, villageId, route.to());
        if (from == null || to == null) return 0;
        BlockPos fromPos = locate(known, from);
        BlockPos toPos = locate(known, to);
        if (fromPos == null || toPos == null) return 0;
        boolean fromCore = fromPos.distManhattan(village.center()) <= toPos.distManhattan(village.center());
        VillageSavedData.WorkSiteRecord outpost = nearestOutpost(data, villageId, fromCore ? toPos : fromPos);
        if (outpost == null) return 0;
        boolean sourceCore = !inside(haul.source(), outpost.min(), outpost.max());
        BlockPos expectedDock = sourceCore == fromCore ? fromPos : toPos;
        if (!haul.destination().equals(expectedDock)) return 0;
        List<VillageStorageService.LocatedContainer> sources = warehouses(known, data, village,
                sourceCore ? null : outpost.id(), from, to, expectedDock);
        List<VillageStorageService.LocatedContainer> targets = warehouses(known, data, village,
                sourceCore ? outpost.id() : null, from, to, sourceCore == fromCore ? toPos : fromPos);
        if (sources.isEmpty() || targets.isEmpty()) return 0;
        for (VillageStorageService.LocatedContainer source : sources) {
            if (!source.record().pos().equals(haul.source())) continue;
            for (int slot = 0; slot < source.container().getContainerSize(); slot++) {
                ItemStack stack = source.container().getItem(slot);
                if (stack.isEmpty() || !itemId(stack).equals(haul.itemId())
                        || (!sourceCore && !isOutpostOutput(stack, outpost.purpose()))) continue;
                return dispatchable(VillageResourceReservations.capture(data, village), sources, targets, stack, sourceCore);
            }
        }
        return 0;
    }

    /** Real category stock, with operational and construction reserves retained. */
    private static int dispatchable(VillageResourceReservations.Snapshot reservations,
            List<VillageStorageService.LocatedContainer> sources,
            List<VillageStorageService.LocatedContainer> targets, ItemStack stack, boolean fromCore) {
        String category = freightCategory(stack);
        long sourceStock = categoryTotal(sources, category);
        long destinationStock = categoryTotal(targets, category);
        if (!reservations.complete()) return 0;
        long categoryReserved = reservations.categoryCount(category);
        long itemReserved = reservations.itemCount(stack);
        long freeCategory = sourceStock - categoryReserved;
        if (freeCategory < (fromCore ? 64 : 48)
                || destinationStock >= (fromCore ? 24 : 32)) return 0;
        // Category headroom does not authorize taking an exact reserved item
        // just because a different item in that category is abundant.
        long freeItem = (long) total(sources, stack) - itemReserved;
        return (int)Math.max(0L, Math.min(MAX_TRIP_ITEMS,
                Math.min(freeItem, freeCategory - (fromCore ? 32 : 16))));
    }

    private static long categoryTotal(List<VillageStorageService.LocatedContainer> stores, String category) {
        long total = 0L;
        for (VillageStorageService.LocatedContainer store : stores) {
            for (int slot = 0; slot < store.container().getContainerSize(); slot++) {
                ItemStack stack = store.container().getItem(slot);
                if (!stack.isEmpty() && category.equals(freightCategory(stack))) total += stack.getCount();
            }
        }
        return total;
    }

    private static String freightCategory(ItemStack stack) {
        return VillageResourceReservations.category(stack);
    }

    private static VillageSavedData.WorkSiteRecord nearestOutpost(
            VillageSavedData data, UUID villageId, BlockPos remoteDock) {
        VillageSavedData.WorkSiteRecord best = null;
        int nearest = 41;
        for (VillageSavedData.WorkSiteRecord site : data.workSitesForVillage(villageId)) {
            if (!"outpost".equals(site.type()) || !"active".equals(site.state())) continue;
            BlockPos center = new BlockPos((site.min().getX() + site.max().getX()) / 2,
                    (site.min().getY() + site.max().getY()) / 2,
                    (site.min().getZ() + site.max().getZ()) / 2);
            int distance = remoteDock.distManhattan(center);
            if (distance < nearest) {
                best = site;
                nearest = distance;
            }
        }
        return best;
    }

    private static BlockPos locate(
            List<VillageStorageService.LocatedContainer> known, Container container) {
        for (VillageStorageService.LocatedContainer entry : known) {
            if (entry.container() == container) return entry.record().pos();
        }
        return null;
    }

    private static Container recognized(ServerLevel level, VillageSavedData data,
                                        UUID villageId, BlockPos pos) {
        if (!VillageSimulationScheduler.isChunkLoaded(level, pos)
                || data.storageAt(villageId, pos).isEmpty()) return null;
        return level.getBlockEntity(pos) instanceof Container c ? c : null;
    }

    private static boolean inside(BlockPos pos, BlockPos min, BlockPos max) {
        return pos.getX() >= min.getX() && pos.getX() <= max.getX()
                && pos.getY() >= min.getY() && pos.getY() <= max.getY()
                && pos.getZ() >= min.getZ() && pos.getZ() <= max.getZ();
    }

    private static int total(
            List<VillageStorageService.LocatedContainer> stores, ItemStack sample) {
        int count = 0;
        for (VillageStorageService.LocatedContainer store : stores) {
            count += countMatching(store.container(), sample);
        }
        return count;
    }

    private static int countMatching(Container c, ItemStack sample) {
        int count = 0;
        for (int i = 0; i < c.getContainerSize(); i++) {
            ItemStack stack = c.getItem(i);
            if (ItemStack.isSameItemSameComponents(stack, sample)) count += stack.getCount();
        }
        return count;
    }

    private static int count(Container c, Item item) {
        int count = 0;
        for (int i = 0; i < c.getContainerSize(); i++) {
            if (c.getItem(i).is(item)) count += c.getItem(i).getCount();
        }
        return count;
    }

    private static int canAccept(Container c, ItemStack sample) {
        int capacity = 0;
        for (int i = 0; i < c.getContainerSize(); i++) {
            if (!c.canPlaceItem(i, sample)) continue;
            ItemStack stack = c.getItem(i);
            if (stack.isEmpty()) capacity += Math.min(sample.getMaxStackSize(), c.getMaxStackSize());
            else if (ItemStack.isSameItemSameComponents(stack, sample)) {
                capacity += Math.max(0, Math.min(stack.getMaxStackSize(), c.getMaxStackSize()) - stack.getCount());
            }
        }
        return capacity;
    }

    private static ItemStack insert(Container c, ItemStack incoming) {
        ItemStack work = incoming.copy();
        for (int i = 0; i < c.getContainerSize() && !work.isEmpty(); i++) {
            ItemStack stored = c.getItem(i);
            if (stored.isEmpty() || !c.canPlaceItem(i, work)
                    || !ItemStack.isSameItemSameComponents(stored, work)) continue;
            int n = Math.min(work.getCount(),
                    Math.max(0, Math.min(stored.getMaxStackSize(), c.getMaxStackSize()) - stored.getCount()));
            if (n <= 0) continue;
            stored.grow(n);
            work.shrink(n);
            c.setChanged();
        }
        for (int i = 0; i < c.getContainerSize() && !work.isEmpty(); i++) {
            if (!c.getItem(i).isEmpty() || !c.canPlaceItem(i, work)) continue;
            int n = Math.min(work.getCount(), Math.min(work.getMaxStackSize(), c.getMaxStackSize()));
            c.setItem(i, work.copyWithCount(n));
            work.shrink(n);
            c.setChanged();
        }
        return work;
    }

    private static boolean isOutpostOutput(ItemStack item, String purpose) {
        return switch (purpose) {
            case "forestry" -> item.is(net.minecraft.tags.ItemTags.LOGS);
            case "quarry" -> item.is(Items.COBBLESTONE) || item.is(Items.STONE)
                    || item.is(Items.ANDESITE) || item.is(Items.DIORITE)
                    || item.is(Items.GRANITE);
            case "fishing" -> item.is(Items.COD) || item.is(Items.SALMON);
            case "farm" -> item.is(Items.CARROT) || item.is(Items.POTATO)
                    || item.is(Items.BEETROOT) || item.is(Items.WHEAT);
            default -> false;
        };
    }

    private static String itemId(ItemStack stack) {
        return BuiltInRegistries.ITEM.getKey(stack.getItem()).toString();
    }
}
