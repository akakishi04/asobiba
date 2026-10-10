package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaks;
import io.netty.buffer.ByteBuf;
import net.minecraft.network.FriendlyByteBuf;
import net.minecraft.network.codec.StreamCodec;
import net.minecraft.network.protocol.common.custom.CustomPacketPayload;
import net.minecraft.resources.ResourceLocation;

/** Owner-only, server-authoritative short input-control window after a real Wind Burst. */
public record WindAerialControlPayload(float strength, int ticks) implements CustomPacketPayload {
    public static final Type<WindAerialControlPayload> TYPE = new Type<>(
            ResourceLocation.fromNamespaceAndPath(AsobibaTweaks.MOD_ID, "wind_aerial_control"));
    public static final StreamCodec<ByteBuf, WindAerialControlPayload> STREAM_CODEC =
            StreamCodec.ofMember(WindAerialControlPayload::write, WindAerialControlPayload::new);
    public WindAerialControlPayload(ByteBuf raw) {
        this(raw.readFloat(), new FriendlyByteBuf(raw).readVarInt());
    }
    private void write(ByteBuf raw) {
        raw.writeFloat(strength);
        new FriendlyByteBuf(raw).writeVarInt(ticks);
    }
    @Override public Type<? extends CustomPacketPayload> type() { return TYPE; }
}
