package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.WeakHashMap;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.util.Mth;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.Mob;
import net.minecraft.world.entity.ai.behavior.BlockPosTracker;
import net.minecraft.world.entity.ai.behavior.MoveToTargetSink;
import net.minecraft.world.entity.ai.behavior.PositionTracker;
import net.minecraft.world.entity.ai.memory.MemoryModuleType;
import net.minecraft.world.entity.ai.memory.WalkTarget;
import net.minecraft.world.entity.decoration.ArmorStand;
import net.minecraft.world.entity.monster.Monster;
import net.minecraft.world.entity.npc.Villager;
import net.minecraft.world.entity.schedule.Activity;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.CampfireBlock;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.entity.EntityTypeTest;
import net.minecraft.world.level.pathfinder.Node;
import net.minecraft.world.level.pathfinder.Path;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;

/** A brief idle vignette. No saved data, rewards, spawned actors, AI removal or chunk requests. */
public final class VillagerArmorStandImitationService {
    static final int CHECK_INTERVAL = 100;
    static final int COOLDOWN = 2400;
    static final int ARRIVAL_TIMEOUT = 100;
    static final int MAX_QUERY_RESULTS = 24;
    static final int MAX_BLOCK_PROBES = 192;
    static final int MAX_ROUTE_LENGTH = 6;
    private static final Map<ServerLevel, State> STATES = new WeakHashMap<>();

    private static final class State {
        long nextCheck;
        long cooldownUntil;
        int observerCursor;
        Scene scene;
        String lastStopReason = "none";
    }

    record Proof(List<BlockPos> floors, List<BlockPos> air, AABB corridor) {}
    record Plan(BlockPos destination, List<BlockPos> route, Proof proof, int probes) {}
    record Snapshot(UUID villager, UUID stand, BlockPos destination, boolean posing, long releaseAt, int probes) {}

    private static final class Scene {
        final UUID observer;
        final UUID villager;
        final UUID stand;
        final Vec3 standOrigin;
        final float yaw;
        final Plan plan;
        final Path path;
        final WalkTarget walk;
        final PositionTracker look;
        final long deadline;
        final int duration;
        long releaseAt = Long.MAX_VALUE;
        boolean posing;

        Scene(ServerPlayer observer, Villager villager, ArmorStand stand, Plan plan, long now, int duration) {
            this.observer = observer.getUUID();
            this.villager = villager.getUUID();
            this.stand = stand.getUUID();
            this.standOrigin = stand.position();
            this.yaw = stand.getYRot();
            this.plan = plan;
            this.deadline = now + ARRIVAL_TIMEOUT;
            this.duration = duration;
            this.path = new Path(plan.route().stream()
                    .map(p -> new Node(p.getX(), p.getY(), p.getZ())).toList(), plan.destination(), true);
            this.walk = new WalkTarget(plan.destination(), 0.5F, 0);
            Vec3 facing = Vec3.directionFromRotation(0.0F, yaw);
            this.look = new BlockPosTracker(Vec3.atBottomCenterOf(plan.destination())
                    .add(facing.scale(8)).add(0, villager.getEyeHeight(), 0));
        }
    }

    /** Unique reads fail closed at a hard cap and only consult already present full chunks. */
    static final class Probe {
        final ServerLevel level;
        final Map<BlockPos, BlockState> blocks = new HashMap<>();
        int count;
        Probe(ServerLevel level) { this.level = level; }
        BlockState block(BlockPos pos) {
            BlockState cached = blocks.get(pos);
            if (cached != null) return cached;
            if (count >= MAX_BLOCK_PROBES || level.isOutsideBuildHeight(pos)) return null;
            count++;
            var chunk = level.getChunkSource().getChunkNow(pos.getX() >> 4, pos.getZ() >> 4);
            if (chunk == null) return null;
            BlockState state = chunk.getBlockState(pos);
            blocks.put(pos.immutable(), state);
            return state;
        }
    }

