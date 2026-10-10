package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import java.lang.ref.WeakReference;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.EnumSet;
import java.util.HashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.WeakHashMap;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Direction;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.util.Mth;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.ai.goal.Goal;
import net.minecraft.world.entity.ai.goal.LookAtPlayerGoal;
import net.minecraft.world.entity.ai.goal.RandomLookAroundGoal;
import net.minecraft.world.entity.ai.memory.MemoryModuleType;
import net.minecraft.world.entity.monster.EnderMan;
import net.minecraft.world.entity.monster.Monster;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.BlockState;
import net.minecraft.world.level.chunk.LevelChunk;
import net.minecraft.world.level.entity.EntityTypeTest;
import net.minecraft.world.level.levelgen.Heightmap;
import net.minecraft.world.level.pathfinder.Node;
import net.minecraft.world.level.pathfinder.Path;
import net.minecraft.world.phys.Vec3;

/** A temporary, loaded-only End scene. No spawning, teleporting, block edits, or saved AI. */
public final class EndermanVoidGatheringService {
    /** Implemented by the narrow navigation mixin; only cleared while acquiring idle or owned AI. */
    public interface IdleNavigationState { void clearIdleRecomputation(); }

    static final int MAX_QUERY_RESULTS = 24;
    static final int MAX_BLOCK_PROBES = 128;
    static final int MAX_MEMBERS = 4;
    static final int CHECK_INTERVAL = 200;
    static final int COOLDOWN = 2400;
    static final int ARRIVAL_TIMEOUT = 160;
    static final int RELEASE_STAGGER = 40;
    private static final int MAX_ROUTE_LENGTH = 8;
    private static final Direction[] OUTWARD = { Direction.NORTH, Direction.SOUTH, Direction.WEST, Direction.EAST };
    // Values contain UUIDs, geometry and weak entity references, never a world reference.
    private static final Map<ServerLevel, State> STATES = new WeakHashMap<>();

    private static final class State {
        long nextCheck;
        long cooldownUntil;
        int playerCursor;
        int probes;
        Group group;
    }

    record PlannedMember(UUID entityId, Vec3 origin, BlockPos anchor, List<BlockPos> route) {
        PlannedMember { route = List.copyOf(route); }
    }
    record Proof(List<BlockPos> floors, List<BlockPos> air, List<BlockPos> voidColumns) {}
    record Plan(Direction direction, List<PlannedMember> members, int probes, Proof proof) {
        Plan { members = List.copyOf(members); }
    }
    record MemberSnapshot(UUID entityId, Vec3 origin, BlockPos anchor, long releaseAt, boolean arrived) {}
    record Snapshot(Direction direction, List<MemberSnapshot> members, long cooldownUntil, int probes, boolean dwelling) {}

    private static final class Member {
        final PlannedMember plan;
        final Path path;
        final GatheringGoal goal;
        boolean active = true;
        boolean arrived;
        long releaseAt = Long.MAX_VALUE;

        Member(EnderMan mob, PlannedMember plan, Group group) {
            this.plan = plan;
            List<Node> nodes = new ArrayList<>();
            BlockPos first = plan.route().getFirst();
            nodes.add(new Node(first.getX(), first.getY(), first.getZ()));
            if (!first.equals(plan.anchor())) nodes.add(new Node(plan.anchor().getX(), plan.anchor().getY(), plan.anchor().getZ()));
            this.path = new Path(nodes, plan.anchor(), true);
            this.arrived = mob.position().distanceToSqr(Vec3.atBottomCenterOf(plan.anchor())) <= 0.09D;
            this.goal = new GatheringGoal(mob, group, this);
        }
    }

    private static final class Group {
        final UUID observer;
        final Plan plan;
        final long arrivalDeadline;
        final int duration;
        final List<Member> members = new ArrayList<>();
        boolean cancelled;
        boolean dwelling;

        Group(UUID observer, Plan plan, long now, int duration) {
            this.observer = observer;
            this.plan = plan;
            this.arrivalDeadline = now + ARRIVAL_TIMEOUT;
            this.duration = duration;
        }
    }

