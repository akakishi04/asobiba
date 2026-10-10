package io.github.akakishi04.asobibatweaks.client;

import com.mojang.blaze3d.vertex.PoseStack;
import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import io.github.akakishi04.asobibatweaks.feature.CloudLineState;
import java.lang.ref.WeakReference;
import net.minecraft.client.Camera;
import net.minecraft.client.CameraType;
import net.minecraft.client.CloudStatus;
import net.minecraft.client.Minecraft;
import net.minecraft.client.multiplayer.ClientLevel;
import net.minecraft.client.renderer.DimensionSpecialEffects;
import net.minecraft.util.RandomSource;
import net.minecraft.world.effect.MobEffects;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.level.Level;
import net.minecraft.world.level.material.FogType;
import net.minecraft.world.phys.Vec3;
import net.neoforged.bus.api.SubscribeEvent;
import net.neoforged.neoforge.client.event.ClientPlayerNetworkEvent;
import net.neoforged.neoforge.client.event.ClientTickEvent;
import net.neoforged.neoforge.event.level.LevelEvent;
import org.joml.Matrix4f;

/** Observer-only; no server events, world changes, sounds, packets or player rewards. */
public final class CloudLineClient {
    private static final CloudLineState STATE = new CloudLineState();
    private static final RandomSource RANDOM = RandomSource.create();
    private static WeakReference<ClientLevel> previousLevel = new WeakReference<>(null);
    private static WeakReference<Entity> previousCamera = new WeakReference<>(null);
    private static CameraType previousPerspective;
    private static CloudStatus previousCloudQuality;
    private static Vec3 previousPosition;
    private static long ticks;
    private static long lastCloudFrame = -100L;

    @SubscribeEvent
    public void onTick(ClientTickEvent.Post event) {
        Minecraft minecraft = Minecraft.getInstance();
        if (minecraft.level != null && !minecraft.isPaused()) ticks++;
        if (!context(minecraft)) return;
        boolean recentCloudFrame = ticks >= lastCloudFrame && ticks - lastCloudFrame <= 5L;
        // Use yaw, not pitch: looking straight up still has a stable horizontal heading.
        Vec3 forward = Vec3.directionFromRotation(0.0F, minecraft.gameRenderer.getMainCamera().getYRot());
        Vec3 camera = minecraft.gameRenderer.getMainCamera().getPosition();
        STATE.update(ticks, recentCloudFrame, camera.x, camera.z, forward.x, forward.z,
                AsobibaTweaksConfig.CLOUD_LINE_CHANCE.getAsDouble(), RANDOM::nextDouble, RANDOM::nextBoolean);
        if (!STATE.active()) CloudLineRenderer.release();
    }

    @SubscribeEvent
    public void onLogout(ClientPlayerNetworkEvent.LoggingOut event) {
        clearWorld();
    }

    @SubscribeEvent
    public void onUnload(LevelEvent.Unload event) {
        if (event.getLevel() == previousLevel.get()) clearWorld();
    }

    /** Invoked only at the end of vanilla's cloud pass, with the same matrices and camera. */
    public static void render(PoseStack poses, Matrix4f view, Matrix4f projection,
            float partialTick, double cameraX, double cameraY, double cameraZ) {
        Minecraft minecraft = Minecraft.getInstance();
        if (!context(minecraft)) return;
        lastCloudFrame = ticks;
        CloudLineRenderer.render(STATE.snapshot(partialTick), minecraft.options.getCloudsType(),
                minecraft.level.getCloudColor(partialTick), minecraft.level.effects().getCloudHeight(),
                poses, view, projection, cameraX, cameraY, cameraZ);
    }

    private static boolean context(Minecraft minecraft) {
        ClientLevel level = minecraft.level;
        Camera camera = minecraft.gameRenderer.getMainCamera();
        Entity cameraEntity = minecraft.getCameraEntity();
        CameraType perspective = minecraft.options.getCameraType();
        CloudStatus quality = minecraft.options.getCloudsType();
        if (previousLevel.get() != level) {
            clearWorld();
            previousLevel = new WeakReference<>(level);
        }
        Vec3 position = camera.getPosition();
        if (previousCamera.get() != cameraEntity || previousPerspective != perspective
                || previousCloudQuality != quality || previousPosition != null
                && previousPosition.distanceToSqr(position) > 256.0D * 256.0D) {
            cancel();
        }
        previousCamera = new WeakReference<>(cameraEntity);
        previousPerspective = perspective;
        previousCloudQuality = quality;
        previousPosition = position;
        if (level == null || minecraft.player == null || cameraEntity != minecraft.player
                || !camera.isInitialized() || camera.getEntity() != cameraEntity
                || cameraEntity.level() != level || minecraft.isPaused() || minecraft.screen != null
                || !minecraft.player.isAlive() || minecraft.player.isSpectator()
                || camera.getFluidInCamera() != FogType.NONE || !level.tickRateManager().runsNormally()
                || minecraft.player.hasEffect(MobEffects.BLINDNESS) || minecraft.player.hasEffect(MobEffects.DARKNESS)
                || quality == CloudStatus.OFF || minecraft.options.getEffectiveRenderDistance() < 8
                || !level.dimension().equals(Level.OVERWORLD) || !level.dimensionType().hasSkyLight()
                || !Float.isFinite(level.effects().getCloudHeight())
                // Leave replacement dimension/cloud renderers alone, including custom Overworld effects.
                || level.effects().getClass() != DimensionSpecialEffects.OverworldEffects.class
                || !AsobibaTweaksConfig.CLOUD_LINE_ENABLED.getAsBoolean()) {
            STATE.advance(ticks);
            cancel();
            return false;
        }
        return true;
    }

    private static void cancel() {
        STATE.resetObservation();
        CloudLineRenderer.release();
        lastCloudFrame = -100L;
    }

    private static void clearWorld() {
        STATE.clear();
        CloudLineRenderer.release();
        previousLevel.clear();
        previousCamera.clear();
        previousPerspective = null;
        previousCloudQuality = null;
        previousPosition = null;
        ticks = 0L;
        lastCloudFrame = -100L;
    }
}
