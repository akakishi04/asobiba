package io.github.akakishi04.asobibatweaks.feature;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import java.util.function.Predicate;
import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.Container;
import net.minecraft.world.entity.npc.Villager;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.level.block.Blocks;

/**
 * Recognized village storage facade.
 *
 * <p>Physical containers remain authoritative. StorageRecord caches are last-known summaries
 * used for planning while chunks are unloaded. A one-time legacy bootstrap is allowed only
 * for villages that predate V3 and have no recognized storage records yet.</p>
 */
public final class VillageStorageService {
    private static final int LEGACY_BOOTSTRAP_RADIUS = 18;
    private static final int MAX_LEGACY_STORAGES = 32;
    private static final double PHYSICAL_ACCESS_DISTANCE_SQR = 4.5D * 4.5D;

    private VillageStorageService() {
    }

    public static Optional<UUID> villageId(Villager villager) {
        return VillagerSimData.villageId(villager);
    }

    public static void bootstrapLegacyIfNeeded(Villager villager, ServerLevel level) {
        Optional<UUID> villageId = villageId(villager);
        if (villageId.isEmpty()) return;

        VillageSavedData data = VillageSavedData.get(level);
        VillageSavedData.VillageRecord village = data.village(villageId.get()).orElse(null);
        if (village == null || village.storageBootstrapComplete()) return;

        BlockPos center = village.center();
        BlockPos min = center.offset(-LEGACY_BOOTSTRAP_RADIUS, -4, -LEGACY_BOOTSTRAP_RADIUS);
        BlockPos max = center.offset(LEGACY_BOOTSTRAP_RADIUS, 4, LEGACY_BOOTSTRAP_RADIUS);
        if (!VillageSimulationScheduler.isAreaLoaded(level, min, max)) return;

        int added = 0;
        for (BlockPos pos : BlockPos.betweenClosed(min, max)) {
            if (added >= MAX_LEGACY_STORAGES) break;
            var state = level.getBlockState(pos);
            if (!(state.is(Blocks.CHEST) || state.is(Blocks.TRAPPED_CHEST) || state.is(Blocks.BARREL))) continue;
            if (!level.isVillage(pos)) continue;
            if (!(level.getBlockEntity(pos) instanceof Container)) continue;
            if (data.storageAt(villageId.get(), pos).isPresent()) continue;

            data.createStorage(villageId.get(), pos, "general");
            added++;
        }

        village.setStorageBootstrapComplete(true);
        data.touch();
        reconcileVillage(villageId.get(), level);
    }

    /**
     * Containers the villager can physically interact with right now.
     * Planning uses the village ledger / StorageRecords instead of this local-access view.
     */
    public static List<LocatedContainer> containers(Villager villager, ServerLevel level) {
        Optional<UUID> villageId = villageId(villager);
        if (villageId.isEmpty()) return List.of();

        bootstrapLegacyIfNeeded(villager, level);
        List<LocatedContainer> result = new ArrayList<>();
        for (LocatedContainer located : containers(villageId.get(), level)) {
            if (villager.distanceToSqr(located.record.pos().getCenter()) <= PHYSICAL_ACCESS_DISTANCE_SQR) {
                result.add(located);
            }
        }
        return result;
    }

    public static List<LocatedContainer> containers(UUID villageId, ServerLevel level) {
        VillageSavedData data = VillageSavedData.get(level);
        List<LocatedContainer> result = new ArrayList<>();

        for (VillageSavedData.StorageRecord record : data.storagesForVillage(villageId)) {
            BlockPos pos = record.pos();
            if (!VillageSimulationScheduler.isChunkLoaded(level, pos)) continue;
            if (level.getBlockEntity(pos) instanceof Container container) {
                result.add(new LocatedContainer(record, container));
            }
        }
        return result;
    }

    public static Optional<LocatedContainer> nearestContainer(Villager villager, ServerLevel level) {
        LocatedContainer best = null;
        double bestDistance = Double.MAX_VALUE;
        Optional<UUID> villageId = villageId(villager);
        if (villageId.isEmpty()) return Optional.empty();
        bootstrapLegacyIfNeeded(villager, level);

        for (LocatedContainer located : containers(villageId.get(), level)) {
            double distance = villager.distanceToSqr(located.record.pos().getCenter());
            if (distance < bestDistance) {
                bestDistance = distance;
                best = located;
            }
        }
        return Optional.ofNullable(best);
    }

    public static Optional<LocatedContainer> nearestContainerWith(
            Villager villager, ServerLevel level, Item item) {
        return nearestContainerMatching(villager, level, stack -> stack.is(item));
    }

