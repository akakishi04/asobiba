package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaks;
import io.netty.buffer.ByteBuf;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.network.FriendlyByteBuf;
import net.minecraft.network.codec.StreamCodec;
import net.minecraft.network.protocol.common.custom.CustomPacketPayload;
import net.minecraft.resources.ResourceLocation;

public record QuiverSyncPayload(CompoundTag snapshot) implements CustomPacketPayload {
    public static final Type<QuiverSyncPayload> TYPE = new Type<>(
            ResourceLocation.fromNamespaceAndPath(AsobibaTweaks.MOD_ID, "quiver_sync")
    );
    public static final StreamCodec<ByteBuf, QuiverSyncPayload> STREAM_CODEC =
            StreamCodec.ofMember(QuiverSyncPayload::write, QuiverSyncPayload::new);

    public QuiverSyncPayload(ByteBuf raw) {
        this(new FriendlyByteBuf(raw).readNbt());
    }

    private void write(ByteBuf raw) {
        new FriendlyByteBuf(raw).writeNbt(snapshot);
    }

    @Override
    public Type<? extends CustomPacketPayload> type() {
        return TYPE;
    }
}
