package io.github.akakishi04.asobibatweaks.client;

import io.github.akakishi04.asobibatweaks.feature.NodGesturePayload;
import java.lang.ref.WeakReference;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;
import net.minecraft.client.Minecraft;
import net.minecraft.client.multiplayer.ClientLevel;
import net.minecraft.util.Mth;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.npc.Villager;

/** Bounded model-only overlay. Never changes client gameplay rotation, AI, or the player's camera. */
public final class NodGestureClient {
    private record Nod(int entityId, float startAge, int duration) {}
    private static final Map<UUID, Nod> ACTIVE = new HashMap<>();
    private static WeakReference<ClientLevel> previousLevel = new WeakReference<>(null);
    private NodGestureClient() {}

    public static void accept(NodGesturePayload payload) {
        ClientLevel level = Minecraft.getInstance().level;
        if (level != previousLevel.get()) { ACTIVE.clear(); previousLevel = new WeakReference<>(level); }
        if (level == null || !(level.getEntity(payload.entityId()) instanceof Villager villager)) return;
        if (payload.duration() <= 0) { ACTIVE.remove(villager.getUUID()); return; }
        ACTIVE.entrySet().removeIf(entry -> level.getEntity(entry.getValue().entityId()) == null
                || !level.getEntity(entry.getValue().entityId()).getUUID().equals(entry.getKey()));
        if (ACTIVE.size() >= 64 && !ACTIVE.containsKey(villager.getUUID())) ACTIVE.clear();
        ACTIVE.put(villager.getUUID(), new Nod(villager.getId(), villager.tickCount, Math.min(24, payload.duration())));
    }

    public static float pitch(Entity entity, float ageInTicks) {
        if (Minecraft.getInstance().level != previousLevel.get()) {
            ACTIVE.clear(); previousLevel = new WeakReference<>(Minecraft.getInstance().level);
        }
        Nod nod = ACTIVE.get(entity.getUUID());
        if (nod == null) return 0;
        float elapsed = ageInTicks - nod.startAge();
        if (elapsed < 0 || elapsed >= nod.duration() || !entity.isAlive()
                || entity instanceof Villager villager && (villager.hurtTime > 0 || villager.isSleeping() || villager.isTrading())) {
            ACTIVE.remove(entity.getUUID()); return 0;
        }
        return 24.0F * Mth.DEG_TO_RAD * Mth.sin(Mth.PI * elapsed / nod.duration());
    }
}
