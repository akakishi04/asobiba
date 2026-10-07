package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaks;
import io.netty.buffer.ByteBuf;
import net.minecraft.network.FriendlyByteBuf;
import net.minecraft.network.codec.StreamCodec;
import net.minecraft.network.protocol.common.custom.CustomPacketPayload;
import net.minecraft.resources.ResourceLocation;

public record QuiverSelectPayload(int slot) implements CustomPacketPayload {
    public static final Type<QuiverSelectPayload> TYPE = new Type<>(
            ResourceLocation.fromNamespaceAndPath(AsobibaTweaks.MOD_ID, "quiver_select")
    );

    public static final StreamCodec<ByteBuf, QuiverSelectPayload> STREAM_CODEC =
            StreamCodec.ofMember(QuiverSelectPayload::write, QuiverSelectPayload::new);

    public QuiverSelectPayload(ByteBuf raw) {
        this(new FriendlyByteBuf(raw).readVarInt());
    }

    private void write(ByteBuf raw) {
        new FriendlyByteBuf(raw).writeVarInt(slot);
    }

    @Override
    public Type<? extends CustomPacketPayload> type() {
        return TYPE;
    }
}
