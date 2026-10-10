package io.github.akakishi04.asobibatweaks.client;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import io.github.akakishi04.asobibatweaks.feature.QuiverData;
import io.github.akakishi04.asobibatweaks.feature.QuiverSelectPayload;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.client.gui.screens.Screen;
import net.minecraft.network.chat.Component;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.neoforged.bus.api.SubscribeEvent;
import net.neoforged.neoforge.client.event.InputEvent;
import net.neoforged.neoforge.client.event.RenderGuiEvent;
import net.neoforged.neoforge.network.PacketDistributor;

public final class QuiverClientEvents {
    private static final int FULL_OVERLAY_TICKS = 40;
    private int fullOverlayUntilTick;

    @SubscribeEvent
    public void onMouseScroll(InputEvent.MouseScrollingEvent event) {
        if (!AsobibaTweaksConfig.QUIVER_ENABLED.getAsBoolean()
                || !Screen.hasControlDown()) {
            return;
        }

        Minecraft minecraft = Minecraft.getInstance();
        Player player = minecraft.player;
        if (player == null || !holdingLauncher(player) || !QuiverData.hasEquipped(player)) {
            return;
        }

        double delta = event.getScrollDeltaY();
        if (delta == 0.0D) return;

        int before = QuiverData.selectedSlot(player);
        int direction = delta > 0.0D ? -1 : 1;
        int selected = QuiverData.cycleSelected(player, direction);
        if (selected == before) return;

        PacketDistributor.sendToServer(new QuiverSelectPayload(selected));
        fullOverlayUntilTick = player.tickCount + FULL_OVERLAY_TICKS;

        ItemStack stack = QuiverData.ammo(player, selected);
        player.displayClientMessage(
                Component.translatable(
                        "message.asobibatweaks.quiver.selected",
                        selected + 1,
                        stack.getHoverName()
                ),
                true
        );
        event.setCanceled(true);
    }

    @SubscribeEvent
    public void onRenderGui(RenderGuiEvent.Post event) {
        if (!AsobibaTweaksConfig.QUIVER_ENABLED.getAsBoolean()) return;

        Minecraft minecraft = Minecraft.getInstance();
        Player player = minecraft.player;
        if (player == null || !holdingLauncher(player) || !QuiverData.hasEquipped(player)) {
            return;
        }

        ItemStack selected = QuiverData.selectedAmmo(player);
        if (selected.isEmpty()) return;

        GuiGraphics graphics = event.getGuiGraphics();
        int width = minecraft.getWindow().getGuiScaledWidth();
        int height = minecraft.getWindow().getGuiScaledHeight();

        if (player.tickCount <= fullOverlayUntilTick) {
            renderFullOverlay(graphics, minecraft, player, width, height);
        } else {
            int x = width / 2 + 104;
            int y = height - 23;
            drawSlot(graphics, minecraft, selected, x, y, true);
        }
    }

    private static void renderFullOverlay(
            GuiGraphics graphics,
            Minecraft minecraft,
            Player player,
            int width,
            int height) {
        int totalWidth = QuiverData.AMMO_SLOTS * 20;
        int startX = (width - totalWidth) / 2;
        int y = height - 52;
        int selected = QuiverData.selectedSlot(player);

        for (int slot = 0; slot < QuiverData.AMMO_SLOTS; slot++) {
            ItemStack stack = QuiverData.ammo(player, slot);
            drawSlot(graphics, minecraft, stack, startX + slot * 20, y, slot == selected);
        }
    }

    private static void drawSlot(
            GuiGraphics graphics,
            Minecraft minecraft,
            ItemStack stack,
            int x,
            int y,
            boolean selected) {
        graphics.fill(x - 1, y - 1, x + 18, y + 18, 0xAA101010);
        if (selected) {
            graphics.fill(x - 2, y - 2, x + 19, y, 0xFFE0E0E0);
            graphics.fill(x - 2, y + 18, x + 19, y + 20, 0xFFE0E0E0);
            graphics.fill(x - 2, y, x, y + 18, 0xFFE0E0E0);
            graphics.fill(x + 17, y, x + 19, y + 18, 0xFFE0E0E0);
        }

        if (!stack.isEmpty()) {
            graphics.renderItem(stack, x, y);
            graphics.renderItemDecorations(minecraft.font, stack, x, y);
        }
    }

    private static boolean holdingLauncher(Player player) {
        return isLauncher(player.getMainHandItem()) || isLauncher(player.getOffhandItem());
    }

    private static boolean isLauncher(ItemStack stack) {
        return stack.is(Items.BOW) || stack.is(Items.CROSSBOW);
    }
}
