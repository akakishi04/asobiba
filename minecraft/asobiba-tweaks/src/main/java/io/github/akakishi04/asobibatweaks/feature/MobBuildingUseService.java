package io.github.akakishi04.asobibatweaks.feature;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.tags.BlockTags;
import net.minecraft.tags.FluidTags;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.PathfinderMob;
import net.minecraft.world.entity.TamableAnimal;
import net.minecraft.world.entity.ai.goal.Goal;
import net.minecraft.world.entity.ai.memory.MemoryModuleType;
import net.minecraft.world.entity.ai.memory.WalkTarget;
import net.minecraft.world.entity.animal.Animal;
import net.minecraft.world.entity.npc.Villager;
import net.minecraft.world.entity.schedule.Activity;
import net.minecraft.world.level.ChunkPos;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.CampfireBlock;
import net.minecraft.world.level.block.DoorBlock;
import net.minecraft.world.level.block.SlabBlock;
import net.minecraft.world.level.block.StairBlock;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.block.state.properties.Half;
import net.minecraft.world.level.block.state.properties.SlabType;
import net.minecraft.world.level.pathfinder.Path;
import net.minecraft.world.phys.AABB;

/** Idle-only destinations, not a replacement movement AI or furniture/seat entity system. */
final class MobBuildingUseService {
    static final int MAX_DESTINATION_PROBES = 128;
    static final int MAX_ROUTE_PROBES = 96;
    static final int MAX_PATHS = 3;
    static final int MAX_PATH_NODES = 40;
    private static final int LOCAL_RADIUS = 9;
    private static final int INDEX_RADIUS = 24;

    private MobBuildingUseService() {}

    static boolean isAvailable(PathfinderMob mob, ServerLevel level) {
        if (!mob.isAlive() || mob.isRemoved() || mob.isNoAi() || mob.isSleeping()
                || mob.isPassenger() || mob.isVehicle() || mob.isLeashed()
                || mob.isOnFire() || mob.isInWaterOrBubble() || mob.getTarget() != null
                || mob.getNavigation().isInProgress()
                || mob.getLastHurtByMob() != null && mob.tickCount - mob.getLastHurtByMobTimestamp() < 200
                || mob.getBrain().hasMemoryValue(MemoryModuleType.WALK_TARGET)
                || mob.getBrain().hasMemoryValue(MemoryModuleType.ATTACK_TARGET)
                || mob.getBrain().hasMemoryValue(MemoryModuleType.HURT_BY)
                || mob.getBrain().hasMemoryValue(MemoryModuleType.AVOID_TARGET)
                || mob.getBrain().hasMemoryValue(MemoryModuleType.BREED_TARGET)
                || mob.getBrain().hasMemoryValue(MemoryModuleType.TEMPTING_PLAYER)
                || mob.getBrain().hasMemoryValue(MemoryModuleType.NEAREST_HOSTILE)
                || mob.getBrain().hasMemoryValue(MemoryModuleType.IS_PANICKING)) return false;
        // Includes temptation, breeding, following, panic and combat goals, even
        // when their navigation happens to be between paths this tick.
        if (mob.goalSelector.getAvailableGoals().stream().anyMatch(goal ->
                goal.isRunning() && goal.getFlags().contains(Goal.Flag.MOVE))) return false;
        if (mob instanceof Animal animal && (animal.isInLove() || animal.isBaby())) return false;
        if (mob instanceof TamableAnimal animal && animal.isOrderedToSit()) return false;
        return !(mob instanceof Villager villager) || !villagerBusy(villager, level, level.getDayTime());
    }

    static boolean villagerBusy(Villager villager, ServerLevel level, long dayTime) {
        long time = Math.floorMod(dayTime, 24000L);
        return villager.isTrading() || time >= 1500L && time <= 10500L
                    || villager.getBrain().isActive(Activity.WORK)
                    || villager.getBrain().isActive(Activity.REST)
                    || villager.getBrain().isActive(Activity.PANIC)
                    || villager.getBrain().isActive(Activity.RAID)
                    || villager.getBrain().isActive(Activity.PRE_RAID)
                    || villager.getBrain().isActive(Activity.HIDE)
                    || !"none".equals(VillagerSimData.emergencyDuty(villager))
                    || VillagerSimData.migrationId(villager).isPresent()
                    || VillagerSimData.riverHaul(villager).isPresent()
                    || VillagerSimData.hasWorkCargo(villager, level.registryAccess(), 16);
    }

