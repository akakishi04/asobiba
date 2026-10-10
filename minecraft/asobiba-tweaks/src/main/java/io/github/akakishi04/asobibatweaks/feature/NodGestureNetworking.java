package io.github.akakishi04.asobibatweaks.feature;

import java.util.function.Consumer;
import net.minecraft.world.entity.npc.Villager;
import net.neoforged.neoforge.network.PacketDistributor;
import net.minecraft.server.level.ServerLevel;
import net.neoforged.neoforge.network.registration.NetworkRegistry;
import net.neoforged.neoforge.network.event.RegisterPayloadHandlersEvent;

public final class NodGestureNetworking {
    private static volatile Consumer<NodGesturePayload> clientHandler = payload -> {};
    private NodGestureNetworking() {}
    public static void registerPayloads(RegisterPayloadHandlersEvent event) {
        event.registrar("1").playToClient(NodGesturePayload.TYPE, NodGesturePayload.STREAM_CODEC,
                (payload, context) -> clientHandler.accept(payload));
    }
    public static void installClientHandler(Consumer<NodGesturePayload> handler) { clientHandler = handler; }
    static void send(Villager villager, int duration) {
        if (!(villager.level() instanceof ServerLevel level)) return;
        NodGesturePayload payload = new NodGesturePayload(villager.getId(),
                Math.max(0, Math.min(NodGreetingEvents.DURATION, duration)));
        for (var observer : AmbientOddityService.nearby(level, net.minecraft.server.level.ServerPlayer.class,
                villager.getBoundingBox().inflate(64))) {
            if (observer.distanceToSqr(villager) <= 64 * 64 && observer.connection != null
                    && NetworkRegistry.hasChannel(observer.connection, NodGesturePayload.TYPE.id()))
                PacketDistributor.sendToPlayer(observer, payload);
        }
    }
}
