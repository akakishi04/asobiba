package io.github.akakishi04.asobibatweaks.feature;

import java.util.HashMap;
import java.util.Map;
import java.util.UUID;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.core.registries.Registries;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.tags.ItemTags;
import net.minecraft.tags.TagKey;
import net.minecraft.world.item.ItemStack;

/** Read-only, bounded outstanding demand. Never writes bills into physical stock. */
final class VillageResourceReservations {
    static final int MAX_PROJECTS = 256;
    static final int MAX_ENTRIES = 2048;
    private VillageResourceReservations() {}

    static Snapshot capture(VillageSavedData data, VillageSavedData.VillageRecord village) {
        if (village.projectIds().size() > MAX_PROJECTS) return new Snapshot(false, Map.of());
        Map<String, Long> counts = new HashMap<>();
        int entries = village.reservedCounts().size();
        if (entries > MAX_ENTRIES) return new Snapshot(false, Map.of());
        village.reservedCounts().forEach((key, count) -> {
            if (count > 0) counts.merge(key, (long)count, Long::sum);
        });
        // Project bills are not mirrored into the legacy village reserve map.
        // Iterate indexed identities once; complete/cancelled bills are inert.
        for (UUID id : village.projectIds()) {
            var project = data.project(id).orElse(null);
            if (project == null || !project.villageId().equals(village.id()))
                return new Snapshot(false, Map.of());
            if ("complete".equals(project.phase()) || "cancelled".equals(project.phase())) continue;
            entries += project.reservations().size();
            if (entries > MAX_ENTRIES) return new Snapshot(false, Map.of());
            project.reservations().forEach((key, count) -> {
                if (count > 0) counts.merge(key, (long)count, Long::sum);
            });
        }
        return new Snapshot(true, Map.copyOf(counts));
    }

    static Snapshot legacy(VillageSavedData.VillageRecord village) {
        if (village.reservedCounts().size() > MAX_ENTRIES) return new Snapshot(false, Map.of());
        Map<String, Long> counts = new HashMap<>();
        village.reservedCounts().forEach((key, count) -> counts.put(key, (long)Math.max(0, count)));
        return new Snapshot(true, Map.copyOf(counts));
    }

    static String category(ItemStack stack) {
        String category = VillageEconomyService.category(stack.getItem());
        if (category != null) return category;
        if (stack.is(ItemTags.LOGS) || stack.is(ItemTags.PLANKS)) return "wood";
        if (stack.is(ItemTags.WOOL)) return "wool";
        return BuiltInRegistries.ITEM.getKey(stack.getItem()).toString();
    }

    private static String category(String key) {
        if (key.equals("tag:minecraft:planks") || key.equals("tag:minecraft:logs")) return "wood";
        if (key.equals("tag:minecraft:wool")) return "wool";
        ResourceLocation id = ResourceLocation.tryParse(key);
        return id != null && BuiltInRegistries.ITEM.containsKey(id)
                ? category(new ItemStack(BuiltInRegistries.ITEM.get(id))) : key;
    }

    record Snapshot(boolean complete, Map<String, Long> counts) {
        long categoryCount(String category) {
            if (!complete) return Long.MAX_VALUE;
            long total = 0;
            for (var entry : counts.entrySet())
                if (category.equals(VillageResourceReservations.category(entry.getKey()))) total += entry.getValue();
            return total;
        }
        long itemCount(ItemStack stack) {
            if (!complete) return Long.MAX_VALUE;
            String item = BuiltInRegistries.ITEM.getKey(stack.getItem()).toString();
            long total = 0;
            for (var entry : counts.entrySet()) {
                String key = entry.getKey();
                if (key.equals(item)) total += entry.getValue();
                else if (key.startsWith("tag:")) {
                    ResourceLocation tag = ResourceLocation.tryParse(key.substring(4));
                    if (tag != null && stack.is(TagKey.create(Registries.ITEM, tag))) total += entry.getValue();
                }
            }
            return total;
        }
        int freeCategory(String category, long physicalCount) {
            return complete ? (int)Math.max(0, Math.min(Integer.MAX_VALUE,
                    physicalCount - categoryCount(category))) : 0;
        }
    }
}
