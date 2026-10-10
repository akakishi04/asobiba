package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import java.util.List;
import java.util.UUID;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.Tag;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.tags.ItemTags;
import net.minecraft.world.Container;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.item.ItemEntity;
import net.minecraft.world.entity.vehicle.ChestBoat;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.phys.Vec3;
import net.neoforged.bus.api.SubscribeEvent;
import net.neoforged.neoforge.event.entity.EntityLeaveLevelEvent;
import net.neoforged.neoforge.event.tick.EntityTickEvent;
import net.neoforged.neoforge.event.tick.LevelTickEvent;

/**
 * Experimental REAL-boat cargo courier between two finished River Docks.
 *
 * One paid, vanilla ChestBoat entity is the sole cargo holder during travel.
 * Its identity is saved on the route and its route/waypoint state is saved on
 * the physical entity. Unknown/unloaded carrier state never authorizes a
 * replacement boat: fail closed instead of minting a second inventory.
 *
 * Loading/unloading happens only at the corresponding *physical*, registered
 * dock Barrel; no item is moved from source to destination instantaneously.
 * In particular this is NOT yet a general inter-village merchant system.
 */
public final class VillageRiverCargoService {
    private static final String ROUTE = "asobibatweaks_river_cargo_route";
    private static final String FORWARD = "asobibatweaks_river_cargo_forward";
    private static final String PHASE = "asobibatweaks_river_cargo_phase";
    private static final String CURSOR = "asobibatweaks_river_cargo_cursor";
    private static final String COURSE_HASH = "asobibatweaks_river_course";
    private static final String CARGO_ITEM = "asobibatweaks_river_cargo_item";
    private static final String IDLE_SINCE = "asobibatweaks_river_idle_since";
    private static final long MAX_IDLE_TICKS = 24_000L;
    private static final int MAX_SHIPMENT = 16;
    private static final double MOVE_SPEED = 0.16D;
    // Real vanilla boat hulls can drift while damping velocity near a dock.
    // A slightly wider berth radius avoids permanent stranding a boat that
    // has genuinely reached its water-side landing, without teleportation.
    private static final double MOOR_RADIUS_SQUARED = 2.25D * 2.25D;

    public VillageRiverCargoService() {}

    @SubscribeEvent
    public void onLevelTick(LevelTickEvent.Post event) {
        if (!enabled() || !(event.getLevel() instanceof ServerLevel level)
                || level.getGameTime() % 200 != 0L) return;

        VillageSavedData data = VillageSavedData.get(level);
        int examined = 0;
        for (VillageSavedData.VillageRecord village : data.villagesView().values()) {
            if (!"active".equals(village.lifecycle())) continue;
            for (UUID routeId : village.routeIds()) {
                if (++examined > 8) return; // bounded across all loaded villages
                VillageSavedData.RouteRecord route = data.route(routeId).orElse(null);
                if (route == null || !"river".equals(route.type())
                        || !"active".equals(route.state())
                        || route.carrierEntityId() != null
                        || route.waypoints().size() < 2) continue;
                tryLaunch(level, data, route);
            }
        }
    }

    @SubscribeEvent
    public void onBoatTick(EntityTickEvent.Post event) {
        if (!(event.getEntity() instanceof ChestBoat boat)
                || !(boat.level() instanceof ServerLevel level)) return;
        // Normal dispatch remains gated by the experimental config; the
        // shared physical boat state machine is exercised directly by
        // server GameTests without enabling the feature for other worlds.
        if (!enabled()) return;
        tickCarrier(boat, level);
    }

    /** Only an observed terminal removal can release an occupied route.
     * Unloading, dimension transfer, or an absent UUID is not destruction.
     * Vanilla owns physical cargo/boat drops; never synthesize a refund here.
     */
    @SubscribeEvent
    public void onCarrierRemoved(EntityLeaveLevelEvent event) {
        if (!(event.getEntity() instanceof ChestBoat boat)
                || !(event.getLevel() instanceof ServerLevel level)) return;
        Entity.RemovalReason reason = boat.getRemovalReason();
        if (reason != Entity.RemovalReason.KILLED
                && reason != Entity.RemovalReason.DISCARDED) return;
        CompoundTag state = boat.getPersistentData();
        if (!state.hasUUID(ROUTE)) return;
        VillageSavedData data = VillageSavedData.get(level);
        VillageSavedData.RouteRecord route = data.route(state.getUUID(ROUTE)).orElse(null);
        if (route == null || !boat.getUUID().equals(route.carrierEntityId())) return;
        route.setCarrierEntityId(null);
        data.touch();
    }

