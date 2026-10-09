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
 * V89: a bounded, durable in-place expansion of an ORIGINAL village-built
 * one-storey 5x5 house. Never targets an adopted or player-owned building.
 *
 * The existing 25-plank roof becomes the upper floor. Only the two genuine
 * roof planks needed for the stairwell are removed; these are demolition
 * losses, not free construction inventory. New walls, roof, stairs and beds
 * are all paid from real Carpenter cargo or recognized village storage.
 *
 * The original BuildingRecord ID is retained and its bounds are enlarged
 * only after the entire physical upper storey and staircase are verified.
 * Unloaded chunks or player-edited blocks pause without overwriting them.
 */
public final class VillageHouseVerticalExpansionService {
    public static final String TEMPLATE = "house_expand_second_floor_v1";
    private static final String BUILDING = "expand_building";
    private static final String ORIGINAL = "expand_original";
    private static final String WOOD = "expand_plank";
    private static final String PAID_BED_CURSOR = "expand_paid_bed_cursor";
    private static final int CARGO_SLOTS = 8;
    private static final int MAX_HOMES = 24;

    private VillageHouseVerticalExpansionService() {}

    public static boolean tryPlan(Villager carpenter, ServerLevel level, UUID villageId) {
        if (VillagerSimData.carpentrySkill(carpenter) < 50) return false;
        VillageSavedData data = VillageSavedData.get(level);
        VillageSavedData.VillageRecord village = data.village(villageId).orElse(null);
        if (village == null || !"active".equals(village.lifecycle())) return false;

        for (VillageSavedData.BuildingRecord home : village.buildingIds().stream()
                .sorted(Comparator.comparing(UUID::toString))
                .limit(MAX_HOMES)
                .map(data::building).flatMap(java.util.Optional::stream).toList()) {
            if (!home.villageBuilt() || !villageId.equals(home.villageId())
                    || !"house_5x5".equals(home.templateId())
                    || !"residential".equals(home.classification())
                    || !"valid".equals(home.validationState())
                    || home.validatedCapacity() < 1
                    || home.validatedCapacity() > 2
                    || home.min().distManhattan(carpenter.blockPosition()) > 72
                    || !isOriginalOneStory(home)
                    || data.activeProjectsForVillage(villageId).stream().anyMatch(p ->
                        TEMPLATE.equals(p.templateId())
                            && home.id().toString().equals(p.parameter(BUILDING)))) continue;

            VillageSavedData.ProjectRecord original = village.projectIds().stream()
                    .map(data::project).flatMap(java.util.Optional::stream)
                    .filter(p -> "building".equals(p.type())
                            && "house_5x5".equals(p.templateId())
                            && "complete".equals(p.phase())
                            && !Boolean.parseBoolean(p.parameter("outpost"))
                            && home.min().equals(p.site())).findFirst().orElse(null);
            if (original == null) continue;
            Block plank = VillageBridgeService.plank(original.parameter("plank"));
            if (!safeInitialShell(level, home.min(), plank)) continue;
            // A real starting stock prevents speculative projects from tearing
            // into a shortage-stricken village. Later missing items pause safely.
            if (VillageStorageService.count(carpenter, level, plank.asItem()) < 32) continue;

            VillageSavedData.ProjectRecord project = data.createProject(
                    villageId, "building", 86, home.min());
            project.setTemplateId(TEMPLATE);
            project.setAnchor(home.min());
            project.setLeadCarpenterId(carpenter.getUUID());
            project.setParameter(BUILDING, home.id().toString());
            project.setParameter(ORIGINAL, original.id().toString());
            project.setParameter(WOOD, original.parameter("plank"));
            project.setPhase("upper_shell");
            project.setWorkCursor(0);
            project.setReservation(VillageStorageService.itemKey(plank.asItem()), 75);
            project.setReservation(VillageStorageService.itemKey(
                    VillageSimulationEvents.stairsForPlank(plank).asItem()), 4);
            project.setReservation(VillageStorageService.itemKey(Items.WHITE_BED), 2);
            data.touch();
            return true;
        }
        return false;
    }

