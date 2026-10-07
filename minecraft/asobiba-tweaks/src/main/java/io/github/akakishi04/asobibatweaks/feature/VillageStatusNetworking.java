package io.github.akakishi04.asobibatweaks.feature;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.UUID;
import java.util.function.Consumer;
import net.minecraft.core.BlockPos;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.entity.npc.Villager;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.Items;
import net.minecraft.world.phys.AABB;
import net.neoforged.neoforge.network.PacketDistributor;
import net.neoforged.neoforge.network.event.RegisterPayloadHandlersEvent;

public final class VillageStatusNetworking {
    private static volatile Consumer<VillageStatusPayload> CLIENT_HANDLER = payload -> {};

    private VillageStatusNetworking() {
    }

    public static void registerPayloads(RegisterPayloadHandlersEvent event) {
        var registrar = event.registrar("1");
        registrar.playToClient(
                VillageStatusPayload.TYPE,
                VillageStatusPayload.STREAM_CODEC,
                (payload, context) -> CLIENT_HANDLER.accept(payload)
        );
        registrar.playToServer(
                VillageStatusRequestPayload.TYPE,
                VillageStatusRequestPayload.STREAM_CODEC,
                (payload, context) -> {
                    if (context.player() instanceof ServerPlayer player) {
                        sendStatus(player, payload.villageId());
                    }
                }
        );
    }

    public static void installClientHandler(Consumer<VillageStatusPayload> handler) {
        CLIENT_HANDLER = handler == null ? payload -> {} : handler;
    }

    public static void sendStatus(ServerPlayer player, UUID villageId) {
        if (!(player.level() instanceof ServerLevel level)) return;

        VillageSavedData data = VillageSavedData.get(level);
        VillageSavedData.VillageRecord village = data.village(villageId).orElse(null);
        if (village == null) return;

        if ("merged".equals(village.lifecycle()) && village.mergedIntoVillageId() != null) {
            village = data.village(village.mergedIntoVillageId()).orElse(null);
            if (village == null) return;
        }

        if (!canView(player, village)) return;
        PacketDistributor.sendToPlayer(player, buildSnapshot(level, data, village));
    }

    public static VillageStatusPayload buildSnapshot(
            ServerLevel level,
            VillageSavedData data,
            VillageSavedData.VillageRecord village) {
        int population = Math.max(village.lastKnownPopulation(), village.residentIds().size());
        int housing = housingCapacity(data, village);
        int food = foodCount(village);
        int foodDaysTenths = population <= 0 ? 0 : Math.max(0, (food * 10) / Math.max(1, population * 4));
        int averageWelfare = averageLoadedWelfare(level, village);

        int outposts = 0;
        for (VillageSavedData.WorkSiteRecord site : data.workSitesForVillage(village.id())) {
            if ("outpost".equals(site.type()) || "founding_site".equals(site.type())) outposts++;
        }

        List<String> needs = buildNeeds(village, population);
        List<String> projects = buildProjects(data, village);

        String title = "Village " + village.id().toString().substring(0, 8);
        return new VillageStatusPayload(
                village.id(),
                title,
                population,
                village.sustainablePopulation(),
                housing,
                Math.max(0, housing - population),
                foodDaysTenths,
                averageWelfare,
                village.settlementViability(),
                village.lifecycle(),
                village.fireEmergencyState(),
                Math.max(1, village.districtCenters().size()),
                outposts,
                needs,
                projects
        );
    }

    public static UUID nearestVisibleVillage(ServerLevel level, BlockPos pos, int maxDistance) {
        VillageSavedData data = VillageSavedData.get(level);
        VillageSavedData.VillageRecord best = null;
        int bestDistance = Integer.MAX_VALUE;

        for (VillageSavedData.VillageRecord village : data.villagesView().values()) {
            if ("merged".equals(village.lifecycle()) || "abandoned".equals(village.lifecycle())) continue;
            int distance = distanceToVillage(village, pos);
            if (distance <= maxDistance && distance < bestDistance) {
                best = village;
                bestDistance = distance;
            }
        }
        return best == null ? null : best.id();
    }

    private static boolean canView(ServerPlayer player, VillageSavedData.VillageRecord village) {
        return distanceToVillage(village, player.blockPosition()) <= 160;
    }

    private static int distanceToVillage(VillageSavedData.VillageRecord village, BlockPos pos) {
        int best = village.center().distManhattan(pos);
        for (Long packed : village.districtCenters()) {
            best = Math.min(best, BlockPos.of(packed).distManhattan(pos));
        }
        return best;
    }