    static boolean tryVisit(PathfinderMob mob, ServerLevel level, boolean shelter, boolean night) {
        if (!isAvailable(mob, level)) return false;
        Probe probe = new Probe(level, MAX_DESTINATION_PROBES);
        List<Destination> destinations = new ArrayList<>();
        addInteriors(mob, probe, destinations, shelter || night ? 18 : 10);
        // Rotate a finite sample through the local volume; no world scan or chunk request.
        int width = LOCAL_RADIUS * 2 + 1;
        int volume = width * width * 3;
        int start = Math.floorMod(mob.tickCount / 160 * 64 + mob.getId(), volume);
        for (int i = 0; i < 64 && !probe.exhausted; i++) {
            int cell = (start + i * 17) % volume;
            BlockPos anchor = mob.blockPosition().offset(cell % width - LOCAL_RADIUS,
                    cell / (width * width) - 1, cell / width % width - LOCAL_RADIUS);
            BlockState state = probe.state(anchor);
            if (state == null) continue;
            if (shelter) {
                addDestination(mob, probe, destinations, anchor, 8, true);
            } else {
                BlockPos besideTable = benchTableStanding(probe, anchor);
                if (besideTable != null) addDestination(mob, probe, destinations, besideTable, 20, false);
                if (night && state.getBlock() instanceof CampfireBlock
                        && state.getValue(CampfireBlock.LIT)) {
                    for (Direction direction : Direction.Plane.HORIZONTAL)
                        addDestination(mob, probe, destinations, anchor.relative(direction, 2), 18, false);
                }
            }
        }
        return navigateBest(mob, level, destinations, shelter);
    }

    static void addInteriors(PathfinderMob mob, Probe probe,
                                     List<Destination> destinations, int appeal) {
        VillageSavedData data = VillageSavedData.get(probe.level);
        BlockPos center = mob.blockPosition();
        Set<UUID> visited = new HashSet<>();
        // At most 16 local index buckets, 8 records and 15 cells per record.
        for (int x = (center.getX() - INDEX_RADIUS) >> 4; x <= (center.getX() + INDEX_RADIUS) >> 4; x++) {
            for (int z = (center.getZ() - INDEX_RADIUS) >> 4; z <= (center.getZ() + INDEX_RADIUS) >> 4; z++) {
                for (UUID id : data.recordsForChunk(new ChunkPos(x, z)).buildingIds()) {
                    if (visited.contains(id)) continue;
                    if (visited.size() >= 8 || probe.exhausted) return;
                    visited.add(id);
                    VillageSavedData.BuildingRecord building = data.building(id).orElse(null);
                    if (building == null || !"valid".equals(building.validationState())) continue;
                    BlockPos middle = new BlockPos((building.min().getX() + building.max().getX()) / 2,
                            building.min().getY() + 1, (building.min().getZ() + building.max().getZ()) / 2);
                    if (center.distSqr(middle) > INDEX_RADIUS * INDEX_RADIUS) continue;
                    for (int y = 0; y < 3 && !probe.exhausted; y++) {
                        if (inside(middle.above(y), building.min(), building.max()))
                            addDestination(mob, probe, destinations, middle.above(y), appeal, true);
                        for (Direction direction : Direction.Plane.HORIZONTAL) {
                            BlockPos pos = middle.above(y).relative(direction);
                            if (inside(pos, building.min(), building.max()))
                                addDestination(mob, probe, destinations, pos, appeal, true);
                        }
                    }
                }
            }
        }
    }

    private static boolean inside(BlockPos pos, BlockPos min, BlockPos max) {
        return pos.getX() > min.getX() && pos.getX() < max.getX()
                && pos.getZ() > min.getZ() && pos.getZ() < max.getZ()
                && pos.getY() > min.getY() && pos.getY() < max.getY();
    }

