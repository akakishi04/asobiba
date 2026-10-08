package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaks;
import io.netty.buffer.ByteBuf;
import net.minecraft.core.BlockPos;
import net.minecraft.network.FriendlyByteBuf;
import net.minecraft.network.codec.StreamCodec;
import net.minecraft.network.protocol.common.custom.CustomPacketPayload;
import net.minecraft.resources.ResourceLocation;

/** Server-authoritative Fletching Table quote and available materials. */
public record FletchingCopyPreviewPayload(
        BlockPos tablePos, String templateName, int availableCount,
        long perArrowXp, long playerXp, String error
) implements CustomPacketPayload {
    public static final Type<FletchingCopyPreviewPayload> TYPE = new Type<>(
            ResourceLocation.fromNamespaceAndPath(AsobibaTweaks.MOD_ID, "fletching_copy_preview")
    );
    public static final StreamCodec<ByteBuf, FletchingCopyPreviewPayload> STREAM_CODEC =
            StreamCodec.ofMember(FletchingCopyPreviewPayload::write, FletchingCopyPreviewPayload::new);

    public FletchingCopyPreviewPayload(ByteBuf raw) {
        this(new FriendlyByteBuf(raw));
    }

    private FletchingCopyPreviewPayload(FriendlyByteBuf buf) {
        this(buf.readBlockPos(), buf.readUtf(96), buf.readVarInt(),
                buf.readLong(), buf.readLong(), buf.readUtf(160));
    }

    private void write(ByteBuf raw) {
        FriendlyByteBuf buf = new FriendlyByteBuf(raw);
        buf.writeBlockPos(tablePos);
        buf.writeUtf(templateName, 96);
        buf.writeVarInt(Math.max(0, availableCount));
        buf.writeLong(Math.max(0L, perArrowXp));
        buf.writeLong(Math.max(0L, playerXp));
        buf.writeUtf(error, 160);
    }

    @Override
    public Type<? extends CustomPacketPayload> type() {
        return TYPE;
    }
}
