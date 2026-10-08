package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaRegistries;
import java.util.Comparator;
import java.util.List;
import java.util.UUID;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.tags.BlockTags;
import net.minecraft.world.Container;
import net.minecraft.world.entity.ai.memory.MemoryModuleType;
import net.minecraft.world.entity.npc.Villager;
import net.minecraft.world.entity.npc.VillagerProfession;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.level.block.BedBlock;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.phys.AABB;

/**
 * A conservative, inventory-backed retrofit of an adopted public/work building.
 *
 * Only an existing, explicitly recognized public/work/mixed-use building may be
 * touched, and then only one vacant, sheltered interior air cell. No floor,
 * roof, chest, bed, doorway or player block is broken. The persistent project
 * survives replacement of its Carpenter and keeps physical cargo authoritative.
 */
public final class VillageWorkstationRetrofitService {
    public static final String TEMPLATE = "retrofit_workstation_v1";
    private static final String TARGET_BUILDING = "retrofit_building_id";
    private static final String TARGET_VILLAGER = "retrofit_villager_id";
    private static final String WORKSTATION = "retrofit_workstation";
    private static final int MAX_SCAN_VOLUME = 800;

    private VillageWorkstationRetrofitService() {}

    /** Called from the normal low-frequency village building planner. */
    public static boolean tryPlan(Villager carpenter, ServerLevel level, UUID villageId) {
        VillageSavedData data = VillageSavedData.get(level);
        VillageSavedData.VillageRecord village = data.village(villageId).orElse(null);
        if (village == null) return false;

        List<Villager> residents = level.getEntitiesOfClass(
                Villager.class, carpenter.getBoundingBox().inflate(28.0D),
                v -> v.isAlive() && !v.isBaby()
                        && VillagerSimData.villageId(v).filter(villageId::equals).isPresent()
                        && !v.getBrain().hasMemoryValue(MemoryModuleType.JOB_SITE));
        residents.sort(Comparator.comparing(v -> v.getUUID().toString()));

        for (Villager resident : residents) {
            // Without this durable deduplication, an unclaimed station could
            // make the same resident request fresh blocks in every building
            // on successive planning days.
            boolean alreadyProvided = data.projectsView().values().stream()
                    .anyMatch(p -> TEMPLATE.equals(p.templateId())
                            && !"cancelled".equals(p.phase())
                            && resident.getUUID().toString().equals(
                                    p.parameter(TARGET_VILLAGER)));
            if (alreadyProvided) continue;
            Block fixture = workstationFor(resident.getVillagerData().getProfession());
            if (fixture == null) continue;
            Item fixtureItem = fixture.asItem();
            // Do not start a persistent project for an item that nobody can
            // physically supply. No abstract block/material substitution.
            if (VillageStorageService.count(carpenter, level, fixtureItem) <= 0
                    && VillagerSimData.workCargoCount(
                            carpenter, level.registryAccess(), 8, fixtureItem) <= 0) {
                continue;
            }

            for (UUID buildingId : village.buildingIds().stream()
                    .sorted(Comparator.comparing(UUID::toString)).toList()) {
                VillageSavedData.BuildingRecord building = data.building(buildingId).orElse(null);
                if (!eligible(building, villageId, level, carpenter.blockPosition())) continue;
                BlockPos site = findEmptyAnchor(level, building, fixture);
                if (site == null) continue;

                VillageSavedData.ProjectRecord project =
                        data.createProject(villageId, "building", 65, site);
                project.setTemplateId(TEMPLATE);
                project.setPhase("interior");
                project.setWorkCursor(0);
                project.setLeadCarpenterId(carpenter.getUUID());
                project.setAnchor(building.min());
                project.setParameter(TARGET_BUILDING, building.id().toString());
                project.setParameter(TARGET_VILLAGER, resident.getUUID().toString());
                project.setParameter(WORKSTATION, keyFor(fixture));
                project.setReservation(VillageStorageService.itemKey(fixtureItem), 1);
                data.touch();
                return true;
            }
        }
        return false;
    }