    static void tickCarrier(ChestBoat boat, ServerLevel level) {
        CompoundTag state = boat.getPersistentData();
        if (!state.hasUUID(ROUTE)) return;
        if (!boat.isAlive() || boat.isVehicle()) {
            // If a player took control, restart the conservative idle period.
            if (boat.isVehicle()) state.remove(IDLE_SINCE);
            stop(boat);
            return;
        }

        VillageSavedData data = VillageSavedData.get(level);
        VillageSavedData.RouteRecord route =
                data.route(state.getUUID(ROUTE)).orElse(null);
        if (route == null || !boat.getUUID().equals(route.carrierEntityId())
                || !"active".equals(route.state())) {
            stop(boat);
            return;
        }
        List<BlockPos> points = route.waypoints();
        if (points.size() < 2 || points.hashCode() != state.getInt(COURSE_HASH)) {
            // A changed route must not suddenly steer loaded cargo onto an
            // unrelated path. Keep the boat and contents where they are.
            stop(boat);
            return;
        }

        boolean forward = state.getBoolean(FORWARD);
        String phase = state.getString(PHASE);
        if ("idle".equals(phase)) {
            stop(boat);
            if (!state.contains(IDLE_SINCE, Tag.TAG_LONG))
                state.putLong(IDLE_SINCE, level.getGameTime());
            if (emptyCargo(boat)
                    && level.getGameTime() - state.getLong(IDLE_SINCE) >= MAX_IDLE_TICKS
                    && releaseIdleBoat(boat, level, data, route, forward)) return;
            if (boat.tickCount % 40 != 0 || !emptyCargo(boat)) return;
            BlockPos sourcePoint = forward ? route.from() : route.to();
            if (horizontalDistanceSqr(boat, sourcePoint) > MOOR_RADIUS_SQUARED) return;
            Container source = dockBarrel(level, data, route.villageId(), sourcePoint);
            Container target = dockBarrel(level, data, route.villageId(),
                    forward ? route.to() : route.from());
            CargoChoice cargo = chooseCargo(source, target,
                    route.dockReceipts(!forward));
            if (cargo == null) return;
            // The boat physically receives the same stack removed from the
            // source Barrel. Nothing is copied or regenerated on departure.
            ItemStack loaded = source.removeItem(cargo.slot(), cargo.count());
            if (loaded.isEmpty()) return;
            boat.setItem(0, loaded);
            source.setChanged();
            state.putString(CARGO_ITEM,
                    BuiltInRegistries.ITEM.getKey(loaded.getItem()).toString());
            state.putString(PHASE, "outbound");
            state.remove(IDLE_SINCE);
            state.putInt(CURSOR, forward ? 1 : points.size() - 2);
            return;
        }

        if ("unload".equals(phase) || "return_unload".equals(phase)) {
            stop(boat);
            boolean homeward = "return_unload".equals(phase);
            boolean destinationAtTo = homeward ? !forward : forward;
            BlockPos destinationPoint = destinationAtTo ? route.to() : route.from();
            Container destination = dockBarrel(level, data, route.villageId(),
                    destinationPoint);
            if (destination == null || horizontalDistanceSqr(boat,
                    destinationPoint) > MOOR_RADIUS_SQUARED) return;

            String manifest = state.getString(CARGO_ITEM);
            int before = manifestCount(boat, manifest);
            boolean emptied = unload(boat, destination, manifest);
            int physicallyDelivered = before - manifestCount(boat, manifest);
            if (physicallyDelivered > 0) {
                route.recordDockDelivery(destinationAtTo, manifest, physicallyDelivered);
                data.touch();
                VillageStorageService.reconcileVillage(route.villageId(), level);
            }
            // A full destination holds the remaining real cargo in the boat.
            if (!emptied) return;
            if (homeward) {
                state.putString(PHASE, "idle");
                state.putLong(IDLE_SINCE, level.getGameTime());
                state.remove(CARGO_ITEM);
                return;
            }

            // On the return leg, carry qualifying real stock from the remote
            // dock when the original endpoint has an actual shortage.
            // Ordinary second-leg loading uses the same conservation rules.
            Container origin = dockBarrel(level, data, route.villageId(),
                    forward ? route.from() : route.to());
            CargoChoice backhaul = chooseCargo(destination, origin,
                    route.dockReceipts(destinationAtTo));
            if (backhaul != null) {
                ItemStack picked = destination.removeItem(
                        backhaul.slot(), backhaul.count());
                if (!picked.isEmpty()) {
                    boat.setItem(0, picked);
                    destination.setChanged();
                    state.putString(CARGO_ITEM,
                            BuiltInRegistries.ITEM.getKey(picked.getItem()).toString());
                    VillageStorageService.reconcileVillage(route.villageId(), level);
                }
            } else {
                state.remove(CARGO_ITEM);
            }
            state.putString(PHASE, "return");
            state.putInt(CURSOR, forward ? points.size() - 2 : 1);
            return;
        }

        if (!"outbound".equals(phase) && !"return".equals(phase)) {
            stop(boat);
            return;
        }

        boolean travelForward = "outbound".equals(phase) == forward;
        int targetIndex = state.getInt(CURSOR);
        if (targetIndex < 0 || targetIndex >= points.size()) {
            stop(boat);
            return;
        }
        BlockPos destination = points.get(targetIndex);
        double dx = destination.getX() + 0.5D - boat.getX();
        double dz = destination.getZ() + 0.5D - boat.getZ();
        double distance2 = dx * dx + dz * dz;

        if (distance2 <= MOOR_RADIUS_SQUARED) {
            int next = targetIndex + (travelForward ? 1 : -1);
            if (next < 0 || next >= points.size()) {
                stop(boat);
                if ("outbound".equals(phase)) {
                    state.putString(PHASE, "unload");
                } else {
                    state.putString(PHASE, emptyCargo(boat) ? "idle" : "return_unload");
                    if (emptyCargo(boat)) state.putLong(IDLE_SINCE, level.getGameTime());
                }
                return;
            }
            targetIndex = next;
            state.putInt(CURSOR, targetIndex);
            destination = points.get(targetIndex);
            dx = destination.getX() + 0.5D - boat.getX();
            dz = destination.getZ() + 0.5D - boat.getZ();
            distance2 = dx * dx + dz * dz;
        }
        if (distance2 < 1.0E-4D) {
            stop(boat);
            return;
        }
        double distance = Math.sqrt(distance2);
        double towardX = dx / distance;
        double towardZ = dz / distance;
        BlockPos ahead = new BlockPos(
                (int)Math.floor(boat.getX() + towardX * 1.5D),
                route.from().getY(),
                (int)Math.floor(boat.getZ() + towardZ * 1.5D));
        if (!VillageSimulationScheduler.isChunkLoaded(level, ahead)
                || !VillageRiverNavigationService.navigable(level, ahead)) {
            stop(boat);
            return;
        }
        // Velocity is applied to the REAL vanilla boat, not its position.
        // It remains subject to collisions, buoyancy, world saving and chunk
        // unload. A passenger can take over by mounting it.
        boat.setDeltaMovement(new Vec3(
                towardX * MOVE_SPEED,
                boat.getDeltaMovement().y,
                towardZ * MOVE_SPEED));
    }

