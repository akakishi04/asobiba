package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import java.util.ArrayList;
import java.util.List;
import java.util.Objects;
import java.util.UUID;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.tags.BlockTags;
import net.minecraft.tags.FluidTags;
import net.minecraft.tags.ItemTags;
import net.minecraft.world.Container;
import net.minecraft.world.SimpleContainer;
import net.minecraft.world.entity.npc.Villager;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.block.Block;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.state.properties.BlockStateProperties;
import net.minecraft.world.level.levelgen.Heightmap;

/** Planner-approved, immutable resource footprints; workers never chase resources from their position. */
public final class VillageResourceSiteService {
    static final int FORESTRY_RADIUS = 24;
    static final int QUARRY_RADIUS = 8;
    static final int QUARRY_DEPTH = 12;
    private static final int CARGO = 8;
    private static final long DAY = 24_000L;
    // Forestry: 2*100 protected-neighborhood checks + 225 crown/trunk checks +
    // 100 final protection checks + <=264 reserve columns + one candidate = 790.
    static final int FORESTRY_PREFLIGHT = 800;
    static final int QUARRY_PREFLIGHT = 208;
    static final int FISHING_PREFLIGHT = 112;
    private static final String PLAN_AFTER = "asobibatweaks_resource_plan_after";

    private VillageResourceSiteService() {}

    static String typeForDuty(String duty) {
        return switch (duty) {
            case "forester" -> "forestry";
            case "quarry" -> "quarry";
            case "fisher" -> "fishing";
            default -> "";
        };
    }

    public static void requestPlan(Villager worker, ServerLevel level) {
        if (typeForDuty(VillagerSimData.duty(worker)).isEmpty()) return;
        if (level.getGameTime() < worker.getPersistentData().getLong(PLAN_AFTER)) return;
        worker.getPersistentData().putLong(PLAN_AFTER, level.getGameTime() + DAY);
        VillageSimulationScheduler.enqueuePlanning(level, "resource_sites:" + worker.getUUID(),
                () -> { if (worker.isAlive() && worker.level() == level) planForWorker(worker, level); });
    }

