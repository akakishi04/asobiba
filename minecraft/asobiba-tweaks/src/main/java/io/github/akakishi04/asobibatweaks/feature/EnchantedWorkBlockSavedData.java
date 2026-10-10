package io.github.akakishi04.asobibatweaks.feature;

import java.util.HashMap;
import java.util.Map;
import net.minecraft.core.HolderLookup;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.nbt.ListTag;
import net.minecraft.nbt.Tag;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.util.datafix.DataFixTypes;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.level.saveddata.SavedData;

public final class EnchantedWorkBlockSavedData extends SavedData {
    private static final String NAME = "asobibatweaks_enchanted_work_blocks";
    private static final Factory<EnchantedWorkBlockSavedData> FACTORY =
            new Factory<>(EnchantedWorkBlockSavedData::new, EnchantedWorkBlockSavedData::load,
                    DataFixTypes.SAVED_DATA_RANDOM_SEQUENCES);

    private final Map<Long, ItemStack> stacks = new HashMap<>();

    public static EnchantedWorkBlockSavedData get(ServerLevel level) {
        return level.getDataStorage().computeIfAbsent(FACTORY, NAME);
    }

    public void put(long pos, ItemStack stack) {
        stacks.put(pos, stack.copyWithCount(1));
        setDirty();
    }

    public ItemStack remove(long pos) {
        ItemStack stack = stacks.remove(pos);
        if (stack != null) setDirty();
        return stack == null ? ItemStack.EMPTY : stack;
    }

    public ItemStack peek(long pos) {
        ItemStack stack = stacks.get(pos);
        return stack == null ? ItemStack.EMPTY : stack;
    }

    public static EnchantedWorkBlockSavedData load(CompoundTag tag, HolderLookup.Provider registries) {
        EnchantedWorkBlockSavedData data = new EnchantedWorkBlockSavedData();
        ListTag entries = tag.getList("entries", Tag.TAG_COMPOUND);
        for (int i = 0; i < entries.size(); i++) {
            CompoundTag row = entries.getCompound(i);
            ItemStack stack = ItemStack.parseOptional(registries, row.getCompound("stack"));
            if (!stack.isEmpty()) {
                data.stacks.put(row.getLong("pos"), stack.copyWithCount(1));
            }
        }
        return data;
    }

    @Override
    public CompoundTag save(CompoundTag tag, HolderLookup.Provider registries) {
        ListTag entries = new ListTag();
        for (var entry : stacks.entrySet()) {
            Tag encoded = entry.getValue().saveOptional(registries);
            if (!(encoded instanceof CompoundTag stackTag) || stackTag.isEmpty()) continue;

            CompoundTag row = new CompoundTag();
            row.putLong("pos", entry.getKey());
            row.put("stack", stackTag);
            entries.add(row);
        }
        tag.put("entries", entries);
        return tag;
    }
}
