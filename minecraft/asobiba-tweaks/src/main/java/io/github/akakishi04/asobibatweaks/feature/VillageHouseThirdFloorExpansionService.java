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
import net.minecraft.world.item.Items;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.block.BedBlock;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.HorizontalDirectionalBlock;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.state.properties.BedPart;

/**
 * V89 second-to-third-floor extension for an ORIGINAL, village-owned 5x5 home.
 * The second-storey roof becomes a floor. Two matching planks form the stair
 * opening, and an existing second bedroom bed must be removed with actual
 * vanilla drops before its space is reused as the new stair flight.
 *
 * The project carries an exact blueprint, paid worker inventory, stable source
 * BuildingRecord identity and durable cursor. It pauses on unloaded or edited
 * space instead of replacing private blocks or inventing construction stock.
 */
public final class VillageHouseThirdFloorExpansionService {
    public static final String TEMPLATE = "house_expand_third_floor_v1";
    private static final String BUILDING = "third_building";
    private static final String SOURCE = "third_source";
    private static final String WOOD = "third_plank";
    private static final String PAID_BED = "third_paid_bed_cursor";
    private static final int WORK_SLOTS = 8;
    private static final int MAX_HOMES = 24;

    private VillageHouseThirdFloorExpansionService() {}

    public static boolean tryPlan(Villager carpenter, ServerLevel level, UUID villageId) {
        if (VillagerSimData.carpentrySkill(carpenter) < 75) return false;
        VillageSavedData data = VillageSavedData.get(level);
        VillageSavedData.VillageRecord village = data.village(villageId).orElse(null);
        if (village == null || !"active".equals(village.lifecycle())) return false;

        for (VillageSavedData.BuildingRecord home : village.buildingIds().stream()
                .sorted(Comparator.comparing(UUID::toString)).limit(MAX_HOMES)
                .map(data::building).flatMap(java.util.Optional::stream).toList()) {
            if (!home.villageBuilt() || !villageId.equals(home.villageId())
                    || !"residential".equals(home.classification())
                    || !"valid".equals(home.validationState())
                    || !"house_2story_5x5".equals(home.templateId())
                    || !home.max().equals(home.min().offset(4, 8, 4))
                    || home.validatedCapacity() < 2
                    || home.min().distManhattan(carpenter.blockPosition()) > 72
                    || conflicts(data, villageId, home.id())) continue;

            VillageSavedData.ProjectRecord source = village.projectIds().stream()
                    .map(data::project).flatMap(java.util.Optional::stream)
                    .filter(p -> p.site().equals(home.min())
                            && "complete".equals(p.phase())
                            && ("house_2story_5x5".equals(p.templateId())
                                && !Boolean.parseBoolean(p.parameter("outpost"))
                                || VillageHouseVerticalExpansionService.TEMPLATE.equals(
                                    p.templateId())
                                && home.id().toString().equals(p.parameter("expand_building"))))
                    .min(Comparator.comparing(p -> p.id().toString())).orElse(null);
            if (source == null) continue;
            String woodName = VillageHouseVerticalExpansionService.TEMPLATE.equals(
                    source.templateId()) ? source.parameter("expand_plank") : source.parameter("plank");
            if (woodName.isBlank()) continue;
            Block timber = VillageBridgeService.plank(woodName);
            if (!safeSecondStorey(level, home.min(), timber)
                    || VillageStorageService.count(carpenter, level, timber.asItem()) < 32)
                continue;

            VillageSavedData.ProjectRecord project = data.createProject(
                    villageId, "building", 87, home.min());
            project.setTemplateId(TEMPLATE);
            project.setParameter("circulation_version", "2");
            project.setParameter("third_source_circulation",
                    originalUpperBedPresent(level, home.min(), true) ? "2" : "1");
            project.setLeadCarpenterId(carpenter.getUUID());
            project.setAnchor(home.min());
            project.setParameter(BUILDING, home.id().toString());
            project.setParameter(SOURCE, source.id().toString());
            project.setParameter(WOOD, woodName);
            project.setPhase("third_shell");
            project.setWorkCursor(0);
            project.setReservation(VillageStorageService.itemKey(timber.asItem()), 71);
            project.setReservation(VillageStorageService.itemKey(
                    VillageSimulationEvents.stairsForPlank(timber).asItem()), 4);
            project.setReservation(VillageStorageService.itemKey(Items.WHITE_BED), 2);
            data.touch();
            return true;
        }
        return false;
    }