    /** Bottom stair/slab, one free standing cell, then a fence with a pressure-plate tabletop. */
    static BlockPos benchTableStanding(Probe probe, BlockPos bench) {
        BlockState state = probe.state(bench);
        if (!isBench(state)) return null;
        for (Direction direction : Direction.Plane.HORIZONTAL) {
            BlockPos table = bench.relative(direction, 2);
            BlockState support = probe.state(table);
            if (support == null || !support.is(BlockTags.FENCES)) continue;
            BlockState top = probe.state(table.above());
            if (top != null && top.is(BlockTags.PRESSURE_PLATES)) return bench.relative(direction);
        }
        return null;
    }

    static boolean isBench(BlockState state) {
        return state != null && state.getFluidState().isEmpty()
                && (state.getBlock() instanceof StairBlock && state.getValue(StairBlock.HALF) == Half.BOTTOM
                    || state.getBlock() instanceof SlabBlock && state.getValue(SlabBlock.TYPE) == SlabType.BOTTOM);
    }

    private static void addDestination(PathfinderMob mob, Probe probe, List<Destination> destinations,
                                       BlockPos pos, int appeal, boolean requireCover) {
        if (destinations.stream().anyMatch(d -> d.pos().equals(pos)) || !safeStanding(mob, probe, pos)) return;
        boolean covered = hasPhysicalCover(probe, pos);
        if (requireCover && !covered) return;
        destinations.add(new Destination(pos.immutable(), appeal + (covered ? 3 : 0)));
        destinations.sort(Comparator.comparingInt((Destination d) ->
                d.appeal() * 2 - mob.blockPosition().distManhattan(d.pos())).reversed());
        if (destinations.size() > 6) destinations.removeLast();
    }

    static boolean safeStanding(PathfinderMob mob, Probe probe, BlockPos pos) {
        BlockState feet = probe.state(pos);
        if (feet == null || !feet.isAir()) return false;
        BlockState floor = probe.state(pos.below());
        if (floor == null || !floor.isFaceSturdy(probe.level, pos.below(), Direction.UP)
                || !floor.getFluidState().isEmpty() || harmfulFloor(floor)) return false;
        // A golem needs three blocks of headroom; never put any mob on the furniture itself.
        int height = Math.max(2, (int)Math.ceil(mob.getBbHeight()));
        int radius = mob.getBbWidth() > 1.0F ? 1 : 0;
        for (int x = -radius; x <= radius; x++) {
            for (int z = -radius; z <= radius; z++) {
                for (int y = 0; y < height; y++) {
                    BlockState clear = probe.state(pos.offset(x, y, z));
                    if (clear == null || !clear.isAir()) return false;
                }
            }
        }
        AABB target = mob.getBoundingBox().move(pos.getX() + 0.5D - mob.getX(),
                pos.getY() - mob.getY(), pos.getZ() + 0.5D - mob.getZ()).inflate(0.15D);
        return probe.level.getEntitiesOfClass(LivingEntity.class, target,
                entity -> entity != mob && entity.isAlive() && !entity.isSpectator()).isEmpty();
    }

    private static boolean harmfulFloor(BlockState state) {
        return state.is(Blocks.MAGMA_BLOCK) || state.getBlock() instanceof CampfireBlock
                || state.is(Blocks.CACTUS) || state.is(Blocks.POWDER_SNOW);
    }

    private static boolean hasPhysicalCover(Probe probe, BlockPos pos) {
        // canSeeSky reads asynchronously propagated skylight. Check an actual
        // nearby underside instead: fresh/removing roofs must work immediately,
        // and a stale recognized record or residual darkness is not shelter.
        for (int up = 2; up <= 6; up++) {
            BlockPos roof = pos.above(up);
            BlockState state = probe.state(roof);
            if (state == null) return false;
            if (state.getFluidState().isEmpty() && state.isFaceSturdy(probe.level, roof, Direction.DOWN))
                return true;
        }
        return false;
    }

