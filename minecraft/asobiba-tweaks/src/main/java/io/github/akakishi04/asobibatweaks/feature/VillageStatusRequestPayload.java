package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaks;
import io.netty.buffer.ByteBuf;
import java.util.UUID;
import net.minecraft.network.FriendlyByteBuf;
import net.minecraft.network.codec.StreamCodec;
import net.minecraft.network.protocol.common.custom.CustomPacketPayload;
import net.minecraft.resources.ResourceLocation;

public record VillageStatusRequestPayload(UUID villageId) implements CustomPacketPayload {
    public static final Type<VillageStatusRequestPayload> TYPE = new Type<>(
            ResourceLocation.fromNamespaceAndPath(AsobibaTweaks.MOD_ID, "village_status_request")
    );

    public static final StreamCodec<ByteBuf, VillageStatusRequestPayload> STREAM_CODEC =
            StreamCodec.ofMember(VillageStatusRequestPayload::write, VillageStatusRequestPayload::new);

    public VillageStatusRequestPayload(ByteBuf raw) {
        this(new FriendlyByteBuf(raw).readUUID());
    }

    private void write(ByteBuf raw) {
        new FriendlyByteBuf(raw).writeUUID(villageId);
    }

    @Override
    public Type<? extends CustomPacketPayload> type() {
        return TYPE;
    }
}
