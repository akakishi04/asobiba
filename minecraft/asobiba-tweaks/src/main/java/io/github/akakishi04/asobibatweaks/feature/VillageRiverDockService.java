package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import java.util.Comparator;
import java.util.List;
import java.util.UUID;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.tags.BlockTags;
import net.minecraft.tags.FluidTags;
import net.minecraft.world.Container;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.npc.Villager;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.levelgen.Heightmap;
import net.minecraft.world.phys.AABB;

/**
 * First physical river landing: three plank deck cells and a real Barrel.
 *
 * A surveyed river is only geographic information. It becomes a usable
 * village dock after a saved Carpenter project has physically placed every
 * block, consumed real stored items and confirmed an unobstructed water lane.
 * This does not create a boat or teleport any cargo.
 */
public final class VillageRiverDockService {
    public static final String TEMPLATE = "river_dock_v1";
    private static final String WATER_Y = "dock_water_y";
    private static final String DIRECTION = "dock_direction";
    private static final String PLANK = "dock_plank";
    private static final int MAX_BANK_SEARCH = 9;
    private static final int BUILD_STEPS = 4;
    private static final int CARPENTER_CARGO = 8;

    private VillageRiverDockService() {}

    /** Called on the separate low-frequency route-search queue after a real corridor survey. */
    public static void plan(ServerLevel level, UUID villageId, BlockPos riverSample) {
        if (!enabled() || !VillageSimulationScheduler.isChunkLoaded(level, riverSample)) return;
        VillageSavedData data = VillageSavedData.get(level);
        VillageSavedData.VillageRecord village = data.village(villageId).orElse(null);
        if (village == null || !"active".equals(village.lifecycle())) return;

        int existingDocks = 0;
        for (VillageSavedData.WorkSiteRecord site : data.workSitesForVillage(villageId)) {
            if (!"river_dock".equals(site.type())) continue;
            existingDocks++;
            if (!"active".equals(site.state())) continue;
            Boolean physicallyValid = verifyPhysicalDock(level, data, site);
            // Unknown (unloaded) is NOT damage. Do not force-load or rebuild
            // the same facility merely because its chunk is absent.
            if (physicallyValid == null || physicallyValid) return;
            site.setState("inactive");
            data.touch();
        }
        // Do not fill the world with failed docks if local river geometry later changes.
        if (existingDocks >= 2) return;
        if (data.activeProjectsForVillage(villageId).stream()
                .anyMatch(p -> TEMPLATE.equals(p.templateId()))) return;

        Block chosenPlank = availablePlank(village);
        if (chosenPlank == null) return;
        Candidate bank = findBank(level, village.center(), riverSample);
        if (bank == null) return;

        VillageSavedData.ProjectRecord project = data.createProject(
                villageId, "building", 55, bank.ground());
        project.setTemplateId(TEMPLATE);
        project.setPhase("dock_foundation");
        project.setWorkCursor(0);
        project.setAnchor(village.center());
        project.setParameter(WATER_Y, Integer.toString(bank.waterY()));
        project.setParameter(DIRECTION, bank.waterDirection().getName());
        project.setParameter(PLANK, BuiltInRegistries.BLOCK.getKey(chosenPlank).toString());
        project.setReservation(VillageStorageService.itemKey(chosenPlank.asItem()), 3);
        project.setReservation(VillageStorageService.itemKey(Items.BARREL), 1);
        data.touch();
    }

