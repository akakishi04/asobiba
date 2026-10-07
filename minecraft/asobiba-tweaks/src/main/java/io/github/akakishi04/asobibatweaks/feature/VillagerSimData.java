package io.github.akakishi04.asobibatweaks.feature;

import java.util.ArrayList;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import net.minecraft.core.HolderLookup;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.ListTag;
import net.minecraft.nbt.Tag;
import net.minecraft.util.Mth;
import net.minecraft.world.entity.npc.Villager;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.ItemStack;

/**
 * Compact persistent per-villager simulation state.
 *
 * <p>This deliberately lives on the Villager entity while shared settlement state lives in
 * {@link VillageSavedData}. Final behavior passes can migrate legacy top-level keys into this
 * namespace without changing the shared VillageSavedData schema.</p>
 */
public final class VillagerSimData {
    public static final int SCHEMA_VERSION = 1;

    private static final String ROOT = "asobibatweaks_village_sim";
    private static final String SCHEMA = "schema";
    private static final String VILLAGE_ID = "village_id";
    private static final String DISTRICT_ID = "district_id";
    private static final String DUTY = "duty";
    private static final String DUTY_ASSIGNED_AT = "duty_assigned_at";
    private static final String WELFARE = "welfare";
    private static final String CARPENTRY_SKILL = "carpentry_skill";
    private static final String ACTIVE_OBSERVED_TICKS = "active_observed_ticks";
    private static final String REMIGRATION_COOLDOWN_UNTIL = "remigration_cooldown_until";
    private static final String DISPLACED = "displaced";
    private static final String ORIGIN_VILLAGE_ID = "origin_village_id";
    private static final String WORK_CARGO = "work_cargo";
    private static final String REFUSAL = "refusal";
    private static final String LAST_WELFARE_PRICE_PERCENT = "last_welfare_price_percent";
    private static final String LAST_WELFARE_OFFER_COUNT = "last_welfare_offer_count";
    private static final String LAST_SAMPLE_POS = "last_sample_pos";
    private static final String LAST_MOVE_ACTIVE = "last_move_active";
    private static final String LAST_SLEEP_ACTIVE = "last_sleep_active";
    private static final String LAST_WORK_ACTIVE = "last_work_active";
    private static final String LAST_OPEN_ACTIVE = "last_open_active";
    private static final String LAST_SOCIAL_ACTIVE = "last_social_active";

    private VillagerSimData() {
    }

    public static void ensureInitialized(Villager villager) {
        CompoundTag root = root(villager, true);
        if (!root.contains(SCHEMA, Tag.TAG_INT)) root.putInt(SCHEMA, SCHEMA_VERSION);
        if (!root.contains(DUTY, Tag.TAG_STRING)) root.putString(DUTY, "none");
        if (!root.contains(WELFARE, Tag.TAG_INT)) root.putInt(WELFARE, 100);
        if (!root.contains(CARPENTRY_SKILL, Tag.TAG_INT)) root.putInt(CARPENTRY_SKILL, 0);
        if (!root.contains(REFUSAL, Tag.TAG_BYTE)) root.putBoolean(REFUSAL, false);
    }

    public static Optional<UUID> villageId(Villager villager) {
        return readUuid(root(villager, false), VILLAGE_ID);
    }

    public static void setVillageId(Villager villager, UUID id) {
        CompoundTag root = root(villager, true);
        putUuid(root, VILLAGE_ID, id);
    }

    public static void clearVillageId(Villager villager) {
        root(villager, true).remove(VILLAGE_ID);
    }

    public static Optional<UUID> districtId(Villager villager) {
        return readUuid(root(villager, false), DISTRICT_ID);
    }

    public static void setDistrictId(Villager villager, UUID id) {
        putUuid(root(villager, true), DISTRICT_ID, id);
    }

    public static void clearDistrictId(Villager villager) {
        root(villager, true).remove(DISTRICT_ID);
    }

    public static String duty(Villager villager) {
        CompoundTag root = root(villager, false);
        String duty = root.getString(DUTY);
        return duty.isBlank() ? "none" : duty;
    }

