package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import java.util.function.Consumer;
import net.minecraft.core.BlockPos;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.level.block.Blocks;
import net.neoforged.neoforge.network.PacketDistributor;
import net.neoforged.neoforge.network.event.RegisterPayloadHandlersEvent;

/**
 * Opens a display-only screen. Every purchase request is validated on the
 * server against the actual Fletching Table, current hands, XP and distance.
 * No item or cost data is accepted from the client.
 */
public final class FletchingCopyNetworking {
    private static volatile Consumer<FletchingCopyPreviewPayload> CLIENT_HANDLER = p -> {};

    private FletchingCopyNetworking() {}

    public static void registerPayloads(RegisterPayloadHandlersEvent event) {
        var registrar = event.registrar("1");
        registrar.playToClient(
                FletchingCopyPreviewPayload.TYPE,
                FletchingCopyPreviewPayload.STREAM_CODEC,
                (payload, context) ->
                        context.enqueueWork(() -> CLIENT_HANDLER.accept(payload))
        );
        registrar.playToServer(
                FletchingCopyRequestPayload.TYPE,
                FletchingCopyRequestPayload.STREAM_CODEC,
                (payload, context) -> context.enqueueWork(() -> {
                    if (!(context.player() instanceof ServerPlayer player)
                            || !canUse(player, payload.tablePos())) return;

                    if (payload.quantity() > 0) {
                        if (payload.quantity() > 64) return;
                        EnchantedArrowCopyService.copy(player,
                                player.getMainHandItem(), player.getOffhandItem(),
                                payload.quantity());
                    } else if (payload.quantity() < 0) {
                        return;
                    }
                    sendPreview(player, payload.tablePos());
                })
        );
    }

    public static void installClientHandler(Consumer<FletchingCopyPreviewPayload> handler) {
        CLIENT_HANDLER = handler == null ? p -> {} : handler;
    }

    public static boolean open(ServerPlayer player, BlockPos pos) {
        if (!canUse(player, pos)
                || !EnchantedArrowCopyService.hasTemplate(player.getMainHandItem())) {
            return false;
        }
        sendPreview(player, pos);
        return true;
    }

    private static boolean canUse(ServerPlayer player, BlockPos pos) {
        return AsobibaTweaksConfig.FLETCHING_TABLE_ENABLED.getAsBoolean()
                && player.isAlive()
                && player.level().hasChunkAt(pos)
                && player.level().getBlockState(pos).is(Blocks.FLETCHING_TABLE)
                && player.distanceToSqr(pos.getCenter()) <= 64.0D;
    }

    private static void sendPreview(ServerPlayer player, BlockPos pos) {
        ItemStack template = player.getMainHandItem();
        EnchantedArrowCopyService.Quote quote =
                EnchantedArrowCopyService.quote(
                        player, template, player.getOffhandItem());
        String name = template.isEmpty() ? "Enchanted Arrow"
                : template.getHoverName().getString();
        if (name.length() > 96) name = name.substring(0, 96);

        PacketDistributor.sendToPlayer(player, new FletchingCopyPreviewPayload(
                pos, name, quote.materialCount(), quote.perCopyXp(),
                quote.availableXp(), quote.error()));
    }
}