    /** Only this low-priority idle goal is added/removed. All original goals remain installed. */
    private static final class GatheringGoal extends Goal {
        final WeakReference<EnderMan> actor;
        final Group group;
        final Member member;

        GatheringGoal(EnderMan actor, Group group, Member member) {
            this.actor = new WeakReference<>(actor);
            this.group = group;
            this.member = member;
            setFlags(EnumSet.of(Flag.MOVE, Flag.LOOK));
        }

        @Override public boolean canUse() { return valid(); }
        @Override public boolean canContinueToUse() { return valid(); }
        @Override public boolean requiresUpdateEveryTick() { return true; }

        private boolean valid() {
            EnderMan mob = actor.get();
            if (!member.active || group.cancelled || mob == null || !(mob.level() instanceof ServerLevel level)) return false;
            State state = STATES.get(level);
            if (!enabled(level) || state == null || state.group != group
                    || !validObserver(level, group) || !idle(mob, this)
                    || !proofStillSafe(level, group.plan.proof())) {
                group.cancelled = true;
                return false;
            }
            // Revalidate the complete swept route before native navigation can move this tick.
            if (!onRoute(mob, member.plan) || !insideProof(mob, group.plan.proof()) || (!member.arrived && level.getGameTime() >= group.arrivalDeadline)) {
                group.cancelled = true;
                return false;
            }
            return true;
        }

        @Override public void start() {
            EnderMan mob = actor.get();
            if (mob == null || mob.getNavigation().isInProgress()
                    || !(mob.getNavigation() instanceof IdleNavigationState idleNavigation)) {
                group.cancelled = true;
                return;
            }
            // The old completed path may compare sameAs ours, and even stationary actors can retain
            // a delayed request to an old wander target. Clear only this confirmed idle navigator.
            idleNavigation.clearIdleRecomputation();
            mob.getNavigation().stop();
            if (!member.arrived && !mob.getNavigation().moveTo(member.path, 0.65D)) group.cancelled = true;
        }

        @Override public void tick() {
            // Navigation runs after goal selection. This check also covers reduced-rate goal cleanup.
            if (!valid()) stopOwnedPath();
        }

        @Override public void stop() {
            if (member.active) group.cancelled = true;
            stopOwnedPath();
        }

        private void stopOwnedPath() {
            EnderMan mob = actor.get();
            if (mob != null && mob.getNavigation().getPath() == member.path) {
                if (mob.getNavigation() instanceof IdleNavigationState idleNavigation) idleNavigation.clearIdleRecomputation();
                mob.getNavigation().stop();
                mob.getMoveControl().setWantedPosition(mob.getX(), mob.getY(), mob.getZ(), 0);
            }
        }
    }

    /** Per-attempt cached reads include heightmap reads; missing/unprimed chunks fail closed. */
    private static final class Probe {
        final ServerLevel level;
        final Map<BlockPos, BlockState> blocks = new HashMap<>();
        final Map<Long, Boolean> columns = new HashMap<>();
        final Set<BlockPos> floors = new LinkedHashSet<>();
        final Set<BlockPos> air = new LinkedHashSet<>();
        final Set<BlockPos> voidColumns = new LinkedHashSet<>();
        int count;
        boolean exhausted;

        Probe(ServerLevel level) { this.level = level; }

        BlockState block(BlockPos pos) {
            BlockState cached = blocks.get(pos);
            if (cached != null) return cached;
            if (count >= MAX_BLOCK_PROBES) { exhausted = true; return null; }
            count++;
            LevelChunk chunk = loaded(level, pos);
            if (chunk == null || level.isOutsideBuildHeight(pos)) return null;
            BlockState state = chunk.getBlockState(pos);
            blocks.put(pos.immutable(), state);
            return state;
        }

        boolean floor(BlockPos pos) {
            BlockState block = block(pos);
            if (block == null || !block.is(Blocks.END_STONE)) return false;
            floors.add(pos.immutable());
            return true;
        }

