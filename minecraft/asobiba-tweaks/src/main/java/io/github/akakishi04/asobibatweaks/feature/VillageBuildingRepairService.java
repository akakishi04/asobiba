package io.github.akakishi04.asobibatweaks.feature;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import net.minecraft.core.BlockPos;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.tags.BlockTags;
import net.minecraft.world.entity.npc.Villager;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.BlockState;

/**
 * V86: selectively restores missing original village-owned shell blocks
 * from the completed durable construction blueprint.
 *
 * Never takes ownership of an adopted player house, never overwrites an
 * existing block or liquid, and never fabricates a material. A finite list of
 * original blueprint step indexes is stored in a new village ProjectRecord;
 * the normal Carpenter advances that project across reloads/replacements.
 */
public final class VillageBuildingRepairService {
    public static final String TEMPLATE = "repair_village_shell_v1";
    private static final String BUILDING_ID = "repair_building_id";
    private static final String SOURCE_PROJECT = "repair_source_project";
    private static final String STEP_INDICES = "repair_blueprint_indices";
    private static final int MAX_BUILDINGS_EXAMINED = 24;
    private static final int MAX_HOLES = 12;
    private static final int MAX_REPAIR_STEPS = 256;
    private static final int WORK_CARGO_SLOTS = 8;

    private VillageBuildingRepairService() {}

    /** Called only from the already bounded, low-frequency Carpenter planner. */
    public static boolean tryPlan(Villager carpenter, ServerLevel level, UUID villageId) {
        VillageSavedData data = VillageSavedData.get(level);
        VillageSavedData.VillageRecord village = data.village(villageId).orElse(null);
        if (village == null || !"active".equals(village.lifecycle())) return false;

        List<VillageSavedData.BuildingRecord> buildings = village.buildingIds().stream()
                .sorted(Comparator.comparing(UUID::toString))
                .limit(MAX_BUILDINGS_EXAMINED)
                .map(data::building).flatMap(java.util.Optional::stream)
                .filter(b -> b.villageBuilt()
                        && b.villageId().equals(villageId)
                        && ("residential".equals(b.classification())
                            || "storage".equals(b.classification())
                            || "workshop".equals(b.classification()))
                        && supportedTemplate(b.templateId()))
                .toList();

        for (VillageSavedData.BuildingRecord building : buildings) {
            if (building.min().distManhattan(carpenter.blockPosition()) > 64
                    || !VillageSimulationScheduler.isAreaLoaded(
                            level, building.min(), building.max())
                    || data.activeProjectsForVillage(villageId).stream()
                            .anyMatch(p -> TEMPLATE.equals(p.templateId())
                                    && building.id().toString().equals(
                                            p.parameter(BUILDING_ID)))) continue;

            VillageSavedData.ProjectRecord original = village.projectIds().stream()
                    .map(data::project).flatMap(java.util.Optional::stream)
                    .filter(p -> "building".equals(p.type())
                            && "complete".equals(p.phase())
                            && p.site().equals(building.min())
                            && p.templateId().equals(building.templateId()))
                    .min(Comparator.comparing(p -> p.id().toString()))
                    .orElse(null);
            if (original == null) continue;

            List<VillageSimulationEvents.BuildStep> blueprint =
                    VillageSimulationEvents.projectPlan(original);
            if (blueprint.isEmpty() || blueprint.size() > MAX_REPAIR_STEPS) continue;
            List<Integer> missing = new ArrayList<>();
            Map<Item, Integer> supplies = new HashMap<>();
            int intactShell = 0;
            boolean budgetAvailable = true;
            for (int index = 0; index < blueprint.size(); index++) {
                var step = blueprint.get(index);
                if (!structural(step)
                        || !within(step.pos(), building.min(), building.max())) continue;
                if (!VillageSimulationScheduler.tryConsumeBlockProbe(level)) {
                    budgetAvailable = false;
                    break;
                }
                BlockState current = level.getBlockState(step.pos());
                if (current.is(step.state().getBlock())) {
                    intactShell++;
                } else if (current.isAir()
                        && level.getFluidState(step.pos()).isEmpty()) {
                    missing.add(index);
                    supplies.merge(step.cost(), 1, Integer::sum);
                    if (missing.size() > MAX_HOLES) break;
                }
                // Different solid/placed blocks are deliberate external edits;
                // never overwrite them and never bill them for repair.
            }
            if (!budgetAvailable || intactShell < 20
                    || missing.isEmpty() || missing.size() > MAX_HOLES) continue;

            VillageSavedData.ProjectRecord repair = data.createProject(
                    villageId, "building", 85, building.min());
            repair.setTemplateId(TEMPLATE);
            repair.setLeadCarpenterId(carpenter.getUUID());
            repair.setAnchor(building.min());
            repair.setParameter(BUILDING_ID, building.id().toString());
            repair.setParameter(SOURCE_PROJECT, original.id().toString());
            repair.setParameter(STEP_INDICES, missing.stream()
                    .map(String::valueOf).collect(java.util.stream.Collectors.joining(",")));
            repair.setWorkCursor(0);
            repair.setPhase("repair");
            repair.setPausedReason("");
            for (Map.Entry<Item, Integer> item : supplies.entrySet()) {
                repair.setReservation(VillageStorageService.itemKey(item.getKey()),
                        item.getValue());
            }
            data.touch();
            return true;
        }
        return false;
    }