    /** Only the planner can designate or replace an assignment. Its anchor is the settlement/outpost. */
    static void planForWorker(Villager worker, ServerLevel level) {
        var data = VillageSavedData.get(level);
        UUID villageId = VillagerSimData.villageId(worker).orElse(null);
        var village = villageId == null ? null : data.village(villageId).orElse(null);
        String type = typeForDuty(VillagerSimData.duty(worker));
        if (village == null || type.isEmpty() || "abandoned".equals(village.lifecycle())
                || "merged".equals(village.lifecycle())) return;
        VillageStorageService.bootstrapLegacyIfNeeded(worker, level);
        UUID parentId = VillagerSimData.outpostSiteId(worker).orElse(null);
        var parent = parentId == null ? null : data.workSite(parentId).orElse(null);
        if (parentId != null && (parent == null || !villageId.equals(parent.villageId())
                || !"outpost".equals(parent.type()) || !"active".equals(parent.state())
                || !type.equals(parent.purpose()))) return;
        var assigned = assignedSite(worker, level, type);
        if (assigned != null) {
            refreshSite(level, data, assigned);
            // A depleted site receives an explicit daily recheck, retaining its original footprint.
            // Replacement is planner-owned and never rebases an existing quarry's surface.
            if (!"depleted".equals(assigned.state()) || assigned.idleDays() < 3) return;
        }
        VillagerSimData.clearWorkSiteId(worker);
        int matching = 0;
        List<VillageSavedData.WorkSiteRecord> sites = data.workSitesForVillage(villageId);
        if (sites.size() > 128) return;
        for (var site : sites) {
            if (!type.equals(site.type()) || !Objects.equals(parentId, site.parentWorkSiteId())) continue;
            matching++;
            refreshSite(level, data, site);
            if (("active".equals(site.state()) || "resting".equals(site.state())
                    || "stocked".equals(site.state())) && site.idleDays() < 3) {
                VillagerSimData.setWorkSiteId(worker, site.id());
                return;
            }
        }
        if (matching >= 4 || !hasDemand(level, village, type)) return;
        BlockPos anchor = parent == null ? village.center() : center(parent);
        // A remote footprint is anchored to the original outpost, never the travelling worker.
        int searchRadius = parent == null ? 48 : 24;
        long salt = villageId.getLeastSignificantBits() ^ level.getGameTime() / DAY;
        for (int i = 0; i < 96; i++) {
            if (!VillageSimulationScheduler.tryConsumeWorkerProbe(level)) return;
            int x = anchor.getX() + Math.floorMod(Long.hashCode(salt + i * 104729L), searchRadius * 2 + 1) - searchRadius;
            int z = anchor.getZ() + Math.floorMod(Long.hashCode(salt * 31 + i * 15485863L), searchRadius * 2 + 1) - searchRadius;
            BlockPos column = new BlockPos(x, anchor.getY(), z);
            if (!VillageSimulationScheduler.isChunkLoaded(level, column)) continue;
            int y = level.getHeight(Heightmap.Types.MOTION_BLOCKING_NO_LEAVES, x, z) - 1;
            BlockPos surface = new BlockPos(x, y, z);
            if (parent == null && !VillageActivityBoundary.contains(village, surface)) continue;
            BlockState state = level.getBlockState(surface);
            if ("forestry".equals(type) && !state.is(BlockTags.LOGS)) continue;
            if ("quarry".equals(type) && (!isQuarryMaterial(state) || y < 0)) continue;
            if ("fishing".equals(type) && !level.getFluidState(surface).is(FluidTags.WATER)) continue;
            int radius = "forestry".equals(type) ? FORESTRY_RADIUS : "quarry".equals(type) ? QUARRY_RADIUS : 12;
            int floor = "quarry".equals(type) ? Math.max(0, y - QUARRY_DEPTH) : Math.max(level.getMinBuildHeight(), y - 12);
            int top = "quarry".equals(type) ? y : Math.min(level.getMaxBuildHeight() - 1, y + 12);
            BlockPos min = new BlockPos(x - radius, floor, z - radius);
            BlockPos max = new BlockPos(x + radius, top, z + radius);
            if (!VillageSimulationScheduler.isAreaLoaded(level, min.offset(-2, 0, -2), max.offset(2, 0, 2))) continue;
            if (protectedUse(level, surface, null)) continue;
            if (overlapsExistingFootprint(type, min, max, sites)) continue;
            var site = data.createWorkSite(villageId, type, min, max);
            site.setPurpose("forestry".equals(type) ? "wood" : "quarry".equals(type) ? "stone" : "fishing");
            site.setParentWorkSiteId(parentId);
            site.setCreatedGameTime(level.getGameTime());
            site.setLastLifecycleGameTime(level.getGameTime());
            VillagerSimData.setWorkSiteId(worker, site.id());
            data.touch();
            return;
        }
    }

    static boolean overlapsExistingFootprint(String type, BlockPos min, BlockPos max,
                                             List<VillageSavedData.WorkSiteRecord> sites) {
        // A replacement cannot give previously excavated terrain a new, lower surface.
        for (var old : sites) {
            if (type.equals(old.type()) && old.min().getX() <= max.getX() && old.max().getX() >= min.getX()
                    && old.min().getZ() <= max.getZ() && old.max().getZ() >= min.getZ()) return true;
        }
        return false;
    }

    static void refreshSite(ServerLevel level, VillageSavedData data, VillageSavedData.WorkSiteRecord site) {
        if (level.getGameTime() - site.lastLifecycleGameTime() < DAY
                || !VillageSimulationScheduler.isAreaLoaded(level, site.min(), site.max())) return;
        site.setLastLifecycleGameTime(level.getGameTime());
        if ("forestry".equals(site.type()) && "depleted".equals(site.state())
                && site.idleDays() >= 3 && level.getGameTime() >= site.nextHarvestGameTime()) {
            // Managed woodland may regrow. Reapproval reuses its identity and immutable bounds.
            site.setIdleDays(0);
        }
        if (level.getGameTime() >= site.nextHarvestGameTime() && site.idleDays() < 3
                && !"abandoned".equals(site.state())) {
            site.setState("active");
            site.setResourceCursor(0);
        }
        data.touch();
    }

