package io.github.akakishi04.asobibatweaks.feature;

import java.util.Comparator;
import java.util.List;
import java.util.UUID;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.npc.Villager;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.level.block.BedBlock;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.HorizontalDirectionalBlock;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.state.properties.BedPart;
import net.minecraft.world.phys.AABB;

/**
 * In-place housing reuse before new land is consumed.
 *
 * Furnishes the unused second bed location of a previously completed,
 * village-owned 5x5 one-story hut. No custom/player-adopted building is ever
 * altered. Each finished White Bed is a real carried ItemStack, sourced from
 * recognized storage or crafted from three White Wool and three identical
 * Planks; the original shell and other existing furnishings stay untouched.
 *
 * The durable project survives a reload or change of Carpenter. Partial
 * bed placement is recorded as already paid and repaired without a second
 * debit; another player placing a different block vetoes the whole operation.
 */
public final class VillageHouseReuseService {
    public static final String TEMPLATE = "house_furnish_second_bed_v1";
    private static final String BUILDING = "reuse_building";
    private static final String ORIGINAL = "reuse_original_project";
    private static final String WOOD = "reuse_wood";
    private static final String PAID = "reuse_bed_paid";
    private static final int CARGO_CAPACITY = 8;
    private static final int MAX_BUILDINGS = 24;

    private VillageHouseReuseService() {}

    public static boolean tryPlan(Villager carpenter, ServerLevel level, UUID villageId) {
        VillageSavedData data = VillageSavedData.get(level);
        VillageSavedData.VillageRecord village = data.village(villageId).orElse(null);
        if (village == null || !"active".equals(village.lifecycle())) return false;

        List<VillageSavedData.BuildingRecord> homes = village.buildingIds().stream()
                .sorted(Comparator.comparing(UUID::toString))
                .limit(MAX_BUILDINGS)
                .map(data::building).flatMap(java.util.Optional::stream)
                .filter(b -> b.villageBuilt() && b.villageId().equals(villageId)
                        && "house_5x5".equals(b.templateId())
                        && "residential".equals(b.classification())
                        && "valid".equals(b.validationState())
                        && b.validatedCapacity() == 1)
                .toList();
        for (VillageSavedData.BuildingRecord home : homes) {
            if (home.min().distManhattan(carpenter.blockPosition()) > 72
                    || !VillageSimulationScheduler.isAreaLoaded(
                            level, home.min(), home.max())
                    || !isOriginalSingleHouse(home)
                    || data.activeProjectsForVillage(villageId).stream()
                            .anyMatch(p -> (TEMPLATE.equals(p.templateId())
                                        && home.id().toString().equals(p.parameter(BUILDING)))
                                    || (VillageHouseVerticalExpansionService.TEMPLATE.equals(
                                            p.templateId())
                                        && home.id().toString().equals(
                                                p.parameter("expand_building"))))) {
                continue;
            }
            VillageSavedData.ProjectRecord original = village.projectIds().stream()
                    .map(data::project).flatMap(java.util.Optional::stream)
                    .filter(p -> "building".equals(p.type())
                            && "house_5x5".equals(p.templateId())
                            && "complete".equals(p.phase())
                            && home.min().equals(p.site())
                            && !Boolean.parseBoolean(p.parameter("outpost")))
                    .findFirst().orElse(null);
            if (original == null || !roomReady(level, home.min())) continue;
            Block timber = VillageBridgeService.plank(original.parameter("plank"));

            boolean supplied = VillageStorageService.count(carpenter, level, Items.WHITE_BED) > 0
                    || VillageStorageService.count(carpenter, level, Items.WHITE_WOOL) >= 3
                            && VillageStorageService.count(carpenter, level, timber.asItem()) >= 3;
            if (!supplied && VillagerSimData.workCargoCount(carpenter,
                    level.registryAccess(), CARGO_CAPACITY, Items.WHITE_BED) == 0) continue;

            VillageSavedData.ProjectRecord project = data.createProject(
                    villageId, "building", 88, home.min().offset(1, 1, 2));
            project.setTemplateId(TEMPLATE);
            project.setLeadCarpenterId(carpenter.getUUID());
            project.setAnchor(home.min());
            project.setParameter(BUILDING, home.id().toString());
            project.setParameter(ORIGINAL, original.id().toString());
            project.setParameter(WOOD, original.parameter("plank"));
            project.setPhase("interior");
            project.setWorkCursor(0);
            project.setReservation(VillageStorageService.itemKey(Items.WHITE_BED), 1);
            data.touch();
            return true;
        }
        return false;
    }