    /**
     * Return an EMPTY physical ChestBoat to one physical item after an entire
     * idle Minecraft day at its real registered home berth. No cargo,
     * passengers or player-added stock may be deleted by maintenance.
     */
    static boolean releaseIdleBoat(ChestBoat boat, ServerLevel level,
                                   VillageSavedData data, VillageSavedData.RouteRecord route,
                                   boolean forward) {
        if (!boat.isAlive() || boat.isVehicle() || !emptyCargo(boat)
                || !boat.getUUID().equals(route.carrierEntityId())
                || !"active".equals(route.state())
                || !"idle".equals(boat.getPersistentData().getString(PHASE))) return false;
        BlockPos home = forward ? route.from() : route.to();
        if (horizontalDistanceSqr(boat, home) > MOOR_RADIUS_SQUARED) return false;
        Container dock = dockBarrel(level, data, route.villageId(), home);
        if (dock == null) return false;

        // Convert the paid entity to exactly one reusable physical item.
        // A rejected world-item spawn leaves the original entity intact.
        ItemStack remaining = insert(dock, new ItemStack(Items.OAK_CHEST_BOAT));
        if (!remaining.isEmpty()) {
            ItemEntity dropped = new ItemEntity(level, boat.getX(),
                    boat.getY() + 0.35D, boat.getZ(), remaining);
            if (!level.addFreshEntity(dropped)) return false;
        }
        route.setCarrierEntityId(null);
        data.touch();
        boat.getPersistentData().remove(ROUTE);
        boat.discard();
        VillageStorageService.reconcileVillage(route.villageId(), level);
        return true;
    }

