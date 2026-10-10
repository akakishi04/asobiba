package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaks;
import io.netty.buffer.ByteBuf;
import net.minecraft.network.FriendlyByteBuf;
import net.minecraft.network.codec.StreamCodec;
import net.minecraft.network.protocol.common.custom.CustomPacketPayload;
import net.minecraft.resources.ResourceLocation;

public record FrostWalkerTogglePayload(int request) implements CustomPacketPayload {
    public static final Type<FrostWalkerTogglePayload> TYPE =
            new Type<>(ResourceLocation.fromNamespaceAndPath(
                    AsobibaTweaks.MOD_ID, "frost_walker_toggle"));

    public static final StreamCodec<ByteBuf, FrostWalkerTogglePayload> STREAM_CODEC =
            StreamCodec.ofMember(FrostWalkerTogglePayload::write, FrostWalkerTogglePayload::new);

    public FrostWalkerTogglePayload(ByteBuf raw) {
        this(new FriendlyByteBuf(raw).readVarInt());
    }

    private void write(ByteBuf raw) {
        new FriendlyByteBuf(raw).writeVarInt(request);
    }

    @Override
    public Type<? extends CustomPacketPayload> type() {
        return TYPE;
    }
}
