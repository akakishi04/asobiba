package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaks;
import io.netty.buffer.ByteBuf;
import net.minecraft.network.codec.StreamCodec;
import net.minecraft.network.protocol.common.custom.CustomPacketPayload;
import net.minecraft.resources.ResourceLocation;

/** A fixed-size, server-to-client-only presentation snapshot. No client setting or allowance API. */
public record DailyPlayTimePayload(boolean enabled, long playedDays, long remainingMillis,
        long limitMillis, long resetAtEpochMillis, boolean paused) implements CustomPacketPayload {
    public static final Type<DailyPlayTimePayload> TYPE = new Type<>(
            ResourceLocation.fromNamespaceAndPath(AsobibaTweaks.MOD_ID, "daily_play_time"));
    public static final StreamCodec<ByteBuf, DailyPlayTimePayload> STREAM_CODEC =
            StreamCodec.ofMember(DailyPlayTimePayload::write, DailyPlayTimePayload::new);

    private DailyPlayTimePayload(ByteBuf buf) {
        this(buf.readBoolean(), buf.readLong(), buf.readLong(), buf.readLong(),
                buf.readLong(), buf.readBoolean());
    }

    private void write(ByteBuf buf) {
        buf.writeBoolean(enabled);
        buf.writeLong(playedDays);
        buf.writeLong(remainingMillis);
        buf.writeLong(limitMillis);
        buf.writeLong(resetAtEpochMillis);
        buf.writeBoolean(paused);
    }

    @Override
    public Type<? extends CustomPacketPayload> type() {
        return TYPE;
    }
}