    public static Optional<LocatedContainer> nearestContainerMatching(
            Villager villager, ServerLevel level, Predicate<ItemStack> predicate) {
        Optional<UUID> villageId = villageId(villager);
        if (villageId.isEmpty()) return Optional.empty();
        bootstrapLegacyIfNeeded(villager, level);

        LocatedContainer best = null;
        double bestDistance = Double.MAX_VALUE;
        for (LocatedContainer located : containers(villageId.get(), level)) {
            boolean matches = false;
            Container container = located.container();
            for (int slot = 0; slot < container.getContainerSize(); slot++) {
                ItemStack stack = container.getItem(slot);
                if (!stack.isEmpty() && predicate.test(stack)) {
                    matches = true;
                    break;
                }
            }
            if (!matches) continue;

            double distance = villager.distanceToSqr(located.record().pos().getCenter());
            if (distance < bestDistance) {
                bestDistance = distance;
                best = located;
            }
        }
        return Optional.ofNullable(best);
    }

    public static void reconcileVillage(Villager villager, ServerLevel level) {
        villageId(villager).ifPresent(id -> reconcileVillage(id, level));
    }

    public static void reconcileVillage(UUID villageId, ServerLevel level) {
        VillageSavedData data = VillageSavedData.get(level);
        VillageSavedData.VillageRecord village = data.village(villageId).orElse(null);
        if (village == null) return;

        for (VillageSavedData.StorageRecord record : data.storagesForVillage(villageId)) {
            BlockPos pos = record.pos();
            if (!VillageSimulationScheduler.isChunkLoaded(level, pos)) continue;

            if (level.getBlockEntity(pos) instanceof Container container) {
                record.replaceCachedCounts(countContainer(container));
                record.setValidationState("valid");
                record.setLastValidatedGameTime(level.getGameTime());
            } else {
                // The chunk is loaded, so absence is authoritative for this position.
                record.replaceCachedCounts(Map.of());
                record.setValidationState("invalid");
                record.setLastValidatedGameTime(level.getGameTime());
            }
        }

        Map<String, Integer> aggregate = new HashMap<>();
        for (VillageSavedData.StorageRecord record : data.storagesForVillage(villageId)) {
            record.cachedCounts().forEach((key, value) -> aggregate.merge(key, value, Integer::sum));
        }
        village.replaceLedger(aggregate);
        data.touch();
    }

    public static int count(Villager villager, ServerLevel level, Item... items) {
        Optional<UUID> villageId = villageId(villager);
        if (villageId.isEmpty()) return 0;
        bootstrapLegacyIfNeeded(villager, level);

        VillageSavedData data = VillageSavedData.get(level);
        VillageSavedData.VillageRecord village = data.village(villageId.get()).orElse(null);
        if (village == null) return 0;

        int total = 0;
        for (Item item : items) {
            total += village.ledgerCount(itemKey(item));
        }
        return total;
    }

    public static int countMatching(Villager villager, ServerLevel level, Predicate<ItemStack> predicate) {
        int total = 0;
        for (LocatedContainer located : containers(villager, level)) {
            Container container = located.container;
            for (int slot = 0; slot < container.getContainerSize(); slot++) {
                ItemStack stack = container.getItem(slot);
                if (predicate.test(stack)) total += stack.getCount();
            }
        }
        return total;
    }

    public static List<ItemStack> extract(Villager villager, ServerLevel level, Item item, int count) {
        if (count <= 0) return List.of();
        return extractMatching(villager, level, stack -> stack.is(item), count);
    }

    public static List<ItemStack> extractMatching(Villager villager, ServerLevel level,
                                                  Predicate<ItemStack> predicate, int count) {
        if (count <= 0) return List.of();
        if (countMatching(villager, level, predicate) < count) return List.of();

        int remaining = count;
        List<ItemStack> extracted = new ArrayList<>();
        for (LocatedContainer located : containers(villager, level)) {
            Container container = located.container;
            for (int slot = 0; slot < container.getContainerSize() && remaining > 0; slot++) {
                ItemStack stack = container.getItem(slot);
                if (!predicate.test(stack)) continue;

                int take = Math.min(remaining, stack.getCount());
                extracted.add(stack.copyWithCount(take));
                stack.shrink(take);
                remaining -= take;
                container.setChanged();
            }
            if (remaining <= 0) break;
        }

        if (remaining > 0) {
            // This should be unreachable after the pre-count under a single-threaded server tick.
            // Restore what was extracted rather than allowing a partial silent withdrawal.
            for (ItemStack stack : extracted) {
                ItemStack remainder = insert(villager, level, stack);
                if (!remainder.isEmpty()) {
                    // If the container topology changed unexpectedly, preserve the item physically
                    // in-world rather than silently deleting it.
                    villager.spawnAtLocation(remainder);
                }
            }
            reconcileVillage(villager, level);
            return List.of();
        }

        reconcileVillage(villager, level);
        return extracted;
    }

