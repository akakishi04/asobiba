package io.github.akakishi04.asobibatweaks.feature;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.UUID;
import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.Tag;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.Container;
import net.minecraft.world.entity.npc.Villager;
import net.minecraft.world.item.ItemStack;

/**
 * V91: bounded village-to-village freight pilot.
 *
 * A real Porter withdraws actual goods from a recognized origin Barrel,
 * walks to an independently recognized destination-village Barrel and deposits
 * only the physically carried stack. An accepted, fully loaded road-planner
 * route is required before a new trade starts. No abstract imports, teleport,
 * offline production, extra chunk tickets or invented currency.
 *
 * The transfer ticket lives in the Villager's persistent entity data; real
 * ItemStacks live only in the established persistent work cargo. Unloaded,
 * removed or full destinations retain their physical cargo with the Porter.
 */
public final class VillageInterSettlementFreightService {
    private static final String TICKET = "asobibatweaks_inter_village_freight";
    private static final int SLOTS = 16;
    private static final int MAX_SHIPMENT = 16;
    private static final int MAX_VILLAGES = 8;
    private static final int MAX_STORES = 16;
    private static final int MAX_ROUTES = 32;
    private static final int MAX_VILLAGE_DISTANCE = 56;

    private VillageInterSettlementFreightService() {}

    public static boolean handlePorter(Villager porter, ServerLevel level) {
        CompoundTag persistent = porter.getPersistentData();
        if (persistent.contains(TICKET, Tag.TAG_COMPOUND)) {
            return advance(porter, level, persistent.getCompound(TICKET));
        }
        if (VillagerSimData.hasWorkCargo(porter, level.registryAccess(), SLOTS)
                || VillagerSimData.villageId(porter).isEmpty()
                || level.getDayTime() % 24_000L >= 12_000L
                || level.getGameTime() % 400 != Math.floorMod(porter.getId(), 400)) {
            return false;
        }
        return plan(porter, level);
    }

    private static boolean plan(Villager porter, ServerLevel level) {
        VillageSavedData data = VillageSavedData.get(level);
        UUID originId = VillagerSimData.villageId(porter).orElse(null);
        VillageSavedData.VillageRecord origin = data.village(originId).orElse(null);
        if (origin == null || !"active".equals(origin.lifecycle())) return false;

        List<VillageStorageService.LocatedContainer> sources = stores(level, data, origin);
        if (sources.isEmpty()) return false;
        List<VillageSavedData.VillageRecord> neighbors = data.villagesView().values().stream()
                .filter(v -> !v.id().equals(originId) && "active".equals(v.lifecycle())
                        && v.center().distManhattan(origin.center()) <= MAX_VILLAGE_DISTANCE)
                .sorted(Comparator.comparing(v -> v.id().toString()))
                .limit(MAX_VILLAGES).toList();
        for (VillageSavedData.VillageRecord neighbor : neighbors) {
            List<VillageStorageService.LocatedContainer> targets = stores(level, data, neighbor);
            if (targets.isEmpty()) continue;
            for (VillageStorageService.LocatedContainer source : sources) {
                BlockPos from = source.record().pos();
                if (porter.distanceToSqr(from.getCenter()) > 24.0D * 24.0D) continue;
                for (int slot = 0; slot < source.container().getContainerSize(); slot++) {
                    ItemStack offered = source.container().getItem(slot);
                    if (offered.isEmpty() || !VillageRiverCargoService.approved(offered)
                            || stock(sources, offered) < 48) continue;
                    for (VillageStorageService.LocatedContainer target : targets) {
                        BlockPos to = target.record().pos();
                        if (from.distManhattan(to) > MAX_VILLAGE_DISTANCE
                                || stock(targets, offered) >= 16
                                || !canReceive(target.container(), offered, MAX_SHIPMENT)) continue;
                        // Never infer a direct road across unknown terrain. This
                        // planner returns empty for unloaded or failed corridors.
                        List<BlockPos> checked = VillageRoadPlanner.planLoaded(level, from, to);
                        if (checked.size() < 2 || !from.equals(checked.getFirst())
                                || !to.equals(checked.getLast())) continue;
                        VillageSavedData.RouteRecord route = findOrCreateRoute(
                                data, origin, from, to, checked);
                        if (route == null) continue;
                        if (assign(porter, level, route.id(), origin.id(), neighbor.id(),
                                from, to, offered, MAX_SHIPMENT)) return true;
                    }
                }
            }
        }
        return false;
    }

    private static List<VillageStorageService.LocatedContainer> stores(
            ServerLevel level, VillageSavedData data, VillageSavedData.VillageRecord village) {
        List<VillageStorageService.LocatedContainer> result = new ArrayList<>();
        for (VillageStorageService.LocatedContainer found :
                VillageStorageService.containers(village.id(), level)) {
            if (result.size() >= MAX_STORES) break;
            if (!"valid".equals(found.record().validationState())
                    || found.record().pos().distManhattan(village.center()) > 24) continue;
            result.add(found);
        }
        result.sort(Comparator.comparing(x -> x.record().id().toString()));
        return result;
    }