    /** Rank actual reachable vanilla paths, not straight lines or synthetic bridge/door waypoints. */
    static boolean navigateBest(PathfinderMob mob, ServerLevel level,
                                List<Destination> destinations, boolean shelter) {
        if (!isAvailable(mob, level)) return false;
        Probe probe = new Probe(level, MAX_ROUTE_PROBES);
        Destination best = null;
        Path bestPath = null;
        int bestScore = Integer.MIN_VALUE;
        int attempts = 0;
        for (Destination destination : destinations) {
            if (attempts++ >= MAX_PATHS || probe.exhausted) break;
            if (!safeStanding(mob, probe, destination.pos())
                    || shelter && !hasPhysicalCover(probe, destination.pos())) continue;
            Path path = mob.getNavigation().createPath(destination.pos(), 0);
            if (path == null || !path.canReach() || path.getNodeCount() > MAX_PATH_NODES) continue;
            int preference = pathPreference(mob, probe, path, shelter);
            if (preference == Integer.MIN_VALUE) continue;
            int score = destination.appeal() * 2 - path.getNodeCount() * 2 + preference;
            if (score > bestScore) {
                bestScore = score;
                best = destination;
                bestPath = path;
            }
        }
        if (bestPath == null || !isAvailable(mob, level)) return false;
        if (!mob.getNavigation().moveTo(bestPath, shelter ? 0.75D : 0.6D)) return false;
        if (mob instanceof Villager villager) {
            // The normal brain owns movement and wooden-door opening/closing.
            // Do not replace PATH memory: that would block MoveToTargetSink.
            villager.getBrain().setMemoryWithExpiry(MemoryModuleType.WALK_TARGET,
                    new WalkTarget(best.pos(), shelter ? 0.75F : 0.6F, 0), 160L);
        }
        return true;
    }

    static int pathPreference(PathfinderMob mob, Probe probe, Path path, boolean rain) {
        boolean door = false;
        boolean bridge = false;
        int covered = 0;
        // Every path node is loaded; at most six equally spaced route samples.
        for (int i = 0; i < path.getNodeCount(); i++) {
            if (!VillageSimulationScheduler.isChunkLoaded(probe.level, path.getNode(i).asBlockPos()))
                return Integer.MIN_VALUE;
        }
        int samples = Math.min(6, path.getNodeCount());
        for (int i = 0; i < samples; i++) {
            BlockPos pos = path.getNode(i * (path.getNodeCount() - 1) / Math.max(1, samples - 1)).asBlockPos();
            BlockState feet = probe.state(pos);
            BlockState floor = probe.state(pos.below());
            BlockState belowDeck = probe.state(pos.below(2));
            if (feet == null || floor == null || belowDeck == null || harmfulFloor(floor)
                    || !feet.getFluidState().isEmpty()) return Integer.MIN_VALUE;
            if (feet.getBlock() instanceof DoorBlock) {
                if (!feet.getValue(DoorBlock.OPEN)
                        && (!(mob instanceof Villager) || !feet.is(BlockTags.WOODEN_DOORS)))
                    return Integer.MIN_VALUE;
                door = true;
            }
            bridge |= floor.isFaceSturdy(probe.level, pos.below(), Direction.UP)
                    && floor.getFluidState().isEmpty() && belowDeck.getFluidState().is(FluidTags.WATER);
            if (hasPhysicalCover(probe, pos)) covered++;
        }
        return routeBonus(door, bridge, covered, samples, rain);
    }

    static int routeBonus(boolean door, boolean bridge, int covered, int samples, boolean rain) {
        // Bounded tie-breakers: a long detour never wins merely by passing many doors.
        return (door ? 3 : 0) + (bridge ? 4 : 0)
                + (samples == 0 ? 0 : Math.min(samples, covered) * (rain ? 8 : 3) / samples);
    }

    record Destination(BlockPos pos, int appeal) {}

    /** Every unique block read is charged to the existing global low-priority budget. */
    static final class Probe {
        final ServerLevel level;
        private final int limit;
        private final Map<BlockPos, BlockState> states = new HashMap<>();
        boolean exhausted;

        Probe(ServerLevel level, int limit) {
            this.level = level;
            this.limit = limit;
        }

        BlockState state(BlockPos pos) {
            BlockState cached = states.get(pos);
            if (cached != null) return cached;
            if (exhausted || !VillageSimulationScheduler.isChunkLoaded(level, pos)) return null;
            if (states.size() >= limit || !VillageSimulationScheduler.tryConsumeBlockProbe(level)) {
                exhausted = true;
                return null;
            }
            BlockState state = level.getBlockState(pos);
            states.put(pos.immutable(), state);
            return state;
        }
    }
}
