package io.github.akakishi04.asobibatweaks.client;

import io.github.akakishi04.asobibatweaks.feature.FrostWalkerToggle;
import io.github.akakishi04.asobibatweaks.feature.FrostWalkerTogglePayload;
import net.minecraft.client.Minecraft;
import net.minecraft.world.entity.EquipmentSlot;
import net.neoforged.bus.api.SubscribeEvent;
import net.neoforged.neoforge.client.event.ClientTickEvent;
import net.neoforged.neoforge.network.PacketDistributor;

/** A rising-edge sneak+jump gesture; held keys only toggle once. */
public final class FrostWalkerToggleClientEvents {
    private boolean previousJumpPressed;

    @SubscribeEvent
    public void onClientTick(ClientTickEvent.Post event) {
        Minecraft minecraft = Minecraft.getInstance();
        boolean pressed = minecraft.options.keyJump.isDown();
        boolean gesture = pressed && !previousJumpPressed;
        previousJumpPressed = pressed;

        if (!gesture || minecraft.screen != null || minecraft.player == null
                || !minecraft.options.keyShift.isDown()) return;

        if (FrostWalkerToggle.hasFrostWalker(
                minecraft.player.getItemBySlot(EquipmentSlot.FEET))) {
            PacketDistributor.sendToServer(new FrostWalkerTogglePayload(1));
        }
    }
}
