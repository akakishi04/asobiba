package io.github.akakishi04.asobibatweaks.feature;

import java.util.Objects;
import net.minecraft.ChatFormatting;
import net.minecraft.core.component.DataComponents;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;

/**
 * Copy a single enchanted arrow template into a user-selected batch using
 * ordinary same-kind offhand arrows. The offhand stack count is the selected
 * batch size (players can split the stack before using the Fletching Table).
 */
public final class EnchantedArrowCopyService {
    private EnchantedArrowCopyService() {}

    /** Returns true if this interaction is owned by the copying subsystem. */
    public static boolean tryCopy(ServerPlayer player, ItemStack template, ItemStack material) {
        if (!ExtendedEnchantingTargets.isExtendedArrowTarget(template)
                || EnchantmentMasteryData.enchantments(template).isEmpty()
                || material.isEmpty() || material.getItem() != template.getItem()) {
            return false;
        }
        if (!EnchantmentMasteryData.enchantments(material).isEmpty()) {
            message(player, "Use unenchanted arrows as the copying material.", false);
            return true;
        }
        if (template.is(Items.TIPPED_ARROW) &&
                !Objects.equals(template.get(DataComponents.POTION_CONTENTS),
                        material.get(DataComponents.POTION_CONTENTS))) {
            message(player, "Tipped-arrow potion contents must match the template.", false);
            return true;
        }

        int count = material.getCount();
        if (count <= 0 || count > 64) {
            message(player, "Select 1-64 arrows in the offhand.", false);
            return true;
        }

        long perCopy = 0L;
        for (var entry : EnchantmentMasteryData.enchantments(template).entrySet()) {
            int level = entry.getIntValue();
            int anvilCost = entry.getKey().value().getAnvilCost();
            if (level <= 0 || anvilCost < 0) {
                message(player, "Invalid enchantment level or anvil cost.", false);
                return true;
            }
            perCopy += (long)level * anvilCost;
            if (perCopy > Integer.MAX_VALUE) {
                message(player, "The copying XP cost exceeds the supported transaction limit.", false);
                return true;
            }
        }
        long amount = perCopy * count;
        if (amount > Integer.MAX_VALUE || amount < 0L) {
            message(player, "The copying XP cost exceeds the supported transaction limit.", false);
            return true;
        }

        int price = (int)amount;
        if (currentXp(player) < amount) {
            message(player, "Need " + amount + " XP points to copy " + count + " arrows.", false);
            return true;
        }

        // Both debits happen before any new arrows are materialized.
        if (price > 0) player.giveExperiencePoints(-price);
        material.shrink(count);

        ItemStack exemplar = template.copyWithCount(1);
        int left = count;
        while (left > 0) {
            int batch = Math.min(left, Math.max(1, exemplar.getMaxStackSize()));
            ItemStack cloned = exemplar.copyWithCount(batch);
            if (!player.getInventory().add(cloned) && !cloned.isEmpty()) {
                player.drop(cloned, false);
            }
            left -= batch;
        }
        message(player, "Copied " + count + " enchanted arrows for " + amount + " XP.", true);
        return true;
    }

    /** Compute current spendable points: totalExperience is lifetime-oriented. */
    private static long currentXp(ServerPlayer player) {
        long l = Math.max(0, player.experienceLevel);
        long earnedLevels = l <= 16 ? l * l + 6 * l
                : l <= 31 ? (5 * l * l - 81 * l + 720) / 2
                : (9 * l * l - 325 * l + 4440) / 2;
        long progress = (long)Math.floor(Math.max(0.0F, player.experienceProgress)
                * player.getXpNeededForNextLevel());
        return earnedLevels + progress;
    }

    private static void message(ServerPlayer player, String text, boolean success) {
        player.displayClientMessage(Component.literal(text).withStyle(
                success ? ChatFormatting.GREEN : ChatFormatting.RED), true);
    }
}