    static ChestBoat tryLaunch(ServerLevel level, VillageSavedData data,
                               VillageSavedData.RouteRecord route) {
        List<BlockPos> path = route.waypoints();
        if (path.isEmpty() || !path.getFirst().equals(route.from())
                || !path.getLast().equals(route.to())) return null;
        if (!VillageRiverNavigationService.navigable(level, route.from())
                || !VillageRiverNavigationService.navigable(level, route.to())) return null;

        Container first = dockBarrel(level, data, route.villageId(), route.from());
        Container second = dockBarrel(level, data, route.villageId(), route.to());
        if (first == null || second == null) return null;

        boolean forward = true;
        CargoChoice shipment = chooseCargo(first, second,
                route.dockReceipts(false));
        Container source = first;
        if (shipment == null) {
            shipment = chooseCargo(second, first,
                    route.dockReceipts(true));
            source = second;
            forward = false;
        }
        if (shipment == null) return null;

        int boatItemSlot = findBoatItem(source);
        if (boatItemSlot < 0) return null; // no free boats or synthetic recipes
        BlockPos departure = forward ? route.from() : route.to();
        ChestBoat boat = EntityType.CHEST_BOAT.create(level);
        if (boat == null) return null;
        // Boat position is its bottom, not the center of the water block.
        // Spawning at waterY + 0.3 submerges the hull, causing it to sink
        // and stall on the river bed under real vanilla boat physics.
        // Place the hull at the actual source-water surface instead.
        boat.setPos(departure.getX() + 0.5D,
                departure.getY() + 1.0D, departure.getZ() + 0.5D);
        CompoundTag state = boat.getPersistentData();
        state.putUUID(ROUTE, route.id());
        state.putBoolean(FORWARD, forward);
        state.putString(PHASE, "outbound");
        state.putInt(CURSOR, forward ? 1 : path.size() - 2);
        state.putInt(COURSE_HASH, path.hashCode());

        if (!level.addFreshEntity(boat)) return null;
        // Consume exactly one actual ChestBoat item only after the physical
        // entity has successfully entered the loaded world.
        ItemStack paid = source.removeItem(boatItemSlot, 1);
        if (!paid.is(Items.OAK_CHEST_BOAT) || paid.getCount() != 1) {
            if (!paid.isEmpty()) insert(source, paid);
            boat.discard();
            return null;
        }
        ItemStack shipped = source.removeItem(shipment.slot(), shipment.count());
        if (shipped.isEmpty()) {
            // No shipment: keep the paid physical boat moored for subsequent
            // dispatches rather than discarding a legitimate item.
            state.putString(PHASE, "idle");
        } else {
            boat.setItem(0, shipped);
            state.putString(CARGO_ITEM,
                    BuiltInRegistries.ITEM.getKey(shipped.getItem()).toString());
        }
        source.setChanged();
        route.setCarrierEntityId(boat.getUUID());
        data.touch();
        VillageStorageService.reconcileVillage(route.villageId(), level);
        return boat;
    }