    private VillagerArmorStandImitationService() {}
    private static boolean enabled() { return AsobibaTweaksConfig.VILLAGER_ARMOR_STAND_IMITATION_ENABLED.getAsBoolean(); }

    static boolean priorityFree(Villager villager, ServerLevel level) {
        return villager.isAlive() && !villager.isRemoved() && !villager.isNoAi() && !villager.isBaby()
                && villager.getBbWidth() <= 0.7F && villager.getBbHeight() <= 2.0F
                && villager.onGround() && !villager.isSleeping() && !villager.isTrading()
                && !villager.isPassenger() && !villager.isVehicle() && !villager.isLeashed()
                && !villager.isOnFire() && !villager.isInWaterOrBubble() && villager.hurtTime == 0
                && villager.getTarget() == null && villager.getUnhappyCounter() <= 0
                && villager.goalSelector.getAvailableGoals().stream().noneMatch(g -> g.isRunning()
                    && (g.getFlags().contains(net.minecraft.world.entity.ai.goal.Goal.Flag.MOVE)
                        || g.getFlags().contains(net.minecraft.world.entity.ai.goal.Goal.Flag.TARGET)
                        || g.getFlags().contains(net.minecraft.world.entity.ai.goal.Goal.Flag.JUMP)))
                && (villager.getLastHurtByMob() == null
                    || villager.tickCount - villager.getLastHurtByMobTimestamp() >= 200)
                && villager.getBrain().isActive(Activity.IDLE)
                && !MobBuildingUseService.villagerBusy(villager, level, level.getDayTime())
                && !villager.getBrain().hasMemoryValue(MemoryModuleType.ATTACK_TARGET)
                && !villager.getBrain().hasMemoryValue(MemoryModuleType.HURT_BY)
                && !villager.getBrain().hasMemoryValue(MemoryModuleType.HURT_BY_ENTITY)
                && !villager.getBrain().hasMemoryValue(MemoryModuleType.NEAREST_HOSTILE)
                && !villager.getBrain().hasMemoryValue(MemoryModuleType.AVOID_TARGET)
                && !villager.getBrain().hasMemoryValue(MemoryModuleType.IS_PANICKING)
                && !villager.getBrain().hasMemoryValue(MemoryModuleType.BREED_TARGET)
                && !villager.getBrain().hasMemoryValue(MemoryModuleType.INTERACTION_TARGET)
                && !villager.getBrain().hasMemoryValue(MemoryModuleType.POTENTIAL_JOB_SITE)
                && VillagerSimData.workSiteId(villager).isEmpty()
                && VillagerSimData.outpostSiteId(villager).isEmpty()
                && "none".equals(VillagerSimData.duty(villager));
    }

    static boolean idle(Villager villager, ServerLevel level) {
        return priorityFree(villager, level) && !villager.getNavigation().isInProgress()
                && villager.getDeltaMovement().horizontalDistanceSqr() <= 0.0025D
                && !villager.getBrain().hasMemoryValue(MemoryModuleType.WALK_TARGET)
                && !villager.getBrain().hasMemoryValue(MemoryModuleType.PATH)
                && !villager.getBrain().hasMemoryValue(MemoryModuleType.LOOK_TARGET)
                // A sink already stopping can erase even a newly installed memory on its final tick.
                && villager.getBrain().getRunningBehaviors().stream().noneMatch(b -> b instanceof MoveToTargetSink)
                && villager.goalSelector.getAvailableGoals().stream().noneMatch(g -> g.isRunning()
                    && (g.getFlags().contains(net.minecraft.world.entity.ai.goal.Goal.Flag.MOVE)
                        || g.getFlags().contains(net.minecraft.world.entity.ai.goal.Goal.Flag.TARGET)));
    }

    private static boolean suitableStand(ArmorStand stand) {
        return stand.isAlive() && !stand.isRemoved() && !stand.isMarker() && !stand.isSmall()
                && !stand.isInvisible() && !stand.isOnFire() && !stand.isPassenger()
                && !stand.isInWaterOrBubble() && stand.onGround()
                && stand.getDeltaMovement().horizontalDistanceSqr() <= 0.0001D;
    }