    private static boolean conflicts(VillageSavedData data, UUID villageId, UUID homeId) {
        for (VillageSavedData.ProjectRecord project : data.activeProjectsForVillage(villageId)) {
            String house = homeId.toString();
            if (TEMPLATE.equals(project.templateId())
                    && house.equals(project.parameter(BUILDING))
                    || VillageHouseVerticalExpansionService.TEMPLATE.equals(project.templateId())
                    && house.equals(project.parameter("expand_building"))
                    || VillageBuildingRepairService.TEMPLATE.equals(project.templateId())
                    && house.equals(project.parameter("repair_building_id"))
                    || VillageStairRepairService.TEMPLATE.equals(project.templateId())
                    && house.equals(project.parameter("stair_repair_home"))
                    || VillageHouseReuseService.TEMPLATE.equals(project.templateId())
                    && house.equals(project.parameter("reuse_building"))) return true;
        }
        return false;
    }

    static boolean safeSecondStorey(ServerLevel level, BlockPos base, Block timber) {
        if (base.getY() + 13 >= level.getMaxBuildHeight()
                || !VillageSimulationScheduler.isAreaLoaded(
                    level, base, base.offset(4, 13, 4))
                || !VillageBuildingService.connectedUpperStories(level, base, 1))
            return false;

        for (int x = 0; x < 5; x++) for (int z = 0; z < 5; z++) {
            if (!level.getBlockState(base.offset(x, 8, z)).is(timber)) return false;
            for (int y = 9; y <= 12; y++) {
                if (!level.getBlockState(base.offset(x, y, z)).isAir()) return false;
            }
        }
        if (!level.getBlockState(base.offset(2, 6, 1)).isAir()
                || !level.getBlockState(base.offset(3, 7, 1)).isAir()) return false;
        return (originalUpperBedPresent(level, base, false) || originalUpperBedPresent(level, base, true))
                && level.getBlockState(base.offset(1, 5, 2)).is(Blocks.WHITE_BED);
    }

    private static boolean originalUpperBedPresent(ServerLevel level, BlockPos base, boolean v2) {
        BlockState foot = bedFoot(v2 ? Direction.NORTH : Direction.WEST);
        BlockPos position = base.offset(v2 ? 1 : 2, 5, v2 ? 2 : 1);
        return level.getBlockState(position).equals(foot)
                && level.getBlockState(position.relative(foot.getValue(BedBlock.FACING)))
                    .equals(foot.setValue(BedBlock.PART, BedPart.HEAD));
    }

