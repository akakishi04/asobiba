package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaks;
import io.netty.buffer.ByteBuf;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import net.minecraft.network.FriendlyByteBuf;
import net.minecraft.network.codec.StreamCodec;
import net.minecraft.network.protocol.common.custom.CustomPacketPayload;
import net.minecraft.resources.ResourceLocation;

public record VillageStatusPayload(
        UUID villageId,
        String title,
        int population,
        int sustainablePopulation,
        int housingCapacity,
        int spareHousing,
        int foodDaysTenths,
        int averageWelfare,
        int viability,
        String lifecycle,
        int districtCount,
        int outpostCount,
        List<String> needs,
        List<String> projects
) implements CustomPacketPayload {
    public static final Type<VillageStatusPayload> TYPE = new Type<>(
            ResourceLocation.fromNamespaceAndPath(AsobibaTweaks.MOD_ID, "village_status")
    );

    public static final StreamCodec<ByteBuf, VillageStatusPayload> STREAM_CODEC =
            StreamCodec.ofMember(VillageStatusPayload::write, VillageStatusPayload::new);

    public VillageStatusPayload(ByteBuf raw) {
        this(new FriendlyByteBuf(raw));
    }

    private VillageStatusPayload(FriendlyByteBuf buf) {
        this(
                buf.readUUID(),
                buf.readUtf(96),
                buf.readVarInt(),
                buf.readVarInt(),
                buf.readVarInt(),
                buf.readVarInt(),
                buf.readVarInt(),
                buf.readVarInt(),
                buf.readVarInt(),
                buf.readUtf(32),
                buf.readVarInt(),
                buf.readVarInt(),
                readStrings(buf, 5),
                readStrings(buf, 5)
        );
    }

    private void write(ByteBuf raw) {
        FriendlyByteBuf buf = new FriendlyByteBuf(raw);
        buf.writeUUID(villageId);
        buf.writeUtf(title, 96);
        buf.writeVarInt(Math.max(0, population));
        buf.writeVarInt(Math.max(0, sustainablePopulation));
        buf.writeVarInt(Math.max(0, housingCapacity));
        buf.writeVarInt(Math.max(0, spareHousing));
        buf.writeVarInt(Math.max(0, foodDaysTenths));
        buf.writeVarInt(Math.max(0, Math.min(100, averageWelfare)));
        buf.writeVarInt(Math.max(0, Math.min(100, viability)));
        buf.writeUtf(lifecycle, 32);
        buf.writeVarInt(Math.max(0, districtCount));
        buf.writeVarInt(Math.max(0, outpostCount));
        writeStrings(buf, needs, 5);
        writeStrings(buf, projects, 5);
    }

    private static List<String> readStrings(FriendlyByteBuf buf, int limit) {
        int count = Math.min(limit, Math.max(0, buf.readVarInt()));
        List<String> result = new ArrayList<>(count);
        for (int i = 0; i < count; i++) result.add(buf.readUtf(160));
        return List.copyOf(result);
    }

    private static void writeStrings(FriendlyByteBuf buf, List<String> values, int limit) {
        int count = Math.min(limit, values.size());
        buf.writeVarInt(count);
        for (int i = 0; i < count; i++) buf.writeUtf(values.get(i), 160);
    }

    @Override
    public Type<? extends CustomPacketPayload> type() {
        return TYPE;
    }
}