    static VillageSavedData.WorkSiteRecord assignedSite(Villager worker, ServerLevel level, String type) {
        var data = VillageSavedData.get(level);
        var id = VillagerSimData.workSiteId(worker);
        if (id.isEmpty()) return null;
        var site = data.workSite(id.get()).orElse(null);
        UUID village = VillagerSimData.villageId(worker).orElse(null);
        UUID parentId = VillagerSimData.outpostSiteId(worker).orElse(null);
        if (site == null || !site.villageId().equals(village) || !type.equals(site.type())
                || !Objects.equals(parentId, site.parentWorkSiteId())) return null;
        if (parentId != null) {
            var parent = data.workSite(parentId).orElse(null);
            if (parent == null || !parent.villageId().equals(village) || !"active".equals(parent.state())
                    || !"outpost".equals(parent.type()) || !type.equals(parent.purpose())) return null;
        }
        return site;
    }

    /** All storage records must be physically readable. Unknown reserves never look like empty storage. */
    static boolean hasDemand(ServerLevel level, VillageSavedData.VillageRecord village, String type) {
        if (village == null || "abandoned".equals(village.lifecycle()) || "merged".equals(village.lifecycle())
                || village.storageIds().isEmpty() || village.storageIds().size() > 32) return false;
        String category = "forestry".equals(type) ? "wood" : "quarry".equals(type) ? "stone" : "fishing";
        long total = 0;
        var data = VillageSavedData.get(level);
        for (UUID id : village.storageIds()) {
            var record = data.storage(id).orElse(null);
            if (record == null || !VillageSimulationScheduler.isChunkLoaded(level, record.pos())
                    || !(level.getBlockEntity(record.pos()) instanceof Container container)
                    || container.getContainerSize() > 128) return false;
            for (int i = 0; i < container.getContainerSize(); i++) {
                ItemStack stack = container.getItem(i);
                if (!stack.isEmpty() && category.equals(VillageResourceReservations.category(stack))) total += stack.getCount();
            }
        }
        int population = Math.max(1, village.residentIds().size());
        long target = "fishing".equals(type) ? Math.max(24L, population * 3L) : Math.max(96L, population * 16L);
        var commitments = VillageResourceReservations.capture(data, village);
        if (!commitments.complete()) return false;
        // Actual unpaid construction bills increase finite demand, never physical stock.
        target = Math.min(16_384L, target + Math.min(16_384L, commitments.categoryCount(category)));
        return total < target;
    }

    static boolean mayHarvest(Villager worker, ServerLevel level, VillageSavedData.WorkSiteRecord site, BlockPos pos) {
        if (site == null || assignedSite(worker, level, site.type()) != site
                || !"active".equals(site.state()) || level.getGameTime() < site.nextHarvestGameTime()
                || !contains(site, pos) || ("quarry".equals(site.type()) && (pos.getY() < 0
                || pos.getY() < site.max().getY() - QUARRY_DEPTH))
                || !VillageSimulationScheduler.isAreaLoaded(level, pos.offset(-2, -1, -2), pos.offset(2, 10, 2))) return false;
        var village = VillageSavedData.get(level).village(site.villageId()).orElse(null);
        return village != null && (site.parentWorkSiteId() != null || VillageActivityBoundary.contains(village, pos))
                && hasDemand(level, village, site.type()) && !protectedUse(level, pos, site);
    }

