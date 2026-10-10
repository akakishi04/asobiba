package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.WeakHashMap;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.util.Mth;
import net.minecraft.world.entity.EquipmentSlot;
import net.minecraft.world.entity.npc.Villager;
import net.minecraft.world.phys.Vec3;
import net.neoforged.bus.api.SubscribeEvent;
import net.neoforged.neoforge.event.level.LevelEvent;
import net.neoforged.neoforge.event.tick.EntityTickEvent;
import net.neoforged.neoforge.event.tick.LevelTickEvent;

/** Genuine crouch-edge greetings; a server-approved, client model-only overlay renders the nod. */
public final class NodGreetingEvents {
    static final int DURATION = 24;
    static final int ATTEMPT_COOLDOWN = 200;
    private static final Map<ServerLevel, Map<UUID, Greeting>> GREETINGS = new WeakHashMap<>();
    private static final Map<ServerLevel, Map<UUID, Gesture>> GESTURES = new WeakHashMap<>();

    static final class Greeting {
        boolean crouching;
        long standingSince;
        long crouchedAt;
        long nextAttempt;
        long seen;
        boolean armed;
    }
    record Gesture(UUID player, long start, Vec3 origin) {}

    @SubscribeEvent
    public void onEntityTick(EntityTickEvent.Post event) {
        if (!(event.getEntity().level() instanceof ServerLevel level)) return;
        if (event.getEntity() instanceof ServerPlayer player) tickGreeting(player);
        if (event.getEntity() instanceof Villager villager) tickGesture(villager);
    }

    @SubscribeEvent
    public void onUnload(LevelEvent.Unload event) {
        if (event.getLevel() instanceof ServerLevel level) { GREETINGS.remove(level); GESTURES.remove(level); }
    }

    @SubscribeEvent
    public void onLevelTick(LevelTickEvent.Post event) {
        if (!(event.getLevel() instanceof ServerLevel level) || level.getGameTime() % 20 != 0) return;
        long now = level.getGameTime();
        cleanGestures(level);
        Map<UUID, Greeting> entries = GREETINGS.get(level);
        if (entries != null) entries.values().removeIf(entry -> entry.seen < now - 400);
    }

    static void cleanGestures(ServerLevel level) {
        long now = level.getGameTime();
        gestures(level).entrySet().removeIf(entry -> now >= entry.getValue().start() + DURATION
                || level.getEntity(entry.getKey()) == null);
    }

    static void tickGreeting(ServerPlayer player) {
        ServerLevel level = player.serverLevel();
        long now = level.getGameTime();
        Map<UUID, Greeting> entries = GREETINGS.computeIfAbsent(level, ignored -> new HashMap<>());
        if (!AsobibaTweaksConfig.NOD_ENABLED.getAsBoolean()) { entries.remove(player.getUUID()); return; }
        if (!entries.containsKey(player.getUUID()) && entries.size() >= AmbientOddityService.MAX_COOLDOWNS) return;
        Greeting greeting = entries.computeIfAbsent(player.getUUID(), ignored -> {
            Greeting fresh = new Greeting();
            fresh.crouching = player.isShiftKeyDown();
            fresh.standingSince = now;
            return fresh;
        });
        greeting.seen = now;
        if (!player.isShiftKeyDown()) {
            if (greeting.crouching) greeting.standingSince = now;
            greeting.crouching = false;
            greeting.armed = false;
            return;
        }
        if (!greeting.crouching) {
            greeting.crouching = true;
            greeting.crouchedAt = now;
            greeting.armed = now - greeting.standingSince >= 8;
        }
        if (!greeting.armed || now - greeting.crouchedAt < 4 || now < greeting.nextAttempt) return;
        greeting.armed = false;
        greeting.nextAttempt = now + ATTEMPT_COOLDOWN;
        attemptGreeting(player, level.random.nextDouble());
    }

    static boolean wearsNod(ServerPlayer player) {
        return player.getItemBySlot(EquipmentSlot.HEAD).is(net.minecraft.tags.ItemTags.HEAD_ARMOR_ENCHANTABLE)
                && NewEnchantments.has(player.getItemBySlot(EquipmentSlot.HEAD), player.registryAccess(), NewEnchantments.NOD);
    }