    static void advance(Villager carpenter, ServerLevel level,
                        VillageSavedData.ProjectRecord project) {
        VillageSavedData data = VillageSavedData.get(level);
        UUID houseId = parse(project.parameter(BUILDING));
        UUID sourceId = parse(project.parameter(SOURCE));
        VillageSavedData.BuildingRecord home = houseId == null
                ? null : data.building(houseId).orElse(null);
        VillageSavedData.ProjectRecord source = sourceId == null
                ? null : data.project(sourceId).orElse(null);
        if (home == null || source == null || !home.villageBuilt()
                || !project.villageId().equals(home.villageId())
                || !home.min().equals(project.site())
                || !source.site().equals(project.site())
                || !"complete".equals(source.phase())
                || !("house_2story_5x5".equals(source.templateId())
                     || VillageHouseVerticalExpansionService.TEMPLATE.equals(source.templateId()))) {
            pause(data, project, "third-floor source/ownership changed");
            return;
        }
        BlockPos base = project.site();
        if (!VillageSimulationScheduler.isAreaLoaded(level, base, base.offset(4, 13, 4))) {
            pause(data, project, "third-floor chunks unloaded");
            return;
        }
        List<Step> plan = steps(project);
        if (project.workCursor() >= plan.size()) {
            finish(carpenter, level, data, project, home);
            return;
        }

        Step step = plan.get(project.workCursor());
        if (completed(level, project, step)) {
            advanceCursor(data, project, step);
            return;
        }
        BlockState actual = level.getBlockState(step.pos());
        if (step.kind() == REMOVE_ROOF) {
            Block timber = VillageBridgeService.plank(project.parameter(WOOD));
            if (!actual.is(timber)) {
                pause(data, project, "third-floor stair opening player edited");
                return;
            }
        } else if (step.kind() == SALVAGE_BED) {
            if (!originalUpperBedPresent(level, base, "2".equals(project.parameter("third_source_circulation")))) {
                pause(data, project, "second bedroom changed; refuse demolition");
                return;
            }
        } else if (!actual.isAir()
                && !(step.kind() == PLACE_BED && actual.equals(step.state()))) {
            pause(data, project, "third-floor target occupied or rotated");
            return;
        }

        // A third floor is outside ground-level warehouse reach.
        // Load the actual finished piece into durable Carpenter cargo before
        // navigating upstairs; never ping-pong to an unreachable roof.
        if (step.kind() == PLACE_BED) {
            String cursor = Integer.toString(project.workCursor());
            if (!cursor.equals(project.parameter(PAID_BED))
                    && VillagerSimData.workCargoCount(carpenter,
                        level.registryAccess(), WORK_SLOTS, Items.WHITE_BED) < 1
                    && !VillageCarpenterCraftingService.ensureWhiteBed(
                        carpenter, level,
                        VillageBridgeService.plank(project.parameter(WOOD)), WORK_SLOTS)) {
                pause(data, project, "stage a real third-floor bed near warehouse");
                return;
            }
        } else if (step.kind() == PLACE) {
            Block wood = VillageBridgeService.plank(project.parameter(WOOD));
            if (VillagerSimData.workCargoCount(carpenter,
                    level.registryAccess(), WORK_SLOTS, step.material()) < 1) {
                boolean staged = VillageCarpenterCraftingService.isCraftedFixture(
                        step.material(), wood)
                    ? VillageCarpenterCraftingService.ensureFixture(
                        carpenter, level, step.material(), wood, WORK_SLOTS)
                    : VillageSimulationEvents.ensureCargoItem(
                        carpenter, level, step.material(), 1, WORK_SLOTS);
                if (!staged) {
                    pause(data, project, "stage real third-floor construction stock");
                    return;
                }
            }
        }

        if (carpenter.distanceToSqr(step.pos().getCenter()) > 8.0D * 8.0D) {
            VillageConstructionAccessService.approach(carpenter, level, project, step.pos());
            return;
        }

        if (step.kind() == REMOVE_ROOF) {
            if (!level.setBlock(step.pos(), Blocks.AIR.defaultBlockState(), Block.UPDATE_ALL)) {
                pause(data, project, "roof opening removal refused");
                return;
            }
            advanceCursor(data, project, step);
            return;
        }
        if (step.kind() == SALVAGE_BED) {
            // Vanilla physically drops the one existing bed as a real item.
            // Reentry sees the missing original foot, so no second item drops.
            if (!level.destroyBlock(step.pos(), true)) {
                pause(data, project, "bed salvage rejected");
                return;
            }
            if (!salvaged(level, project)) {
                pause(data, project, "bed partly removed; inspect before resuming");
                return;
            }
            advanceCursor(data, project, step);
            return;
        }
        if (step.kind() == PLACE_BED) {
            placeBed(carpenter, level, data, project, step);
            return;
        }

        Block plank = VillageBridgeService.plank(project.parameter(WOOD));
        boolean stocked = VillageCarpenterCraftingService.isCraftedFixture(step.material(), plank)
                ? VillageCarpenterCraftingService.ensureFixture(
                    carpenter, level, step.material(), plank, WORK_SLOTS)
                : VillageSimulationEvents.ensureCargoItem(
                    carpenter, level, step.material(), 1, WORK_SLOTS);
        if (!stocked) {
            pause(data, project, "third-floor material unavailable");
            return;
        }
        if (!VillagerSimData.takeWorkCargo(carpenter, level.registryAccess(),
                WORK_SLOTS, step.material(), 1)) return;
        if (!level.setBlock(step.pos(), step.state(), Block.UPDATE_ALL)) {
            ItemStack remainder = VillagerSimData.insertWorkCargo(
                    carpenter, level.registryAccess(),
                    new ItemStack(step.material()), WORK_SLOTS);
            if (!remainder.isEmpty()) carpenter.spawnAtLocation(remainder);
            pause(data, project, "third-floor rejected placement refunded");
            return;
        }
        advanceCursor(data, project, step);
    }

