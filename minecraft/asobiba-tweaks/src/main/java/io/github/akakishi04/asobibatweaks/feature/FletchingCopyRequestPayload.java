package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaks;
import io.netty.buffer.ByteBuf;
import net.minecraft.core.BlockPos;
import net.minecraft.network.FriendlyByteBuf;
import net.minecraft.network.codec.StreamCodec;
import net.minecraft.network.protocol.common.custom.CustomPacketPayload;
import net.minecraft.resources.ResourceLocation;

/** Quantity 0 requests a new quote without purchasing anything. */
public record FletchingCopyRequestPayload(
        BlockPos tablePos, int quantity
) implements CustomPacketPayload {
    public static final Type<FletchingCopyRequestPayload> TYPE = new Type<>(
            ResourceLocation.fromNamespaceAndPath(AsobibaTweaks.MOD_ID, "fletching_copy_request")
    );
    public static final StreamCodec<ByteBuf, FletchingCopyRequestPayload> STREAM_CODEC =
            StreamCodec.ofMember(FletchingCopyRequestPayload::write, FletchingCopyRequestPayload::new);

    public FletchingCopyRequestPayload(ByteBuf raw) {
        this(new FriendlyByteBuf(raw));
    }

    private void write(ByteBuf raw) {
        FriendlyByteBuf buf = new FriendlyByteBuf(raw);
        buf.writeBlockPos(tablePos);
        buf.writeVarInt(quantity);
    }

    @Override
    public Type<? extends CustomPacketPayload> type() {
        return TYPE;
    }
}
