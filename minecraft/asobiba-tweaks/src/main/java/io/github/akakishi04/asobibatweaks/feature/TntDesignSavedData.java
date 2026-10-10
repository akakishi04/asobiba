package io.github.akakishi04.asobibatweaks.feature;

import java.util.HashMap;
import java.util.Map;
import net.minecraft.core.HolderLookup;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.ListTag;
import net.minecraft.nbt.Tag;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.util.datafix.DataFixTypes;
import net.minecraft.world.level.saveddata.SavedData;

public final class TntDesignSavedData extends SavedData {
    private static final String NAME = "asobibatweaks_tnt_designs";
    private static final Factory<TntDesignSavedData> FACTORY =
            new Factory<>(TntDesignSavedData::new, TntDesignSavedData::load, DataFixTypes.SAVED_DATA_RANDOM_SEQUENCES);

    private final Map<Long, TntDesign> designs = new HashMap<>();

    public static TntDesignSavedData get(ServerLevel level) {
        return level.getDataStorage().computeIfAbsent(FACTORY, NAME);
    }

    public TntDesign getOrCreate(long pos) {
        TntDesign design = designs.computeIfAbsent(pos, ignored -> new TntDesign());
        setDirty();
        return design;
    }

    public TntDesign remove(long pos) {
        TntDesign design = designs.remove(pos);
        if (design != null) setDirty();
        return design;
    }

    public void markDirty() {
        setDirty();
    }

    public static TntDesignSavedData load(CompoundTag tag, HolderLookup.Provider registries) {
        TntDesignSavedData data = new TntDesignSavedData();
        ListTag entries = tag.getList("entries", Tag.TAG_COMPOUND);
        for (int i = 0; i < entries.size(); i++) {
            CompoundTag row = entries.getCompound(i);
            TntDesign design = new TntDesign();
            design.power = row.getFloat("power");
            design.fuse = row.getInt("fuse");
            design.preserveBlocks = row.getBoolean("preserve_blocks");
            design.fire = row.getBoolean("fire");
            design.windMultiplier = row.contains("wind") ? row.getDouble("wind") : 1.0D;
            if (design.power <= 0.0F) design.power = 4.0F;
            if (design.fuse <= 0) design.fuse = 80;
            data.designs.put(row.getLong("pos"), design);
        }
        return data;
    }

    @Override
    public CompoundTag save(CompoundTag tag, HolderLookup.Provider registries) {
        ListTag entries = new ListTag();
        for (var entry : designs.entrySet()) {
            CompoundTag row = new CompoundTag();
            row.putLong("pos", entry.getKey());
            TntDesign design = entry.getValue();
            row.putFloat("power", design.power);
            row.putInt("fuse", design.fuse);
            row.putBoolean("preserve_blocks", design.preserveBlocks);
            row.putBoolean("fire", design.fire);
            row.putDouble("wind", design.windMultiplier);
            entries.add(row);
        }
        tag.put("entries", entries);
        return tag;
    }

    public static final class TntDesign {
        public float power = 4.0F;
        public int fuse = 80;
        public boolean preserveBlocks;
        public boolean fire;
        public double windMultiplier = 1.0D;
    }
}
