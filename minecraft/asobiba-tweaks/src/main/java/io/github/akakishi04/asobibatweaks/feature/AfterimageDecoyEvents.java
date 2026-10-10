package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import io.github.akakishi04.asobibatweaks.entity.AfterimageDecoyEntity;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;
import net.minecraft.core.BlockPos;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.util.Mth;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.EquipmentSlot;
import net.minecraft.world.entity.Mob;
import net.minecraft.world.level.ClipContext;
import net.minecraft.world.level.entity.EntityTypeTest;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.HitResult;
import net.minecraft.world.phys.Vec3;
import net.neoforged.bus.api.EventPriority;
import net.neoforged.bus.api.SubscribeEvent;
import net.neoforged.neoforge.event.entity.EntityLeaveLevelEvent;
import net.neoforged.neoforge.event.entity.living.LivingChangeTargetEvent;
import net.neoforged.neoforge.event.entity.living.LivingDeathEvent;
import net.neoforged.neoforge.event.entity.player.PlayerEvent;
import net.neoforged.neoforge.event.server.ServerStoppingEvent;
import net.neoforged.neoforge.event.tick.LevelTickEvent;
import net.neoforged.neoforge.event.tick.PlayerTickEvent;

/** A sprint edge and measured departure grant one strictly temporary, bounded target lease. */
public final class AfterimageDecoyEvents {
    private static final int DEPARTURE_WINDOW = 40;
    private static final String COOLDOWN = "asobibatweaks_afterimage_next_use";
    private static final int SCAN_LIMIT = 32;
    private static final double MAX_STEP_SQUARED = 1.5D * 1.5D;
    private final Map<UUID, SprintState> states = new HashMap<>();

    @SubscribeEvent
    public void onPlayerTick(PlayerTickEvent.Post event) {
        if (event.getEntity() instanceof ServerPlayer player) tickPlayer(player, player.server.overworld().getGameTime());
    }

    void tickPlayer(ServerPlayer player, long now) {
        if (!AsobibaTweaksConfig.AFTERIMAGE_DECOY_ENABLED.getAsBoolean() || !wearsAfterimage(player)
                || !player.isAlive() || player.isRemoved() || player.isSpectator() || player.isCreative()) {
            // Keep a live player's cooldown across unequipping/re-equipping and config toggles.
            SprintState old = states.get(player.getUUID());
            if (old != null) {
                endDecoy(old);
                old.departure = null;
                old.lastPosition = player.position();
                old.wasSprinting = player.isSprinting();
                old.grounded = false;
            }
            return;
        }
        SprintState state = states.get(player.getUUID());
        if (state == null || state.level != player.serverLevel()) {
            if (state != null) endDecoy(state);
            state = new SprintState(player);
            state.nextUse = Math.min(player.getPersistentData().getLong(COOLDOWN),
                    now + AsobibaTweaksConfig.AFTERIMAGE_COOLDOWN_TICKS.getAsInt());
            states.put(player.getUUID(), state);
            return; // Equipping, login or dimension change while sprinting is not a sprint edge.
        }
        if (state.decoy != null && (state.decoy.isRemoved() || state.decoy.hasExpired(player.level().getGameTime()))) endDecoy(state);
        Vec3 position = player.position();
        Vec3 step = position.subtract(state.lastPosition);
        boolean grounded = groundSprintEligible(player);
        boolean continuousStep = step.horizontalDistanceSqr() <= MAX_STEP_SQUARED && Math.abs(step.y) <= 1.0D;
        boolean sprinting = player.isSprinting();
        if (!sprinting || !grounded || !continuousStep) state.departure = null;
        if (sprinting && !state.wasSprinting && grounded && state.grounded && continuousStep
                && now >= state.nextUse && state.decoy == null) {
            state.departure = state.lastPosition;
            state.departureYaw = player.getYRot();
            state.startedAt = now;
            state.movingTicks = 0;
        }
        if (state.departure != null) {
            if (now - state.startedAt > DEPARTURE_WINDOW) {
                state.departure = null;
            } else {
                if (step.horizontalDistanceSqr() >= 0.0025D) state.movingTicks++;
                double distance = AsobibaTweaksConfig.AFTERIMAGE_TRIGGER_DISTANCE.getAsDouble();
                if (state.movingTicks >= 2
                        && position.subtract(state.departure).horizontalDistanceSqr() >= distance * distance) {
                    Vec3 departure = state.departure;
                    state.departure = null; // Exactly one attempt per genuine sprint edge.
                    if (validDeparture(player, departure)) {
                        var decoy = spawnDecoy(player, departure, state.departureYaw);
                        if (decoy != null) {
                            state.decoy = decoy;
                            state.nextUse = now + AsobibaTweaksConfig.AFTERIMAGE_COOLDOWN_TICKS.getAsInt();
                            player.getPersistentData().putLong(COOLDOWN, state.nextUse);
                        }
                    }
                }
            }
        }
        state.lastPosition = position;
        state.wasSprinting = sprinting;
        state.grounded = grounded;
    }