    /** One carefully checked, physically paid repair action per Carpenter step. */
    public static void advance(Villager carpenter, ServerLevel level,
                               VillageSavedData.ProjectRecord repair) {
        VillageSavedData data = VillageSavedData.get(level);
        UUID buildingId = parseUuid(repair.parameter(BUILDING_ID));
        UUID sourceId = parseUuid(repair.parameter(SOURCE_PROJECT));
        VillageSavedData.BuildingRecord building = buildingId == null
                ? null : data.building(buildingId).orElse(null);
        VillageSavedData.ProjectRecord original = sourceId == null
                ? null : data.project(sourceId).orElse(null);

        if (building == null || original == null || !building.villageBuilt()
                || !building.villageId().equals(repair.villageId())
                || !original.site().equals(building.min())
                || !original.templateId().equals(building.templateId())
                || !"complete".equals(original.phase())
                || !supportedTemplate(original.templateId())) {
            cancel(data, repair, "original village-owned blueprint missing");
            return;
        }
        if (!VillageSimulationScheduler.isAreaLoaded(level, building.min(), building.max())) {
            pause(data, repair, "repair building unloaded");
            return;
        }

        List<Integer> indices = parseIndices(repair.parameter(STEP_INDICES));
        List<VillageSimulationEvents.BuildStep> blueprint =
                VillageSimulationEvents.projectPlan(original);
        if (indices.isEmpty() || blueprint.size() > MAX_REPAIR_STEPS
                || indices.stream().anyMatch(i -> i < 0 || i >= blueprint.size()
                        || !structural(blueprint.get(i))
                        || !within(blueprint.get(i).pos(), building.min(), building.max()))) {
            cancel(data, repair, "invalid saved repair steps");
            return;
        }

        int cursor = repair.workCursor();
        if (cursor >= indices.size()) {
            finish(data, level, repair, building);
            return;
        }
        VillageSimulationEvents.BuildStep step = blueprint.get(indices.get(cursor));
        if (!VillageSimulationScheduler.isChunkLoaded(level, step.pos())) {
            pause(data, repair, "repair target chunk unloaded");
            return;
        }
        BlockState now = level.getBlockState(step.pos());
        if (!now.isAir()) {
            // Already fixed by a player or replaced with something else.
            // Either way, never pay and never overwrite a real block.
            completeStep(data, level, repair, building, indices, null);
            return;
        }
        if (!level.getFluidState(step.pos()).isEmpty()
                || !step.state().canSurvive(level, step.pos())) {
            pause(data, repair, "repair target no longer safe");
            return;
        }
        if (carpenter.distanceToSqr(step.pos().getCenter()) > 7.0D * 7.0D) {
            carpenter.getNavigation().moveTo(
                    step.pos().getX() + 0.5D, step.pos().getY(),
                    step.pos().getZ() + 0.5D, 0.75D);
            pause(data, repair, "carpenter travelling to repair");
            return;
        }
        Item material = step.cost();
        if (!VillageSimulationEvents.ensureCargoItem(
                carpenter, level, material, 1, WORK_CARGO_SLOTS)
                || !VillagerSimData.takeWorkCargo(carpenter, level.registryAccess(),
                        WORK_CARGO_SLOTS, material, 1)) {
            pause(data, repair, "missing real repair materials");
            return;
        }
        if (!level.setBlock(step.pos(), step.state(), Block.UPDATE_ALL)) {
            ItemStack remaining = VillagerSimData.insertWorkCargo(
                    carpenter, level.registryAccess(), new ItemStack(material),
                    WORK_CARGO_SLOTS);
            if (!remaining.isEmpty()) carpenter.spawnAtLocation(remaining);
            pause(data, repair, "repair placement rejected; refunded item");
            return;
        }
        completeStep(data, level, repair, building, indices, material);
    }