    static Container dockBarrel(ServerLevel level, VillageSavedData data,
                                        UUID villageId, BlockPos waterEnd) {
        for (VillageSavedData.WorkSiteRecord site : data.workSitesForVillage(villageId)) {
            if (!"river_dock".equals(site.type()) || !"active".equals(site.state())
                    || !site.purpose().startsWith("dock:")) continue;
            UUID projectId;
            try {
                projectId = UUID.fromString(site.purpose().substring("dock:".length()));
            } catch (IllegalArgumentException ignored) {
                continue;
            }
            VillageSavedData.ProjectRecord project = data.project(projectId).orElse(null);
            if (project == null || !VillageRiverDockService.TEMPLATE.equals(project.templateId())
                    || !"complete".equals(project.phase())
                    || !project.villageId().equals(villageId)) continue;
            Direction direction = switch (project.parameter("dock_direction")) {
                case "north" -> Direction.NORTH;
                case "south" -> Direction.SOUTH;
                case "east" -> Direction.EAST;
                case "west" -> Direction.WEST;
                default -> null;
            };
            if (direction == null) continue;
            int waterY;
            try {
                waterY = Integer.parseInt(project.parameter("dock_water_y"));
            } catch (NumberFormatException ignored) {
                continue;
            }
            BlockPos bank = project.site();
            BlockPos savedBerth = new BlockPos(
                    bank.getX() + direction.getStepX() * 3, waterY,
                    bank.getZ() + direction.getStepZ() * 3);
            if (!waterEnd.equals(savedBerth)) continue;
            // Sailing must validate real water. Once the vessel has reached a
            // dock, unloading requires the VERIFIED physical Barrel and saved
            // storage identity, not re-running navigability checks that can
            // transiently fail in a changing game-test or player-built world.
            BlockPos storagePos = bank.relative(direction.getClockWise()).above();
            if (!VillageSimulationScheduler.isChunkLoaded(level, storagePos)
                    || !level.getBlockState(storagePos).is(net.minecraft.world.level.block.Blocks.BARREL)
                    || data.storageAt(villageId, storagePos).isEmpty()) continue;
            if (level.getBlockEntity(storagePos) instanceof Container barrel) return barrel;
        }
        return null;
    }

    /**
     * Select real cargo using receiving capacity before slot order. A full
     * destination is still allowed as a last resort: the physical ChestBoat
     * retains the shipment until its Barrel has room (GT12).
     *
     * Among equally receivable goods prefer the one with less stock in the
     * destination Barrel. This is only a dock-level V90 priority, not yet a
     * village-wide scarcity or inter-settlement market decision.
     */
    private static CargoChoice chooseCargo(
            Container source, Container destination,
            java.util.Map<String, Integer> pendingDockDeliveries) {
        if (source == null || destination == null) return null;
        CargoChoice best = null;
        boolean bestFits = false;
        int bestDestinationCount = Integer.MAX_VALUE;
        for (int slot = 0; slot < source.getContainerSize(); slot++) {
            ItemStack stack = source.getItem(slot);
            if (stack.isEmpty() || !approved(stack)) continue;
            String key = BuiltInRegistries.ITEM.getKey(stack.getItem()).toString();
            // Boat arrivals are already owned by the local warehouse
            // transfer backlog. Never send the same stock straight back.
            int awaitingPorter = pendingDockDeliveries.getOrDefault(key, 0);
            int available = stack.getCount() - awaitingPorter;
            if (available < 32) continue;
            int destinationCount = countMatching(destination, stack);
            if (destinationCount >= 16) continue;
            int quantity = Math.min(MAX_SHIPMENT,
                    Math.min(available - 16, 16 - destinationCount));
            if (quantity <= 0) continue;

            boolean fits = canReceive(destination, stack, quantity);
            if (best == null
                    || (fits && !bestFits)
                    || (fits == bestFits && destinationCount < bestDestinationCount)) {
                best = new CargoChoice(slot, quantity);
                bestFits = fits;
                bestDestinationCount = destinationCount;
            }
        }
        return best;
    }

    /** Does the physical destination currently have room for this exact stack? */
    private static boolean canReceive(Container destination, ItemStack candidate, int amount) {
        int space = 0;
        int emptyCapacity = Math.min(candidate.getMaxStackSize(), destination.getMaxStackSize());
        for (int slot = 0; slot < destination.getContainerSize(); slot++) {
            ItemStack existing = destination.getItem(slot);
            if (existing.isEmpty()) {
                space += emptyCapacity;
            } else if (ItemStack.isSameItemSameComponents(existing, candidate)) {
                space += Math.max(0,
                        Math.min(existing.getMaxStackSize(), destination.getMaxStackSize())
                                - existing.getCount());
            }
            if (space >= amount) return true;
        }
        return false;
    }

    private static int countMatching(Container container, ItemStack exemplar) {
        int total = 0;
        for (int slot = 0; slot < container.getContainerSize(); slot++) {
            ItemStack stack = container.getItem(slot);
            if (ItemStack.isSameItemSameComponents(stack, exemplar)) total += stack.getCount();
        }
        return total;
    }