    static boolean wearsAfterimage(ServerPlayer player) {
        return NewEnchantments.equippedLevel(player, EquipmentSlot.CHEST, NewEnchantments.AFTERIMAGE) > 0;
    }

    private static boolean groundSprintEligible(ServerPlayer player) {
        return player.onGround() && !player.isPassenger() && !player.isFallFlying()
                && !player.isSwimming() && !player.isInWaterOrBubble() && !player.isInLava()
                && !player.getAbilities().flying && !player.isSleeping();
    }

    private static boolean validDeparture(ServerPlayer player, Vec3 origin) {
        ServerLevel level = player.serverLevel();
        if (!loadedBetween(level, origin, player.position())) return false;
        AABB body = new AABB(origin.x - 0.3D, origin.y, origin.z - 0.3D,
                origin.x + 0.3D, origin.y + 1.8D, origin.z + 0.3D);
        BlockPos feet = BlockPos.containing(origin);
        return level.getFluidState(feet).isEmpty() && level.noCollision(body)
                && level.clip(new ClipContext(origin.add(0.0D, 1.4D, 0.0D), player.getEyePosition(),
                    ClipContext.Block.COLLIDER, ClipContext.Fluid.NONE, player)).getType() == HitResult.Type.MISS;
    }

    static AfterimageDecoyEntity spawnDecoy(ServerPlayer owner, Vec3 origin, float yaw) {
        ServerLevel level = owner.serverLevel();
        var decoy = AfterimageDecoyRegistration.DECOY.get().create(level);
        if (decoy == null) return null;
        decoy.initialize(owner, origin, yaw, AsobibaTweaksConfig.AFTERIMAGE_LIFETIME_TICKS.getAsInt());
        if (!level.addFreshEntity(decoy)) return null;
        double radius = AsobibaTweaksConfig.AFTERIMAGE_TARGET_RADIUS.getAsDouble();
        int maximum = Math.min(4, AsobibaTweaksConfig.AFTERIMAGE_MAX_TARGETS.getAsInt());
        var candidates = new ArrayList<Mob>();
        level.getEntities(EntityTypeTest.forClass(Mob.class), decoy.getBoundingBox().inflate(radius),
                mob -> true, candidates, SCAN_LIMIT);
        for (Mob mob : candidates) {
            if (decoy.leaseCount() >= maximum) break;
            if (eligibleHostile(mob, owner) && mob.distanceToSqr(decoy) <= radius * radius
                    && loadedBetween(level, mob.position(), origin)
                    && loadedBetween(level, mob.position(), owner.position())
                    && mob.hasLineOfSight(owner) && mob.hasLineOfSight(decoy)) decoy.lease(mob, maximum);
        }
        return decoy;
    }

    static boolean eligibleHostile(Mob mob, ServerPlayer owner) {
        if (!mob.isAlive() || mob.isRemoved() || mob.getTarget() != owner || mob.level() != owner.level()
                || mob.isNoAi() || mob.isPassenger() || mob.isVehicle() || mob.isLeashed()
                || mob.isAlliedTo(owner) || UniversalBondData.isBonded(mob)) return false;
        // Exact vanilla types only: no bosses, raids, explosives, brains/anger memories or modded scripts.
        EntityType<?> type = mob.getType();
        return type == EntityType.ZOMBIE || type == EntityType.HUSK || type == EntityType.DROWNED
                || type == EntityType.SKELETON || type == EntityType.STRAY || type == EntityType.BOGGED
                || type == EntityType.SPIDER || type == EntityType.CAVE_SPIDER;
    }

