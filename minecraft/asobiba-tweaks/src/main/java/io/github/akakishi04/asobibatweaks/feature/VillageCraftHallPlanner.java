package io.github.akakishi04.asobibatweaks.feature;

import java.util.UUID;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.entity.ai.memory.MemoryModuleType;
import net.minecraft.world.entity.npc.Villager;
import net.minecraft.world.entity.npc.VillagerProfession;
import net.minecraft.world.item.Items;
import net.minecraft.world.phys.AABB;

/**
 * Low-frequency functional building demand, separate from block placement.
 *
 * Adds workshops only for resident smithing/stoneworking professions and only
 * when real village storage can supply their workstation items or the exact
 * raw ingredients. Housing and ordinary storage always take precedence.
 */
public final class VillageCraftHallPlanner {
    public static final String TEMPLATE = "craft_hall_5x5";

    private VillageCraftHallPlanner() {}

    public static boolean needsHall(
            Villager carpenter, ServerLevel level, VillageSavedData data, UUID villageId) {
        VillageSavedData.VillageRecord village = data.village(villageId).orElse(null);
        if (village == null || !"active".equals(village.lifecycle())) return false;

        // Avoid world-wide resident searches or decisions based on unobserved
        // villagers. This is a modest local public-works need, not a demand
        // inferred from unloaded or forgotten population.
        int workersMissingSites = level.getEntitiesOfClass(Villager.class,
                VillageActivityBoundary.searchBounds(village),
                v -> v.isAlive() && VillageActivityBoundary.contains(village, v.blockPosition()) && !v.isBaby()
                        && VillagerSimData.villageId(v).filter(villageId::equals).isPresent()
                        && !v.getBrain().hasMemoryValue(MemoryModuleType.JOB_SITE)
                        && (v.getVillagerData().getProfession() == VillagerProfession.TOOLSMITH
                            || v.getVillagerData().getProfession() == VillagerProfession.MASON)
        ).size();
        if (workersMissingSites == 0) return false;

        int target = Math.min(3, (workersMissingSites + 1) / 2);
        long built = village.buildingIds().stream()
                .map(data::building)
                .filter(java.util.Optional::isPresent)
                .map(java.util.Optional::get)
                .filter(b -> TEMPLATE.equals(b.templateId())
                        && "valid".equals(b.validationState()))
                .count();
        long planned = data.activeProjectsForVillage(villageId).stream()
                .filter(p -> TEMPLATE.equals(p.templateId())).count();
        if (built + planned >= target) return false;

        // Finished blocks are preferred. Crafting the missing pieces consumes
        // real iron, stone and biome-selected planks through Carpenter cargo.
        int smithingStock = village.ledgerCount(
                VillageStorageService.itemKey(Items.SMITHING_TABLE));
        int stonecutterStock = village.ledgerCount(
                VillageStorageService.itemKey(Items.STONECUTTER));
        int missingIron = (smithingStock > 0 ? 0 : 2)
                + (stonecutterStock > 0 ? 0 : 1);
        int missingStone = stonecutterStock > 0 ? 0 : 3;
        int missingPlanks = smithingStock > 0 ? 0 : 4;

        int availablePlanks = VillageStorageService.count(carpenter, level,
                Items.OAK_PLANKS, Items.SPRUCE_PLANKS, Items.BIRCH_PLANKS,
                Items.JUNGLE_PLANKS, Items.ACACIA_PLANKS, Items.DARK_OAK_PLANKS,
                Items.MANGROVE_PLANKS, Items.CHERRY_PLANKS);
        return VillageStorageService.count(carpenter, level, Items.IRON_INGOT) >= missingIron
                && VillageStorageService.count(carpenter, level, Items.STONE) >= missingStone
                && availablePlanks >= missingPlanks;
    }
}
