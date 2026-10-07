package io.github.akakishi04.asobibatweaks.feature;

import java.util.Optional;
import java.util.UUID;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.Tag;
import net.minecraft.util.Mth;
import net.minecraft.world.entity.npc.Villager;

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

    private VillagerSimData() {
    }

    public static void ensureInitialized(Villager villager) {
        CompoundTag root = root(villager, true);
        if (!root.contains(SCHEMA, Tag.TAG_INT)) root.putInt(SCHEMA, SCHEMA_VERSION);
        if (!root.contains(DUTY, Tag.TAG_STRING)) root.putString(DUTY, "none");
        if (!root.contains(WELFARE, Tag.TAG_INT)) root.putInt(WELFARE, 100);
        if (!root.contains(CARPENTRY_SKILL, Tag.TAG_INT)) root.putInt(CARPENTRY_SKILL, 0);
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