    private static int housingCapacity(VillageSavedData data, VillageSavedData.VillageRecord village) {
        int total = 0;
        for (UUID id : village.buildingIds()) {
            VillageSavedData.BuildingRecord building = data.building(id).orElse(null);
            if (building != null
                    && "valid".equals(building.validationState())
                    && "residential".equals(building.classification())) {
                total += building.validatedCapacity();
            }
        }
        return total > 0 ? total : Math.max(village.lastKnownPopulation(), village.sustainablePopulation());
    }

    private static int foodCount(VillageSavedData.VillageRecord village) {
        return count(village, Items.BREAD, Items.CARROT, Items.POTATO, Items.BEETROOT, Items.WHEAT);
    }

    private static int averageLoadedWelfare(ServerLevel level, VillageSavedData.VillageRecord village) {
        List<Villager> loaded = level.getEntitiesOfClass(
                Villager.class,
                new AABB(village.center()).inflate(160.0D, 80.0D, 160.0D),
                villager -> villager.isAlive()
                        && VillagerSimData.villageId(villager).filter(village.id()::equals).isPresent()
        );
        if (loaded.isEmpty()) return 100;

        int total = 0;
        for (Villager villager : loaded) total += VillagerSimData.welfare(villager);
        return Math.max(0, Math.min(100, Math.round(total / (float)loaded.size())));
    }

    private static List<String> buildNeeds(VillageSavedData.VillageRecord village, int population) {
        List<NeedLine> lines = new ArrayList<>();
        addNeed(lines, village, "Food", "food",
                foodCount(village), Math.max(24, population * 24));
        addNeed(lines, village, "Wood", "wood",
                count(village,
                        Items.OAK_LOG, Items.SPRUCE_LOG, Items.BIRCH_LOG, Items.JUNGLE_LOG,
                        Items.ACACIA_LOG, Items.DARK_OAK_LOG, Items.MANGROVE_LOG, Items.CHERRY_LOG,
                        Items.OAK_PLANKS, Items.SPRUCE_PLANKS, Items.BIRCH_PLANKS, Items.JUNGLE_PLANKS,
                        Items.ACACIA_PLANKS, Items.DARK_OAK_PLANKS, Items.MANGROVE_PLANKS, Items.CHERRY_PLANKS),
                Math.max(96, population * 16));
        addNeed(lines, village, "Stone", "stone",
                count(village, Items.COBBLESTONE, Items.STONE, Items.ANDESITE, Items.DIORITE,
                        Items.GRANITE, Items.STONE_BRICKS, Items.BRICKS),
                Math.max(96, population * 16));
        addNeed(lines, village, "Metal", "metal",
                count(village, Items.IRON_INGOT, Items.GOLD_INGOT, Items.COPPER_INGOT),
                Math.max(24, population * 4));
        addNeed(lines, village, "Farm supplies", "farming",
                count(village, Items.WHEAT_SEEDS, Items.BEETROOT_SEEDS, Items.PUMPKIN_SEEDS,
                        Items.MELON_SEEDS, Items.BONE_MEAL),
                Math.max(32, population * 4));
        addNeed(lines, village, "Fish", "fishing",
                count(village, Items.COD, Items.SALMON, Items.TROPICAL_FISH, Items.PUFFERFISH),
                Math.max(24, population * 3));

        lines.sort(Comparator
                .comparingInt(NeedLine::permille).reversed()
                .thenComparing(NeedLine::label));

        return lines.stream()
                .limit(5)
                .map(line -> line.label + ": " + line.current + "/" + line.target
                        + " (" + urgency(line.permille) + ")")
                .toList();
    }

    private static void addNeed(List<NeedLine> lines, VillageSavedData.VillageRecord village,
                                String label, String category, int current, int target) {
        int permille = village.marketPermille(category);
        if (permille <= 1000 || current >= target) return;
        lines.add(new NeedLine(label, current, target, permille));
    }

    private static String urgency(int permille) {
        if (permille >= 1600) return "Emergency";
        if (permille >= 1350) return "High";
        return "Normal";
    }

    private static List<String> buildProjects(VillageSavedData data, VillageSavedData.VillageRecord village) {
        return data.activeProjectsForVillage(village.id()).stream()
                .limit(5)
                .map(project -> {
                    String name = project.templateId().isBlank() ? project.type() : project.templateId();
                    String text = name + " - " + project.phase();
                    if (!project.pausedReason().isBlank()) text += " - " + project.pausedReason();
                    return text;
                })
                .toList();
    }

    private static int count(VillageSavedData.VillageRecord village, Item... items) {
        int total = 0;
        for (Item item : items) total += village.ledgerCount(VillageStorageService.itemKey(item));
        return total;
    }

    private record NeedLine(String label, int current, int target, int permille) {
    }
}
