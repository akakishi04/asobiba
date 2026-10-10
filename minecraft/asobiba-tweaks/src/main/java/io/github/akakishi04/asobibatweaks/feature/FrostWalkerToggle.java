package io.github.akakishi04.asobibatweaks.feature;

import net.minecraft.core.component.DataComponents;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.entity.EquipmentSlot;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.component.CustomData;
import net.minecraft.world.item.enchantment.Enchantment;

/**
 * Persist Frost Walker's ON/OFF state on the enchanted boots themselves.
 * Absence of the field means vanilla default: enabled.
 */
public final class FrostWalkerToggle {
    private static final String KEY = "asobibatweaks_frost_walker_enabled";

    private FrostWalkerToggle() {}

    public static boolean enabled(ItemStack boots) {
        CustomData data = boots.get(DataComponents.CUSTOM_DATA);
        return data == null || !data.contains(KEY) || data.copyTag().getBoolean(KEY);
    }

    public static boolean hasFrostWalker(ItemStack stack) {
        if (stack.isEmpty()) return false;
        for (var entry : EnchantmentMasteryData.enchantments(stack).entrySet()) {
            if (entry.getIntValue() > 0
                    && "minecraft:frost_walker".equals(EnchantmentMasteryData.id(entry.getKey()))) {
                return true;
            }
        }
        return false;
    }

    public static void toggle(ServerPlayer player) {
        ItemStack boots = player.getItemBySlot(EquipmentSlot.FEET);
        if (!hasFrostWalker(boots)) return;

        boolean nowEnabled = !enabled(boots);
        CustomData.update(DataComponents.CUSTOM_DATA, boots,
                tag -> tag.putBoolean(KEY, nowEnabled));
        player.getInventory().setChanged();
        player.inventoryMenu.broadcastChanges();
        player.displayClientMessage(
                Component.literal("Frost Walker: " + (nowEnabled ? "ON" : "OFF")),
                true
        );
    }
}