    private static VillageSavedData.RouteRecord findOrCreateRoute(
            VillageSavedData data, VillageSavedData.VillageRecord origin,
            BlockPos from, BlockPos to, List<BlockPos> checked) {
        int seen = 0;
        for (UUID id : origin.routeIds()) {
            if (++seen > MAX_ROUTES) return null;
            VillageSavedData.RouteRecord route = data.route(id).orElse(null);
            if (route != null && "inter_village_trade".equals(route.type())
                    && route.from().equals(from) && route.to().equals(to)) {
                // Never mutate an existing route while its task is in motion.
                if (!"active".equals(route.state())) {
                    route.setState("active");
                    data.touch();
                }
                return route;
            }
        }
        VillageSavedData.RouteRecord route = data.createRoute(
                origin.id(), "inter_village_trade", from, to);
        data.setRouteWaypoints(route.id(), checked);
        route.setState("active");
        data.touch();
        return route;
    }

    /** Package-visible so GameTests can exercise the real transaction on a real route. */
    static boolean assign(Villager porter, ServerLevel level, UUID routeId,
                          UUID fromVillage, UUID toVillage, BlockPos from,
                          BlockPos to, ItemStack sample, int quantity) {
        if (quantity <= 0 || quantity > MAX_SHIPMENT
                || sample.isEmpty() || !VillageRiverCargoService.approved(sample)
                || porter.getPersistentData().contains(TICKET, Tag.TAG_COMPOUND)
                || VillagerSimData.hasWorkCargo(porter, level.registryAccess(), SLOTS)
                || !VillagerSimData.villageId(porter).filter(fromVillage::equals).isPresent()
                || !VillageSimulationScheduler.isAreaLoaded(level, from, to)) return false;
        VillageSavedData data = VillageSavedData.get(level);
        VillageSavedData.RouteRecord route = data.route(routeId).orElse(null);
        if (route == null || !"inter_village_trade".equals(route.type())
                || !"active".equals(route.state())
                || !route.villageId().equals(fromVillage)
                || !route.from().equals(from) || !route.to().equals(to)
                || route.waypoints().size() < 2
                || data.village(toVillage).filter(v -> "active".equals(v.lifecycle())).isEmpty()) return false;
        Container source = recognized(level, data, fromVillage, from);
        Container target = recognized(level, data, toVillage, to);
        if (source == null || target == null
                || !canReceive(target, sample, quantity)) return false;
        int present = 0;
        for (int slot = 0; slot < source.getContainerSize(); slot++) {
            ItemStack stack = source.getItem(slot);
            if (ItemStack.isSameItemSameComponents(stack, sample)) present += stack.getCount();
        }
        if (present < quantity + 32) return false;

        CompoundTag ticket = new CompoundTag();
        ticket.putUUID("route", routeId);
        ticket.putUUID("origin", fromVillage);
        ticket.putUUID("destination_village", toVillage);
        ticket.putLong("source", from.asLong());
        ticket.putLong("target", to.asLong());
        ticket.putString("item", itemId(sample));
        ticket.putInt("remaining", quantity);
        ticket.putString("phase", "pickup");
        porter.getPersistentData().put(TICKET, ticket);
        return true;
    }

