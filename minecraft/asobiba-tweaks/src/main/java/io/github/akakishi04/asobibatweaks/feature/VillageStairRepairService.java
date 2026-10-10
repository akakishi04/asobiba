package io.github.akakishi04.asobibatweaks.feature;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.UUID;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.entity.npc.Villager;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.HorizontalDirectionalBlock;
import net.minecraft.world.level.block.state.BlockState;

/**
 * V86: physical, cursor-persistent staircase repair for original village-built
 * two-/three-storey houses. A loaded, genuinely empty tread can be replaced
 * using one real, correctly matching stair item. Player-reoriented or occupied
 * steps are not "missing", and never become overwrite targets.
 *
 * No new BuildingRecord, source item, or chunk ticket is ever fabricated.
 * Existing house expansion/construction projects take precedence.
 */
public final class VillageStairRepairService {
    public static final String TEMPLATE = "repair_village_stairs_v1";
    private static final String HOME = "stair_repair_home";
    private static final String OWNER = "stair_repair_original_project";
    private static final String PLANK = "stair_repair_plank";
    private static final String MISSING = "stair_repair_indices";
    private static final int WORK_SLOTS = 8;
    private static final int MAX_BUILDINGS = 24;
    private static final int MAX_MISSING = 3;

    private VillageStairRepairService() {}

    public static boolean tryPlan(Villager carpenter, ServerLevel level, UUID villageId) {
        VillageSavedData data = VillageSavedData.get(level);
        VillageSavedData.VillageRecord village = data.village(villageId).orElse(null);
        if (village == null || !"active".equals(village.lifecycle())) return false;
        for (VillageSavedData.BuildingRecord home : village.buildingIds().stream()
                .sorted(Comparator.comparing(UUID::toString))
                .limit(MAX_BUILDINGS)
                .map(data::building).flatMap(java.util.Optional::stream).toList()) {
            int floors = floors(home);
            if (floors < 2 || !home.villageBuilt()
                    || !"residential".equals(home.classification())
                    || !villageId.equals(home.villageId())
                    || home.min().distManhattan(carpenter.blockPosition()) > 64
                    || conflicting(data, villageId, home.id())
                    || !VillageSimulationScheduler.isAreaLoaded(
                            level, home.min(), home.max())) continue;

            VillageSavedData.ProjectRecord original = sourceProject(data, village, home);
            if (original == null) continue;
            String wood = timberName(original);
            if (wood.isBlank()) continue;
            List<Tread> treads = treads(home.min(), wood, floors);
            List<Integer> holes = new ArrayList<>();
            int intact = 0;
            boolean unknownOrAltered = false;
            for (int i = 0; i < treads.size(); i++) {
                Tread tread = treads.get(i);
                if (!VillageSimulationScheduler.tryConsumeBlockProbe(level)) {
                    unknownOrAltered = true;
                    break;
                }
                BlockState actual = level.getBlockState(tread.pos());
                if (actual.equals(tread.state())) {
                    intact++;
                } else if (actual.isAir() && level.getFluidState(tread.pos()).isEmpty()) {
                    holes.add(i);
                } else {
                    // Even the same StairBlock with a different facing/half
                    // is a deliberate player state; do not "correct" it.
                    unknownOrAltered = true;
                    break;
                }
            }
            if (unknownOrAltered || holes.isEmpty() || holes.size() > MAX_MISSING
                    || intact < treads.size() - MAX_MISSING) continue;

            Item item = treads.getFirst().state().getBlock().asItem();
            // Do not queue an unsupplied repair that never makes progress.
            // Existing stairs or ordinary timber can pay the vanilla recipe.
            if (VillageStorageService.count(carpenter, level, item) < holes.size()
                    && VillageStorageService.count(carpenter, level,
                            VillageBridgeService.plank(wood).asItem()) < 6
                    && VillagerSimData.workCargoCount(carpenter,
                            level.registryAccess(), WORK_SLOTS, item) < holes.size()) continue;

            VillageSavedData.ProjectRecord repair = data.createProject(
                    villageId, "building", 89, home.min());
            repair.setTemplateId(TEMPLATE);
            repair.setLeadCarpenterId(carpenter.getUUID());
            repair.setAnchor(home.min());
            repair.setParameter(HOME, home.id().toString());
            repair.setParameter(OWNER, original.id().toString());
            repair.setParameter(PLANK, wood);
            repair.setParameter(MISSING, holes.stream()
                    .map(String::valueOf).collect(java.util.stream.Collectors.joining(",")));
            repair.setWorkCursor(0);
            repair.setPhase("stair_repair");
            repair.setReservation(VillageStorageService.itemKey(item), holes.size());
            data.touch();
            return true;
        }
        return false;
    }