    public static boolean take(Villager villager, ServerLevel level, Item item, int count) {
        if (count <= 0) return true;
        int remaining = count;

        for (LocatedContainer located : containers(villager, level)) {
            Container container = located.container;
            for (int slot = 0; slot < container.getContainerSize(); slot++) {
                ItemStack stack = container.getItem(slot);
                if (!stack.is(item)) continue;
                int take = Math.min(remaining, stack.getCount());
                stack.shrink(take);
                remaining -= take;
                container.setChanged();
                if (remaining <= 0) {
                    reconcileVillage(villager, level);
                    return true;
                }
            }
        }

        // Preserve legacy atomic semantics: callers are expected to pre-count before multi-stack takes.
        reconcileVillage(villager, level);
        return false;
    }

    public static boolean takeMatching(Villager villager, ServerLevel level, Predicate<ItemStack> predicate, int count) {
        if (count <= 0) return true;
        if (countMatching(villager, level, predicate) < count) return false;

        int remaining = count;
        for (LocatedContainer located : containers(villager, level)) {
            Container container = located.container;
            for (int slot = 0; slot < container.getContainerSize(); slot++) {
                ItemStack stack = container.getItem(slot);
                if (!predicate.test(stack)) continue;
                int take = Math.min(remaining, stack.getCount());
                stack.shrink(take);
                remaining -= take;
                container.setChanged();
                if (remaining <= 0) {
                    reconcileVillage(villager, level);
                    return true;
                }
            }
        }

        reconcileVillage(villager, level);
        return false;
    }

    /**
     * Inserts a physical stack into recognized loaded village storage.
     *
     * @return remaining stack that could not be inserted; EMPTY means full success.
     */
    public static ItemStack insert(Villager villager, ServerLevel level, ItemStack incoming) {
        if (incoming.isEmpty()) return ItemStack.EMPTY;
        ItemStack work = incoming.copy();

        for (LocatedContainer located : containers(villager, level)) {
            Container container = located.container;

            for (int slot = 0; slot < container.getContainerSize() && !work.isEmpty(); slot++) {
                ItemStack stack = container.getItem(slot);
                if (!stack.isEmpty() && ItemStack.isSameItemSameComponents(stack, work)
                        && stack.getCount() < stack.getMaxStackSize()) {
                    int move = Math.min(work.getCount(), stack.getMaxStackSize() - stack.getCount());
                    stack.grow(move);
                    work.shrink(move);
                    container.setChanged();
                }
            }

            for (int slot = 0; slot < container.getContainerSize() && !work.isEmpty(); slot++) {
                if (!container.getItem(slot).isEmpty()) continue;
                int move = Math.min(work.getCount(), work.getMaxStackSize());
                container.setItem(slot, work.copyWithCount(move));
                work.shrink(move);
                container.setChanged();
            }

            if (work.isEmpty()) break;
        }

        reconcileVillage(villager, level);
        return work;
    }

    public static boolean reserve(Villager villager, ServerLevel level, Item item, int count) {
        Optional<UUID> villageId = villageId(villager);
        if (villageId.isEmpty() || count <= 0) return false;
        bootstrapLegacyIfNeeded(villager, level);

        VillageSavedData data = VillageSavedData.get(level);
        VillageSavedData.VillageRecord village = data.village(villageId.get()).orElse(null);
        if (village == null) return false;

        boolean reserved = village.reserve(itemKey(item), count);
        if (reserved) data.touch();
        return reserved;
    }

    public static void releaseReservation(Villager villager, ServerLevel level, Item item, int count) {
        Optional<UUID> villageId = villageId(villager);
        if (villageId.isEmpty()) return;

        VillageSavedData data = VillageSavedData.get(level);
        VillageSavedData.VillageRecord village = data.village(villageId.get()).orElse(null);
        if (village == null) return;

        village.releaseReservation(itemKey(item), count);
        data.touch();
    }

    public static String itemKey(Item item) {
        return BuiltInRegistries.ITEM.getKey(item).toString();
    }

    private static Map<String, Integer> countContainer(Container container) {
        Map<String, Integer> counts = new HashMap<>();
        for (int slot = 0; slot < container.getContainerSize(); slot++) {
            ItemStack stack = container.getItem(slot);
            if (stack.isEmpty()) continue;
            counts.merge(itemKey(stack.getItem()), stack.getCount(), Integer::sum);
        }
        return counts;
    }

    public record LocatedContainer(VillageSavedData.StorageRecord record, Container container) {
    }
}