    public static void setDuty(Villager villager, String duty, long assignedAtGameTime) {
        CompoundTag root = root(villager, true);
        root.putString(DUTY, duty == null || duty.isBlank() ? "none" : duty);
        root.putLong(DUTY_ASSIGNED_AT, assignedAtGameTime);
    }

    public static long dutyAssignedAt(Villager villager) {
        return root(villager, false).getLong(DUTY_ASSIGNED_AT);
    }

    public static int welfare(Villager villager) {
        CompoundTag root = root(villager, false);
        return root.contains(WELFARE, Tag.TAG_INT) ? Mth.clamp(root.getInt(WELFARE), 0, 100) : 100;
    }

    public static void setWelfare(Villager villager, int welfare) {
        root(villager, true).putInt(WELFARE, Mth.clamp(welfare, 0, 100));
    }

    public static boolean refusal(Villager villager) {
        return root(villager, false).getBoolean(REFUSAL);
    }

    public static void setRefusal(Villager villager, boolean value) {
        root(villager, true).putBoolean(REFUSAL, value);
    }

    public static int lastWelfarePricePercent(Villager villager) {
        return Math.max(0, root(villager, false).getInt(LAST_WELFARE_PRICE_PERCENT));
    }

    public static void setLastWelfarePricePercent(Villager villager, int value) {
        root(villager, true).putInt(LAST_WELFARE_PRICE_PERCENT, Math.max(0, value));
    }

    public static int lastWelfareOfferCount(Villager villager) {
        return Math.max(0, root(villager, false).getInt(LAST_WELFARE_OFFER_COUNT));
    }

    public static void setLastWelfareOfferCount(Villager villager, int value) {
        root(villager, true).putInt(LAST_WELFARE_OFFER_COUNT, Math.max(0, value));
    }

    public static Optional<net.minecraft.core.BlockPos> lastSamplePos(Villager villager) {
        CompoundTag root = root(villager, false);
        return root.contains(LAST_SAMPLE_POS, Tag.TAG_LONG)
                ? Optional.of(net.minecraft.core.BlockPos.of(root.getLong(LAST_SAMPLE_POS)))
                : Optional.empty();
    }

    public static void setLastSamplePos(Villager villager, net.minecraft.core.BlockPos pos) {
        root(villager, true).putLong(LAST_SAMPLE_POS, pos.asLong());
    }

    public static long lastMoveActive(Villager villager) { return root(villager, false).getLong(LAST_MOVE_ACTIVE); }
    public static void setLastMoveActive(Villager villager, long value) { root(villager, true).putLong(LAST_MOVE_ACTIVE, value); }
    public static long lastSleepActive(Villager villager) { return root(villager, false).getLong(LAST_SLEEP_ACTIVE); }
    public static void setLastSleepActive(Villager villager, long value) { root(villager, true).putLong(LAST_SLEEP_ACTIVE, value); }
    public static long lastWorkActive(Villager villager) { return root(villager, false).getLong(LAST_WORK_ACTIVE); }
    public static void setLastWorkActive(Villager villager, long value) { root(villager, true).putLong(LAST_WORK_ACTIVE, value); }
    public static long lastOpenActive(Villager villager) { return root(villager, false).getLong(LAST_OPEN_ACTIVE); }
    public static void setLastOpenActive(Villager villager, long value) { root(villager, true).putLong(LAST_OPEN_ACTIVE, value); }
    public static long lastSocialActive(Villager villager) { return root(villager, false).getLong(LAST_SOCIAL_ACTIVE); }
    public static void setLastSocialActive(Villager villager, long value) { root(villager, true).putLong(LAST_SOCIAL_ACTIVE, value); }

    public static int carpentrySkill(Villager villager) {
        CompoundTag root = root(villager, false);
        return root.contains(CARPENTRY_SKILL, Tag.TAG_INT)
                ? Mth.clamp(root.getInt(CARPENTRY_SKILL), 0, 100)
                : 0;
    }

    public static void setCarpentrySkill(Villager villager, int skill) {
        root(villager, true).putInt(CARPENTRY_SKILL, Mth.clamp(skill, 0, 100));
    }