    private static <T extends Entity> List<T> nearby(ServerLevel level, Class<T> type, AABB bounds) {
        List<T> found = new ArrayList<>();
        level.getEntities(EntityTypeTest.forClass(type), bounds,
                entity -> entity.isAlive() && !entity.isSpectator(), found, MAX_QUERY_RESULTS);
        return found;
    }

    private static boolean quiet(ServerLevel level, Villager villager) {
        List<Mob> mobs = nearby(level, Mob.class, villager.getBoundingBox().inflate(10));
        return mobs.size() < MAX_QUERY_RESULTS && mobs.stream().noneMatch(mob -> mob instanceof Monster
                || mob.getTarget() != null || mob.isOnFire() || mob.hurtTime > 0);
    }

    static Plan plan(ServerLevel level, Villager villager, ArmorStand stand) {
        if (!suitableStand(stand) || Math.abs(villager.getY() - stand.getY()) > 0.1D) return null;
        Direction side = Direction.fromYRot(stand.getYRot()).getClockWise();
        List<BlockPos> choices = new ArrayList<>(List.of(stand.blockPosition().relative(side),
                stand.blockPosition().relative(side.getOpposite())));
        choices.sort(Comparator.comparingDouble(p -> villager.position().distanceToSqr(Vec3.atBottomCenterOf(p))));
        Probe probe = new Probe(level);
        for (BlockPos destination : choices) {
            BlockPos origin = villager.blockPosition();
            int dx = destination.getX() - origin.getX();
            int dz = destination.getZ() - origin.getZ();
            if (origin.getY() != destination.getY() || Math.abs(dx) + Math.abs(dz) > MAX_ROUTE_LENGTH) continue;
            // Validate the entire possible diagonal sweep, plus a one-block supported safety margin.
            List<BlockPos> floors = new ArrayList<>();
            List<BlockPos> air = new ArrayList<>();
            boolean safe = true;
            for (BlockPos cell : BlockPos.betweenClosed(new BlockPos(Math.min(origin.getX(), destination.getX()) - 1,
                    origin.getY(), Math.min(origin.getZ(), destination.getZ()) - 1),
                    new BlockPos(Math.max(origin.getX(), destination.getX()) + 1, origin.getY(),
                            Math.max(origin.getZ(), destination.getZ()) + 1))) {
                if (!safeFloor(level, probe.block(cell.below()), cell.below())
                        || !air(probe.block(cell)) || !air(probe.block(cell.above()))) { safe = false; break; }
                floors.add(cell.below().immutable());
                air.add(cell.immutable());
                air.add(cell.above().immutable());
            }
            if (!safe) continue;
            AABB corridor = new AABB(Vec3.atBottomCenterOf(origin), Vec3.atBottomCenterOf(destination))
                    .inflate(0.38D, 0.0D, 0.38D).expandTowards(0, 1.95D, 0);
            if (!unoccupied(level, villager, corridor)) continue;
            List<BlockPos> route = new ArrayList<>();
            int steps = Math.max(Math.abs(dx), Math.abs(dz));
            for (int i = 0; i <= steps; i++) {
                route.add(origin.offset(steps == 0 ? 0 : (int)Math.round((double)dx * i / steps),
                        0, steps == 0 ? 0 : (int)Math.round((double)dz * i / steps)).immutable());
            }
            return new Plan(destination.immutable(), List.copyOf(route),
                    new Proof(List.copyOf(floors), List.copyOf(air), corridor), probe.count);
        }
        return null;
    }

