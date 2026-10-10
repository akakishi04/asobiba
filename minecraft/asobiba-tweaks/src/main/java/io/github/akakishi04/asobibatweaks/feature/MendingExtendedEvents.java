package io.github.akakishi04.asobibatweaks.feature;

import io.github.akakishi04.asobibatweaks.AsobibaTweaksConfig;
import java.util.ArrayList;
import java.util.IdentityHashMap;
import java.util.List;
import net.minecraft.ChatFormatting;
import net.minecraft.core.component.DataComponents;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.component.CustomData;
import net.neoforged.bus.api.SubscribeEvent;
import net.neoforged.neoforge.event.entity.player.ItemTooltipEvent;

/** Linked Mending XP and item-local mastery over-repair. */
public final class MendingExtendedEvents {
    private static final String BUFFER = "asobibatweaks_mending_buffer";
    private static final String CREDIT = "asobibatweaks_mending_repair_credit";
    private static final long UNIT = 1000000L;

    public MendingExtendedEvents() {}

    public static int reserve(ItemStack item) {
        CustomData custom = item.get(DataComponents.CUSTOM_DATA);
        return custom == null ? 0 : Math.max(0, custom.copyTag().getInt(BUFFER));
    }

    public static int maximum(ItemStack item) {
        if (!AsobibaTweaksConfig.GROWING_ENCHANTMENTS_ENABLED.getAsBoolean()
                || !item.isDamageableItem()) return 0;
        for (var enchantment : EnchantmentMasteryData.enchantments(item).keySet()) {
            if (!"minecraft:mending".equals(EnchantmentMasteryData.id(enchantment))) continue;
            int mastery = EnchantmentMasteryData.getMastery(item, enchantment);
            if (mastery < 50) return 0;
            double fraction = 0.05D + 0.15D * (Math.min(100, mastery) - 50) / 50.0D;
            return Math.max(1, (int)Math.round(item.getMaxDamage() * fraction));
        }
        return 0;
    }

    public static int absorb(ItemStack item, int amount) {
        if (amount <= 0 || !AsobibaTweaksConfig.GROWING_ENCHANTMENTS_ENABLED.getAsBoolean()) return amount;
        int saved = Math.min(amount, reserve(item));
        if (saved > 0) write(item, reserve(item) - saved, fractional(item));
        return amount - saved;
    }

    private static long fractional(ItemStack item) {
        CustomData custom = item.get(DataComponents.CUSTOM_DATA);
        return custom == null ? 0L : Math.max(0L, Math.min(UNIT - 1L, custom.copyTag().getLong(CREDIT)));
    }

    private static void write(ItemStack item, int buffer, long credit) {
        CustomData.update(DataComponents.CUSTOM_DATA, item, tag -> {
            if (buffer > 0) tag.putInt(BUFFER, buffer);
            else tag.remove(BUFFER);
            if (credit > 0L) tag.putLong(CREDIT, credit);
            else tag.remove(CREDIT);
        });
    }

