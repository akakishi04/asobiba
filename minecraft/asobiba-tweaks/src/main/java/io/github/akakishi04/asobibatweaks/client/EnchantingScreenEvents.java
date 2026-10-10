package io.github.akakishi04.asobibatweaks.client;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import io.github.akakishi04.asobibatweaks.feature.EnchantmentRerollProtocol;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.components.Button;
import net.minecraft.client.gui.screens.inventory.EnchantmentScreen;
import net.minecraft.network.chat.Component;
import net.neoforged.bus.api.SubscribeEvent;
import net.neoforged.neoforge.client.event.ScreenEvent;

public final class EnchantingScreenEvents {
    @SubscribeEvent
    public void onScreenInit(ScreenEvent.Init.Post event) {
        if (!AsobibaTweaksConfig.ENCHANTMENT_REROLL_ENABLED.getAsBoolean()
                || !(event.getScreen() instanceof EnchantmentScreen screen)) {
            return;
        }

        int x = Math.min(screen.width - 106, screen.width / 2 + 92);
        int y = screen.height / 2 - 10;
        int cost = AsobibaTweaksConfig.ENCHANTMENT_REROLL_LEVEL_COST.getAsInt();

        event.addListener(Button.builder(
                Component.translatable("button.asobibatweaks.enchantment_reroll", cost),
                button -> {
                    Minecraft mc = Minecraft.getInstance();
                    if (mc.gameMode != null && mc.player != null
                            && mc.player.containerMenu == screen.getMenu()) {
                        mc.gameMode.handleInventoryButtonClick(
                                screen.getMenu().containerId,
                                EnchantmentRerollProtocol.BUTTON_ID
                        );
                    }
                })
                .bounds(x, y, 102, 20)
                .build());
    }
}