    /** Called by the ordinary Carpenter worker queue for this one-step project. */
    public static void advance(Villager carpenter, ServerLevel level,
                               VillageSavedData.ProjectRecord project, int cargoSlots) {
        VillageSavedData data = VillageSavedData.get(level);
        UUID buildingId = parseUuid(project.parameter(TARGET_BUILDING));
        UUID targetId = parseUuid(project.parameter(TARGET_VILLAGER));
        Block fixture = blockFor(project.parameter(WORKSTATION));
        VillageSavedData.BuildingRecord building = buildingId == null
                ? null : data.building(buildingId).orElse(null);
        if (building == null || fixture == null || targetId == null) {
            cancel(data, project, "building or workstation missing");
            return;
        }
        if (!VillageSimulationScheduler.isAreaLoaded(level, building.min(), building.max())) {
            pause(data, project, "waiting for loaded building");
            return;
        }
        if (!eligible(building, project.villageId(), level, null)) {
            cancel(data, project, "building no longer eligible");
            return;
        }

        BlockPos site = project.site();

        // If a player installed the requested block while the worker was
        // traveling, accept it without spending another item.
        if (level.getBlockState(site).is(fixture)) {
            finish(data, level, project, building, carpenter);
            return;
        }

        Villager intended = level.getEntity(targetId) instanceof Villager resident ? resident : null;
        if (intended == null) {
            pause(data, project, "waiting for requesting villager");
            return;
        }
        if (!intended.isAlive()
                || !VillagerSimData.villageId(intended).filter(project.villageId()::equals).isPresent()
                || workstationFor(intended.getVillagerData().getProfession()) != fixture
                || intended.getBrain().hasMemoryValue(MemoryModuleType.JOB_SITE)) {
            cancel(data, project, "job-site need resolved or profession changed");
            return;
        }

        if (!safeSlot(level, building, site) || alreadyHasWorkstation(level, building, fixture)) {
            cancel(data, project, "interior layout changed");
            return;
        }

        if (!VillageSimulationEvents.ensureCargoItem(carpenter, level, fixture.asItem(), 1, cargoSlots)) {
            pause(data, project, "waiting for physical workstation item");
            return;
        }
        if (carpenter.distanceToSqr(site.getCenter()) > 7.0D * 7.0D) {
            carpenter.getNavigation().moveTo(
                    site.getX() + 0.5D, site.getY(), site.getZ() + 0.5D, 0.75D);
            pause(data, project, "worker travelling");
            return;
        }

        // Avoid placing the workstation into a villager/player currently
        // standing at its selected cell.
        if (!level.getEntitiesOfClass(net.minecraft.world.entity.LivingEntity.class,
                new AABB(site), entity -> entity.isAlive()).isEmpty()) {
            pause(data, project, "workstation cell occupied");
            return;
        }

        ItemStack payment = new ItemStack(fixture);
        if (!VillagerSimData.takeWorkCargo(
                carpenter, level.registryAccess(), cargoSlots, fixture.asItem(), 1)) {
            pause(data, project, "missing carried workstation");
            return;
        }
        if (!level.setBlock(site, fixture.defaultBlockState(), Block.UPDATE_ALL)) {
            // If placement did not happen, give the same real item back rather
            // than losing paid cargo. Overflow remains in the world.
            if (!level.getBlockState(site).is(fixture)) {
                ItemStack overflow = VillagerSimData.insertWorkCargo(
                        carpenter, level.registryAccess(), payment, cargoSlots);
                if (!overflow.isEmpty()) carpenter.spawnAtLocation(overflow);
            }
            pause(data, project, "block placement rejected");
            return;
        }
        finish(data, level, project, building, carpenter);
    }

    private static boolean eligible(VillageSavedData.BuildingRecord building,
                                    UUID villageId, ServerLevel level, BlockPos near) {
        if (building == null || !building.villageId().equals(villageId)
                || !"valid".equals(building.validationState())
                || building.villageBuilt() || !"player_adopted".equals(building.templateId())) {
            return false;
        }
        // Only knowingly public/work space; ordinary private houses and storage
        // do not become freely available construction sites.
        if (!("public".equals(building.classification())
                || "workshop".equals(building.classification())
                || "mixed_use".equals(building.classification()))) return false;
        if (near != null && building.min().distManhattan(near) > 64) return false;
        int x = building.max().getX() - building.min().getX() + 1;
        int y = building.max().getY() - building.min().getY() + 1;
        int z = building.max().getZ() - building.min().getZ() + 1;
        return (long)x * y * z <= MAX_SCAN_VOLUME
                && VillageSimulationScheduler.isAreaLoaded(level, building.min(), building.max());
    }

    private static BlockPos findEmptyAnchor(ServerLevel level,
            VillageSavedData.BuildingRecord building, Block fixture) {
        if (alreadyHasWorkstation(level, building, fixture)) return null;
        BlockPos min = building.min();
        BlockPos max = building.max();
        for (int y = min.getY() + 1; y < max.getY() - 1; y++) {
            for (int x = min.getX() + 1; x < max.getX(); x++) {
                for (int z = min.getZ() + 1; z < max.getZ(); z++) {
                    BlockPos pos = new BlockPos(x, y, z);
                    if (!VillageSimulationScheduler.tryConsumeBlockProbe(level)) return null;
                    if (safeSlot(level, building, pos)) return pos;
                }
            }
        }
        return null;
    }

    private static boolean alreadyHasWorkstation(ServerLevel level,
            VillageSavedData.BuildingRecord building, Block fixture) {
        for (BlockPos pos : BlockPos.betweenClosed(building.min(), building.max())) {
            if (!VillageSimulationScheduler.tryConsumeBlockProbe(level)) return true;
            if (level.getBlockState(pos).is(fixture)) return true;
        }
        return false;
    }

