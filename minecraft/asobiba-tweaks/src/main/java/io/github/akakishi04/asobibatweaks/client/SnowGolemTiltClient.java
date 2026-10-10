package io.github.akakishi04.asobibatweaks.client;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import io.github.akakishi04.asobibatweaks.feature.SnowGolemTiltState;
import java.lang.ref.WeakReference;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;
import net.minecraft.client.Camera;
import net.minecraft.client.CameraType;
import net.minecraft.client.Minecraft;
import net.minecraft.client.multiplayer.ClientLevel;
import net.minecraft.util.RandomSource;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.animal.SnowGolem;
import net.minecraft.world.level.ClipContext;
import net.minecraft.world.level.entity.EntityTypeTest;
import net.minecraft.world.phys.HitResult;
import net.minecraft.world.phys.Vec3;
import net.neoforged.bus.api.SubscribeEvent;
import net.neoforged.neoforge.client.event.ClientTickEvent;
import net.neoforged.neoforge.client.event.RenderLevelStageEvent;

/** Observer-local cosmetic only. No entity rotation, AI, packets, NBT or gameplay RNG changes. */
public final class SnowGolemTiltClient {
    private static final SnowGolemTiltState STATE = new SnowGolemTiltState();
    private static final Map<UUID, Integer> TRACKED = new HashMap<>();
    private static final Map<UUID, Boolean> LOOKING = new HashMap<>();
    private static final RandomSource RANDOM = RandomSource.create();
    private static WeakReference<ClientLevel> previousLevel = new WeakReference<>(null);
    private static WeakReference<Entity> previousCamera = new WeakReference<>(null);
    private static CameraType previousPerspective;
    private static long ticks;
    private static long lastFrame = -100;

    @SubscribeEvent
    public void onTick(ClientTickEvent.Post event) {
        Minecraft minecraft = Minecraft.getInstance();
        if (!context(minecraft)) return;
        ticks++;
        if (ticks - lastFrame > 5) { clearState(); return; }
        STATE.tick(ticks);
        var candidates = new ArrayList<SnowGolem>();
        minecraft.level.getEntities(EntityTypeTest.forClass(SnowGolem.class),
                minecraft.player.getBoundingBox().inflate(24), Entity::isAlive, candidates, 33);
        if (candidates.size() > 32) { clearState(); return; }
        TRACKED.clear();
        for (SnowGolem golem : candidates) TRACKED.put(golem.getUUID(), golem.getId());
        STATE.retain(TRACKED.keySet());
        LOOKING.keySet().retainAll(TRACKED.keySet());
        for (SnowGolem golem : candidates) {
            STATE.update(golem.getUUID(), ticks, eligible(golem, minecraft),
                    LOOKING.getOrDefault(golem.getUUID(), true),
                    AsobibaTweaksConfig.SNOW_GOLEM_TILT_CHANCE.getAsDouble(), RANDOM::nextDouble, RANDOM::nextBoolean);
        }
    }

    /** Runs before entity rendering with this frame's actual camera/frustum, even for culled golems. */
    @SubscribeEvent
    public void onFrame(RenderLevelStageEvent event) {
        if (event.getStage() != RenderLevelStageEvent.Stage.AFTER_SKY) return;
        Minecraft minecraft = Minecraft.getInstance();
        if (!context(minecraft)) return;
        lastFrame = ticks;
        Camera camera = event.getCamera();
        for (var entry : TRACKED.entrySet()) {
            Entity entity = minecraft.level.getEntity(entry.getValue());
            if (!(entity instanceof SnowGolem golem) || !golem.getUUID().equals(entry.getKey())) {
                STATE.cancel(entry.getKey());
                LOOKING.put(entry.getKey(), true);
                continue;
            }
            boolean available = eligible(golem, minecraft);
            boolean visible = available && event.getFrustum().isVisible(golem.getBoundingBox());
            // Only the single armed cosmetic needs an expensive line-of-sight ray each frame.
            if (visible && STATE.tiltDegrees(entry.getKey()) != 0) {
                Vec3 head = golem.getEyePosition();
                visible = minecraft.level.clip(new ClipContext(camera.getPosition(), head,
                        ClipContext.Block.COLLIDER, ClipContext.Fluid.NONE, minecraft.player)).getType() == HitResult.Type.MISS;
            }
            LOOKING.put(entry.getKey(), visible);
            STATE.observe(entry.getKey(), available, visible);
        }
    }

    public static float roll(Entity entity) {
        Minecraft minecraft = Minecraft.getInstance();
        if (!context(minecraft) || !(entity instanceof SnowGolem golem)
                || entity.level() != minecraft.level || !eligible(golem, minecraft)
                || !LOOKING.getOrDefault(entity.getUUID(), false)
                || TRACKED.getOrDefault(entity.getUUID(), -1) != entity.getId()) return 0;
        return STATE.tiltDegrees(entity.getUUID()) * (float)(AsobibaTweaksConfig.SNOW_GOLEM_TILT_ANGLE.getAsDouble() / 6.0)
                * ((float)Math.PI / 180.0F);
    }

    private static boolean eligible(SnowGolem golem, Minecraft minecraft) {
        return golem.isAlive() && !golem.isRemoved() && !golem.isInvisibleTo(minecraft.player)
                && !golem.isOnFire() && !golem.isInWaterOrBubble() && golem.hurtTime == 0
                && golem.getTarget() == null && !golem.isPassenger() && !golem.isVehicle()
                && golem.getDeltaMovement().lengthSqr() < 0.0025
                && golem.position().distanceToSqr(new Vec3(golem.xo, golem.yo, golem.zo)) < 0.0025
                && golem.distanceToSqr(minecraft.player) >= 4 && golem.distanceToSqr(minecraft.player) <= 24 * 24;
    }

    private static boolean context(Minecraft minecraft) {
        ClientLevel level = minecraft.level;
        Camera camera = minecraft.gameRenderer.getMainCamera();
        Entity cameraEntity = minecraft.getCameraEntity();
        CameraType perspective = minecraft.options.getCameraType();
        boolean changed = previousLevel.get() != level || previousCamera.get() != cameraEntity
                || previousPerspective != perspective;
        if (changed) {
            if (previousLevel.get() != level) STATE.clear();
            clearState();
            previousLevel = new WeakReference<>(level);
            previousCamera = new WeakReference<>(cameraEntity);
            previousPerspective = perspective;
        }
        if (level == null || minecraft.player == null || cameraEntity != minecraft.player
                || !camera.isInitialized() || camera.getEntity() != cameraEntity
                || cameraEntity.level() != level || minecraft.isPaused() || minecraft.screen != null
                || minecraft.player.isSpectator() || !minecraft.player.isAlive()
                || !AsobibaTweaksConfig.SNOW_GOLEM_HEAD_TILT_ENABLED.getAsBoolean()) {
            clearState();
            return false;
        }
        return true;
    }

    private static void clearState() {
        STATE.resetObservation();
        TRACKED.clear();
        LOOKING.clear();
        lastFrame = -100;
    }
}