        boolean air(BlockPos pos) {
            BlockState block = block(pos);
            if (block == null || !block.isAir()) return false;
            air.add(pos.immutable());
            return true;
        }

        boolean voidColumn(BlockPos pos) {
            long key = BlockPos.asLong(pos.getX(), 0, pos.getZ());
            Boolean cached = columns.get(key);
            if (cached != null) return cached;
            if (count >= MAX_BLOCK_PROBES) { exhausted = true; return false; }
            count++;
            boolean empty = emptyLoadedColumn(level, pos);
            columns.put(key, empty);
            if (empty) voidColumns.add(pos.immutable());
            return empty;
        }

        boolean standing(BlockPos feet) {
            for (int x = -1; x <= 1; x++) for (int z = -1; z <= 1; z++)
                if (!floor(feet.offset(x, -1, z))) return false;
            for (int y = 0; y < 3; y++) if (!air(feet.above(y))) return false;
            return true;
        }

        Proof proof() { return new Proof(List.copyOf(floors), List.copyOf(air), List.copyOf(voidColumns)); }
    }

    private EndermanVoidGatheringService() {}

    private static boolean enabled(ServerLevel level) {
        return level.dimension().equals(Level.END) && AsobibaTweaksConfig.ENDERMAN_VOID_GATHERING_ENABLED.getAsBoolean();
    }

    private static LevelChunk loaded(ServerLevel level, BlockPos pos) {
        return level.getChunkSource().getChunkNow(pos.getX() >> 4, pos.getZ() >> 4);
    }

    static boolean emptyLoadedColumn(ServerLevel level, BlockPos pos) {
        LevelChunk chunk = loaded(level, pos);
        return chunk != null && chunk.hasPrimedHeightmap(Heightmap.Types.WORLD_SURFACE)
                && chunk.getHeight(Heightmap.Types.WORLD_SURFACE, pos.getX() & 15, pos.getZ() & 15) < level.getMinBuildHeight();
    }

    private static boolean idle(EnderMan mob, GatheringGoal own) {
        if (!mob.isAlive() || mob.isRemoved() || mob.isNoAi() || !mob.onGround() || mob.isPassenger()
                || mob.isVehicle() || mob.isLeashed() || mob.isOnFire() || mob.isInWaterOrBubble()
                || mob.isCreepy() || mob.hasBeenStaredAt() || mob.getRemainingPersistentAngerTime() > 0
                || mob.getPersistentAngerTarget() != null || mob.getTarget() != null || mob.hurtTime > 0
                || mob.getCarriedBlock() != null || mob.getPersistentData().getBoolean("asobibatweaks_micro_active")
                || UniversalBondData.isBonded(mob) || mob.getBbWidth() > 0.9F || mob.getBbHeight() > 3.0F
                || mob.getLastHurtByMob() != null && mob.tickCount - mob.getLastHurtByMobTimestamp() < 200
                || mob.getBrain().hasMemoryValue(MemoryModuleType.ATTACK_TARGET)
                || mob.getBrain().hasMemoryValue(MemoryModuleType.WALK_TARGET)
                || mob.getBrain().hasMemoryValue(MemoryModuleType.HURT_BY)
                || mob.getBrain().hasMemoryValue(MemoryModuleType.AVOID_TARGET)
                || mob.getBrain().hasMemoryValue(MemoryModuleType.IS_PANICKING)) return false;
        if (own == null && (mob.getNavigation().isInProgress() || mob.getDeltaMovement().horizontalDistanceSqr() > 0.0025D)) return false;
        if (own != null && (mob.getNavigation().isInProgress() && mob.getNavigation().getPath() != own.member.path
                || mob.getDeltaMovement().horizontalDistanceSqr() > 0.09D)) return false;
        if (mob.targetSelector.getAvailableGoals().stream().anyMatch(goal -> goal.isRunning())) return false;
        return mob.goalSelector.getAvailableGoals().stream().noneMatch(goal -> goal.isRunning()
                && goal.getGoal() != own && !(goal.getGoal() instanceof LookAtPlayerGoal)
                && !(goal.getGoal() instanceof RandomLookAroundGoal)
                && (goal.getFlags().contains(Goal.Flag.MOVE) || goal.getFlags().contains(Goal.Flag.LOOK)
                    || goal.getFlags().contains(Goal.Flag.TARGET) || goal.getFlags().contains(Goal.Flag.JUMP)));
    }