    public static long activeObservedTicks(Villager villager) {
        return Math.max(0L, root(villager, false).getLong(ACTIVE_OBSERVED_TICKS));
    }

    public static void addActiveObservedTicks(Villager villager, long ticks) {
        if (ticks <= 0L) return;
        CompoundTag root = root(villager, true);
        long current = Math.max(0L, root.getLong(ACTIVE_OBSERVED_TICKS));
        long next;
        try {
            next = Math.addExact(current, ticks);
        } catch (ArithmeticException ignored) {
            next = Long.MAX_VALUE;
        }
        root.putLong(ACTIVE_OBSERVED_TICKS, next);
    }

    public static long remigrationCooldownUntil(Villager villager) {
        return root(villager, false).getLong(REMIGRATION_COOLDOWN_UNTIL);
    }

    public static void setRemigrationCooldownUntil(Villager villager, long gameTime) {
        root(villager, true).putLong(REMIGRATION_COOLDOWN_UNTIL, gameTime);
    }

    public static boolean displaced(Villager villager) {
        return root(villager, false).getBoolean(DISPLACED);
    }

    public static Optional<UUID> originVillageId(Villager villager) {
        return readUuid(root(villager, false), ORIGIN_VILLAGE_ID);
    }

    public static void setDisplaced(Villager villager, UUID originVillageId) {
        CompoundTag root = root(villager, true);
        root.putBoolean(DISPLACED, true);
        putUuid(root, ORIGIN_VILLAGE_ID, originVillageId);
    }

    public static void clearDisplaced(Villager villager) {
        CompoundTag root = root(villager, true);
        root.putBoolean(DISPLACED, false);
        root.remove(ORIGIN_VILLAGE_ID);
    }

    public static List<ItemStack> workCargo(Villager villager, HolderLookup.Provider registries, int capacity) {
        int safeCapacity = Math.max(0, capacity);
        List<ItemStack> cargo = new ArrayList<>(safeCapacity);
        for (int i = 0; i < safeCapacity; i++) cargo.add(ItemStack.EMPTY);

        ListTag rows = root(villager, false).getList(WORK_CARGO, Tag.TAG_COMPOUND);
        for (int i = 0; i < rows.size(); i++) {
            CompoundTag row = rows.getCompound(i);
            int slot = row.getInt("slot");
            if (slot < 0 || slot >= safeCapacity) continue;
            ItemStack stack = ItemStack.parseOptional(registries, row.getCompound("stack"));
            cargo.set(slot, stack);
        }
        return cargo;
    }

    public static void setWorkCargo(Villager villager, HolderLookup.Provider registries, List<ItemStack> cargo, int capacity) {
        int safeCapacity = Math.max(0, capacity);
        ListTag rows = new ListTag();
        for (int slot = 0; slot < Math.min(cargo.size(), safeCapacity); slot++) {
            ItemStack stack = cargo.get(slot);
            if (stack == null || stack.isEmpty()) continue;
            CompoundTag row = new CompoundTag();
            row.putInt("slot", slot);
            row.put("stack", stack.saveOptional(registries));
            rows.add(row);
        }
        root(villager, true).put(WORK_CARGO, rows);
    }

    public static boolean canInsertWorkCargo(Villager villager, HolderLookup.Provider registries,
                                             ItemStack incoming, int capacity) {
        if (incoming.isEmpty()) return true;
        List<ItemStack> cargo = workCargo(villager, registries, capacity);
        int remaining = incoming.getCount();

        for (ItemStack existing : cargo) {
            if (remaining <= 0) return true;
            if (existing.isEmpty() || !ItemStack.isSameItemSameComponents(existing, incoming)) continue;
            remaining -= Math.max(0, existing.getMaxStackSize() - existing.getCount());
        }
        for (ItemStack existing : cargo) {
            if (remaining <= 0) return true;
            if (existing.isEmpty()) remaining -= incoming.getMaxStackSize();
        }
        return remaining <= 0;
    }

