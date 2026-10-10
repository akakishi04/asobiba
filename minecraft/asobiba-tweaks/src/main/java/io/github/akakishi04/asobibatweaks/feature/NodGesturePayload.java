package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaks;
import net.minecraft.network.RegistryFriendlyByteBuf;
import net.minecraft.network.codec.StreamCodec;
import net.minecraft.network.protocol.common.custom.CustomPacketPayload;
import net.minecraft.resources.ResourceLocation;

/** Zero duration cancels; positive duration is capped by both server and client. No client request exists. */
public record NodGesturePayload(int entityId, int duration) implements CustomPacketPayload {
    public static final Type<NodGesturePayload> TYPE = new Type<>(ResourceLocation.fromNamespaceAndPath(
            AsobibaTweaks.MOD_ID, "nod_gesture"));
    public static final StreamCodec<RegistryFriendlyByteBuf, NodGesturePayload> STREAM_CODEC = StreamCodec.of(
            (buffer, payload) -> { buffer.writeVarInt(payload.entityId()); buffer.writeVarInt(payload.duration()); },
            buffer -> new NodGesturePayload(buffer.readVarInt(), buffer.readVarInt()));
    @Override public Type<? extends CustomPacketPayload> type() { return TYPE; }
}
