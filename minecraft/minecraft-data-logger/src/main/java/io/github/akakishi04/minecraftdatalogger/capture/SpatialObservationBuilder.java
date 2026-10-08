package io.github.akakishi04.minecraftdatalogger.capture;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import java.util.Comparator;
import java.util.List;
import net.minecraft.core.BlockPos;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.level.ClipContext;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.BlockHitResult;
import net.minecraft.world.phys.HitResult;
import net.minecraft.world.phys.Vec3;

/**
 * Optional bounded spatial context for offline LLM/agent dataset assembly.
 * Only reads already-loaded server world state and never creates chunk tickets.
 */
public final class SpatialObservationBuilder {
    private static final double LOOK_DISTANCE = 6.0D;
    private static final double NEARBY_RADIUS = 12.0D;
    private static final int MAX_RECORDED_ENTITIES = 16;
    private static final int MAX_RAY_SAMPLES = 16;

    private SpatialObservationBuilder() {}

    public static void attach(JsonObject observation, ServerPlayer player) {
        ServerLevel level = player.serverLevel();
        JsonObject viewTarget = buildTarget(level, player);
        observation.add("crosshair_target", viewTarget);

        List<LivingEntity> nearby = level.getEntitiesOfClass(
                LivingEntity.class, player.getBoundingBox().inflate(NEARBY_RADIUS),
                entity -> entity != player && entity.isAlive());
        nearby.sort(Comparator.comparingDouble(player::distanceToSqr));

        JsonArray summary = new JsonArray();
        for (int i = 0; i < Math.min(MAX_RECORDED_ENTITIES, nearby.size()); i++) {
            LivingEntity entity = nearby.get(i);
            JsonObject row = new JsonObject();
            row.addProperty("type", BuiltInRegistries.ENTITY_TYPE
                    .getKey(entity.getType()).toString());
            row.addProperty("uuid", entity.getUUID().toString());
            row.addProperty("x", entity.getX());
            row.addProperty("y", entity.getY());
            row.addProperty("z", entity.getZ());
            row.addProperty("distance", Math.sqrt(player.distanceToSqr(entity)));
            row.addProperty("health", entity.getHealth());
            summary.add(row);
        }
        observation.add("nearby_entities", summary);
        observation.addProperty("nearby_entity_count", nearby.size());
        observation.addProperty("nearby_entities_truncated",
                nearby.size() > MAX_RECORDED_ENTITIES);
    }

    private static JsonObject buildTarget(ServerLevel level, ServerPlayer player) {
        JsonObject record = new JsonObject();
        Vec3 eye = player.getEyePosition();
        Vec3 end = eye.add(player.getViewVector(1.0F).scale(LOOK_DISTANCE));

        // A look ray can cross a chunk edge even when the player chunk is
        // loaded. Never call a world raycast along an unknown chunk span.
        for (int i = 0; i <= MAX_RAY_SAMPLES; i++) {
            Vec3 sample = eye.lerp(end, i / (double) MAX_RAY_SAMPLES);
            if (!level.hasChunkAt(BlockPos.containing(sample))) {
                record.addProperty("kind", "unloaded");
                return record;
            }
        }

        BlockHitResult blockHit = level.clip(new ClipContext(
                eye, end, ClipContext.Block.COLLIDER,
                ClipContext.Fluid.NONE, player));
        double nearestDistanceSquared = blockHit.getType() == HitResult.Type.BLOCK
                ? eye.distanceToSqr(blockHit.getLocation())
                : LOOK_DISTANCE * LOOK_DISTANCE + 0.01D;

        Entity closest = null;
        Vec3 closestHit = null;
        // Entity snapshots are queried only in a narrow six-block ray volume.
        // They cannot see through an earlier solid block collision.
        List<Entity> candidates = level.getEntities(player,
                new AABB(eye, end).inflate(1.0D),
                entity -> entity.isPickable() && !entity.isSpectator());
        for (Entity entity : candidates) {
            var intersection = entity.getBoundingBox().inflate(0.15D).clip(eye, end);
            if (intersection.isEmpty()) continue;
            double distanceSquared = eye.distanceToSqr(intersection.get());
            if (distanceSquared >= nearestDistanceSquared) continue;
            nearestDistanceSquared = distanceSquared;
            closest = entity;
            closestHit = intersection.get();
        }

        if (closest != null) {
            record.addProperty("kind", "entity");
            record.addProperty("type", BuiltInRegistries.ENTITY_TYPE
                    .getKey(closest.getType()).toString());
            record.addProperty("uuid", closest.getUUID().toString());
            record.addProperty("distance", Math.sqrt(nearestDistanceSquared));
            record.addProperty("x", closestHit.x);
            record.addProperty("y", closestHit.y);
            record.addProperty("z", closestHit.z);
        } else if (blockHit.getType() == HitResult.Type.BLOCK) {
            BlockPos pos = blockHit.getBlockPos();
            record.addProperty("kind", "block");
            record.addProperty("block", BuiltInRegistries.BLOCK
                    .getKey(level.getBlockState(pos).getBlock()).toString());
            record.addProperty("face", blockHit.getDirection().getName());
            record.addProperty("x", pos.getX());
            record.addProperty("y", pos.getY());
            record.addProperty("z", pos.getZ());
            record.addProperty("distance", Math.sqrt(nearestDistanceSquared));
        } else {
            record.addProperty("kind", "miss");
        }
        return record;
    }
}