    static boolean safeInitialShell(ServerLevel level, BlockPos base, Block plank) {
        if (base.getY() + 9 >= level.getMaxBuildHeight()
                || !VillageSimulationScheduler.isAreaLoaded(level,
                        base, base.offset(4, 9, 4))) return false;
        for (int x = 0; x < 5; x++) for (int z = 0; z < 5; z++) {
            if (!level.getBlockState(base.offset(x, 4, z)).is(plank)) return false;
            for (int y = 5; y <= 8; y++) {
                if (!level.getBlockState(base.offset(x, y, z)).isAir()) return false;
            }
        }
        for (int x = 1; x <= 3; x++) {
            if (!level.getBlockState(base.offset(x, x, 1)).isAir()) return false;
        }
        return level.getBlockState(base.offset(2, 1, 2)).is(Blocks.WHITE_BED)
                && level.getBlockState(base.offset(2, 1, 3)).is(Blocks.WHITE_BED)
                && level.getBlockState(base.offset(2, 1, 0)).isAir();
    }

    static void advance(Villager carpenter, ServerLevel level,
                        VillageSavedData.ProjectRecord project) {
        VillageSavedData data = VillageSavedData.get(level);
        UUID homeId = parse(project.parameter(BUILDING));
        UUID originalId = parse(project.parameter(ORIGINAL));
        VillageSavedData.BuildingRecord home = homeId == null
                ? null : data.building(homeId).orElse(null);
        VillageSavedData.ProjectRecord original = originalId == null
                ? null : data.project(originalId).orElse(null);
        if (home == null || original == null || !home.villageBuilt()
                || !home.villageId().equals(project.villageId())
                || !home.min().equals(project.site())
                || !"house_5x5".equals(original.templateId())
                || !"complete".equals(original.phase())
                || !original.site().equals(project.site())) {
            pause(data, project, "original village house no longer valid");
            return;
        }
        BlockPos base = home.min();
        if (!VillageSimulationScheduler.isAreaLoaded(level, base, base.offset(4, 9, 4))) {
            pause(data, project, "upper construction chunks unloaded");
            return;
        }

        List<Step> steps = steps(project);
        if (project.workCursor() >= steps.size()) {
            finish(level, data, project, home);
            return;
        }
        Step step = steps.get(project.workCursor());
        BlockState actual = level.getBlockState(step.pos());
        if (completed(level, step)) {
            advanceCursor(data, project, step);
            return;
        }
        if (step.remove()) {
            Block expectedRoof = VillageBridgeService.plank(project.parameter(WOOD));
            if (!actual.is(expectedRoof)) {
                pause(data, project, "original roof opening player-edited");
                return;
            }
        } else if (!actual.isAir()
                && !(step.bed() && actual.equals(step.state()))) {
            // Existing physical blocks with different facing/components are
            // never replaced merely because the block type happens to match.
            pause(data, project, "upper-building target player occupied");
            return;
        }

        if (carpenter.distanceToSqr(step.pos().getCenter()) > 8.0D * 8.0D) {
            carpenter.getNavigation().moveTo(
                    step.pos().getX() + 0.5D,
                    step.pos().getY(), step.pos().getZ() + 0.5D, 0.75D);
            pause(data, project, "carpenter travelling to expansion work");
            return;
        }
        if (step.remove()) {
            if (!level.setBlock(step.pos(), Blocks.AIR.defaultBlockState(), Block.UPDATE_ALL)) {
                pause(data, project, "original roof opening refused");
                return;
            }
            advanceCursor(data, project, step);
            return;
        }
        if (step.bed()) {
            placeRealBed(carpenter, level, data, project, step);
            return;
        }

        Block plank = VillageBridgeService.plank(project.parameter(WOOD));
        boolean crafted = VillageCarpenterCraftingService.isCraftedFixture(step.material(), plank);
        boolean ready = crafted
                ? VillageCarpenterCraftingService.ensureFixture(
                        carpenter, level, step.material(), plank, CARGO_SLOTS)
                : VillageSimulationEvents.ensureCargoItem(
                        carpenter, level, step.material(), 1, CARGO_SLOTS);
        if (!ready) {
            pause(data, project, "missing physically supplied expansion material");
            return;
        }
        if (!VillagerSimData.takeWorkCargo(carpenter, level.registryAccess(),
                CARGO_SLOTS, step.material(), 1)) {
            pause(data, project, "expansion material not in worker cargo");
            return;
        }
        if (!level.setBlock(step.pos(), step.state(), Block.UPDATE_ALL)) {
            ItemStack extra = VillagerSimData.insertWorkCargo(
                    carpenter, level.registryAccess(),
                    new ItemStack(step.material()), CARGO_SLOTS);
            if (!extra.isEmpty()) carpenter.spawnAtLocation(extra);
            pause(data, project, "expansion placement rejected; real material refunded");
            return;
        }
        advanceCursor(data, project, step);
    }