    private static boolean safeSlot(ServerLevel level,
            VillageSavedData.BuildingRecord building, BlockPos pos) {
        BlockPos min = building.min();
        BlockPos max = building.max();
        if (pos.getX() <= min.getX() || pos.getX() >= max.getX()
                || pos.getZ() <= min.getZ() || pos.getZ() >= max.getZ()
                || pos.getY() <= min.getY() || pos.getY() >= max.getY() - 1
                || !VillageSimulationScheduler.isChunkLoaded(level, pos)
                || !level.getBlockState(pos).isAir()
                || !level.getBlockState(pos.above()).isAir()
                || !level.getBlockState(pos.below()).isFaceSturdy(
                        level, pos.below(), Direction.UP)
                || level.canSeeSky(pos)
                || !VillageBuildingAdoptionService.hasAdjacentStandingSpace(
                        level, pos, min, max)) return false;

        int openNeighbors = 0;
        int walls = 0;
        for (Direction direction : Direction.Plane.HORIZONTAL) {
            BlockPos neighbor = pos.relative(direction);
            BlockState state = level.getBlockState(neighbor);
            if (state.is(BlockTags.DOORS)
                    || state.getBlock() instanceof BedBlock
                    || state.is(Blocks.BELL)
                    || level.getBlockEntity(neighbor) instanceof Container) return false;
            if (state.isAir() && level.getBlockState(neighbor.above()).isAir()) {
                openNeighbors++;
            } else if (state.isFaceSturdy(level, neighbor, direction.getOpposite())) {
                walls++;
            }
        }
        // Put the block against a wall, leaving at least two routes around it.
        // Never fill a one-cell corridor or block a door.
        return walls >= 1 && openNeighbors >= 2;
    }

    private static void finish(VillageSavedData data, ServerLevel level,
            VillageSavedData.ProjectRecord project, VillageSavedData.BuildingRecord building,
            Villager carpenter) {
        if ("residential".equals(building.classification())) {
            building.setClassification("mixed_use");
        } else if ("public".equals(building.classification())) {
            building.setClassification("workshop");
        }
        building.setLastValidatedGameTime(level.getGameTime());
        project.setReservation(VillageStorageService.itemKey(
                blockFor(project.parameter(WORKSTATION)).asItem()), 0);
        project.setWorkCursor(1);
        project.setPhase("complete");
        project.setPausedReason("");
        VillagerSimData.setCarpentrySkill(carpenter,
                Math.min(100, VillagerSimData.carpentrySkill(carpenter) + 1));
        data.touch();
    }

    private static void pause(VillageSavedData data,
            VillageSavedData.ProjectRecord project, String reason) {
        project.setPausedReason(reason);
        data.touch();
    }

    private static void cancel(VillageSavedData data,
            VillageSavedData.ProjectRecord project, String reason) {
        project.clearReservations();
        project.setPausedReason(reason);
        project.setPhase("cancelled");
        data.touch();
    }

    private static UUID parseUuid(String value) {
        try { return UUID.fromString(value); }
        catch (IllegalArgumentException ignored) { return null; }
    }

    private static Block workstationFor(VillagerProfession profession) {
        if (profession == AsobibaRegistries.CARPENTER.value())
            return AsobibaRegistries.CARPENTER_WORKBENCH.get();
        if (profession == VillagerProfession.FARMER) return Blocks.COMPOSTER;
        if (profession == VillagerProfession.FISHERMAN) return Blocks.BARREL;
        if (profession == VillagerProfession.FLETCHER) return Blocks.FLETCHING_TABLE;
        if (profession == VillagerProfession.SHEPHERD) return Blocks.LOOM;
        if (profession == VillagerProfession.LIBRARIAN) return Blocks.LECTERN;
        if (profession == VillagerProfession.CARTOGRAPHER) return Blocks.CARTOGRAPHY_TABLE;
        if (profession == VillagerProfession.ARMORER) return Blocks.BLAST_FURNACE;
        if (profession == VillagerProfession.BUTCHER) return Blocks.SMOKER;
        if (profession == VillagerProfession.MASON) return Blocks.STONECUTTER;
        if (profession == VillagerProfession.TOOLSMITH) return Blocks.SMITHING_TABLE;
        if (profession == VillagerProfession.WEAPONSMITH) return Blocks.GRINDSTONE;
        if (profession == VillagerProfession.CLERIC) return Blocks.BREWING_STAND;
        if (profession == VillagerProfession.LEATHERWORKER) return Blocks.CAULDRON;
        return null;
    }

    private static String keyFor(Block block) {
        return net.minecraft.core.registries.BuiltInRegistries.BLOCK.getKey(block).toString();
    }

    private static Block blockFor(String key) {
        net.minecraft.resources.ResourceLocation id =
                net.minecraft.resources.ResourceLocation.tryParse(key);
        if (id == null) return null;
        Block block = net.minecraft.core.registries.BuiltInRegistries.BLOCK.get(id);
        if (block == Blocks.AIR || !keyFor(block).equals(key)) return null;
        return block;
    }
}
