package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import net.minecraft.world.entity.item.ItemEntity;
import net.minecraft.world.item.ItemStack;
import net.neoforged.bus.api.SubscribeEvent;
import net.neoforged.neoforge.event.level.BlockDropsEvent;

public final class EnchantedWorkBlockEvents {
    @SubscribeEvent
    public void onDrops(BlockDropsEvent event) {
        if (!AsobibaTweaksConfig.EXTENDED_ENCHANTING_TARGETS_ENABLED.getAsBoolean()) return;

        ItemStack expected = new ItemStack(event.getState().getBlock().asItem());
        if (!ExtendedEnchantingTargets.isExtendedBlockTarget(expected)) return;

        ItemStack saved = EnchantedWorkBlockSavedData.get(event.getLevel()).remove(event.getPos().asLong());
        if (saved.isEmpty()) return;

        for (int i = 0; i < event.getDrops().size(); i++) {
            ItemEntity drop = event.getDrops().get(i);
            if (drop.getItem().is(expected.getItem())) {
                event.getDrops().set(i, new ItemEntity(
                        event.getLevel(),
                        drop.getX(), drop.getY(), drop.getZ(),
                        saved.copyWithCount(1)
                ));
                return;
            }
        }

        event.getDrops().add(new ItemEntity(
                event.getLevel(),
                event.getPos().getX() + 0.5D,
                event.getPos().getY() + 0.5D,
                event.getPos().getZ() + 0.5D,
                saved.copyWithCount(1)
        ));
    }
}