    private static void placeBed(Villager carpenter, ServerLevel level, VillageSavedData data,
                                 VillageSavedData.ProjectRecord project, Step step) {
        BlockPos head = step.pos().relative(step.state().getValue(BedBlock.FACING));
        BlockState expectedHead = step.state().setValue(BedBlock.PART, BedPart.HEAD);
        BlockState actualFoot = level.getBlockState(step.pos());
        BlockState actualHead = level.getBlockState(head);
        if (!actualFoot.isAir() && !actualFoot.equals(step.state())
                || !actualHead.isAir() && !actualHead.equals(expectedHead)) {
            pause(data, project, "third bedroom was modified");
            return;
        }
        String index = Integer.toString(project.workCursor());
        if (!index.equals(project.parameter(PAID_BED))) {
            if (!VillageCarpenterCraftingService.ensureWhiteBed(carpenter, level,
                    VillageBridgeService.plank(project.parameter(WOOD)), WORK_SLOTS)) {
                pause(data, project, "missing real third-story bed materials");
                return;
            }
            if (!VillagerSimData.takeWorkCargo(carpenter, level.registryAccess(),
                    WORK_SLOTS, Items.WHITE_BED, 1)) return;
            project.setParameter(PAID_BED, index);
            data.touch();
        }
        if (actualFoot.isAir())
            level.setBlock(step.pos(), step.state(), Block.UPDATE_CLIENTS);
        if (actualHead.isAir())
            level.setBlock(head, expectedHead, Block.UPDATE_CLIENTS);
        level.updateNeighborsAt(step.pos(), Blocks.WHITE_BED);
        level.updateNeighborsAt(head, Blocks.WHITE_BED);
        if (!completed(level, project, step)) {
            pause(data, project, "already-paid third bed incomplete");
            return;
        }
        project.setParameter(PAID_BED, "");
        advanceCursor(data, project, step);
    }

    private static void finish(Villager carpenter, ServerLevel level, VillageSavedData data,
                               VillageSavedData.ProjectRecord project,
                               VillageSavedData.BuildingRecord home) {
        if (!VillageHouseCirculationService.ensure(carpenter, level, project)) return;
        if (!VillageBuildingService.connectedUpperStories(level, project.site(), 2)) {
            pause(data, project, "third-story physical rooms not navigable");
            return;
        }
        if (!VillageConstructionAccessService.cleanup(carpenter, level, project)) return;
        if (!data.upgradeVillageHouseThirdFloor(home.id())) {
            pause(data, project, "original house bounds no longer convertible");
            return;
        }
        project.clearReservations();
        project.setPhase("complete");
        project.setPausedReason("");
        data.touch();
        VillageHousingPlanner.recordFinishedHouse(level, data, project.villageId());
        VillageSimulationScheduler.enqueueValidation(level,
                "third_floor:" + home.id(),
                () -> VillageBuildingService.revalidateChunk(
                    level, new ChunkPos(project.site())));
    }

    static boolean allComplete(ServerLevel level, VillageSavedData.ProjectRecord project) {
        List<Step> planned = steps(project);
        for (Step step : planned) {
            // A finished turning stair intentionally occupies the second roof
            // opening, replacing the temporarily excavated roof plank.
            if (step.kind() == REMOVE_ROOF
                    && step.pos().equals(project.site().offset(3, 8, 2))) continue;
            if (!completed(level, project, step)) return false;
        }
        return true;
    }

    static boolean completed(ServerLevel level,
                             VillageSavedData.ProjectRecord project, Step step) {
        if (!VillageSimulationScheduler.isChunkLoaded(level, step.pos())) return false;
        BlockState actual = level.getBlockState(step.pos());
        if (step.kind() == REMOVE_ROOF) {
            if (actual.isAir()) return true;
            if (step.pos().equals(project.site().offset(3, 8, 2))) {
                Block expected = VillageSimulationEvents.stairsForPlank(
                    VillageBridgeService.plank(project.parameter(WOOD)));
                return actual.is(expected)
                        && actual.getValue(HorizontalDirectionalBlock.FACING) == Direction.SOUTH;
            }
            return false;
        }
        if (step.kind() == SALVAGE_BED) return salvaged(level, project);
        if (!actual.equals(step.state())) return false;
        if (step.kind() != PLACE_BED) return true;
        BlockPos head = step.pos().relative(step.state().getValue(BedBlock.FACING));
        return VillageSimulationScheduler.isChunkLoaded(level, head)
                && level.getBlockState(head).equals(
                    step.state().setValue(BedBlock.PART, BedPart.HEAD));
    }

    private static boolean salvaged(ServerLevel level,
                                    VillageSavedData.ProjectRecord project) {
        BlockPos base = project.site();
        boolean sourceV2 = "2".equals(project.parameter("third_source_circulation"));
        BlockState foot = level.getBlockState(base.offset(sourceV2 ? 1 : 2, 5, sourceV2 ? 2 : 1));
        BlockState head = level.getBlockState(base.offset(1, 5, 1));
        Block expected = VillageSimulationEvents.stairsForPlank(
            VillageBridgeService.plank(project.parameter(WOOD)));
        return foot.isAir() && (head.isAir()
                || head.is(expected)
                && head.getValue(HorizontalDirectionalBlock.FACING) == Direction.EAST);
    }