    /** Bounded production planner, also exercised directly by real-engine GameTests. */
    static Plan plan(ServerLevel level, ServerPlayer observer) {
        State state = STATES.computeIfAbsent(level, ignored -> new State());
        state.probes = 0;
        if (!enabled(level) || observer.serverLevel() != level || !AmbientOddityService.safePlayer(observer)) return null;
        List<Entity> sampled = new ArrayList<>();
        level.getEntities(EntityTypeTest.forClass(Entity.class), observer.getBoundingBox().inflate(32, 8, 32),
                Entity::isAlive, sampled, MAX_QUERY_RESULTS);
        if (sampled.size() >= MAX_QUERY_RESULTS || sampled.stream().anyMatch(entity -> entity instanceof Monster monster
                && (!(monster instanceof EnderMan enderman) || !idle(enderman, null)))) return null;
        List<EnderMan> candidates = sampled.stream().filter(EnderMan.class::isInstance).map(EnderMan.class::cast)
                .filter(mob -> idle(mob, null) && mob.distanceToSqr(observer) >= 64 && mob.distanceToSqr(observer) <= 576)
                .sorted(Comparator.comparingDouble(observer::distanceToSqr)).toList();
        if (candidates.size() < 2) return null;
        Probe probe = new Probe(level);
        for (EnderMan seed : candidates) {
            BlockPos seedFeet = seed.blockPosition();
            for (Direction direction : OUTWARD) {
                if (probe.exhausted) break;
                BlockPos firstVoid = null;
                for (int distance = 2; distance <= 5; distance++) {
                    BlockPos check = seedFeet.relative(direction, distance);
                    if (probe.voidColumn(check)) { firstVoid = check; break; }
                }
                if (firstVoid == null) continue;
                BlockPos base = firstVoid.relative(direction.getOpposite(), 2);
                Direction lateral = direction.getClockWise();
                List<PlannedMember> members = new ArrayList<>();
                // Alternating anchors keeps the scene local instead of stretching toward a distant mob.
                for (int offset : new int[] { 0, 2, -2, 4 }) {
                    if (members.size() >= 2 && probe.count > MAX_BLOCK_PROBES - 30) break;
                    BlockPos anchor = base.relative(lateral, offset);
                    BlockPos rim = anchor.relative(direction, 2);
                    if (!probe.voidColumn(rim) || !probe.voidColumn(rim.relative(direction, 2)) || !probe.standing(anchor)) continue;
                    EnderMan best = candidates.stream().filter(mob -> members.stream().noneMatch(member -> member.entityId().equals(mob.getUUID())))
                            .filter(mob -> mob.blockPosition().getY() == anchor.getY()
                                    && mob.position().distanceToSqr(Vec3.atBottomCenterOf(anchor)) <= MAX_ROUTE_LENGTH * MAX_ROUTE_LENGTH)
                            .min(Comparator.comparingDouble(mob -> mob.position().distanceToSqr(Vec3.atBottomCenterOf(anchor)))).orElse(null);
                    if (best == null) continue;
                    List<BlockPos> route = route(best, anchor, probe);
                    if (route == null) continue;
                    members.add(new PlannedMember(best.getUUID(), best.position(), anchor, route));
                    if (members.size() >= MAX_MEMBERS) break;
                }
                if (members.size() < 2 || probe.exhausted) continue;
                int min = members.stream().mapToInt(member -> lateralCoordinate(member.anchor(), lateral)).min().orElse(0);
                int max = members.stream().mapToInt(member -> lateralCoordinate(member.anchor(), lateral)).max().orElse(0);
                boolean straight = true;
                // Every intervening edge cell is supported inward and entirely empty outward.
                for (int coordinate = min; coordinate <= max; coordinate++) {
                    BlockPos anchor = lateral.getAxis() == Direction.Axis.X
                            ? new BlockPos(coordinate, base.getY(), base.getZ()) : new BlockPos(base.getX(), base.getY(), coordinate);
                    if (!probe.floor(anchor.relative(direction).below()) || !probe.voidColumn(anchor.relative(direction, 2))) { straight = false; break; }
                }
                if (!straight || probe.exhausted) continue;
                state.probes = probe.count;
                return new Plan(direction, members, probe.count, probe.proof());
            }
            if (probe.exhausted) break;
        }
        state.probes = probe.count;
        return null;
    }