    /** Advances exactly one construction step and no more than one physical withdrawal. */
    public static void advance(Villager carpenter, ServerLevel level,
                               VillageSavedData.ProjectRecord project) {
        VillageSavedData data = VillageSavedData.get(level);
        if (!enabled()) {
            pause(data, project, "river docks disabled");
            return;
        }
        Direction direction = direction(project.parameter(DIRECTION));
        Block plank = allowedPlank(project.parameter(PLANK));
        int waterY;
        try {
            waterY = Integer.parseInt(project.parameter(WATER_Y));
        } catch (NumberFormatException ignored) {
            cancel(data, project, "invalid saved river water elevation");
            return;
        }
        if (plank == null || direction == null) {
            cancel(data, project, "invalid saved dock materials or direction");
            return;
        }

        BlockPos ground = project.site();
        BlockPos firstWater = new BlockPos(ground.getX() + direction.getStepX(),
                waterY, ground.getZ() + direction.getStepZ());
        BlockPos secondWater = firstWater.relative(direction);
        BlockPos thirdWater = secondWater.relative(direction);

        if (!VillageSimulationScheduler.isAreaLoaded(
                level, ground.offset(-2, -2, -2), thirdWater.offset(2, 3, 2))) {
            pause(data, project, "dock surroundings unloaded");
            return;
        }
        // Water is never converted into a solid block. The pier deck is above
        // the real surface. If the water corridor dries up, construction stops.
        if (!waterAt(level, firstWater) || !waterAt(level, secondWater)
                || !waterAt(level, thirdWater)
                || !level.getBlockState(thirdWater.above()).isAir()) {
            pause(data, project, "navigable water no longer present");
            return;
        }
        BlockPos barrelPos = ground.relative(direction.getClockWise()).above();
        List<Step> steps = List.of(
                new Step(ground.above(), plank, "dock_landing"),
                new Step(firstWater.above(), plank, "dock_pier"),
                new Step(secondWater.above(), plank, "dock_pier"),
                new Step(barrelPos, Blocks.BARREL, "dock_storage")
        );

        int cursor = project.workCursor();
        if (cursor >= BUILD_STEPS) {
            finish(data, level, carpenter, project, steps);
            return;
        }
        Step step = steps.get(cursor);
        BlockState existing = level.getBlockState(step.pos());
        if (existing.is(step.block())) {
            advanceCursor(data, level, carpenter, project, steps);
            return;
        }
        if (!existing.isAir() || !level.getBlockState(step.pos().above()).isAir()
                || !step.block().defaultBlockState().canSurvive(level, step.pos())) {
            pause(data, project, "dock location blocked by existing construction");
            return;
        }
        if (cursor == 0 && !stableNaturalGround(level, ground)) {
            pause(data, project, "dock bank changed");
            return;
        }
        if (cursor == 3 && !level.getBlockState(barrelPos.below())
                .isFaceSturdy(level, barrelPos.below(), Direction.UP)) {
            pause(data, project, "dock storage lacks solid footing");
            return;
        }
        if (carpenter.distanceToSqr(ground.getCenter()) > 7.0D * 7.0D) {
            carpenter.getNavigation().moveTo(ground.getX() + 0.5D,
                    ground.getY() + 1.0D, ground.getZ() + 0.5D, 0.75D);
            pause(data, project, "carpenter travelling to shore");
            return;
        }
        if (!level.getEntitiesOfClass(LivingEntity.class, new AABB(step.pos()),
                entity -> entity.isAlive()).isEmpty()) {
            pause(data, project, "dock step occupied");
            return;
        }

        Item material = step.block().asItem();
        boolean stocked = step.block() == Blocks.BARREL
                ? VillageCarpenterCraftingService.ensureFixture(
                        carpenter, level, material, plank, CARPENTER_CARGO)
                : VillageSimulationEvents.ensureCargoItem(
                        carpenter, level, material, 1, CARPENTER_CARGO);
        if (!stocked) {
            pause(data, project, "missing dock materials");
            return;
        }
        if (!VillagerSimData.takeWorkCargo(carpenter,
                level.registryAccess(), CARPENTER_CARGO, material, 1)) {
            pause(data, project, "missing carried dock block");
            return;
        }

        if (!level.setBlock(step.pos(), step.block().defaultBlockState(), Block.UPDATE_ALL)) {
            // A canceled placement must never silently consume physical stock.
            ItemStack refund = new ItemStack(material);
            ItemStack overflow = VillagerSimData.insertWorkCargo(
                    carpenter, level.registryAccess(), refund, CARPENTER_CARGO);
            if (!overflow.isEmpty()) carpenter.spawnAtLocation(overflow);
            pause(data, project, "dock placement rejected");
            return;
        }
        advanceCursor(data, level, carpenter, project, steps);
    }