    private static boolean air(BlockState state) { return state != null && state.isAir(); }
    private static boolean safeFloor(ServerLevel level, BlockState state, BlockPos pos) {
        return state != null && state.getFluidState().isEmpty() && state.isCollisionShapeFullBlock(level, pos)
                && !state.is(Blocks.MAGMA_BLOCK) && !state.is(Blocks.CACTUS) && !state.is(Blocks.POWDER_SNOW)
                && !(state.getBlock() instanceof CampfireBlock);
    }
    private static boolean unoccupied(ServerLevel level, Villager villager, AABB corridor) {
        List<Entity> entities = nearby(level, Entity.class, corridor);
        return entities.size() < MAX_QUERY_RESULTS && entities.stream().noneMatch(e -> e != villager
                && (e instanceof net.minecraft.world.entity.LivingEntity || e.blocksBuilding));
    }
    private static boolean proofSafe(ServerLevel level, Villager villager, Proof proof) {
        Probe probe = new Probe(level);
        for (BlockPos floor : proof.floors()) if (!safeFloor(level, probe.block(floor), floor)) return false;
        for (BlockPos cell : proof.air()) if (!air(probe.block(cell))) return false;
        return unoccupied(level, villager, proof.corridor());
    }

    /** Deterministic entry shared by the natural scheduler and native-tick regression fixtures. */
    static boolean tryStart(ServerLevel level, ServerPlayer observer, Villager villager, ArmorStand stand, int duration) {
        State state = STATES.computeIfAbsent(level, ignored -> new State());
        if (!enabled() || state.scene != null || state.cooldownUntil > level.getGameTime()
                || observer.serverLevel() != level || !AmbientOddityService.safePlayer(observer)
                || observer.distanceToSqr(villager) > 24 * 24 || !idle(villager, level) || !quiet(level, villager)
                || !(villager.getNavigation() instanceof EndermanVoidGatheringService.IdleNavigationState navState)) return false;
        Plan plan = plan(level, villager, stand);
        if (plan == null) return false;
        Scene scene = new Scene(observer, villager, stand, plan, level.getGameTime(), Mth.clamp(duration, 30, 80));
        // Only empty, transient memories are reserved. Native work, panic, trading and schedule
        // behaviors continue normally and may replace any token; replacement ends this scene.
        long ttl = ARRIVAL_TIMEOUT + scene.duration + 2L;
        villager.getBrain().setMemoryWithExpiry(MemoryModuleType.WALK_TARGET, scene.walk, ttl);
        villager.getBrain().setMemoryWithExpiry(MemoryModuleType.PATH, scene.path, ttl);
        villager.getBrain().setMemoryWithExpiry(MemoryModuleType.LOOK_TARGET, scene.look, ttl);
        navState.clearIdleRecomputation();
        villager.getNavigation().stop();
        state.scene = scene;
        state.cooldownUntil = level.getGameTime() + COOLDOWN;
        if (!villager.getNavigation().moveTo(scene.path, 0.5D)) {
            release(level, state, villager);
            return false;
        }
        return true;
    }

    /** Exact ownership also guards vanilla block-change and delayed path recomputation. */
    public static boolean ownsNavigation(Villager villager) {
        if (!(villager.level() instanceof ServerLevel level)) return false;
        State state = STATES.get(level);
        return state != null && state.scene != null && state.scene.villager.equals(villager.getUUID())
                && villager.getNavigation().getPath() == state.scene.path;
    }