    private static void placeRealBed(Villager carpenter, ServerLevel level,
                                     VillageSavedData data,
                                     VillageSavedData.ProjectRecord project, Step step) {
        BlockPos head = step.pos().relative(step.state().getValue(BedBlock.FACING));
        BlockState headState = step.state().setValue(BedBlock.PART, BedPart.HEAD);
        BlockState footBefore = level.getBlockState(step.pos());
        BlockState headBefore = level.getBlockState(head);
        if ((!footBefore.isAir() && !footBefore.equals(step.state()))
                || (!headBefore.isAir() && !headBefore.equals(headState))) {
            pause(data, project, "upper bed slot occupied or modified");
            return;
        }
        String index = Integer.toString(project.workCursor());
        boolean alreadyPaid = index.equals(project.parameter(PAID_BED_CURSOR));
        if (!alreadyPaid) {
            Block timber = VillageBridgeService.plank(project.parameter(WOOD));
            if (!VillageCarpenterCraftingService.ensureWhiteBed(
                    carpenter, level, timber, CARGO_SLOTS)) {
                pause(data, project, "missing physical bed or exact wool/planks");
                return;
            }
            if (!VillagerSimData.takeWorkCargo(carpenter,
                    level.registryAccess(), CARGO_SLOTS, Items.WHITE_BED, 1)) return;
            // An acknowledged paid partial bed may be retried after a normal
            // save/reload without deducting a second finished Bed.
            project.setParameter(PAID_BED_CURSOR, index);
            data.touch();
        }
        if (footBefore.isAir())
            level.setBlock(step.pos(), step.state(), Block.UPDATE_CLIENTS);
        if (headBefore.isAir())
            level.setBlock(head, headState, Block.UPDATE_CLIENTS);
        level.updateNeighborsAt(step.pos(), Blocks.WHITE_BED);
        level.updateNeighborsAt(head, Blocks.WHITE_BED);
        if (!completed(level, step)) {
            pause(data, project, "paid bed placement incomplete");
            return;
        }
        project.setParameter(PAID_BED_CURSOR, "");
        advanceCursor(data, project, step);
    }

    private static void finish(ServerLevel level, VillageSavedData data,
                               VillageSavedData.ProjectRecord project,
                               VillageSavedData.BuildingRecord home) {
        BlockPos base = home.min();
        if (!allComplete(level, project)
                || !VillageBuildingService.connectedUpperStories(level, base, 1)) {
            pause(data, project, "finished two-storey geometry not navigable");
            return;
        }
        if (!data.upgradeVillageHouseSecondFloor(home.id())) {
            pause(data, project, "building identity/size changed before completion");
            return;
        }
        project.clearReservations();
        project.setPhase("complete");
        project.setPausedReason("");
        data.touch();
        VillageHousingPlanner.recordFinishedHouse(level, data, project.villageId());
        VillageSimulationScheduler.enqueueValidation(level,
                "expanded_house:" + home.id(),
                () -> VillageBuildingService.revalidateChunk(
                        level, new ChunkPos(home.min())));
    }

    static boolean allComplete(ServerLevel level, VillageSavedData.ProjectRecord project) {
        for (Step step : steps(project)) {
            // The second roof opening is intentionally occupied by the
            // correctly oriented landing stair when the project is finished.
            if (step.remove()
                    && step.pos().equals(project.site().offset(3, 4, 2))) continue;
            if (!completed(level, step)) return false;
        }
        return true;
    }

