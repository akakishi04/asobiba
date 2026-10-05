package io.github.akakishi04.asobibatweaks.feature;

import java.util.HashMap;
import java.util.Map;
import net.minecraft.core.HolderLookup;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.ListTag;
import net.minecraft.nbt.Tag;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.util.datafix.DataFixTypes;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.saveddata.SavedData;

public final class FolkloreSavedData extends SavedData {
    private static final String NAME = "asobibatweaks_folklore";
    private static final Factory<FolkloreSavedData> FACTORY =
            new Factory<>(FolkloreSavedData::new, FolkloreSavedData::load, DataFixTypes.SAVED_DATA_RANDOM_SEQUENCES);

    private final Map<Long, LocationMemory> memories = new HashMap<>();

    public static FolkloreSavedData get(ServerLevel level) {
        return level.getDataStorage().computeIfAbsent(FACTORY, NAME);
    }

    public LocationMemory visit(ChunkPos chunk) {
        LocationMemory memory = memories.computeIfAbsent(chunk.toLong(), ignored -> new LocationMemory());
        memory.visits++;
        setDirty();
        return memory;
    }

    public LocationMemory memory(ChunkPos chunk) {
        return memories.computeIfAbsent(chunk.toLong(), ignored -> new LocationMemory());
    }

    public void ritual(ChunkPos chunk) {
        LocationMemory memory = memory(chunk);
        memory.rituals++;
        setDirty();
    }

    public static FolkloreSavedData load(CompoundTag tag, HolderLookup.Provider registries) {
        FolkloreSavedData data = new FolkloreSavedData();
        ListTag rows = tag.getList("locations", Tag.TAG_COMPOUND);
        for (int i = 0; i < rows.size(); i++) {
            CompoundTag row = rows.getCompound(i);
            LocationMemory memory = new LocationMemory();
            memory.visits = row.getInt("visits");
            memory.rituals = row.getInt("rituals");
            data.memories.put(row.getLong("chunk"), memory);
        }
        return data;
    }

    @Override
    public CompoundTag save(CompoundTag tag, HolderLookup.Provider registries) {
        ListTag rows = new ListTag();
        for (var entry : memories.entrySet()) {
            CompoundTag row = new CompoundTag();
            row.putLong("chunk", entry.getKey());
            row.putInt("visits", entry.getValue().visits);
            row.putInt("rituals", entry.getValue().rituals);
            rows.add(row);
        }
        tag.put("locations", rows);
        return tag;
    }

    public static final class LocationMemory {
        private int visits;
        private int rituals;

        public int visits() {
            return visits;
        }

        public int rituals() {
            return rituals;
        }

        public boolean familiar() {
            return visits >= 36;
        }

        public boolean ritualized() {
            return rituals >= 3;
        }
    }
}