    private static boolean advance(Villager porter, ServerLevel level, CompoundTag ticket) {
        if (!ticket.hasUUID("route") || !ticket.hasUUID("origin")
                || !ticket.hasUUID("destination_village")
                || !ticket.contains("source", Tag.TAG_LONG)
                || !ticket.contains("target", Tag.TAG_LONG)) return true;
        UUID originId = ticket.getUUID("origin");
        UUID destinationId = ticket.getUUID("destination_village");
        BlockPos from = BlockPos.of(ticket.getLong("source"));
        BlockPos to = BlockPos.of(ticket.getLong("target"));
        int remaining = ticket.getInt("remaining");
        if (!VillageSimulationScheduler.isAreaLoaded(level, from, to)) return true;
        VillageSavedData data = VillageSavedData.get(level);
        VillageSavedData.RouteRecord route = data.route(ticket.getUUID("route")).orElse(null);
        if (route == null || !"inter_village_trade".equals(route.type())
                || !route.villageId().equals(originId)
                || !route.from().equals(from) || !route.to().equals(to)) return true;
        boolean delivery = "delivery".equals(ticket.getString("phase"));
        BlockPos where = delivery ? to : from;
        Container container = recognized(level, data, delivery ? destinationId : originId, where);
        if (container == null) return true;
        if (porter.distanceToSqr(where.getCenter()) > 4.5D * 4.5D) {
            porter.getNavigation().moveTo(where.getX() + 0.5D, where.getY() + 1.0D,
                    where.getZ() + 0.5D, 0.75D);
            return true;
        }
        if (remaining <= 0) {
            porter.getPersistentData().remove(TICKET);
            return true;
        }
        if (!delivery) {
            if (VillagerSimData.hasWorkCargo(porter, level.registryAccess(), SLOTS)) return true;
            for (int i = 0; i < container.getContainerSize(); i++) {
                ItemStack stack = container.getItem(i);
                if (stack.isEmpty() || !VillageRiverCargoService.approved(stack)
                        || !ticket.getString("item").equals(itemId(stack))
                        || stack.getCount() < remaining + 32) continue;
                ItemStack parcel = stack.copyWithCount(remaining);
                if (!VillagerSimData.canInsertWorkCargo(
                        porter, level.registryAccess(), parcel, SLOTS)) return true;
                ItemStack leftover = VillagerSimData.insertWorkCargo(
                        porter, level.registryAccess(), parcel, SLOTS);
                int taken = remaining - leftover.getCount();
                if (taken <= 0) return true;
                stack.shrink(taken);
                container.setChanged();
                ticket.putInt("remaining", taken);
                ticket.putString("phase", "delivery");
                VillageStorageService.reconcileVillage(originId, level);
                return true;
            }
            // No resource at pickup: the parcel was never paid. Safe to cancel.
            porter.getPersistentData().remove(TICKET);
            return true;
        }

        List<ItemStack> cargo = VillagerSimData.workCargo(
                porter, level.registryAccess(), SLOTS);
        int delivered = 0;
        for (int i = 0; i < cargo.size() && delivered < remaining; i++) {
            ItemStack carried = cargo.get(i);
            if (carried.isEmpty() || !ticket.getString("item").equals(itemId(carried))) continue;
            int take = Math.min(carried.getCount(), remaining - delivered);
            ItemStack left = insert(container, carried.copyWithCount(take));
            int accepted = take - left.getCount();
            if (accepted <= 0) continue;
            carried.shrink(accepted);
            if (carried.isEmpty()) cargo.set(i, ItemStack.EMPTY);
            delivered += accepted;
        }
        if (delivered > 0) {
            VillagerSimData.setWorkCargo(porter, level.registryAccess(), cargo, SLOTS);
            ticket.putInt("remaining", remaining - delivered);
            route.setTrafficScore(route.trafficScore() + delivered);
            data.touch();
            VillageStorageService.reconcileVillage(originId, level);
            VillageStorageService.reconcileVillage(destinationId, level);
        }
        if (ticket.getInt("remaining") == 0) porter.getPersistentData().remove(TICKET);
        return true;
    }

    private static Container recognized(ServerLevel level, VillageSavedData data,
                                         UUID villageId, BlockPos pos) {
        if (!VillageSimulationScheduler.isChunkLoaded(level, pos)
                || data.storageAt(villageId, pos)
                        .filter(s -> "valid".equals(s.validationState())).isEmpty()) return null;
        return level.getBlockEntity(pos) instanceof Container c ? c : null;
    }

    private static String itemId(ItemStack stack) {
        return BuiltInRegistries.ITEM.getKey(stack.getItem()).toString();
    }

    private static int stock(List<VillageStorageService.LocatedContainer> containers,
                             ItemStack sample) {
        int sum = 0;
        for (VillageStorageService.LocatedContainer c : containers) {
            for (int i = 0; i < c.container().getContainerSize(); i++) {
                ItemStack held = c.container().getItem(i);
                if (ItemStack.isSameItemSameComponents(held, sample))
                    sum = Math.min(Integer.MAX_VALUE, sum + held.getCount());
            }
        }
        return sum;
    }

    private static boolean canReceive(Container target, ItemStack sample, int quantity) {
        int capacity = 0;
        for (int i = 0; i < target.getContainerSize(); i++) {
            if (!target.canPlaceItem(i, sample)) continue;
            ItemStack existing = target.getItem(i);
            if (existing.isEmpty()) capacity += Math.min(sample.getMaxStackSize(), target.getMaxStackSize());
            else if (ItemStack.isSameItemSameComponents(existing, sample))
                capacity += Math.max(0, Math.min(existing.getMaxStackSize(),
                        target.getMaxStackSize()) - existing.getCount());
            if (capacity >= quantity) return true;
        }
        return false;
    }

    private static ItemStack insert(Container target, ItemStack source) {
        ItemStack remainder = source.copy();
        for (int i = 0; i < target.getContainerSize() && !remainder.isEmpty(); i++) {
            ItemStack existing = target.getItem(i);
            if (existing.isEmpty() || !target.canPlaceItem(i, remainder)
                    || !ItemStack.isSameItemSameComponents(existing, remainder)) continue;
            int move = Math.min(remainder.getCount(),
                    Math.max(0, Math.min(existing.getMaxStackSize(), target.getMaxStackSize())
                            - existing.getCount()));
            if (move > 0) {
                existing.grow(move);
                remainder.shrink(move);
                target.setChanged();
            }
        }
        for (int i = 0; i < target.getContainerSize() && !remainder.isEmpty(); i++) {
            if (!target.getItem(i).isEmpty() || !target.canPlaceItem(i, remainder)) continue;
            int move = Math.min(remainder.getCount(),
                    Math.min(remainder.getMaxStackSize(), target.getMaxStackSize()));
            target.setItem(i, remainder.copyWithCount(move));
            remainder.shrink(move);
        }
        return remainder;
    }
}