    private static void advanceCursor(VillageSavedData data, ServerLevel level,
                                      Villager carpenter,
                                      VillageSavedData.ProjectRecord project,
                                      List<Step> steps) {
        Step step = steps.get(project.workCursor());
        String key = VillageStorageService.itemKey(step.block().asItem());
        project.setReservation(key, project.reservations().getOrDefault(key, 0) - 1);
        project.setWorkCursor(project.workCursor() + 1);
        project.setPhase(step.phase());
        project.setPausedReason("");
        data.touch();
        if (project.workCursor() >= BUILD_STEPS) finish(data, level, carpenter, project, steps);
    }

    private static void finish(VillageSavedData data, ServerLevel level, Villager carpenter,
                               VillageSavedData.ProjectRecord project, List<Step> steps) {
        // A restored, partially completed project can only finish if all four
        // actual blocks are present, and the physical storage is still there.
        for (Step step : steps) {
            if (!VillageSimulationScheduler.isChunkLoaded(level, step.pos())
                    || !level.getBlockState(step.pos()).is(step.block())) {
                pause(data, project, "dock blocks incomplete");
                return;
            }
        }
        BlockPos barrelPos = steps.get(3).pos();
        if (!(level.getBlockEntity(barrelPos) instanceof Container)) {
            pause(data, project, "dock storage block entity missing");
            return;
        }

        String purpose = "dock:" + project.id();
        boolean registered = data.workSitesForVillage(project.villageId()).stream()
                .anyMatch(s -> "river_dock".equals(s.type())
                        && purpose.equals(s.purpose()));
        if (!registered) {
            BlockPos a = steps.get(0).pos();
            BlockPos b = steps.get(2).pos();
            BlockPos min = new BlockPos(Math.min(a.getX(), Math.min(b.getX(), barrelPos.getX())),
                    Math.min(a.getY(), Math.min(b.getY(), barrelPos.getY())) - 1,
                    Math.min(a.getZ(), Math.min(b.getZ(), barrelPos.getZ())));
            BlockPos max = new BlockPos(Math.max(a.getX(), Math.max(b.getX(), barrelPos.getX())),
                    Math.max(a.getY(), Math.max(b.getY(), barrelPos.getY())) + 1,
                    Math.max(a.getZ(), Math.max(b.getZ(), barrelPos.getZ())));
            VillageSavedData.WorkSiteRecord dock = data.createWorkSite(
                    project.villageId(), "river_dock", min, max);
            dock.setPurpose(purpose);
            dock.setState("active");
            dock.setCreatedGameTime(level.getGameTime());
            dock.setLastUsedGameTime(level.getGameTime());
        }
        if (data.storageAt(project.villageId(), barrelPos).isEmpty()) {
            VillageSavedData.StorageRecord storage = data.createStorage(
                    project.villageId(), barrelPos, "general");
            storage.setValidationState("valid");
            storage.setLastValidatedGameTime(level.getGameTime());
        }
        project.setPhase("complete");
        project.setPausedReason("");
        data.touch();
        VillageStorageService.reconcileVillage(project.villageId(), level);
        VillageSimulationEvents.scheduleDockRoad(level, project.villageId(),
                project.site(), project.anchor(), carpenter);
    }