    static boolean approved(ItemStack stack) {
        return stack.is(ItemTags.LOGS) || stack.is(ItemTags.PLANKS)
                || stack.is(ItemTags.WOOL) || stack.is(Items.COBBLESTONE)
                || stack.is(Items.STONE) || stack.is(Items.IRON_INGOT)
                || stack.is(Items.BREAD) || stack.is(Items.WHEAT)
                || stack.is(Items.CARROT) || stack.is(Items.POTATO)
                || stack.is(Items.COD) || stack.is(Items.SALMON);
    }

    private static int findBoatItem(Container source) {
        for (int i = 0; i < source.getContainerSize(); i++) {
            if (source.getItem(i).is(Items.OAK_CHEST_BOAT)) return i;
        }
        return -1;
    }

    private static int manifestCount(ChestBoat boat, String manifest) {
        if (manifest.isBlank()) return 0;
        int total = 0;
        for (int i = 0; i < boat.getContainerSize(); i++) {
            ItemStack stack = boat.getItem(i);
            if (!stack.isEmpty() && BuiltInRegistries.ITEM.getKey(
                    stack.getItem()).toString().equals(manifest)) total += stack.getCount();
        }
        return total;
    }

    private static boolean unload(ChestBoat boat, Container destination, String manifestItem) {
        if (manifestItem.isBlank()) return false;
        // The boat is a normal vanilla entity: players/mods may put their own
        // things inside. Never claim, unload or destroy unrelated contents.
        for (int i = 0; i < boat.getContainerSize(); i++) {
            ItemStack stack = boat.getItem(i);
            if (stack.isEmpty()) continue;
            if (!approved(stack) || !BuiltInRegistries.ITEM.getKey(
                    stack.getItem()).toString().equals(manifestItem)) return false;
        }
        for (int i = 0; i < boat.getContainerSize(); i++) {
            ItemStack stack = boat.getItem(i);
            if (stack.isEmpty()) continue;
            ItemStack remainder = insert(destination, stack);
            int moved = stack.getCount() - remainder.getCount();
            if (moved > 0) {
                boat.setItem(i, remainder);
                boat.setChanged();
            }
        }
        return emptyCargo(boat);
    }

    private static ItemStack insert(Container destination, ItemStack source) {
        ItemStack remainder = source.copy();
        for (int i = 0; i < destination.getContainerSize() && !remainder.isEmpty(); i++) {
            ItemStack current = destination.getItem(i);
            if (current.isEmpty()
                    || !ItemStack.isSameItemSameComponents(current, remainder)) continue;
            int amount = Math.min(remainder.getCount(),
                    current.getMaxStackSize() - current.getCount());
            if (amount <= 0) continue;
            current.grow(amount);
            remainder.shrink(amount);
            destination.setChanged();
        }
        for (int i = 0; i < destination.getContainerSize() && !remainder.isEmpty(); i++) {
            if (!destination.getItem(i).isEmpty()) continue;
            int amount = Math.min(remainder.getCount(), remainder.getMaxStackSize());
            destination.setItem(i, remainder.copyWithCount(amount));
            remainder.shrink(amount);
        }
        return remainder;
    }

    private static boolean emptyCargo(ChestBoat boat) {
        for (int i = 0; i < boat.getContainerSize(); i++) {
            if (!boat.getItem(i).isEmpty()) return false;
        }
        return true;
    }

    private static void stop(ChestBoat boat) {
        boat.setDeltaMovement(new Vec3(0.0D, boat.getDeltaMovement().y, 0.0D));
    }

    private static double horizontalDistanceSqr(ChestBoat boat, BlockPos point) {
        double x = boat.getX() - point.getX() - 0.5D;
        double z = boat.getZ() - point.getZ() - 0.5D;
        return x * x + z * z;
    }

    private static boolean enabled() {
        return AsobibaTweaksConfig.VILLAGE_SIMULATION_ENABLED.getAsBoolean()
                && AsobibaTweaksConfig.VILLAGE_RIVER_DOCKS_ENABLED.getAsBoolean()
                && AsobibaTweaksConfig.VILLAGE_LOGISTICS_ENABLED.getAsBoolean()
                && AsobibaTweaksConfig.VILLAGE_RIVER_CARGO_ENABLED.getAsBoolean();
    }

    private record CargoChoice(int slot, int count) {}
}