    static void gather(Villager worker, ServerLevel level, String type) {
        var site = assignedSite(worker, level, type);
        if (site == null || !"active".equals(site.state()) || level.getGameTime() < site.nextHarvestGameTime()) return;
        var data = VillageSavedData.get(level);
        if (!hasDemand(level, data.village(site.villageId()).orElse(null), type)) return;
        // A target column cursor belongs to the immutable site, not the worker or its random walk.
        int width = site.max().getX() - site.min().getX() + 1;
        int depth = site.max().getZ() - site.min().getZ() + 1;
        if (width <= 0 || depth <= 0 || width > 65 || depth > 65) return;
        int columns = width * depth;
        for (int attempt = 0; attempt < 32; attempt++) {
            if (!admitPreflight(level, site, true)) return;
            if (!VillageSimulationScheduler.tryConsumeWorkerProbe(level)) return;
            int cursor = site.resourceCursor();
            if (cursor >= columns) {
                site.setState("depleted"); site.setIdleDays(site.idleDays() + 1);
                site.setNextHarvestGameTime(level.getGameTime()
                        + ("forestry".equals(type) && site.idleDays() >= 3 ? 7 * DAY : DAY)); data.touch(); return;
            }
            int x = site.min().getX() + cursor % width;
            int z = site.min().getZ() + cursor / width;
            BlockPos column = new BlockPos(x, site.max().getY(), z);
            if (!VillageSimulationScheduler.isChunkLoaded(level, column)) return;
            int y = level.getHeight(Heightmap.Types.MOTION_BLOCKING_NO_LEAVES, x, z) - 1;
            BlockPos target = new BlockPos(x, y, z);
            if ("forestry".equals(type)) target = treeBase(level, target);
            site.setResourceCursor(cursor + 1); data.touch();
            if (target == null || !contains(site, target)) continue;
            if ("forestry".equals(type)) {
                if (!mayHarvest(worker, level, site, target)) continue;
                if (collectSapling(worker, level, target)) { site.setResourceCursor(cursor); return; }
                if (approach(worker, level, target, 6.25D)) { site.setResourceCursor(cursor); return; }
                if (harvestTree(worker, level, site, target)) return;
                continue;
            }
            if ("quarry".equals(type)) {
                if (!isQuarryMaterial(level.getBlockState(target)) || !mayHarvest(worker, level, site, target)) continue;
                if (hasAdjacentFluid(level, target)) { suspendFlooded(level, site); return; }
                if (approach(worker, level, target, 6.25D)) { site.setResourceCursor(cursor); return; }
                harvestQuarry(worker, level, site, target); return;
            }
            if (!level.getFluidState(target).is(FluidTags.WATER) || !mayHarvest(worker, level, site, target)) continue;
            if (approach(worker, level, target, 25.0D)) { site.setResourceCursor(cursor); return; }
            if (worker.getRandom().nextInt(3) == 0) {
                ItemStack fish = new ItemStack(worker.getRandom().nextInt(5) == 0 ? Items.SALMON : Items.COD);
                if (VillagerSimData.canInsertWorkCargo(worker, level.registryAccess(), fish, CARGO)) {
                    VillagerSimData.insertWorkCargo(worker, level.registryAccess(), fish, CARGO);
                    used(level, site);
                }
            }
            return;
        }
    }

    static boolean harvestQuarry(Villager worker, ServerLevel level, VillageSavedData.WorkSiteRecord site, BlockPos pos) {
        if (site == null || !"quarry".equals(site.type()) || assignedSite(worker, level, "quarry") != site
                || !admitPreflight(level, site, false)
                || !mayHarvest(worker, level, site, pos)
                || worker.distanceToSqr(pos.getCenter()) > 6.25D || !isQuarryMaterial(level.getBlockState(pos))) return false;
        if (hasAdjacentFluid(level, pos)) { suspendFlooded(level, site); return false; }
        // Open-face shallow excavation only. An air pocket in a cave does not authorize tunnelling.
        if (!level.canSeeSky(pos.above())) return false;
        boolean success = harvestBlocks(worker, level, List.of(pos), new ItemStack(Items.IRON_PICKAXE));
        if (success) used(level, site);
        return success;
    }