    static void advance(Villager carpenter, ServerLevel level,
                        VillageSavedData.ProjectRecord repair) {
        VillageSavedData data = VillageSavedData.get(level);
        UUID homeId = parseUuid(repair.parameter(HOME));
        UUID ownerId = parseUuid(repair.parameter(OWNER));
        VillageSavedData.BuildingRecord home = homeId == null
                ? null : data.building(homeId).orElse(null);
        VillageSavedData.ProjectRecord owner = ownerId == null
                ? null : data.project(ownerId).orElse(null);
        if (home == null || owner == null || !home.villageBuilt()
                || !home.villageId().equals(repair.villageId())
                || !repair.site().equals(home.min())
                || !isProvenance(home, owner)
                || !repair.parameter(PLANK).equals(timberName(owner))) {
            pause(data, repair, "original staircase identity no longer valid");
            return;
        }
        if (!VillageSimulationScheduler.isAreaLoaded(level, home.min(), home.max())) {
            pause(data, repair, "stairwell unloaded");
            return;
        }
        List<Tread> expected = treads(home.min(), repair.parameter(PLANK), floors(home));
        List<Integer> indices = parseIndices(repair.parameter(MISSING), expected.size());
        if (indices.isEmpty() || indices.size() > MAX_MISSING) {
            pause(data, repair, "invalid saved staircase repair targets");
            return;
        }
        if (repair.workCursor() >= indices.size()) {
            finish(level, data, repair, home);
            return;
        }

        Tread tread = expected.get(indices.get(repair.workCursor()));
        BlockPos pos = tread.pos();
        if (!VillageSimulationScheduler.isChunkLoaded(level, pos)) {
            pause(data, repair, "stair chunk unloaded");
            return;
        }
        BlockState current = level.getBlockState(pos);
        if (current.equals(tread.state())) {
            completeStep(level, data, repair, home, indices, false);
            return;
        }
        if (!current.isAir() || !level.getFluidState(pos).isEmpty()
                || !tread.state().canSurvive(level, pos)) {
            pause(data, repair, "stair position occupied or unsupported");
            return;
        }

        Block wood = VillageBridgeService.plank(repair.parameter(PLANK));
        Item material = tread.state().getBlock().asItem();
        // Acquire the actual item while still near recognized village stock,
        // BEFORE walking upstairs. Fetching only after arrival would make
        // upper-floor workers oscillate endlessly between storage and tread.
        if (VillagerSimData.workCargoCount(carpenter,
                level.registryAccess(), WORK_SLOTS, material) < 1
                && !VillageCarpenterCraftingService.ensureFixture(
                        carpenter, level, material, wood, WORK_SLOTS)) {
            pause(data, repair, "missing real matching stairs or crafting inputs");
            return;
        }
        if (carpenter.distanceToSqr(pos.getCenter()) > 7.0D * 7.0D) {
            carpenter.getNavigation().moveTo(
                    pos.getX() + 0.5D, pos.getY(), pos.getZ() + 0.5D, 0.75D);
            pause(data, repair, "carpenter carrying stairs to missing tread");
            return;
        }
        if (!VillagerSimData.takeWorkCargo(
                carpenter, level.registryAccess(), WORK_SLOTS, material, 1)) {
            pause(data, repair, "real stair item no longer in worker cargo");
            return;
        }
        if (!level.setBlock(pos, tread.state(), Block.UPDATE_ALL)) {
            ItemStack refund = VillagerSimData.insertWorkCargo(
                    carpenter, level.registryAccess(),
                    new ItemStack(material), WORK_SLOTS);
            if (!refund.isEmpty()) carpenter.spawnAtLocation(refund);
            pause(data, repair, "stair placement rejected; item refunded");
            return;
        }
        completeStep(level, data, repair, home, indices, true);
    }

    private static void completeStep(ServerLevel level, VillageSavedData data,
                                     VillageSavedData.ProjectRecord repair,
                                     VillageSavedData.BuildingRecord home,
                                     List<Integer> indices, boolean paid) {
        if (paid) {
            String key = VillageStorageService.itemKey(
                    VillageSimulationEvents.stairsForPlank(
                        VillageBridgeService.plank(repair.parameter(PLANK))).asItem());
            repair.setReservation(key, repair.reservations().getOrDefault(key, 0) - 1);
        }
        repair.setWorkCursor(repair.workCursor() + 1);
        repair.setPausedReason("");
        if (repair.workCursor() >= indices.size()) finish(level, data, repair, home);
        else {
            repair.setPhase("stair_repair");
            data.touch();
        }
    }

    private static void finish(ServerLevel level, VillageSavedData data,
                               VillageSavedData.ProjectRecord repair,
                               VillageSavedData.BuildingRecord home) {
        repair.clearReservations();
        repair.setPhase("complete");
        repair.setPausedReason("");
        data.touch();
        VillageSimulationScheduler.enqueueValidation(level,
                "repaired_stairs:" + home.id(),
                () -> VillageBuildingService.revalidateChunk(
                        level, new ChunkPos(home.min())));
    }