    /** Every queried/ray-tested chunk must already exist; never cause a chunk request. */
    static boolean loadedBetween(ServerLevel level, Vec3 from, Vec3 to) {
        int minX = Mth.floor(Math.min(from.x, to.x) - 1.0D) >> 4;
        int maxX = Mth.floor(Math.max(from.x, to.x) + 1.0D) >> 4;
        int minZ = Mth.floor(Math.min(from.z, to.z) - 1.0D) >> 4;
        int maxZ = Mth.floor(Math.max(from.z, to.z) + 1.0D) >> 4;
        if (maxX - minX > 3 || maxZ - minZ > 3) return false;
        for (int x = minX; x <= maxX; x++) {
            for (int z = minZ; z <= maxZ; z++) if (!level.hasChunk(x, z)) return false;
        }
        return true;
    }

    @SubscribeEvent(priority = EventPriority.LOWEST)
    public void onChangeTarget(LivingChangeTargetEvent event) {
        if (!(event.getEntity() instanceof Mob mob)) return;
        if (event.getNewAboutToBeSetTarget() instanceof AfterimageDecoyEntity candidate && !candidate.permits(mob)) {
            // Cancellation preserves both ordinary targets and any unrelated brain state.
            event.setCanceled(true);
        }
        // A target-change event may be cancelled by another listener. Retire leases only
        // after observing the actual target in entity.tick(), never during event dispatch.
    }

    @SubscribeEvent
    public void onLevelTick(LevelTickEvent.Post event) {
        if (!(event.getLevel() instanceof ServerLevel level)) return;
        for (SprintState state : states.values()) {
            if (state.level != level || state.decoy == null) continue;
            // Also cleans up when the decoy's own chunk is no longer ticking.
            if (!AsobibaTweaksConfig.AFTERIMAGE_DECOY_ENABLED.getAsBoolean() || state.decoy.isRemoved()
                    || state.decoy.hasExpired(level.getGameTime())) endDecoy(state);
        }
    }

    @SubscribeEvent public void onLogout(PlayerEvent.PlayerLoggedOutEvent event) { forget(event.getEntity().getUUID()); }
    @SubscribeEvent public void onDimensionChange(PlayerEvent.PlayerChangedDimensionEvent event) { forget(event.getEntity().getUUID()); }
    @SubscribeEvent public void onClone(PlayerEvent.Clone event) {
        long nextUse = event.getOriginal().getPersistentData().getLong(COOLDOWN);
        if (nextUse > 0L) event.getEntity().getPersistentData().putLong(COOLDOWN, nextUse);
    }
    @SubscribeEvent public void onDeath(LivingDeathEvent event) {
        if (event.getEntity() instanceof ServerPlayer player) forget(player.getUUID());
    }
    @SubscribeEvent public void onRemoved(EntityLeaveLevelEvent event) {
        if (event.getEntity() instanceof AfterimageDecoyEntity decoy) decoy.releaseTargets();
    }
    @SubscribeEvent public void onStopping(ServerStoppingEvent event) { clear(); }

    void forget(UUID playerId) {
        SprintState state = states.remove(playerId);
        if (state != null) endDecoy(state);
    }

    void clear() {
        states.values().forEach(AfterimageDecoyEvents::endDecoy);
        states.clear();
    }

    AfterimageDecoyEntity active(UUID playerId) {
        SprintState state = states.get(playerId);
        return state == null ? null : state.decoy;
    }

    private static void endDecoy(SprintState state) {
        if (state.decoy != null) {
            state.decoy.releaseTargets();
            if (!state.decoy.isRemoved()) state.decoy.discard();
            state.decoy = null;
        }
    }

    private static final class SprintState {
        final ServerLevel level;
        Vec3 lastPosition;
        boolean wasSprinting;
        boolean grounded;
        Vec3 departure;
        float departureYaw;
        int movingTicks;
        long startedAt;
        long nextUse;
        AfterimageDecoyEntity decoy;
        SprintState(ServerPlayer player) {
            level = player.serverLevel();
            lastPosition = player.position();
            wasSprinting = player.isSprinting();
            grounded = groundSprintEligible(player);
        }
    }
}