    static void onEntityTick(Villager villager, boolean afterAi) {
        if (!(villager.level() instanceof ServerLevel level)) return;
        State state = STATES.get(level);
        if (state == null || state.scene == null || !state.scene.villager.equals(villager.getUUID())) return;
        Scene scene = state.scene;
        Entity target = level.getEntity(scene.stand);
        Entity observer = level.getEntity(scene.observer);
        long now = level.getGameTime();
        if (!enabled() || !(target instanceof ArmorStand stand) || !suitableStand(stand)
                || stand.position().distanceToSqr(scene.standOrigin) > 0.01D
                || Math.abs(Mth.wrapDegrees(stand.getYRot() - scene.yaw)) > 1.0F
                || !(observer instanceof ServerPlayer player) || !AmbientOddityService.safePlayer(player)
                || player.distanceToSqr(villager) > 24 * 24 || !priorityFree(villager, level)
                || villager.getBrain().getMemory(MemoryModuleType.WALK_TARGET).orElse(null) != scene.walk
                || villager.getBrain().getMemory(MemoryModuleType.PATH).orElse(null) != scene.path
                || villager.getBrain().hasMemoryValue(MemoryModuleType.LOOK_TARGET)
                    && villager.getBrain().getMemory(MemoryModuleType.LOOK_TARGET).orElse(null) != scene.look
                || villager.getNavigation().getPath() != scene.path
                || !scene.plan.proof().corridor().inflate(0.1D).contains(villager.position())
                || now >= scene.releaseAt || !scene.posing && now >= scene.deadline
                || !quiet(level, villager) || !proofSafe(level, villager, scene.plan.proof())) {
            state.lastStopReason = "tick=" + villager.tickCount + ", afterAi=" + afterAi
                    + ", priority=" + priorityFree(villager, level)
                    + ", activity=" + villager.getBrain().getActiveNonCoreActivity()
                    + ", ground=" + villager.onGround() + ", busy=" + MobBuildingUseService.villagerBusy(villager, level, level.getDayTime())
                    + ", walk=" + (villager.getBrain().getMemory(MemoryModuleType.WALK_TARGET).orElse(null) == scene.walk)
                    + ", memoryPath=" + (villager.getBrain().getMemory(MemoryModuleType.PATH).orElse(null) == scene.path)
                    + ", look=" + villager.getBrain().getMemory(MemoryModuleType.LOOK_TARGET).orElse(null)
                    + ", navigation=" + (villager.getNavigation().getPath() == scene.path)
                    + ", inside=" + scene.plan.proof().corridor().inflate(0.1D).contains(villager.position())
                    + ", position=" + villager.position() + ", posing=" + scene.posing
                    + ", quiet=" + quiet(level, villager) + ", proof=" + proofSafe(level, villager, scene.plan.proof())
                    + ", stand=" + (target instanceof ArmorStand a ? suitableStand(a) + ":" + a.position() : target)
                    + ", observer=" + (observer instanceof ServerPlayer p ? AmbientOddityService.safePlayer(p) + ":" + p.position() : observer);
            release(level, state, villager);
            return;
        }
        if (!afterAi) return;
        // LookAtTargetSink naturally expires after 45–90 ticks and erases its look memory.
        // Refill only an empty slot while every other ownership/priority check still holds;
        // a replacement look target always wins and is never rewritten.
        if (!villager.getBrain().hasMemoryValue(MemoryModuleType.LOOK_TARGET))
            villager.getBrain().setMemoryWithExpiry(MemoryModuleType.LOOK_TARGET, scene.look,
                    Math.max(1L, scene.deadline + scene.duration - now));
        Vec3 destination = Vec3.atBottomCenterOf(scene.plan.destination());
        // Match native per-axis waypoint tolerance, including diagonal arrivals.
        if (!scene.posing && Math.abs(villager.getX() - destination.x) <= 0.46D
                && Math.abs(villager.getZ() - destination.z) <= 0.46D
                && Math.abs(villager.getY() - destination.y) <= 0.1D) {
            scene.posing = true;
            scene.releaseAt = now + scene.duration;
            scene.path.setNextNodeIndex(scene.path.getNodeCount());
            villager.getMoveControl().setWantedPosition(villager.getX(), villager.getY(), villager.getZ(), 0);
        }
        if (scene.posing) {
            // Cosmetic yaw only. No position, velocity, health, item or statistic is changed.
            villager.setYRot(scene.yaw);
            villager.setYHeadRot(scene.yaw);
            villager.setYBodyRot(scene.yaw);
        }
    }