    private static boolean completed(ServerLevel level, Step step) {
        if (!VillageSimulationScheduler.isChunkLoaded(level, step.pos())) return false;
        if (step.remove()) return level.getBlockState(step.pos()).isAir();
        if (!level.getBlockState(step.pos()).equals(step.state())) return false;
        if (!step.bed()) return true;
        BlockPos head = step.pos().relative(step.state().getValue(BedBlock.FACING));
        BlockState expectedHead = step.state().setValue(BedBlock.PART, BedPart.HEAD);
        return VillageSimulationScheduler.isChunkLoaded(level, head)
                && level.getBlockState(head).equals(expectedHead);
    }

    private static void advanceCursor(VillageSavedData data,
                                      VillageSavedData.ProjectRecord project, Step step) {
        project.setWorkCursor(project.workCursor() + 1);
        project.setPausedReason("");
        project.setPhase(step.bed() ? "interior" : step.remove() ? "stairwell" : "upper_shell");
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
        BlockState facingEast = stairs.defaultBlockState()
                .setValue(HorizontalDirectionalBlock.FACING, Direction.EAST);
        BlockState facingSouth = stairs.defaultBlockState()
                .setValue(HorizontalDirectionalBlock.FACING, Direction.SOUTH);
        List<Step> list = new ArrayList<>();

        // Keep the original roof/floor intact while raising the outer shell
        // and weatherproof final roof; no overnight exposed open floor.
        for (int y = 5; y <= 7; y++) for (int x = 0; x < 5; x++)
            for (int z = 0; z < 5; z++) {
                boolean edge = x == 0 || x == 4 || z == 0 || z == 4;
                boolean window = y == 6 && (x == 0 || x == 4) && z == 2;
                if (edge && !window)
                    list.add(new Step(base.offset(x, y, z),
                            timber.defaultBlockState(), wood, false, false));
            }
        for (int x = 0; x < 5; x++) for (int z = 0; z < 5; z++) {
            list.add(new Step(base.offset(x, 8, z),
                    timber.defaultBlockState(), wood, false, false));
        }
        for (int x = 1; x <= 3; x++) {
            list.add(new Step(base.offset(x, x, 1), facingEast, stairs.asItem(), false, false));
        }
        list.add(new Step(base.offset(3, 4, 1),
                Blocks.AIR.defaultBlockState(), null, true, false));
        list.add(new Step(base.offset(3, 4, 2),
                Blocks.AIR.defaultBlockState(), null, true, false));
        list.add(new Step(base.offset(3, 4, 2), facingSouth, stairs.asItem(), false, false));

        BlockState southFoot = Blocks.WHITE_BED.defaultBlockState()
                .setValue(BedBlock.PART, BedPart.FOOT)
                .setValue(HorizontalDirectionalBlock.FACING, Direction.SOUTH);
        BlockState westFoot = Blocks.WHITE_BED.defaultBlockState()
                .setValue(BedBlock.PART, BedPart.FOOT)
                .setValue(HorizontalDirectionalBlock.FACING, Direction.WEST);
        list.add(new Step(base.offset(1, 5, 2), southFoot, Items.WHITE_BED, false, true));
        list.add(new Step(base.offset(2, 5, 1), westFoot, Items.WHITE_BED, false, true));
        return List.copyOf(list);
    }

    private static boolean isOriginalOneStory(VillageSavedData.BuildingRecord home) {
        return home.max().getX() == home.min().getX() + 4
                && home.max().getY() == home.min().getY() + 4
                && home.max().getZ() == home.min().getZ() + 4;
    }

    private static UUID parse(String text) {
        try { return UUID.fromString(text); }
        catch (IllegalArgumentException | NullPointerException ignored) { return null; }
    }

    private static void pause(VillageSavedData data,
                              VillageSavedData.ProjectRecord project, String reason) {
        project.setPausedReason(reason);
        data.touch();
    }

    static record Step(BlockPos pos, BlockState state, Item material,
                       boolean remove, boolean bed) {}
}
