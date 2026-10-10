package io.github.akakishi04.asobibatweaks.feature;

import java.util.HashMap;
import java.util.Iterator;
import java.util.Map;
import net.minecraft.core.HolderLookup;
import net.minecraft.core.BlockPos;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.ListTag;
import net.minecraft.nbt.Tag;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.util.datafix.DataFixTypes;
import net.minecraft.world.level.saveddata.SavedData;

/** Loaded-only, persistent end-of-life/freshness of newly frozen ice. */
public final class MasteryFrostIceData extends SavedData {
    private static final String NAME = "asobibatweaks_mastery_frost_ice";
    private static final int MAX = 8192;
    private static final Factory<MasteryFrostIceData> FACTORY = new Factory<>(
            MasteryFrostIceData::new, MasteryFrostIceData::load,
            DataFixTypes.SAVED_DATA_RANDOM_SEQUENCES);

    private final Map<Long, Mark> marks = new HashMap<>();

    public static MasteryFrostIceData get(ServerLevel level) {
        return level.getDataStorage().computeIfAbsent(FACTORY, NAME);
    }

    public void track(ServerLevel level, BlockPos position, long protectedUntil,
                      long freshUntil) {
        if (marks.size() >= MAX) prune(level.getGameTime());
        if (marks.size() >= MAX && !marks.containsKey(position.asLong())) return;
        marks.put(position.asLong(), new Mark(protectedUntil, freshUntil));
        setDirty();
    }

    public boolean mustKeep(ServerLevel level, BlockPos pos) {
        Mark mark = marks.get(pos.asLong());
        if (mark == null) return false;
        if (level.getGameTime() < mark.protectedUntil()) return true;
        if (mark.freshUntil() < level.getGameTime()) {
            marks.remove(pos.asLong());
            setDirty();
        }
        return false;
    }

    public boolean recentlyCreated(ServerLevel level, BlockPos pos) {
        Mark mark = marks.get(pos.asLong());
        return mark != null && mark.freshUntil() >= level.getGameTime();
    }

    public void prune(long now) {
        boolean changed = false;
        for (Iterator<Map.Entry<Long, Mark>> it = marks.entrySet().iterator(); it.hasNext();) {
            Mark state = it.next().getValue();
            if (Math.max(state.protectedUntil(), state.freshUntil()) < now) {
                it.remove();
                changed = true;
            }
        }
        if (changed) setDirty();
    }

    public static MasteryFrostIceData load(CompoundTag tag, HolderLookup.Provider registries) {
        MasteryFrostIceData data = new MasteryFrostIceData();
        ListTag entries = tag.getList("entries", Tag.TAG_COMPOUND);
        for (int i = 0; i < entries.size() && i < MAX; i++) {
            CompoundTag record = entries.getCompound(i);
            data.marks.put(record.getLong("pos"),
                    new Mark(record.getLong("protected_until"), record.getLong("fresh_until")));
        }
        return data;
    }

    @Override
    public CompoundTag save(CompoundTag tag, HolderLookup.Provider registries) {
        ListTag entries = new ListTag();
        for (var entry : marks.entrySet()) {
            CompoundTag record = new CompoundTag();
            record.putLong("pos", entry.getKey());
            record.putLong("protected_until", entry.getValue().protectedUntil());
            record.putLong("fresh_until", entry.getValue().freshUntil());
            entries.add(record);
        }
        tag.put("entries", entries);
        return tag;
    }

    private record Mark(long protectedUntil, long freshUntil) {}
}