    static void tick(ServerLevel level) {
        State state = STATES.computeIfAbsent(level, ignored -> new State());
        if (!enabled()) { stop(level); return; }
        if (state.scene != null) {
            Entity actor = level.getEntity(state.scene.villager);
            if (actor instanceof Villager villager) onEntityTick(villager, false);
            else state.scene = null;
            return;
        }
        long now = level.getGameTime();
        if (now < state.nextCheck || now < state.cooldownUntil) return;
        state.nextCheck = now + CHECK_INTERVAL;
        List<ServerPlayer> players = level.players();
        if (players.isEmpty()) return;
        ServerPlayer observer = players.get(Math.floorMod(state.observerCursor++, players.size()));
        if (!AmbientOddityService.safePlayer(observer)
                || level.random.nextDouble() >= AsobibaTweaksConfig.VILLAGER_ARMOR_STAND_IMITATION_CHANCE.getAsDouble()) return;
        List<ArmorStand> stands = nearby(level, ArmorStand.class, observer.getBoundingBox().inflate(16));
        List<Villager> villagers = nearby(level, Villager.class, observer.getBoundingBox().inflate(16));
        if (stands.size() >= MAX_QUERY_RESULTS || villagers.size() >= MAX_QUERY_RESULTS) return;
        int attempts = 0;
        for (Villager villager : villagers) {
            if (!idle(villager, level)) continue;
            for (ArmorStand stand : stands) {
                if (villager.distanceToSqr(stand) > 36 || !suitableStand(stand)) continue;
                if (++attempts > 2) return;
                if (tryStart(level, observer, villager, stand, 40 + level.random.nextInt(21))) return;
            }
        }
    }

    private static void release(ServerLevel level, State state, Villager villager) {
        Scene scene = state.scene;
        if (scene == null) return;
        if (villager.getNavigation().getPath() == scene.path) {
            if (villager.getNavigation() instanceof EndermanVoidGatheringService.IdleNavigationState navState)
                navState.clearIdleRecomputation();
            villager.getNavigation().stop();
            villager.getMoveControl().setWantedPosition(villager.getX(), villager.getY(), villager.getZ(), 0);
        }
        if (villager.getBrain().getMemory(MemoryModuleType.WALK_TARGET).orElse(null) == scene.walk)
            villager.getBrain().eraseMemory(MemoryModuleType.WALK_TARGET);
        if (villager.getBrain().getMemory(MemoryModuleType.PATH).orElse(null) == scene.path)
            villager.getBrain().eraseMemory(MemoryModuleType.PATH);
        if (villager.getBrain().getMemory(MemoryModuleType.LOOK_TARGET).orElse(null) == scene.look)
            villager.getBrain().eraseMemory(MemoryModuleType.LOOK_TARGET);
        state.scene = null;
    }

    static void onLeave(Entity entity, ServerLevel level) {
        State state = STATES.get(level);
        if (state == null || state.scene == null) return;
        if (state.scene.villager.equals(entity.getUUID()) && entity instanceof Villager villager) {
            release(level, state, villager);
        } else if (state.scene.stand.equals(entity.getUUID()) || state.scene.observer.equals(entity.getUUID())) {
            Entity actor = level.getEntity(state.scene.villager);
            if (actor instanceof Villager villager) release(level, state, villager);
            else state.scene = null;
        }
    }

    static String lastStopReason(ServerLevel level) {
        State state = STATES.get(level);
        return state == null ? "no state" : state.lastStopReason;
    }

    static Snapshot snapshot(ServerLevel level) {
        State state = STATES.get(level);
        Scene s = state == null ? null : state.scene;
        return s == null ? null : new Snapshot(s.villager, s.stand, s.plan.destination(), s.posing, s.releaseAt, s.plan.probes());
    }

    static void stop(ServerLevel level) {
        State state = STATES.get(level);
        if (state != null && state.scene != null) {
            Entity actor = level.getEntity(state.scene.villager);
            if (actor instanceof Villager villager) release(level, state, villager);
        }
        STATES.remove(level);
    }
    static void reset() { for (ServerLevel level : List.copyOf(STATES.keySet())) stop(level); }
}