    /**
     * Inserts into the persistent work cargo and returns the uninserted remainder.
     */
    public static ItemStack insertWorkCargo(Villager villager, HolderLookup.Provider registries,
                                            ItemStack incoming, int capacity) {
        if (incoming.isEmpty()) return ItemStack.EMPTY;
        List<ItemStack> cargo = workCargo(villager, registries, capacity);
        ItemStack work = incoming.copy();

        for (int slot = 0; slot < cargo.size() && !work.isEmpty(); slot++) {
            ItemStack existing = cargo.get(slot);
            if (existing.isEmpty() || !ItemStack.isSameItemSameComponents(existing, work)
                    || existing.getCount() >= existing.getMaxStackSize()) {
                continue;
            }
            int move = Math.min(work.getCount(), existing.getMaxStackSize() - existing.getCount());
            existing.grow(move);
            work.shrink(move);
        }

        for (int slot = 0; slot < cargo.size() && !work.isEmpty(); slot++) {
            if (!cargo.get(slot).isEmpty()) continue;
            int move = Math.min(work.getCount(), work.getMaxStackSize());
            cargo.set(slot, work.copyWithCount(move));
            work.shrink(move);
        }

        setWorkCargo(villager, registries, cargo, capacity);
        return work;
    }

    public static boolean hasWorkCargo(Villager villager, HolderLookup.Provider registries, int capacity) {
        for (ItemStack stack : workCargo(villager, registries, capacity)) {
            if (!stack.isEmpty()) return true;
        }
        return false;
    }

    public static int workCargoCount(Villager villager, HolderLookup.Provider registries,
                                     int capacity, Item item) {
        return workCargoCountMatching(villager, registries, capacity, stack -> stack.is(item));
    }

    public static int workCargoCountMatching(Villager villager, HolderLookup.Provider registries,
                                             int capacity, java.util.function.Predicate<ItemStack> predicate) {
        int total = 0;
        for (ItemStack stack : workCargo(villager, registries, capacity)) {
            if (predicate.test(stack)) total += stack.getCount();
        }
        return total;
    }

    public static boolean takeWorkCargo(Villager villager, HolderLookup.Provider registries,
                                        int capacity, Item item, int count) {
        return takeWorkCargoMatching(villager, registries, capacity, stack -> stack.is(item), count);
    }

    public static boolean takeWorkCargoMatching(Villager villager, HolderLookup.Provider registries,
                                                int capacity,
                                                java.util.function.Predicate<ItemStack> predicate,
                                                int count) {
        if (count <= 0) return true;
        List<ItemStack> cargo = workCargo(villager, registries, capacity);

        int available = 0;
        for (ItemStack stack : cargo) if (predicate.test(stack)) available += stack.getCount();
        if (available < count) return false;

        int remaining = count;
        for (int slot = 0; slot < cargo.size() && remaining > 0; slot++) {
            ItemStack stack = cargo.get(slot);
            if (!predicate.test(stack)) continue;
            int take = Math.min(remaining, stack.getCount());
            stack.shrink(take);
            remaining -= take;
            if (stack.isEmpty()) cargo.set(slot, ItemStack.EMPTY);
        }

        setWorkCargo(villager, registries, cargo, capacity);
        return true;
    }

    public static void clearWorkCargo(Villager villager) {
        root(villager, true).remove(WORK_CARGO);
    }

    private static CompoundTag root(Villager villager, boolean create) {
        CompoundTag persistent = villager.getPersistentData();
        if (persistent.contains(ROOT, Tag.TAG_COMPOUND)) {
            return persistent.getCompound(ROOT);
        }
        if (!create) {
            return new CompoundTag();
        }

        CompoundTag root = new CompoundTag();
        root.putInt(SCHEMA, SCHEMA_VERSION);
        persistent.put(ROOT, root);
        return root;
    }

    private static void putUuid(CompoundTag tag, String key, UUID id) {
        if (id == null) tag.remove(key);
        else tag.putString(key, id.toString());
    }

    private static Optional<UUID> readUuid(CompoundTag tag, String key) {
        if (!tag.contains(key, Tag.TAG_STRING)) return Optional.empty();
        try {
            String raw = tag.getString(key);
            return raw.isBlank() ? Optional.empty() : Optional.of(UUID.fromString(raw));
        } catch (IllegalArgumentException ignored) {
            return Optional.empty();
        }
    }
}