    private static void completeStep(VillageSavedData data, ServerLevel level,
                                     VillageSavedData.ProjectRecord repair,
                                     VillageSavedData.BuildingRecord building,
                                     List<Integer> indices, Item spent) {
        if (spent != null) {
            String key = VillageStorageService.itemKey(spent);
            repair.setReservation(key,
                    repair.reservations().getOrDefault(key, 0) - 1);
        }
        repair.setWorkCursor(repair.workCursor() + 1);
        repair.setPhase("repair");
        repair.setPausedReason("");
        data.touch();
        if (repair.workCursor() >= indices.size()) finish(data, level, repair, building);
    }

    private static void finish(VillageSavedData data, ServerLevel level,
                               VillageSavedData.ProjectRecord repair,
                               VillageSavedData.BuildingRecord building) {
        repair.clearReservations();
        repair.setPhase("complete");
        repair.setPausedReason("");
        data.touch();
        ChunkPos chunk = new ChunkPos(building.min());
        VillageSimulationScheduler.enqueueValidation(level,
                "repair_revalidate:" + building.id(),
                () -> VillageBuildingService.revalidateChunk(level, chunk));
    }

    private static boolean structural(VillageSimulationEvents.BuildStep step) {
        if (step.cost() == null) return false;
        BlockState state = step.state();
        return state.is(Blocks.COBBLESTONE) || state.is(BlockTags.PLANKS);
    }

    private static boolean supportedTemplate(String name) {
        return "house_5x5".equals(name)
                || "house_gabled_5x5".equals(name)
                || "house_2story_5x5".equals(name)
                || "house_3story_5x5".equals(name)
                || "storage_5x5".equals(name)
                || VillageCraftHallPlanner.TEMPLATE.equals(name);
    }

    private static boolean within(BlockPos pos, BlockPos min, BlockPos max) {
        return pos.getX() >= min.getX() && pos.getX() <= max.getX()
                && pos.getY() >= min.getY() && pos.getY() <= max.getY()
                && pos.getZ() >= min.getZ() && pos.getZ() <= max.getZ();
    }

    private static List<Integer> parseIndices(String text) {
        if (text == null || text.isBlank()) return List.of();
        String[] pieces = text.split(",", -1);
        if (pieces.length > MAX_HOLES) return List.of();
        List<Integer> result = new ArrayList<>();
        int last = -1;
        for (String piece : pieces) {
            try {
                int index = Integer.parseInt(piece);
                if (index <= last || index < 0 || index >= MAX_REPAIR_STEPS) return List.of();
                result.add(index);
                last = index;
            } catch (NumberFormatException ignored) {
                return List.of();
            }
        }
        return result;
    }

    private static UUID parseUuid(String text) {
        try {
            return UUID.fromString(text);
        } catch (IllegalArgumentException | NullPointerException ignored) {
            return null;
        }
    }

    private static void pause(VillageSavedData data,
                              VillageSavedData.ProjectRecord project, String reason) {
        project.setPausedReason(reason);
        data.touch();
    }

    private static void cancel(VillageSavedData data,
                               VillageSavedData.ProjectRecord project, String reason) {
        project.clearReservations();
        project.setPhase("cancelled");
        project.setPausedReason(reason);
        data.touch();
    }
}
