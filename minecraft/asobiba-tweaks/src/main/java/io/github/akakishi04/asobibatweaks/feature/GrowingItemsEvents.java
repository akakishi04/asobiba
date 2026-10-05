package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import net.minecraft.ChatFormatting;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.item.ItemStack;
import net.neoforged.bus.api.SubscribeEvent;
import net.neoforged.neoforge.event.entity.living.LivingDeathEvent;
import net.neoforged.neoforge.event.entity.player.ItemTooltipEvent;
import net.neoforged.neoforge.event.level.BlockDropsEvent;

public final class GrowingItemsEvents {
    @SubscribeEvent
    public void onBlockDrops(BlockDropsEvent event) {
        if (!AsobibaTweaksConfig.GROWING_ITEMS_ENABLED.getAsBoolean()) {
            return;
        }
        if (event.getBreaker() instanceof ServerPlayer player) {
            gainXp(player, player.getMainHandItem(), 1);
        }
    }

    @SubscribeEvent
    public void onLivingDeath(LivingDeathEvent event) {
        if (!AsobibaTweaksConfig.GROWING_ITEMS_ENABLED.getAsBoolean()) {
            return;
        }
        if (event.getSource().getEntity() instanceof ServerPlayer player) {
            gainXp(player, player.getMainHandItem(), 5);
        }
    }

    @SubscribeEvent
    public void onTooltip(ItemTooltipEvent event) {
        if (!AsobibaTweaksConfig.GROWING_ITEMS_ENABLED.getAsBoolean()) {
            return;
        }

        ItemStack stack = event.getItemStack();
        if (!GrowingItemData.isEligible(stack)) {
            return;
        }

        int xp = GrowingItemData.getXp(stack);
        int level = GrowingItemData.getLevel(stack);
        int max = AsobibaTweaksConfig.GROWING_ITEMS_MAX_LEVEL.getAsInt();

        event.getToolTip().add(Component.literal("Growth Lv. " + level + "/" + max)
                .withStyle(ChatFormatting.AQUA));

        if (level < max) {
            event.getToolTip().add(Component.literal("Growth XP: " + xp + "/" + GrowingItemData.nextLevelThreshold(level))
                    .withStyle(ChatFormatting.DARK_GRAY));
        } else {
            event.getToolTip().add(Component.literal("Growth XP: MAX")
                    .withStyle(ChatFormatting.DARK_GRAY));
        }
    }

    private static void gainXp(ServerPlayer player, ItemStack stack, int amount) {
        if (!GrowingItemData.isEligible(stack)) {
            return;
        }

        int oldLevel = GrowingItemData.getLevel(stack);
        int xp = GrowingItemData.getXp(stack) + amount;
        GrowingItemData.setXp(stack, xp);
        int newLevel = GrowingItemData.getLevel(stack);

        if (newLevel > oldLevel) {
            player.displayClientMessage(
                    Component.literal(stack.getHoverName().getString() + " grew to Lv. " + newLevel)
                            .withStyle(ChatFormatting.GREEN),
                    true
            );
        }

        double repairChance = Math.min(
                1.0D,
                newLevel * AsobibaTweaksConfig.GROWING_ITEMS_REPAIR_CHANCE_PER_LEVEL.getAsDouble()
        );
        if (stack.isDamaged() && player.getRandom().nextDouble() < repairChance) {
            stack.setDamageValue(Math.max(0, stack.getDamageValue() - 1));
        }
    }
}
