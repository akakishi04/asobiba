package io.github.akakishi04.asobibatweaks.feature;

import java.util.HashMap;
import java.util.UUID;
import net.minecraft.core.HolderLookup;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.ListTag;
import net.minecraft.nbt.Tag;
import net.minecraft.server.MinecraftServer;
import net.minecraft.world.level.saveddata.SavedData;
import net.minecraft.world.level.storage.LevelResource;
import net.neoforged.neoforge.common.IOUtilities;

/** One world-root ledger, shared by all dimensions and keyed by authenticated player UUID. */
public final class DailyPlayTimeSavedData extends SavedData {
    public static final String NAME = "asobibatweaks_daily_play_time_v1";
    private static final Factory<DailyPlayTimeSavedData> FACTORY =
            new Factory<>(DailyPlayTimeSavedData::new, DailyPlayTimeSavedData::load);
    private DailyPlayTimeLedger ledger = new DailyPlayTimeLedger();

    public static DailyPlayTimeSavedData get(MinecraftServer server) {
        return server.overworld().getDataStorage().computeIfAbsent(FACTORY, NAME);
    }

    public DailyPlayTimeLedger ledger() { return ledger; }

    /** Write only this ledger, not every unrelated SavedData entry. Healthy disk IO is assumed. */
    public void checkpoint(MinecraftServer server) {
        if (isDirty()) {
            save(server.getWorldPath(LevelResource.ROOT).resolve("data").resolve(NAME + ".dat").toFile(),
                    server.registryAccess());
        }
        IOUtilities.waitUntilIOWorkerComplete();
    }

    public static DailyPlayTimeSavedData load(CompoundTag tag, HolderLookup.Provider registries) {
        var result = new DailyPlayTimeSavedData();
        var accounts = new HashMap<UUID, DailyPlayTimeLedger.AccountState>();
        ListTag rows = tag.getList("players", Tag.TAG_COMPOUND);
        for (int i = 0; i < rows.size(); i++) {
            CompoundTag row = rows.getCompound(i);
            if (!row.hasUUID("uuid") || row.getLong("usedMillis") < 0) continue;
            int offset = row.getInt("offsetMinutes");
            if (offset < -840 || offset > 840) continue;
            var dates = new HashMap<Long, Long>();
            ListTag history = row.getList("playedDates", Tag.TAG_COMPOUND);
            for (int dateIndex = 0; dateIndex < history.size(); dateIndex++) {
                CompoundTag date = history.getCompound(dateIndex);
                long used = date.getLong("usedMillis");
                if (used > 0) dates.merge(date.getLong("day"), used, Math::max);
            }
            accounts.put(row.getUUID("uuid"), new DailyPlayTimeLedger.AccountState(
                    row.getLong("day"), row.getLong("usedMillis"), offset, row.getLong("playedDays"),
                    row.contains("prunedDateFence", Tag.TAG_LONG) ? row.getLong("prunedDateFence") : Long.MIN_VALUE, dates));
        }
        long highWater = tag.contains("wallHighWater", Tag.TAG_LONG)
                ? tag.getLong("wallHighWater") : Long.MIN_VALUE;
        result.ledger = DailyPlayTimeLedger.restore(new DailyPlayTimeLedger.SavedState(highWater, accounts));
        return result;
    }

    @Override
    public CompoundTag save(CompoundTag tag, HolderLookup.Provider registries) {
        DailyPlayTimeLedger.SavedState state = ledger.saveState();
        tag.putInt("version", 1);
        tag.putLong("wallHighWater", state.wallHighWater());
        ListTag rows = new ListTag();
        state.accounts().forEach((id, account) -> {
            CompoundTag row = new CompoundTag();
            row.putUUID("uuid", id);
            row.putLong("day", account.day());
            row.putLong("usedMillis", account.usedMillis());
            row.putInt("offsetMinutes", account.offsetMinutes());
            row.putLong("playedDays", account.playedDays());
            row.putLong("prunedDateFence", account.prunedDateFence());
            ListTag history = new ListTag();
            account.playedDates().entrySet().stream().sorted(java.util.Map.Entry.comparingByKey()).forEach(entry -> {
                CompoundTag date = new CompoundTag();
                date.putLong("day", entry.getKey());
                date.putLong("usedMillis", entry.getValue());
                history.add(date);
            });
            row.put("playedDates", history);
            rows.add(row);
        });
        tag.put("players", rows);
        return tag;
    }
}