    private static Candidate findBank(ServerLevel level, BlockPos village,
                                      BlockPos waterSample) {
        for (int radius = 1; radius <= MAX_BANK_SEARCH; radius++) {
            for (int dx = -radius; dx <= radius; dx++) {
                for (int dz = -radius; dz <= radius; dz++) {
                    if (Math.max(Math.abs(dx), Math.abs(dz)) != radius) continue;
                    int x = waterSample.getX() + dx;
                    int z = waterSample.getZ() + dz;
                    BlockPos column = new BlockPos(x, level.getMinBuildHeight(), z);
                    if (!VillageSimulationScheduler.isChunkLoaded(level, column)) {
                        // Another shore may still be visible without any chunk load.
                        continue;
                    }
                    if (!VillageSimulationScheduler.tryConsumeBlockProbe(level)) return null;
                    int y = level.getHeight(Heightmap.Types.MOTION_BLOCKING_NO_LEAVES, x, z) - 1;
                    BlockPos land = new BlockPos(x, y, z);
                    if (land.distManhattan(village) > 96 || !stableNaturalGround(level, land)) continue;
                    for (Direction dir : Direction.Plane.HORIZONTAL) {
                        Candidate site = checkBank(level, land, dir);
                        if (site != null) return site;
                    }
                }
            }
        }
        return null;
    }

    /** Only real, source-water boat lanes with a free outer navigation strip. */
    private static Candidate checkBank(ServerLevel level, BlockPos ground, Direction direction) {
        BlockPos edge = ground.relative(direction);
        if (!VillageSimulationScheduler.isChunkLoaded(level, edge)
                || !VillageSimulationScheduler.tryConsumeBlockProbe(level)) return null;
        int waterY = level.getHeight(Heightmap.Types.MOTION_BLOCKING_NO_LEAVES,
                edge.getX(), edge.getZ()) - 1;
        if (Math.abs(waterY - ground.getY()) > 1) return null;
        BlockPos first = new BlockPos(edge.getX(), waterY, edge.getZ());
        BlockPos second = first.relative(direction);
        BlockPos third = second.relative(direction);
        BlockPos fourth = third.relative(direction);
        BlockPos barrel = ground.relative(direction.getClockWise()).above();
        if (!VillageSimulationScheduler.isAreaLoaded(level,
                ground.offset(-2, -2, -2), fourth.offset(2, 3, 2))) return null;
        if (!waterAt(level, first) || !waterAt(level, second)
                || !waterAt(level, third) || !waterAt(level, fourth)) return null;
        if (!waterAt(level, third.relative(direction.getClockWise()))
                || !waterAt(level, third.relative(direction.getCounterClockWise()))) return null;
        if (!level.getBlockState(ground.above()).isAir()
                || !level.getBlockState(ground.above(2)).isAir()
                || !level.getBlockState(first.above()).isAir()
                || !level.getBlockState(first.above(2)).isAir()
                || !level.getBlockState(second.above()).isAir()
                || !level.getBlockState(second.above(2)).isAir()
                || !level.getBlockState(third.above()).isAir()
                || !level.getBlockState(barrel).isAir()
                || !level.getBlockState(barrel.above()).isAir()
                || !level.getBlockState(barrel.below()).isFaceSturdy(
                        level, barrel.below(), Direction.UP)) return null;
        return new Candidate(ground.immutable(), direction, waterY);
    }

    private static boolean stableNaturalGround(ServerLevel level, BlockPos pos) {
        BlockState ground = level.getBlockState(pos);
        return ground.is(Blocks.GRASS_BLOCK) || ground.is(Blocks.DIRT)
                || ground.is(Blocks.COARSE_DIRT) || ground.is(Blocks.SAND)
                || ground.is(Blocks.GRAVEL) || ground.is(Blocks.STONE)
                || ground.is(Blocks.MUD) || ground.is(Blocks.RED_SAND);
    }

    private static boolean waterAt(ServerLevel level, BlockPos pos) {
        return VillageSimulationScheduler.isChunkLoaded(level, pos)
                && level.getFluidState(pos).is(FluidTags.WATER)
                && level.getFluidState(pos).isSource();
    }