    private static int lateralCoordinate(BlockPos pos, Direction lateral) {
        return lateral.getAxis() == Direction.Axis.X ? pos.getX() : pos.getZ();
    }

    /** A swept corridor for the actual position -> first node center -> final native node. */
    private static List<BlockPos> route(EnderMan mob, BlockPos anchor, Probe probe) {
        Vec3 start = mob.position();
        Vec3 end = Vec3.atBottomCenterOf(anchor);
        if (Math.abs(start.y - end.y) > 0.1D || start.distanceToSqr(end) > MAX_ROUTE_LENGTH * MAX_ROUTE_LENGTH) return null;
        Vec3 center = Vec3.atBottomCenterOf(mob.blockPosition());
        Set<BlockPos> swept = new LinkedHashSet<>();
        List<BlockPos> nodes = new ArrayList<>();
        // Native navigation can skip the first node when already close enough to its center.
        Vec3[][] segments = { { start, center }, { center, end }, { start, end } };
        for (Vec3[] segment : segments) {
            int steps = Math.max(1, Mth.ceil(segment[0].distanceTo(segment[1]) * 4));
            for (int i = 0; i <= steps; i++) {
                Vec3 point = segment[0].lerp(segment[1], (double)i / steps);
                BlockPos node = BlockPos.containing(point.x, end.y, point.z);
                if (nodes.isEmpty() || !nodes.getLast().equals(node)) nodes.add(node);
                // More than the actor's half-width, covering the entire swept body, not only nodes.
                for (int x = Mth.floor(point.x - 0.49D); x <= Mth.floor(point.x + 0.49D); x++)
                    for (int z = Mth.floor(point.z - 0.49D); z <= Mth.floor(point.z + 0.49D); z++)
                        swept.add(new BlockPos(x, anchor.getY(), z));
            }
        }
        Set<BlockPos> required = new LinkedHashSet<>();
        for (BlockPos feet : swept) {
            for (int x = -1; x <= 1; x++) for (int z = -1; z <= 1; z++) required.add(feet.offset(x, -1, z));
            for (int y = 0; y < 3; y++) required.add(feet.above(y));
        }
        long unread = required.stream().filter(pos -> !probe.blocks.containsKey(pos)).count();
        // Preserve room for the common straight rim rather than exhausting a valid smaller group.
        if (probe.count + unread > MAX_BLOCK_PROBES - 16) return null;
        for (BlockPos feet : swept) if (!probe.standing(feet)) return null;
        if (!nodes.getLast().equals(anchor)) nodes.add(anchor);
        return nodes;
    }

