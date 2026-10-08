package io.github.akakishi04.asobibatweaks.feature;

import java.util.Objects;
import net.minecraft.ChatFormatting;
import net.minecraft.core.component.DataComponents;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;

/**
 * One authoritative server transaction for enchanted-arrow copying.
 *
 * The quote and the completed transaction use the same pricing formula.
 * A client-provided batch size is never trusted: material identity,
 * source enchantments, exact potion components, stock, spendable XP, and
 * resulting output are rechecked on the server at the moment of purchase.
 */
public final class EnchantedArrowCopyService {
    private EnchantedArrowCopyService() {}

    public record Quote(int materialCount, long perCopyXp,
                        long availableXp, String error) {
        public boolean valid() { return error.isEmpty(); }

        public long total(int requested) {
            return requested <= 0 || requested > materialCount
                    ? -1L : perCopyXp * requested;
        }
    }

    public static boolean hasTemplate(ItemStack template) {
        return ExtendedEnchantingTargets.isExtendedArrowTarget(template)
                && !EnchantmentMasteryData.enchantments(template).isEmpty();
    }

    public static Quote quote(ServerPlayer player, ItemStack template, ItemStack material) {
        long xp = currentXp(player);
        if (!hasTemplate(template)) {
            return new Quote(0, 0L, xp, "Hold an enchanted arrow in your main hand.");
        }

        long perCopy = 0L;
        for (var entry : EnchantmentMasteryData.enchantments(template).entrySet()) {
            int level = entry.getIntValue();
            int anvilCost = entry.getKey().value().getAnvilCost();
            if (level <= 0 || anvilCost < 0) {
                return new Quote(0, 0L, xp, "Invalid enchantment level or cost.");
            }
            perCopy += (long)level * anvilCost;
            if (perCopy > Integer.MAX_VALUE) {
                return new Quote(0, perCopy, xp, "Per-arrow XP cost is too large.");
            }
        }

        if (material.isEmpty() || material.getItem() != template.getItem()) {
            return new Quote(0, perCopy, xp,
                    "Place compatible ordinary arrows in your offhand.");
        }
        if (!EnchantmentMasteryData.enchantments(material).isEmpty()) {
            return new Quote(0, perCopy, xp, "Copy material must be unenchanted.");
        }
        if (template.is(Items.TIPPED_ARROW)
                && !Objects.equals(template.get(DataComponents.POTION_CONTENTS),
                        material.get(DataComponents.POTION_CONTENTS))) {
            return new Quote(0, perCopy, xp, "Tipped-arrow potion contents must match.");
        }

        int available = Math.min(64, material.getCount());
        if (available <= 0) {
            return new Quote(0, perCopy, xp, "No copy material available.");
        }
        return new Quote(available, perCopy, xp, "");
    }

    /** Legacy direct-copy API retained for other integrations. */
    public static boolean tryCopy(ServerPlayer player, ItemStack template, ItemStack material) {
        if (!hasTemplate(template)) return false;
        return copy(player, template, material, material.getCount());
    }

    public static boolean copy(
            ServerPlayer player, ItemStack template,
            ItemStack material, int requested) {
        Quote quote = quote(player, template, material);
        if (!quote.valid()) {
            message(player, quote.error(), false);
            return false;
        }
        if (requested < 1 || requested > quote.materialCount()) {
            message(player, "Choose between 1 and " + quote.materialCount() + " arrows.", false);
            return false;
        }

        long amount = quote.total(requested);
        if (amount < 0L || amount > Integer.MAX_VALUE) {
            message(player, "Batch XP cost exceeds the supported transaction limit.", false);
            return false;
        }
        if (quote.availableXp() < amount) {
            message(player, "Need " + amount + " XP to copy " + requested + " arrows.", false);
            return false;
        }

        // Debit XP first. A canceled or partially applied debit never spends
        // physical arrow material or emits a single extra arrow.
        if (amount > 0L) {
            long before = currentXp(player);
            player.giveExperiencePoints(-(int)amount);
            long charged = before - currentXp(player);
            if (charged != amount) {
                if (charged > 0L && charged <= Integer.MAX_VALUE) {
                    player.giveExperiencePoints((int)charged);
                }
                message(player, "Copy canceled: XP payment did not complete.", false);
                return false;
            }
        }

        material.shrink(requested);

        ItemStack exemplar = template.copyWithCount(1);
        int remainingCount = requested;
        while (remainingCount > 0) {
            int batch = Math.min(remainingCount, Math.max(1, exemplar.getMaxStackSize()));
            ItemStack output = exemplar.copyWithCount(batch);
            player.getInventory().add(output);
            if (!output.isEmpty()) player.drop(output, false);
            remainingCount -= batch;
        }

        message(player, "Copied " + requested + " enchanted arrows for " + amount + " XP.", true);
        return true;
    }

    /** Spendable XP points; player's totalExperience is lifetime-oriented. */
    private static long currentXp(ServerPlayer player) {
        long level = Math.max(0, player.experienceLevel);
        long earned = level <= 16 ? level * level + 6L * level
                : level <= 31 ? (5L * level * level - 81L * level + 720L) / 2L
                : (9L * level * level - 325L * level + 4440L) / 2L;
        long progress = (long)Math.floor(
                Math.max(0.0F, player.experienceProgress) * player.getXpNeededForNextLevel());
        return Math.max(0L, earned + progress);
    }

    private static void message(ServerPlayer player, String text, boolean success) {
        player.displayClientMessage(Component.literal(text).withStyle(
                success ? ChatFormatting.GREEN : ChatFormatting.RED), true);
    }
}