    /**
     * Recheck existing dock blocks on the next natural river survey.
     * null means the physical site cannot be observed because it is unloaded.
     * No stock, items, land, or water are fabricated during this inspection.
     */
    private static Boolean verifyPhysicalDock(ServerLevel level, VillageSavedData data,
                                               VillageSavedData.WorkSiteRecord site) {
        if (!VillageSimulationScheduler.isAreaLoaded(level, site.min(), site.max())) return null;
        String purpose = site.purpose();
        if (!purpose.startsWith("dock:")) return false;
        UUID projectId;
        try {
            projectId = UUID.fromString(purpose.substring("dock:".length()));
        } catch (IllegalArgumentException ignored) {
            return false;
        }
        VillageSavedData.ProjectRecord project = data.project(projectId).orElse(null);
        if (project == null || !TEMPLATE.equals(project.templateId())) return false;
        Block plank = allowedPlank(project.parameter(PLANK));
        Direction direction = direction(project.parameter(DIRECTION));
        if (plank == null || direction == null) return false;
        int waterY;
        try {
            waterY = Integer.parseInt(project.parameter(WATER_Y));
        } catch (NumberFormatException ignored) {
            return false;
        }
        BlockPos ground = project.site();
        BlockPos water = new BlockPos(ground.getX() + direction.getStepX(),
                waterY, ground.getZ() + direction.getStepZ());
        BlockPos barrel = ground.relative(direction.getClockWise()).above();
        BlockPos second = water.relative(direction);
        BlockPos third = second.relative(direction);
        if (!VillageSimulationScheduler.isChunkLoaded(level, third)) return null;
        return level.getBlockState(ground.above()).is(plank)
                && level.getBlockState(water.above()).is(plank)
                && level.getBlockState(second.above()).is(plank)
                && level.getBlockState(barrel).is(Blocks.BARREL)
                && level.getBlockEntity(barrel) instanceof Container
                && waterAt(level, water)
                && waterAt(level, second)
                && waterAt(level, third);
    }

    private static Block availablePlank(VillageSavedData.VillageRecord village) {
        boolean barrelInStock = village.ledgerCount(
                VillageStorageService.itemKey(Items.BARREL)) > 0;
        int required = barrelInStock ? 3 : 12;
        Block[] allowed = {
                Blocks.OAK_PLANKS, Blocks.SPRUCE_PLANKS, Blocks.BIRCH_PLANKS,
                Blocks.JUNGLE_PLANKS, Blocks.ACACIA_PLANKS, Blocks.DARK_OAK_PLANKS,
                Blocks.MANGROVE_PLANKS, Blocks.CHERRY_PLANKS
        };
        return java.util.Arrays.stream(allowed)
                .filter(p -> village.ledgerCount(
                        VillageStorageService.itemKey(p.asItem())) >= required)
                .max(Comparator.comparingInt(p -> village.ledgerCount(
                        VillageStorageService.itemKey(p.asItem()))))
                .orElse(null);
    }

    private static Block allowedPlank(String key) {
        ResourceLocation id = ResourceLocation.tryParse(key);
        if (id == null) return null;
        Block block = BuiltInRegistries.BLOCK.get(id);
        return block.defaultBlockState().is(BlockTags.PLANKS) ? block : null;
    }

    private static Direction direction(String raw) {
        return switch (raw) {
            case "north" -> Direction.NORTH;
            case "south" -> Direction.SOUTH;
            case "east" -> Direction.EAST;
            case "west" -> Direction.WEST;
            default -> null;
        };
    }

    private static boolean enabled() {
        return AsobibaTweaksConfig.VILLAGE_SIMULATION_ENABLED.getAsBoolean()
                && AsobibaTweaksConfig.VILLAGE_CARPENTER_ENABLED.getAsBoolean()
                && AsobibaTweaksConfig.VILLAGE_AUTONOMOUS_GROWTH_ENABLED.getAsBoolean()
                && AsobibaTweaksConfig.VILLAGE_RIVER_DOCKS_ENABLED.getAsBoolean();
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

    private record Candidate(BlockPos ground, Direction waterDirection, int waterY) {}
    private record Step(BlockPos pos, Block block, String phase) {}
}