    static boolean attempt(ServerPlayer observer, double roll) {
        ServerLevel level = observer.serverLevel();
        if (!enabled(level)) return false;
        State state = STATES.computeIfAbsent(level, ignored -> new State());
        if (state.group != null || state.cooldownUntil > level.getGameTime() || !Double.isFinite(roll) || roll < 0 || roll >= 1) return false;
        // Independent cheap roll: Ominous never participates, and failed rolls do no world probing.
        if (roll >= AsobibaTweaksConfig.ENDERMAN_VOID_GATHERING_CHANCE.getAsDouble()) return false;
        Plan plan = plan(level, observer);
        if (plan == null) return false;
        Group group = new Group(observer.getUUID(), plan, level.getGameTime(), 120 + level.random.nextInt(81));
        for (PlannedMember planned : plan.members()) {
            if (!(level.getEntity(planned.entityId()) instanceof EnderMan mob) || !idle(mob, null)) return false;
            group.members.add(new Member(mob, planned, group));
        }
        state.group = group;
        state.cooldownUntil = level.getGameTime() + COOLDOWN;
        for (Member member : group.members) {
            EnderMan mob = member.goal.actor.get();
            if (mob != null) mob.goalSelector.addGoal(6, member.goal);
        }
        return true;
    }

    private static boolean proofStillSafe(ServerLevel level, Proof proof) {
        for (BlockPos pos : proof.floors()) {
            LevelChunk chunk = loaded(level, pos);
            if (chunk == null || !chunk.getBlockState(pos).is(Blocks.END_STONE)) return false;
        }
        for (BlockPos pos : proof.air()) {
            LevelChunk chunk = loaded(level, pos);
            if (chunk == null || !chunk.getBlockState(pos).isAir()) return false;
        }
        for (BlockPos pos : proof.voidColumns()) if (!emptyLoadedColumn(level, pos)) return false;
        return true;
    }

    private static boolean validObserver(ServerLevel level, Group group) {
        if (!(level.getEntity(group.observer) instanceof ServerPlayer observer) || !AmbientOddityService.safePlayer(observer)) return false;
        for (Member member : group.members) if (member.active) {
            double distance = observer.position().distanceToSqr(Vec3.atBottomCenterOf(member.plan.anchor()));
            if (distance < 36 || distance > 1024) return false;
        }
        return true;
    }

    private static boolean onRoute(EnderMan mob, PlannedMember plan) {
        if (Math.abs(mob.getY() - plan.anchor().getY()) > 0.15D) return false;
        for (BlockPos pos : plan.route()) if (mob.position().distanceToSqr(Vec3.atBottomCenterOf(pos)) <= 1.0D) return true;
        return false;
    }

    private static boolean insideProof(EnderMan mob, Proof proof) {
        double halfWidth = mob.getBbWidth() / 2.0D;
        for (int x = Mth.floor(mob.getX() - halfWidth); x <= Mth.floor(mob.getX() + halfWidth); x++)
            for (int z = Mth.floor(mob.getZ() - halfWidth); z <= Mth.floor(mob.getZ() + halfWidth); z++) {
                BlockPos feet = new BlockPos(x, mob.getBlockY(), z);
                for (int dx = -1; dx <= 1; dx++) for (int dz = -1; dz <= 1; dz++)
                    if (!proof.floors().contains(feet.offset(dx, -1, dz))) return false;
                for (int y = 0; y < 3; y++) if (!proof.air().contains(feet.above(y))) return false;
            }
        return true;
    }

    public static void tick(ServerLevel level) {
        if (!enabled(level)) { stop(level); return; }
        State state = STATES.computeIfAbsent(level, ignored -> new State());
        maintain(level, state);
        long now = level.getGameTime();
        if (state.group != null || now < state.cooldownUntil || now < state.nextCheck || level.players().isEmpty()) return;
        state.nextCheck = now + CHECK_INTERVAL;
        ServerPlayer player = level.players().get(Math.floorMod(state.playerCursor++, level.players().size()));
        attempt(player, level.random.nextDouble());
    }

    /** Used only by the narrow navigation hook to suppress unvalidated native recomputation. */
    public static boolean ownsNavigation(EnderMan mob) {
        if (!(mob.level() instanceof ServerLevel level)) return false;
        State state = STATES.get(level);
        if (state == null || state.group == null) return false;
        for (Member member : state.group.members) if (member.active && member.plan.entityId().equals(mob.getUUID()))
            return mob.getNavigation().getPath() == member.path;
        return false;
    }

