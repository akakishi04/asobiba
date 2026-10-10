package io.github.akakishi04.asobibatweaks.item;

import io.github.akakishi04.asobibatweaks.feature.QuiverData;
import java.util.List;
import net.minecraft.ChatFormatting;
import net.minecraft.network.chat.Component;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.TooltipFlag;
import net.minecraft.world.item.component.ItemContainerContents;
import net.minecraft.core.component.DataComponents;

public final class QuiverItem extends Item {
    public QuiverItem(Properties properties) {
        super(properties.stacksTo(1));
    }

    @Override
    public void appendHoverText(ItemStack stack, TooltipContext context,
                                List<Component> tooltip, TooltipFlag flag) {
        super.appendHoverText(stack, context, tooltip, flag);

        ItemContainerContents contents = stack.get(DataComponents.CONTAINER);
        int used = 0;
        if (contents != null) {
            int limit = Math.min(QuiverData.AMMO_SLOTS, contents.getSlots());
            for (int i = 0; i < limit; i++) {
                if (!contents.getStackInSlot(i).isEmpty()) used++;
            }
        }

        tooltip.add(Component.translatable(
                "tooltip.asobibatweaks.quiver.slots", used, QuiverData.AMMO_SLOTS
        ).withStyle(ChatFormatting.GRAY));
    }
}