    static void advance(Villager carpenter, ServerLevel level,
                        VillageSavedData.ProjectRecord project) {
        VillageSavedData data = VillageSavedData.get(level);
        UUID buildingId = parse(project.parameter(BUILDING));
        UUID originalId = parse(project.parameter(ORIGINAL));
        VillageSavedData.BuildingRecord home = buildingId == null
                ? null : data.building(buildingId).orElse(null);
        VillageSavedData.ProjectRecord original = originalId == null
                ? null : data.project(originalId).orElse(null);
        if (home == null || original == null || !home.villageBuilt()
                || !"house_5x5".equals(home.templateId())
                || !home.villageId().equals(project.villageId())
                || !original.site().equals(home.min())
                || !"house_5x5".equals(original.templateId())
                || !"complete".equals(original.phase())
                || !isOriginalSingleHouse(home)
                || !project.site().equals(home.min().offset(1, 1, 2))) {
            cancel(data, project, "no longer an original village-owned one-bed house");
            return;
        }
        if (!VillageSimulationScheduler.isAreaLoaded(
                level, home.min(), home.max())) {
            pause(data, project, "home temporarily unloaded");
            return;
        }
        BlockPos foot = project.site();
        BlockPos head = foot.relative(Direction.SOUTH);
        BlockState expectedFoot = bedState(BedPart.FOOT);
        BlockState expectedHead = bedState(BedPart.HEAD);
        boolean paid = Boolean.parseBoolean(project.parameter(PAID));

        if (level.getBlockState(foot).equals(expectedFoot)
                && level.getBlockState(head).equals(expectedHead)) {
            complete(data, level, project, home);
            return;
        }
        boolean footAir = level.getBlockState(foot).isAir();
        boolean headAir = level.getBlockState(head).isAir();
        if (!footAir && !level.getBlockState(foot).equals(expectedFoot)
                || !headAir && !level.getBlockState(head).equals(expectedHead)) {
            // Player or mod edited this furnishing slot while travelling.
            // Never overwrite the new block or charge further materials.
            cancel(data, project, "player-edited second-bed slot");
            return;
        }
        if (!shellReady(level, home.min())
                || !level.getBlockState(foot.below()).isFaceSturdy(
                        level, foot.below(), Direction.UP)
                || !level.getBlockState(head.below()).isFaceSturdy(
                        level, head.below(), Direction.UP)) {
            pause(data, project, "house interior no longer safe");
            return;
        }
        if (!paid && !level.getEntitiesOfClass(LivingEntity.class,
                new AABB(foot).minmax(new AABB(head)),
                e -> e.isAlive()).isEmpty()) {
            pause(data, project, "bed slot occupied");
            return;
        }
        // The bed slot may be much farther from a recognized warehouse than
        // the worker's interaction radius. Load a genuinely finished Bed
        // (or exact wool + plank inputs) before traveling to that room.
        // A paid, partially placed bed never needs another inventory debit.
        if (!paid) {
            Block timber = VillageBridgeService.plank(project.parameter(WOOD));
            if (!VillageCarpenterCraftingService.ensureWhiteBed(
                    carpenter, level, timber, CARGO_CAPACITY)) {
                pause(data, project, "stage real white bed at village storage");
                return;
            }
        }
        if (carpenter.distanceToSqr(foot.getCenter()) > 7.0D * 7.0D) {
            carpenter.getNavigation().moveTo(
                    foot.getX() + 0.5D, foot.getY(), foot.getZ() + 0.5D, 0.75D);
            pause(data, project, "carpenter carrying physical bed to home");
            return;
        }
        if (!paid) {
            if (!VillagerSimData.takeWorkCargo(carpenter,
                    level.registryAccess(), CARGO_CAPACITY, Items.WHITE_BED, 1)) {
                pause(data, project, "staged finished bed missing from cargo");
                return;
            }
            project.setParameter(PAID, "true");
            data.touch();
        }
        // Send both halves as a single server-worker action, followed by
        // vanilla neighbor updates. An already-paid partial bed can resume
        // without consuming another inventory item.
        if (footAir) level.setBlock(foot, expectedFoot, Block.UPDATE_CLIENTS);
        if (headAir) level.setBlock(head, expectedHead, Block.UPDATE_CLIENTS);
        level.updateNeighborsAt(foot, Blocks.WHITE_BED);
        level.updateNeighborsAt(head, Blocks.WHITE_BED);

        if (!level.getBlockState(foot).equals(expectedFoot)
                || !level.getBlockState(head).equals(expectedHead)) {
            // Keep PAID and the real partial block state; do not refund a
            // whole bed item while a physical bed half may remain.
            pause(data, project, "paid bed partly placed; retry without charge");
            return;
        }
        complete(data, level, project, home);
    }

