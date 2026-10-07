package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import java.util.HashSet;
import java.util.Set;
import java.util.UUID;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.entity.npc.Villager;
import net.minecraft.world.item.Items;
import net.neoforged.bus.api.SubscribeEvent;
import net.neoforged.neoforge.event.tick.EntityTickEvent;

/**
 * Persistent real-need/public-works planner.
 *
 * <p>Requests are not quests. They mirror real village deficits and active project
 * reservations, and close automatically when the underlying need disappears.</p>
 */
public final class VillagePublicWorksService {
    private static final long DAILY_TICKS = 24_000L;

    public VillagePublicWorksService() {
    }

    @SubscribeEvent
    public void onVillagerTick(EntityTickEvent.Post event) {
        if (!AsobibaTweaksConfig.VILLAGE_SIMULATION_ENABLED.getAsBoolean()
                || !AsobibaTweaksConfig.VILLAGE_PUBLIC_WORKS_ENABLED.getAsBoolean()
                || !(event.getEntity() instanceof Villager villager)
                || villager.level().isClientSide()
                || villager.tickCount % 200 != Math.floorMod(villager.getId(), 200)) {
            return;
        }

        ServerLevel level = (ServerLevel)villager.level();
        VillageIdentityBootstrap.ensure(villager, level);
        VillagerSimData.villageId(villager).ifPresent(villageId -> schedule(level, villageId));
    }

    public static void schedule(ServerLevel level, UUID villageId) {
        VillageSavedData data = VillageSavedData.get(level);
        VillageSavedData.VillageRecord village = data.village(villageId).orElse(null);
        if (village == null || "merged".equals(village.lifecycle()) || "abandoned".equals(village.lifecycle())) return;

        long now = level.getGameTime();
        if (now < village.nextPublicWorksUpdateGameTime()) return;
        village.setNextPublicWorksUpdateGameTime(now + DAILY_TICKS);
        data.touch();

        VillageSimulationScheduler.enqueuePlanning(
                level,
                "public_works:" + villageId,
                () -> refresh(level, villageId)
        );
    }

    public static void refresh(ServerLevel level, UUID villageId) {
        VillageSavedData data = VillageSavedData.get(level);
        VillageSavedData.VillageRecord village = data.village(villageId).orElse(null);
        if (village == null) return;

        VillageStorageService.reconcileVillage(villageId, level);
        int population = Math.max(1, Math.max(village.lastKnownPopulation(), village.residentIds().size()));
        long now = level.getGameTime();
        Set<String> activeKeys = new HashSet<>();

        addCategoryNeed(data, village, activeKeys, "food", "Food reserve",
                food(village), Math.max(24, population * 24), now);
        addCategoryNeed(data, village, activeKeys, "wood", "Construction wood",
                wood(village), Math.max(96, population * 16), now);
        addCategoryNeed(data, village, activeKeys, "stone", "Stone / construction",
                stone(village), Math.max(96, population * 16), now);
        addCategoryNeed(data, village, activeKeys, "metal", "Metal reserve",
                metal(village), Math.max(24, population * 4), now);
        addCategoryNeed(data, village, activeKeys, "farming", "Farm supplies",
                farming(village), Math.max(32, population * 4), now);
        addCategoryNeed(data, village, activeKeys, "fishing", "Fishing stock",
                fishing(village), Math.max(24, population * 3), now);

        if ("active".equals(village.fireEmergencyState())
                || "candidate".equals(village.fireEmergencyState())
                || "suspended".equals(village.fireEmergencyState())) {
            String key = "emergency:fire";
            activeKeys.add(key);
            int waterBuckets = village.ledgerCount(VillageStorageService.itemKey(Items.WATER_BUCKET));
            int desired = 3;
            data.upsertPublicRequest(
                    villageId,
                    key,
                    "emergency",
                    VillageStorageService.itemKey(Items.WATER_BUCKET),
                    desired,
                    Math.max(0, desired - waterBuckets),
                    "Fire emergency support",
                    village.fireCenter() == null ? "Village fire response"
                            : "Fire near " + village.fireCenter().toShortString(),
                    null,
                    now
            );
        }

        for (VillageSavedData.ProjectRecord project : data.activeProjectsForVillage(villageId)) {
            if ("complete".equals(project.phase()) || "cancelled".equals(project.phase())) continue;
            for (var reservation : project.reservations().entrySet()) {
                int required = Math.max(0, reservation.getValue());
                if (required <= 0) continue;

                int available = availableForReservation(village, reservation.getKey());
                int missing = Math.max(0, required - available);
                if (missing <= 0) continue;

                String key = "project:" + project.id() + ":" + reservation.getKey();
                activeKeys.add(key);
                String urgency = project.priority() >= 90 ? "emergency"
                        : project.priority() >= 70 ? "high" : "normal";
                String context = project.templateId().isBlank() ? project.type() : project.templateId();
                data.upsertPublicRequest(
                        villageId,
                        key,
                        urgency,
                        reservation.getKey(),
                        required,
                        missing,
                        project.pausedReason().isBlank() ? "Project material requirement" : project.pausedReason(),
                        context,
                        project.id(),
                        now
                );
            }
        }

        reprioritizeProjects(village, data);
        data.closeInactivePublicRequests(villageId, activeKeys, now);
        data.touch();
    }