    private static List<Tread> treads(BlockPos base, String wood, int floors) {
        if (floors < 2 || floors > 3) return List.of();
        Block stairs = VillageSimulationEvents.stairsForPlank(
                VillageBridgeService.plank(wood));
        BlockState east = stairs.defaultBlockState()
                .setValue(HorizontalDirectionalBlock.FACING, Direction.EAST);
        BlockState south = stairs.defaultBlockState()
                .setValue(HorizontalDirectionalBlock.FACING, Direction.SOUTH);
        List<Tread> result = new ArrayList<>(4 * (floors - 1));
        for (int floor = 0; floor < floors - 1; floor++) {
            int y = 4 * floor;
            for (int x = 1; x <= 3; x++)
                result.add(new Tread(base.offset(x, y + x, 1), east));
            result.add(new Tread(base.offset(3, y + 4, 2), south));
        }
        return List.copyOf(result);
    }

    private static int floors(VillageSavedData.BuildingRecord home) {
        if ("house_2story_5x5".equals(home.templateId())
                && home.max().equals(home.min().offset(4, 8, 4))) return 2;
        if ("house_3story_5x5".equals(home.templateId())
                && home.max().equals(home.min().offset(4, 12, 4))) return 3;
        return 0;
    }

    private static VillageSavedData.ProjectRecord sourceProject(
            VillageSavedData data, VillageSavedData.VillageRecord village,
            VillageSavedData.BuildingRecord home) {
        for (UUID id : village.projectIds()) {
            VillageSavedData.ProjectRecord project = data.project(id).orElse(null);
            if (project != null && isProvenance(home, project)) return project;
        }
        return null;
    }

    private static boolean isProvenance(VillageSavedData.BuildingRecord home,
                                       VillageSavedData.ProjectRecord project) {
        if (!"building".equals(project.type())
                || !"complete".equals(project.phase())
                || !project.site().equals(home.min())) return false;
        if (project.templateId().equals(home.templateId()))
            return !Boolean.parseBoolean(project.parameter("outpost"));
        if (home.id().toString().equals(project.parameter("expand_building"))
                && VillageHouseVerticalExpansionService.TEMPLATE.equals(project.templateId())
                && floors(home) == 2) return true;
        return home.id().toString().equals(project.parameter("third_building"))
                && VillageHouseThirdFloorExpansionService.TEMPLATE.equals(project.templateId())
                && floors(home) == 3;
    }

    private static String timberName(VillageSavedData.ProjectRecord project) {
        return switch (project.templateId()) {
            case VillageHouseVerticalExpansionService.TEMPLATE -> project.parameter("expand_plank");
            case VillageHouseThirdFloorExpansionService.TEMPLATE -> project.parameter("third_plank");
            default -> project.parameter("plank");
        };
    }

    private static boolean conflicting(VillageSavedData data, UUID villageId, UUID homeId) {
        String house = homeId.toString();
        for (VillageSavedData.ProjectRecord project : data.activeProjectsForVillage(villageId)) {
            if (TEMPLATE.equals(project.templateId())
                    && house.equals(project.parameter(HOME))
                    || VillageBuildingRepairService.TEMPLATE.equals(project.templateId())
                    && house.equals(project.parameter("repair_building_id"))
                    || VillageHouseVerticalExpansionService.TEMPLATE.equals(project.templateId())
                    && house.equals(project.parameter("expand_building"))
                    || VillageHouseThirdFloorExpansionService.TEMPLATE.equals(project.templateId())
                    && house.equals(project.parameter("third_building"))) return true;
        }
        return false;
    }

    private static List<Integer> parseIndices(String text, int max) {
        if (text == null || text.isBlank() || max < 1) return List.of();
        String[] pieces = text.split(",", -1);
        if (pieces.length > MAX_MISSING) return List.of();
        int last = -1;
        List<Integer> values = new ArrayList<>();
        for (String piece : pieces) {
            try {
                int i = Integer.parseInt(piece);
                if (i < 0 || i >= max || i <= last) return List.of();
                values.add(i);
                last = i;
            } catch (NumberFormatException ex) {
                return List.of();
            }
        }
        return values;
    }

    private static UUID parseUuid(String value) {
        try { return UUID.fromString(value); }
        catch (IllegalArgumentException | NullPointerException ignored) { return null; }
    }

    private static void pause(VillageSavedData data,
                              VillageSavedData.ProjectRecord repair, String why) {
        repair.setPausedReason(why);
        data.touch();
    }

    private record Tread(BlockPos pos, BlockState state) {}
}