    static boolean harvestTree(Villager worker, ServerLevel level, VillageSavedData.WorkSiteRecord site, BlockPos base) {
        if (site == null || !"forestry".equals(site.type()) || assignedSite(worker, level, "forestry") != site
                || !admitPreflight(level, site, false)
                || !mayHarvest(worker, level, site, base)
                || worker.distanceToSqr(base.getCenter()) > 6.25D) return false;
        List<BlockPos> trunk = simpleTree(level, site, base);
        if (trunk.isEmpty() || !hasStandingReserve(level, site, base)) return false;
        Block sapling = saplingFor(level.getBlockState(base).getBlock());
        // Validation covers the whole trunk first, avoiding floating chopped remnants.
        if (!harvestBlocks(worker, level, trunk.reversed(), new ItemStack(Items.IRON_AXE))) return false;
        used(level, site);
        site.setNextHarvestGameTime(level.getGameTime() + DAY);
        site.setState("resting");
        if (sapling != null && level.getBlockState(base).isAir() && sapling.defaultBlockState().canSurvive(level, base)) {
            boolean paid = VillagerSimData.takeWorkCargo(worker, level.registryAccess(), CARGO, sapling.asItem(), 1);
            if (!paid) paid = !VillageStorageService.extract(worker, level, sapling.asItem(), 1).isEmpty();
            if (paid && !level.setBlock(base, sapling.defaultBlockState(), Block.UPDATE_ALL)) {
                preserveDrop(worker, level, new ItemStack(sapling));
            }
        }
        return true;
    }

    private static boolean collectSapling(Villager worker, ServerLevel level, BlockPos tree) {
        Block sapling = saplingFor(level.getBlockState(tree).getBlock());
        if (sapling == null || VillagerSimData.workCargoCount(worker, level.registryAccess(), CARGO, sapling.asItem()) > 0) return false;
        var supply = VillageStorageService.nearestContainerWith(worker, level, sapling.asItem()).orElse(null);
        // Bring a real compatible seed from nearby recognized storage. No cross-world withdrawal.
        if (supply == null || supply.record().pos().distSqr(tree) > 64 * 64) return false;
        if (worker.distanceToSqr(supply.record().pos().getCenter()) > 16) {
            approach(worker, level, supply.record().pos(), 16); return true;
        }
        for (ItemStack seed : VillageStorageService.extract(worker, level, sapling.asItem(), 1)) preserveDrop(worker, level, seed);
        return false;
    }

    private static boolean harvestBlocks(Villager worker, ServerLevel level, List<BlockPos> positions, ItemStack tool) {
        List<List<ItemStack>> drops = new ArrayList<>();
        List<BlockState> expected = new ArrayList<>();
        SimpleContainer preview = new SimpleContainer(CARGO);
        List<ItemStack> cargo = VillagerSimData.workCargo(worker, level.registryAccess(), CARGO);
        for (int i = 0; i < CARGO; i++) preview.setItem(i, cargo.get(i).copy());
        for (BlockPos pos : positions) {
            BlockState state = level.getBlockState(pos);
            expected.add(state);
            List<ItemStack> loot = Block.getDrops(state, level, pos, level.getBlockEntity(pos), worker, tool);
            for (ItemStack stack : loot) if (!preview.addItem(stack.copy()).isEmpty()) return false;
            drops.add(loot);
        }
        boolean any = false;
        for (int i = 0; i < positions.size(); i++) {
            if (level.getBlockState(positions.get(i)) != expected.get(i)) break;
            if (!level.setBlock(positions.get(i), Blocks.AIR.defaultBlockState(), Block.UPDATE_ALL)) break;
            any = true;
            for (ItemStack stack : drops.get(i)) preserveDrop(worker, level, stack);
        }
        return any;
    }

    private static void preserveDrop(Villager worker, ServerLevel level, ItemStack stack) {
        ItemStack rest = VillagerSimData.insertWorkCargo(worker, level.registryAccess(), stack, CARGO);
        if (!rest.isEmpty()) worker.spawnAtLocation(rest);
    }