    private static void addCategoryNeed(
            VillageSavedData data,
            VillageSavedData.VillageRecord village,
            Set<String> activeKeys,
            String category,
            String label,
            int stock,
            int target,
            long now) {
        int remaining = Math.max(0, target - stock);
        int permille = village.marketPermille(category);
        if (remaining <= 0 || permille <= 1000) return;

        String key = "stock:" + category;
        activeKeys.add(key);
        String urgency = permille >= 1600 ? "emergency" : permille >= 1350 ? "high" : "normal";
        data.upsertPublicRequest(
                village.id(),
                key,
                urgency,
                "category:" + category,
                target,
                remaining,
                label + " below target",
                "Village reserve",
                null,
                now
        );
    }

    private static void reprioritizeProjects(
            VillageSavedData.VillageRecord village,
            VillageSavedData data) {
        boolean fire = "active".equals(village.fireEmergencyState());
        for (VillageSavedData.ProjectRecord project : data.activeProjectsForVillage(village.id())) {
            int priority;
            if ("repair".equals(project.type()) || "fire_repair".equals(project.type())) {
                priority = fire ? 100 : 90;
            } else if ("building".equals(project.type())) {
                priority = village.settlementViability() < 40 ? 85 : 70;
            } else if ("road".equals(project.type())) {
                priority = village.settlementViability() < 40 ? 35 : 55;
            } else {
                priority = 40;
            }
            project.setPriority(priority);
        }
    }

    private static int availableForReservation(
            VillageSavedData.VillageRecord village,
            String key) {
        if ("tag:minecraft:planks".equals(key)) {
            return count(village,
                    Items.OAK_PLANKS, Items.SPRUCE_PLANKS, Items.BIRCH_PLANKS, Items.JUNGLE_PLANKS,
                    Items.ACACIA_PLANKS, Items.DARK_OAK_PLANKS, Items.MANGROVE_PLANKS, Items.CHERRY_PLANKS);
        }
        if ("tag:minecraft:wool".equals(key)) {
            return count(village,
                    Items.WHITE_WOOL, Items.ORANGE_WOOL, Items.MAGENTA_WOOL, Items.LIGHT_BLUE_WOOL,
                    Items.YELLOW_WOOL, Items.LIME_WOOL, Items.PINK_WOOL, Items.GRAY_WOOL,
                    Items.LIGHT_GRAY_WOOL, Items.CYAN_WOOL, Items.PURPLE_WOOL, Items.BLUE_WOOL,
                    Items.BROWN_WOOL, Items.GREEN_WOOL, Items.RED_WOOL, Items.BLACK_WOOL);
        }
        if (key == null || key.isBlank() || key.startsWith("category:") || key.startsWith("tag:")) return 0;

        var item = BuiltInRegistries.ITEM.get(net.minecraft.resources.ResourceLocation.tryParse(key));
        return item == null ? 0 : village.ledgerCount(VillageStorageService.itemKey(item));
    }

    private static int food(VillageSavedData.VillageRecord village) {
        return count(village, Items.BREAD, Items.CARROT, Items.POTATO, Items.BEETROOT, Items.WHEAT);
    }

    private static int wood(VillageSavedData.VillageRecord village) {
        return count(village,
                Items.OAK_LOG, Items.SPRUCE_LOG, Items.BIRCH_LOG, Items.JUNGLE_LOG,
                Items.ACACIA_LOG, Items.DARK_OAK_LOG, Items.MANGROVE_LOG, Items.CHERRY_LOG,
                Items.OAK_PLANKS, Items.SPRUCE_PLANKS, Items.BIRCH_PLANKS, Items.JUNGLE_PLANKS,
                Items.ACACIA_PLANKS, Items.DARK_OAK_PLANKS, Items.MANGROVE_PLANKS, Items.CHERRY_PLANKS);
    }

    private static int stone(VillageSavedData.VillageRecord village) {
        return count(village, Items.COBBLESTONE, Items.STONE, Items.ANDESITE,
                Items.DIORITE, Items.GRANITE, Items.STONE_BRICKS, Items.BRICKS);
    }

    private static int metal(VillageSavedData.VillageRecord village) {
        return count(village, Items.IRON_INGOT, Items.GOLD_INGOT, Items.COPPER_INGOT);
    }

    private static int farming(VillageSavedData.VillageRecord village) {
        return count(village, Items.WHEAT_SEEDS, Items.BEETROOT_SEEDS,
                Items.PUMPKIN_SEEDS, Items.MELON_SEEDS, Items.BONE_MEAL);
    }

    private static int fishing(VillageSavedData.VillageRecord village) {
        return count(village, Items.COD, Items.SALMON, Items.TROPICAL_FISH, Items.PUFFERFISH);
    }

    private static int count(VillageSavedData.VillageRecord village, net.minecraft.world.item.Item... items) {
        int total = 0;
        for (var item : items) total += village.ledgerCount(VillageStorageService.itemKey(item));
        return total;
    }
}
