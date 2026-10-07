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

        List<String> needs = buildNeeds(data, village);
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

    private static List<String> buildNeeds(
            VillageSavedData data,
            VillageSavedData.VillageRecord village) {
        return data.publicRequestsForVillage(village.id()).stream()
                .limit(5)
                .map(request -> {
                    String label = requestLabel(request.itemKey());
                    String amount = request.remainingCount() > 0
                            ? " " + request.remainingCount()
                            : "";
                    String text = urgencyLabel(request.urgency()) + " " + label + amount;
                    if (!request.reason().isBlank()) text += " - " + request.reason();
                    if (!request.context().isBlank()) text += " [" + request.context() + "]";
                    return text;
                })
                .toList();
    }

    private static String urgencyLabel(String urgency) {
        if ("emergency".equals(urgency)) return "Emergency:";
        if ("high".equals(urgency)) return "High:";
        return "Normal:";
    }

    private static String requestLabel(String itemKey) {
        if (itemKey == null || itemKey.isBlank()) return "Support";
        if (itemKey.startsWith("category:")) {
            String category = itemKey.substring("category:".length());
            return switch (category) {
                case "food" -> "Food";
                case "wood" -> "Wood";
                case "stone" -> "Stone";
                case "metal" -> "Metal";
                case "farming" -> "Farm supplies";
                case "fishing" -> "Fishing stock";
                default -> category;
            };
        }
        if ("tag:minecraft:planks".equals(itemKey)) return "Planks";
        if ("tag:minecraft:wool".equals(itemKey)) return "Wool";
        int colon = itemKey.indexOf(':');
        return colon >= 0 ? itemKey.substring(colon + 1).replace('_', ' ') : itemKey;
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

}