    private static void complete(VillageSavedData data, ServerLevel level,
                                 VillageSavedData.ProjectRecord project,
                                 VillageSavedData.BuildingRecord home) {
        project.clearReservations();
        project.setWorkCursor(1);
        project.setPhase("complete");
        project.setPausedReason("");
        data.touch();
        VillageHousingPlanner.recordFinishedHouse(level, data, project.villageId());
        VillageSimulationScheduler.enqueueValidation(level,
                "reoccupy_home:" + home.id(),
                () -> VillageBuildingService.revalidateChunk(
                        level, new net.minecraft.world.level.ChunkPos(home.min())));
    }

    private static boolean roomReady(ServerLevel level, BlockPos origin) {
        BlockPos foot = origin.offset(1, 1, 2);
        BlockPos head = foot.relative(Direction.SOUTH);
        return shellReady(level, origin)
                && level.getBlockState(foot).isAir()
                && level.getBlockState(head).isAir()
                && level.getBlockState(foot.below()).isFaceSturdy(
                        level, foot.below(), Direction.UP)
                && level.getBlockState(head.below()).isFaceSturdy(
                        level, head.below(), Direction.UP);
    }

    private static boolean shellReady(ServerLevel level, BlockPos base) {
        BlockPos primaryFoot = base.offset(2, 1, 2);
        BlockPos primaryHead = base.offset(2, 1, 3);
        BlockPos entrance = base.offset(2, 1, 0);
        return level.getBlockState(primaryFoot).is(Blocks.WHITE_BED)
                && level.getBlockState(primaryHead).is(Blocks.WHITE_BED)
                && level.getBlockState(entrance).isAir()
                && level.getBlockState(entrance.above()).isAir()
                && level.getBlockState(base.offset(2, 4, 2)).isSolidRender(
                        level, base.offset(2, 4, 2))
                // Sky light is propagated asynchronously after a real roof is built.
                // This owner-linked 5x5 blueprint has a known roof plane: require
                // actual cover over both new bed halves, including after player edits.
                && level.getBlockState(base.offset(1, 4, 2)).isSolidRender(
                        level, base.offset(1, 4, 2))
                && level.getBlockState(base.offset(1, 4, 3)).isSolidRender(
                        level, base.offset(1, 4, 3))
                && level.getBlockState(base.offset(1, 2, 2)).isAir()
                && level.getBlockState(base.offset(1, 2, 3)).isAir();
    }

    private static boolean isOriginalSingleHouse(VillageSavedData.BuildingRecord building) {
        BlockPos a = building.min();
        BlockPos b = building.max();
        return b.getX() == a.getX() + 4
                && b.getY() == a.getY() + 4
                && b.getZ() == a.getZ() + 4;
    }

    private static BlockState bedState(BedPart part) {
        return Blocks.WHITE_BED.defaultBlockState()
                .setValue(BedBlock.PART, part)
                .setValue(HorizontalDirectionalBlock.FACING, Direction.SOUTH);
    }

    private static UUID parse(String raw) {
        try { return UUID.fromString(raw); }
        catch (IllegalArgumentException | NullPointerException ignored) { return null; }
    }

    private static void pause(VillageSavedData data,
                              VillageSavedData.ProjectRecord project, String why) {
        project.setPausedReason(why);
        data.touch();
    }

    private static void cancel(VillageSavedData data,
                               VillageSavedData.ProjectRecord project, String why) {
        project.clearReservations();
        project.setPhase("cancelled");
        project.setPausedReason(why);
        data.touch();
    }
}