    /** Post-AI gaze; priority AI is checked before touching the pose and no look request is queued. */
    public static void onEntityTick(EnderMan mob) {
        if (!(mob.level() instanceof ServerLevel level)) return;
        State state = STATES.get(level);
        if (state == null || state.group == null || state.group.members.stream()
                .noneMatch(member -> member.active && member.plan.entityId().equals(mob.getUUID()))) return;
        maintain(level, state);
        Group group = state.group;
        if (group == null || !group.dwelling) return;
        for (Member member : group.members) if (member.active && member.plan.entityId().equals(mob.getUUID())) {
            if (!idle(mob, member.goal)) { cancel(level, state); return; }
            Direction direction = group.plan.direction();
            float yaw = direction.toYRot();
            float turn = Mth.clamp(Mth.wrapDegrees(yaw - mob.getYHeadRot()), -15, 15);
            mob.setYHeadRot(mob.getYHeadRot() + turn);
            mob.setYRot(mob.getYHeadRot());
            mob.yBodyRot = mob.getYRot();
            mob.setXRot(0);
            return;
        }
    }

    private static void maintain(ServerLevel level, State state) {
        Group group = state.group;
        if (group == null) return;
        long now = level.getGameTime();
        if (!enabled(level) || group.cancelled || !validObserver(level, group) || !proofStillSafe(level, group.plan.proof())) {
            cancel(level, state); return;
        }
        for (Member member : group.members) if (member.active && now >= member.releaseAt) release(member);
        for (Member member : group.members) if (member.active) {
            if (!(level.getEntity(member.plan.entityId()) instanceof EnderMan mob) || !idle(mob, member.goal)
                    || !onRoute(mob, member.plan) || !insideProof(mob, group.plan.proof()) || loaded(level, mob.blockPosition()) == null) {
                cancel(level, state); return;
            }
            if (!member.arrived && mob.getNavigation().getPath() == member.path && member.path.isDone()) {
                if (mob.position().distanceToSqr(Vec3.atBottomCenterOf(member.plan.anchor())) > 0.64D) { cancel(level, state); return; }
                member.arrived = true;
            }
            if (member.arrived && mob.position().distanceToSqr(Vec3.atBottomCenterOf(member.plan.anchor())) > 0.64D) {
                cancel(level, state); return;
            }
        }
        if (!group.dwelling && group.members.stream().allMatch(member -> member.arrived)) {
            group.dwelling = true;
            for (int index = 0; index < group.members.size(); index++) group.members.get(index).releaseAt = now + group.duration + index * RELEASE_STAGGER;
        }
        if (!group.dwelling && now >= group.arrivalDeadline) { cancel(level, state); return; }
        if (group.members.stream().noneMatch(member -> member.active)) state.group = null;
    }

    private static void release(Member member) {
        member.active = false;
        EnderMan mob = member.goal.actor.get();
        if (mob != null) {
            member.goal.stopOwnedPath();
            mob.goalSelector.removeGoal(member.goal);
        }
    }

    private static void cancel(ServerLevel level, State state) {
        Group group = state.group;
        state.group = null;
        if (group != null) {
            group.cancelled = true;
            for (Member member : group.members) release(member);
        }
    }

    static Snapshot snapshot(ServerLevel level) {
        State state = STATES.get(level);
        if (state == null) return new Snapshot(null, List.of(), 0, 0, false);
        Group group = state.group;
        if (group == null) return new Snapshot(null, List.of(), state.cooldownUntil, state.probes, false);
        List<MemberSnapshot> members = group.members.stream().filter(member -> member.active)
                .map(member -> new MemberSnapshot(member.plan.entityId(), member.plan.origin(), member.plan.anchor(), member.releaseAt, member.arrived)).toList();
        return new Snapshot(group.plan.direction(), members, state.cooldownUntil, state.probes, group.dwelling);
    }

    public static void stop(ServerLevel level) {
        State state = STATES.remove(level);
        if (state != null) cancel(level, state);
    }

    public static void reset() {
        for (State state : List.copyOf(STATES.values())) cancel(null, state);
        STATES.clear();
    }
}