    /** Returns -1 when no enhanced Mending behavior applies (use vanilla). */
    public static int distribute(ServerPlayer player, int receivedXp) {
        if (receivedXp <= 0) return -1;
        List<ItemStack> equipped = new ArrayList<>();
        IdentityHashMap<ItemStack, Boolean> identities = new IdentityHashMap<>();
        for (ItemStack armor : player.getArmorSlots()) unique(equipped, identities, armor);
        unique(equipped, identities, player.getMainHandItem());
        unique(equipped, identities, player.getOffhandItem());

        ItemStack source = ItemStack.EMPTY;
        int sourceLevel = 0;
        boolean anyBuffer = false;
        for (ItemStack stack : equipped) {
            if (!stack.isDamageableItem()) continue;
            int level = MendingLevelHelper.level(stack);
            if (level <= 0) continue;
            if (maximum(stack) > 0) anyBuffer = true;
            if (level >= 4 && (level > sourceLevel ||
                    (level == sourceLevel && wearRatio(stack) > wearRatio(source)))) {
                source = stack;
                sourceLevel = level;
            }
        }
        if (sourceLevel < 4 && !anyBuffer) return -1;

        List<ItemStack> recipients = new ArrayList<>(equipped);
        if (sourceLevel >= 10) {
            for (int i = 0; i < player.getInventory().getContainerSize(); i++) {
                unique(recipients, identities, player.getInventory().getItem(i));
            }
        }

        int left = receivedXp;
        for (int visit = 0; left > 0 && visit <= recipients.size() * 2; visit++) {
            ItemStack target = bestRecipient(recipients);
            if (target == null) break;

            int rate = MendingLevelHelper.durabilityPerXp(MendingLevelHelper.level(target));
            double factor = transferFactor(source, sourceLevel, target);
            double pointsPerXp = rate * factor;
            if (pointsPerXp <= 0.0D) break;

            int needed = target.getDamageValue() > 0
                    ? target.getDamageValue() : Math.max(0, maximum(target) - reserve(target));
            if (needed <= 0) break;
            long previousCredit = fractional(target);
            double xpForTarget = ((double)needed * UNIT - previousCredit) / (pointsPerXp * UNIT);
            int spend = Math.min(left, (int)Math.max(1L,
                    Math.min(Integer.MAX_VALUE, (long)Math.ceil(xpForTarget))));

            long units = previousCredit + (long)Math.floor(spend * pointsPerXp * UNIT);
            int whole = (int)Math.min(Integer.MAX_VALUE, units / UNIT);
            long restCredit = units % UNIT;
            int repaired = Math.min(target.getDamageValue(), whole);
            if (repaired > 0) target.setDamageValue(target.getDamageValue() - repaired);

            int extra = Math.min(Math.max(0, maximum(target) - reserve(target)), whole - repaired);
            int nextBuffer = reserve(target) + Math.max(0, extra);
            boolean moreRoom = target.getDamageValue() > 0 || nextBuffer < maximum(target);
            write(target, nextBuffer, moreRoom ? restCredit : 0L);
            left -= spend;
        }
        return left;
    }

    private static ItemStack bestRecipient(List<ItemStack> candidates) {
        ItemStack best = null;
        boolean damagedBest = false;
        double bestRatio = -1.0D;
        int bestLevel = -1;
        for (ItemStack stack : candidates) {
            int level = MendingLevelHelper.level(stack);
            if (level <= 0 || !stack.isDamageableItem()) continue;
            boolean damaged = stack.getDamageValue() > 0;
            if (!damaged && reserve(stack) >= maximum(stack)) continue;
            double ratio = damaged ? wearRatio(stack)
                    : 1.0D - reserve(stack) / (double)Math.max(1, maximum(stack));
            if (best == null || (damaged && !damagedBest)
                    || (damaged == damagedBest && (ratio > bestRatio
                            || (ratio == bestRatio && level > bestLevel)))) {
                best = stack;
                damagedBest = damaged;
                bestRatio = ratio;
                bestLevel = level;
            }
        }
        return best;
    }

    private static double transferFactor(ItemStack source, int level, ItemStack target) {
        if (level < 4 || source == target) return 1.0D;
        double route = switch (level) {
            case 4 -> 0.40D;
            case 5 -> 0.50D;
            case 6 -> 0.60D;
            case 7 -> 0.65D;
            case 8 -> 0.70D;
            case 9 -> 0.75D;
            default -> 0.80D;
        };
        double recipient = switch (Math.min(10, MendingLevelHelper.level(target))) {
            case 1 -> 0.50D;
            case 2 -> 0.55D;
            case 3 -> 0.60D;
            case 4 -> 0.66D;
            case 5 -> 0.72D;
            case 6 -> 0.78D;
            case 7 -> 0.84D;
            case 8 -> 0.90D;
            case 9 -> 0.95D;
            default -> 1.00D;
        };
        return route * recipient;
    }

    private static double wearRatio(ItemStack stack) {
        return stack.isEmpty() || stack.getMaxDamage() <= 0
                ? 0.0D : stack.getDamageValue() / (double)stack.getMaxDamage();
    }

    private static void unique(List<ItemStack> list, IdentityHashMap<ItemStack, Boolean> seen, ItemStack stack) {
        if (stack != null && !stack.isEmpty() && seen.put(stack, true) == null) list.add(stack);
    }

    @SubscribeEvent
    public void onTooltip(ItemTooltipEvent event) {
        int cap = maximum(event.getItemStack());
        if (cap > 0) {
            event.getToolTip().add(Component.literal(
                    "Mending Over-Repair: " + reserve(event.getItemStack()) + "/" + cap
            ).withStyle(ChatFormatting.AQUA));
        }
    }
}