    static boolean facing(ServerPlayer player, Villager villager) {
        Vec3 difference = villager.getEyePosition().subtract(player.getEyePosition());
        for (int i = 0; i <= 10; i++) {
            if (!player.serverLevel().hasChunkAt(net.minecraft.core.BlockPos.containing(
                    player.getEyePosition().add(difference.scale(i / 10.0D))))) return false;
        }
        return difference.lengthSqr() <= 25 && difference.lengthSqr() >= 0.25D
                && player.getLookAngle().dot(difference.normalize()) >= 0.92D
                && player.hasLineOfSight(villager);
    }

    static boolean attemptGreeting(ServerPlayer player, double roll) {
        ServerLevel level = player.serverLevel();
        if (!player.isShiftKeyDown() || !wearsNod(player)
                || !AmbientOddityService.ready(level, player, player.blockPosition(), AmbientOddityService.Kind.NOD)
                || !AmbientOddityService.claimProbe(level) || !AmbientOddityService.quiet(player)) return false;
        List<Villager> villagers = AmbientOddityService.nearby(level, Villager.class, player.getBoundingBox().inflate(5));
        if (villagers.size() >= AmbientOddityService.MAX_QUERY_RESULTS) return false;
        Villager target = villagers.stream().filter(villager -> AmbientOddityService.idle(villager)
                && facing(player, villager) && !gestures(level).containsKey(villager.getUUID()))
                .min(java.util.Comparator.comparingDouble(player::distanceToSqr)).orElse(null);
        if (target == null || gestures(level).size() >= 4
                || roll >= AmbientOddityService.chance(player, AsobibaTweaksConfig.NOD_GREETING_CHANCE.getAsDouble(), true)) return false;
        AmbientOddityService.reserve(level, player, target.blockPosition());
        gestures(level).put(target.getUUID(), new Gesture(player.getUUID(), level.getGameTime(), target.position()));
        NodGestureNetworking.send(target, DURATION);
        tickGesture(target);
        return true;
    }

    static Map<UUID, Gesture> gestures(ServerLevel level) {
        return GESTURES.computeIfAbsent(level, ignored -> new HashMap<>());
    }

    static float nodPitch(long elapsed) {
        return 24.0F * (float)Math.sin(Math.PI * Mth.clamp(elapsed / (double)DURATION, 0, 1));
    }

    static void tickGesture(Villager villager) {
        ServerLevel level = (ServerLevel)villager.level();
        Map<UUID, Gesture> active = gestures(level);
        Gesture gesture = active.get(villager.getUUID());
        if (gesture == null) return;
        ServerPlayer player = level.getServer().getPlayerList().getPlayer(gesture.player());
        // Mock GameTest players are in the level but not the server's PlayerList.
        if (player == null && level.getEntity(gesture.player()) instanceof ServerPlayer local) player = local;
        long elapsed = level.getGameTime() - gesture.start();
        if (!AsobibaTweaksConfig.NOD_ENABLED.getAsBoolean() || elapsed >= DURATION || player == null
                || player.level() != level || !AmbientOddityService.safePlayer(player) || !wearsNod(player)
                || !AmbientOddityService.idle(villager) || !facing(player, villager)
                || villager.position().distanceToSqr(gesture.origin()) > 0.1D) {
            active.remove(villager.getUUID());
            NodGestureNetworking.send(villager, 0);
            return; // Never restore stale pitch or overwrite a new vanilla AI task on cancellation.
        }
        Vec3 direction = player.getEyePosition().subtract(villager.getEyePosition());
        float yaw = (float)(Math.atan2(direction.z, direction.x) * 180.0D / Math.PI) - 90.0F;
        float baseline = Mth.clamp((float)(-Math.atan2(direction.y, direction.horizontalDistance()) * 180.0D / Math.PI), -12, 12);
        villager.getLookControl().setLookAt(player, 20, 20);
        villager.setYHeadRot(Mth.rotLerp(0.5F, villager.getYHeadRot(), yaw));
        villager.setXRot(baseline); // The model overlay adds the nod once; no doubled native pitch.
    }

    static void clear(ServerLevel level) { GREETINGS.remove(level); GESTURES.remove(level); }
}