    private static void used(ServerLevel level, VillageSavedData.WorkSiteRecord site) {
        site.setLastUsedGameTime(level.getGameTime());
        site.setIdleDays(0);
        site.setResourceCursor(0);
        VillageSavedData.get(level).touch();
    }

    private static boolean admitPreflight(ServerLevel level, VillageSavedData.WorkSiteRecord site, boolean dispatch) {
        int required = "forestry".equals(site.type()) ? FORESTRY_PREFLIGHT
                : "quarry".equals(site.type()) ? QUARRY_PREFLIGHT : FISHING_PREFLIGHT;
        int configured = AsobibaTweaksConfig.VILLAGE_WORKER_PROBES_PER_TICK.getAsInt();
        // Called twice by the dispatch path; the second check needs only the remaining
        // harvest preflight because dispatch already performed its 100-cell protection scan.
        int remaining = dispatch ? required : required - 104;
        String reason = configured < required ? "resource preflight requires worker probe budget >= " + required
                : !VillageSimulationScheduler.hasWorkerProbeAllowance(level, remaining)
                ? "resource preflight waiting for next tick's probe allowance" : "";
        if (!reason.equals(site.resourcePauseReason())) {
            site.setResourcePauseReason(reason);
            VillageSavedData.get(level).touch();
        }
        return reason.isEmpty();
    }

    private static void suspendFlooded(ServerLevel level, VillageSavedData.WorkSiteRecord site) {
        site.setState("flooded");
        site.setNextHarvestGameTime(level.getGameTime() + DAY);
        VillageSavedData.get(level).touch();
    }

    private static boolean approach(Villager worker, ServerLevel level, BlockPos target, double reach) {
        if (worker.distanceToSqr(target.getCenter()) <= reach) return false;
        if (VillageSimulationScheduler.isAreaLoaded(level, worker.blockPosition(), target))
            worker.getNavigation().moveTo(target.getX() + 0.5D, target.getY() + 1, target.getZ() + 0.5D, 0.7D);
        return true;
    }

    private static BlockPos treeBase(ServerLevel level, BlockPos top) {
        if (!level.getBlockState(top).is(BlockTags.LOGS)) return null;
        BlockPos base = top;
        for (int i = 0; i < 8 && level.getBlockState(base.below()).is(BlockTags.LOGS); i++) base = base.below();
        return level.getBlockState(base.below()).is(BlockTags.DIRT) ? base : null;
    }

    static List<BlockPos> simpleTree(ServerLevel level, VillageSavedData.WorkSiteRecord site, BlockPos base) {
        if (!contains(site, base) || !VillageSimulationScheduler.isAreaLoaded(level, base.offset(-2, -1, -2), base.offset(2, 10, 2))
                || !level.getBlockState(base.below()).is(BlockTags.DIRT)) return List.of();
        Block trunk = level.getBlockState(base).getBlock();
        if (saplingFor(trunk) == null) return List.of();
        List<BlockPos> logs = new ArrayList<>();
        boolean leaves = false;
        for (int y = 0; y <= 8; y++) {
            BlockPos pos = base.above(y);
            BlockState state = level.getBlockState(pos);
            if (state.is(trunk)) {
                if (y == 8 || !contains(site, pos) || !state.hasProperty(BlockStateProperties.AXIS)
                        || state.getValue(BlockStateProperties.AXIS) != Direction.Axis.Y
                        || VillageSavedData.get(level).isPlayerResourceBlock(pos)) return List.of();
                logs.add(pos);
            } else if (state.is(BlockTags.LOGS)) return List.of();
            else if (!state.isAir() && !state.is(BlockTags.LEAVES)) return List.of();
            // Branches, 2x2/giant trunks and nearby built surfaces veto the whole tree.
            for (int dx = -2; dx <= 2; dx++) for (int dz = -2; dz <= 2; dz++) {
                if (!VillageSimulationScheduler.tryConsumeWorkerProbe(level)) return List.of();
                BlockPos around = pos.offset(dx, 0, dz);
                BlockState neighbor = level.getBlockState(around);
                if ((dx != 0 || dz != 0) && neighbor.is(BlockTags.LOGS)) return List.of();
                if (ForestRegenerationEvents.isProtectedSurface(level, around)
                        || neighbor.is(BlockTags.BEDS) || neighbor.is(BlockTags.STAIRS)
                        || neighbor.is(BlockTags.SLABS)) return List.of();
                if (neighbor.is(BlockTags.LEAVES)) {
                    if (neighbor.hasProperty(BlockStateProperties.PERSISTENT)
                            && neighbor.getValue(BlockStateProperties.PERSISTENT)) return List.of();
                    leaves = true;
                }
            }
        }
        if (logs.size() < 3 || !leaves || protectedUse(level, base, site)) return List.of();
        // No gap in the trunk may hide a detached upper log.
        for (int i = 0; i < logs.size(); i++) if (!logs.get(i).equals(base.above(i))) return List.of();
        return logs;
    }