    private static void advanceCursor(VillageSavedData data,
                                      VillageSavedData.ProjectRecord project, Step step) {
        project.setWorkCursor(project.workCursor() + 1);
        project.setPhase(step.kind() == PLACE_BED ? "interior"
                : step.kind() == REMOVE_ROOF || step.kind() == SALVAGE_BED
                        ? "stairwell" : "third_shell");
        project.setPausedReason("");
        if (step.material() != null) {
            String key = VillageStorageService.itemKey(step.material());
            project.setReservation(key, Math.max(0,
                project.reservations().getOrDefault(key, 0) - 1));
        }
        data.touch();
    }

    static List<Step> steps(VillageSavedData.ProjectRecord project) {
        BlockPos base = project.site();
        Block timber = VillageBridgeService.plank(project.parameter(WOOD));
        Item wood = timber.asItem();
        Block stairs = VillageSimulationEvents.stairsForPlank(timber);
        BlockState east = stairs.defaultBlockState()
                .setValue(HorizontalDirectionalBlock.FACING, Direction.EAST);
        BlockState south = stairs.defaultBlockState()
                .setValue(HorizontalDirectionalBlock.FACING, Direction.SOUTH);
        List<Step> result = new ArrayList<>();

        // Weatherproof the existing home before opening the old upper roof.
        for (int y = 9; y <= 11; y++) for (int x = 0; x < 5; x++)
            for (int z = 0; z < 5; z++) {
                boolean edge = x == 0 || x == 4 || z == 0 || z == 4;
                boolean window = y == 10 && (x == 0 || x == 4) && z == 2;
                if (edge && !window)
                    result.add(new Step(base.offset(x, y, z),
                        timber.defaultBlockState(), wood, PLACE));
            }
        for (int x = 0; x < 5; x++) for (int z = 0; z < 5; z++)
            result.add(new Step(base.offset(x, 12, z),
                timber.defaultBlockState(), wood, PLACE));

        // Physically deconstruct ONE obstructing, already-owned upper bed
        // before putting the next flight in its place. Vanilla supplies its
        // actual dropped White Bed item; no phantom inventory credit.
        boolean sourceV2 = "2".equals(project.parameter("third_source_circulation"));
        result.add(new Step(base.offset(sourceV2 ? 1 : 2, 5, sourceV2 ? 2 : 1),
                Blocks.AIR.defaultBlockState(), null, SALVAGE_BED));
        for (int x = 1; x <= 3; x++)
            result.add(new Step(base.offset(x, 4 + x, 1),
                east, stairs.asItem(), PLACE));
        result.add(new Step(base.offset(3, 8, 1),
                Blocks.AIR.defaultBlockState(), null, REMOVE_ROOF));
        result.add(new Step(base.offset(3, 8, 2),
                Blocks.AIR.defaultBlockState(), null, REMOVE_ROOF));
        result.add(new Step(base.offset(3, 8, 2),
                south, stairs.asItem(), PLACE));

        result.add(new Step(base.offset(1, 9, 2),
                bedFoot(Direction.SOUTH), Items.WHITE_BED, PLACE_BED));
        result.add(new Step(base.offset(2, 9, 1),
                bedFoot(Direction.WEST), Items.WHITE_BED, PLACE_BED));
        if ("2".equals(project.parameter("circulation_version"))) {
            result.removeIf(s -> s.kind() == PLACE_BED);
            result.add(new Step(base.offset(2, 8, 1), Blocks.AIR.defaultBlockState(), null, REMOVE_ROOF));
            result.add(new Step(base.offset(1, 9, 2), bedFoot(Direction.NORTH), Items.WHITE_BED, PLACE_BED));
            result.add(new Step(base.offset(2, 9, 3), bedFoot(Direction.WEST), Items.WHITE_BED, PLACE_BED));
        }
        return List.copyOf(result);
    }

    private static BlockState bedFoot(Direction facing) {
        return Blocks.WHITE_BED.defaultBlockState()
                .setValue(BedBlock.PART, BedPart.FOOT)
                .setValue(HorizontalDirectionalBlock.FACING, facing);
    }

    private static UUID parse(String input) {
        try { return UUID.fromString(input); }
        catch (IllegalArgumentException | NullPointerException ignored) { return null; }
    }

    private static void pause(VillageSavedData data,
                              VillageSavedData.ProjectRecord project, String why) {
        project.setPausedReason(why);
        data.touch();
    }

    static final int PLACE = 0;
    static final int REMOVE_ROOF = 1;
    static final int SALVAGE_BED = 2;
    static final int PLACE_BED = 3;
    static record Step(BlockPos pos, BlockState state, Item material, int kind) {}
}
