package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.phys.Vec3;
import net.neoforged.bus.api.SubscribeEvent;
import net.neoforged.neoforge.event.entity.player.PlayerEvent;
import net.neoforged.neoforge.event.tick.PlayerTickEvent;

public final class MovementTweaksEvents {
    private final Map<UUID, Long> wallKickCooldown = new HashMap<>();
    private final Map<UUID, Long> slideCooldown = new HashMap<>();
    private final Map<UUID, Long> ledgeCooldown = new HashMap<>();

    @SubscribeEvent
    public void onPlayerTick(PlayerTickEvent.Post event) {
        if (!(event.getEntity() instanceof ServerPlayer player)) return;
        long now = player.level().getGameTime();
        if (AsobibaTweaksConfig.WALL_KICK_ENABLED.getAsBoolean()) tryWallKick(player, now);
        if (AsobibaTweaksConfig.SLIDING_ENABLED.getAsBoolean()) trySlide(player, now);
        if (AsobibaTweaksConfig.LEDGE_CLIMB_ENABLED.getAsBoolean()) tryLedgeClimb(player, now);
    }

    private void tryWallKick(ServerPlayer player, long now) {
        if (player.onGround() || !player.horizontalCollision || player.isInWater() || player.isPassenger()) return;
        if (now - wallKickCooldown.getOrDefault(player.getUUID(), Long.MIN_VALUE / 2) < 12L) return;
        Vec3 velocity = player.getDeltaMovement();
        if (velocity.y < 0.05D) return;
        Vec3 look = player.getLookAngle();
        Vec3 away = new Vec3(-look.x, 0.0D, -look.z);
        if (away.lengthSqr() < 0.001D) return;
        away = away.normalize().scale(0.42D);
        player.setDeltaMovement(away.x, Math.max(0.48D, velocity.y), away.z);
        player.hurtMarked = true;
        wallKickCooldown.put(player.getUUID(), now);
    }

    private void trySlide(ServerPlayer player, long now) {
        if (!player.onGround() || !player.isSprinting() || !player.isShiftKeyDown() || player.isPassenger()) return;
        if (now - slideCooldown.getOrDefault(player.getUUID(), Long.MIN_VALUE / 2) < 16L) return;
        Vec3 look = player.getLookAngle();
        Vec3 horizontal = new Vec3(look.x, 0.0D, look.z);
        if (horizontal.lengthSqr() < 0.001D) return;
        horizontal = horizontal.normalize().scale(0.55D);
        Vec3 current = player.getDeltaMovement();
        player.setDeltaMovement(current.x + horizontal.x, current.y, current.z + horizontal.z);
        player.hurtMarked = true;
        slideCooldown.put(player.getUUID(), now);
    }

    private void tryLedgeClimb(ServerPlayer player, long now) {
        if (player.onGround() || !player.horizontalCollision || player.isShiftKeyDown() || player.isPassenger()) return;
        if (now - ledgeCooldown.getOrDefault(player.getUUID(), Long.MIN_VALUE / 2) < 10L) return;
        Vec3 look = player.getLookAngle();
        Vec3 horizontal = new Vec3(look.x, 0.0D, look.z);
        if (horizontal.lengthSqr() < 0.001D) return;
        horizontal = horizontal.normalize();
        var lower = player.blockPosition().offset((int)Math.round(horizontal.x), 0, (int)Math.round(horizontal.z));
        var upper = lower.above();
        if (player.level().getBlockState(lower).isAir() || !player.level().getBlockState(upper).isAir()) return;
        Vec3 velocity = player.getDeltaMovement();
        player.setDeltaMovement(velocity.x, Math.max(0.34D, velocity.y), velocity.z);
        player.hurtMarked = true;
        ledgeCooldown.put(player.getUUID(), now);
    }

    @SubscribeEvent
    public void onLogout(PlayerEvent.PlayerLoggedOutEvent event) {
        UUID id = event.getEntity().getUUID();
        wallKickCooldown.remove(id);
        slideCooldown.remove(id);
        ledgeCooldown.remove(id);
    }
}