    private static boolean hasStandingReserve(ServerLevel level, VillageSavedData.WorkSiteRecord site, BlockPos base) {
        int standing = 0;
        for (int dx = -8; dx <= 8; dx++) for (int dz = -8; dz <= 8; dz++) {
            if (Math.abs(dx) <= 2 && Math.abs(dz) <= 2) continue;
            BlockPos column = base.offset(dx, 0, dz);
            if (!insideXZ(site, column, 0) || !VillageSimulationScheduler.isChunkLoaded(level, column)) continue;
            if (!VillageSimulationScheduler.tryConsumeWorkerProbe(level)) return false;
            int y = level.getHeight(Heightmap.Types.MOTION_BLOCKING_NO_LEAVES, column.getX(), column.getZ()) - 1;
            BlockPos other = treeBase(level, new BlockPos(column.getX(), y, column.getZ()));
            if (other != null && contains(site, other) && !VillageSavedData.get(level).isPlayerResourceBlock(other)
                    && ++standing >= 2) return true;
        }
        return false;
    }

    static boolean hasAdjacentFluid(ServerLevel level, BlockPos pos) {
        if (!VillageSimulationScheduler.isAreaLoaded(level, pos.offset(-1, -1, -1), pos.offset(1, 1, 1))) return true;
        for (Direction direction : Direction.values()) if (!level.getFluidState(pos.relative(direction)).isEmpty()) return true;
        return !level.getFluidState(pos).isEmpty();
    }

    /** Full horizontal columns beneath recognized infrastructure are excluded from quarrying. */
    static boolean protectedUse(ServerLevel level, BlockPos pos, VillageSavedData.WorkSiteRecord own) {
        var data = VillageSavedData.get(level);
        if (data.isPlayerResourceBlock(pos) || !VillageSimulationScheduler.isAreaLoaded(level,
                pos.offset(-2, -1, -2), pos.offset(2, 2, 2))) return true;
        ChunkPos chunk = new ChunkPos(pos);
        for (int dx = -1; dx <= 1; dx++) for (int dz = -1; dz <= 1; dz++) {
            var index = data.recordsForChunk(new ChunkPos(chunk.x + dx, chunk.z + dz));
            for (UUID id : index.buildingIds()) {
                var building = data.building(id).orElse(null);
                if (building != null && inXZ(pos, building.min(), building.max(), 2)) return true;
            }
            for (UUID id : index.projectIds()) {
                var project = data.project(id).orElse(null);
                if (project != null && !"cancelled".equals(project.phase()) && !"complete".equals(project.phase())
                        && inXZ(pos, project.site().offset(-2, 0, -2), project.site().offset(8, 0, 8), 0)) return true;
            }
            for (UUID id : index.workSiteIds()) {
                var site = data.workSite(id).orElse(null);
                if (site != null && ("farm".equals(site.type()) || "dock".equals(site.type()) || "river_dock".equals(site.type())
                        || "farm".equals(site.purpose())) && insideXZ(site, pos, 2)) return true;
            }
            for (UUID id : index.routeIds()) {
                var route = data.route(id).orElse(null);
                if (route == null || !"active".equals(route.state()) || "waterway".equals(route.type()) || "river".equals(route.type())) continue;
                List<BlockPos> points = route.waypoints().isEmpty() ? List.of(route.from(), route.to()) : route.waypoints();
                for (int i = 1; i < points.size(); i++) if (nearSegment(pos, points.get(i - 1), points.get(i), route.width() + 2)) return true;
            }
        }
        for (BlockPos p : BlockPos.betweenClosed(pos.offset(-2, -1, -2), pos.offset(2, 2, 2))) {
            if (!VillageSimulationScheduler.tryConsumeWorkerProbe(level)) return true;
            if (ForestRegenerationEvents.isProtectedSurface(level, p)
                    || level.getBlockState(p).is(BlockTags.BEDS)
                    || level.getBlockState(p).is(BlockTags.STAIRS)
                    || level.getBlockState(p).is(BlockTags.SLABS)) return true;
        }
        return false;
    }

    private static boolean nearSegment(BlockPos p, BlockPos a, BlockPos b, double radius) {
        double x = b.getX() - a.getX(), z = b.getZ() - a.getZ();
        double length = x * x + z * z;
        double t = length == 0 ? 0 : Math.max(0, Math.min(1, ((p.getX() - a.getX()) * x + (p.getZ() - a.getZ()) * z) / length));
        double dx = p.getX() - a.getX() - t * x, dz = p.getZ() - a.getZ() - t * z;
        return dx * dx + dz * dz <= radius * radius;
    }

    static boolean contains(VillageSavedData.WorkSiteRecord site, BlockPos pos) {
        return site != null && insideXZ(site, pos, 0) && pos.getY() >= site.min().getY() && pos.getY() <= site.max().getY();
    }

    private static boolean insideXZ(VillageSavedData.WorkSiteRecord site, BlockPos pos, int margin) {
        return inXZ(pos, site.min(), site.max(), margin);
    }

    private static boolean inXZ(BlockPos pos, BlockPos min, BlockPos max, int margin) {
        return pos.getX() >= min.getX() - margin && pos.getX() <= max.getX() + margin
                && pos.getZ() >= min.getZ() - margin && pos.getZ() <= max.getZ() + margin;
    }

    private static BlockPos center(VillageSavedData.WorkSiteRecord site) {
        return new BlockPos((site.min().getX() + site.max().getX()) / 2, site.min().getY(),
                (site.min().getZ() + site.max().getZ()) / 2);
    }

    static boolean isQuarryMaterial(BlockState state) {
        return state.is(Blocks.STONE) || state.is(Blocks.ANDESITE) || state.is(Blocks.DIORITE)
                || state.is(Blocks.GRANITE) || state.is(Blocks.COAL_ORE)
                || state.is(Blocks.IRON_ORE) || state.is(Blocks.COPPER_ORE);
    }

    public static void playerPlaced(ServerLevel level, BlockPos pos) {
        BlockState state = level.getBlockState(pos);
        VillageSavedData.get(level).setPlayerResourceBlock(pos, state.is(BlockTags.LOGS) || isQuarryMaterial(state));
    }

    private static Block saplingFor(Block log) {
        if (log == Blocks.OAK_LOG) return Blocks.OAK_SAPLING;
        if (log == Blocks.SPRUCE_LOG) return Blocks.SPRUCE_SAPLING;
        if (log == Blocks.BIRCH_LOG) return Blocks.BIRCH_SAPLING;
        if (log == Blocks.JUNGLE_LOG) return Blocks.JUNGLE_SAPLING;
        if (log == Blocks.ACACIA_LOG) return Blocks.ACACIA_SAPLING;
        if (log == Blocks.DARK_OAK_LOG) return Blocks.DARK_OAK_SAPLING;
        if (log == Blocks.CHERRY_LOG) return Blocks.CHERRY_SAPLING;
        return null; // Giant/mangrove/root systems deliberately need a more capable planner.
    }
}
